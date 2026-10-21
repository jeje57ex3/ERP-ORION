"""Prévenir avant, informer pendant : annonce et pages de maintenance.

**Prévenir et bloquer sont deux choses distinctes, et c'est l'idée
centrale.** Une annonce dont l'heure n'est pas venue affiche un bandeau et
n'interrompt rien — on a le temps d'enregistrer son devis. Le blocage, lui,
ne vient que du fichier verrou. Confondre les deux obligerait à couper le
service pour pouvoir prévenir.

**Deux mécanismes, pas un.** Le verrou est un FICHIER : il fonctionne
quand la base est en cours de migration, c'est-à-dire précisément pendant
une mise à jour. L'annonce est en base : elle porte le motif et l'heure.
Fusionner les deux rendrait la page de maintenance dépendante de ce qui est
justement en train d'être modifié — d'où les tests qui vérifient qu'elle
s'affiche quand même.

**Et pendant un redémarrage, Django est ARRÊTÉ.** Il ne peut servir
aucune page, pas même la sienne. C'est nginx qui répond, avec un fichier
statique : les tests vérifient que la configuration le prévoit, et que ce
fichier se recharge tout seul.
"""

import re
from pathlib import Path

import pytest
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db

RACINE = Path(__file__).resolve().parent.parent


# ── Terrain ─────────────────────────────────────────────────────────────────

@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Dupont SA', slug='dupont-sa')


@pytest.fixture(autouse=True)
def verrou_propre():
    """Le verrou est un fichier : il survivrait d'un test à l'autre."""
    from apps.core.maintenance import disable_maintenance_mode

    disable_maintenance_mode()
    yield
    disable_maintenance_mode()


@pytest.fixture
def admin(client, entreprise, django_user_model):
    user = django_user_model.objects.create_superuser(
        username='patron', password='motdepasse-test',
        email='patron@example.test')
    user.profile.companies.add(entreprise)
    user.profile.current_company = entreprise
    user.profile.save()
    client.force_login(user)
    return client


@pytest.fixture
def employe(client, entreprise, django_user_model):
    user = django_user_model.objects.create_user(
        username='employe', password='motdepasse-test')
    user.profile.companies.add(entreprise)
    user.profile.current_company = entreprise
    user.profile.save()
    client.force_login(user)
    return client


def _annonce(**extra):
    from apps.core.models import MaintenanceAnnonce

    donnees = {
        'motif': 'mise_a_jour',
        'debut_prevu': timezone.now() + timezone.timedelta(hours=2),
        'duree_minutes': 20,
    }
    donnees.update(extra)
    return MaintenanceAnnonce.objects.create(**donnees)


# ═══ L'ANNONCE : PRÉVENIR SANS BLOQUER ══════════════════════════════════════

def test_une_annonce_a_venir_ne_bloque_personne(employe, entreprise):
    """Elle prévient pour qu'on enregistre son travail, pas pour couper."""
    _annonce()

    reponse = employe.get(reverse('accounts:profile'))
    assert reponse.status_code != 503


def test_le_bandeau_s_affiche_avant_l_heure(employe, entreprise):
    _annonce(duree_minutes=20)

    corps = employe.get(reverse('accounts:profile')).content.decode()
    assert 'Mise à jour' in corps
    assert 'Enregistrez votre travail' in corps


def test_le_bandeau_change_quand_l_heure_est_passee(employe, entreprise):
    """Doré avant, rouge pendant : la même information ne se lit pas de la
    même façon selon qu'on a encore le temps ou non."""
    _annonce(debut_prevu=timezone.now() - timezone.timedelta(minutes=2))

    corps = employe.get(reverse('accounts:profile')).content.decode()
    assert 'retour prévu vers' in corps
    assert 'Enregistrez votre travail' not in corps


def test_le_message_libre_apparait(employe, entreprise):
    _annonce(message='Passage en version 2.4, pensez à vider votre cache.')

    corps = employe.get(reverse('accounts:profile')).content.decode()
    assert 'version 2.4' in corps


def test_une_annonce_inactive_n_affiche_rien(employe, entreprise):
    _annonce(active=False)

    corps = employe.get(reverse('accounts:profile')).content.decode()
    assert 'Enregistrez votre travail' not in corps


def test_une_annonce_lointaine_n_affiche_rien(employe, entreprise):
    """Prévenir trois semaines à l'avance, c'est un bandeau qu'on
    n'apprend plus à voir."""
    _annonce(debut_prevu=timezone.now() + timezone.timedelta(days=30))

    corps = employe.get(reverse('accounts:profile')).content.decode()
    assert 'Enregistrez votre travail' not in corps


