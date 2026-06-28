import secrets
from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Company


class ClientPortalAccess(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    customer_name = models.CharField(max_length=200)
    email = models.EmailField()
    access_token = models.CharField(max_length=64, unique=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Accès portail client'

    def __str__(self):
        return f'{self.customer_name} - {self.email}'


class ClientPortalAccount(models.Model):
    """Compte client espace chantier — lié à un User Django."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='portal_accounts')
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='portal_account')
    first_name = models.CharField('Prénom', max_length=100)
    last_name = models.CharField('Nom', max_length=100)
    email = models.EmailField('Email')
    phone = models.CharField('Téléphone', max_length=20, blank=True)
    address = models.TextField('Adresse', blank=True)

    # Lien CRM
    crm_customer_id = models.PositiveIntegerField('ID client CRM', null=True, blank=True)

    # Droits
    can_upload = models.BooleanField('Peut uploader des documents', default=True)
    can_message = models.BooleanField('Peut envoyer des messages', default=True)
    can_request_changes = models.BooleanField('Peut demander des modifications', default=True)
    can_report_reservations = models.BooleanField('Peut signaler des réserves', default=True)

    is_active = models.BooleanField('Actif', default=True)
    is_email_verified = models.BooleanField('Email vérifié', default=False)
    is_approved = models.BooleanField('Approuvé', default=True)
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_from_guided_quote = models.BooleanField('Créé depuis demande guidée', default=False)
    created_from_signup = models.BooleanField('Créé depuis inscription libre', default=False)

    class Meta:
        verbose_name = 'Compte portail client'
        verbose_name_plural = 'Comptes portail client'

    def __str__(self):
        return f'{self.first_name} {self.last_name} ({self.email})'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def unread_notifications(self):
        from apps.btp.models import ClientNotification
        return ClientNotification.objects.filter(client_email=self.email, is_read=False).count()

    @property
    def active_projects(self):
        from apps.btp.models import BTPProject
        return BTPProject.objects.filter(
            company=self.company,
            customer__email=self.email,
            status__in=['won', 'in_progress'],
        )


# ── Paramètres portail client ─────────────────────────────────────────────────

class ClientPortalSettings(models.Model):
    """Configuration de l'inscription client par entreprise."""
    company = models.OneToOneField(
        Company, on_delete=models.CASCADE, related_name='portal_settings',
        verbose_name='Entreprise',
    )
    allow_client_registration = models.BooleanField(
        'Autoriser les inscriptions clients', default=True,
    )
    registration_requires_approval = models.BooleanField(
        'Validation admin requise', default=True,
    )
    registration_requires_email_verification = models.BooleanField(
        'Vérification email obligatoire', default=True,
    )
    allow_unknown_clients = models.BooleanField(
        'Autoriser les emails inconnus du CRM', default=True,
    )
    default_registered_client_status = models.CharField(
        'Statut par défaut', max_length=20, default='pending',
    )
    notify_admin_on_registration = models.BooleanField(
        'Notifier les admins à chaque inscription', default=True,
    )
    registration_intro_text = models.TextField(
        'Texte d\'introduction inscription', blank=True, default='',
    )

    class Meta:
        verbose_name = 'Paramètres portail client'
        verbose_name_plural = 'Paramètres portail client'

    def __str__(self):
        return f'Paramètres portail — {self.company.name}'

    @classmethod
    def get_for_company(cls, company):
        if company is None:
            return None
        obj, _ = cls.objects.get_or_create(company=company)
        return obj


# ── Demandes d'inscription ────────────────────────────────────────────────────

class ClientPortalSignupRequest(models.Model):
    """Demande d'inscription d'un nouveau client au portail."""

    STATUS_PENDING_EMAIL = 'pending_email_verification'
    STATUS_PENDING_APPROVAL = 'pending_approval'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_CONVERTED = 'converted'
    STATUS_EXPIRED = 'expired'

    STATUS_CHOICES = [
        (STATUS_PENDING_EMAIL, 'En attente de vérification email'),
        (STATUS_PENDING_APPROVAL, 'En attente de validation'),
        (STATUS_APPROVED, 'Approuvé'),
        (STATUS_REJECTED, 'Refusé'),
        (STATUS_CONVERTED, 'Converti en compte'),
        (STATUS_EXPIRED, 'Expiré'),
    ]

    ACTIVE_STATUSES = [STATUS_PENDING_EMAIL, STATUS_PENDING_APPROVAL, STATUS_APPROVED]

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='signup_requests',
        verbose_name='Entreprise',
    )
    first_name = models.CharField('Prénom', max_length=100)
    last_name = models.CharField('Nom', max_length=100)
    email = models.EmailField('Adresse email')
    phone = models.CharField('Téléphone', max_length=20, blank=True)
    company_name = models.CharField('Nom de l\'entreprise', max_length=200, blank=True)
    message = models.TextField('Message', blank=True)

    password_hash = models.CharField('Mot de passe (hashé)', max_length=256)

    status = models.CharField(
        'Statut', max_length=30, choices=STATUS_CHOICES,
        default=STATUS_PENDING_EMAIL, db_index=True,
    )

    # Vérification email
    email_verified = models.BooleanField('Email vérifié', default=False)
    email_verification_token = models.CharField(
        'Token de vérification', max_length=64, unique=True, blank=True,
    )
    email_verification_sent_at = models.DateTimeField(
        'Email de vérification envoyé le', null=True, blank=True,
    )

    # Validation admin
    approved_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='approved_signups', verbose_name='Validé par',
    )
    approved_at = models.DateTimeField('Validé le', null=True, blank=True)

    # Refus admin
    rejected_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='rejected_signups', verbose_name='Refusé par',
    )
    rejected_at = models.DateTimeField('Refusé le', null=True, blank=True)
    rejection_reason = models.TextField('Raison du refus', blank=True)

    # Liens CRM / portail
    linked_customer_id = models.PositiveIntegerField('ID client CRM', null=True, blank=True)
    linked_portal_account = models.OneToOneField(
        ClientPortalAccount, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='signup_request', verbose_name='Compte portail créé',
    )

    # Sécurité
    ip_address = models.GenericIPAddressField('Adresse IP', null=True, blank=True)
    user_agent = models.TextField('User-Agent', blank=True)

    created_at = models.DateTimeField('Créée le', auto_now_add=True)
    updated_at = models.DateTimeField('Mise à jour le', auto_now=True)

    class Meta:
        verbose_name = 'Demande d\'inscription client'
        verbose_name_plural = 'Demandes d\'inscription client'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'status', '-created_at'], name='signup_company_status_idx'),
            models.Index(fields=['email', 'company'], name='signup_email_company_idx'),
        ]

    def __str__(self):
        return f'{self.first_name} {self.last_name} <{self.email}> [{self.get_status_display()}]'

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES

    @property
    def status_badge_class(self):
        return {
            self.STATUS_PENDING_EMAIL: 'warning',
            self.STATUS_PENDING_APPROVAL: 'info',
            self.STATUS_APPROVED: 'success',
            self.STATUS_REJECTED: 'danger',
            self.STATUS_CONVERTED: 'primary',
            self.STATUS_EXPIRED: 'secondary',
        }.get(self.status, 'secondary')


