"""
apps/orion_ops/models.py — Observabilité, fiabilité et opérations Orion ERP

Couvre :
  - Cartographie des composants et dépendances services
  - Objectifs de niveau de service (SLO/SLI/SLA)
  - Budget d'erreur et violations SLO
  - Registre des déploiements
  - Tests de restauration automatisés
  - Anomalies de qualité des données
  - Moteur de règles d'alerte
  - Métriques métier
  - Scores de santé étendus
  - Tâches Celery échouées
  - Prévisions de capacité
"""
import uuid

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# ──────────────────────────────────────────────────────────────────────────────
# 1. CARTOGRAPHIE DES COMPOSANTS ET DÉPENDANCES
# ──────────────────────────────────────────────────────────────────────────────

class ServiceComponent(models.Model):
    """Composant du système (serveur web, DB, Redis, Celery, API externe…)."""

    COMPONENT_TYPES = [
        ('web_app',        'Application web'),
        ('database',       'Base de données'),
        ('cache',          'Cache'),
        ('queue',          'File de messages'),
        ('broker',         'Broker'),
        ('celery_worker',  'Worker Celery'),
        ('celery_beat',    'Celery Beat'),
        ('storage',        'Stockage fichiers'),
        ('email',          'Serveur email'),
        ('payment',        'API paiement'),
        ('external_api',   'API externe'),
        ('notification',   'Service notification'),
        ('accounting',     'Service comptable'),
        ('partner',        'Service partenaire'),
        ('cdn',            'CDN'),
        ('tunnel',         'Tunnel / Proxy'),
    ]
    CRITICALITY_CHOICES = [
        ('critical', 'Critique — panne = ERP hors-service'),
        ('major',    'Majeur — panne = fonctionnalité dégradée'),
        ('minor',    'Mineur — panne = gêne partielle'),
    ]
    STATUS_CHOICES = [
        ('ok',       'Opérationnel'),
        ('degraded', 'Dégradé'),
        ('down',     'Hors-service'),
        ('unknown',  'Inconnu'),
        ('maintenance', 'Maintenance'),
    ]

    slug          = models.SlugField('Identifiant', max_length=60, unique=True)
    name          = models.CharField('Nom', max_length=150)
    component_type = models.CharField('Type', max_length=30, choices=COMPONENT_TYPES, db_index=True)
    criticality   = models.CharField('Criticité', max_length=20, choices=CRITICALITY_CHOICES, default='major')
    status        = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='unknown', db_index=True)
    last_check    = models.DateTimeField('Dernier contrôle', null=True, blank=True)
    check_url     = models.CharField('URL health check', max_length=500, blank=True)
    host          = models.CharField('Hôte / IP', max_length=255, blank=True)
    port          = models.PositiveIntegerField('Port', null=True, blank=True)
    version       = models.CharField('Version', max_length=50, blank=True)
    metadata      = models.JSONField('Métadonnées', default=dict, blank=True)
    notes         = models.TextField('Notes', blank=True)
    is_active     = models.BooleanField('Actif', default=True)
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Composant service'
        verbose_name_plural = 'Composants services'
        ordering = ['criticality', 'name']

    def __str__(self):
        return f'{self.name} [{self.get_status_display()}]'

    @property
    def status_color(self):
        return {'ok': 'success', 'degraded': 'warning', 'down': 'danger',
                'unknown': 'secondary', 'maintenance': 'info'}.get(self.status, 'secondary')


class ComponentDependency(models.Model):
    """Dépendance entre deux composants — permet la propagation des pannes."""

    DEP_TYPES = [
        ('required', 'Requise — panne source = panne cible'),
        ('optional', 'Optionnelle — panne source = dégradation cible'),
        ('fallback', 'Fallback — activée si la source tombe'),
    ]

    source      = models.ForeignKey(ServiceComponent, on_delete=models.CASCADE,
                                    related_name='dependencies_out', verbose_name='Composant source')
    target      = models.ForeignKey(ServiceComponent, on_delete=models.CASCADE,
                                    related_name='dependencies_in', verbose_name='Composant cible (dépend de)')
    dep_type    = models.CharField('Type', max_length=20, choices=DEP_TYPES, default='required')
    impact_desc = models.CharField('Impact en cas de panne', max_length=300, blank=True)
    notes       = models.TextField('Notes', blank=True)

    class Meta:
        verbose_name = 'Dépendance composant'
        unique_together = [('source', 'target')]

    def __str__(self):
        return f'{self.source.slug} → {self.target.slug} [{self.dep_type}]'


