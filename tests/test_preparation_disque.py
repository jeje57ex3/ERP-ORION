# -*- coding: utf-8 -*-
"""Préparer un disque neuf doit être un bouton, pas un formulaire.

RAPPORTÉ DEPUIS L'ÉCRAN : « je n'ai toujours pas de bouton pour formater ou
préparer les nouveaux disques de manière simple et rapide ».

C'était exact. Le formulaire exigeait DEUX saisies — un nom de volume, et
la recopie exacte de « /dev/sdb » — y compris pour un disque sorti de son
emballage, sans partition ni système de fichiers, où il n'y a rigoureusement
rien à perdre.

LA FRICTION EST DÉSORMAIS PROPORTIONNELLE AU RISQUE.

* **Disque vierge** — un bouton, avec une confirmation du navigateur qui
  nomme le disque et sa taille. Le nom de volume est pré-rempli.
* **Disque qui contient quelque chose** — la recopie à la main est
  conservée. C'est là que l'erreur coûte, et seulement là.

ET C'EST LE SERVEUR QUI TRANCHE. Il redemande l'inventaire à l'assistant
root plutôt que de croire le formulaire : une page restée ouverte pendant
qu'on branche un autre disque proposerait sinon un raccourci sur un disque
devenu plein. Le test qui forge une requête le vérifie.
"""

import copy

import pytest
from django.urls import reverse

from tests.test_stockage_affichage import (  # noqa: F401  (fixtures pytest)
    DISQUES_REELS, VOLUMES_UN_SEUL_DISQUE, _assistant_qui_repond, _machine,
    _super_admin)

pytestmark = pytest.mark.django_db

URL_PREPARER = 'system_health:stockage_preparer_disque'


def _inventaire(contient_des_donnees=False, montages=()):
    """L'inventaire réel de la machine, ajusté pour le cas testé."""
    reponse = copy.deepcopy(DISQUES_REELS)
    for disque in reponse['disques']:
        if disque['peripherique'] == '/dev/sdb':
            disque['contient_des_donnees'] = contient_des_donnees
            disque['systemes_de_fichiers'] = (
                ['ext4'] if contient_des_donnees else [])
    reponse['montages_orion'] = list(montages)
    return reponse


@pytest.fixture
def file_acceptee(monkeypatch):
    """Celery n'est pas joignable en test : on ne mesure pas sa file."""
    monkeypatch.setattr(
        'apps.system_health.views._mettre_en_file',
        lambda tache, operation: True)


def _page(client):
    reponse = client.get(reverse('system_health:disk_dashboard'))
    assert reponse.status_code == 200
    return reponse.content.decode()


def _operations():
    from apps.system_health.models import OperationDeStockage
    return OperationDeStockage.objects.all()


# ─── L'écran : un bouton pour un disque vierge ────────────────────────────

def test_un_disque_vierge_propose_un_bouton_sans_recopie(
        client, django_user_model, monkeypatch):
    _assistant_qui_repond(monkeypatch, _inventaire(False))
    _machine(monkeypatch, VOLUMES_UN_SEUL_DISQUE, VOLUMES_UN_SEUL_DISQUE[0])
    _super_admin(client, django_user_model)

    contenu = _page(client)

    assert 'Préparer ce disque' in contenu
    assert 'vierge' in contenu
    assert 'name="confirmation"' not in contenu, (
        'recopier le nom du disque n-a aucun sens quand il n-y a rien a '
        'perdre : c-est ce qui faisait dire qu-il n-y avait pas de bouton')


def test_le_nom_du_volume_est_deja_rempli(client, django_user_model,
                                           monkeypatch):
    """Sur un ERP à un ou deux disques, le faire saisir n'apprend rien."""
    _assistant_qui_repond(monkeypatch, _inventaire(False))
    _machine(monkeypatch, VOLUMES_UN_SEUL_DISQUE, VOLUMES_UN_SEUL_DISQUE[0])
    _super_admin(client, django_user_model)

    contenu = _page(client)

    assert 'value="donnees"' in contenu


def test_un_disque_qui_contient_des_donnees_garde_la_recopie(
        client, django_user_model, monkeypatch):
    """C'est là que l'erreur coûte, et la friction s'y justifie."""
    _assistant_qui_repond(monkeypatch, _inventaire(True))
    _machine(monkeypatch, VOLUMES_UN_SEUL_DISQUE, VOLUMES_UN_SEUL_DISQUE[0])
    _super_admin(client, django_user_model)

    contenu = _page(client)

    assert 'name="confirmation"' in contenu
    assert 'Effacer et préparer' in contenu
    assert 'contient déjà des données' in contenu


# ─── Le POST : le serveur décide ──────────────────────────────────────────

