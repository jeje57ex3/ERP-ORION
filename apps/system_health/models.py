"""
apps/system_health/models.py — Module Santé du système (Super Admin)

Couvre : erreurs techniques, incidents, registre des risques,
capteurs temps-réel, seuils d'alerte, permissions granulaires, audit.
"""
import uuid
import hashlib

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

from apps.core.models import Company


# ─── Niveaux de gravité / sévérité ────────────────────────────────────────────

SEVERITY_CHOICES = [
    ('debug',    'Debug'),
    ('info',     'Info'),
    ('warning',  'Attention'),
    ('error',    'Erreur'),
    ('critical', 'Critique'),
]

SEVERITY_COLORS = {
    'debug':    'secondary',
    'info':     'info',
    'warning':  'warning',
    'error':    'danger',
    'critical': 'danger',
}

# ─── État global ───────────────────────────────────────────────────────────────

HEALTH_STATUSES = [
    ('healthy',     'Sain'),
    ('degraded',    'Dégradé'),
    ('unstable',    'Instable'),
    ('critical',    'Critique'),
    ('unavailable', 'Indisponible'),
    ('unknown',     'Inconnu'),
]


# ──────────────────────────────────────────────────────────────────────────────
# 1. RAPPORTS D'ERREURS
# ──────────────────────────────────────────────────────────────────────────────

class SystemError(models.Model):
    """Erreur technique ou fonctionnelle centralisée (16.2)."""

    ERROR_STATUSES = [
        ('new',        'Nouvelle'),
        ('analysed',   'Analysée'),
        ('confirmed',  'Confirmée'),
        ('in_progress','En cours'),
        ('monitoring', 'Surveillée'),
        ('resolved',   'Résolue'),
        ('ignored',    'Ignorée'),
        ('reopened',   'Rouverte'),
    ]

    # Identité
    uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    fingerprint = models.CharField(max_length=64, db_index=True)  # regroupement erreurs similaires

    # Classification
    severity      = models.CharField('Gravité', max_length=20, choices=SEVERITY_CHOICES, db_index=True)
    module        = models.CharField('Module', max_length=100, db_index=True)
    environment   = models.CharField('Environnement', max_length=50, default='production')
    error_type    = models.CharField('Type', max_length=200)
    app_version   = models.CharField('Version app', max_length=50, blank=True)

    # Messages
    user_message      = models.TextField('Message utilisateur')
    technical_message = models.TextField('Message technique')  # masqué à l'affichage selon rôle

    # Occurrences
    occurrence_count = models.PositiveIntegerField('Occurrences', default=1)
    first_seen       = models.DateTimeField('Première occurrence', default=timezone.now)
    last_seen        = models.DateTimeField('Dernière occurrence', auto_now=True)

    # Contexte
    affected_user    = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                         related_name='system_errors', verbose_name='Utilisateur')
    company          = models.ForeignKey(Company, null=True, blank=True, on_delete=models.SET_NULL,
                                         related_name='system_errors', verbose_name='Établissement')
    api_route        = models.CharField('Route / Action', max_length=500, blank=True)
    http_method      = models.CharField('Méthode HTTP', max_length=10, blank=True)
    response_code    = models.PositiveSmallIntegerField('Code réponse', null=True, blank=True)
    correlation_id   = models.CharField('ID corrélation', max_length=100, blank=True, db_index=True)
    user_agent       = models.CharField('Navigateur / Appareil', max_length=500, blank=True)

    # Traitement
    status        = models.CharField('Statut', max_length=20, choices=ERROR_STATUSES, default='new', db_index=True)
    assigned_to   = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                      related_name='assigned_errors', verbose_name='Responsable')
    probable_cause    = models.TextField('Cause probable', blank=True)
    solution_applied  = models.TextField('Solution appliquée', blank=True)
    resolved_at       = models.DateTimeField('Date résolution', null=True, blank=True)
    ignore_reason     = models.TextField('Justification ignorée', blank=True)

    # Lien incident
    incident = models.ForeignKey('SystemIncident', null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name='errors', verbose_name='Incident lié')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Erreur système'
        verbose_name_plural = 'Erreurs système'
        ordering = ['-last_seen']
        indexes = [
            models.Index(fields=['severity', 'status']),
            models.Index(fields=['module', 'status']),
            models.Index(fields=['fingerprint', 'status']),
        ]

    def __str__(self):
        return f'[{self.get_severity_display()}] {self.error_type} — {self.module}'

    @property
    def severity_color(self):
        return SEVERITY_COLORS.get(self.severity, 'secondary')

    @classmethod
    def compute_fingerprint(cls, module, error_type, technical_message=''):
        content = f"{module}:{error_type}:{technical_message[:200]}"
        return hashlib.sha256(content.encode('utf-8', errors='replace')).hexdigest()[:64]

    def safe_technical_message(self, can_view_sensitive=False):
        """Retourne le message technique en masquant les secrets."""
        if can_view_sensitive:
            return self.technical_message
        import re
        msg = self.technical_message
        msg = re.sub(r'(password|passwd|secret|token|key|api_key|apikey)\s*[=:]\s*\S+',
                     r'\1=***', msg, flags=re.IGNORECASE)
        msg = re.sub(r'Bearer\s+\S+', 'Bearer ***', msg, flags=re.IGNORECASE)
        return msg


