"""
apps/private_saas/models.py — Couche SaaS privé multi-entreprises Orion ERP
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


ALL_MODULE_CODES = [
    'dashboard', 'crm', 'sales', 'accounting', 'purchases', 'inventory',
    'btp', 'ecommerce', 'commerce', 'production', 'hr', 'documents',
    'websites', 'client_portal', 'messages', 'reporting', 'notifications',
    'automation', 'domains', 'domain_diagnostics', 'backups_module',
]

MODULE_LABELS = {
    'dashboard':     'Dashboard',
    'crm':           'CRM',
    'sales':         'Ventes',
    'accounting':    'Comptabilité',
    'purchases':     'Achats',
    'inventory':     'Stocks',
    'btp':           'BTP',
    'ecommerce':     'E-commerce',
    'commerce':      'Commerce',
    'production':    'Production',
    'hr':            'RH',
    'documents':     'Documents',
    'websites':      'Sites web',
    'client_portal': 'Portail client',
    'messages':      'Messages',
    'reporting':     'Reporting',
    'notifications': 'Notifications',
    'automation':    'Automatisation',
    'domains':       'Domaines',
    'domain_diagnostics': 'Diagnostic domaines & Cloudflare',
    'backups_module':     'Sauvegardes',
}

MODULE_NAV_IDS = {
    'dashboard':     ['dashboard', 'erp_overview'],
    'crm':           ['crm'],
    'sales':         ['sales'],
    'accounting':    ['accounting'],
    'purchases':     ['purchases'],
    'inventory':     ['inventory'],
    'btp':           ['btp'],
    'ecommerce':     ['ecommerce'],
    'commerce':      ['commerce'],
    'production':    ['production'],
    'hr':            ['hr'],
    'documents':     ['documents'],
    'websites':      ['websites'],
    'reporting':     ['bi'],
    'notifications': [],
    'automation':    [],
    'client_portal': [],
    'messages':      [],
    'domains':       [],
    'domain_diagnostics': [],
    'backups_module':     [],
}

DEFAULT_MODULES_BY_TYPE = {
    'btp': [
        'dashboard', 'crm', 'sales', 'accounting', 'btp',
        'documents', 'websites', 'client_portal', 'hr',
        'notifications', 'domains', 'messages',
    ],
    'fashion': [
        'dashboard', 'crm', 'ecommerce', 'commerce', 'inventory', 'sales',
        'documents', 'websites', 'client_portal', 'notifications', 'domains',
    ],
    'beauty': [
        'dashboard', 'crm', 'ecommerce', 'commerce', 'inventory', 'sales',
        'documents', 'websites', 'client_portal', 'notifications', 'domains',
    ],
    'watch': [
        'dashboard', 'crm', 'ecommerce', 'inventory', 'sales',
        'documents', 'websites', 'client_portal', 'notifications', 'domains',
    ],
    'ecommerce': [
        'dashboard', 'crm', 'ecommerce', 'inventory', 'sales', 'accounting',
        'documents', 'websites', 'notifications', 'domains',
    ],
    'commerce': [
        'dashboard', 'crm', 'commerce', 'inventory', 'sales', 'accounting',
        'hr', 'documents', 'notifications',
    ],
    'audio': [
        'dashboard', 'crm', 'sales', 'accounting', 'hr',
        'documents', 'websites', 'notifications',
    ],
    'production': [
        'dashboard', 'crm', 'sales', 'purchases', 'inventory', 'production',
        'hr', 'documents', 'notifications',
    ],
    'generic': [
        'dashboard', 'crm', 'sales', 'accounting', 'purchases', 'inventory',
        'hr', 'documents', 'websites', 'notifications',
    ],
}


class CompanyModule(models.Model):
    company = models.ForeignKey(
        'core.Company', on_delete=models.CASCADE, related_name='modules',
    )
    module_code = models.CharField(max_length=50)
    module_name = models.CharField(max_length=100)
    is_enabled = models.BooleanField(default=False)
    enabled_at = models.DateTimeField(null=True, blank=True)
    enabled_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='enabled_modules',
    )
    settings_json = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'private_saas'
        unique_together = ('company', 'module_code')
        ordering = ['module_code']
        verbose_name = 'Module entreprise'
        verbose_name_plural = 'Modules entreprise'

    def __str__(self):
        return f'{self.company.name} — {self.module_name} ({"actif" if self.is_enabled else "inactif"})'

    def enable(self, user=None):
        self.is_enabled = True
        self.enabled_at = timezone.now()
        if user:
            self.enabled_by = user
        self.save(update_fields=['is_enabled', 'enabled_at', 'enabled_by'])

    def disable(self):
        self.is_enabled = False
        self.save(update_fields=['is_enabled'])


class PrivateSaaSSettings(models.Model):
    private_mode_enabled         = models.BooleanField(default=True)
    public_signup_enabled        = models.BooleanField(default=False)
    default_language             = models.CharField(max_length=10, default='fr')
    default_timezone             = models.CharField(max_length=50, default='Europe/Paris')
    default_currency             = models.CharField(max_length=3, default='EUR')
    allow_company_database_creation = models.BooleanField(default=True)
    allow_domain_management      = models.BooleanField(default=True)
    allow_module_management      = models.BooleanField(default=True)
    maintenance_mode             = models.BooleanField(default=False)
    created_at                   = models.DateTimeField(auto_now_add=True)
    updated_at                   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'private_saas'
        verbose_name = 'Paramètres SaaS privé'

    def __str__(self):
        return 'Paramètres SaaS privé Orion ERP'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class CompanyBackup(models.Model):
    BACKUP_TYPES = [
        ('full',      'Complète'),
        ('database',  'Base de données'),
        ('media',     'Médias'),
        ('documents', 'Documents'),
    ]
    STATUS_CHOICES = [
        ('pending', 'En cours'),
        ('success', 'Réussie'),
        ('error',   'Erreur'),
    ]

    company     = models.ForeignKey(
        'core.Company', on_delete=models.CASCADE, related_name='backups',
    )
    backup_type = models.CharField(max_length=20, choices=BACKUP_TYPES, default='database')
    file_path   = models.CharField(max_length=500, blank=True)
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    size        = models.BigIntegerField(default=0)
    error_message = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    created_by  = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='company_backups',
    )

    class Meta:
        app_label = 'private_saas'
        ordering = ['-created_at']
        verbose_name = 'Sauvegarde entreprise'
        verbose_name_plural = 'Sauvegardes entreprise'

    def __str__(self):
        return f'{self.company.name} — {self.get_backup_type_display()} — {self.created_at:%d/%m/%Y %H:%M}'

    @property
    def size_display(self):
        if self.size < 1024:
            return f'{self.size} o'
        elif self.size < 1024 * 1024:
            return f'{self.size / 1024:.1f} Ko'
        return f'{self.size / (1024 * 1024):.1f} Mo'