# ──────────────────────────────────────────────────────────────────────────────
# 2. OBJECTIFS DE NIVEAU DE SERVICE (SLO / SLI / SLA)
# ──────────────────────────────────────────────────────────────────────────────

class SLOTarget(models.Model):
    """Objectif de niveau de service (SLO) avec budget d'erreur."""

    PERIOD_CHOICES = [
        ('daily',   'Quotidien'),
        ('weekly',  'Hebdomadaire'),
        ('monthly', 'Mensuel'),
        ('rolling_7d',  'Glissant 7 jours'),
        ('rolling_30d', 'Glissant 30 jours'),
    ]
    STATUS_CHOICES = [
        ('ok',       'Respecté'),
        ('at_risk',  'À risque'),
        ('breached', 'Violé'),
        ('inactive', 'Inactif'),
        ('no_data',  'Données insuffisantes'),
    ]

    name            = models.CharField('Nom', max_length=150)
    slug            = models.SlugField('Identifiant', max_length=60, unique=True)
    description     = models.TextField('Description', blank=True)

    sli_sensor      = models.CharField('Capteur SLI', max_length=80,
                                       help_text='Type de capteur system_health.SensorReading')
    period          = models.CharField('Fenêtre', max_length=20, choices=PERIOD_CHOICES, default='monthly')

    target_pct      = models.FloatField('Objectif (%)', help_text='Ex: 99.9')
    sla_pct         = models.FloatField('SLA contractuel (%)', null=True, blank=True,
                                        help_text='Engagement externe — vide si interne uniquement')
    at_risk_pct     = models.FloatField('Seuil à risque (%)', null=True, blank=True,
                                        help_text='En-dessous → statut at_risk. Vide = target - 0.5 %')

    current_value   = models.FloatField('Valeur actuelle', null=True, blank=True)
    error_budget_pct = models.FloatField('Budget d\'erreur restant (%)', null=True, blank=True)
    status          = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='no_data', db_index=True)

    services        = models.JSONField('Services couverts', default=list, blank=True)
    components      = models.ManyToManyField(ServiceComponent, blank=True, verbose_name='Composants concernés')

    owner           = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                        related_name='owned_slos', verbose_name='Responsable')
    enabled         = models.BooleanField('Actif', default=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Objectif de service (SLO)'
        verbose_name_plural = 'Objectifs de service (SLO)'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} — cible {self.target_pct} %'

    @property
    def status_color(self):
        return {'ok': 'success', 'at_risk': 'warning', 'breached': 'danger',
                'inactive': 'secondary', 'no_data': 'secondary'}.get(self.status, 'secondary')

    def compute_at_risk_threshold(self):
        return self.at_risk_pct if self.at_risk_pct is not None else max(0.0, self.target_pct - 0.5)


class SLOBreach(models.Model):
    """Violation d'un SLO sur une période donnée."""

    SEVERITY_CHOICES = [
        ('warning', 'Avertissement — budget à risque'),
        ('breach',  'Violation — objectif manqué'),
        ('sla',     'Violation SLA — engagement manqué'),
    ]

    slo          = models.ForeignKey(SLOTarget, on_delete=models.CASCADE, related_name='breaches')
    severity     = models.CharField('Gravité', max_length=20, choices=SEVERITY_CHOICES, default='breach')
    period_start = models.DateTimeField('Début période')
    period_end   = models.DateTimeField('Fin période')
    target_pct   = models.FloatField('Objectif au moment de la violation')
    actual_pct   = models.FloatField('Valeur réelle atteinte')
    error_minutes = models.FloatField('Minutes d\'erreur', default=0.0)
    budget_consumed_pct = models.FloatField('Budget consommé (%)', default=0.0)
    incident     = models.ForeignKey('system_health.SystemIncident', null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='slo_breaches')
    notes        = models.TextField('Notes', blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Violation SLO'
        verbose_name_plural = 'Violations SLO'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.slo.name} — {self.actual_pct:.2f} % (cible {self.target_pct} %)'


# ──────────────────────────────────────────────────────────────────────────────
# 3. REGISTRE DES DÉPLOIEMENTS
# ──────────────────────────────────────────────────────────────────────────────

