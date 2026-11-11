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
    """L'assistant disque FONCTIONNE-T-IL ? Pas « les fichiers existent-ils ».

    La première version se contentait de regarder si deux fichiers étaient
    présents. C'était trop faible, et un rapport réel l'a montré : le script
    installé, sa règle sudo absente. Dans ce cas précis, `est_disponible()`
    — qui ne teste que le bit d'exécution — rend True, l'écran des disques
    croit l'assistant utilisable, appelle sudo, et reçoit un refus. Le
    symptôme n'est donc pas « pas de bouton » mais « une erreur rouge », et
    le message du contrôle décrivait la mauvaise panne.

    On exerce donc le CHEMIN RÉEL : le même appel que fait l'interface.
    Un `sudo -n` écrit une ligne dans les journaux d'authentification ;
    `est_disponible()` l'évite pour cette raison, puisqu'il tourne à chaque
    affichage de page. Ici c'est une fois par mois : le coût est nul et la
    réponse est définitive.

    Les trois situations sont distinguées, parce qu'elles n'appellent pas le
    même geste.
    """
    if os.name != 'posix':
        return OK, 'Hors Linux : sans objet sur un poste de développement.', {}

    from . import stockage_privilegie as pont

    script = pont.CHEMIN_DU_SCRIPT
    regle = '/etc/sudoers.d/orion-stockage'
    detail = {'script': os.path.exists(script), 'regle_sudo': os.path.exists(regle)}

    if not detail['script']:
        return AVERTISSEMENT, (
            f'{script} est absent : la préparation d’un disque neuf est '
            f'impossible et aucun bouton ne s’affichera. Lancez une mise à '
            f'jour depuis /orion-admin/system-updates/, qui l’installe.'
        ), detail

    if not detail['regle_sudo']:
        # Le cas constaté. On le nomme précisément : le script est là, donc
        # l'interface le croit utilisable et échoue à l'usage.
        return AVERTISSEMENT, (
            f'{regle} est absent alors que le script est installé. '
            f'L’écran des disques croira l’assistant utilisable et recevra '
            f'un refus de sudo. Une mise à jour pose cette règle ; si elle '
            f'ne revient pas, c’est que « visudo -c » la refuse et la mise à '
            f'jour l’écrit dans son journal.'
        ), detail

    # Les deux fichiers sont là : reste à savoir si sudo accepte vraiment.
    try:
        inventaire = pont.lister_les_disques()
    except pont.StockagePrivilegieIndisponible as exc:
        return AVERTISSEMENT, (
            f'L’assistant est installé mais injoignable : {exc}'), detail
    except pont.ActionPrivilegieeRefusee as exc:
        return AVERTISSEMENT, (
            f'sudo refuse l’assistant alors que la règle existe. Elle ne '
            f'correspond probablement plus à ce que le code appelle. '
            f'Détail : {exc}'), detail
    except Exception as exc:                                    # noqa: BLE001
        return AVERTISSEMENT, (
            f'L’assistant a échoué : {type(exc).__name__}: {exc}'), detail

    nombre = len(((inventaire or {}).get('disques')) or [])
    detail['disques_vus'] = nombre
    return OK, (
        f'Assistant disque opérationnel : {nombre} disque(s) inventorié(s).'
    ), detail


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
        # DEUX ÉCHECS QUI SE RESSEMBLENT ET N'APPELLENT PAS LE MÊME GESTE.
        #
        # Rien n'est configuré : le repli tente « localhost:25 », où rien
        # n'écoute sur cette appliance. L'erreur brute « Connection refused »
        # est alors exacte et inutile — elle envoie chercher une panne
        # réseau là où il manque simplement un réglage. Le geste est
        # d'aller remplir la page.
        #
        # Un serveur EST configuré et ne répond pas : là, l'erreur du
        # serveur est le renseignement principal.
        motif = f'{type(exc).__name__}: {exc}'
        if reglages is None:
            return CRITIQUE, (
                'Aucun serveur d’envoi n’est configuré : l’ERP se rabat sur '
                '« localhost », où rien n’écoute. Renseignez votre SMTP sur '
                f'/orion-admin/courriels/. Détail : {motif}'), {}
        return CRITIQUE, (
            f'Connexion au serveur de courriel impossible '
            f'({reglages.hote}:{reglages.port}) — {motif}'), {}

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


EXTENSIONS_DE_SAUVEGARDE = ('.sql', '.gz', '.zip', '.tar', '.dump', '.bak',
                            '.sql.gz', '.tar.gz')


def _fichiers_de_sauvegarde():
    """Ce qui ressemble à une sauvegarde dans BACKUP_DIR. (nombre, plus récent)

    On regarde le DISQUE, pas la base. Voir `_sauvegardes` pour pourquoi les
    deux sont nécessaires.
    """
    from django.conf import settings

    dossier = getattr(settings, 'BACKUP_DIR', None)
    if dossier is None or not os.path.isdir(str(dossier)):
        return 0, None, str(dossier or '')

    nombre, plus_recent = 0, None
    try:
        for racine, _dossiers, fichiers in os.walk(str(dossier)):
            for nom in fichiers:
                if not nom.lower().endswith(EXTENSIONS_DE_SAUVEGARDE):
                    continue
                chemin = os.path.join(racine, nom)
                try:
                    date = os.path.getmtime(chemin)
                except OSError:
                    continue
                nombre += 1
                if plus_recent is None or date > plus_recent:
                    plus_recent = date
    except OSError:
        return 0, None, str(dossier)

    return nombre, plus_recent, str(dossier)


