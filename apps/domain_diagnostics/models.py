from django.conf import settings
from django.db import models
from django.utils import timezone


class CloudflareZoneConfig(models.Model):
    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='cloudflare_zone_configs',
    )
    zone_name = models.CharField('Zone (ex: elysiums.fr)', max_length=255)
    zone_id = models.CharField('Zone ID Cloudflare', max_length=255, blank=True)
    api_token_hint = models.CharField(
        'Indice token API',
        max_length=80,
        blank=True,
        help_text='Ne pas stocker le token ici. Ex : token se terminant par …abcd.',
    )
    is_active = models.BooleanField('Active', default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'domain_diagnostics'
        unique_together = [('company', 'zone_name')]
        verbose_name = 'Configuration zone Cloudflare'
        verbose_name_plural = 'Configurations zones Cloudflare'
        indexes = [
            models.Index(fields=['company', 'zone_name']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.zone_name


class DomainDiagnosticTarget(models.Model):
    TARGET_TYPE_CHOICES = [
        ('website', 'Site web Orion'),
        ('login',   'Login Orion'),
        ('api',     'API'),
        ('custom',  'Personnalisé'),
    ]
    EXPECTED_PROXY_CHOICES = [
        ('auto',     'Automatique'),
        ('proxied',  'Proxy Cloudflare activé'),
        ('dns_only', 'DNS uniquement'),
    ]

    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='domain_diagnostic_targets',
    )
    website = models.ForeignKey(
        'websites.Website',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='diagnostic_targets',
    )
    cloudflare_zone = models.ForeignKey(
        CloudflareZoneConfig,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='targets',
    )
    domain = models.CharField('Domaine', max_length=255)
    # brand_key sert d'identifiant de marque (siecle, lunea…) — non stocké sur Website
    brand_key = models.CharField('Marque (slug)', max_length=50, blank=True,
                                 help_text='siecle, lunea, login, orion…')
    target_type = models.CharField('Type', max_length=40, choices=TARGET_TYPE_CHOICES, default='website')
    expected_origin_ip = models.GenericIPAddressField('IP origine attendue', null=True, blank=True)
    expected_record_type = models.CharField('Type DNS', max_length=20, default='A')
    expected_record_content = models.CharField('Contenu DNS attendu', max_length=255, blank=True)
    expected_proxy = models.CharField('Proxy attendu', max_length=20, choices=EXPECTED_PROXY_CHOICES, default='proxied')
    expected_ssl_mode = models.CharField('Mode SSL attendu', max_length=40, default='strict')
    expected_https_status = models.PositiveIntegerField('Code HTTP attendu', default=200)
    is_active = models.BooleanField('Actif', default=True)
    auto_repair_enabled = models.BooleanField('Réparation auto', default=False)
    last_scan_at = models.DateTimeField('Dernier scan', null=True, blank=True)
    last_status = models.CharField('Dernier statut', max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'domain_diagnostics'
        unique_together = [('company', 'domain')]
        verbose_name = 'Cible diagnostic domaine'
        verbose_name_plural = 'Cibles diagnostic domaines'
        indexes = [
            models.Index(fields=['company', 'domain']),
            models.Index(fields=['brand_key']),
            models.Index(fields=['is_active']),
            models.Index(fields=['last_status']),
        ]

    def __str__(self):
        return self.domain


class DomainDiagnosticRun(models.Model):
    STATUS_CHOICES = [
        ('running',  'En cours'),
        ('ok',       'OK'),
        ('warning',  'Avertissement'),
        ('error',    'Erreur'),
        ('repaired', 'Réparé'),
    ]

    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        related_name='domain_diagnostic_runs',
    )
    target = models.ForeignKey(
        DomainDiagnosticTarget,
        on_delete=models.CASCADE,
        related_name='runs',
    )
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='running')
    summary = models.TextField(blank=True)
    raw_results = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )

    class Meta:
        app_label = 'domain_diagnostics'
        ordering = ['-started_at']
        verbose_name = 'Diagnostic run'
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['started_at']),
        ]

    def finish(self, status, summary='', raw_results=None):
        self.status = status
        self.summary = summary
        if raw_results is not None:
            self.raw_results = raw_results
        self.finished_at = timezone.now()
        self.save(update_fields=['status', 'summary', 'raw_results', 'finished_at'])

    def __str__(self):
        return f'{self.target.domain} — {self.get_status_display()} ({self.started_at:%d/%m/%Y %H:%M})'


