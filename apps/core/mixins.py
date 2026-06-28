"""
apps/core/mixins.py — Mixins pour Class-Based Views Orion ERP

Ces mixins s'appliquent aux vues Django (ListView, DetailView, CreateView, etc.)
pour injecter automatiquement le contexte multi-tenant, vérifier les permissions
et journaliser les actions.

Ordre d'héritage recommandé (MRO Django) :
    class MaVue(ModuleAccessMixin, CreateView):
        module_code = 'sales'
        model = Invoice
        ...
"""
import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect

logger = logging.getLogger('orion.views')


class CompanyMixin:
    """
    Mixin de base pour les CBVs : injecte l'entreprise active et filtre
    automatiquement les QuerySets par entreprise.

    Fournit :
        - get_company()       → instance Company active ou None
        - get_queryset()      → filtré par entreprise
        - get_context_data()  → injecte 'current_company' dans le contexte
        - form_valid()        → assigne automatiquement l'entreprise aux nouveaux objets
    """

    def get_company(self):
        """Retourne l'entreprise active depuis la requête (injectée par CompanyMiddleware)."""
        return getattr(self.request, 'current_company', None)

    def get_queryset(self):
        """
        Filtre le QuerySet par entreprise.
        Utilise for_company() si disponible (CompanyManager), sinon filtre sur company.
        """
        qs = super().get_queryset()
        company = self.get_company()
        if company is None:
            return qs.none()
        if hasattr(qs, 'for_company'):
            return qs.for_company(company)
        return qs.filter(company=company)

    def get_context_data(self, **kwargs):
        """Ajoute l'entreprise courante au contexte de template."""
        ctx = super().get_context_data(**kwargs)
        ctx['current_company'] = self.get_company()
        return ctx

    def form_valid(self, form):
        """
        Assigne automatiquement l'entreprise active à l'objet si le champ est vide.
        Évite d'avoir à le faire dans chaque vue Create.
        """
        if hasattr(form.instance, 'company') and not form.instance.company_id:
            form.instance.company = self.get_company()
        return super().form_valid(form)


class LoginAndCompanyMixin(LoginRequiredMixin, CompanyMixin):
    """
    Combinaison LoginRequiredMixin + CompanyMixin.

    Redirige vers la page de connexion si l'utilisateur n'est pas authentifié.
    Hérite du filtrage par entreprise de CompanyMixin.
    """

    login_url = '/accounts/login/'
    redirect_field_name = 'next'


class ModuleAccessMixin(LoginAndCompanyMixin):
    """
    Vérifie que l'utilisateur a accès au module ERP requis.

    Définir module_code dans la vue fille :
        class InvoiceListView(ModuleAccessMixin, ListView):
            module_code = 'sales'
            model = Invoice

    Les superusers passent sans vérification de permission.
    """

    module_code = None  # À définir dans la vue fille

    def dispatch(self, request, *args, **kwargs):
        """
        Intercepte la requête avant le traitement de la vue.
        Vérifie login, entreprise active et accès au module.
        """
        # Vérification login (héritée de LoginRequiredMixin via LoginAndCompanyMixin)
        response = super().dispatch(request, *args, **kwargs)

        # Si LoginRequiredMixin a redirigé, on retourne directement
        if not request.user.is_authenticated:
            return response

        company = self.get_company()

        # Les superusers ont accès à tout
        if request.user.is_superuser:
            return response

        # Vérification de l'accès au module
        if self.module_code:
            if not company:
                messages.error(request, "Aucune entreprise sélectionnée.")
                return redirect('core:dashboard')
            try:
                from apps.access_control.services import user_has_module_access
                if not user_has_module_access(request.user, company, self.module_code):
                    messages.error(
                        request,
                        f"Accès au module '{self.module_code}' non autorisé."
                    )
                    return redirect('core:dashboard')
            except ImportError:
                logger.warning(
                    'apps.access_control.services introuvable — vérification module ignorée'
                )

        return response