def _sauvegardes():
    """Y a-t-il une sauvegarde récente, et l'ERP le sait-il ?

    DEUX QUESTIONS DIFFÉRENTES, et c'est tout le sujet d'un constat qu'on a
    eu sous les yeux : « il y a des sauvegardes sur la VM » et « l'ERP
    signale une erreur » peuvent être vrais EN MÊME TEMPS, sans que l'un
    contredise l'autre.

    Le capteur `backup_age_hours` lit la table BackupJob, c'est-à-dire ce
    que l'ERP a lui-même produit et enregistré. Il ne regarde AUCUN fichier.
    Des archives déposées par un script, par le provisionnement, par un
    `mysqldump` à la main ou par une sauvegarde Proxmox n'y figurent pas :
    l'ERP les ignore totalement, et ne peut donc ni en vérifier l'intégrité,
    ni les restaurer, ni dire ce qu'elles contiennent.

    Ce contrôle regarde les deux et NOMME L'ÉCART, au lieu de rendre une
    erreur que l'exploitant sait être fausse en regardant son disque.

    Il interroge BackupJob directement plutôt que le capteur : pour une
    vérification mensuelle, le coût est nul, et cela évite de dépendre d'une
    collecte qui pourrait ne pas avoir tourné.
    """
    # `datetime.timezone` et non `django.utils.timezone` : le second expose
    # bien un `utc`, mais déprécié depuis Django 4.2 et retiré en 5.0. Le
    # premier est celui de la bibliothèque standard, et ne bougera pas.
    from datetime import datetime, timezone as fuseau

    nombre_fichiers, plus_recent, dossier = _fichiers_de_sauvegarde()
    detail = {'fichiers_sur_disque': nombre_fichiers, 'dossier': dossier}

    try:
        from apps.backups.models import BackupJob
        travail = (BackupJob.objects
                   .filter(status='success', finished_at__isnull=False)
                   .order_by('-finished_at')
                   .first())
    except Exception as exc:                                    # noqa: BLE001
        return ERREUR, f'Table des sauvegardes illisible : {exc}', detail

    if plus_recent is not None:
        age_fichier = (timezone.now()
                       - datetime.fromtimestamp(plus_recent, tz=fuseau.utc))
        detail['fichier_le_plus_recent_jours'] = round(age_fichier.days)

    if travail is None:
        if nombre_fichiers:
            # LE CAS CONSTATÉ. Des fichiers existent, l'ERP n'en a fait
            # aucun. Dire « aucune sauvegarde » serait faux et ferait perdre
            # confiance dans tout le rapport.
            return AVERTISSEMENT, (
                f'{nombre_fichiers} fichier(s) de sauvegarde sont présents '
                f'dans {dossier}, mais AUCUN n’a été produit par l’ERP : '
                f'il ne peut ni les vérifier, ni les restaurer depuis le '
                f'Centre sauvegardes. Lancez-en une depuis l’ERP pour qu’il '
                f'en ait une qu’il maîtrise.'), detail
        return CRITIQUE, (
            f'Aucune sauvegarde : ni travail enregistré par l’ERP, ni '
            f'fichier dans {dossier}.'), detail

    age = timezone.now() - travail.finished_at
    heures = age.total_seconds() / 3600
    detail['age_heures'] = round(heures, 1)
    detail['derniere'] = travail.name

    if heures > 168:
        return CRITIQUE, (
            f'La dernière sauvegarde faite par l’ERP date d’il y a '
            f'{age.days} jours ({travail.name}).'), detail
    if heures > 48:
        return AVERTISSEMENT, (
            f'La dernière sauvegarde faite par l’ERP date d’il y a '
            f'{heures:.0f} heures ({travail.name}).'), detail
    return OK, (
        f'Sauvegarde de l’ERP datant de {heures:.0f} heure(s) '
        f'({travail.name}) ; {nombre_fichiers} fichier(s) dans '
        f'{dossier}.'), detail


def _planification_des_sauvegardes():
    """Une planification configurée est-elle réellement déclenchée ?

    `run_scheduled_backup` existe, `BackupSchedule` existe, et RIEN
    n'appelait la première — vérifié sur tout le dépôt. Une planification
    saisie dans le Centre sauvegardes ne partait donc jamais, sans que rien
    ne le signale : l'écran affichait une prochaine exécution qui
    n'arrivait pas.
    """
    from datetime import timedelta

    try:
        from apps.backups.models import BackupSchedule
        planifications = list(BackupSchedule.objects.filter(is_active=True))
    except Exception as exc:                                    # noqa: BLE001
        return ERREUR, f'Planifications illisibles : {exc}', {}

    if not planifications:
        return OK, (
            'Aucune sauvegarde planifiée (facultatif). Le Centre '
            'sauvegardes permet d’en créer une.'), {}

    jamais = [p for p in planifications if p.last_run_at is None]
    anciennes = [p for p in planifications
                 if p.last_run_at is not None
                 and p.last_run_at < timezone.now() - timedelta(days=2)]
    detail = {'total': len(planifications), 'jamais_executees': len(jamais)}

    if len(jamais) == len(planifications):
        return AVERTISSEMENT, (
            f'{len(planifications)} planification(s) active(s), aucune n’a '
            f'jamais tourné. Normal juste après leur création ; anormal '
            f'au-delà de leur première échéance.'), detail
    if anciennes:
        return AVERTISSEMENT, (
            f'{len(anciennes)} planification(s) n’ont pas tourné depuis plus '
            f'de deux jours.'), detail
    return OK, (
        f'{len(planifications)} planification(s) active(s), toutes '
        f'exécutées récemment.'), detail


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
        Controle('planification_sauvegardes', 'Sauvegardes planifiées',
                 _planification_des_sauvegardes, 'Données'),
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