# ── Rate limiting ─────────────────────────────────────────────────────────────

class ClientPortalSignupAttempt(models.Model):
    """Enregistrement des tentatives d'inscription (rate limiting)."""
    ip_address = models.GenericIPAddressField('Adresse IP')
    email = models.EmailField('Email', blank=True)
    created_at = models.DateTimeField('Date', auto_now_add=True)

    class Meta:
        verbose_name = 'Tentative d\'inscription'
        verbose_name_plural = 'Tentatives d\'inscription'
        indexes = [
            models.Index(fields=['ip_address', 'created_at'], name='signup_attempt_ip_idx'),
            models.Index(fields=['email', 'created_at'], name='signup_attempt_email_idx'),
        ]

    def __str__(self):
        return f'{self.ip_address} / {self.email} — {self.created_at}'


# ── Journal d'activité ────────────────────────────────────────────────────────

class ClientPortalActivity(models.Model):
    """Journal des actions liées à l'inscription et à la connexion client."""

    ACTION_CHOICES = [
        ('signup_created', 'Inscription créée'),
        ('signup_email_verified', 'Email vérifié'),
        ('signup_approved', 'Inscription approuvée'),
        ('signup_rejected', 'Inscription refusée'),
        ('portal_account_created', 'Compte portail créé'),
        ('client_logged_in', 'Connexion client'),
    ]

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name='portal_activities',
        verbose_name='Entreprise',
    )
    action = models.CharField('Action', max_length=50, choices=ACTION_CHOICES, db_index=True)
    email = models.EmailField('Email')
    signup_request = models.ForeignKey(
        ClientPortalSignupRequest, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='activities',
    )
    performed_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='portal_activities_performed',
    )
    ip_address = models.GenericIPAddressField('IP', null=True, blank=True)
    notes = models.TextField('Notes', blank=True)
    created_at = models.DateTimeField('Date', auto_now_add=True)

    class Meta:
        verbose_name = 'Activité portail client'
        verbose_name_plural = 'Activités portail client'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_action_display()}] {self.email} — {self.created_at:%d/%m/%Y %H:%M}'
