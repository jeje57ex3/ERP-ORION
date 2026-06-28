"""
apps/accounts/models.py — Profils utilisateurs, rôles, permissions
"""
from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Company


ROLE_CHOICES = [
    ('superadmin', 'Super Administrateur'),
    ('admin', 'Administrateur'),
    ('manager', 'Responsable'),
    ('accountant', 'Comptable'),
    ('salesperson', 'Commercial'),
    ('purchaser', 'Acheteur'),
    ('warehouse', 'Magasinier'),
    ('hr_manager', 'Responsable RH'),
    ('technician', 'Technicien'),
    ('user', 'Utilisateur'),
    ('readonly', 'Lecture seule'),
]

MODULE_PERMISSIONS = [
    ('crm', 'CRM'),
    ('sales', 'Ventes'),
    ('accounting', 'Comptabilité'),
    ('purchases', 'Achats'),
    ('inventory', 'Stocks'),
    ('documents', 'Documents'),
    ('hr', 'RH'),
    ('payroll', 'Paie'),
    ('support', 'Support'),
    ('btp', 'BTP'),
    ('ecommerce', 'E-commerce'),
    ('commerce', 'Commerce'),
    ('production', 'Production'),
    ('audio', 'Audio/AV'),
    ('websites', 'Sites web'),
    ('bi', 'Reporting'),
    ('admin', 'Administration'),
]


class UserProfile(models.Model):
    """Profil étendu utilisateur avec rôles multi-entreprises."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    companies = models.ManyToManyField(Company, blank=True, verbose_name='Entreprises', related_name='users')
    current_company = models.ForeignKey(
        Company, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='current_users', verbose_name='Entreprise courante'
    )
    role = models.CharField('Rôle', max_length=20, choices=ROLE_CHOICES, default='user')
    phone = models.CharField('Téléphone', max_length=20, blank=True)
    mobile = models.CharField('Mobile', max_length=20, blank=True)
    avatar = models.ImageField('Avatar', upload_to='avatars/', blank=True, null=True)
    bio = models.TextField('Bio', blank=True)
    job_title = models.CharField('Poste', max_length=100, blank=True)
    department = models.CharField('Département', max_length=100, blank=True)

    # Préférences
    language = models.CharField('Langue', max_length=5, default='fr')
    timezone = models.CharField('Fuseau horaire', max_length=50, default='Europe/Paris')
    date_format = models.CharField('Format date', max_length=20, default='%d/%m/%Y')
    items_per_page = models.PositiveIntegerField('Éléments par page', default=25)
    theme = models.CharField('Thème', max_length=10, default='light',
                             choices=[('light', 'Clair'), ('dark', 'Sombre'), ('system', 'Système')])
    compact_mode = models.BooleanField('Mode compact', default=False)

    # Notifications
    email_notifications = models.BooleanField('Notifications email', default=True)
    browser_notifications = models.BooleanField('Notifications navigateur', default=False)

    # Sécurité
    two_factor_enabled = models.BooleanField('2FA activé', default=False)
    last_login_ip = models.GenericIPAddressField('Dernière IP', null=True, blank=True)
    failed_login_attempts = models.PositiveIntegerField('Tentatives échouées', default=0)
    locked_until = models.DateTimeField('Verrouillé jusqu\'au', null=True, blank=True)

    is_active = models.BooleanField('Actif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Profil utilisateur'
        verbose_name_plural = 'Profils utilisateurs'

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} ({self.get_role_display()})'

    @property
    def display_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def initials(self):
        name = self.user.get_full_name()
        if name:
            parts = name.split()
            return ''.join(p[0].upper() for p in parts[:2])
        return self.user.username[:2].upper()

    def has_module_access(self, module, company=None):
        """Vérifie si l'utilisateur a accès à un module pour une entreprise."""
        if self.user.is_superuser or self.role == 'superadmin':
            return True
        if self.role == 'admin':
            return True

        if company and not self.companies.filter(pk=company.pk).exists():
            return False

        # Vérifier permissions spécifiques
        perms = self.module_permissions.filter(module=module)
        if perms.exists():
            return perms.first().can_read

        # Permissions par rôle par défaut
        role_modules = {
            'manager': ['crm', 'sales', 'purchases', 'inventory', 'documents', 'support', 'bi'],
            'accountant': ['accounting', 'sales', 'purchases', 'documents'],
            'salesperson': ['crm', 'sales', 'inventory'],
            'purchaser': ['purchases', 'inventory', 'documents'],
            'warehouse': ['inventory'],
            'hr_manager': ['hr', 'payroll'],
            'technician': ['support', 'documents'],
            'user': ['crm', 'sales'],
            'readonly': [],
        }
        return module in role_modules.get(self.role, [])


class UserModulePermission(models.Model):
    """Permissions granulaires par module par utilisateur."""
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='module_permissions')
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    module = models.CharField('Module', max_length=20, choices=MODULE_PERMISSIONS)
    can_read = models.BooleanField('Lecture', default=True)
    can_create = models.BooleanField('Création', default=False)
    can_update = models.BooleanField('Modification', default=False)
    can_delete = models.BooleanField('Suppression', default=False)
    can_export = models.BooleanField('Export', default=False)
    can_validate = models.BooleanField('Validation', default=False)

    class Meta:
        verbose_name = 'Permission module'
        verbose_name_plural = 'Permissions modules'
        unique_together = ['user_profile', 'company', 'module']

    def __str__(self):
        return f'{self.user_profile.user.username} — {self.module} — {self.company.name}'


class UserActivity(models.Model):
    """Historique d'activité utilisateur."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField('Action', max_length=200)
    url = models.CharField('URL', max_length=500, blank=True)
    ip_address = models.GenericIPAddressField('IP', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Activité utilisateur'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} — {self.action}'
