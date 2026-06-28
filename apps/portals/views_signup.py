"""
Vues d'inscription au portail client + gestion admin ERP des demandes.

Routes publiques (namespace client_portal) :
  /client/inscription/                      → ClientRegisterView
  /client/inscription/succes/               → ClientRegisterSuccessView
  /client/verification-email/<token>/       → ClientVerifyEmailView

Routes ERP admin (namespace portals) :
  /portails/inscriptions/                   → ClientSignupRequestListView
  /portails/inscriptions/<pk>/              → ClientSignupRequestDetailView
  /portails/inscriptions/<pk>/valider/      → ApproveClientSignupView
  /portails/inscriptions/<pk>/refuser/      → RejectClientSignupView
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.http import HttpResponseBadRequest
from django.core.paginator import Paginator

from .models import ClientPortalSettings, ClientPortalSignupRequest
from .forms import ClientPortalSignupForm, RejectSignupForm
from .services import signup_service
from .services.rate_limit_service import can_submit_signup, record_signup_attempt


def _get_company(request):
    return getattr(request, 'current_company', None)


def _get_company_for_public(request):
    """
    Résout l'entreprise pour les vues publiques (client non authentifié).
    Le middleware ne résout la company que pour les users ERP authentifiés.
    Pour les portails publics on cherche la première company active en fallback.
    """
    company = _get_company(request)
    if company is None:
        from apps.core.models import Company
        company = Company.objects.filter(is_active=True).first()
    return company


def _get_portal_settings(company):
    return ClientPortalSettings.get_for_company(company) if company else None


# ═══════════════════════════════════════════════════════════════════════════════
# VUES PUBLIQUES
# ═══════════════════════════════════════════════════════════════════════════════

class ClientRegisterView(View):
    """Affiche et traite le formulaire d'inscription au portail client."""

    template_name = 'client_portal/register.html'

    def _check_allowed(self, company, portal_settings):
        if company is None:
            return False, 'Portail client introuvable. Vérifiez l\'adresse.'
        if portal_settings is None or not portal_settings.allow_client_registration:
            return False, 'Les inscriptions ne sont pas ouvertes pour le moment.'
        return True, None

    def get(self, request):
        company = _get_company_for_public(request)
        portal_settings = _get_portal_settings(company)
        allowed, error = self._check_allowed(company, portal_settings)
        if not allowed:
            return render(request, self.template_name, {
                'company': company,
                'portal_settings': portal_settings,
                'error': error,
            })
        form = ClientPortalSignupForm()
        return render(request, self.template_name, {
            'form': form,
            'company': company,
            'portal_settings': portal_settings,
        })

    def post(self, request):
        company = _get_company_for_public(request)
        portal_settings = _get_portal_settings(company)

        # Honeypot anti-spam (vérifier en premier, silencieusement)
        if request.POST.get('website'):
            return redirect('client_portal:register_success')

        allowed, error = self._check_allowed(company, portal_settings)
        if not allowed:
            return render(request, self.template_name, {
                'company': company,
                'portal_settings': portal_settings,
                'error': error,
            })

        form = ClientPortalSignupForm(request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {
                'form': form,
                'company': company,
                'portal_settings': portal_settings,
            })

        email = form.cleaned_data['email']
        ip = signup_service._get_client_ip(request)

        # Rate limiting
        allowed_rate, rate_msg = can_submit_signup(ip, email)
        if not allowed_rate:
            form.add_error(None, rate_msg)
            return render(request, self.template_name, {
                'form': form,
                'company': company,
                'portal_settings': portal_settings,
            })

        record_signup_attempt(ip, email)

        try:
            signup = signup_service.create_signup_request(company, form.cleaned_data, request)
        except ValueError as exc:
            form.add_error(None, str(exc))
            return render(request, self.template_name, {
                'form': form,
                'company': company,
                'portal_settings': portal_settings,
            })

        # Envoyer email de vérification si nécessaire
        if portal_settings and portal_settings.registration_requires_email_verification:
            base_url = request.build_absolute_uri('/').rstrip('/')
            signup_service.send_email_verification(signup, base_url=base_url)
        elif portal_settings and portal_settings.registration_requires_approval:
            # Pas de vérif email mais approval requise → notifier admins
            signup_service.notify_company_admins(signup)

        request.session['signup_email'] = email
        request.session['signup_needs_verification'] = (
            portal_settings.registration_requires_email_verification if portal_settings else True
        )
        request.session['signup_needs_approval'] = (
            portal_settings.registration_requires_approval if portal_settings else True
        )

        return redirect('client_portal:register_success')


class ClientRegisterSuccessView(View):
    """Page de confirmation après soumission du formulaire d'inscription."""

    template_name = 'client_portal/register_success.html'

    def get(self, request):
        company = _get_company_for_public(request)
        email = request.session.pop('signup_email', None)
        needs_verification = request.session.pop('signup_needs_verification', True)
        needs_approval = request.session.pop('signup_needs_approval', True)

        return render(request, self.template_name, {
            'company': company,
            'email': email,
            'needs_verification': needs_verification,
            'needs_approval': needs_approval,
        })


