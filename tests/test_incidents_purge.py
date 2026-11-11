"""Six mille incidents : le dédoublonnage ne dédoublonnait rien.

LE CONSTAT

Une installation réelle portait environ 6 000 incidents. Ils n'étaient pas
6 000 pannes : l'escalade automatique de `check_and_alert` ouvrait un
incident À CHAQUE passage de la collecte, soit toutes les cinq minutes,
pour chaque capteur critique depuis plus de trente minutes.

DEUX DÉFAUTS DANS LA MÊME REQUÊTE

  1. elle cherchait `title__icontains=sensor`, donc le CODE du capteur
     (« disk_free_gb ») dans un titre qui ne porte que son LIBELLÉ humain
     (« Dégradation prolongée : Espace disque libre »). La correspondance
     était impossible ;
  2. elle filtrait sur « open » et « identified », deux statuts absents de
     INCIDENT_STATUSES, et créait ses incidents avec « open ». Une valeur
     hors choix se range sans broncher — Django ne valide les choix que
     dans `full_clean()`, que `create()` n'appelle pas — donc rien ne
     signalait l'écart.

Le même dédoublonnage existait dans apps/orion_ops, écrit à la main, et
JUSTE. Deux listes manuelles pour la même règle : elles avaient divergé, et
le prix de cette divergence est ce millier d'incidents.

Ces défauts dormaient tant que rien ne collectait les capteurs. Ils se sont
réveillés le jour où le planificateur a reçu un horaire.
"""
import pytest
from django.utils import timezone


# ── 1. La source de vérité unique ────────────────────────────────────────────

def test_les_statuts_ouverts_existent_tous_dans_les_choix():
    """La liste manuelle contenait « open » et « identified », qui ne
    figurent nulle part dans le modèle."""
    from apps.system_health.models import SystemIncident

    connus = {code for code, _ in SystemIncident.INCIDENT_STATUSES}
    inconnus = set(SystemIncident.STATUTS_OUVERTS) - connus
    assert inconnus == set(), f'statuts hors choix : {inconnus}'


def test_les_statuts_termines_ne_sont_pas_dans_les_ouverts():
    """Sinon un incident clos empêcherait d'en ouvrir un nouveau pour une
    panne qui revient."""
    from apps.system_health.models import SystemIncident

    for termine in ('resolved', 'closed'):
        assert termine not in SystemIncident.STATUTS_OUVERTS


def test_les_deux_modules_partagent_la_meme_liste():
    """C'est la recopie qui a provoqué la divergence : le code du moteur de
    règles ne doit plus porter sa propre liste."""
    from pathlib import Path

    source = Path('apps/orion_ops/services/rule_engine.py').read_text(
        encoding='utf-8')
    assert 'STATUTS_OUVERTS' in source
    assert "'investigating', 'fixing']" not in source, (
        'une liste de statuts écrite à la main subsiste')


# ── 2. Le robinet est fermé ──────────────────────────────────────────────────

def _sante_critique(capteur='disk_free_gb'):
    """Un état de santé où ce capteur est critique."""
    from apps.system_health.models import SensorReading

    lecture = SensorReading(sensor_type=capteur, value=1.0, status='critical')
    return {'critical': [capteur], 'readings': {capteur: lecture},
            'score': 10, 'status': 'critical', 'breakdown': {}}


def _snapshots_critiques(capteur, combien=6):
    """Assez d'instantanés pour déclencher l'escalade (6 × 5 min = 30 min)."""
    from datetime import timedelta

    from apps.system_health.models import HealthSnapshot

    for i in range(combien):
        instantane = HealthSnapshot.objects.create(
            global_score=10, global_status='critical',
            critical_sensors=[capteur])
        HealthSnapshot.objects.filter(pk=instantane.pk).update(
            collected_at=timezone.now() - timedelta(minutes=i * 2))


@pytest.mark.django_db
def test_une_degradation_prolongee_ouvre_un_incident():
    """Le chemin qui aboutit : l'escalade doit continuer de fonctionner.

    Sans ce test, le correctif pourrait consister à ne plus rien créer du
    tout — ce qui ferait disparaître le problème et la fonction avec.
    """
    from apps.system_health.models import SystemIncident
    from apps.system_health.services import check_and_alert

    _snapshots_critiques('disk_free_gb')
    check_and_alert([], _sante_critique('disk_free_gb'))

    incidents = SystemIncident.objects.all()
    assert incidents.count() == 1
    incident = incidents.first()
    assert incident.component == 'capteur:disk_free_gb'
    assert incident.auto_created is True