class ErrorComment(models.Model):
    """Commentaire sur une erreur."""
    error     = models.ForeignKey(SystemError, on_delete=models.CASCADE, related_name='comments')
    author    = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    content   = models.TextField('Commentaire')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Commentaire erreur'


# ──────────────────────────────────────────────────────────────────────────────
# 2. INCIDENTS
# ──────────────────────────────────────────────────────────────────────────────

class SystemIncident(models.Model):
    """Incident de production (16.11)."""

    INCIDENT_SEVERITIES = [
        ('minor',     'Mineur'),
        ('major',     'Majeur'),
        ('critical',  'Critique'),
        ('emergency', 'Urgence'),
    ]
    INCIDENT_STATUSES = [
        ('detected',      'Détecté'),
        ('confirmed',     'Confirmé'),
        ('assigned',      'Assigné'),
        ('investigating', 'En investigation'),
        ('fixing',        'En correction'),
        ('monitoring',    'Surveillance'),
        ('resolved',      'Résolu'),
        ('closed',        'Clôturé'),
        ('reopened',      'Rouvert'),
    ]

    title              = models.CharField('Titre', max_length=300)
    severity           = models.CharField('Gravité', max_length=20, choices=INCIDENT_SEVERITIES, db_index=True)
    status             = models.CharField('Statut', max_length=20, choices=INCIDENT_STATUSES, default='detected', db_index=True)
    description        = models.TextField('Description')
    affected_services  = models.JSONField('Services affectés', default=list)
    affected_companies = models.ManyToManyField(Company, blank=True, verbose_name='Établissements affectés')

    started_at    = models.DateTimeField('Début', default=timezone.now)
    detected_at   = models.DateTimeField('Détection', default=timezone.now)
    resolved_at   = models.DateTimeField('Résolution', null=True, blank=True)
    closed_at     = models.DateTimeField('Clôture', null=True, blank=True)

    # Traçabilité
    uid                    = models.CharField('Référence', max_length=20, blank=True,
                                              help_text='Format INC-XXXX — généré automatiquement')
    acknowledged_at        = models.DateTimeField('Accusé le', null=True, blank=True)
    acknowledged_by        = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                               related_name='acknowledged_incidents', verbose_name='Accusé par')

    # Contexte technique
    app_version            = models.CharField('Version app', max_length=50, blank=True)
    component              = models.CharField('Composant', max_length=60, blank=True,
                                              help_text='server | database | celery | redis | app | external_api…')

    # Contexte métier
    business_module        = models.CharField('Module métier affecté', max_length=100, blank=True)
    affected_users_count   = models.PositiveIntegerField('Utilisateurs impactés (estimation)', null=True, blank=True)

    # Équipe & escalade
    team                   = models.JSONField('Équipe assignée', default=list, blank=True,
                                              help_text='[{"user_id": N, "role": "lead|support"}]')
    aggravating_factors    = models.TextField('Facteurs aggravants', blank=True)
    detection_delay_reason = models.TextField('Raison du délai de détection', blank=True)

    # Lien déploiement (souple, évite la dépendance circulaire avec orion_ops)
    probable_deployment_id = models.IntegerField('ID déploiement probable', null=True, blank=True)

    # Indicateurs de répétition
    auto_created           = models.BooleanField('Créé automatiquement', default=False)
    reopen_count           = models.PositiveSmallIntegerField('Nombre de réouvertures', default=0)

    # Impact SLO
    slo_impact             = models.JSONField('Impact SLO', default=dict, blank=True,
                                              help_text='{slo_slug: {before_pct, breach_minutes}}')

    root_cause        = models.TextField('Cause racine', blank=True)
    immediate_actions = models.TextField('Actions immédiates', blank=True)
    fix_applied       = models.TextField('Correctif appliqué', blank=True)
    consequences      = models.TextField('Conséquences', blank=True)
    prevention_plan   = models.TextField('Plan de prévention', blank=True)

    assigned_to  = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='assigned_incidents', verbose_name='Responsable')
    created_by   = models.ForeignKey(User, null=True, on_delete=models.SET_NULL,
                                     related_name='created_incidents', verbose_name='Créé par')
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Incident'
        verbose_name_plural = 'Incidents'
        ordering = ['-detected_at']

    def __str__(self):
        return f'[{self.get_severity_display()}] {self.title}'

    @property
    def duration(self):
        end = self.resolved_at or timezone.now()
        return end - self.started_at

    @property
    def severity_color(self):
        return {'minor': 'info', 'major': 'warning', 'critical': 'danger', 'emergency': 'danger'}.get(self.severity, 'secondary')