class ClientVerifyEmailView(View):
    """Vérifie le token email et affiche le résultat."""

    template_name = 'client_portal/verify_email.html'

    def get(self, request, token: str):
        company = _get_company_for_public(request)
        signup, error = signup_service.verify_signup_email(token)

        if error:
            return render(request, self.template_name, {
                'company': company,
                'success': False,
                'error': error,
            })

        needs_approval = (
            signup.status == ClientPortalSignupRequest.STATUS_PENDING_APPROVAL
        )
        is_active = signup.status == ClientPortalSignupRequest.STATUS_CONVERTED

        return render(request, self.template_name, {
            'company': company,
            'success': True,
            'needs_approval': needs_approval,
            'is_active': is_active,
            'signup': signup,
        })


# ═══════════════════════════════════════════════════════════════════════════════
# VUES ERP ADMIN
# ═══════════════════════════════════════════════════════════════════════════════

@method_decorator(login_required, name='dispatch')
class ClientSignupRequestListView(View):
    """Liste des demandes d'inscription pour l'entreprise courante (ERP)."""

    template_name = 'client_portal/admin/signup_list.html'

    def get(self, request):
        company = _get_company(request)
        status_filter = request.GET.get('status', '')
        qs = ClientPortalSignupRequest.objects.filter(company=company).select_related(
            'approved_by', 'rejected_by', 'linked_portal_account',
        )
        if status_filter:
            qs = qs.filter(status=status_filter)

        paginator = Paginator(qs, 25)
        page_obj = paginator.get_page(request.GET.get('page'))

        pending_count = ClientPortalSignupRequest.objects.filter(
            company=company,
            status=ClientPortalSignupRequest.STATUS_PENDING_APPROVAL,
        ).count()

        return render(request, self.template_name, {
            'page_obj': page_obj,
            'status_filter': status_filter,
            'status_choices': ClientPortalSignupRequest.STATUS_CHOICES,
            'pending_count': pending_count,
            'page_title': 'Demandes d\'inscription client',
            'company': company,
        })


@method_decorator(login_required, name='dispatch')
class ClientSignupRequestDetailView(View):
    """Détail d'une demande d'inscription (ERP)."""

    template_name = 'client_portal/admin/signup_detail.html'

    def get(self, request, pk: int):
        company = _get_company(request)
        signup = get_object_or_404(ClientPortalSignupRequest, pk=pk, company=company)
        activities = signup.activities.all()[:20]
        reject_form = RejectSignupForm()
        return render(request, self.template_name, {
            'signup': signup,
            'activities': activities,
            'reject_form': reject_form,
            'page_title': f'Inscription — {signup.full_name}',
            'company': company,
        })


@method_decorator(login_required, name='dispatch')
class ApproveClientSignupView(View):
    """Valide une demande d'inscription et crée le compte portail (POST)."""

    def post(self, request, pk: int):
        company = _get_company(request)
        signup = get_object_or_404(ClientPortalSignupRequest, pk=pk, company=company)

        portal_settings = _get_portal_settings(company)
        if (portal_settings and portal_settings.registration_requires_email_verification
                and not signup.email_verified):
            messages.error(request, 'L\'email du client n\'a pas encore été vérifié.')
            return redirect('portals:signup_detail', pk=pk)

        if signup.status not in (
            ClientPortalSignupRequest.STATUS_PENDING_APPROVAL,
            ClientPortalSignupRequest.STATUS_PENDING_EMAIL,
        ):
            messages.warning(request, f'Cette demande ne peut pas être validée (statut : {signup.get_status_display()}).')
            return redirect('portals:signup_detail', pk=pk)

        try:
            account = signup_service.approve_signup_request(signup, approved_by=request.user)
            messages.success(
                request,
                f'Compte portail créé pour {account.full_name}. Un email d\'activation a été envoyé.',
            )
        except Exception as exc:
            messages.error(request, f'Erreur lors de la validation : {exc}')

        return redirect('portals:signup_list')


@method_decorator(login_required, name='dispatch')
class RejectClientSignupView(View):
    """Refuse une demande d'inscription (POST avec raison optionnelle)."""

    def post(self, request, pk: int):
        company = _get_company(request)
        signup = get_object_or_404(ClientPortalSignupRequest, pk=pk, company=company)

        if signup.status not in ClientPortalSignupRequest.ACTIVE_STATUSES:
            messages.warning(request, f'Cette demande ne peut pas être refusée (statut : {signup.get_status_display()}).')
            return redirect('portals:signup_detail', pk=pk)

        form = RejectSignupForm(request.POST)
        if form.is_valid():
            reason = form.cleaned_data.get('reason', '')
            signup_service.reject_signup_request(signup, rejected_by=request.user, reason=reason)
            messages.success(request, f'La demande de {signup.full_name} a été refusée.')
        else:
            messages.error(request, 'Formulaire invalide.')

        return redirect('portals:signup_list')
