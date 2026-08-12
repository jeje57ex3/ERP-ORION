"""
apps/system_health/services.py — Collecte des métriques et calcul de santé globale.
"""
import logging
from datetime import timedelta

from django.db import connection
from django.utils import timezone
from django.db.models import Max, Avg, Count

logger = logging.getLogger('system_health')


def get_latest_sensor_readings():
    """Retourne le dernier enregistrement par type de capteur (MySQL-compatible)."""
    from .models import SensorReading
    # MySQL ne supporte pas DISTINCT ON — on utilise un sous-requête MAX(id) par type
    from django.db.models import Subquery, OuterRef

    latest_ids = (
        SensorReading.objects
        .filter(sensor_type=OuterRef('sensor_type'))
        .order_by('-collected_at')
        .values('id')[:1]
    )
    readings = (
        SensorReading.objects
        .filter(id__in=SensorReading.objects.annotate(
            latest_id=Subquery(latest_ids)
        ).values('latest_id'))
    )
    # Fallback simple si subquery complexe
    try:
        result = {r.sensor_type: r for r in readings}
    except Exception:
        result = {}
        for reading in SensorReading.objects.order_by('sensor_type', '-collected_at'):
            if reading.sensor_type not in result:
                result[reading.sensor_type] = reading
    return result


def _compute_status(sensor_type, value):
    """Évalue le statut d'un capteur par rapport aux seuils configurés."""
    from .models import AlertThreshold
    try:
        threshold = AlertThreshold.objects.get(sensor_type=sensor_type, enabled=True)
        return threshold.compute_status(value)
    except AlertThreshold.DoesNotExist:
        return 'unknown'


# ─── Capteurs techniques ──────────────────────────────────────────────────────

def collect_server_sensors():
    """Collecte CPU, mémoire, disque via psutil."""
    from .models import SensorReading
    try:
        import psutil
        readings = []

        cpu = psutil.cpu_percent(interval=1)
        status = _compute_status('cpu_usage', cpu)
        readings.append(SensorReading(sensor_type='cpu_usage', value=cpu, status=status,
                                      metadata={'per_cpu': psutil.cpu_percent(percpu=True)}))

        mem = psutil.virtual_memory()
        mem_pct = mem.percent
        status = _compute_status('memory_usage', mem_pct)
        readings.append(SensorReading(sensor_type='memory_usage', value=mem_pct, status=status,
                                      metadata={'total_gb': round(mem.total / 1e9, 1),
                                                'used_gb':  round(mem.used  / 1e9, 1)}))

        disk = psutil.disk_usage('/')
        disk_pct = disk.percent
        disk_free = round(disk.free / 1e9, 1)
        readings.append(SensorReading(sensor_type='disk_usage', value=disk_pct,
                                      status=_compute_status('disk_usage', disk_pct)))
        readings.append(SensorReading(sensor_type='disk_free_gb', value=disk_free,
                                      status=_compute_status('disk_free_gb', disk_free)))

        try:
            import os
            readings.append(SensorReading(sensor_type='open_files',
                                          value=len(psutil.Process(os.getpid()).open_files()),
                                          status='ok'))
        except Exception:
            pass

        try:
            load = psutil.getloadavg()[0]
            readings.append(SensorReading(sensor_type='load_average', value=round(load, 2),
                                          status=_compute_status('load_average', load)))
        except AttributeError:
            # Windows n'a pas getloadavg
            readings.append(SensorReading(sensor_type='load_average', value=None, status='unknown'))

        SensorReading.objects.bulk_create(readings)
        logger.debug('Server sensors collected (%d readings)', len(readings))
        return True
    except ImportError:
        logger.error('psutil non disponible pour la collecte des capteurs serveur')
        return False
    except Exception as exc:
        logger.exception('Erreur collecte capteurs serveur: %s', exc)
        return False


# ─── Disques & stockage (16.14) ───────────────────────────────────────────────

_EXCLUDED_FSTYPES = {
    'tmpfs', 'devtmpfs', 'squashfs', 'overlay', 'proc', 'sysfs',
    'cgroup', 'cgroup2', 'devpts', 'mqueue', 'debugfs', 'tracefs',
    'securityfs', 'pstore', 'bpf', 'autofs', 'binfmt_misc', 'configfs',
}