class AuditMixin:
    """
    Ajoute un journal d'audit automatique sur les actions create/update/delete.

    Définir audit_module dans la vue fille :
        class InvoiceCreateView(AuditMixin, CreateView):
            audit_module = 'sales'
            model = Invoice

    Pour personnaliser la description, surcharger get_audit_description().
    """

    audit_module: str = ''

    def get_audit_module(self) -> str:
        """Retourne le code module pour l'audit. Peut être surchargé."""
        return self.audit_module

    def get_audit_description(self, action: str, obj) -> str:
        """Retourne la description de l'entrée d'audit. Peut être surchargé."""
        labels = {'create': 'Création', 'update': 'Modification', 'delete': 'Suppression'}
        label = labels.get(action, action.capitalize())
        model_name = obj.__class__.__name__
        return f'{label} de {model_name} : {obj}'

    def _write_audit(self, action: str, obj):
        """Écrit l'entrée d'audit via AuditLog."""
        from apps.core.models import AuditLog
        from apps.core.utils import get_client_ip

        company = getattr(self.request, 'current_company', None)
        user = self.request.user if self.request.user.is_authenticated else None

        try:
            AuditLog.objects.create(
                user=user,
                company=company,
                action=action,
                module=self.get_audit_module(),
                model_name=obj.__class__.__name__,
                object_id=str(obj.pk) if obj.pk else '',
                object_repr=str(obj)[:200],
                description=self.get_audit_description(action, obj),
                ip_address=get_client_ip(self.request),
            )
        except Exception as exc:
            logger.warning('Échec écriture audit (%s %s) : %s', action, obj, exc)

    def form_valid(self, form):
        """Journalise la création ou la modification après sauvegarde du formulaire."""
        is_new = not form.instance.pk
        response = super().form_valid(form)
        action = 'create' if is_new else 'update'
        self._write_audit(action, form.instance)
        return response

    def delete(self, request, *args, **kwargs):
        """Journalise la suppression avant suppression effective."""
        obj = self.get_object()
        self._write_audit('delete', obj)
        return super().delete(request, *args, **kwargs)


class PaginationMixin:
    """
    Mixin de pagination avec taille de page configurable via paramètre GET.

    Exemples d'URL :
        /invoices/?page=2
        /invoices/?page=3&page_size=50
    """

    from apps.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

    paginate_by = DEFAULT_PAGE_SIZE
    max_page_size = MAX_PAGE_SIZE

    def get_paginate_by(self, queryset):
        """Permet de surcharger la taille de page via le paramètre GET 'page_size'."""
        try:
            page_size = int(self.request.GET.get('page_size', self.paginate_by))
            return min(max(1, page_size), self.max_page_size)
        except (ValueError, TypeError):
            return self.paginate_by

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['current_page_size'] = self.get_paginate_by(None)
        from apps.core.constants import PAGE_SIZE_CHOICES
        ctx['page_size_choices'] = PAGE_SIZE_CHOICES
        return ctx


class SearchMixin:
    """
    Mixin pour les ListViews avec recherche textuelle via le paramètre GET 'q'.

    Surcharger search_fields pour définir les champs à interroger :
        class CustomerListView(SearchMixin, ListView):
            search_fields = ['name', 'email', 'phone']
    """

    search_fields: list = []
    search_param: str = 'q'

    def get_search_query(self) -> str:
        """Retourne la chaîne de recherche depuis les paramètres GET."""
        return self.request.GET.get(self.search_param, '').strip()

    def get_queryset(self):
        qs = super().get_queryset()
        query = self.get_search_query()
        if query and self.search_fields:
            from django.db.models import Q
            conditions = Q()
            for field in self.search_fields:
                conditions |= Q(**{f'{field}__icontains': query})
            qs = qs.filter(conditions)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['search_query'] = self.get_search_query()
        ctx['search_param'] = self.search_param
        return ctx