class IncidentTimeline(models.Model):
    """Événement dans la chronologie d'un incident."""
    EVENT_TYPES = [
        ('detected',   'Détection'),
        ('update',     'Mise à jour'),
        ('action',     'Action prise'),
        ('resolved',   'Résolution'),
        ('closed',     'Clôture'),
        ('comment',    'Commentaire'),
        ('escalated',  'Escalade'),
        ('reopened',   'Réouverture'),
    ]
    incident    = models.ForeignKey(SystemIncident, on_delete=models.CASCADE, related_name='timeline')
    event_type  = models.CharField('Type', max_length=20, choices=EVENT_TYPES)
    description = models.TextField('Description')
    author      = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    timestamp   = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']
        verbose_name = 'Chronologie incident'


class PostIncidentReport(models.Model):
    """Rapport post-incident pour les incidents majeurs/critiques."""
    incident                  = models.OneToOneField(SystemIncident, on_delete=models.CASCADE, related_name='post_report')
    what_happened             = models.TextField("Ce qui s'est passé")
    why_it_happened           = models.TextField('Pourquoi cela est arrivé')
    why_not_detected_earlier  = models.TextField('Pourquoi non détecté plus tôt')
    how_fixed                 = models.TextField('Comment corrigé')
    how_to_prevent            = models.TextField('Comment prévenir la répétition')

    # Champs enrichis (ajoutés via migration 0003)
    executive_summary         = models.TextField('Résumé exécutif', blank=True)
    user_impact_detail        = models.TextField('Impact concret sur les utilisateurs', blank=True)
    duration_minutes          = models.PositiveIntegerField('Durée (minutes)', null=True, blank=True,
                                                            help_text='Calculé automatiquement depuis started_at → resolved_at')
    corrective_actions        = models.JSONField('Actions correctives', default=list, blank=True,
                                                 help_text='[{action, owner, due_date, status}]')
    preventive_actions        = models.JSONField('Actions préventives', default=list, blank=True,
                                                 help_text='[{action, owner, due_date, status}]')
    validated_by              = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                                  related_name='validated_post_reports', verbose_name='Validé par')
    validated_at              = models.DateTimeField('Validé le', null=True, blank=True)

    created_by  = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Rapport post-incident'


# ──────────────────────────────────────────────────────────────────────────────
# 3. CAPTEURS ET MÉTRIQUES
# ──────────────────────────────────────────────────────────────────────────────

SENSOR_TYPE_CHOICES = [
    # Serveur
    ('cpu_usage',           'CPU (%)'),
    ('memory_usage',        'Mémoire (%)'),
    ('disk_usage',          'Disque utilisé (%)'),
    ('disk_free_gb',        'Disque libre (Go)'),
    ('open_files',          'Fichiers ouverts'),
    ('load_average',        'Charge système'),
    ('network_latency_ms',  'Latence réseau (ms)'),
    # Application
    ('app_available',       'Application disponible'),
    ('avg_response_ms',     'Temps réponse moyen (ms)'),
    ('max_response_ms',     'Temps réponse max (ms)'),
    ('requests_per_min',    'Requêtes/min'),
    ('error_rate_pct',      'Taux d\'erreur (%)'),
    ('active_sessions',     'Sessions actives'),
    ('slow_requests_1h',    'Requêtes lentes/h'),
    # Base de données
    ('db_available',        'DB disponible'),
    ('db_connections',      'Connexions DB'),
    ('db_slow_queries_1h',  'Requêtes lentes DB/h'),
    ('db_size_gb',          'Taille DB (Go)'),
    ('db_pending_migrations','Migrations en attente'),
    # Sauvegardes
    ('backup_age_hours',    'Âge dernière sauvegarde (h)'),
    ('backup_size_mb',      'Taille dernière sauvegarde (Mo)'),
    ('backup_test_age_days','Âge dernier test restauration (j)'),
    # Files Celery
    ('queue_pending',       'Tâches en attente'),
    ('queue_failed_1h',     'Tâches échouées/h'),
    ('queue_workers',       'Workers actifs'),
    # Sécurité
    ('failed_logins_1h',    'Connexions échouées/h'),
    ('locked_accounts',     'Comptes verrouillés'),
    ('open_errors',         'Erreurs ouvertes'),
    ('open_incidents',      'Incidents ouverts'),
]