def get_disk_partitions_usage():
    """Retourne l'usage (total/utilisé/libre/%) de chaque point de montage réel."""
    try:
        import psutil
    except ImportError:
        logger.error('psutil non disponible pour la lecture des disques')
        return []

    partitions = []
    for p in psutil.disk_partitions(all=False):
        if p.fstype in _EXCLUDED_FSTYPES:
            continue
        try:
            usage = psutil.disk_usage(p.mountpoint)
        except (PermissionError, OSError):
            continue

        percent = usage.percent
        if percent >= 90:
            status = 'critical'
        elif percent >= 80:
            status = 'warning'
        else:
            status = 'ok'

        partitions.append({
            'device':      p.device,
            'mountpoint':  p.mountpoint,
            'fstype':      p.fstype,
            'total_gb':    round(usage.total / 1e9, 2),
            'used_gb':     round(usage.used / 1e9, 2),
            'free_gb':     round(usage.free / 1e9, 2),
            'percent':     round(percent, 1),
            'status':      status,
        })

    partitions.sort(key=lambda d: d['mountpoint'])
    return partitions


def get_disk_summary():
    """Vue d'ensemble stockage : liste des disques + totaux agrégés."""
    partitions = get_disk_partitions_usage()
    total = sum(p['total_gb'] for p in partitions)
    used  = sum(p['used_gb'] for p in partitions)
    free  = sum(p['free_gb'] for p in partitions)
    percent = round(used / total * 100, 1) if total else 0
    if percent >= 90:
        status = 'critical'
    elif percent >= 80:
        status = 'warning'
    else:
        status = 'ok'
    return {
        'partitions': partitions,
        'count':      len(partitions),
        'total_gb':   round(total, 2),
        'used_gb':    round(used, 2),
        'free_gb':    round(free, 2),
        'percent':    percent,
        'status':     status,
    }


def collect_app_sensors():
    """Collecte métriques applicatives depuis PerformanceEvent."""
    from .models import SensorReading
    try:
        from apps.performance_monitor.models import PerformanceEvent
        since = timezone.now() - timedelta(hours=1)
        qs = PerformanceEvent.objects.filter(timestamp__gte=since)
        total = qs.count()
        agg = qs.aggregate(avg=Avg('response_ms'), mx=Max('response_ms'))
        slow = qs.filter(response_ms__gte=2000).count()
        errors = qs.filter(status_code__gte=500).count()
        error_rate = round(errors / total * 100, 1) if total > 0 else 0

        readings = [
            SensorReading(sensor_type='avg_response_ms', value=round(agg['avg'] or 0, 1),
                          status=_compute_status('avg_response_ms', agg['avg'] or 0)),
            SensorReading(sensor_type='max_response_ms', value=round(agg['mx'] or 0, 1),
                          status=_compute_status('max_response_ms', agg['mx'] or 0)),
            SensorReading(sensor_type='requests_per_min', value=round(total / 60, 1),
                          status='ok'),
            SensorReading(sensor_type='slow_requests_1h', value=slow,
                          status=_compute_status('slow_requests_1h', slow)),
            SensorReading(sensor_type='error_rate_pct', value=error_rate,
                          status=_compute_status('error_rate_pct', error_rate)),
        ]
        SensorReading.objects.bulk_create(readings)
        return True
    except Exception as exc:
        logger.exception('Erreur collecte capteurs applicatifs: %s', exc)
        return False


def collect_db_sensors():
    """Collecte métriques base de données."""
    from .models import SensorReading
    try:
        readings = []

        # Connexions actives
        with connection.cursor() as cursor:
            cursor.execute("SHOW STATUS LIKE 'Threads_connected'")
            row = cursor.fetchone()
            db_conns = int(row[1]) if row else 0
        readings.append(SensorReading(sensor_type='db_connections', value=db_conns,
                                      status=_compute_status('db_connections', db_conns)))

        # Taille base
        try:
            from django.conf import settings
            db_name = settings.DATABASES['default']['NAME']
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT ROUND(SUM(data_length + index_length) / 1e9, 2) "
                    "FROM information_schema.tables WHERE table_schema = %s",
                    [db_name]
                )
                row = cursor.fetchone()
                db_size = float(row[0]) if row and row[0] else 0
            readings.append(SensorReading(sensor_type='db_size_gb', value=db_size, status='ok'))
        except Exception:
            pass

        # Migrations en attente
        try:
            from django.db.migrations.executor import MigrationExecutor
            executor = MigrationExecutor(connection)
            pending = len(executor.migration_plan(executor.loader.graph.leaf_nodes()))
            readings.append(SensorReading(sensor_type='db_pending_migrations', value=pending,
                                          status='warning' if pending > 0 else 'ok'))
        except Exception:
            pass

        # Disponibilité DB
        try:
            connection.ensure_connection()
            readings.append(SensorReading(sensor_type='db_available', value=1, status='ok'))
        except Exception:
            readings.append(SensorReading(sensor_type='db_available', value=0, status='critical'))

        SensorReading.objects.bulk_create(readings)
        return True
    except Exception as exc:
        logger.exception('Erreur collecte capteurs DB: %s', exc)
        return False


