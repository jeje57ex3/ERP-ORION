"""
Service d'inscription au portail client.

Workflow :
  1. client remplit formulaire
  2. créer ClientPortalSignupRequest
  3. envoyer email de vérification
  4. client clique lien email → statut pending_approval
  5. admin valide → créer ClientPortalAccount
  6. envoyer email d'activation
  7. client peut se connecter
"""
import secrets
import logging
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


# ── Helpers privés ────────────────────────────────────────────────────────────

def _get_client_ip(request) -> str:
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '127.0.0.1')


def _log_activity(company, action: str, email: str, signup_request=None,
                  performed_by=None, ip_address=None, notes='') -> None:
    try:
        from apps.portals.models import ClientPortalActivity
        ClientPortalActivity.objects.create(
            company=company,
            action=action,
            email=email,
            signup_request=signup_request,
            performed_by=performed_by,
            ip_address=ip_address,
            notes=notes,
        )
    except Exception as exc:
        logger.warning('ClientPortalActivity log failed: %s', exc)


def _send_email(subject: str, template: str, context: dict, recipient: str) -> None:
    try:
        html = render_to_string(template, context)
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@orion-erp.fr')
        send_mail(
            subject=subject,
            message='',
            from_email=from_email,
            recipient_list=[recipient],
            html_message=html,
            fail_silently=True,
        )
    except Exception as exc:
        logger.warning('Email send failed (%s → %s): %s', template, recipient, exc)


# ── API publique ──────────────────────────────────────────────────────────────

def create_signup_request(company, form_data: dict, request):
    """
    Crée une demande d'inscription après validation du formulaire.

    Raises ValueError si une demande active existe déjà pour cet email.
    """
    from apps.portals.models import ClientPortalSignupRequest, ClientPortalSettings

    email = form_data['email'].lower().strip()

    # Vérifier unicité des demandes actives
    existing = ClientPortalSignupRequest.objects.filter(
        company=company,
        email=email,
        status__in=ClientPortalSignupRequest.ACTIVE_STATUSES,
    ).first()
    if existing:
        raise ValueError(
            'Une demande est déjà en cours pour cette adresse email. '
            'Vérifiez votre boîte mail ou contactez l\'entreprise.'
        )

    # Vérifier si l'email est inconnu et si c'est autorisé
    portal_settings = ClientPortalSettings.get_for_company(company)
    if portal_settings and not portal_settings.allow_unknown_clients:
        customer = find_existing_customer(company, email)
        if customer is None:
            raise ValueError(
                'Nous n\'avons pas trouvé de dossier client associé à cette adresse email. '
                'Veuillez contacter l\'entreprise.'
            )

    token = secrets.token_urlsafe(48)
    ip = _get_client_ip(request)

    needs_email_verification = (
        portal_settings.registration_requires_email_verification
        if portal_settings else True
    )
    initial_status = (
        ClientPortalSignupRequest.STATUS_PENDING_EMAIL
        if needs_email_verification
        else ClientPortalSignupRequest.STATUS_PENDING_APPROVAL
    )

    signup = ClientPortalSignupRequest.objects.create(
        company=company,
        first_name=form_data['first_name'].strip(),
        last_name=form_data['last_name'].strip(),
        email=email,
        phone=form_data.get('phone', '').strip(),
        company_name=form_data.get('company_name', '').strip(),
        message=form_data.get('message', '').strip(),
        password_hash=make_password(form_data['password']),
        email_verification_token=token,
        status=initial_status,
        ip_address=ip,
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
    )

    _log_activity(company, 'signup_created', email, signup, ip_address=ip)

    # Lier au client CRM existant si trouvé
    customer = find_existing_customer(company, email)
    if customer:
        signup.linked_customer_id = customer.pk
        signup.save(update_fields=['linked_customer_id'])

    return signup


