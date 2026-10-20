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

        # Fallback : dernière entreprise mémorisée sur le profil (persiste
        # au-delà de la session — évite de retomber au hasard sur la
        # première entreprise par ordre alphabétique à chaque nouvelle
        # session, ex. après une purge des sessions côté serveur).
        if not request.current_company:
            try:
                profile_company = request.user.profile.current_company
                if profile_company and profile_company.is_active and (
                    request.user.is_superuser
                    or request.user.profile.companies.filter(pk=profile_company.pk).exists()
                ):
                    request.current_company = profile_company
                    request.session['current_company_id'] = profile_company.pk
            except Exception:
                pass

        # Fallback ultime : première entreprise disponible
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

        # Mémorise le choix résolu sur le profil pour qu'il reste sticky
        # même si la session est perdue/purgée.
        if request.current_company:
            try:
                profile = request.user.profile
                if profile.current_company_id != request.current_company.pk:
                    profile.current_company = request.current_company
                    profile.save(update_fields=['current_company'])
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
        # Validation reciproque entre serveurs : doit repondre meme avant
        # que l'assistant de premier acces n'ait ete complete, sinon un
        # serveur neuf ne peut pas etre valide pour entrer dans la grappe.
        '/ha/join-check/',
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


def _page_de_maintenance():
    """La page 503, nourrie de l'annonce en cours s'il y en a une.

    **Tolérante par construction.** Elle s'affiche justement quand le
    serveur est en travaux : la base peut être en cours de migration, la
    table des annonces pas encore créée, le gabarit absent d'un déploiement
    partiel. Chacun de ces cas doit donner une page lisible, pas une
    erreur 500 — une panne DANS la page de panne est le pire moment pour
    découvrir une exception.

    503 et non 200 : c'est le code que les navigateurs, les moteurs et les
    sondes de surveillance comprennent comme « indisponible, réessayez »,
    là où un 200 ferait croire au service rendu.
    """
    from django.http import HttpResponse
    from django.template.loader import render_to_string

    contexte = {'motif': '', 'message': '', 'fin_prevue': None}
    try:
        from apps.core.models import MaintenanceAnnonce

        annonce = MaintenanceAnnonce.courante()
        if annonce is not None:
            contexte = {
                'motif': f'{annonce.get_motif_display()} en cours',
                'message': annonce.message or '',
                'fin_prevue': annonce.fin_prevue,
            }
    except Exception:
        # Base indisponible, table absente, migration en cours : on affiche
        # la page generique. C'est exactement la situation que cette page
        # est censee couvrir.
        pass

    try:
        corps = render_to_string('maintenance.html', contexte)
    except Exception:
        corps = (
            '<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">'
            '<meta http-equiv="refresh" content="20">'
            '<title>Maintenance — Orion ERP</title></head><body '
            'style="font-family:system-ui,sans-serif;text-align:center;'
            'padding:80px 24px">'
            '<h1>Maintenance en cours</h1>'
            '<p>Orion ERP est momentanément indisponible. Vos données ne '
            'sont pas affectées. Cette page se recharge toute seule.</p>'
            '</body></html>')

    return HttpResponse(corps, status=503,
                        content_type='text/html; charset=utf-8')


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
            # Place apres AuthenticationMiddleware, request.user existe --
            # mais y toucher interroge la session, donc la base. Or cette
            # page s'affiche justement quand la base peut etre en cours de
            # migration : une exception ici ferait echouer la page de panne
            # elle-meme. En cas de doute, on bloque : c'est le choix sur.
            try:
                user = getattr(request, 'user', None)
                est_super_admin = bool(
                    user and user.is_authenticated and user.is_superuser)
            except Exception:
                est_super_admin = False
            if est_super_admin:
                return self.get_response(request)
            return _page_de_maintenance()
        return self.get_response(request)
