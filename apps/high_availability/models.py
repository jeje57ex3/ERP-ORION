from django.conf import settings
from django.db import models
from django.utils import timezone


class OrionHANode(models.Model):
    ROLE_CHOICES = [
        ('primary', 'Principal'),
        ('secondary', 'Secondaire'),
        ('observer', 'Observateur'),
    ]

    STATUS_CHOICES = [
        ('unknown', 'Inconnu'),
        ('healthy', 'Sain'),
        ('warning', 'Avertissement'),
        ('down', 'Hors ligne'),
        ('maintenance', 'Maintenance'),
        ('active', 'Actif'),
        ('passive', 'Passif'),
        ('promoting', 'Promotion en cours'),
        ('disabled', 'Désactivé'),
    ]

    node_id = models.SlugField(max_length=120, unique=True)
    name = models.CharField(max_length=180)

    role = models.CharField(max_length=40, choices=ROLE_CHOICES, default='secondary')
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='unknown')

    base_url = models.URLField(blank=True)
    public_ip = models.GenericIPAddressField(null=True, blank=True)
    private_ip = models.GenericIPAddressField(null=True, blank=True)

    region = models.CharField(max_length=80, blank=True)

    priority = models.PositiveIntegerField(
        default=100,
        help_text='1 = serveur principal, 2 = secondaire prioritaire, 3 = secondaire de secours.',
    )

    is_enabled = models.BooleanField(default=True)
    is_current_active = models.BooleanField(default=False)
    is_failover_target = models.BooleanField(default=False)
    allow_auto_failover = models.BooleanField(default=True)

    last_heartbeat_at = models.DateTimeField(null=True, blank=True)
    last_health_payload = models.JSONField(default=dict, blank=True)

    app_version = models.CharField(max_length=80, blank=True)
    git_commit = models.CharField(max_length=80, blank=True)

    database_role = models.CharField(max_length=40, default='unknown')
    database_status = models.CharField(max_length=40, default='unknown')
    replication_lag_seconds = models.PositiveIntegerField(null=True, blank=True)

    media_sync_status = models.CharField(max_length=40, default='unknown')
    media_last_sync_at = models.DateTimeField(null=True, blank=True)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'high_availability'
        ordering = ['priority', 'name']
        indexes = [
            models.Index(fields=['role', 'priority']),
            models.Index(fields=['is_current_active']),
            models.Index(fields=['is_failover_target']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f'{self.name} ({self.node_id})'

    @property
    def heartbeat_age_seconds(self):
        if not self.last_heartbeat_at:
            return None
        return int((timezone.now() - self.last_heartbeat_at).total_seconds())

    @property
    def is_stale(self):
        age = self.heartbeat_age_seconds
        return age is None or age > 120

    @property
    def can_be_failover_target(self):
        return (
            self.is_enabled
            and self.role == 'secondary'
            and self.status in ('healthy', 'passive', 'warning')
        )


class OrionHASettings(models.Model):
    failover_enabled = models.BooleanField(default=True)

    automatic_failover_enabled = models.BooleanField(
        default=False,
        help_text='Ne pas activer avant tests complets.',
    )

    require_manual_confirmation = models.BooleanField(default=True)
    failover_after_seconds = models.PositiveIntegerField(default=120)
    max_allowed_replication_lag_seconds = models.PositiveIntegerField(default=10)

    minimum_healthy_secondaries = models.PositiveIntegerField(
        default=1,
        help_text='Nombre minimal de serveurs secondaires disponibles.',
    )

    preferred_secondary_node = models.ForeignKey(
        OrionHANode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='preferred_by_settings',
        help_text='Serveur secondaire préféré pour la bascule.',
    )

    allow_failover_to_secondary_2 = models.BooleanField(
        default=True,
        help_text='Autoriser la bascule vers le second serveur secondaire si le premier est indisponible.',
    )

    media_sync_enabled = models.BooleanField(default=True)
    database_replication_check_enabled = models.BooleanField(default=True)

    cloudflare_failover_enabled = models.BooleanField(default=False)
    cloudflare_zone_id = models.CharField(max_length=180, blank=True)
    cloudflare_dns_record_id = models.CharField(max_length=180, blank=True)
    cloudflare_record_name = models.CharField(max_length=180, default='erp')

    notify_admins = models.BooleanField(default=True)
    notify_email = models.EmailField(blank=True)

    split_brain_protection_enabled = models.BooleanField(default=True)
    maintenance_mode_enabled = models.BooleanField(default=False)

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'high_availability'
        verbose_name = 'Paramètres haute disponibilité'
        verbose_name_plural = 'Paramètres haute disponibilité'

    def __str__(self):
        return 'Paramètres haute disponibilité Orion'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj


class OrionHAReplicationStatus(models.Model):
    node = models.OneToOneField(
        OrionHANode,
        on_delete=models.CASCADE,
        related_name='replication_status',
    )

    database_status = models.CharField(max_length=40, default='unknown')
    io_thread_running = models.BooleanField(default=False)
    sql_thread_running = models.BooleanField(default=False)

    seconds_behind_primary = models.PositiveIntegerField(null=True, blank=True)

    primary_log_file = models.CharField(max_length=180, blank=True)
    primary_log_position = models.CharField(max_length=80, blank=True)

    checked_at = models.DateTimeField(auto_now=True)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = 'high_availability'
        ordering = ['node__priority']

    def __str__(self):
        return f'Réplication {self.node.node_id}'


class OrionHAFailoverEvent(models.Model):
    EVENT_TYPE_CHOICES = [
        ('manual_failover', 'Bascule manuelle'),
        ('automatic_failover', 'Bascule automatique'),
        ('manual_failback', 'Retour manuel'),
        ('test', 'Test'),
    ]

    STATUS_CHOICES = [
        ('planned', 'Planifié'),
        ('running', 'En cours'),
        ('success', 'Succès'),
        ('failed', 'Échec'),
        ('cancelled', 'Annulé'),
    ]

    event_type = models.CharField(max_length=60, choices=EVENT_TYPE_CHOICES)
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='planned')

    from_node = models.ForeignKey(
        OrionHANode,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='failover_from_events',
    )
    to_node = models.ForeignKey(
        OrionHANode,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='failover_to_events',
    )

    reason = models.TextField(blank=True)
    steps = models.JSONField(default=list, blank=True)
    result_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )

    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'high_availability'
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.event_type} — {self.status}'


class OrionHAClusterLock(models.Model):
    active_node_id = models.CharField(max_length=120)
    lock_token = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'high_availability'
        verbose_name = 'Verrou cluster HA'

    def __str__(self):
        return f'Lock → {self.active_node_id}'

    @classmethod
    def get_lock(cls):
        obj, _ = cls.objects.get_or_create(
            id=1,
            defaults={
                'active_node_id': 'orion-primary',
                'lock_token': '',
            },
        )
        return obj