def send_email_verification(signup_request, base_url: str = '') -> None:
    """Envoie l'email de vérification avec le lien tokenisé."""
    from django.urls import reverse

    if base_url:
        verify_path = reverse('client_portal:verify_email', kwargs={'token': signup_request.email_verification_token})
        verification_url = base_url.rstrip('/') + verify_path
    else:
        verification_url = f'/client/verification-email/{signup_request.email_verification_token}/'

    signup_request.email_verification_sent_at = timezone.now()
    signup_request.save(update_fields=['email_verification_sent_at'])

    _send_email(
        subject=f'Confirmez votre adresse email — {signup_request.company.name}',
        template='client_portal/emails/client_verify_email.html',
        context={
            'first_name': signup_request.first_name,
            'verification_url': verification_url,
            'company': signup_request.company,
        },
        recipient=signup_request.email,
    )


def verify_signup_email(token: str):
    """
    Vérifie le token email et fait progresser le statut de la demande.

    Returns:
        (signup_request, None) si succès
        (None, message_erreur) si échec
    """
    from apps.portals.models import ClientPortalSignupRequest, ClientPortalSettings

    try:
        signup = ClientPortalSignupRequest.objects.select_related('company').get(
            email_verification_token=token,
            status=ClientPortalSignupRequest.STATUS_PENDING_EMAIL,
        )
    except ClientPortalSignupRequest.DoesNotExist:
        return None, 'Ce lien de vérification est invalide ou a déjà été utilisé.'

    signup.email_verified = True

    portal_settings = ClientPortalSettings.get_for_company(signup.company)
    needs_approval = portal_settings.registration_requires_approval if portal_settings else True

    if needs_approval:
        signup.status = ClientPortalSignupRequest.STATUS_PENDING_APPROVAL
        signup.save(update_fields=['email_verified', 'status'])
        _log_activity(signup.company, 'signup_email_verified', signup.email, signup)
        # Notifier les admins
        notify_company_admins(signup)
        _send_email(
            subject=f'Votre demande est en attente de validation — {signup.company.name}',
            template='client_portal/emails/client_signup_pending_admin.html',
            context={'first_name': signup.first_name, 'company': signup.company},
            recipient=signup.email,
        )
    else:
        # Validation auto sans approval
        signup.status = ClientPortalSignupRequest.STATUS_APPROVED
        signup.approved_at = timezone.now()
        signup.save(update_fields=['email_verified', 'status', 'approved_at'])
        _log_activity(signup.company, 'signup_email_verified', signup.email, signup)
        approve_signup_request(signup, approved_by=None)

    return signup, None


def approve_signup_request(signup_request, approved_by):
    """
    Valide une demande d'inscription et crée le compte portail.

    Returns: ClientPortalAccount
    """
    from apps.portals.models import ClientPortalSignupRequest as _SR
    if approved_by:
        signup_request.approved_by = approved_by
        signup_request.approved_at = timezone.now()
        signup_request.status = _SR.STATUS_APPROVED
        signup_request.save(update_fields=['status', 'approved_by', 'approved_at'])

    account = convert_signup_to_portal_account(signup_request)
    _log_activity(
        signup_request.company, 'signup_approved', signup_request.email,
        signup_request, performed_by=approved_by,
    )
    return account


def reject_signup_request(signup_request, rejected_by, reason: str = '') -> None:
    """Refuse une demande d'inscription."""
    from apps.portals.models import ClientPortalSignupRequest
    signup_request.status = ClientPortalSignupRequest.STATUS_REJECTED
    signup_request.rejected_by = rejected_by
    signup_request.rejected_at = timezone.now()
    signup_request.rejection_reason = reason or ''
    signup_request.save(update_fields=['status', 'rejected_by', 'rejected_at', 'rejection_reason'])

    _log_activity(
        signup_request.company, 'signup_rejected', signup_request.email,
        signup_request, performed_by=rejected_by, notes=reason,
    )

    if reason is not None:
        _send_email(
            subject=f'Votre demande d\'inscription — {signup_request.company.name}',
            template='client_portal/emails/client_signup_rejected.html',
            context={
                'first_name': signup_request.first_name,
                'company': signup_request.company,
                'reason': reason,
            },
            recipient=signup_request.email,
        )


