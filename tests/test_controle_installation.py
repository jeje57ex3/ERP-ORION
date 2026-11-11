"""Le planificateur avait un horaire vide, et le score Celery le disait.

LE 80 SUR 100, EXPLIQUÉ PAR L'ARITHMÉTIQUE

`compute_celery_score` note dix dimensions. Deux étaient perdues d'avance :

  * « Celery Beat fonctionnel » valait 10 points, plus 5 de pénalité quand
    il échoue — soit 15. `_check_celery_beat()` rend False dès qu'aucune
    tâche périodique n'est active, et il n'y en avait AUCUNE : le
    planificateur lit ses horaires en base (DatabaseScheduler), aucun
    CELERY_BEAT_SCHEDULE n'existe dans les réglages, et le seul moyen de
    créer ces lignes était `manage.py setup_orion_ops`, une commande que ni
    le provisionnement ni la mise à jour ne lancent ;

  * « Retries configurés » valait 5 points répartis sur quatre réglages
    (ACKS_LATE, REJECT_ON_WORKER_LOST, TIME_LIMIT,
    WORKER_MAX_TASKS_PER_CHILD). Les quatre étaient absents de base.py.

15 + 5 = 20. 100 − 20 = 80.

CE QUE LE SCORE CACHAIT, ET QUI COMPTE PLUS

Un planificateur vide ne perd pas seulement des points : il n'exécute rien.
`system_health.collect_all_sensors` annonce « Planifié toutes les 5 minutes
via Celery Beat » et n'était appelée de nulle part. La page des capteurs
affiche « Métriques temps-réel collectées toutes les 5 minutes », et
`get_latest_sensor_readings()` ne borne pas l'ancienneté : elle rend la
dernière ligne quelle que soit sa date. Tous les scores de santé pouvaient
donc décrire un état vieux de plusieurs semaines.
"""
import pytest
from django.test import override_settings


# ── 1. Les quatre réglages de fiabilité ──────────────────────────────────────

def test_les_quatre_reglages_de_fiabilite_sont_la():
    """Ils valaient 0 sur 5 au score, et surtout : une tâche perdue avec son
    worker était perdue pour de bon."""
    from django.conf import settings

    assert settings.CELERY_TASK_ACKS_LATE is True
    assert settings.CELERY_TASK_REJECT_ON_WORKER_LOST is True
    assert settings.CELERY_TASK_TIME_LIMIT
    assert settings.CELERY_WORKER_MAX_TASKS_PER_CHILD


def test_le_score_accorde_les_cinq_points_de_fiabilite():
    from apps.system_health.services import _check_celery_retry_config
    assert _check_celery_retry_config() == 5


def test_la_limite_de_temps_ne_tue_pas_une_copie_de_plusieurs_heures():
    """Le piège de ce réglage.

    Une heure serait le réflexe, et tuerait `copier_puis_basculer` au milieu
    d'une copie de plusieurs téraoctets — exactement quand une interruption
    coûte le plus cher. Une limite n'est là que pour arrêter ce qui est
    vraiment bloqué.
    """
    from django.conf import settings
    assert settings.CELERY_TASK_TIME_LIMIT >= 43200, (
        'une limite trop courte interrompt une copie légitime')


# ── 2. Le planificateur a enfin un horaire ───────────────────────────────────

@pytest.mark.django_db
def test_la_migration_cree_les_trois_horaires():
    """Créés par une MIGRATION et non par une commande en terminal.

    C'est le point : une commande que personne ne lance ne planifie rien.
    """
    from django_celery_beat.models import PeriodicTask

    taches = {t.task for t in PeriodicTask.objects.filter(enabled=True)}
    assert 'system_health.collect_all_sensors' in taches
    assert 'system_health.purge_old_sensor_readings' in taches
    assert 'system_health.controler_l_installation' in taches