SENSOR_STATUS_CHOICES = [
    ('ok',      'Sain'),
    ('warning', 'Attention'),
    ('critical','Critique'),
    ('error',   'Erreur collecte'),
    ('unknown', 'Inconnu'),
]


class SensorReading(models.Model):
    """Lecture instantanée d'un capteur technique (16.3)."""
    sensor_type = models.CharField('Capteur', max_length=60, choices=SENSOR_TYPE_CHOICES, db_index=True)
    value       = models.FloatField('Valeur', null=True)
    status      = models.CharField('Statut', max_length=20, choices=SENSOR_STATUS_CHOICES, default='unknown')
    metadata    = models.JSONField('Métadonnées', default=dict)
    collected_at = models.DateTimeField('Collecté à', auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Lecture capteur'
        ordering = ['-collected_at']
        indexes = [models.Index(fields=['sensor_type', '-collected_at'])]

    def __str__(self):
        return f'{self.sensor_type}={self.value} [{self.status}]'

    @property
    def status_color(self):
        return {'ok': 'success', 'warning': 'warning', 'critical': 'danger', 'error': 'secondary', 'unknown': 'secondary'}.get(self.status, 'secondary')


# ──────────────────────────────────────────────────────────────────────────────
# 4. SEUILS D'ALERTE
# ──────────────────────────────────────────────────────────────────────────────

class AlertThreshold(models.Model):
    """Seuil configurable par capteur (16.8)."""
    COMPARISON_CHOICES = [('gt', '>'), ('lt', '<'), ('gte', '>='), ('lte', '<=')]

    sensor_type          = models.CharField('Capteur', max_length=60, unique=True)
    warning_threshold    = models.FloatField('Seuil attention', null=True, blank=True)
    critical_threshold   = models.FloatField('Seuil critique', null=True, blank=True)
    comparison           = models.CharField('Comparaison', max_length=5, choices=COMPARISON_CHOICES, default='gt')
    enabled              = models.BooleanField('Actif', default=True)
    silence_until        = models.DateTimeField('Silencieux jusqu\'à', null=True, blank=True)
    notification_emails  = models.JSONField('Emails notification', default=list)
    escalation_after_min = models.PositiveIntegerField('Escalade après (min)', default=30)
    created_by  = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Seuil d\'alerte'
        ordering = ['sensor_type']

    def __str__(self):
        return f'{self.sensor_type} {self.comparison} W:{self.warning_threshold} C:{self.critical_threshold}'

    def compute_status(self, value):
        if value is None or not self.enabled:
            return 'unknown'
        silenced = self.silence_until and self.silence_until > timezone.now()

        def exceeds(threshold):
            if threshold is None:
                return False
            op = self.comparison
            return (
                (op == 'gt'  and value > threshold) or
                (op == 'lt'  and value < threshold) or
                (op == 'gte' and value >= threshold) or
                (op == 'lte' and value <= threshold)
            )

        if exceeds(self.critical_threshold):
            return 'warning' if silenced else 'critical'
        if exceeds(self.warning_threshold):
            return 'warning'
        return 'ok'


# ──────────────────────────────────────────────────────────────────────────────
# 5. REGISTRE DES RISQUES
# ──────────────────────────────────────────────────────────────────────────────

class RiskRegister(models.Model):
    """Registre des risques (16.7)."""

    CATEGORY_CHOICES = [
        ('security',             'Sécurité'),
        ('privacy',              'Confidentialité'),
        ('availability',         'Disponibilité'),
        ('data_integrity',       'Intégrité des données'),
        ('performance',          'Performance'),
        ('compliance',           'Conformité'),
        ('human_error',          'Erreur humaine'),
        ('business_error',       'Erreur métier'),
        ('external_dependency',  'Dépendance externe'),
        ('backup',               'Sauvegarde'),
        ('infrastructure',       'Infrastructure'),
        ('health',               'Santé'),
        ('finance',              'Finance'),
        ('business_continuity',  'Continuité d\'activité'),
    ]
    PROBABILITY_CHOICES = [
        ('1', 'Rare'),
        ('2', 'Peu probable'),
        ('3', 'Possible'),
        ('4', 'Probable'),
        ('5', 'Quasi-certain'),
    ]
    IMPACT_CHOICES = [
        ('1', 'Négligeable'),
        ('2', 'Mineur'),
        ('3', 'Modéré'),
        ('4', 'Majeur'),
        ('5', 'Catastrophique'),
    ]
    RISK_STATUS_CHOICES = [
        ('identified', 'Identifié'),
        ('assessed',   'Évalué'),
        ('treating',   'Traitement en cours'),
        ('monitored',  'Surveillé'),
        ('accepted',   'Accepté'),
        ('closed',     'Clôturé'),
    ]
    ORIGIN_CHOICES = [
        ('audit',     'Audit'),
        ('incident',  'Incident'),
        ('manual',    'Manuel'),
        ('sensor',    'Capteur automatique'),
        ('security',  'Alerte sécurité'),
    ]

    uid         = models.CharField('Identifiant', max_length=20, unique=True)
    title       = models.CharField('Titre', max_length=300)
    description = models.TextField('Description')
    category    = models.CharField('Catégorie', max_length=50, choices=CATEGORY_CHOICES, db_index=True)
    origin      = models.CharField('Origine', max_length=20, choices=ORIGIN_CHOICES, default='manual')

    affected_module = models.CharField('Module concerné', max_length=100, blank=True)
    affected_data   = models.TextField('Données concernées', blank=True)

    probability               = models.CharField('Probabilité', max_length=1, choices=PROBABILITY_CHOICES)
    impact                    = models.CharField('Impact', max_length=1, choices=IMPACT_CHOICES)
    probability_justification = models.TextField('Justification probabilité', blank=True)
    impact_justification      = models.TextField('Justification impact', blank=True)

    detected_at = models.DateField('Détecté le', default=timezone.now)
    owner       = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='owned_risks', verbose_name='Propriétaire')

    existing_measures   = models.TextField('Mesures existantes', blank=True)
    corrective_actions  = models.TextField('Actions correctives', blank=True)
    target_date         = models.DateField('Date cible', null=True, blank=True)

    status         = models.CharField('État', max_length=20, choices=RISK_STATUS_CHOICES, default='identified', db_index=True)
    residual_risk  = models.CharField('Risque résiduel', max_length=1, choices=IMPACT_CHOICES, blank=True)
    last_review    = models.DateField('Dernière réévaluation', null=True, blank=True)

    linked_incident = models.ForeignKey(SystemIncident, null=True, blank=True, on_delete=models.SET_NULL,
                                         related_name='risks', verbose_name='Incident lié')

    created_by  = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name='created_risks')
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Risque'
        verbose_name_plural = 'Registre des risques'
        ordering = ['-updated_at']
        indexes = [models.Index(fields=['category', 'status'])]

    def __str__(self):
        return f'{self.uid} — {self.title}'

    @property
    def criticality_score(self):
        try:
            return int(self.probability) * int(self.impact)
        except (ValueError, TypeError):
            return 0

    @property
    def criticality_level(self):
        s = self.criticality_score
        if s <= 3:  return 'low'
        if s <= 8:  return 'moderate'
        if s <= 12: return 'important'
        if s <= 16: return 'high'
        return 'critical'

    @property
    def criticality_label(self):
        return {'low': 'Faible', 'moderate': 'Modéré', 'important': 'Important',
                'high': 'Élevé', 'critical': 'Critique'}.get(self.criticality_level, '?')

    @property
    def criticality_color(self):
        return {'low': 'success', 'moderate': 'info', 'important': 'warning',
                'high': 'warning', 'critical': 'danger'}.get(self.criticality_level, 'secondary')

    def save(self, *args, **kwargs):
        if not self.uid:
            count = RiskRegister.objects.count() + 1
            self.uid = f'RSK-{count:04d}'
        super().save(*args, **kwargs)


