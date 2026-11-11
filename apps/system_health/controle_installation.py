"""apps/system_health/controle_installation.py — Le contrôle périodique.

CE QUE CE MODULE VÉRIFIE, ET POURQUOI PAS LA SUITE DE TESTS

La demande était d'employer les tests du dépôt comme contrôle mensuel de
l'état de l'ERP. Trois obstacles mesurés l'interdisent :

  * pytest et pytest-django ne sont PAS dans requirements.txt, donc absents
    de l'environnement du serveur. Les y ajouter installerait l'outillage de
    test en production ;
  * la suite construit une base entière en rejouant toutes les migrations,
    puis la détruit. Sur le serveur qui porte les données, ce n'est pas une
    opération qu'on planifie ;
  * et surtout : elle vérifie le CODE, qui est exactement celui qu'un commit
    a déjà validé. Le rejouer chaque mois ne révèle rien de nouveau.

Ce qui dérive sans qu'une ligne de code change, c'est l'INSTALLATION :
une migration oubliée, un service arrêté, un planificateur vide, un
assistant privilégié absent, une sauvegarde qui date, un disque qui se
remplit, un SMTP qui ne répond plus. Rien de cela n'est visible d'un test
unitaire, et tout cela casse en silence.

Trois contrôles sont cependant reprises de la suite, parce qu'elles portent
sur l'installation : les vérifications système de Django, l'absence de
migration en attente, et la résolution de toutes les confs d'URL incluses
(tests/test_depot_complet.py garde la même idée pour le dépôt).

RÈGLE DE CONCEPTION : UN CONTRÔLE NE PLANTE JAMAIS LE CONTRÔLE

Chaque vérification est encadrée. Une exception devient un résultat
« erreur » portant son motif, et les suivantes s'exécutent. Un contrôle
mensuel qui s'arrête au premier incident ne vaut rien — c'est précisément
quand quelque chose va mal qu'on a besoin du reste du rapport.

ET IL NE RÉPARE RIEN. Il mesure et il rapporte. Une action corrective
automatique, lancée sans témoin à trois heures du matin, est la dernière
chose qu'on souhaite sur un serveur de production.
"""
import logging
import os
import time

from django.utils import timezone

journal = logging.getLogger('system_health')

OK = 'ok'
AVERTISSEMENT = 'warning'
CRITIQUE = 'critical'
ERREUR = 'erreur'


# ── Déclaration d'un contrôle ────────────────────────────────────────────────

class Controle:
    """Un point de vérification nommé."""

    def __init__(self, cle, libelle, fonction, famille='Installation'):
        self.cle = cle
        self.libelle = libelle
        self.fonction = fonction
        self.famille = famille

    def executer(self):
        depart = time.monotonic()
        try:
            etat, message, detail = self.fonction()
        except Exception as exc:                                # noqa: BLE001
            journal.warning('Controle %s en echec : %s', self.cle, exc)
            etat, message, detail = (
                ERREUR, f'Le contrôle n’a pas pu s’exécuter — '
                        f'{type(exc).__name__}: {exc}', {})
        return {
            'cle': self.cle,
            'libelle': self.libelle,
            'famille': self.famille,
            'etat': etat,
            'message': message,
            'detail': detail or {},
            'duree_ms': round((time.monotonic() - depart) * 1000),
        }


# ── Les contrôles, un par fonction ───────────────────────────────────────────

def _verifications_django():
    """`manage.py check`, mais sans terminal.

    Repris de la suite parce qu'il porte sur la configuration réelle de
    CETTE installation : un réglage incohérent dans le .env du serveur ne se
    voit pas autrement.
    """
    from io import StringIO

    from django.core.management import call_command

    sortie = StringIO()
    try:
        call_command('check', stdout=sortie, stderr=sortie)
    except Exception as exc:                                    # noqa: BLE001
        return CRITIQUE, f'Django signale un problème : {exc}', {
            'sortie': sortie.getvalue()[:2000]}
    return OK, 'Aucun problème signalé par les vérifications Django.', {}