@pytest.mark.django_db
def test_la_collecte_des_capteurs_tourne_bien_toutes_les_cinq_minutes():
    """La docstring de la tâche et la page des capteurs l'annoncent toutes
    les deux. L'horaire doit correspondre à ce qui est écrit."""
    from django_celery_beat.models import PeriodicTask

    tache = PeriodicTask.objects.get(task='system_health.collect_all_sensors')
    assert tache.interval is not None
    assert tache.interval.every == 5
    assert tache.interval.period == 'minutes'


@pytest.mark.django_db
def test_beat_n_est_plus_declare_absent():
    """`_check_celery_beat` rendait False faute de tâche. C'était les 15
    points manquants."""
    from apps.system_health.services import _check_celery_beat

    ok, detail = _check_celery_beat()
    assert ok is True, detail
    assert detail['total_periodic'] >= 3


@pytest.mark.django_db
def test_la_migration_ne_cree_pas_de_doublon_si_rejouee():
    """Idempotence : une migration rejouée ne doit pas doubler l'horaire."""
    from importlib import import_module

    from django.apps import apps as registre
    from django_celery_beat.models import PeriodicTask

    avant = PeriodicTask.objects.count()
    # On rejoue la fonction de la migration avec le registre réel. Le nom du
    # module commence par un chiffre : seul import_module sait l'importer.
    module = import_module(
        'apps.system_health.migrations.0007_planifier_les_taches')
    module.planifier(registre, None)
    assert PeriodicTask.objects.count() == avant


# ── 3. Le contrôle de l'installation ─────────────────────────────────────────

@pytest.mark.django_db
def test_le_controle_s_execute_entierement_et_enregistre_un_rapport():
    from apps.system_health import controle_installation
    from apps.system_health.models import ControleDeLInstallation

    controle = controle_installation.executer(declencheur='manuel')

    assert isinstance(controle, ControleDeLInstallation)
    assert controle.nombre_total == len(controle_installation.controles())
    assert len(controle.resultats) == controle.nombre_total
    assert 0 <= controle.score <= 100
    assert controle.etat in ('ok', 'warning', 'critical')
    # Chaque résultat doit être lisible par un humain, pas seulement par du
    # code : un rapport sans phrase n'aide personne.
    for resultat in controle.resultats:
        assert resultat['message'], resultat
        assert resultat['libelle']
        assert resultat['famille']


@pytest.mark.django_db
def test_un_controle_qui_leve_ne_fait_pas_tomber_les_autres():
    """LA RÈGLE CENTRALE de ce module.

    Un contrôle mensuel qui s'arrête au premier incident ne vaut rien :
    c'est précisément quand quelque chose va mal qu'on a besoin du reste du
    rapport.
    """
    from apps.system_health import controle_installation

    def _explose():
        raise RuntimeError('panne simulée')

    controle = controle_installation.Controle(
        'essai', 'Contrôle qui explose', _explose)
    resultat = controle.executer()

    assert resultat['etat'] == 'erreur'
    assert 'panne simulée' in resultat['message']
    assert 'RuntimeError' in resultat['message']


@pytest.mark.django_db
def test_ne_pas_savoir_ne_compte_pas_comme_tout_va_bien():
    """Un contrôle en erreur pèse zéro, comme un contrôle critique.

    Le défaut inverse existe ailleurs dans ce dépôt : un statut « unknown »
    noté 50 sur 100, qui fait passer « je n'ai pas pu mesurer » pour un
    demi-succès.
    """
    from apps.system_health import controle_installation as ci

    assert ci.POIDS[ci.ERREUR] == 0.0
    assert ci.POIDS[ci.CRITIQUE] == 0.0
    assert ci.POIDS[ci.AVERTISSEMENT] == 0.5
    assert ci.POIDS[ci.OK] == 1.0


@pytest.mark.django_db
def test_les_migrations_en_attente_sont_vues_comme_critiques():
    """Le défaut le plus fréquent après une mise à jour interrompue : le
    code attend une colonne que la base n'a pas."""
    from apps.system_health.controle_installation import _migrations_en_attente

    etat, message, _detail = _migrations_en_attente()
    # Dans une base de test, tout est appliqué.
    assert etat == 'ok', message