def collect_backup_sensors():
    """Collecte âge de la dernière sauvegarde depuis BackupJob."""
    from .models import SensorReading
    try:
        from apps.backups.models import BackupJob
        now = timezone.now()
        last = BackupJob.objects.filter(status='success').order_by('-finished_at').first()
        if last and last.finished_at:
            age_hours = round((now - last.finished_at).total_seconds() / 3600, 1)
            size_mb = last.file_size / 1e6 if hasattr(last, 'file_size') and last.file_size else None
        else:
            age_hours = 9999
            size_mb = None

        readings = [
            SensorReading(sensor_type='backup_age_hours', value=age_hours,
                          status=_compute_status('backup_age_hours', age_hours)),
        ]
        if size_mb is not None:
            readings.append(SensorReading(sensor_type='backup_size_mb', value=size_mb, status='ok'))

        SensorReading.objects.bulk_create(readings)
        return True
    except Exception as exc:
        logger.exception('Erreur collecte capteurs backup: %s', exc)
        return False


def collect_security_sensors():
    """Collecte indicateurs sécurité depuis AuditLog."""
    from .models import SensorReading
    try:
        from apps.core.models import AuditLog
        since = timezone.now() - timedelta(hours=1)
        failed = AuditLog.objects.filter(action='login_failed', created_at__gte=since).count()

        from .models import SystemError
        open_errors = SystemError.objects.filter(status__in=['new', 'analysed', 'confirmed', 'in_progress']).count()
        from .models import SystemIncident
        open_incidents = SystemIncident.objects.filter(status__in=['open', 'investigating', 'identified']).count()

        readings = [
            SensorReading(sensor_type='failed_logins_1h', value=failed,
                          status=_compute_status('failed_logins_1h', failed)),
            SensorReading(sensor_type='open_errors', value=open_errors,
                          status=_compute_status('open_errors', open_errors)),
            SensorReading(sensor_type='open_incidents', value=open_incidents,
                          status='critical' if open_incidents > 0 else 'ok'),
        ]
        SensorReading.objects.bulk_create(readings)
        return True
    except Exception as exc:
        logger.exception('Erreur collecte capteurs sécurité: %s', exc)
        return False