def _migrations_en_attente():
    """Une migration non appliquée casse des pages au hasard.

    C'est le défaut le plus fréquent après une mise à jour interrompue : le
    code attend une colonne que la base n'a pas.
    """
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    executeur = MigrationExecutor(connection)
    plan = executeur.migration_plan(
        executeur.loader.graph.leaf_nodes())
    if not plan:
        return OK, 'Toutes les migrations sont appliquées.', {}

    noms = [f'{migration.app_label}.{migration.name}'
            for migration, _ in plan]
    return CRITIQUE, (
        f'{len(noms)} migration(s) en attente. Le code attend un schéma que '
        f'la base n’a pas encore.'
    ), {'migrations': noms[:30]}


def _confs_d_url():
    """Toutes les confs d'URL incluses se résolvent-elles ?

    Le résolveur charge l'arbre ENTIER à la première requête : un include
    qui ne résout pas met tout le site à terre, pas seulement sa branche.
    La suite garde la même idée côté dépôt (fichier versionné ou non) ; ici
    on vérifie l'installation (module réellement importable).
    """
    from django.urls import get_resolver

    resolveur = get_resolver()
    try:
        nombre = len(resolveur.url_patterns)
    except Exception as exc:                                    # noqa: BLE001
        return CRITIQUE, (
            f'L’arbre des adresses ne se charge pas : {exc}. Tout l’ERP '
            f'répondrait en erreur.'), {}
    return OK, f'{nombre} branches d’adresses chargées.', {'branches': nombre}


def _assistants_privilegies():
    """Les ponts root sont-ils installés ?

    Sans eux, des boutons de l'interface n'apparaissent pas — et rien ne
    l'explique. C'est exactement ce qui fait dire « il n'y a pas de
    bouton ».
    """
    if os.name != 'posix':
        return OK, 'Hors Linux : sans objet sur un poste de développement.', {}

    attendus = {
        '/usr/local/sbin/orion-stockage': 'préparation des disques',
        '/etc/sudoers.d/orion-stockage': 'règles sudo des disques',
    }
    manquants = [f'{chemin} ({role})'
                 for chemin, role in attendus.items()
                 if not os.path.exists(chemin)]
    if not manquants:
        return OK, 'Les assistants privilégiés sont en place.', {}
    return AVERTISSEMENT, (
        'Assistant(s) absent(s) : les boutons correspondants ne '
        's’afficheront pas.'), {'manquants': manquants}


def _planificateur():
    """Celery Beat a-t-il quelque chose à faire, et le fait-il ?

    Une file vide est le cas réel de cette installation : le planificateur
    lit ses horaires EN BASE (DatabaseScheduler) et personne n'y avait
    écrit. Beat tournait donc à vide, et la collecte des capteurs annoncée
    « toutes les 5 minutes » n'avait jamais lieu.
    """
    from datetime import timedelta

    from django_celery_beat.models import PeriodicTask

    taches = PeriodicTask.objects.filter(enabled=True).exclude(
        name__startswith='celery.')
    total = taches.count()
    if total == 0:
        return CRITIQUE, (
            'Aucune tâche périodique active : le planificateur tourne à '
            'vide. Rien de ce qui doit s’exécuter régulièrement ne '
            's’exécute.'), {}

    jamais = taches.filter(last_run_at__isnull=True).count()
    if jamais == total:
        return AVERTISSEMENT, (
            f'{total} tâche(s) planifiée(s), aucune n’a encore tourné. '
            f'Normal juste après une mise à jour ; anormal au-delà.'
        ), {'total': total}

    recentes = taches.filter(
        last_run_at__gte=timezone.now() - timedelta(hours=1)).count()
    if recentes == 0:
        return CRITIQUE, (
            f'{total} tâche(s) planifiée(s) et aucune exécution depuis une '
            f'heure : le service orion-celery-beat est probablement '
            f'arrêté.'), {'total': total, 'jamais': jamais}

    return OK, (
        f'{total} tâche(s) planifiée(s), {recentes} exécutée(s) dans la '
        f'dernière heure.'), {'total': total, 'recentes': recentes}