def test_courante_ne_leve_jamais(monkeypatch):
    """Appelée sur CHAQUE page : une table absente entre le déploiement du
    code et la migration ne doit pas rendre l'ERP inaccessible."""
    from apps.core.models import MaintenanceAnnonce

    def tombe(*args, **kwargs):
        raise RuntimeError('table absente')

    monkeypatch.setattr(MaintenanceAnnonce.objects, 'filter', tombe)
    assert MaintenanceAnnonce.courante() is None


def test_la_fin_prevue_se_calcule():
    from apps.core.models import MaintenanceAnnonce

    debut = timezone.now()
    annonce = MaintenanceAnnonce(debut_prevu=debut, duree_minutes=45)
    assert annonce.fin_prevue == debut + timezone.timedelta(minutes=45)


# ═══ LA PAGE DE MAINTENANCE ═════════════════════════════════════════════════

def test_le_verrou_bloque_un_employe(employe, entreprise):
    from apps.core.maintenance import enable_maintenance_mode

    enable_maintenance_mode()
    reponse = employe.get(reverse('accounts:profile'))

    assert reponse.status_code == 503
    assert 'Maintenance' in reponse.content.decode()


def test_le_code_est_503_et_non_200(employe, entreprise):
    """503 est ce que comprennent les navigateurs, les moteurs et les
    sondes : « indisponible, réessayez ». Un 200 ferait croire au service
    rendu."""
    from apps.core.maintenance import enable_maintenance_mode

    enable_maintenance_mode()
    assert employe.get(reverse('accounts:profile')).status_code == 503


def test_la_page_de_maintenance_se_recharge_seule(employe, entreprise):
    """Sans cela, l'utilisateur rafraîchit à l'aveugle — ou abandonne alors
    que le service est revenu depuis deux minutes."""
    from apps.core.maintenance import enable_maintenance_mode

    enable_maintenance_mode()
    corps = employe.get(reverse('accounts:profile')).content.decode()
    assert 'http-equiv="refresh"' in corps


def test_la_page_dit_le_motif_et_l_heure_de_retour(employe, entreprise):
    """« Maintenance programmée » quoi qu'il arrive n'apprend rien."""
    from apps.core.maintenance import enable_maintenance_mode

    _annonce(motif='mise_a_jour',
             debut_prevu=timezone.now() - timezone.timedelta(minutes=1),
             duree_minutes=15)
    enable_maintenance_mode()

    corps = employe.get(reverse('accounts:profile')).content.decode()
    assert 'Mise à jour en cours' in corps
    assert 'Retour prévu' in corps


def test_la_page_rassure_sur_les_donnees(employe, entreprise):
    from apps.core.maintenance import enable_maintenance_mode

    enable_maintenance_mode()
    corps = employe.get(reverse('accounts:profile')).content.decode()
    assert 'données' in corps


def test_la_page_s_affiche_meme_sans_la_table_des_annonces(employe,
                                                           entreprise,
                                                           monkeypatch):
    """Le cas qui compte : pendant une migration, la base peut refuser.
    Une panne DANS la page de panne est le pire moment pour découvrir une
    exception."""
    from apps.core import middleware
    from apps.core.maintenance import enable_maintenance_mode
    from apps.core.models import MaintenanceAnnonce

    def tombe():
        raise RuntimeError('base indisponible')

    monkeypatch.setattr(MaintenanceAnnonce, 'courante', staticmethod(tombe))
    enable_maintenance_mode()

    reponse = employe.get(reverse('accounts:profile'))
    assert reponse.status_code == 503
    assert 'Maintenance' in reponse.content.decode()


def test_la_page_s_affiche_meme_sans_le_gabarit(monkeypatch):
    """Déploiement partiel : le gabarit peut manquer. Le repli est en dur
    dans le code, et doit rester lisible."""
    from apps.core import middleware

    def tombe(*args, **kwargs):
        raise RuntimeError('gabarit absent')

    monkeypatch.setattr(
        'django.template.loader.render_to_string', tombe)

    reponse = middleware._page_de_maintenance()
    assert reponse.status_code == 503
    corps = reponse.content.decode()
    assert 'Maintenance' in corps
    assert 'refresh' in corps


def test_un_super_admin_traverse_la_maintenance(admin, entreprise):
    """Sinon on se verrouille dehors : c'est lui qui doit lever le verrou."""
    from apps.core.maintenance import enable_maintenance_mode

    enable_maintenance_mode()
    assert admin.get(reverse('accounts:profile')).status_code != 503