class Deployment(models.Model):
    """Registre d'un déploiement en production."""

    ENVIRONMENTS = [
        ('production', 'Production'),
        ('staging',    'Préproduction'),
        ('dev',        'Développement'),
    ]
    RESULTS = [
        ('pending',     'En cours'),
        ('success',     'Succès'),
        ('failed',      'Échec'),
        ('partial',     'Partiel'),
        ('rolled_back', 'Rollback'),
    ]

    uid              = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    version          = models.CharField('Version', max_length=50)
    environment      = models.CharField('Environnement', max_length=20, choices=ENVIRONMENTS, default='production', db_index=True)
    deployed_at      = models.DateTimeField('Déployé le', default=timezone.now, db_index=True)
    deployed_by      = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                         related_name='deployments', verbose_name='Déployé par')
    git_commit       = models.CharField('Commit git', max_length=40, blank=True)
    git_branch       = models.CharField('Branche', max_length=150, blank=True)
    modules_changed  = models.JSONField('Modules modifiés', default=list, blank=True)
    migrations_count = models.PositiveSmallIntegerField('Migrations appliquées', default=0)
    features         = models.TextField('Nouvelles fonctionnalités', blank=True)
    fixes            = models.TextField('Corrections', blank=True)
    risks            = models.TextField('Risques identifiés', blank=True)
    tests_passed     = models.BooleanField('Tests passés', null=True, blank=True)
    rollback_procedure = models.TextField('Procédure de rollback', blank=True)
    result           = models.CharField('Résultat', max_length=20, choices=RESULTS, default='pending', db_index=True)
    metrics_before   = models.JSONField('Scores avant déploiement', default=dict, blank=True)
    metrics_after    = models.JSONField('Scores après déploiement', default=dict, blank=True)
    notes            = models.TextField('Notes', blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)
    updated_at       = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Déploiement'
        verbose_name_plural = 'Déploiements'
        ordering = ['-deployed_at']

    def __str__(self):
        return f'v{self.version} — {self.environment} — {self.deployed_at:%d/%m/%Y %H:%M}'

    @property
    def result_color(self):
        return {'success': 'success', 'failed': 'danger', 'partial': 'warning',
                'rolled_back': 'warning', 'pending': 'info'}.get(self.result, 'secondary')


# ──────────────────────────────────────────────────────────────────────────────
# 4. TESTS DE RESTAURATION
# ──────────────────────────────────────────────────────────────────────────────

class RestoreTest(models.Model):
    """Résultat d'un test de restauration de sauvegarde."""

    RESULTS = [
        ('success', 'Succès'),
        ('partial', 'Partiel'),
        ('failed',  'Échec'),
    ]

    backup_job       = models.ForeignKey('backups.BackupJob', on_delete=models.PROTECT,
                                         related_name='restore_tests', verbose_name='Sauvegarde testée')
    tested_at        = models.DateTimeField('Testé le', auto_now_add=True, db_index=True)
    duration_secs    = models.FloatField('Durée (s)', null=True, blank=True)
    result           = models.CharField('Résultat', max_length=20, choices=RESULTS, db_index=True)
    tables_checked   = models.PositiveIntegerField('Tables vérifiées', default=0)
    rows_verified    = models.PositiveIntegerField('Lignes vérifiées', default=0)
    constraints_ok   = models.BooleanField('Contraintes intégrité OK', null=True, blank=True)
    rpo_minutes      = models.FloatField('RPO réel (min)', null=True, blank=True,
                                         help_text='Âge des données au moment de la restauration')
    rto_minutes      = models.FloatField('RTO réel (min)', null=True, blank=True,
                                         help_text='Durée totale pour restaurer et valider')
    errors           = models.JSONField('Erreurs détectées', default=list, blank=True)
    recommendations  = models.TextField('Recommandations', blank=True)
    triggered_by     = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                         related_name='restore_tests', verbose_name='Déclenché par')
    is_automated     = models.BooleanField('Test automatique', default=False)

    class Meta:
        verbose_name = 'Test de restauration'
        verbose_name_plural = 'Tests de restauration'
        ordering = ['-tested_at']

    def __str__(self):
        return f'Restore {self.result} — {self.tested_at:%d/%m/%Y} ({self.rto_minutes or "?"} min)'

    @property
    def result_color(self):
        return {'success': 'success', 'partial': 'warning', 'failed': 'danger'}.get(self.result, 'secondary')


# ──────────────────────────────────────────────────────────────────────────────
# 5. QUALITÉ DES DONNÉES
# ──────────────────────────────────────────────────────────────────────────────