def _courtier_et_workers():
    """Redis et les workers Celery, mesurés et non supposés."""
    from . import services

    if not services._check_celery_broker():
        return CRITIQUE, (
            'Le courtier Redis ne répond pas : aucune tâche de fond ne peut '
            'être prise en charge.'), {}

    try:
        from celery import current_app
        reponses = current_app.control.ping(timeout=2) or []
    except Exception as exc:                                    # noqa: BLE001
        return AVERTISSEMENT, (
            f'Courtier joignable, mais l’interrogation des workers a '
            f'échoué : {exc}'), {}

    if not reponses:
        return CRITIQUE, (
            'Courtier joignable, aucun worker ne répond : les tâches '
            's’empilent sans être exécutées.'), {}
    return OK, f'{len(reponses)} worker(s) Celery répondent.', {
        'workers': len(reponses)}


def _cache_partage():
    """Le cache doit être partagé entre les workers, pas par processus.

    Un cache par processus casse les jetons de réinitialisation de mot de
    passe et rend les limites de débit inopérantes.
    """
    from django.conf import settings
    from django.core.cache import cache

    backend = settings.CACHES.get('default', {}).get('BACKEND', '')
    cle = 'controle-installation-sonde'
    try:
        cache.set(cle, 'ok', 30)
        lu = cache.get(cle)
        cache.delete(cle)
    except Exception as exc:                                    # noqa: BLE001
        return CRITIQUE, f'Le cache ne répond pas : {exc}', {
            'backend': backend}

    if lu != 'ok':
        return CRITIQUE, 'Le cache n’a pas relu ce qu’il vient d’écrire.', {
            'backend': backend}

    if 'locmem' in backend.lower():
        return AVERTISSEMENT, (
            'Le cache est local au processus. Avec plusieurs workers '
            'gunicorn, chacun a le sien : les jetons et les limites de '
            'débit ne sont pas partagés.'), {'backend': backend}

    return OK, 'Cache partagé opérationnel.', {'backend': backend}


def _courriels():
    """L'ERP peut-il envoyer un courriel ?

    On n'en envoie pas : on ouvre la connexion. Un contrôle mensuel qui
    expédie un message réel remplirait une boîte sans rien prouver de plus.
    """
    from django.conf import settings

    from apps.core.mail import chemin_du_repli, reglages_utilisables

    reglages = reglages_utilisables()
    if reglages is None:
        repli = chemin_du_repli()
        if 'smtp' not in repli.lower():
            return AVERTISSEMENT, (
                'Aucun envoi réel configuré : les messages ne quittent pas '
                'le serveur. À régler sur /orion-admin/courriels/.'
            ), {'repli': repli}
        if not getattr(settings, 'EMAIL_HOST', ''):
            return AVERTISSEMENT, (
                'SMTP sans serveur renseigné. À régler sur '
                '/orion-admin/courriels/.'), {}

    from django.core.mail import get_connection

    connexion = get_connection(fail_silently=False)
    try:
        connexion.open()
        connexion.close()
    except Exception as exc:                                    # noqa: BLE001
        return CRITIQUE, (
            f'Connexion au serveur de courriel impossible — '
            f'{type(exc).__name__}: {exc}'), {}

    cible = (f'{reglages.hote}:{reglages.port}' if reglages
             else f'{getattr(settings, "EMAIL_HOST", "?")}')
    return OK, f'Connexion au serveur de courriel établie ({cible}).', {}


def _place_disque():
    """La place libre, lue sur le disque et non dans un capteur ancien."""
    import shutil

    from django.conf import settings

    chemin = str(getattr(settings, 'BASE_DIR', '.'))
    total, _utilise, libre = shutil.disk_usage(chemin)
    libre_go = libre / 1e9
    pourcent = round(libre / total * 100, 1) if total else 0

    detail = {'libre_go': round(libre_go, 1), 'libre_pct': pourcent}
    if libre_go < 2:
        return CRITIQUE, (
            f'{libre_go:.1f} Go libres seulement. En dessous de 2 Go, une '
            f'mise à jour ou une sauvegarde échoue.'), detail
    if libre_go < 10 or pourcent < 10:
        return AVERTISSEMENT, (
            f'{libre_go:.1f} Go libres ({pourcent} %). Prévoyez un disque '
            f'de données.'), detail
    return OK, f'{libre_go:.1f} Go libres ({pourcent} %).', detail