@pytest.mark.django_db
def test_le_statut_cree_fait_partie_des_choix_du_modele():
    """« open » n'existe pas. Il se rangeait quand même, et rendait les
    incidents invisibles aux filtres de la page."""
    from apps.system_health.models import SystemIncident
    from apps.system_health.services import check_and_alert

    _snapshots_critiques('disk_free_gb')
    check_and_alert([], _sante_critique('disk_free_gb'))

    incident = SystemIncident.objects.first()
    connus = {code for code, _ in SystemIncident.INCIDENT_STATUSES}
    assert incident.status in connus
    assert incident.status != 'open'


@pytest.mark.django_db
def test_dix_passages_n_ouvrent_pas_dix_incidents():
    """LE CŒUR DE LA CORRECTION.

    Dix appels valent cinquante minutes de collecte. Avant, c'étaient dix
    incidents ; sur des jours, plusieurs milliers.
    """
    from apps.system_health.models import SystemIncident
    from apps.system_health.services import check_and_alert

    _snapshots_critiques('disk_free_gb')
    for _ in range(10):
        check_and_alert(['disk_free_gb'], _sante_critique('disk_free_gb'))

    assert SystemIncident.objects.count() == 1


@pytest.mark.django_db
def test_un_incident_clos_laisse_rouvrir_pour_la_meme_panne():
    """La contrepartie : le dédoublonnage ne doit pas étouffer une panne qui
    revient après avoir été résolue."""
    from apps.system_health.models import SystemIncident
    from apps.system_health.services import check_and_alert

    _snapshots_critiques('disk_free_gb')
    check_and_alert([], _sante_critique('disk_free_gb'))
    SystemIncident.objects.update(status='closed')

    check_and_alert([], _sante_critique('disk_free_gb'))
    assert SystemIncident.objects.count() == 2


@pytest.mark.django_db
def test_deux_capteurs_distincts_ont_chacun_leur_incident():
    """Le rapprochement se fait sur le capteur, pas sur « il existe un
    incident ouvert »."""
    from apps.system_health.models import SystemIncident
    from apps.system_health.services import check_and_alert

    _snapshots_critiques('disk_free_gb')
    _snapshots_critiques('memory_usage')

    check_and_alert([], _sante_critique('disk_free_gb'))
    check_and_alert([], _sante_critique('memory_usage'))

    composants = set(
        SystemIncident.objects.values_list('component', flat=True))
    assert composants == {'capteur:disk_free_gb', 'capteur:memory_usage'}


# ── 3. La purge ──────────────────────────────────────────────────────────────

def _incidents(combien, statut='closed'):
    from datetime import timedelta

    from apps.system_health.models import SystemIncident

    crees = []
    base = timezone.now()
    for i in range(combien):
        incident = SystemIncident.objects.create(
            title=f'Incident {i}', severity='minor', status=statut,
            description='x')
        SystemIncident.objects.filter(pk=incident.pk).update(
            detected_at=base - timedelta(minutes=combien - i))
        crees.append(incident)
    return crees


def _super_admin(client, django_user_model):
    from apps.core.models import Company

    Company.objects.get_or_create(
        slug='volt-sarl', defaults={'name': 'Volt SARL'})
    utilisateur = django_user_model.objects.create_superuser(
        username='patron', password='motdepasse-test', email='p@volt.fr')
    client.force_login(utilisateur)
    return utilisateur


@pytest.mark.django_db
def test_la_purge_ne_garde_que_les_plus_recents(client, django_user_model):
    from apps.system_health.models import SystemIncident

    _super_admin(client, django_user_model)
    _incidents(50)

    reponse = client.post('/orion-admin/sante-systeme/incidents/purger/',
                          {'conserver': '20'}, follow=True)
    assert reponse.status_code == 200
    assert SystemIncident.objects.count() == 20

    # Et ce sont bien les plus RÉCENTS qui restent.
    restants = set(SystemIncident.objects.values_list('title', flat=True))
    assert 'Incident 49' in restants
    assert 'Incident 0' not in restants


@pytest.mark.django_db
def test_les_incidents_ouverts_sont_epargnes(client, django_user_model):
    """LE CHOIX IMPORTANT.

    Un incident en cours porte du travail en train de se faire. Le
    supprimer parce qu'il est vieux ferait disparaître une panne non
    résolue, et personne ne saurait qu'elle a existé.
    """
    from apps.system_health.models import SystemIncident

    _super_admin(client, django_user_model)
    _incidents(30, statut='closed')
    _incidents(5, statut='investigating')

    client.post('/orion-admin/sante-systeme/incidents/purger/',
                {'conserver': '10'})

    ouverts = SystemIncident.objects.filter(status='investigating').count()
    assert ouverts == 5, 'des incidents ouverts ont été supprimés'