def convert_signup_to_portal_account(signup_request):
    """
    Convertit une demande approuvée en compte portail client.

    Returns: ClientPortalAccount
    """
    from apps.portals.models import ClientPortalAccount, ClientPortalSignupRequest

    email = signup_request.email

    # Créer ou récupérer le User Django
    user, user_created = User.objects.get_or_create(
        username=email,
        defaults={
            'email': email,
            'first_name': signup_request.first_name,
            'last_name': signup_request.last_name,
            'is_active': True,
            'is_staff': False,
            'is_superuser': False,
        },
    )
    if user_created:
        user.password = signup_request.password_hash
        user.save(update_fields=['password'])

    # Créer ou récupérer le compte portail
    account, acc_created = ClientPortalAccount.objects.get_or_create(
        user=user,
        defaults={
            'company': signup_request.company,
            'first_name': signup_request.first_name,
            'last_name': signup_request.last_name,
            'email': email,
            'phone': signup_request.phone,
            'crm_customer_id': signup_request.linked_customer_id,
            'is_active': True,
            'is_email_verified': signup_request.email_verified,
            'is_approved': True,
            'created_from_signup': True,
        },
    )

    # Lier la demande au compte
    signup_request.linked_portal_account = account
    signup_request.status = ClientPortalSignupRequest.STATUS_CONVERTED
    signup_request.save(update_fields=['linked_portal_account', 'status'])

    _log_activity(signup_request.company, 'portal_account_created', email, signup_request)

    # Envoyer email d'activation
    try:
        from django.urls import reverse
        login_url = '/client/connexion/'
    except Exception:
        login_url = '/client/connexion/'

    _send_email(
        subject=f'Votre espace client est activé — {signup_request.company.name}',
        template='client_portal/emails/client_signup_approved.html',
        context={
            'first_name': signup_request.first_name,
            'company': signup_request.company,
            'login_url': login_url,
        },
        recipient=email,
    )

    return account


def find_existing_customer(company, email: str):
    """Cherche un client CRM existant par email."""
    try:
        from apps.crm.models import Customer
        return Customer.objects.filter(company=company, email__iexact=email).first()
    except Exception:
        return None


def notify_company_admins(signup_request) -> None:
    """Notifie les admins ERP d'une nouvelle demande d'inscription."""
    try:
        from apps.notifications.services import notify_company
        admin_url = f'/portails/inscriptions/{signup_request.pk}/'
        notify_company(
            company=signup_request.company,
            title=f'Nouvelle inscription client — {signup_request.full_name}',
            message=f'Email : {signup_request.email}',
            notification_type='validation_pending',
            link_url=admin_url,
            link_label='Voir la demande',
            priority='normal',
            source_module='portals',
            source_model='ClientPortalSignupRequest',
            source_id=signup_request.pk,
            icon='bi-person-plus',
            icon_color='warning',
        )
    except Exception as exc:
        logger.warning('notify_company_admins failed: %s', exc)

    # Email aux admins
    try:
        from apps.accounts.models import UserProfile
        admin_emails = list(
            UserProfile.objects.filter(
                company=signup_request.company,
                user__is_active=True,
            ).values_list('user__email', flat=True)
        )
    except Exception:
        admin_emails = []

    if not admin_emails:
        try:
            admin_emails = [settings.ADMINS[0][1]] if settings.ADMINS else []
        except Exception:
            admin_emails = []

    for admin_email in admin_emails:
        if admin_email:
            _send_email(
                subject=f'[Orion] Nouvelle inscription client — {signup_request.full_name}',
                template='client_portal/emails/admin_new_client_signup.html',
                context={
                    'signup': signup_request,
                    'company': signup_request.company,
                    'admin_url': f'http://127.0.0.1:8000/portails/inscriptions/{signup_request.pk}/',
                },
                recipient=admin_email,
            )