class DomainIssue(models.Model):
    ISSUE_TYPE_CHOICES = [
        ('website_link',          'Lien Website Orion'),
        ('dns_missing',           'DNS manquant'),
        ('dns_wrong_content',     'DNS incorrect'),
        ('cloudflare_proxy',      'Proxy Cloudflare incorrect'),
        ('cloudflare_ssl',        'SSL Cloudflare incorrect'),
        ('http_error',            'Erreur HTTP'),
        ('https_error',           'Erreur HTTPS'),
        ('redirect_error',        'Erreur redirection'),
        ('nginx_missing',         'Nginx manquant'),
        ('nginx_wrong_server_name','Nginx server_name incorrect'),
        ('brand_mismatch',        'Mauvaise marque'),
        ('unknown',               'Inconnu'),
    ]
    SEVERITY_CHOICES = [
        ('info',     'Info'),
        ('warning',  'Avertissement'),
        ('critical', 'Critique'),
    ]
    STATUS_CHOICES = [
        ('open',    'Ouvert'),
        ('ignored', 'Ignoré'),
        ('fixed',   'Corrigé'),
    ]

    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='domain_issues')
    target = models.ForeignKey(DomainDiagnosticTarget, on_delete=models.CASCADE, related_name='issues')
    run = models.ForeignKey(DomainDiagnosticRun, on_delete=models.SET_NULL, null=True, blank=True, related_name='issues')

    issue_type = models.CharField(max_length=80, choices=ISSUE_TYPE_CHOICES)
    severity = models.CharField(max_length=40, choices=SEVERITY_CHOICES, default='warning')
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='open')

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    repair_code = models.CharField(max_length=120, blank=True)
    repair_payload = models.JSONField(default=dict, blank=True)
    can_auto_repair = models.BooleanField(default=False)

    detected_at = models.DateTimeField(default=timezone.now)
    fixed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'domain_diagnostics'
        ordering = ['-detected_at']
        verbose_name = 'Problème domaine'
        verbose_name_plural = 'Problèmes domaines'
        indexes = [
            models.Index(fields=['company', 'status']),
            models.Index(fields=['issue_type']),
            models.Index(fields=['severity']),
        ]

    def mark_fixed(self):
        self.status = 'fixed'
        self.fixed_at = timezone.now()
        self.save(update_fields=['status', 'fixed_at'])

    def __str__(self):
        return f'[{self.severity}] {self.title}'


class DomainRepairLog(models.Model):
    STATUS_CHOICES = [
        ('success', 'Succès'),
        ('failed',  'Échec'),
        ('skipped', 'Ignoré'),
    ]

    company = models.ForeignKey('core.Company', on_delete=models.CASCADE, related_name='domain_repair_logs')
    issue = models.ForeignKey(DomainIssue, on_delete=models.SET_NULL, null=True, blank=True, related_name='repair_logs')
    target = models.ForeignKey(DomainDiagnosticTarget, on_delete=models.SET_NULL, null=True, blank=True, related_name='repair_logs')

    repair_code = models.CharField(max_length=120)
    status = models.CharField(max_length=40, choices=STATUS_CHOICES)
    message = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)

    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )
    executed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        app_label = 'domain_diagnostics'
        ordering = ['-executed_at']
        verbose_name = 'Journal réparation domaine'
        verbose_name_plural = 'Journal réparations domaines'

    def __str__(self):
        return f'{self.repair_code} — {self.get_status_display()} ({self.executed_at:%d/%m %H:%M})'
