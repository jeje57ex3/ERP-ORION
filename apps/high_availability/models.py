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

    # Rang de préséance, et NON le rôle courant. Les deux étaient confondus :
    # le rôle se déplace à chaque bascule, la préséance est une décision
    # d'exploitation qui ne bouge pas. Un ancien principal rétrogradé garde
    # donc sa priorité 1, ce qui est précisément ce qui le désigne pour
    # reprendre la main quand il revient.
    priority = models.PositiveIntegerField(
        default=100,
        verbose_name='Rang de préséance',
        help_text='1 = reprend la main en priorité, 2 = secours, 3 = dernier '
                  'recours. Indépendant du rôle courant.',
    )

    is_enabled = models.BooleanField(default=True)
    is_current_active = models.BooleanField(default=False)
    is_failover_target = models.BooleanField(
        default=False,
        verbose_name='Peut recevoir la main',
        help_text='Décoché, ce serveur ne sera jamais promu, même seul '
                  'survivant.',
    )
    allow_auto_failover = models.BooleanField(
        default=True,
        verbose_name='Promotion automatique autorisée',
        help_text='Décoché, ce serveur ne peut être promu que par un '
                  'administrateur, jamais par la surveillance.',
    )

    last_heartbeat_at = models.DateTimeField(null=True, blank=True)

    # Date du RETOUR en bon état, pas du dernier battement de cœur. Permet
    # d'exiger une stabilité durable avant de rendre la main à un serveur qui
    # revient : un serveur qui oscille entre marche et panne satisferait
    # sinon le contrôle à chacun de ses passages en bon état.
    healthy_since = models.DateTimeField(
        'En bon état depuis', null=True, blank=True,
        help_text='Réinitialisée à chaque passage hors ligne.',
    )
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
    def stable_healthy_seconds(self):
        """Durée du bon état courant, ou None s'il n'est pas en bon état."""
        if not self.healthy_since:
            return None
        return int((timezone.now() - self.healthy_since).total_seconds())

    @property
    def can_be_failover_target(self):
        return (
            self.is_enabled
            and self.is_failover_target
            and self.role == 'secondary'
            and self.status in ('healthy', 'passive', 'warning')
        )

    @property
    def claims_to_be_writable(self):
        """Le serveur se dit inscriptible d'après son dernier bilan de santé.

        Sert à repérer un ancien principal qui revient sans avoir été
        rétrogradé : sa base accepte encore les écritures alors que le cluster
        a donné la main à un autre. C'est la situation à ne jamais laisser
        s'installer — deux bases divergentes, impossibles à fusionner.
        """
        lecture_seule = (self.last_health_payload or {}).get('read_only')
        return lecture_seule is False


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

    # ─── Grappe : convention de nommage ──────────────────────────────────────
    # Raccorder un serveur demandait de saisir son adresse complète et son rang
    # à la main, pour chaque machine. Avec une convention, les deux se
    # déduisent : « serveur2.exemple.fr » EST le serveur de rang 2. Le rang
    # n'est donc plus une donnée à tenir à jour séparément de l'adresse, et ces
    # deux-là ne peuvent plus se contredire.
    cluster_base_domain = models.CharField(
        max_length=200, blank=True,
        verbose_name='Domaine de la grappe',
        help_text='Ex. exemple.fr — les serveurs y seront cherchés sous le '
                  'motif ci-dessous.',
    )

    node_name_pattern = models.CharField(
        max_length=60, default='serveur{n}',
        verbose_name='Motif de nommage',
        help_text='{n} est remplacé par le rang : serveur1, serveur2… Le rang '
                  '1 est le serveur principal.',
    )

    cluster_max_nodes = models.PositiveSmallIntegerField(
        default=8,
        verbose_name='Rangs à explorer',
        help_text='La recherche essaie les rangs 1 à N. Un rang absent est '
                  'simplement ignoré.',
    )

    cluster_use_https = models.BooleanField(
        default=True,
        verbose_name='Joindre les serveurs en HTTPS',
        help_text='À décocher pour une grappe de test en réseau local, sans '
                  'certificat.',
    )

    # ─── Réseau privé entre sites ────────────────────────────────────────────
    # En production les serveurs ne partagent aucun réseau local. Il leur faut
    # un chemin privé unique, sur lequel passe TOUT : battements de cœur,
    # validation d'adhésion, réplication MySQL, synchronisation des médias.
    # Deux mécanismes séparés feraient deux fois plus de choses à casser — et
    # la réplication, elle, ne peut pas voyager en clair sur Internet.
    #
    # L'adresse privée se déduit du rang, comme le nom : rang 2 donne
    # 10.10.0.2. Un seul chiffre à retenir par serveur.
    mesh_subnet = models.CharField(
        max_length=40, default='10.10.0.0/24',
        verbose_name='Sous-réseau privé',
        help_text='Le dernier octet est le rang du serveur : rang 2 → 10.10.0.2.',
    )

    mesh_port = models.PositiveIntegerField(
        default=51820,
        verbose_name='Port WireGuard (UDP)',
        help_text='À ouvrir sur le pare-feu de chaque site.',
    )

    # ─── Retour d'un serveur (failback) ──────────────────────────────────────
    # Ce qui se passe quand un serveur tombé revient en bon état. Sans règle,
    # il revenait simplement « sain » dans la liste sans que rien ne tranche :
    # le serveur promu gardait la main indéfiniment, et le rang de préséance
    # ne servait plus à rien après la première bascule.
    FAILBACK_POLICY_CHOICES = [
        ('manual', 'Manuel — proposer, et attendre un administrateur'),
        ('never', 'Jamais — le serveur promu garde la main'),
        ('automatic', 'Automatique — le mieux classé reprend la main'),
    ]

    failback_policy = models.CharField(
        max_length=20,
        choices=FAILBACK_POLICY_CHOICES,
        default='manual',
        verbose_name="Au retour d'un serveur",
        help_text='« Automatique » ne rend la main que si le serveur est mieux '
                  'classé, stable depuis assez longtemps et sa réplication à '
                  'jour.',
    )

    failback_min_stable_seconds = models.PositiveIntegerField(
        default=300,
        verbose_name='Stabilité exigée avant de rendre la main',
        help_text='En secondes. Empêche un serveur qui oscille entre marche '
                  'et panne de reprendre la main à chaque passage en bon état.',
    )

    media_sync_enabled = models.BooleanField(default=True)
    database_replication_check_enabled = models.BooleanField(default=True)

    # Redirection du trafic par indirection : tous les domaines publics
    # pointent par CNAME vers l'enregistrement nommé ci-dessous, et la bascule
    # ne déplace que lui. Voir apps/high_availability/failover.py pour le
    # schéma complet, et docs/HAUTE-DISPONIBILITE.md pour la mise en place.
    cloudflare_failover_enabled = models.BooleanField(
        default=False,
        verbose_name='Déplacer les domaines à la bascule',
        help_text="Sans cette option, la bascule promeut la base mais le trafic "
                  "continue d'aller vers l'ancien serveur.",
    )
    cloudflare_zone_id = models.CharField(
        max_length=180, blank=True,
        verbose_name='Identifiant de zone Cloudflare',
        help_text='Facultatif si le nom ci-dessous est un domaine complet : la '
                  'zone est alors déduite automatiquement.',
    )
    cloudflare_dns_record_id = models.CharField(
        max_length=180, blank=True,
        verbose_name="Identifiant de l'enregistrement",
        help_text='Facultatif. Laissez vide pour retrouver automatiquement '
                  "l'enregistrement par son nom.",
    )
    cloudflare_record_name = models.CharField(
        max_length=180, default='erp',
        verbose_name="Nom de l'enregistrement d'indirection",
        help_text="Enregistrement que la bascule déplace, et vers lequel TOUS "
                  'vos domaines doivent pointer par CNAME (ex. « actif » ou '
                  '« actif.exemple.fr »). Il doit déjà exister dans la zone, '
                  'pointé vers le sous-domaine du serveur actif.',
    )

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