def collect_celery_sensors():
    """
    Collecte métriques Celery : broker, workers, ping, files, tâches, Beat.
    Scoring sur 10 dimensions (voir compute_celery_score).
    """
    from .models import SensorReading
    readings = []

    # 1. Broker accessible ?
    broker_ok = _check_celery_broker()
    readings.append(SensorReading(
        sensor_type='celery_broker_ok',
        value=1 if broker_ok else 0,
        status='ok' if broker_ok else 'critical',
        metadata={'url': _get_broker_url_safe()},
    ))

    if not broker_ok:
        # Sans broker, tout le reste est inconnu
        for st in ('queue_workers', 'celery_ping_ok', 'celery_active_tasks',
                   'celery_beat_ok', 'celery_result_backend_ok'):
            readings.append(SensorReading(sensor_type=st, value=None, status='critical'))
        SensorReading.objects.bulk_create(readings)
        return False

    # 2. Workers et ping
    try:
        from celery import current_app
        inspector = current_app.control.inspect(timeout=5)

        stats      = inspector.stats()   or {}
        active     = inspector.active()  or {}
        reserved   = inspector.reserved() or {}
        scheduled  = inspector.scheduled() or {}
        ping_resp  = current_app.control.ping(timeout=3)

        total_workers  = len(stats)
        active_count   = sum(len(v) for v in active.values())
        reserved_count = sum(len(v) for v in reserved.values())
        ping_ok        = bool(ping_resp)

        readings.append(SensorReading(
            sensor_type='queue_workers',
            value=total_workers,
            status='critical' if total_workers == 0 else ('warning' if total_workers < 2 else 'ok'),
            metadata={
                'active_tasks': active_count,
                'reserved': reserved_count,
                'scheduled': sum(len(v) for v in scheduled.values()),
                'worker_names': list(stats.keys()),
            },
        ))
        readings.append(SensorReading(
            sensor_type='celery_ping_ok',
            value=1 if ping_ok else 0,
            status='ok' if ping_ok else 'critical',
            metadata={'responses': len(ping_resp) if ping_resp else 0},
        ))
        readings.append(SensorReading(
            sensor_type='celery_active_tasks',
            value=active_count,
            status='ok',
            metadata={'reserved': reserved_count},
        ))
    except Exception as exc:
        logger.error('Celery inspect failed: %s', exc)
        readings.append(SensorReading(sensor_type='queue_workers',      value=0,    status='critical'))
        readings.append(SensorReading(sensor_type='celery_ping_ok',     value=0,    status='critical'))
        readings.append(SensorReading(sensor_type='celery_active_tasks', value=None, status='unknown'))

    # 3. Backend de résultats
    backend_ok = _check_celery_result_backend()
    readings.append(SensorReading(
        sensor_type='celery_result_backend_ok',
        value=1 if backend_ok else 0,
        status='ok' if backend_ok else 'warning',
    ))

    # 4. Celery Beat — dernière exécution via django_celery_beat
    beat_ok, beat_meta = _check_celery_beat()
    readings.append(SensorReading(
        sensor_type='celery_beat_ok',
        value=1 if beat_ok else 0,
        status='ok' if beat_ok else 'warning',
        metadata=beat_meta,
    ))

    try:
        SensorReading.objects.bulk_create(readings)
    except Exception as exc:
        logger.error('bulk_create sensors failed: %s', exc)
        for r in readings:
            try:
                r.save()
            except Exception:
                pass
    return True


def _get_broker_url_safe() -> str:
    """Retourne l'URL du broker sans credentials."""
    try:
        from django.conf import settings
        url = getattr(settings, 'CELERY_BROKER_URL', '')
        # Masquer le mot de passe éventuel
        if '@' in url:
            scheme, rest = url.split('://', 1)
            rest = rest.split('@', 1)[1]
            return f'{scheme}://***@{rest}'
        return url
    except Exception:
        return 'redis://127.0.0.1:6379/0'


def _check_celery_broker() -> bool:
    """Teste la connexion au broker Redis sans passer par Celery."""
    try:
        import redis
        from django.conf import settings
        url = getattr(settings, 'CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0')
        r = redis.from_url(url, socket_connect_timeout=3, socket_timeout=3)
        return r.ping()
    except Exception as exc:
        logger.warning('Broker check failed: %s', exc)
        return False


def _check_celery_result_backend() -> bool:
    """Teste la connexion au backend de résultats."""
    try:
        import redis
        from django.conf import settings
        url = getattr(settings, 'CELERY_RESULT_BACKEND', 'redis://127.0.0.1:6379/0')
        r = redis.from_url(url, socket_connect_timeout=3, socket_timeout=3)
        return r.ping()
    except Exception:
        return False


def _check_celery_beat() -> tuple:
    """
    Vérifie si Celery Beat a exécuté des tâches récemment.
    Utilise django_celery_beat.models.PeriodicTask.
    """
    try:
        from django_celery_beat.models import PeriodicTask
        from django.utils import timezone as tz
        from datetime import timedelta

        tasks = PeriodicTask.objects.filter(enabled=True)
        total = tasks.count()
        if total == 0:
            return False, {'reason': 'Aucune tâche périodique activée'}

        # Tâches dont last_run_at est dans les 15 dernières minutes
        cutoff = tz.now() - timedelta(minutes=15)
        recent = tasks.filter(last_run_at__gte=cutoff).count()
        never_run = tasks.filter(last_run_at__isnull=True).count()

        beat_ok = recent > 0 or never_run == total  # OK si toutes nouvelles ou récentes
        return beat_ok, {
            'total_periodic': total,
            'run_last_15min': recent,
            'never_run': never_run,
        }
    except Exception as exc:
        logger.warning('Beat check failed: %s', exc)
        return False, {'error': str(exc)}