def test_la_connexion_reste_accessible(client, entreprise):
    from apps.core.maintenance import enable_maintenance_mode

    enable_maintenance_mode()
    assert client.get(reverse('accounts:login')).status_code == 200


# ═══ LEVER LE VERROU CLÔT L'ANNONCE ════════════════════════════════════════

def test_lever_le_verrou_clot_l_annonce():
    """Un bandeau rouge qui survit au retour du service fait douter de
    l'état réel du serveur, et l'on apprend à l'ignorer. Corrigé à la
    SOURCE — il y a plusieurs appelants, les corriger un par un c'est en
    oublier un."""
    from apps.core.maintenance import (
        disable_maintenance_mode, enable_maintenance_mode,
    )
    from apps.core.models import MaintenanceAnnonce

    enable_maintenance_mode()
    _annonce(debut_prevu=timezone.now())
    assert MaintenanceAnnonce.objects.filter(active=True).exists()

    disable_maintenance_mode()

    assert not MaintenanceAnnonce.objects.filter(active=True).exists()


def test_annoncer_remplace_l_annonce_precedente():
    """Deux bandeaux simultanés diraient deux choses différentes du même
    événement."""
    from apps.core.maintenance import annoncer
    from apps.core.models import MaintenanceAnnonce

    annoncer('mise_a_jour', duree_minutes=10)
    annoncer('redemarrage', duree_minutes=5)

    actives = MaintenanceAnnonce.objects.filter(active=True)
    assert actives.count() == 1
    assert actives.first().motif == 'redemarrage'


def test_annoncer_ne_leve_jamais(monkeypatch):
    """Une annonce est un confort, un redémarrage est une nécessité :
    l'action doit se faire même si l'annonce échoue."""
    from apps.core import maintenance
    from apps.core.models import MaintenanceAnnonce

    def tombe(*args, **kwargs):
        raise RuntimeError('base indisponible')

    monkeypatch.setattr(MaintenanceAnnonce.objects, 'filter', tombe)
    assert maintenance.annoncer('mise_a_jour') is None


def test_clore_ne_leve_jamais(monkeypatch):
    from apps.core import maintenance
    from apps.core.models import MaintenanceAnnonce

    def tombe(*args, **kwargs):
        raise RuntimeError('base indisponible')

    monkeypatch.setattr(MaintenanceAnnonce.objects, 'filter', tombe)
    maintenance.clore_annonces()  # ne doit pas lever


# ═══ L'ÉCRAN D'ANNONCE ══════════════════════════════════════════════════════

def test_un_employe_n_atteint_pas_l_ecran_d_annonce(employe):
    reponse = employe.get(reverse('system_updates:maintenance_annonce'))
    assert reponse.status_code in (302, 403)


def test_l_admin_annonce_une_maintenance(admin):
    from apps.core.models import MaintenanceAnnonce

    debut = (timezone.localtime() + timezone.timedelta(hours=3)).strftime(
        '%Y-%m-%dT%H:%M')
    reponse = admin.post(reverse('system_updates:maintenance_annonce'), {
        'motif': 'mise_a_jour', 'debut_prevu': debut,
        'duree_minutes': '30', 'message': 'Passage en version 2.4',
    })

    assert reponse.status_code == 302
    annonce = MaintenanceAnnonce.objects.get()
    assert annonce.motif == 'mise_a_jour'
    assert annonce.duree_minutes == 30
    assert annonce.cree_par is not None


def test_une_duree_nulle_est_refusee(admin):
    """Elle sert à annoncer une heure de retour."""
    from apps.core.models import MaintenanceAnnonce

    debut = (timezone.localtime() + timezone.timedelta(hours=1)).strftime(
        '%Y-%m-%dT%H:%M')
    reponse = admin.post(reverse('system_updates:maintenance_annonce'), {
        'motif': 'maintenance', 'debut_prevu': debut,
        'duree_minutes': '0', 'message': '',
    })

    assert reponse.status_code == 200
    assert not MaintenanceAnnonce.objects.exists()


def test_l_admin_retire_l_annonce(admin):
    from apps.core.models import MaintenanceAnnonce

    _annonce()
    reponse = admin.post(
        reverse('system_updates:maintenance_annonce_annuler'))

    assert reponse.status_code == 302
    assert not MaintenanceAnnonce.objects.filter(active=True).exists()


def test_le_retrait_refuse_un_GET(admin):
    reponse = admin.get(
        reverse('system_updates:maintenance_annonce_annuler'))
    assert reponse.status_code == 405


def test_le_tableau_de_bord_mene_a_l_ecran(admin):
    corps = admin.get(reverse('system_updates:dashboard')).content.decode()
    assert reverse('system_updates:maintenance_annonce') in corps
    assert 'Prévenir les utilisateurs' in corps