# ──────────────────────────────────────────────────────────────────────────────
# 6. PERMISSIONS GRANULAIRES
# ──────────────────────────────────────────────────────────────────────────────

class HealthPermission(models.Model):
    """Permissions granulaires pour la section Santé du système (16.12)."""
    user                 = models.OneToOneField(User, on_delete=models.CASCADE, related_name='health_permission')
    can_view_health      = models.BooleanField('Consulter la santé', default=False)
    can_view_errors      = models.BooleanField('Consulter les erreurs', default=False)
    can_view_technical   = models.BooleanField('Consulter données techniques', default=False)
    can_view_security    = models.BooleanField('Consulter alertes sécurité', default=False)
    can_view_risks       = models.BooleanField('Consulter les risques', default=False)
    can_manage_incidents = models.BooleanField('Gérer les incidents', default=False)
    can_edit_thresholds  = models.BooleanField('Modifier les seuils', default=False)
    can_close_alerts     = models.BooleanField('Fermer les alertes', default=False)
    can_export_reports   = models.BooleanField('Exporter les rapports', default=False)
    can_view_sensitive   = models.BooleanField('Données sensibles', default=False)
    can_administrate     = models.BooleanField('Administrer la supervision', default=False)
    updated_by  = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='+')
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Permission santé système'
        verbose_name_plural = 'Permissions santé système'

    def __str__(self):
        return f'Permissions santé — {self.user.username}'