def _sauvegardes():
    """Une sauvegarde vieille de plus d'une semaine n'en est plus une."""
    from datetime import timedelta

    from .models import SensorReading

    lecture = (SensorReading.objects
               .filter(sensor_type='backup_age_hours')
               .order_by('-collected_at')
               .first())
    if lecture is None or lecture.value is None:
        return AVERTISSEMENT, (
            'Aucune mesure d’ancienneté de sauvegarde. Le capteur n’a '
            'jamais tourné, ou aucune sauvegarde n’existe.'), {}

    if lecture.collected_at < timezone.now() - timedelta(days=2):
        return AVERTISSEMENT, (
            f'La dernière mesure date du '
            f'{lecture.collected_at:%d/%m/%Y}. Elle ne dit rien de l’état '
            f'actuel des sauvegardes.'), {'mesure_le': str(lecture.collected_at)}

    heures = lecture.value
    detail = {'age_heures': heures}
    if heures > 168:
        return CRITIQUE, (
            f'Dernière sauvegarde il y a {heures / 24:.0f} jours.'), detail
    if heures > 48:
        return AVERTISSEMENT, (
            f'Dernière sauvegarde il y a {heures:.0f} heures.'), detail
    return OK, f'Sauvegarde datant de {heures:.0f} heure(s).', detail


def _fraicheur_des_capteurs():
    """Les capteurs affichés sont-ils récents ?

    La page des capteurs annonce « collectées toutes les 5 minutes » et
    `get_latest_sensor_readings()` ne borne PAS l'ancienneté : elle rend la
    dernière ligne, quelle que soit sa date. Un score calculé sur une mesure
    d'il y a trois semaines s'affiche donc comme l'état du moment.
    """
    from datetime import timedelta

    from .models import SensorReading

    derniere = SensorReading.objects.order_by('-collected_at').first()
    if derniere is None:
        return CRITIQUE, (
            'Aucun capteur n’a jamais été collecté : les scores de la page '
            'Santé ne reposent sur rien.'), {}

    age = timezone.now() - derniere.collected_at
    detail = {'age_minutes': round(age.total_seconds() / 60)}
    if age > timedelta(hours=6):
        return CRITIQUE, (
            f'Dernière collecte il y a {age.total_seconds() / 3600:.1f} '
            f'heures. Les scores affichés décrivent le passé.'), detail
    if age > timedelta(minutes=30):
        return AVERTISSEMENT, (
            f'Dernière collecte il y a '
            f'{age.total_seconds() / 60:.0f} minutes.'), detail
    return OK, (
        f'Capteurs collectés il y a '
        f'{age.total_seconds() / 60:.0f} minute(s).'), detail


def _hyperviseur():
    """L'hyperviseur répond-il, quand l'ERP est réglé pour l'interroger ?

    Non configuré n'est PAS un problème : c'est une fonction facultative, et
    la signaler en avertissement remplirait le rapport d'un reproche
    permanent pour une option que l'exploitant a le droit de ne pas
    employer. Configuré mais muet, en revanche, est un vrai constat — le plus
    souvent un jeton révoqué ou une adresse d'hôte qui a changé.
    """
    from .models import ReglagesProxmox

    reglages = ReglagesProxmox.courants()
    if reglages is None or not reglages.actif:
        return OK, 'Interrogation de l’hyperviseur non activée (facultatif).', {}

    from . import proxmox

    resultat = proxmox.inventaire(reglages, use_cache=False)
    if resultat.get('joignable'):
        return OK, (
            f'Hôte joint : {len(resultat["disques"])} disque(s) déclaré(s) '
            f'pour la machine {resultat.get("vmid")}.'
        ), {'disques': len(resultat['disques'])}

    return AVERTISSEMENT, (
        f'L’interrogation est activée et l’hôte ne répond pas : '
        f'{resultat.get("erreur") or "motif inconnu"}'), {}


