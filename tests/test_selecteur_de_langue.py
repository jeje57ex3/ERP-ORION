"""Accès au changement de langue depuis un téléphone.

L'icône de traduction n'apparaissait pas sur téléphone, et pour deux raisons
distinctes :

  1. dans l'ERP, le sélecteur portait « d-none d-lg-block » — masqué en
     dessous de 992 px. Le bouton de thème juste à côté, lui, restait
     visible : rien ne justifiait cette exception, et aucune autre voie ne
     permettait de changer de langue depuis un petit écran ;
  2. l'interface téléphone dédiée (`/m/`) n'en avait aucun.

Ces tests gardent les deux, et la règle qui va avec : une icône qui ouvre un
menu vide est pire que pas d'icône.
"""

import io
import os

import pytest
from django.conf import settings

pytestmark = pytest.mark.django_db


def _gabarit(*morceaux):
    with io.open(os.path.join(settings.BASE_DIR, *morceaux),
                 encoding='utf-8') as fichier:
        return fichier.read()


@pytest.fixture
def langues(db):
    """Deux langues actives : sans quoi il n'y a rien à choisir."""
    from apps.translations.models import Language

    Language.objects.update_or_create(
        code='fr', defaults={'name': 'Français', 'native_name': 'Français',
                             'flag_icon': '🇫🇷', 'is_active': True})
    Language.objects.update_or_create(
        code='en', defaults={'name': 'Anglais', 'native_name': 'English',
                             'flag_icon': '🇬🇧', 'is_active': True})
    return Language.objects.filter(is_active=True)


@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Langue SA', slug='langue-sa')


@pytest.fixture
def connecte(client, django_user_model, entreprise, monkeypatch):
    utilisateur = django_user_model.objects.create_user(
        username='ouvrier', password='motdepasse-test')
    client.force_login(utilisateur)
    from apps.mobile_web import views
    monkeypatch.setattr(views, '_entreprise', lambda requete: entreprise)
    return client


# ── L'ERP sur un petit écran ────────────────────────────────────────────────

def test_le_selecteur_de_langue_n_est_plus_masque_sur_telephone():
    """« d-none d-lg-block » le faisait disparaître en dessous de 992 px.

    Contrôle sur la source du gabarit : la classe est posée par Bootstrap et
    ne se voit pas dans une réponse HTTP autrement qu'en relisant le même
    attribut — autant le lire là où il est écrit.
    """
    gabarit = _gabarit('templates', 'erp_base.html')
    debut = gabarit.index('erpLangToggle')
    # Le conteneur du sélecteur est la balise <div class="dropdown…"> qui
    # précède immédiatement le bouton.
    conteneur = gabarit[:debut].rsplit('<div class="dropdown', 1)[1]
    assert 'd-none' not in conteneur.split('>')[0], (
        'le sélecteur de langue est de nouveau masqué sur petit écran'
    )


def test_le_bouton_creer_reste_reserve_au_grand_ecran():
    """Lui a un équivalent dans la barre d'action du bas : le dupliquer en
    haut encombrerait une barre déjà étroite."""
    gabarit = _gabarit('templates', 'erp_base.html')
    debut = gabarit.index('orionCreateBtn')
    conteneur = gabarit[:debut].rsplit('<div class="dropdown', 1)[1]
    assert 'd-none d-lg-block' in conteneur.split('>')[0]


def test_l_icone_de_langue_est_servie_dans_l_erp(client, django_user_model,
                                                 langues, entreprise):
    client.force_login(django_user_model.objects.create_user(
        username='chef', password='motdepasse-test'))
    corps = client.get('/dashboard/').content.decode()
    assert 'bi-translate' in corps
    assert 'erpLangToggle' in corps


def test_sans_langue_active_aucune_icone_dans_l_erp(client, django_user_model,
                                                    entreprise):
    """Une icône qui ouvre un menu vide est pire que pas d'icône."""
    from apps.translations.models import Language

    Language.objects.update(is_active=False)
    client.force_login(django_user_model.objects.create_user(
        username='chef2', password='motdepasse-test'))
    corps = client.get('/dashboard/').content.decode()
    assert 'erpLangToggle' not in corps


# ── L'interface téléphone dédiée ───────────────────────────────────────────

def test_l_interface_telephone_propose_les_langues(connecte, langues):
    corps = connecte.get('/m/').content.decode()

    assert 'class="langues"' in corps
    assert 'English' in corps
    assert 'Français' in corps


def test_le_lien_mene_au_changement_de_langue(connecte, langues):
    from django.urls import reverse

    corps = connecte.get('/m/').content.decode()
    adresse = reverse('core:set_user_language')
    assert f'{adresse}?lang=en' in corps
    # Et le retour se fait sur la page courante, non sur le tableau de bord :
    # changer de langue ne doit pas faire quitter l'écran photo.
    assert 'next=%2Fm%2F' in corps or 'next=/m/' in corps


def test_le_selecteur_figure_sur_les_trois_pages(connecte, langues):
    """Il est dans la base du gabarit : les trois pages en héritent, et une
    page qui ne l'aurait pas serait un cul-de-sac linguistique."""
    for adresse in ('/m/', '/m/photo/', '/m/serveurs/'):
        corps = connecte.get(adresse).content.decode()
        assert 'class="langues"' in corps, adresse


def test_sans_langue_active_aucune_icone_sur_telephone(connecte):
    from apps.translations.models import Language

    Language.objects.update(is_active=False)
    corps = connecte.get('/m/').content.decode()
    assert 'class="langues"' not in corps


def test_le_selecteur_telephone_ne_depend_d_aucune_bibliotheque():
    """Ce gabarit est autonome — ni Bootstrap ni police d'icônes — et doit
    fonctionner hors ligne, dans l'application installée. Un menu natif
    <details> n'a rien à charger."""
    gabarit = _gabarit('apps', 'mobile_web', 'templates', 'mobile_web',
                       'base_mobile.html')
    debut = gabarit.index('class="langues"')
    bloc = gabarit[debut:debut + 900]
    # Le menu est bien un <details> natif, et non un composant a piloter.
    assert '<details class="langues"' in gabarit
    assert '<summary' in bloc
    assert 'data-bs-toggle' not in bloc, 'dépend de Bootstrap'
    assert 'onclick' not in bloc, 'dépend de JavaScript'


def test_la_langue_choisie_est_marquee(connecte, langues):
    """Sans marque, on ne sait pas dans quelle langue on se trouve — et on
    rebascule au hasard."""
    corps = connecte.get('/m/').content.decode()
    assert 'actuelle' in corps


# ── Le changement lui-même ─────────────────────────────────────────────────

def test_changer_de_langue_depuis_le_telephone_revient_sur_la_page(
        connecte, langues):
    from django.urls import reverse

    reponse = connecte.get(
        reverse('core:set_user_language') + '?lang=en&next=/m/photo/')
    assert reponse.status_code == 302
    assert reponse['Location'] == '/m/photo/'


def test_une_destination_externe_est_refusee(connecte, langues):
    """`next` vient de l'URL : une adresse absolue en ferait une redirection
    ouverte, utilisable pour envoyer un utilisateur connecté ailleurs."""
    from django.urls import reverse

    reponse = connecte.get(
        reverse('core:set_user_language')
        + '?lang=en&next=https://exemple-malveillant.fr/')
    assert reponse.status_code == 302
    assert 'exemple-malveillant' not in reponse['Location']
