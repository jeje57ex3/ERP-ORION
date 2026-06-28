"""
apps/core/security.py — Mixins de sécurité Orion ERP

Utilisation dans les vues :
    class ClientListView(LoginRequiredMixin, CompanyRequiredMixin, ListView):
        ...
"""
import logging
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib import messages

logger = logging.getLogger('orion')


def get_current_company(request):
    """Retourne l'entreprise active de la requête courante."""
    return getattr(request, 'current_company', None)


def check_user_company_access(user, company):
    """Vérifie qu'un utilisateur a accès à une entreprise donnée."""
    if user.is_superuser:
        return True
    try:
        return user.profile.companies.filter(pk=company.pk, is_active=True).exists()
    except Exception:
        return False


class CompanyRequiredMixin:
    """
    Exige qu'une entreprise active soit définie dans la requête.
    Redirige vers le sélecteur d'entreprise si aucune n'est active.
    """

    def dispatch(self, request, *args, **kwargs):
        if not getattr(request, 'current_company', None):
            messages.warning(request, "Aucune entreprise sélectionnée. Veuillez choisir une entreprise.")
            return redirect('core:company_list')
        return super().dispatch(request, *args, **kwargs)


class ViewPermissionRequiredMixin:
    """
    Vérifie qu'un utilisateur a la permission Django requise.

    Utilisation :
        class MyView(ViewPermissionRequiredMixin, ListView):
            permission_code = 'crm.view_customer'
    """
    permission_code = None

    def dispatch(self, request, *args, **kwargs):
        if self.permission_code and not request.user.has_perm(self.permission_code):
            logger.warning(
                "Accès refusé: user=%s permission=%s url=%s",
                request.user, self.permission_code, request.path
            )
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class CompanyObjectMixin:
    """
    Vérifie que l'objet récupéré appartient à l'entreprise active.
    À utiliser avec DetailView, UpdateView, DeleteView.
    """

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        company = get_current_company(self.request)
        if company and hasattr(obj, 'company_id') and obj.company_id != company.pk:
            logger.warning(
                "Tentative d'accès cross-entreprise: user=%s obj=%s company=%s",
                self.request.user, obj, company
            )
            raise PermissionDenied
        return obj


class OrionBaseView(LoginRequiredMixin, CompanyRequiredMixin):
    """Mixin de base pour toutes les vues métier Orion."""
    pass


class OrionPermissionView(LoginRequiredMixin, CompanyRequiredMixin, ViewPermissionRequiredMixin):
    """Mixin pour les vues avec permission explicite."""
    pass