def _reglages_de_fiabilite_celery():
    """Les quatre réglages que le score Celery note, et qui manquaient."""
    from django.conf import settings

    attendus = {
        'CELERY_TASK_ACKS_LATE': True,
        'CELERY_TASK_REJECT_ON_WORKER_LOST': True,
        'CELERY_TASK_TIME_LIMIT': None,
        'CELERY_WORKER_MAX_TASKS_PER_CHILD': None,
    }
    manquants = [cle for cle in attendus
                 if not getattr(settings, cle, None)]
    if manquants:
        return AVERTISSEMENT, (
            'Réglage(s) de fiabilité Celery absent(s) : une tâche perdue '
            'avec son worker ne sera pas rejouée.'), {'manquants': manquants}
    return OK, 'Réglages de fiabilité des tâches en place.', {}


# ── La liste, et son exécution ───────────────────────────────────────────────

def controles():
    """Tous les contrôles, dans l'ordre d'affichage du rapport."""
    return [
        Controle('verifications_django', 'Vérifications système Django',
                 _verifications_django, 'Code et schéma'),
        Controle('migrations', 'Migrations appliquées',
                 _migrations_en_attente, 'Code et schéma'),
        Controle('urls', 'Arbre des adresses', _confs_d_url, 'Code et schéma'),

        Controle('planificateur', 'Planificateur de tâches',
                 _planificateur, 'Tâches de fond'),
        Controle('courtier', 'Courtier et workers',
                 _courtier_et_workers, 'Tâches de fond'),
        Controle('fiabilite_celery', 'Réglages de fiabilité des tâches',
                 _reglages_de_fiabilite_celery, 'Tâches de fond'),

        Controle('cache', 'Cache partagé', _cache_partage, 'Services'),
        Controle('courriels', 'Envoi des courriels', _courriels, 'Services'),
        Controle('assistants', 'Assistants privilégiés',
                 _assistants_privilegies, 'Services'),
        Controle('hyperviseur', 'Hyperviseur Proxmox',
                 _hyperviseur, 'Services'),

        Controle('place_disque', 'Place disque', _place_disque, 'Données'),
        Controle('sauvegardes', 'Sauvegardes', _sauvegardes, 'Données'),
        Controle('fraicheur_capteurs', 'Fraîcheur des mesures',
                 _fraicheur_des_capteurs, 'Données'),
    ]


POIDS = {OK: 1.0, AVERTISSEMENT: 0.5, CRITIQUE: 0.0, ERREUR: 0.0}


def executer(declencheur='planifie', utilisateur=None):
    """Exécute tous les contrôles et enregistre le rapport.

    Rend l'objet ControleDeLInstallation. N'échoue pas : un contrôle qui
    lève est consigné comme « erreur » et les suivants s'exécutent.
    """
    from .models import ControleDeLInstallation

    depart = time.monotonic()
    resultats = [controle.executer() for controle in controles()]

    total = len(resultats)
    compte = {OK: 0, AVERTISSEMENT: 0, CRITIQUE: 0, ERREUR: 0}
    for resultat in resultats:
        compte[resultat['etat']] = compte.get(resultat['etat'], 0) + 1

    # Un avertissement vaut un demi-point : il décrit un risque, pas une
    # panne. Une erreur de contrôle compte comme un échec -- ne pas savoir
    # n'est pas la même chose que savoir que tout va bien.
    gagnes = sum(POIDS.get(r['etat'], 0.0) for r in resultats)
    score = round(gagnes / total * 100) if total else 0

    if compte[CRITIQUE] or compte[ERREUR]:
        etat = 'critical'
    elif compte[AVERTISSEMENT]:
        etat = 'warning'
    else:
        etat = 'ok'

    return ControleDeLInstallation.objects.create(
        duree_ms=round((time.monotonic() - depart) * 1000),
        declencheur=declencheur,
        lance_par=utilisateur,
        etat=etat,
        score=score,
        nombre_total=total,
        nombre_ok=compte[OK],
        nombre_avertissements=compte[AVERTISSEMENT],
        nombre_critiques=compte[CRITIQUE] + compte[ERREUR],
        resultats=resultats,
    )