class DataQualityAnomaly(models.Model):
    """Anomalie de qualité détectée lors d'un audit automatique."""

    ANOMALY_TYPES = [
        ('duplicate_customer',      'Doublons clients (même email)'),
        ('duplicate_product',       'Doublons produits'),
        ('orphan_payment',          'Paiement sans facture'),
        ('orphan_journal_entry',    'Écriture comptable sans journal'),
        ('unpaid_invoice_60d',      'Facture impayée > 60 jours'),
        ('negative_stock',          'Stock négatif'),
        ('orphan_stock_movement',   'Mouvement de stock sans source'),
        ('invoice_modified_after_validation', 'Facture modifiée après validation'),
        ('numbering_gap',           'Interruption dans la numérotation'),
        ('missing_required_field',  'Champ obligatoire manquant'),
        ('referential_integrity',   'Violation d\'intégrité référentielle'),
        ('stale_data',              'Données obsolètes non mises à jour'),
        ('currency_mismatch',       'Incohérence de devise'),
        ('date_logic_error',        'Erreur logique de date'),
        ('custom',                  'Anomalie personnalisée'),
    ]
    SEVERITIES = [
        ('critical', 'Critique'),
        ('high',     'Élevée'),
        ('medium',   'Modérée'),
        ('low',      'Faible'),
    ]
    STATUS_CHOICES = [
        ('open',         'Ouverte'),
        ('acknowledged', 'Prise en compte'),
        ('fixing',       'En correction'),
        ('resolved',     'Résolue'),
        ('ignored',      'Ignorée'),
    ]
    MODULES = [
        ('crm',        'CRM / Clients'),
        ('sales',      'Ventes'),
        ('accounting', 'Comptabilité'),
        ('inventory',  'Stock'),
        ('hr',         'RH'),
        ('ecommerce',  'E-commerce'),
        ('purchases',  'Achats'),
        ('other',      'Autre'),
    ]

    anomaly_type = models.CharField('Type', max_length=60, choices=ANOMALY_TYPES, db_index=True)
    severity     = models.CharField('Gravité', max_length=20, choices=SEVERITIES, db_index=True)
    count        = models.PositiveIntegerField('Nombre d\'occurrences')
    module       = models.CharField('Module', max_length=20, choices=MODULES, db_index=True)
    examples     = models.JSONField('Exemples (max 5)', default=list, blank=True,
                                    help_text='[{id, detail}] — données anonymisées')
    cause        = models.CharField('Cause identifiée', max_length=300, blank=True)
    fix_hint     = models.TextField('Conseil de correction', blank=True)
    can_auto_fix = models.BooleanField('Correction automatique possible', default=False)
    status       = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='open', db_index=True)
    owner        = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='data_anomalies', verbose_name='Responsable')
    detected_at  = models.DateTimeField('Détectée le', auto_now_add=True, db_index=True)
    resolved_at  = models.DateTimeField('Résolue le', null=True, blank=True)
    ignore_reason = models.TextField('Justification ignorée', blank=True)

    class Meta:
        verbose_name = 'Anomalie qualité données'
        verbose_name_plural = 'Anomalies qualité données'
        ordering = ['-detected_at']
        indexes = [models.Index(fields=['severity', 'status'])]

    def __str__(self):
        return f'[{self.severity}] {self.get_anomaly_type_display()} — {self.count} occurrence(s)'

    @property
    def severity_color(self):
        return {'critical': 'danger', 'high': 'warning',
                'medium': 'info', 'low': 'secondary'}.get(self.severity, 'secondary')


# ──────────────────────────────────────────────────────────────────────────────
# 6. MOTEUR DE RÈGLES D'ALERTE
# ──────────────────────────────────────────────────────────────────────────────