@pytest.mark.django_db
def test_le_planificateur_vide_est_signale_comme_critique():
    """Le cas réel de cette installation avant correction."""
    from django_celery_beat.models import PeriodicTask

    from apps.system_health.controle_installation import _planificateur

    PeriodicTask.objects.all().update(enabled=False)
    etat, message, _ = _planificateur()

    assert etat == 'critical'
    assert 'vide' in message.lower()


@pytest.mark.django_db
def test_le_planificateur_garni_mais_jamais_execute_avertit_sans_alarmer():
    """Juste après une mise à jour, aucune tâche n'a encore tourné. C'est
    normal, et ce n'est pas « tout va bien » non plus."""
    from apps.system_health.controle_installation import _planificateur

    etat, message, _ = _planificateur()
    assert etat == 'warning', message
    assert 'tourné' in message or 'tourne' in message


@pytest.mark.django_db
def test_l_absence_totale_de_capteur_est_critique():
    """Les scores de la page Santé reposeraient alors sur rien."""
    from apps.system_health.controle_installation import _fraicheur_des_capteurs

    etat, message, _ = _fraicheur_des_capteurs()
    assert etat == 'critical'
    assert 'jamais' in message.lower()


@pytest.mark.django_db
def test_un_capteur_ancien_n_est_pas_presente_comme_l_etat_du_moment():
    """`get_latest_sensor_readings()` ne borne pas l'ancienneté : elle rend
    la dernière ligne quelle que soit sa date. Ce contrôle est le garde-fou.
    """
    from datetime import timedelta

    from django.utils import timezone

    from apps.system_health.controle_installation import _fraicheur_des_capteurs
    from apps.system_health.models import SensorReading

    lecture = SensorReading.objects.create(
        sensor_type='cpu_usage', value=12.0, status='ok')
    SensorReading.objects.filter(pk=lecture.pk).update(
        collected_at=timezone.now() - timedelta(days=20))

    etat, message, detail = _fraicheur_des_capteurs()
    assert etat == 'critical', message
    assert detail['age_minutes'] > 1000