# ──────────────────────────────────────────────────────────────────────────────
# 7. AUDIT DE LA SECTION SANTÉ
# ──────────────────────────────────────────────────────────────────────────────

# ──────────────────────────────────────────────────────────────────────────────
# 8. SNAPSHOTS DE SANTÉ — historique des scores calculés
# ──────────────────────────────────────────────────────────────────────────────

class HealthSnapshot(models.Model):
    """Score de santé calculé à chaque cycle de collecte (toutes les 5 min)."""
    global_score    = models.PositiveSmallIntegerField('Score global')
    global_status   = models.CharField('Statut', max_length=20, choices=HEALTH_STATUSES)
    server_score    = models.PositiveSmallIntegerField('Serveur', default=0)
    app_score       = models.PositiveSmallIntegerField('Application', default=0)
    database_score  = models.PositiveSmallIntegerField('Base de données', default=0)
    backups_score   = models.PositiveSmallIntegerField('Sauvegardes', default=0)
    security_score  = models.PositiveSmallIntegerField('Sécurité', default=0)
    celery_score    = models.PositiveSmallIntegerField('Celery', default=0)
    critical_sensors = models.JSONField('Capteurs critiques', default=list)
    warning_sensors  = models.JSONField('Capteurs en alerte', default=list)
    collected_at    = models.DateTimeField('Enregistré à', auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Snapshot de santé'
        verbose_name_plural = 'Historique de santé'
        ordering = ['-collected_at']
        indexes = [models.Index(fields=['-collected_at'])]

    def __str__(self):
        return f'{self.global_score}/100 [{self.global_status}] — {self.collected_at:%d/%m %H:%M}'

    @property
    def status_color(self):
        return {
            'healthy': 'success', 'degraded': 'warning',
            'unstable': 'danger', 'critical': 'danger',
        }.get(self.global_status, 'secondary')


class HealthAuditLog(models.Model):
    """Journal d'audit des accès et actions dans la section Santé (16.13)."""
    ACTION_CHOICES = [
        ('view_dashboard',  'Consultation tableau de bord'),
        ('view_errors',     'Consultation erreurs'),
        ('view_incident',   'Consultation incident'),
        ('view_risk',       'Consultation risque'),
        ('export',          'Export'),
        ('edit_threshold',  'Modification seuil'),
        ('close_alert',     'Fermeture alerte'),
        ('delete',          'Archivage'),
        ('status_change',   'Changement statut'),
        ('risk_edit',       'Modification risque'),
        ('sensitive_view',  'Accès données sensibles'),
    ]
    user       = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    action     = models.CharField('Action', max_length=40, choices=ACTION_CHOICES)
    target_type = models.CharField('Type cible', max_length=50, blank=True)
    target_id   = models.CharField('ID cible', max_length=50, blank=True)
    description = models.TextField('Description', blank=True)
    ip_address  = models.GenericIPAddressField('IP', null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Audit santé système'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'action'])]

    def __str__(self):
        return f'{self.get_action_display()} — {self.user} — {self.created_at:%d/%m %H:%M}'