class AlertRule(models.Model):
    """Règle d'alerte configurable déclenché sur les capteurs ou métriques."""

    SOURCES = [
        ('sensor',          'Capteur système (SensorReading)'),
        ('business_metric', 'Métrique métier (BusinessMetricReading)'),
        ('slo',             'SLO (SLOTarget)'),
        ('data_quality',    'Qualité données (DataQualityAnomaly)'),
        ('custom',          'Requête personnalisée'),
    ]
    OPERATORS = [
        ('gt',  '>'),
        ('lt',  '<'),
        ('gte', '>='),
        ('lte', '<='),
        ('eq',  '='),
        ('neq', '≠'),
    ]
    SEVERITIES = [
        ('info',      'Info'),
        ('warning',   'Avertissement'),
        ('critical',  'Critique'),
        ('emergency', 'Urgence'),
    ]
    ACTIONS = [
        ('create_alert',    'Créer une alerte système'),
        ('create_incident', 'Créer un incident automatiquement'),
        ('notify_superusers','Notifier les super-admins'),
        ('notify_team',     'Notifier l\'équipe assignée'),
        ('webhook',         'Appeler un webhook'),
    ]

    name         = models.CharField('Nom', max_length=150, unique=True)
    description  = models.TextField('Description', blank=True)
    source       = models.CharField('Source', max_length=30, choices=SOURCES, default='sensor')
    metric_key   = models.CharField('Clé / Type de métrique', max_length=80)
    operator     = models.CharField('Opérateur', max_length=5, choices=OPERATORS, default='gt')
    threshold    = models.FloatField('Seuil de déclenchement')
    duration_min = models.PositiveIntegerField('Durée minimum (min)', default=0,
                                               help_text='0 = déclenchement immédiat')
    frequency_min = models.PositiveIntegerField('Fréquence de vérification (min)', default=5)
    severity     = models.CharField('Gravité', max_length=20, choices=SEVERITIES, default='warning')
    actions      = models.JSONField('Actions', default=list,
                                    help_text='Liste de: create_alert, create_incident, notify_superusers…')
    notify_users = models.JSONField('Utilisateurs à notifier (IDs)', default=list, blank=True)
    webhook_url  = models.CharField('URL webhook', max_length=500, blank=True)
    enabled      = models.BooleanField('Actif', default=True)
    silence_until = models.DateTimeField('Silencieux jusqu\'à', null=True, blank=True)
    last_triggered = models.DateTimeField('Dernière activation', null=True, blank=True)
    last_status  = models.CharField('Dernier statut', max_length=20, default='ok')
    trigger_count = models.PositiveIntegerField('Nombre d\'activations', default=0)
    owner        = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='alert_rules', verbose_name='Responsable')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Règle d\'alerte'
        verbose_name_plural = 'Règles d\'alerte'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} [{self.severity}]'

    def is_silenced(self):
        return bool(self.silence_until and self.silence_until > timezone.now())


# ──────────────────────────────────────────────────────────────────────────────
# 7. MÉTRIQUES MÉTIER
# ──────────────────────────────────────────────────────────────────────────────

class BusinessMetricReading(models.Model):
    """Lecture d'une métrique fonctionnelle (commandes, paiements, stocks…)."""

    METRIC_TYPES = [
        # Volume
        ('quotes_24h',            'Devis générés (24h)'),
        ('invoices_24h',          'Factures générées (24h)'),
        ('payments_24h',          'Paiements enregistrés (24h)'),
        ('payments_failed_1h',    'Paiements échoués (1h)'),
        ('orders_blocked',        'Commandes bloquées'),
        ('orders_24h',            'Commandes reçues (24h)'),
        # Stock
        ('negative_stock_count',  'Produits en stock négatif'),
        ('low_stock_count',       'Produits en rupture imminente'),
        # Qualité
        ('imports_incomplete',    'Imports incomplets en attente'),
        ('notifications_pending', 'Notifications en attente d\'envoi'),
        ('sync_errors_1h',        'Erreurs de synchronisation (1h)'),
        # Délais
        ('avg_quote_to_order_days', 'Délai moyen devis→commande (jours)'),
        ('avg_invoice_payment_days','Délai moyen facture→paiement (jours)'),
        # E-commerce
        ('ecommerce_orders_24h',  'Commandes boutique (24h)'),
        ('cart_abandonment_pct',  'Taux abandon panier (%)'),
        ('conversion_rate_pct',   'Taux conversion (%)'),
        # Custom
        ('custom',                'Métrique personnalisée'),
    ]
    STATUS_CHOICES = [
        ('ok',       'Normal'),
        ('warning',  'Attention'),
        ('critical', 'Critique'),
        ('unknown',  'Inconnu'),
    ]

    metric_type  = models.CharField('Type', max_length=60, choices=METRIC_TYPES, db_index=True)
    value        = models.FloatField('Valeur')
    status       = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='ok')
    company      = models.ForeignKey('core.Company', null=True, blank=True,
                                     on_delete=models.SET_NULL, related_name='business_metrics')
    metadata     = models.JSONField('Détails', default=dict, blank=True)
    collected_at = models.DateTimeField('Collecté à', auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Métrique métier'
        verbose_name_plural = 'Métriques métier'
        ordering = ['-collected_at']
        indexes = [models.Index(fields=['metric_type', '-collected_at'])]

    def __str__(self):
        return f'{self.metric_type}={self.value} [{self.status}]'


# ──────────────────────────────────────────────────────────────────────────────
# 8. SCORES DE SANTÉ ÉTENDUS
# ──────────────────────────────────────────────────────────────────────────────

class HealthScoreRecord(models.Model):
    """Score de santé calculé pour un domaine donné (hors scores classiques de HealthSnapshot)."""

    DOMAINS = [
        ('data_quality',       'Qualité des données'),
        ('resilience',         'Résilience'),
        ('integrations',       'Intégrations'),
        ('business_processes', 'Processus métier'),
        ('restore_readiness',  'Préparation restauration'),
        ('capacity',           'Capacité / Croissance'),
        ('compliance',         'Conformité'),
    ]
    STATUS_CHOICES = [
        ('ok',          'Bon'),
        ('warning',     'Attention'),
        ('critical',    'Critique'),
        ('unavailable', 'Indisponible'),
        ('stale',       'Données obsolètes'),
    ]

    domain        = models.CharField('Domaine', max_length=30, choices=DOMAINS, db_index=True)
    score         = models.PositiveSmallIntegerField('Score /100', null=True, blank=True)
    status        = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='unavailable')
    points_detail = models.JSONField('Détail des points', default=dict, blank=True,
                                     help_text='{category: {earned, max, reason}}')
    metrics_used  = models.JSONField('Métriques utilisées', default=dict, blank=True)
    is_stale      = models.BooleanField('Données obsolètes', default=False)
    computed_at   = models.DateTimeField('Calculé le', auto_now_add=True, db_index=True)
    expires_at    = models.DateTimeField('Expire le', null=True, blank=True)

    class Meta:
        verbose_name = 'Score de santé étendu'
        verbose_name_plural = 'Scores de santé étendus'
        ordering = ['-computed_at']
        indexes = [models.Index(fields=['domain', '-computed_at'])]

    def __str__(self):
        score_str = f'{self.score}/100' if self.score is not None else 'N/A'
        return f'{self.get_domain_display()} — {score_str} [{self.status}]'

    @property
    def status_color(self):
        return {'ok': 'success', 'warning': 'warning', 'critical': 'danger',
                'unavailable': 'secondary', 'stale': 'secondary'}.get(self.status, 'secondary')