# ═══ LE REDÉMARRAGE POSE SON ANNONCE ════════════════════════════════════════

def test_un_redemarrage_annonce_de_lui_meme(admin, monkeypatch):
    """Pendant la minute de délai, les utilisateurs doivent voir le
    bandeau et pouvoir enregistrer."""
    import platform

    from apps.core.models import MaintenanceAnnonce
    from apps.system_updates import server_actions

    monkeypatch.setattr(platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(server_actions, '_executer',
                        lambda action: {'ok': True})

    admin.post(reverse('system_updates:server_reboot'),
               {'confirm_text': 'REDEMARRER'})

    annonce = MaintenanceAnnonce.objects.filter(active=True).first()
    assert annonce is not None
    assert annonce.motif == 'redemarrage'


def test_annuler_l_action_retire_le_bandeau(admin, monkeypatch):
    """Un bandeau qui survit à son événement fait douter de l'état réel."""
    import platform

    from apps.core.models import MaintenanceAnnonce
    from apps.system_updates import server_actions

    monkeypatch.setattr(platform, 'system', lambda: 'Linux')
    monkeypatch.setattr(server_actions, '_executer',
                        lambda action: {'ok': True})

    admin.post(reverse('system_updates:server_reboot'),
               {'confirm_text': 'REDEMARRER'})
    assert MaintenanceAnnonce.objects.filter(active=True).exists()

    admin.post(reverse('system_updates:server_action_cancel'))
    assert not MaintenanceAnnonce.objects.filter(active=True).exists()


# ═══ LA PAGE SERVIE PAR NGINX, DJANGO ÉTANT ARRÊTÉ ══════════════════════════

PAGE_NGINX = (RACINE / 'deployment' / 'proxmox-appliance' / 'nginx'
              / 'redemarrage.html')
CONF_NGINX = (RACINE / 'deployment' / 'proxmox-appliance' / 'nginx'
              / 'orion-proxmox.conf.tmpl')


def test_la_page_de_redemarrage_existe():
    assert PAGE_NGINX.is_file(), PAGE_NGINX


def test_elle_est_entierement_autonome():
    """Servie par nginx, elle n'a accès ni à Django, ni aux fichiers
    statiques collectés : tout doit être dans le fichier."""
    texte = PAGE_NGINX.read_text(encoding='utf-8')

    assert '{%' not in texte, 'aucune balise de gabarit Django'
    assert '{{' not in texte
    assert 'src=' not in texte, 'aucune ressource externe'
    assert '<link' not in texte


def test_elle_se_recharge_toute_seule():
    texte = PAGE_NGINX.read_text(encoding='utf-8')
    assert re.search(r'http-equiv="refresh"', texte)


def test_elle_rassure_sur_les_donnees():
    texte = PAGE_NGINX.read_text(encoding='utf-8')
    assert 'données ne sont pas affectées' in texte


def test_nginx_sert_cette_page_sur_502():
    """Sans cette directive, l'utilisateur reçoit le « 502 Bad Gateway »
    brut : un message technique qui laisse croire à une panne."""
    conf = CONF_NGINX.read_text(encoding='utf-8')

    assert 'error_page 502 503 504' in conf
    assert '__redemarrage.html' in conf


def test_l_adresse_de_la_page_n_est_pas_publique():
    """Sans « internal », on pourrait afficher « redémarrage en cours » sur
    un serveur en parfait état."""
    conf = CONF_NGINX.read_text(encoding='utf-8')

    bloc = conf.split('location = /__redemarrage.html')[1]
    assert 'internal;' in bloc.split('}')[0]


def test_le_provisionnement_installe_la_page():
    script = (RACINE / 'deployment' / 'proxmox-appliance' / 'provisioning'
              / '04-nginx-config.sh').read_text(encoding='utf-8')

    assert 'redemarrage.html' in script
    assert '/opt/orion/nginx' in script


def test_la_page_est_installee_AVANT_le_test_de_configuration():
    """nginx -t échouerait sur une configuration qui cite un fichier
    absent... et surtout, recharger nginx avec la directive mais sans le
    fichier rendrait un 502 sur le 502."""
    script = (RACINE / 'deployment' / 'proxmox-appliance' / 'provisioning'
              / '04-nginx-config.sh').read_text(encoding='utf-8')

    position_page = script.find('redemarrage.html')
    position_test = script.find('nginx -t')
    assert position_page != -1 and position_test != -1
    assert position_page < position_test, (
        'la page doit etre installee avant « nginx -t »')