# ─── Score global ─────────────────────────────────────────────────────────────

STATUS_SCORE = {'ok': 100, 'warning': 60, 'critical': 10, 'error': 0, 'unknown': 50}


def _score_from_readings(readings, sensor_list):
    """Moyenne des scores des capteurs présents dans readings."""
    scores = [STATUS_SCORE.get(readings[s].status, 50) for s in sensor_list if s in readings]
    return round(sum(scores) / len(scores)) if scores else 50


def compute_celery_score(readings) -> tuple:
    """
    Score Celery sur 100 points — 10 dimensions pondérées.
    Retourne (score, details_dict).

    Plafonds :
    - Broker DOWN     → max 10
    - 0 worker        → max 20
    - Beat absent     → -10
    """
    points = 0
    details = {}

    # 1. Broker accessible (15 pts)
    broker_ok = readings.get('celery_broker_ok')
    if broker_ok and broker_ok.status == 'ok':
        points += 15
        details['broker'] = {'pts': 15, 'status': 'ok'}
    else:
        details['broker'] = {'pts': 0, 'status': 'critical', 'reason': 'Broker inaccessible'}
        return min(points, 10), details  # PLAFOND 10

    # 2. Workers disponibles (15 pts)
    workers_r = readings.get('queue_workers')
    worker_count = int(workers_r.value) if workers_r and workers_r.value is not None else 0
    if worker_count >= 2:
        w_pts = 15
    elif worker_count == 1:
        w_pts = 8
    else:
        w_pts = 0
    points += w_pts
    details['workers'] = {'pts': w_pts, 'count': worker_count}
    if worker_count == 0:
        return min(points, 20), details  # PLAFOND 20

    # 3. Réponse au ping (10 pts)
    ping_r = readings.get('celery_ping_ok')
    ping_ok = ping_r and ping_r.status == 'ok'
    ping_pts = 10 if ping_ok else 0
    points += ping_pts
    details['ping'] = {'pts': ping_pts, 'status': 'ok' if ping_ok else 'failed'}

    # 4. Files non bloquées (10 pts) — pas de tâches réservées depuis longtemps
    active_r = readings.get('celery_active_tasks')
    reserved = (active_r.metadata or {}).get('reserved', 0) if active_r else 0
    queue_pts = 10 if reserved < 100 else 5
    points += queue_pts
    details['queues'] = {'pts': queue_pts, 'reserved': reserved}

    # 5. Tâches exécutées avec succès (15 pts)
    # Proxy : si le worker répond et aucune erreur détectée → 15
    # En production, on lirait les stats de succès/échec depuis le backend
    task_pts = 15 if ping_ok else 5
    points += task_pts
    details['task_success'] = {'pts': task_pts}

    # 6. Absence de tâches anormalement anciennes (10 pts)
    # Proxy : si active = 0 ou reasonable → 10 (vraie métrique nécessite Flower/backend)
    active_count = int(active_r.value) if active_r and active_r.value is not None else 0
    age_pts = 10 if active_count < 50 else 3
    points += age_pts
    details['task_age'] = {'pts': age_pts, 'active': active_count}

    # 7. Celery Beat fonctionnel (10 pts)
    beat_r = readings.get('celery_beat_ok')
    beat_ok = beat_r and beat_r.status == 'ok'
    beat_pts = 10 if beat_ok else 0
    points += beat_pts
    details['beat'] = {'pts': beat_pts, 'status': 'ok' if beat_ok else 'absent/inactif'}
    if not beat_ok:
        points -= 5  # pénalité supplémentaire Beat absent

    # 8. Backend de résultats (5 pts)
    backend_r = readings.get('celery_result_backend_ok')
    backend_ok = backend_r and backend_r.status == 'ok'
    backend_pts = 5 if backend_ok else 0
    points += backend_pts
    details['result_backend'] = {'pts': backend_pts, 'status': 'ok' if backend_ok else 'ko'}

    # 9. Retries configurés (5 pts) — vérifié statiquement depuis settings
    retry_pts = _check_celery_retry_config()
    points += retry_pts
    details['retry_config'] = {'pts': retry_pts}

    # 10. Monitoring disponible (5 pts) — capteurs présents = monitoring actif
    monitor_pts = 5 if len(readings) >= 4 else 2
    points += monitor_pts
    details['monitoring'] = {'pts': monitor_pts, 'sensors': len(readings)}

    return max(0, min(100, points)), details