# ──────────────────────────────────────────────────────────────────────────────
# 9. TÂCHES CELERY ÉCHOUÉES
# ──────────────────────────────────────────────────────────────────────────────

class FailedTask(models.Model):
    """Tâche Celery ayant échoué — traçabilité et relance manuelle."""

    STATUS_CHOICES = [
        ('failed',   'Échouée'),
        ('retrying', 'Nouvelle tentative'),
        ('closed',   'Fermée (non relancée)'),
        ('replayed', 'Relancée'),
    ]

    task_id      = models.CharField('ID tâche Celery', max_length=150, unique=True, db_index=True)
    task_name    = models.CharField('Nom de la tâche', max_length=300)
    queue        = models.CharField('File', max_length=60, default='default')
    args_masked  = models.JSONField('Arguments (masqués)', default=dict, blank=True,
                                    help_text='Secrets remplacés par ***')
    created_at   = models.DateTimeField('Créée le')
    executed_at  = models.DateTimeField('Exécutée le', null=True, blank=True)
    failed_at    = models.DateTimeField('Échouée le', auto_now_add=True, db_index=True)
    retries      = models.PositiveSmallIntegerField('Tentatives', default=0)
    error_type   = models.CharField('Type d\'erreur', max_length=200)
    error_safe   = models.TextField('Trace (sans secrets)')
    status       = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='failed', db_index=True)
    triggered_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='triggered_tasks', verbose_name='Déclenchée par')
    replayed_by  = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='replayed_tasks', verbose_name='Relancée par')
    replayed_at  = models.DateTimeField('Relancée le', null=True, blank=True)
    object_type  = models.CharField('Type d\'objet lié', max_length=100, blank=True)
    object_id    = models.CharField('ID objet lié', max_length=50, blank=True)
    can_replay   = models.BooleanField('Relance possible', default=True)
    close_reason = models.TextField('Justification fermeture', blank=True)

    class Meta:
        verbose_name = 'Tâche Celery échouée'
        verbose_name_plural = 'Tâches Celery échouées'
        ordering = ['-failed_at']
        indexes = [models.Index(fields=['task_name', 'status'])]

    def __str__(self):
        return f'{self.task_name} [{self.status}] — {self.failed_at:%d/%m %H:%M}'


# ──────────────────────────────────────────────────────────────────────────────
# 10. PRÉVISIONS DE CAPACITÉ
# ──────────────────────────────────────────────────────────────────────────────

