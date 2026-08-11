"""
Middleware ERP — Gestion entreprise courante + DB routing + audit automatique
"""
from django.shortcuts import redirect
from django.contrib import messages
from .models import AuditLog


BRAND_KEYS = {'siecle', 'lunea'}

class BrandContextMiddleware:
    """
    Détecte la marque active depuis le domaine ou le chemin.
    Injecte request.brand_key sur chaque requête.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().lower()
        path = request.path.lower()

        if 'lunea' in host or path.startswith('/lunea') or path.startswith('/api/v1/lunea'):
            request.brand_key = 'lunea'
        elif 'siecle' in host or path.startswith('/siecle') or path.startswith('/api/v1/siecle'):
            request.brand_key = 'siecle'
        else:
            brand_param = request.GET.get('brand', '') or request.POST.get('brand_key', '')
            request.brand_key = brand_param if brand_param in BRAND_KEYS else 'siecle'

        return self.get_response(request)


EXEMPT_URLS = [
    '/accounts/login/',
    '/accounts/logout/',
    '/accounts/register/',
    '/admin/',
    '/static/',
    '/media/',
    '/sites/',
]


class CompanyMiddleware:
    """
    Injecte l'entreprise courante dans la requête et configure le routing DB.
    - request.current_company  → instance Company active
    - request.company_db_alias → alias DB à utiliser pour les requêtes métier
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.current_company = None
        request.company_db_alias = 'default'

        if request.user.is_authenticated:
            self._resolve_company(request)

        # Définit l'alias DB thread-local pour le router
        from .db_router import set_company_db
        if request.current_company and request.current_company.database_created:
            from .company_database_service import (
                get_company_database_alias, ensure_company_database_exists
            )
            alias = get_company_database_alias(request.current_company)
            ensure_company_database_exists(request.current_company)
            set_company_db(alias)
            request.company_db_alias = alias
        else:
            set_company_db(None)

        response = self.get_response(request)

        # Nettoyage thread-local après réponse
        from .db_router import clear_company_db
        clear_company_db()

        return response

    def _resolve_company(self, request):
        """Résout l'entreprise active depuis la session ou l'utilisateur."""
        from .models import Company

        company_id = request.session.get('current_company_id')

        if company_id:
            try:
                if request.user.is_superuser:
                    request.current_company = Company.objects.get(pk=company_id, is_active=True)
                else:
                    request.current_company = request.user.profile.companies.get(
                        pk=company_id, is_active=True
                    )
            except Exception:
                request.session.pop('current_company_id', None)

        # Fallback : première entreprise disponible
        if not request.current_company:
            try:
                if request.user.is_superuser:
                    company = Company.objects.filter(is_active=True).first()
                else:
                    company = request.user.profile.companies.filter(is_active=True).first()

                if company:
                    request.current_company = company
                    request.session['current_company_id'] = company.pk
            except Exception:
                pass


class AuditLogMiddleware:
    """Enregistre les connexions/déconnexions dans l'audit."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')


class NoCacheMiddleware:
    """
    Empêche la mise en cache des pages ERP dynamiques (authentifiées) par le
    navigateur ou par une WebView embarquée (ex. app desktop Qt WebEngine).

    Sans ça, un déploiement de code peut rester invisible indéfiniment côté
    client : sans en-tête Cache-Control explicite, certains moteurs (dont Qt
    WebEngine) appliquent une mise en cache heuristique et un simple F5 ne
    revalide jamais avec le serveur — seul un rechargement forçant le
    contournement du cache (Ctrl+Maj+R) le ferait, et l'app desktop n'expose
    pas forcément ce raccourci.

    Les sites publics (request.website défini) et les utilisateurs anonymes
    ne sont pas concernés — seules les pages ERP authentifiées le sont.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated and not getattr(request, 'website', None):
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
        return response


_setup_complete_cache = False


class SetupRequiredMiddleware:
    """
    Redirige vers l'assistant de premier accès (/setup/) tant qu'aucune
    Company n'existe en base — remplace l'ancien wizard de première
    connexion (console série de l'appliance Proxmox) par un formulaire web,
    comme la plupart des logiciels auto-hébergés (Nextcloud, WordPress...).
    """

    ALLOWED_PREFIXES = (
        '/setup/',
        '/static/',
        '/media/',
        '/ha/health/',
        '/ha/public-health/',
        '/admin/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        global _setup_complete_cache

        if not _setup_complete_cache:
            from .models import Company
            try:
                _setup_complete_cache = Company.objects.exists()
            except Exception:
                # Base pas encore migrée/accessible : ne pas bloquer dessus.
                return self.get_response(request)

        is_setup_path = request.path.startswith('/setup/')

        if _setup_complete_cache:
            if is_setup_path:
                return redirect('/')
            return self.get_response(request)

        if any(request.path.startswith(p) for p in self.ALLOWED_PREFIXES):
            return self.get_response(request)
        return redirect('/setup/')


class MaintenanceModeMiddleware:
    """Retourne 503 pendant la maintenance, sauf pour les Super Admin et chemins critiques."""

    ALLOWED_PREFIXES = (
        '/admin/',
        '/orion-admin/',
        '/ha/health/',
        '/accounts/login/',
        '/accounts/logout/',
        '/static/',
        '/media/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from apps.core.maintenance import is_maintenance_mode_enabled
        if is_maintenance_mode_enabled():
            if any(request.path.startswith(p) for p in self.ALLOWED_PREFIXES):
                return self.get_response(request)
            user = getattr(request, 'user', None)
            if user and user.is_authenticated and user.is_superuser:
                return self.get_response(request)
            from django.http import HttpResponse
            return HttpResponse(
                """<!DOCTYPE html>
<html lang="fr">
<head><meta charset="utf-8"><title>Maintenance — Orion ERP</title>
<style>body{font-family:system-ui,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#f8f9fa}
.box{text-align:center;padding:60px;max-width:480px}h1{font-size:24px;font-weight:700;margin-bottom:12px}
p{color:#6c757d;font-size:15px;line-height:1.6}</style></head>
<body><div class="box">
<svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#6c757d" stroke-width="1.5" style="margin-bottom:24px"><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg>
<h1>Maintenance en cours</h1>
<p>Orion ERP est temporairement indisponible pour une maintenance programmée.<br>Veuillez réessayer dans quelques minutes.</p>
</div></body></html>""",
                status=503,
                content_type='text/html; charset=utf-8',
            )
        return self.get_response(request)