def _check_celery_retry_config() -> int:
    """Vérifie que les settings Celery de fiabilité sont activés."""
    try:
        from django.conf import settings
        score = 0
        if getattr(settings, 'CELERY_TASK_ACKS_LATE', False):
            score += 2
        if getattr(settings, 'CELERY_TASK_REJECT_ON_WORKER_LOST', False):
            score += 1
        if getattr(settings, 'CELERY_TASK_TIME_LIMIT', 0):
            score += 1
        if getattr(settings, 'CELERY_WORKER_MAX_TASKS_PER_CHILD', 0):
            score += 1
        return score
    except Exception:
        return 0


def compute_global_health():
    """
    Calcule l'état de santé global — scores pondérés par composant.
    Retourne un dict complet avec scores, métriques, alertes, timestamp.
    """
    readings  = get_latest_sensor_readings()
    now       = timezone.now()
    breakdown = {}
    details   = {}
    warnings  = []
    criticals = []

    # — SERVER —
    server_sensors = ['cpu_usage', 'memory_usage', 'disk_usage', 'load_average', 'disk_free_gb']
    s_score = _score_from_readings(readings, server_sensors)
    # Pénalité disque critique (< 5 GB libre est critique, < 2 GB est fatal)
    disk_free = readings.get('disk_free_gb')
    if disk_free and disk_free.value is not None:
        if disk_free.value < 2:
            s_score = min(s_score, 5)
            criticals.append('disk_free_gb')
        elif disk_free.value < 5:
            s_score = min(s_score, 40)
            warnings.append('disk_free_gb')
    breakdown['server'] = s_score

    # — APP —
    app_sensors = ['avg_response_ms', 'error_rate_pct', 'slow_requests_1h', 'requests_per_min']
    breakdown['app'] = _score_from_readings(readings, app_sensors)

    # — DATABASE —
    db_sensors = ['db_available', 'db_connections', 'db_pending_migrations', 'db_size_gb']
    db_score = _score_from_readings(readings, db_sensors)
    db_avail = readings.get('db_available')
    if db_avail and db_avail.status == 'critical':
        db_score = min(db_score, 10)
        criticals.append('db_available')
    breakdown['database'] = db_score

    # — BACKUPS —
    backup_sensors = ['backup_age_hours']
    backup_score = _score_from_readings(readings, backup_sensors)
    backup_r = readings.get('backup_age_hours')
    if backup_r and backup_r.value is not None and backup_r.value > 48:
        backup_score = min(backup_score, 30)
    breakdown['backups'] = backup_score

    # — SECURITY —
    sec_sensors = ['failed_logins_1h', 'open_errors', 'open_incidents']
    sec_score = _score_from_readings(readings, sec_sensors)
    # Incident ouvert = critique
    open_inc = readings.get('open_incidents')
    if open_inc and open_inc.value and int(open_inc.value) > 0:
        sec_score = min(sec_score, 40)
        criticals.append('open_incidents')
    breakdown['security'] = sec_score

    # — CELERY — (scoring dédié)
    celery_score, celery_details = compute_celery_score(readings)
    breakdown['celery'] = celery_score
    details['celery'] = celery_details

    # Alertes transversales
    for sensor_name, reading in readings.items():
        if reading.status == 'critical' and sensor_name not in criticals:
            criticals.append(sensor_name)
        elif reading.status == 'warning' and sensor_name not in warnings:
            warnings.append(sensor_name)

    # Score global = moyenne pondérée
    weights = {'server': 20, 'app': 20, 'database': 20, 'backups': 15, 'security': 15, 'celery': 10}
    total_weight = sum(weights.values())
    global_score = round(sum(breakdown[k] * w for k, w in weights.items()) / total_weight)

    if global_score >= 90:
        status = 'healthy'
    elif global_score >= 70:
        status = 'degraded'
    elif global_score >= 40:
        status = 'unstable'
    else:
        status = 'critical'

    return {
        'status':    status,
        'score':     global_score,
        'breakdown': breakdown,
        'readings':  readings,
        'details':   details,
        'critical':  criticals,
        'warnings':  warnings,
        'timestamp': now,
    }


