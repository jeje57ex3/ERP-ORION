"""Déclenche enfin les sauvegardes planifiées.

LE DÉFAUT CORRIGÉ

`apps/backups/tasks.py` porte `run_scheduled_backup(schedule_id)` et
`apps/backups/models.py` porte `BackupSchedule`. RIEN n'appelait la première
— vérifié sur tout le dépôt : aucune vue, aucune commande, aucun horaire.

Une planification saisie dans le Centre sauvegardes ne partait donc jamais.
L'écran affichait un « prochain run » qui n'arrivait pas, et aucun message
ne disait que la mécanique était absente. C'est le même défaut que la
collecte des capteurs, corrigé par la migration 0007 : une tâche qui se dit
planifiée, sans rien pour la planifier.

POURQUOI UN DÉCLENCHEUR PLUTÔT QU'UN HORAIRE PAR PLANIFICATION

On aurait pu créer une PeriodicTask par BackupSchedule. Ce serait deux
sources de vérité pour le même horaire, à tenir synchronisées à chaque
modification faite dans le Centre sauvegardes — et la première divergence
ferait partir une sauvegarde supprimée, ou n'en ferait plus partir une
déplacée. Un seul déclencheur qui relit la table à chaque passage garde
l'écran de l'ERP comme unique référence.

TOUTES LES QUINZE MINUTES

Assez fin pour qu'une sauvegarde prévue à 02:00 parte entre 02:00 et 02:15,
et assez espacé pour ne rien coûter. La tâche ne fait qu'une requête quand
rien n'est dû.

CE QUI N'EST DÉLIBÉRÉMENT PAS PLANIFIÉ

`cleanup_old_backup_files` SUPPRIME des fichiers. Elle n'a jamais tourné sur
aucune installation : la planifier d'un coup ferait disparaître d'un seul
passage tout ce qui dépasse la rétention, y compris des archives que
l'exploitant croyait garder. Une purge se décide, elle ne s'allume pas dans
une migration.
"""
from django.db import migrations


NOM = 'Sauvegardes — déclencheur des planifications'
TACHE = 'backups.declencher_les_planifications'


def planifier(apps, schema_editor):
    IntervalSchedule = apps.get_model('django_celery_beat', 'IntervalSchedule')
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')

    intervalle, _ = IntervalSchedule.objects.get_or_create(
        every=15, period='minutes')
    PeriodicTask.objects.get_or_create(
        name=NOM,
        defaults={
            'task': TACHE,
            'interval': intervalle,
            'enabled': True,
            'description': (
                'Relit les planifications du Centre sauvegardes et lance '
                'celles arrivées à échéance. Sans elle, une planification '
                'saisie dans l’interface ne part jamais.'),
        },
    )


def deplanifier(apps, schema_editor):
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    PeriodicTask.objects.filter(name=NOM).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('system_health', '0009_reglages_proxmox'),
        ('django_celery_beat', '0001_initial'),
        # La table des planifications doit exister avant qu'on promette de
        # la lire.
        ('backups', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(planifier, deplanifier),
    ]
