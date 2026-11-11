"""Donne un horaire au planificateur, qui tournait à vide.

LE DÉFAUT CORRIGÉ

CELERY_BEAT_SCHEDULER vaut « django_celery_beat.schedulers:DatabaseScheduler »
et aucun CELERY_BEAT_SCHEDULE n'existe dans les réglages : TOUS les horaires
doivent donc être des lignes en base. Personne n'en avait créé.

Conséquences mesurées :

  * la tâche `system_health.collect_all_sensors` porte dans sa docstring
    « Planifié toutes les 5 minutes via Celery Beat », et la page des
    capteurs affiche « Métriques temps-réel collectées toutes les
    5 minutes ». Elle n'était appelée de NULLE PART — ni horaire, ni vue,
    ni bouton. Les scores de la page Santé reposaient sur la dernière
    collecte manuelle, quelle que soit sa date, parce que
    `get_latest_sensor_readings()` ne borne pas l'ancienneté ;

  * `_check_celery_beat()` rend « False » quand aucune tâche périodique
    n'est active. Le score Celery perdait donc 10 points pour Beat, plus
    5 de pénalité : 15 points sur 100. Avec les 5 points des réglages de
    fiabilité absents, cela fait exactement les 20 points manquants du
    « 80 sur 100 » constaté.

Le seul moyen de créer ces lignes était `manage.py setup_orion_ops`, une
commande en terminal que ni le provisionnement ni la mise à jour ne lancent.
Une migration, elle, arrive avec la mise à jour et ne demande rien.

IDEMPOTENTE ET RÉVERSIBLE

`get_or_create` sur le nom : rejouer la migration ne crée pas de doublon, et
une tâche que l'exploitant aurait désactivée à la main N'EST PAS réactivée --
on ne touche qu'à ce qui n'existe pas. La marche arrière supprime exactement
les trois lignes créées ici, et rien d'autre.
"""
from django.db import migrations


# Les trois horaires. Le nom sert de clé : il ne doit plus changer, sinon une
# mise à jour future recréerait un doublon à côté de l'ancien.
TACHES = [
    {
        'nom': 'Santé — collecte des capteurs',
        'tache': 'system_health.collect_all_sensors',
        'intervalle': (5, 'minutes'),
        'description': (
            'Mesure CPU, mémoire, disque, base, Celery et sauvegardes. '
            'La page des capteurs et tous les scores de santé en dépendent.'),
    },
    {
        'nom': 'Santé — purge des mesures anciennes',
        'tache': 'system_health.purge_old_sensor_readings',
        'intervalle': (1, 'days'),
        'description': (
            'Supprime les lectures de plus de 90 jours et les instantanés de '
            'plus de 30 jours. Sans elle, la table des capteurs grossit de '
            'plusieurs milliers de lignes par jour.'),
    },
    {
        'nom': 'Contrôle mensuel de l’installation',
        'tache': 'system_health.controler_l_installation',
        'intervalle': (30, 'days'),
        'description': (
            'Vérifie migrations, planificateur, courtier, cache, courriels, '
            'assistants privilégiés, place disque et sauvegardes. Ne répare '
            'rien : il mesure et rapporte.'),
    },
]


def planifier(apps, schema_editor):
    # Les modèles passent par `apps` et non par un import direct : une
    # migration doit voir le schéma TEL QU'IL ÉTAIT, pas celui du code
    # d'aujourd'hui.
    IntervalSchedule = apps.get_model('django_celery_beat', 'IntervalSchedule')
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')

    for entree in TACHES:
        nombre, periode = entree['intervalle']
        intervalle, _ = IntervalSchedule.objects.get_or_create(
            every=nombre, period=periode)
        PeriodicTask.objects.get_or_create(
            name=entree['nom'],
            defaults={
                'task': entree['tache'],
                'interval': intervalle,
                'enabled': True,
                'description': entree['description'],
            },
        )


def deplanifier(apps, schema_editor):
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')
    PeriodicTask.objects.filter(
        name__in=[entree['nom'] for entree in TACHES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('system_health', '0006_operations_de_stockage'),
        # Les tables d'horaires doivent exister avant qu'on y écrive.
        ('django_celery_beat', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(planifier, deplanifier),
    ]