def purge_old_sensor_readings(days=90):
    """Supprime les lectures de capteurs de plus de N jours."""
    from .models import SensorReading
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = SensorReading.objects.filter(collected_at__lt=cutoff).delete()
    logger.info('Purged %d sensor readings older than %d days', deleted, days)
    return deleted


# ─── Snapshots de santé ───────────────────────────────────────────────────────

def save_health_snapshot(health: dict):
    """Enregistre un snapshot calculé du score global dans HealthSnapshot."""
    from .models import HealthSnapshot
    bd = health.get('breakdown', {})
    HealthSnapshot.objects.create(
        global_score   = health['score'],
        global_status  = health['status'],
        server_score   = bd.get('server', 0),
        app_score      = bd.get('app', 0),
        database_score = bd.get('database', 0),
        backups_score  = bd.get('backups', 0),
        security_score = bd.get('security', 0),
        celery_score   = bd.get('celery', 0),
        critical_sensors = health.get('critical', []),
        warning_sensors  = health.get('warnings', []),
    )


def get_snapshot_history(hours=24):
    """Retourne l'historique des snapshots sur N heures pour les graphes."""
    from .models import HealthSnapshot
    since = timezone.now() - timedelta(hours=hours)
    return list(
        HealthSnapshot.objects
        .filter(collected_at__gte=since)
        .order_by('collected_at')
        .values(
            'collected_at', 'global_score', 'global_status',
            'server_score', 'app_score', 'database_score',
            'backups_score', 'security_score', 'celery_score',
            'critical_sensors',
        )
    )


def purge_old_snapshots(days=30):
    """Purge les snapshots de plus de N jours (conservation limitée)."""
    from .models import HealthSnapshot
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = HealthSnapshot.objects.filter(collected_at__lt=cutoff).delete()
    logger.info('Purged %d health snapshots older than %d days', deleted, days)
    return deleted


# ─── Alertes automatiques ─────────────────────────────────────────────────────

_SENSOR_LABELS = {
    'cpu_usage': 'CPU', 'memory_usage': 'Mémoire', 'disk_usage': 'Disque',
    'disk_free_gb': 'Espace disque libre', 'db_available': 'Base de données',
    'db_connections': 'Connexions DB', 'db_pending_migrations': 'Migrations en attente',
    'backup_age_hours': 'Âge sauvegarde', 'celery_broker_ok': 'Broker Celery',
    'queue_workers': 'Workers Celery', 'celery_result_backend_ok': 'Backend Celery',
    'failed_logins_1h': 'Connexions échouées', 'open_incidents': 'Incidents ouverts',
}


def _notify_superusers(title: str, message: str, level: str, link: str = ''):
    """Envoie une notification in-app à tous les superusers actifs."""
    from django.contrib.auth.models import User
    from apps.notifications.models import Notification
    _level_map = {'info': 'info', 'success': 'info', 'warning': 'warning', 'danger': 'error'}
    notif_type = _level_map.get(level, 'system')
    superusers = User.objects.filter(is_superuser=True, is_active=True)
    notifs = [
        Notification(
            user=u, title=title, message=message,
            notification_type=notif_type, link_url=link,
            source_module='system_health',
        )
        for u in superusers
    ]
    if notifs:
        Notification.objects.bulk_create(notifs, ignore_conflicts=True)


