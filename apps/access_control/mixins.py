"""
access_control/mixins.py
Mixins Django pour les class-based views.
"""
from django.shortcuts import redirect
from django.contrib import messages
from .services import user_has_module_access, user_has_view_access, user_has_action_access


class CompanyAccessRequiredMixin:
    """Vérifie que l'utilisateur est bien rattaché à une entreprise active."""
    def dispatch(self, request, *args, **kwargs):
        company = getattr(request, 'current_company', None)
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not company:
            messages.error(request, "Aucune entreprise sélectionnée.")
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)


class ModuleAccessRequiredMixin(CompanyAccessRequiredMixin):
    module_code = None

    def dispatch(self, request, *args, **kwargs):
        result = super().dispatch(request, *args, **kwargs)
        if hasattr(result, 'status_code') and result.status_code in (301, 302):
            return result
        company = getattr(request, 'current_company', None)
        if self.module_code and not user_has_module_access(request.user, company, self.module_code):
            messages.error(request, f"Accès au module « {self.module_code} » refusé.")
            return redirect('core:dashboard')
        return result


class ViewAccessRequiredMixin(CompanyAccessRequiredMixin):
    view_code = None

    def dispatch(self, request, *args, **kwargs):
        result = super().dispatch(request, *args, **kwargs)
        if hasattr(result, 'status_code') and result.status_code in (301, 302):
            return result
        company = getattr(request, 'current_company', None)
        if self.view_code and not user_has_view_access(request.user, company, self.view_code):
            messages.error(request, "Accès à cette page refusé.")
            return redirect('core:dashboard')
        return result


class ActionAccessRequiredMixin(CompanyAccessRequiredMixin):
    module_code = None
    action_code = None

    def dispatch(self, request, *args, **kwargs):
        result = super().dispatch(request, *args, **kwargs)
        if hasattr(result, 'status_code') and result.status_code in (301, 302):
            return result
        company = getattr(request, 'current_company', None)
        if self.module_code and self.action_code:
            if not user_has_action_access(request.user, company, self.module_code, self.action_code):
                messages.error(request, "Vous n'avez pas la permission d'effectuer cette action.")
                return redirect('core:dashboard')
        return result


class ObjectCompanyFilterMixin:
    """Filtre automatique des querysets par entreprise courante."""
    def get_queryset(self):
        qs = super().get_queryset()
        company = getattr(self.request, 'current_company', None)
        if company and hasattr(qs.model, 'company'):
            return qs.filter(company=company)
        return qs
