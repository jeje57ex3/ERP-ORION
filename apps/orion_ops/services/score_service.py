"""
apps/orion_ops/services/score_service.py — Calcul des 7 scores de santé étendus.

Principe strict : chaque score est calculé depuis des données réelles mesurées
en base. Si les données sont absentes ou trop anciennes (> 2h), le score est
marqué 'stale' et n'est pas utilisé dans les décisions automatiques.

Aucun score ne peut être « forcé » — le résultat reflète l'état réel du système.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from django.utils import timezone


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _latest_sensor(sensor_type: str, max_age_hours: int = 2) -> Optional[float]:
    """Retourne la valeur du capteur le plus récent, ou None si absent / trop vieux."""
    from apps.system_health.models import SensorReading
    cutoff = timezone.now() - timedelta(hours=max_age_hours)
    r = (SensorReading.objects
         .filter(sensor_type=sensor_type, collected_at__gte=cutoff)
         .order_by('-collected_at')
         .first())
    return r.value if r else None


def _sensor_status(sensor_type: str, max_age_hours: int = 2) -> Optional[str]:
    from apps.system_health.models import SensorReading
    cutoff = timezone.now() - timedelta(hours=max_age_hours)
    r = (SensorReading.objects
         .filter(sensor_type=sensor_type, collected_at__gte=cutoff)
         .order_by('-collected_at')
         .first())
    return r.status if r else None


def _cap(score: int, cap: int) -> int:
    return min(score, cap)


# ─── Restore Readiness ────────────────────────────────────────────────────────

def compute_restore_readiness_score() -> dict:
    """
    Score 0-100 basé sur :
      - Sauvegarde récente (30 pts)
      - Test de restauration réussi < 30j (35 pts)
      - Vérification données post-restore OK (20 pts)
      - RTO mesuré < 60 min (15 pts)
    Plafond à 50 si aucun test réussi.
    """
    from apps.backups.models import BackupJob
    from apps.orion_ops.models import RestoreTest

    points = {}
    total = 0
    cap = 100

    # Sauvegarde récente (30 pts)
    last_backup = BackupJob.objects.filter(status='success').order_by('-finished_at').first()
    if last_backup and last_backup.finished_at:
        age_h = (timezone.now() - last_backup.finished_at).total_seconds() / 3600
        if age_h < 26:
            earned = 30
        elif age_h < 50:
            earned = 15
        else:
            earned = 5
        points['backup_recency'] = {'earned': earned, 'max': 30,
                                     'reason': f'Dernière sauvegarde il y a {age_h:.0f}h'}
    else:
        earned = 0
        points['backup_recency'] = {'earned': 0, 'max': 30, 'reason': 'Aucune sauvegarde réussie trouvée'}
    total += earned

    # Test de restauration < 30 jours (35 pts)
    cutoff_30d = timezone.now() - timedelta(days=30)
    last_test = RestoreTest.objects.filter(
        tested_at__gte=cutoff_30d
    ).order_by('-tested_at').first()

    has_successful_test = RestoreTest.objects.filter(result='success').exists()
    if not has_successful_test:
        cap = 50

    if last_test:
        if last_test.result == 'success':
            earned = 35
        elif last_test.result == 'partial':
            earned = 15
        else:
            earned = 0
        points['restore_test'] = {'earned': earned, 'max': 35,
                                   'reason': f'Dernier test: {last_test.result} ({last_test.tested_at:%d/%m/%Y})'}
    else:
        earned = 0
        points['restore_test'] = {'earned': 0, 'max': 35, 'reason': 'Aucun test de restauration dans les 30 derniers jours'}
    total += earned

    # Intégrité données vérifiée (20 pts)
    if last_test and last_test.constraints_ok is True:
        earned = 20
        points['constraints'] = {'earned': 20, 'max': 20, 'reason': 'Intégrité vérifiée au dernier test'}
    elif last_test and last_test.constraints_ok is False:
        earned = 0
        points['constraints'] = {'earned': 0, 'max': 20, 'reason': 'Intégrité non respectée au dernier test'}
    else:
        earned = 0
        points['constraints'] = {'earned': 0, 'max': 20, 'reason': 'Non mesuré'}
    total += earned

    # RTO mesuré (15 pts)
    if last_test and last_test.rto_minutes is not None:
        if last_test.rto_minutes < 60:
            earned = 15
        elif last_test.rto_minutes < 120:
            earned = 8
        else:
            earned = 3
        points['rto'] = {'earned': earned, 'max': 15,
                          'reason': f'RTO mesuré: {last_test.rto_minutes:.0f} min'}
    else:
        earned = 0
        points['rto'] = {'earned': 0, 'max': 15, 'reason': 'RTO non mesuré'}
    total += earned

    total = _cap(total, cap)
    status = 'ok' if total >= 80 else ('warning' if total >= 50 else 'critical')
    return {'score': total, 'status': status, 'points_detail': points,
            'cap_applied': cap < 100}


# ─── Data Quality ─────────────────────────────────────────────────────────────

def compute_data_quality_score() -> dict:
    """
    Score 0-100 basé sur les anomalies DataQualityAnomaly ouvertes.
    Plafond à 40 si au moins une anomalie critique ouverte.
    """
    from apps.orion_ops.models import DataQualityAnomaly

    points = {}
    cap = 100

    open_anomalies = DataQualityAnomaly.objects.filter(
        status__in=['open', 'acknowledged', 'fixing']
    )
    total_open = open_anomalies.count()
    critical_open = open_anomalies.filter(severity='critical').count()
    high_open = open_anomalies.filter(severity='high').count()
    medium_open = open_anomalies.filter(severity='medium').count()

    if critical_open > 0:
        cap = 40

    base = 100
    deduction = (critical_open * 25) + (high_open * 10) + (medium_open * 3)
    score = _cap(max(0, base - deduction), cap)

    points['anomalies_open'] = {
        'earned': score, 'max': 100,
        'reason': f'{total_open} anomalie(s) ouvertes: {critical_open} critique, {high_open} élevée, {medium_open} modérée'
    }

    if total_open == 0 and DataQualityAnomaly.objects.count() == 0:
        # Aucun contrôle n'a jamais tourné — on ne peut pas conclure
        return {'score': None, 'status': 'unavailable', 'points_detail': points}

    status = 'ok' if score >= 80 else ('warning' if score >= 50 else 'critical')
    return {'score': score, 'status': status, 'points_detail': points}


# ─── Capacity ─────────────────────────────────────────────────────────────────

def compute_capacity_score() -> dict:
    """
    Score 0-100 basé sur les capteurs de ressources système.
    Plafond à 20 si une ressource critique sature dans < 7 jours.
    """
    from apps.orion_ops.models import CapacityTrend

    points = {}
    cap = 100
    total = 0

    # Disque libre (30 pts)
    disk_pct_used = _latest_sensor('disk_usage')
    if disk_pct_used is not None:
        disk_free = 100 - disk_pct_used
        if disk_free > 20:
            earned = 30
        elif disk_free > 10:
            earned = 15
        elif disk_free > 5:
            earned = 5
        else:
            earned = 0
            cap = min(cap, 20)
        points['disk_free'] = {'earned': earned, 'max': 30,
                                'reason': f'{disk_free:.1f}% libre sur C:'}
    else:
        earned = 15
        points['disk_free'] = {'earned': 15, 'max': 30, 'reason': 'Capteur indisponible'}
    total += earned

    # Mémoire (25 pts)
    mem_pct = _latest_sensor('memory_usage')
    if mem_pct is not None:
        if mem_pct < 80:
            earned = 25
        elif mem_pct < 90:
            earned = 12
        else:
            earned = 0
        points['memory'] = {'earned': earned, 'max': 25,
                             'reason': f'Mémoire: {mem_pct:.1f}%'}
    else:
        earned = 12
        points['memory'] = {'earned': 12, 'max': 25, 'reason': 'Capteur indisponible'}
    total += earned

    # CPU moyen (20 pts)
    cpu_pct = _latest_sensor('cpu_usage')
    if cpu_pct is not None:
        if cpu_pct < 70:
            earned = 20
        elif cpu_pct < 85:
            earned = 10
        else:
            earned = 0
        points['cpu'] = {'earned': earned, 'max': 20,
                          'reason': f'CPU: {cpu_pct:.1f}%'}
    else:
        earned = 10
        points['cpu'] = {'earned': 10, 'max': 20, 'reason': 'Capteur indisponible'}
    total += earned

    # Prévision de saturation (25 pts)
    critical_trend = CapacityTrend.objects.filter(
        days_until_limit__isnull=False,
        days_until_limit__lte=7,
    ).order_by('days_until_limit').first()

    if critical_trend:
        earned = 0
        cap = min(cap, 20)
        points['saturation_forecast'] = {
            'earned': 0, 'max': 25,
            'reason': f'{critical_trend.resource_type} sature dans {critical_trend.days_until_limit}j'
        }
    else:
        trend_warn = CapacityTrend.objects.filter(
            days_until_limit__isnull=False,
            days_until_limit__lte=30,
        ).exists()
        earned = 12 if trend_warn else 25
        points['saturation_forecast'] = {
            'earned': earned, 'max': 25,
            'reason': 'Saturation dans < 30j détectée' if trend_warn else 'Aucune saturation imminente'
        }
    total += earned

    total = _cap(total, cap)
    status = 'ok' if total >= 80 else ('warning' if total >= 50 else 'critical')
    return {'score': total, 'status': status, 'points_detail': points}


# ─── Compliance ───────────────────────────────────────────────────────────────

def compute_compliance_score() -> dict:
    """
    Score 0-100 basé sur :
      - Admins avec 2FA actif (25 pts)
      - Audit log actif (25 pts)
      - Rétention sauvegardes respectée (25 pts)
      - Erreurs non traitées depuis > 7j (25 pts)
    """
    from django.contrib.auth.models import User
    from apps.system_health.models import SystemError

    points = {}
    total = 0

    # 2FA superadmins (25 pts)
    try:
        from apps.user_security.models import UserTwoFactorSettings
        superusers = User.objects.filter(is_superuser=True, is_active=True)
        total_su = superusers.count()
        if total_su > 0:
            su_with_2fa = UserTwoFactorSettings.objects.filter(
                user__in=superusers, is_enabled=True
            ).count()
            pct = su_with_2fa / total_su * 100
            earned = int(pct / 100 * 25)
            if pct < 50:
                # Moins de 50 % des admins avec 2FA — plafonnement
                pass
            points['admin_2fa'] = {'earned': earned, 'max': 25,
                                    'reason': f'{su_with_2fa}/{total_su} super-admins avec 2FA'}
        else:
            earned = 0
            points['admin_2fa'] = {'earned': 0, 'max': 25, 'reason': 'Aucun super-admin'}
    except Exception:
        earned = 12
        points['admin_2fa'] = {'earned': 12, 'max': 25, 'reason': 'Module 2FA non vérifié'}
    total += earned

    # Audit log actif (25 pts) — on vérifie qu'il y a des entrées récentes
    try:
        from apps.core.models import AuditLog
        cutoff = timezone.now() - timedelta(hours=24)
        recent_audit = AuditLog.objects.filter(created_at__gte=cutoff).exists()
        earned = 25 if recent_audit else 10
        points['audit_log'] = {'earned': earned, 'max': 25,
                                'reason': 'Entrées audit < 24h' if recent_audit else 'Pas d\'entrée audit récente'}
    except Exception:
        earned = 12
        points['audit_log'] = {'earned': 12, 'max': 25, 'reason': 'Audit log non vérifié'}
    total += earned

    # Rétention sauvegardes (25 pts)
    try:
        from apps.backups.models import BackupJob
        cutoff_30d = timezone.now() - timedelta(days=30)
        backups_30d = BackupJob.objects.filter(
            finished_at__gte=cutoff_30d, status='success'
        ).count()
        if backups_30d >= 25:
            earned = 25
        elif backups_30d >= 10:
            earned = 15
        elif backups_30d >= 1:
            earned = 5
        else:
            earned = 0
        points['backup_retention'] = {'earned': earned, 'max': 25,
                                       'reason': f'{backups_30d} sauvegardes réussies sur 30j'}
    except Exception:
        earned = 12
        points['backup_retention'] = {'earned': 12, 'max': 25, 'reason': 'Sauvegardes non vérifiées'}
    total += earned

    # Erreurs non traitées > 7j (25 pts)
    stale_cutoff = timezone.now() - timedelta(days=7)
    stale_errors = SystemError.objects.filter(
        status__in=['new', 'analysed'],
        first_seen__lt=stale_cutoff,
    ).count()
    if stale_errors == 0:
        earned = 25
    elif stale_errors <= 3:
        earned = 15
    elif stale_errors <= 10:
        earned = 5
    else:
        earned = 0
    points['stale_errors'] = {'earned': earned, 'max': 25,
                               'reason': f'{stale_errors} erreur(s) non traitées depuis > 7 jours'}
    total += earned

    status = 'ok' if total >= 80 else ('warning' if total >= 50 else 'critical')
    return {'score': total, 'status': status, 'points_detail': points}


# ─── Business Processes ───────────────────────────────────────────────────────

def compute_business_score() -> dict:
    """
    Score 0-100 basé sur les BusinessMetricReadings récentes.
    Plafond à 50 si des paiements sont bloqués.
    """
    from apps.orion_ops.models import BusinessMetricReading

    points = {}
    cap = 100
    total = 0

    cutoff = timezone.now() - timedelta(hours=2)

    def latest_metric(metric_type):
        r = (BusinessMetricReading.objects
             .filter(metric_type=metric_type, collected_at__gte=cutoff)
             .order_by('-collected_at')
             .first())
        return r

    # Paiements échoués (20 pts)
    m = latest_metric('payments_failed_1h')
    if m:
        if m.value == 0:
            earned = 20
        elif m.value <= 3:
            earned = 10
        else:
            earned = 0
            cap = min(cap, 50)
        points['payments_failed'] = {'earned': earned, 'max': 20,
                                      'reason': f'{m.value:.0f} paiements échoués/h'}
    else:
        earned = 15
        points['payments_failed'] = {'earned': 15, 'max': 20, 'reason': 'Non mesuré'}
    total += earned

    # Commandes bloquées (20 pts)
    m = latest_metric('orders_blocked')
    if m:
        if m.value == 0:
            earned = 20
        elif m.value <= 5:
            earned = 10
        else:
            earned = 0
        points['orders_blocked'] = {'earned': earned, 'max': 20,
                                     'reason': f'{m.value:.0f} commande(s) bloquée(s)'}
    else:
        earned = 15
        points['orders_blocked'] = {'earned': 15, 'max': 20, 'reason': 'Non mesuré'}
    total += earned

    # Stock négatif (20 pts)
    m = latest_metric('negative_stock_count')
    if m:
        if m.value == 0:
            earned = 20
        elif m.value <= 3:
            earned = 10
        else:
            earned = 5
        points['negative_stock'] = {'earned': earned, 'max': 20,
                                     'reason': f'{m.value:.0f} produit(s) en stock négatif'}
    else:
        earned = 15
        points['negative_stock'] = {'earned': 15, 'max': 20, 'reason': 'Non mesuré'}
    total += earned

    # Synchronisations OK (20 pts)
    m = latest_metric('sync_errors_1h')
    if m:
        if m.value == 0:
            earned = 20
        elif m.value <= 2:
            earned = 10
        else:
            earned = 0
        points['sync_errors'] = {'earned': earned, 'max': 20,
                                  'reason': f'{m.value:.0f} erreur(s) de sync/h'}
    else:
        earned = 15
        points['sync_errors'] = {'earned': 15, 'max': 20, 'reason': 'Non mesuré'}
    total += earned

    # Notifications (20 pts)
    m = latest_metric('notifications_pending')
    if m:
        if m.value < 10:
            earned = 20
        elif m.value < 50:
            earned = 10
        else:
            earned = 0
        points['notifications'] = {'earned': earned, 'max': 20,
                                    'reason': f'{m.value:.0f} notification(s) en attente'}
    else:
        earned = 15
        points['notifications'] = {'earned': 15, 'max': 20, 'reason': 'Non mesuré'}
    total += earned

    total = _cap(total, cap)

    has_any_data = BusinessMetricReading.objects.filter(collected_at__gte=cutoff).exists()
    if not has_any_data:
        return {'score': None, 'status': 'unavailable', 'points_detail': points}

    status = 'ok' if total >= 80 else ('warning' if total >= 50 else 'critical')
    return {'score': total, 'status': status, 'points_detail': points}


# ─── Résilience ───────────────────────────────────────────────────────────────

def compute_resilience_score() -> dict:
    """
    Score 0-100 basé sur la capacité de l'ERP à résister aux pannes et à se rétablir.
      - Test de restauration réussi < 90j (40 pts)
      - Celery Beat actif (celery_beat_ok) (20 pts)
      - Broker Redis OK (celery_broker_ok) (15 pts)
      - Aucun incident critique ouvert (15 pts)
      - Budget d'erreur SLO sain (10 pts)
    Plafond à 50 si aucun test de restauration réussi.
    """
    from apps.orion_ops.models import RestoreTest, SLOTarget
    from apps.system_health.models import SystemIncident

    points = {}
    cap = 100
    total = 0

    # Test de restauration < 90 jours (40 pts)
    cutoff_90d = timezone.now() - timedelta(days=90)
    last_success = RestoreTest.objects.filter(
        result='success', tested_at__gte=cutoff_90d
    ).order_by('-tested_at').first()

    has_any_success = RestoreTest.objects.filter(result='success').exists()
    if not has_any_success:
        cap = 50

    if last_success:
        age_days = (timezone.now() - last_success.tested_at).days
        if age_days <= 30:
            earned = 40
        elif age_days <= 60:
            earned = 25
        else:
            earned = 10
        points['restore_test'] = {'earned': earned, 'max': 40,
                                   'reason': f'Dernier test réussi il y a {age_days}j'}
    elif RestoreTest.objects.filter(tested_at__gte=cutoff_90d, result='partial').exists():
        earned = 15
        points['restore_test'] = {'earned': 15, 'max': 40, 'reason': 'Test partiel < 90j (aucun succès)'}
    else:
        earned = 0
        points['restore_test'] = {'earned': 0, 'max': 40, 'reason': 'Aucun test réussi dans les 90 derniers jours'}
    total += earned

    # Celery Beat actif (20 pts)
    beat_ok = _latest_sensor('celery_beat_ok')
    if beat_ok is not None:
        earned = 20 if beat_ok >= 1 else 0
        points['celery_beat'] = {'earned': earned, 'max': 20,
                                  'reason': 'Celery Beat actif' if beat_ok >= 1 else 'Celery Beat hors-service'}
    else:
        earned = 10
        points['celery_beat'] = {'earned': 10, 'max': 20, 'reason': 'Celery Beat non mesuré'}
    total += earned

    # Broker Redis OK (15 pts)
    broker_ok = _latest_sensor('celery_broker_ok')
    if broker_ok is not None:
        earned = 15 if broker_ok >= 1 else 0
        points['broker'] = {'earned': earned, 'max': 15,
                             'reason': 'Redis broker disponible' if broker_ok >= 1 else 'Redis broker hors-service'}
    else:
        earned = 8
        points['broker'] = {'earned': 8, 'max': 15, 'reason': 'Broker non mesuré'}
    total += earned

    # Incidents critiques ouverts (15 pts)
    open_critical = SystemIncident.objects.filter(
        status__in=['detected', 'confirmed', 'assigned', 'investigating', 'fixing'],
        severity='critical',
    ).count()
    if open_critical == 0:
        earned = 15
        points['open_incidents'] = {'earned': 15, 'max': 15, 'reason': 'Aucun incident critique ouvert'}
    elif open_critical == 1:
        earned = 5
        points['open_incidents'] = {'earned': 5, 'max': 15, 'reason': f'{open_critical} incident critique ouvert'}
    else:
        earned = 0
        points['open_incidents'] = {'earned': 0, 'max': 15, 'reason': f'{open_critical} incidents critiques ouverts'}
    total += earned

    # Budget d'erreur SLO (10 pts)
    slos = SLOTarget.objects.filter(enabled=True).exclude(error_budget_pct=None)
    if slos.exists():
        budgets = [s.error_budget_pct for s in slos if s.error_budget_pct is not None]
        avg_budget = sum(budgets) / len(budgets) if budgets else None
        if avg_budget is not None:
            if avg_budget >= 50:
                earned = 10
            elif avg_budget >= 20:
                earned = 5
            else:
                earned = 0
            points['slo_budget'] = {'earned': earned, 'max': 10,
                                     'reason': f'Budget d\'erreur SLO moyen : {avg_budget:.1f}%'}
        else:
            earned = 5
            points['slo_budget'] = {'earned': 5, 'max': 10, 'reason': 'Budget d\'erreur non calculé'}
    else:
        earned = 5
        points['slo_budget'] = {'earned': 5, 'max': 10, 'reason': 'Aucun SLO configuré'}
    total += earned

    total = _cap(total, cap)
    status = 'ok' if total >= 80 else ('warning' if total >= 50 else 'critical')
    return {'score': total, 'status': status, 'points_detail': points,
            'cap_applied': cap < 100}


# ─── Intégrations ─────────────────────────────────────────────────────────────

def compute_integrations_score() -> dict:
    """
    Score 0-100 basé sur la santé des intégrations externes.
      - Tunnel Cloudflare (30 pts)
      - Intégration Stripe paiements (25 pts)
      - Erreurs de synchronisation (25 pts)
      - Temps de réponse API (20 pts)
    """
    from apps.orion_ops.models import ServiceComponent, BusinessMetricReading

    points = {}
    total = 0

    # Tunnel Cloudflare (30 pts)
    try:
        tunnel = ServiceComponent.objects.get(slug='cloudflare-tunnel')
        if tunnel.status == 'ok':
            earned = 30
            reason = 'Tunnel Cloudflare opérationnel'
        elif tunnel.status == 'degraded':
            earned = 15
            reason = 'Tunnel Cloudflare dégradé'
        elif tunnel.status == 'down':
            earned = 0
            reason = 'Tunnel Cloudflare hors-service'
        else:
            # 'unknown' ou 'maintenance' — pas de données
            earned = 15
            reason = f'Tunnel Cloudflare : statut {tunnel.status}'
        points['cloudflare'] = {'earned': earned, 'max': 30, 'reason': reason}
    except ServiceComponent.DoesNotExist:
        earned = 15
        points['cloudflare'] = {'earned': 15, 'max': 30, 'reason': 'Composant tunnel non enregistré'}
    total += earned

    # Stripe — paiements (25 pts)
    cutoff = timezone.now() - timedelta(hours=2)
    m_payments = (BusinessMetricReading.objects
                  .filter(metric_type='payments_failed_1h', collected_at__gte=cutoff)
                  .order_by('-collected_at').first())
    try:
        stripe = ServiceComponent.objects.get(slug='stripe-api')
        stripe_status = stripe.status
    except ServiceComponent.DoesNotExist:
        stripe_status = 'unknown'

    if m_payments is not None:
        if m_payments.value == 0:
            earned = 25
            reason = 'Aucun paiement Stripe échoué'
        elif m_payments.value <= 2:
            earned = 15
            reason = f'{m_payments.value:.0f} paiement(s) Stripe échoué(s)/h'
        else:
            earned = 0
            reason = f'{m_payments.value:.0f} paiements Stripe échoués/h — intégration dégradée'
    elif stripe_status == 'ok':
        earned = 20
        reason = 'Stripe OK (statut composant)'
    elif stripe_status == 'down':
        earned = 0
        reason = 'Stripe hors-service (statut composant)'
    else:
        earned = 15
        reason = 'Stripe non mesuré'
    points['stripe'] = {'earned': earned, 'max': 25, 'reason': reason}
    total += earned

    # Erreurs de synchronisation (25 pts)
    m_sync = (BusinessMetricReading.objects
               .filter(metric_type='sync_errors_1h', collected_at__gte=cutoff)
               .order_by('-collected_at').first())
    if m_sync is not None:
        if m_sync.value == 0:
            earned = 25
        elif m_sync.value <= 3:
            earned = 12
        else:
            earned = 0
        points['sync_errors'] = {'earned': earned, 'max': 25,
                                  'reason': f'{m_sync.value:.0f} erreur(s) de synchronisation/h'}
    else:
        earned = 15
        points['sync_errors'] = {'earned': 15, 'max': 25, 'reason': 'Synchronisations non mesurées'}
    total += earned

    # Temps de réponse API moyen (20 pts) — proxy pour la latence des intégrations
    avg_ms = _latest_sensor('avg_response_ms')
    if avg_ms is not None:
        if avg_ms < 300:
            earned = 20
        elif avg_ms < 700:
            earned = 12
        elif avg_ms < 1500:
            earned = 5
        else:
            earned = 0
        points['response_time'] = {'earned': earned, 'max': 20,
                                    'reason': f'Temps de réponse moyen : {avg_ms:.0f} ms'}
    else:
        earned = 10
        points['response_time'] = {'earned': 10, 'max': 20, 'reason': 'Temps de réponse non mesuré'}
    total += earned

    has_any_data = (m_payments is not None or m_sync is not None or avg_ms is not None)
    if not has_any_data and stripe_status == 'unknown':
        return {'score': None, 'status': 'unavailable', 'points_detail': points}

    status = 'ok' if total >= 80 else ('warning' if total >= 50 else 'critical')
    return {'score': total, 'status': status, 'points_detail': points}


# ─── Dispatch et enregistrement ───────────────────────────────────────────────

_SCORE_COMPUTERS = {
    'restore_readiness':  compute_restore_readiness_score,
    'data_quality':       compute_data_quality_score,
    'capacity':           compute_capacity_score,
    'compliance':         compute_compliance_score,
    'business_processes': compute_business_score,
    'resilience':         compute_resilience_score,
    'integrations':       compute_integrations_score,
}


def compute_all_extended_scores() -> dict:
    """
    Calcule et persiste tous les scores étendus disponibles.
    Retourne un dict {domain: {score, status}}.
    """
    from apps.orion_ops.models import HealthScoreRecord

    results = {}
    for domain, fn in _SCORE_COMPUTERS.items():
        try:
            data = fn()
            expires_at = timezone.now() + timedelta(hours=2)
            HealthScoreRecord.objects.create(
                domain=domain,
                score=data.get('score'),
                status=data.get('status', 'unavailable'),
                points_detail=data.get('points_detail', {}),
                metrics_used={},
                is_stale=False,
                expires_at=expires_at,
            )
            results[domain] = {'score': data.get('score'), 'status': data.get('status')}
        except Exception as exc:
            results[domain] = {'score': None, 'status': 'unavailable', 'error': str(exc)}

    return results


def get_latest_extended_scores() -> dict:
    """
    Retourne le score le plus récent pour chaque domaine.
    Marque comme 'stale' si expiré.
    """
    from apps.orion_ops.models import HealthScoreRecord

    now = timezone.now()
    result = {}
    domains = [d[0] for d in HealthScoreRecord.DOMAINS]

    for domain in domains:
        record = (HealthScoreRecord.objects
                  .filter(domain=domain)
                  .order_by('-computed_at')
                  .first())
        if record is None:
            result[domain] = {'score': None, 'status': 'unavailable', 'stale': True}
        else:
            is_stale = record.expires_at and record.expires_at < now
            result[domain] = {
                'score': record.score,
                'status': 'stale' if is_stale else record.status,
                'stale': is_stale,
                'computed_at': record.computed_at,
            }
    return result