class CapacityTrend(models.Model):
    """Tendance et prévision de capacité pour une ressource donnée."""

    RESOURCE_TYPES = [
        ('disk_c',      'Disque C: (Go libre)'),
        ('disk_d',      'Disque D: (Go libre)'),
        ('db_size_gb',  'Taille DB (Go)'),
        ('memory_pct',  'Mémoire (%)'),
        ('cpu_avg',     'CPU moyen (%)'),
        ('table_rows',  'Lignes en DB (estimé)'),
        ('backup_size', 'Taille des sauvegardes (Go)'),
    ]

    resource_type     = models.CharField('Ressource', max_length=30, choices=RESOURCE_TYPES, db_index=True)
    current_value     = models.FloatField('Valeur actuelle')
    value_7d_ago      = models.FloatField('Il y a 7 jours', null=True, blank=True)
    value_30d_ago     = models.FloatField('Il y a 30 jours', null=True, blank=True)
    growth_7d_pct     = models.FloatField('Croissance 7j (%)', null=True, blank=True)
    growth_30d_pct    = models.FloatField('Croissance 30j (%)', null=True, blank=True)
    days_until_limit  = models.IntegerField('Jours avant limite', null=True, blank=True,
                                            help_text='Estimation linéaire. Null = stable ou décroissant.')
    saturation_date   = models.DateField('Date de saturation estimée', null=True, blank=True)
    alert_threshold   = models.FloatField('Seuil d\'alerte', null=True, blank=True)
    recommendation    = models.TextField('Recommandation', blank=True)
    computed_at       = models.DateTimeField('Calculé le', auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Tendance de capacité'
        verbose_name_plural = 'Tendances de capacité'
        ordering = ['-computed_at']
        indexes = [models.Index(fields=['resource_type', '-computed_at'])]

    def __str__(self):
        days = f'{self.days_until_limit}j' if self.days_until_limit else '∞'
        return f'{self.resource_type}={self.current_value} | saturation dans {days}'


# ──────────────────────────────────────────────────────────────────────────────
# 11. PLAN DE CONTINUITÉ D'ACTIVITÉ (BCP)
# ──────────────────────────────────────────────────────────────────────────────

class BCPScenario(models.Model):
    """Scénario de continuité d'activité — procédures de rétablissement par type d'incident."""

    SCENARIO_TYPES = [
        ('data_loss',        'Perte de données critique'),
        ('service_down',     'Service ERP indisponible'),
        ('security_breach',  'Violation de sécurité / accès non autorisé'),
        ('ransomware',       'Rançongiciel / cyberattaque'),
        ('hardware_failure', 'Panne matérielle serveur'),
        ('mass_delete',      'Suppression accidentelle de données'),
        ('vendor_failure',   'Défaillance fournisseur critique (Cloudflare, Stripe…)'),
        ('natural_disaster', 'Sinistre / catastrophe naturelle'),
    ]
    PRIORITIES = [
        ('critical', 'Critique — activation immédiate'),
        ('high',     'Élevée — < 4 heures'),
        ('medium',   'Modérée — < 24 heures'),
        ('low',      'Faible — < 72 heures'),
    ]
    EXERCISE_RESULTS = [
        ('not_tested', 'Non testé'),
        ('success',    'Exercice réussi'),
        ('partial',    'Partiellement réussi'),
        ('failed',     'Exercice échoué'),
    ]

    name                = models.CharField('Nom', max_length=200)
    scenario_type       = models.CharField('Type de scénario', max_length=30,
                                           choices=SCENARIO_TYPES, db_index=True)
    description         = models.TextField('Description du scénario', blank=True)
    priority            = models.CharField('Priorité', max_length=20,
                                           choices=PRIORITIES, default='high')
    rto_hours           = models.FloatField('RTO cible (heures)',
                                            help_text='Recovery Time Objective — délai max de rétablissement')
    rpo_hours           = models.FloatField('RPO cible (heures)',
                                            help_text='Recovery Point Objective — perte de données maximale acceptable')
    procedures          = models.JSONField('Procédures de rétablissement', default=list, blank=True,
                                           help_text='[{step, owner, duration_min, notes}]')
    escalation_contacts = models.JSONField('Contacts d\'escalade', default=list, blank=True,
                                           help_text='[{name, role, phone, email}]')
    affected_components = models.ManyToManyField(ServiceComponent, blank=True,
                                                  verbose_name='Composants concernés')
    last_exercised      = models.DateTimeField('Dernier exercice', null=True, blank=True)
    last_result         = models.CharField('Résultat exercice', max_length=20,
                                           choices=EXERCISE_RESULTS, default='not_tested')
    exercise_notes      = models.TextField('Notes exercice', blank=True)
    owner               = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                            related_name='bcp_scenarios', verbose_name='Responsable BCP')
    is_active           = models.BooleanField('Actif', default=True)
    created_at          = models.DateTimeField(auto_now_add=True)
    updated_at          = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Scénario BCP'
        verbose_name_plural = 'Scénarios BCP'
        ordering = ['priority', 'scenario_type']
        indexes = [models.Index(fields=['scenario_type', 'priority'])]

    def __str__(self):
        return f'{self.name} [RTO {self.rto_hours}h / RPO {self.rpo_hours}h]'

    @property
    def is_tested(self):
        return self.last_result != 'not_tested'

    @property
    def needs_retest(self):
        if not self.last_exercised:
            return True
        from datetime import timedelta
        return (timezone.now() - self.last_exercised).days > 180

    @property
    def priority_color(self):
        return {'critical': 'danger', 'high': 'warning',
                'medium': 'info', 'low': 'secondary'}.get(self.priority, 'secondary')