@pytest.mark.django_db
def test_la_case_prevue_emporte_aussi_les_ouverts(client, django_user_model):
    """L'épargne doit rester contournable, mais délibérément."""
    from apps.system_health.models import SystemIncident

    _super_admin(client, django_user_model)
    _incidents(30, statut='investigating')

    client.post('/orion-admin/sante-systeme/incidents/purger/',
                {'conserver': '5', 'emporter_les_ouverts': 'on'})

    assert SystemIncident.objects.count() == 5


@pytest.mark.django_db
def test_un_nombre_illisible_retombe_sur_le_defaut(client,
                                                   django_user_model):
    """Un champ abîmé ne doit pas devenir « tout supprimer »."""
    from apps.system_health.models import SystemIncident

    _super_admin(client, django_user_model)
    _incidents(50)

    client.post('/orion-admin/sante-systeme/incidents/purger/',
                {'conserver': 'vingt'})

    assert SystemIncident.objects.count() == 20


@pytest.mark.django_db
def test_conserver_plus_que_le_total_ne_supprime_rien(client,
                                                      django_user_model):
    from apps.system_health.models import SystemIncident

    _super_admin(client, django_user_model)
    _incidents(10)

    client.post('/orion-admin/sante-systeme/incidents/purger/',
                {'conserver': '100'})

    assert SystemIncident.objects.count() == 10


@pytest.mark.django_db
def test_la_purge_supprime_aussi_les_fils_rattaches(client,
                                                    django_user_model):
    """La cascade est attendue, et le message de la page l'annonce."""
    from apps.system_health.models import IncidentTimeline, SystemIncident

    _super_admin(client, django_user_model)
    incidents = _incidents(30)
    for incident in incidents[:10]:
        IncidentTimeline.objects.create(
            incident=incident, event_type='detected', description='x')

    client.post('/orion-admin/sante-systeme/incidents/purger/',
                {'conserver': '20'})

    assert SystemIncident.objects.count() == 20
    # Les fils des incidents partis ne doivent pas rester orphelins.
    restants = set(SystemIncident.objects.values_list('pk', flat=True))
    for fil in IncidentTimeline.objects.all():
        assert fil.incident_id in restants


@pytest.mark.django_db
def test_la_purge_est_refusee_a_un_salarie(client, django_user_model):
    """Une suppression de masse n'est pas à la portée de tout le monde."""
    from apps.core.models import Company
    from apps.system_health.models import SystemIncident

    Company.objects.get_or_create(
        slug='volt-sarl', defaults={'name': 'Volt SARL'})
    salarie = django_user_model.objects.create_user(
        username='salarie', password='motdepasse-test', email='s@volt.fr')
    client.force_login(salarie)
    _incidents(30)

    reponse = client.post('/orion-admin/sante-systeme/incidents/purger/',
                          {'conserver': '5'})
    assert reponse.status_code == 403
    assert SystemIncident.objects.count() == 30


@pytest.mark.django_db
def test_la_purge_refuse_le_get(client, django_user_model):
    """Une suppression ne doit pas pouvoir partir d'un simple lien."""
    from apps.system_health.models import SystemIncident

    _super_admin(client, django_user_model)
    _incidents(30)

    reponse = client.get('/orion-admin/sante-systeme/incidents/purger/')
    assert reponse.status_code == 405
    assert SystemIncident.objects.count() == 30


@pytest.mark.django_db
def test_la_page_annonce_combien_partiraient(client, django_user_model):
    """Proposer « ne garder que les 20 derniers » sans dire combien
    partiraient reviendrait à faire signer un chèque en blanc."""
    _super_admin(client, django_user_model)
    _incidents(30, statut='closed')
    _incidents(5, statut='investigating')

    reponse = client.get('/orion-admin/sante-systeme/incidents/')
    assert reponse.status_code == 200
    assert reponse.context['total_incidents'] == 35
    assert reponse.context['incidents_ouverts'] == 5
    assert reponse.context['supprimables'] == 10

    contenu = reponse.content.decode()
    assert 'Purger l' in contenu
    assert 'épargnés' in contenu or 'pargn' in contenu