def test_un_disque_vierge_se_prepare_en_un_clic(client, django_user_model,
                                                monkeypatch, file_acceptee):
    _assistant_qui_repond(monkeypatch, _inventaire(False))
    _machine(monkeypatch, VOLUMES_UN_SEUL_DISQUE, VOLUMES_UN_SEUL_DISQUE[0])
    _super_admin(client, django_user_model)

    reponse = client.post(reverse(URL_PREPARER), {
        'peripherique': '/dev/sdb',
        'numero_de_serie': 'QM00013',
        'etiquette': 'donnees',
    })

    assert reponse.status_code == 302
    assert _operations().count() == 1
    operation = _operations().first()
    assert operation.peripherique == '/dev/sdb'
    assert operation.volume_cible == 'donnees'


def test_sans_nom_de_volume_le_serveur_en_propose_un(client,
                                                     django_user_model,
                                                     monkeypatch,
                                                     file_acceptee):
    """Le champ reste facultatif : un bouton ne doit rien exiger."""
    _assistant_qui_repond(monkeypatch, _inventaire(False))
    _machine(monkeypatch, VOLUMES_UN_SEUL_DISQUE, VOLUMES_UN_SEUL_DISQUE[0])
    _super_admin(client, django_user_model)

    client.post(reverse(URL_PREPARER), {
        'peripherique': '/dev/sdb', 'numero_de_serie': 'QM00013'})

    assert _operations().first().volume_cible == 'donnees'


def test_un_disque_plein_refuse_le_raccourci(client, django_user_model,
                                             monkeypatch, file_acceptee):
    """LE test qui compte : le formulaire ne décide pas, l'inventaire oui.

    Une page restée ouverte pendant qu'on branche un autre disque, ou une
    requête forgée, proposerait sinon le parcours en un clic sur un disque
    devenu plein.
    """
    _assistant_qui_repond(monkeypatch, _inventaire(True))
    _machine(monkeypatch, VOLUMES_UN_SEUL_DISQUE, VOLUMES_UN_SEUL_DISQUE[0])
    _super_admin(client, django_user_model)

    reponse = client.post(reverse(URL_PREPARER), {
        'peripherique': '/dev/sdb',
        'numero_de_serie': 'QM00013',
        'etiquette': 'donnees',
    })

    assert reponse.status_code == 302
    assert _operations().count() == 0, (
        'un disque contenant des donnees a ete prepare sans confirmation')


def test_un_disque_plein_se_prepare_avec_la_recopie(client,
                                                    django_user_model,
                                                    monkeypatch,
                                                    file_acceptee):
    _assistant_qui_repond(monkeypatch, _inventaire(True))
    _machine(monkeypatch, VOLUMES_UN_SEUL_DISQUE, VOLUMES_UN_SEUL_DISQUE[0])
    _super_admin(client, django_user_model)

    client.post(reverse(URL_PREPARER), {
        'peripherique': '/dev/sdb',
        'numero_de_serie': 'QM00013',
        'etiquette': 'donnees',
        'confirmation': '/dev/sdb',
    })

    assert _operations().count() == 1


def test_un_disque_absent_de_l_inventaire_est_refuse(client,
                                                     django_user_model,
                                                     monkeypatch,
                                                     file_acceptee):
    """Un nom inventé, ou un disque débranché depuis l'affichage."""
    _assistant_qui_repond(monkeypatch, _inventaire(False))
    _machine(monkeypatch, VOLUMES_UN_SEUL_DISQUE, VOLUMES_UN_SEUL_DISQUE[0])
    _super_admin(client, django_user_model)

    reponse = client.post(reverse(URL_PREPARER), {
        'peripherique': '/dev/sdz', 'etiquette': 'donnees'})

    assert reponse.status_code == 302
    assert _operations().count() == 0


# ─── Le nom proposé ───────────────────────────────────────────────────────

def test_le_nom_propose_evite_ceux_deja_pris(monkeypatch):
    """Deux volumes « donnees » ne peuvent pas coexister."""
    from apps.system_health.views import etiquette_proposee

    assert etiquette_proposee(_inventaire(False)) == 'donnees'
    assert etiquette_proposee(
        _inventaire(False, montages=['/mnt/orion-donnees'])) == 'donnees-2'
    assert etiquette_proposee(_inventaire(
        False,
        montages=['/mnt/orion-donnees', '/mnt/orion-donnees-2'])) == 'donnees-3'


def test_le_nom_propose_tient_sans_assistant(monkeypatch):
    """Il ne doit jamais lever : il sert à remplir une case."""
    from apps.system_health.views import etiquette_proposee

    monkeypatch.setattr(
        'apps.system_health.stockage_privilegie.est_disponible',
        lambda: False)

    assert etiquette_proposee() == 'donnees'