# ──────────────────────────────────────────────────────────────────────────────
# 12. TESTS DE DÉFAILLANCE (CHAOS ENGINEERING LÉGER)
# ──────────────────────────────────────────────────────────────────────────────

class FailureTest(models.Model):
    """Enregistrement d'un test de défaillance délibéré (fire drill)."""

    TEST_TYPES = [
        ('kill_worker',      'Arrêt d\'un worker Celery'),
        ('kill_beat',        'Arrêt Celery Beat'),
        ('db_disconnect',    'Coupure base de données'),
        ('redis_disconnect', 'Coupure Redis / broker'),
        ('disk_pressure',    'Simulation pression disque'),
        ('high_cpu_load',    'Test de charge CPU'),
        ('api_timeout',      'Simulation timeout API externe'),
        ('backup_restore',   'Test restauration complète'),
        ('failover',         'Test basculement'),
        ('custom',           'Test personnalisé'),
    ]
    RESULTS = [
        ('pending',  'En cours'),
        ('success',  'Succès — système résilient'),
        ('partial',  'Partiel — dégradation acceptable'),
        ('failed',   'Échec — point de défaillance identifié'),
        ('aborted',  'Abandonné'),
    ]

    name                 = models.CharField('Nom', max_length=200)
    test_type            = models.CharField('Type de test', max_length=30,
                                            choices=TEST_TYPES, db_index=True)
    description          = models.TextField('Description / objectif', blank=True)
    target_component     = models.ForeignKey(ServiceComponent, null=True, blank=True,
                                             on_delete=models.SET_NULL,
                                             related_name='failure_tests',
                                             verbose_name='Composant cible')
    planned_at           = models.DateTimeField('Planifié le', null=True, blank=True)
    executed_at          = models.DateTimeField('Exécuté le', null=True, blank=True, db_index=True)
    duration_secs        = models.FloatField('Durée (s)', null=True, blank=True)
    result               = models.CharField('Résultat', max_length=20,
                                            choices=RESULTS, default='pending', db_index=True)
    impact_observed      = models.TextField('Impact observé', blank=True)
    recovery_time_secs   = models.FloatField('Temps de rétablissement (s)', null=True, blank=True)
    automated_recovery   = models.BooleanField('Rétablissement automatique', null=True, blank=True)
    actions_triggered    = models.JSONField('Alertes / incidents déclenchés', default=list, blank=True)
    lessons_learned      = models.TextField('Leçons apprises', blank=True)
    remediation_required = models.BooleanField('Remédiation nécessaire', default=False)
    remediation_done     = models.BooleanField('Remédiation effectuée', default=False)
    remediation_notes    = models.TextField('Notes de remédiation', blank=True)
    executed_by          = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                             related_name='failure_tests', verbose_name='Exécuté par')
    incident             = models.ForeignKey('system_health.SystemIncident', null=True, blank=True,
                                             on_delete=models.SET_NULL,
                                             related_name='failure_tests',
                                             verbose_name='Incident associé')
    created_at           = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Test de défaillance'
        verbose_name_plural = 'Tests de défaillance'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} [{self.result}] — {self.executed_at or self.planned_at or "non planifié"}'

    @property
    def result_color(self):
        return {'success': 'success', 'partial': 'warning',
                'failed': 'danger', 'aborted': 'secondary',
                'pending': 'info'}.get(self.result, 'secondary')