@pytest.mark.django_db
@override_settings(
    CACHES={'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}})
def test_un_cache_par_processus_est_signale():
    """Avec trois workers gunicorn, chacun a le sien."""
    from apps.system_health.controle_installation import _cache_partage

    etat, message, _ = _cache_partage()
    assert etat == 'warning'
    assert 'processus' in message.lower()


# ── 4. Les pages ─────────────────────────────────────────────────────────────

def _super_admin(client, django_user_model):
    from apps.core.models import Company

    Company.objects.get_or_create(
        slug='volt-sarl', defaults={'name': 'Volt SARL'})
    utilisateur = django_user_model.objects.create_superuser(
        username='patron', password='motdepasse-test', email='p@volt.fr')
    client.force_login(utilisateur)
    return utilisateur


@pytest.mark.django_db
def test_la_page_de_controle_s_affiche(client, django_user_model):
    _super_admin(client, django_user_model)

    reponse = client.get('/orion-admin/sante-systeme/controle/')
    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert 'Contrôle de l' in contenu
    # La page doit expliquer pourquoi ce n'est pas la suite de tests : c'est
    # la question posée, et la réponse doit rester lisible sur l'écran.
    assert 'pytest' in contenu


@pytest.mark.django_db
def test_lancer_un_controle_depuis_la_page(client, django_user_model):
    """Sans ligne de commande : c'est la règle de cet ERP."""
    from apps.system_health.models import ControleDeLInstallation

    utilisateur = _super_admin(client, django_user_model)

    reponse = client.post(
        '/orion-admin/sante-systeme/controle/lancer/', follow=True)
    assert reponse.status_code == 200

    controle = ControleDeLInstallation.objects.first()
    assert controle is not None
    assert controle.declencheur == 'manuel'
    assert controle.lance_par == utilisateur
    assert controle.nombre_total > 0


@pytest.mark.django_db
def test_la_page_de_controle_est_refusee_a_un_salarie(
        client, django_user_model):
    from apps.core.models import Company

    Company.objects.get_or_create(
        slug='volt-sarl', defaults={'name': 'Volt SARL'})
    salarie = django_user_model.objects.create_user(
        username='salarie', password='motdepasse-test', email='s@volt.fr')
    client.force_login(salarie)

    reponse = client.get('/orion-admin/sante-systeme/controle/')
    assert reponse.status_code == 403


@pytest.mark.django_db
def test_la_tache_planifiee_rend_un_resume():
    from apps.system_health.tasks import controler_l_installation

    resume = controler_l_installation()
    assert set(resume) == {'score', 'etat', 'critiques', 'avertissements'}
    assert 0 <= resume['score'] <= 100


# ── 5. L'écran des disques explique l'étape qu'il ne peut pas faire ──────────

@pytest.mark.django_db
def test_sans_disque_la_page_nomme_l_etape_hyperviseur(
        client, django_user_model):
    """« Aucun disque détecté » était exact et ne menait nulle part.

    Ajouter un disque à la machine virtuelle est une action de
    l'hyperviseur : l'ERP tourne DANS la VM et ne peut pas la faire. C'est
    pourquoi aucun bouton n'apparaissait — l'assistant ne refusait rien, il
    n'avait rien à proposer. L'écran doit le dire.
    """
    _super_admin(client, django_user_model)

    reponse = client.get('/orion-admin/sante-systeme/disques/')
    assert reponse.status_code == 200
    contenu = reponse.content.decode()

    # TROIS SITUATIONS, et la première version de ce test n'en prévoyait que
    # deux. Sur un poste Windows, `est_disponible()` rend False, la page
    # prend la branche « assistant absent » et n'atteignait JAMAIS
    # l'explication. C'est aussi vrai sur un serveur où l'assistant n'est pas
    # encore installé — et là le défaut compte : installer l'assistant ne
    # débloque rien s'il n'y a aucun disque branché. Les deux prérequis sont
    # indépendants, donc l'explication est affichée dans les deux cas.
    assert 'hyperviseur' in contenu, (
        'la page ne nomme pas l’étape qu’elle ne peut pas faire')
    assert 'qm set 100' in contenu, 'la commande exacte manque'
    assert 'Actualiser la détection' in contenu


@pytest.mark.django_db
def test_l_assistant_absent_renvoie_vers_la_mise_a_jour(monkeypatch):
    """Le message disait que l'assistant manquait, sans dire qu'une mise à
    jour l'installe — d'où la conclusion qu'il fallait passer par SSH."""
    from apps.system_health import views

    monkeypatch.setattr(
        'apps.system_health.stockage_privilegie.est_disponible',
        lambda: False)

    contexte = views._contexte_de_stockage()
    assert contexte['assistant_disponible'] is False
    assert 'system-updates' in contexte['erreur_assistant']


# ── 6. L'assistant disque : trois états, trois gestes ────────────────────────
#
# Un rapport réel l'a montré : le script installé, sa règle sudo absente.
# La première version du contrôle ne regardait que la présence de fichiers et
# annonçait « les boutons ne s'afficheront pas ». C'était la mauvaise panne :
# `est_disponible()` ne teste que le bit d'exécution, donc l'écran croit
# l'assistant utilisable, appelle sudo et reçoit un refus — une erreur rouge,
# pas une absence de bouton.

@pytest.mark.django_db
def test_le_script_absent_renvoie_vers_la_mise_a_jour(monkeypatch):
    import os as _os

    from apps.system_health import controle_installation as ci

    monkeypatch.setattr(ci.os, 'name', 'posix')
    monkeypatch.setattr(ci.os.path, 'exists', lambda chemin: False)

    etat, message, detail = ci._assistants_privilegies()
    assert etat == ci.AVERTISSEMENT
    assert 'system-updates' in message
    assert detail['script'] is False


@pytest.mark.django_db
def test_la_regle_sudo_absente_est_nommee_precisement(monkeypatch):
    """LE CAS CONSTATÉ.

    Le script est là, la règle non. Le message doit dire que l'interface
    recevra un refus de sudo — et non qu'aucun bouton ne s'affichera.
    """
    from apps.system_health import controle_installation as ci

    monkeypatch.setattr(ci.os, 'name', 'posix')
    monkeypatch.setattr(
        ci.os.path, 'exists',
        lambda chemin: 'sudoers.d' not in chemin)

    etat, message, detail = ci._assistants_privilegies()
    assert etat == ci.AVERTISSEMENT
    assert detail['script'] is True
    assert detail['regle_sudo'] is False
    assert 'sudo' in message.lower()
    assert 'visudo' in message


@pytest.mark.django_db
def test_sudo_qui_refuse_est_distingue_d_un_fichier_absent(monkeypatch):
    """Les deux fichiers sont là et sudo refuse quand même : la règle ne
    correspond plus à ce que le code appelle."""
    from apps.system_health import controle_installation as ci
    from apps.system_health import stockage_privilegie as pont

    monkeypatch.setattr(ci.os, 'name', 'posix')
    monkeypatch.setattr(ci.os.path, 'exists', lambda chemin: True)

    def _refuse():
        raise pont.ActionPrivilegieeRefusee('sudo: a password is required')

    monkeypatch.setattr(pont, 'lister_les_disques', _refuse)

    etat, message, _ = ci._assistants_privilegies()
    assert etat == ci.AVERTISSEMENT
    assert 'refuse' in message.lower()
    assert 'password' in message


@pytest.mark.django_db
def test_un_assistant_operationnel_compte_les_disques(monkeypatch):
    """Le chemin qui aboutit. Sans lui, les trois tests précédents
    pourraient passer grâce à un contrôle qui échoue toujours."""
    from apps.system_health import controle_installation as ci
    from apps.system_health import stockage_privilegie as pont

    monkeypatch.setattr(ci.os, 'name', 'posix')
    monkeypatch.setattr(ci.os.path, 'exists', lambda chemin: True)
    monkeypatch.setattr(
        pont, 'lister_les_disques',
        lambda: {'disques': [{'peripherique': '/dev/sda'},
                             {'peripherique': '/dev/sdb'}]})

    etat, message, detail = ci._assistants_privilegies()
    assert etat == ci.OK
    assert detail['disques_vus'] == 2
    assert '2 disque' in message


@pytest.mark.django_db
@override_settings(
    ORION_MAIL_BACKEND_DE_REPLI='django.core.mail.backends.smtp.EmailBackend',
    EMAIL_HOST='localhost')
def test_sans_smtp_configure_le_constat_renvoie_a_la_page(monkeypatch):
    """« Connection refused » est exact et inutile quand rien n'est réglé.

    C'est le constat réel d'une appliance neuve : aucun serveur configuré,
    l'ERP se rabat sur « localhost:25 » où rien n'écoute, et le message brut
    envoie chercher une panne réseau là où il manque un réglage.

    Le scénario est MONTÉ, et non deviné : en environnement de test le repli
    est le backend mémoire, donc le contrôle s'arrêterait en avertissement
    avant même d'essayer une connexion. Une première version de ce test
    branchait sur l'état obtenu et ne vérifiait donc rien.
    """
    from apps.system_health import controle_installation as ci

    class _ConnexionQuiRefuse:
        def open(self):
            raise ConnectionRefusedError('[Errno 111] Connection refused')

        def close(self):
            pass

    monkeypatch.setattr(
        'django.core.mail.get_connection',
        lambda *a, **k: _ConnexionQuiRefuse())

    etat, message, _ = ci._courriels()

    assert etat == ci.CRITIQUE
    assert 'orion-admin/courriels' in message
    assert 'localhost' in message
    # L'erreur brute reste présente : elle sert quand la cause est ailleurs.
    assert 'Connection refused' in message