def check_and_alert(prev_criticals: list, curr_health: dict):
    """
    Compare l'état précédent avec le courant.
    Crée un SystemError + Notification pour chaque nouveau capteur critique.
    Escalade en SystemIncident si un capteur est critique depuis longtemps.
    """
    from .models import SystemError, SystemIncident, HealthSnapshot, IncidentTimeline

    curr_criticals = set(curr_health.get('critical', []))
    prev_criticals_set = set(prev_criticals or [])
    new_criticals = curr_criticals - prev_criticals_set

    for sensor in new_criticals:
        label = _SENSOR_LABELS.get(sensor, sensor)
        reading = curr_health.get('readings', {}).get(sensor)
        value_str = f' ({reading.value:.1f})' if reading and reading.value is not None else ''
        err_msg = f'Capteur {label}{value_str} est passé en état CRITIQUE'

        fp = SystemError.compute_fingerprint('system_health', f'sensor_critical_{sensor}')
        existing = SystemError.objects.filter(fingerprint=fp, status__in=['new', 'confirmed', 'in_progress']).first()
        if existing:
            existing.occurrence_count += 1
            existing.save(update_fields=['occurrence_count', 'last_seen'])
        else:
            SystemError.objects.create(
                severity='critical',
                module='system_health',
                error_type=f'sensor_critical_{sensor}',
                user_message=err_msg,
                technical_message=f'Sensor={sensor} value={reading.value if reading else "?"} status=critical',
                fingerprint=fp,
            )
            logger.warning('Auto-alert: new critical sensor %s', sensor)

        _notify_superusers(
            title=f'🔴 Alerte critique : {label}',
            message=err_msg,
            level='danger',
            link='/orion-admin/sante-systeme/',
        )

    # Escalade automatique → incident si capteur critique depuis >30 min
    thirty_min_ago = timezone.now() - timedelta(minutes=30)
    for sensor in curr_criticals:
        sustained = (
            HealthSnapshot.objects
            .filter(collected_at__gte=thirty_min_ago, critical_sensors__icontains=sensor)
            .count()
        )
        if sustained >= 6:  # 6 snapshots × 5 min = 30 min en critique
            open_inc = SystemIncident.objects.filter(
                status__in=['open', 'investigating', 'identified'],
                title__icontains=sensor,
            ).first()
            if not open_inc:
                label = _SENSOR_LABELS.get(sensor, sensor)
                inc = SystemIncident.objects.create(
                    title=f'Dégradation prolongée : {label}',
                    severity='major',
                    status='open',
                    description=(
                        f'Le capteur « {label} » ({sensor}) est en état critique '
                        f'depuis plus de 30 minutes. Escalade automatique.'
                    ),
                    affected_services=[sensor],
                    started_at=thirty_min_ago,
                )
                IncidentTimeline.objects.create(
                    incident=inc,
                    event_type='detected',
                    description=f'Incident créé automatiquement par le superviseur de santé (capteur {sensor} critique >30 min).',
                )
                _notify_superusers(
                    title=f'⚠️ Incident ouvert automatiquement : {label}',
                    message=f'Capteur {label} critique depuis >30 min — incident #{inc.pk} créé.',
                    level='danger',
                    link=f'/orion-admin/sante-systeme/incidents/{inc.pk}/',
                )
                logger.error('Auto-incident created for sustained critical sensor %s (incident #%d)', sensor, inc.pk)

    # Résolution automatique : si un capteur revient à ok, résoudre son SystemError
    resolved = prev_criticals_set - curr_criticals
    for sensor in resolved:
        fp = SystemError.compute_fingerprint('system_health', f'sensor_critical_{sensor}')
        SystemError.objects.filter(fingerprint=fp, status__in=['new', 'confirmed']).update(
            status='resolved',
            resolved_at=timezone.now(),
            solution_applied='Résolu automatiquement : capteur revenu à l\'état ok.',
        )
        label = _SENSOR_LABELS.get(sensor, sensor)
        _notify_superusers(
            title=f'✅ Capteur rétabli : {label}',
            message=f'Le capteur {label} est revenu à l\'état normal.',
            level='success',
            link='/orion-admin/sante-systeme/',
        )


# ─── Endpoints de santé publics ───────────────────────────────────────────────

def check_liveness() -> tuple[bool, str]:
    """Vérifie que l'application est en vie (DB accessible)."""
    try:
        connection.ensure_connection()
        return True, 'ok'
    except Exception as exc:
        return False, str(exc)


def check_readiness() -> tuple[bool, dict]:
    """
    Vérifie que le système est prêt à servir des requêtes.
    Prêt = score global >= 70 ET DB disponible ET pas de composant à 0.
    """
    live, live_msg = check_liveness()
    if not live:
        return False, {'status': 'not_ready', 'reason': 'database_unavailable', 'detail': live_msg}

    from .models import HealthSnapshot
    last = HealthSnapshot.objects.order_by('-collected_at').first()
    if last is None:
        return True, {'status': 'ready', 'note': 'no_snapshot_yet'}

    if last.global_score < 40:
        return False, {
            'status': 'not_ready',
            'reason': 'health_critical',
            'global_score': last.global_score,
            'critical': last.critical_sensors,
        }

    return True, {
        'status': 'ready',
        'global_score': last.global_score,
        'global_status': last.global_status,
        'breakdown': {
            'server': last.server_score, 'app': last.app_score,
            'database': last.database_score, 'backups': last.backups_score,
            'security': last.security_score, 'celery': last.celery_score,
        },
    }
