"""
apps/backups/tasks.py — Tâches Celery pour les sauvegardes
Nécessite Celery + Redis. Fonctionne aussi via management commands.
"""
try:
    from celery import shared_task
except ImportError:
    def shared_task(fn=None, **kwargs):
        if fn:
            return fn
        def decorator(f):
            return f
        return decorator


@shared_task(bind=True, max_retries=3)
def run_scheduled_backup(self, schedule_id):
    try:
        from apps.backups.models import BackupSchedule
        from apps.backups.services import create_database_backup, create_full_backup
        schedule = BackupSchedule.objects.get(pk=schedule_id)
        if not schedule.is_active:
            return 'Schedule inactif'
        if schedule.scope == 'full_system':
            create_full_backup(company=schedule.company)
        else:
            create_database_backup(company=schedule.company, scope=schedule.scope)
        from django.utils import timezone
        schedule.last_run_at = timezone.now()
        schedule.save()
        return f'OK: {schedule.name}'
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)


@shared_task
def run_company_backup(company_id):
    from apps.core.models import Company
    from apps.backups.services import create_database_backup
    try:
        company = Company.objects.get(pk=company_id)
        job = create_database_backup(company=company, scope='company_database')
        return f'Backup {company.name}: {job.status}'
    except Exception as e:
        return f'Erreur: {e}'


@shared_task
def run_full_system_backup():
    from apps.core.models import Company
    from apps.backups.services import create_database_backup, create_full_backup
    results = []
    core_job = create_database_backup(scope='core_database')
    results.append(f'Core: {core_job.status}')
    for company in Company.objects.filter(is_active=True):
        job = create_database_backup(company=company, scope='company_database')
        results.append(f'{company.name}: {job.status}')
    return results


@shared_task
def cleanup_old_backup_files():
    from apps.backups.services import cleanup_old_backups
    deleted = cleanup_old_backups()
    return f'{deleted} sauvegardes supprimées'


# ─── Le déclencheur des planifications ───────────────────────────────────────
#
# `run_scheduled_backup` existait, `BackupSchedule` existait, et RIEN
# n'appelait la première -- vérifié sur tout le dépôt. Une planification
# saisie dans le Centre sauvegardes ne partait donc jamais, et l'écran
# affichait une prochaine exécution qui n'arrivait pas. C'est le même défaut
# que les capteurs de santé : une tâche qui se dit planifiée, sans rien pour
# la planifier.


def _moment_prevu(planification, maintenant):
    """L'heure à laquelle cette planification devait partir aujourd'hui."""
    return maintenant.replace(
        hour=planification.time.hour,
        minute=planification.time.minute,
        second=0, microsecond=0,
    )


def est_due(planification, maintenant):
    """Cette planification doit-elle partir maintenant ?

    DEUX PRÉCAUTIONS qui comptent plus que l'exactitude de l'horaire :

    1. On ne repart pas deux fois pour la même échéance. Le déclencheur
       tourne toutes les quinze minutes ; sans cette garde, une sauvegarde
       quotidienne partirait quatre fois par heure jusqu'à minuit.

    2. Une planification CRÉÉE APRÈS l'heure du jour n'est pas rattrapée
       dans la foulée. `created_at` sert de plancher quand aucune exécution
       n'a eu lieu : saisir à quinze heures une sauvegarde prévue à deux
       heures ne doit pas en déclencher une immédiatement, ce qui
       surprendrait et, sur une grosse base, bloquerait la machine en
       pleine journée.
    """
    if not planification.is_active:
        return False

    moment = _moment_prevu(planification, maintenant)
    if maintenant < moment:
        return False

    if planification.frequency == 'weekly':
        if planification.day_of_week is None:
            return False
        if maintenant.weekday() != planification.day_of_week:
            return False

    if planification.frequency == 'monthly':
        # Le modèle ne porte pas de jour du mois : on retient le premier.
        # Mieux vaut une règle écrite et prévisible qu'un choix implicite.
        if maintenant.day != 1:
            return False

    reference = planification.last_run_at or planification.created_at
    if reference is None:
        return True
    return reference < moment


def _prochaine_echeance(planification, maintenant):
    """À titre indicatif, pour que l'écran affiche quelque chose de vrai."""
    from datetime import timedelta

    moment = _moment_prevu(planification, maintenant)
    if planification.frequency == 'weekly':
        return moment + timedelta(days=7)
    if planification.frequency == 'monthly':
        return moment + timedelta(days=30)
    return moment + timedelta(days=1)


@shared_task(name='backups.declencher_les_planifications')
def declencher_les_planifications():
    """Fait partir les sauvegardes planifiées arrivées à échéance.

    Ne lève jamais pour une planification : une qui échoue ne doit pas
    empêcher les suivantes de partir. C'est la même règle que pour le
    contrôle mensuel, et pour la même raison -- le moment où quelque chose
    va mal est celui où on a le plus besoin du reste.
    """
    import logging

    from django.utils import timezone

    from apps.backups.models import BackupSchedule

    journal = logging.getLogger('backups')
    maintenant = timezone.now()
    lancees, ignorees = [], 0

    for planification in BackupSchedule.objects.filter(is_active=True):
        if not est_due(planification, maintenant):
            ignorees += 1
            continue
        try:
            run_scheduled_backup(planification.pk)
            planification.refresh_from_db()
            planification.next_run_at = _prochaine_echeance(
                planification, maintenant)
            planification.save(update_fields=['next_run_at'])
            lancees.append(planification.name)
        except Exception as exc:                                # noqa: BLE001
            journal.exception(
                'Sauvegarde planifiee « %s » en echec : %s',
                planification.name, exc)

    if lancees:
        journal.info('Sauvegardes planifiees lancees : %s',
                     ', '.join(lancees))
    return {'lancees': lancees, 'ignorees': ignorees}
