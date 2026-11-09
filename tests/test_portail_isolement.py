# -*- coding: utf-8 -*-
"""Chaque client voit SON chantier, et seulement le sien.

Tout le portail retrouve les chantiers par
`company=... , customer__email=account.email`. Les quatorze vues
l'appliquent, et ce fichier le vérifie — mais surtout, il pince la faille
que ce filtre porte en lui.

LA FAILLE DU COURRIEL VIDE.

`Customer.email` est déclaré `blank=True` : un client de BTP créé au
téléphone n'en a souvent pas. Et `ClientPortalAccount.email` vaut la chaîne
vide par défaut au niveau de la base, quoi qu'en dise le formulaire.

Si les deux se rencontrent, le filtre devient `customer__email=''` et
correspond à TOUS les clients sans courriel de l'entreprise. Le compte
verrait leurs chantiers, leurs documents, leurs messages et leurs réserves
— sans qu'aucune page n'ait l'air anormale, ce qui est le pire des cas :
une fuite qu'aucun symptôme ne signale.

LE TEST QUI COMPTE LE PLUS est celui qui balaie TOUTES les URL du portail
d'un coup, en les découvrant au lieu de les énumérer. Une quinzième vue
ajoutée demain sans le filtre le fera échouer, sans que personne ait eu à
penser à l'inscrire ici.
"""

from datetime import date

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _entreprise(nom, slug):
    from apps.core.models import Company
    return Company.objects.create(name=nom, slug=slug)


def _client_du_portail(client_web, entreprise, django_user_model, courriel,
                       nom='Martin'):
    """Un couple Customer + ClientPortalAccount + chantier, connecté."""
    from apps.btp.models import BTPProject
    from apps.crm.models import Customer
    from apps.portals.models import ClientPortalAccount

    utilisateur = django_user_model.objects.create_user(
        username=courriel or ('sans-courriel-%s' % nom),
        email=courriel, password='motdepasse-test')
    ClientPortalAccount.objects.create(
        company=entreprise, user=utilisateur, email=courriel,
        first_name='Paul', last_name=nom)
    acheteur = Customer.objects.create(
        company=entreprise, name=nom, email=courriel)
    chantier = BTPProject.objects.create(
        company=entreprise, name='Chantier %s' % nom, customer=acheteur,
        start_date=date(2026, 3, 2))

    navigateur = client_web.__class__()
    navigateur.force_login(utilisateur)
    return navigateur, chantier


@pytest.fixture
def deux_clients(client, django_user_model):
    """Deux clients DE LA MÊME ENTREPRISE, chacun avec son chantier.

    Le cas le plus dangereux : l'isolement par entreprise ne protège de
    rien ici, puisqu'ils la partagent. Seul le courriel les sépare.
    """
    entreprise = _entreprise('Volt SARL', 'volt-sarl')
    martin = _client_du_portail(client, entreprise, django_user_model,
                                'martin@exemple.fr', nom='Martin')
    durand = _client_du_portail(client, entreprise, django_user_model,
                                'durand@exemple.fr', nom='Durand')
    return martin, durand


# ─── Chacun chez soi ───────────────────────────────────────────────────────

def test_chaque_client_ne_voit_que_son_chantier(deux_clients):
    (navigateur_martin, chantier_martin), (_n, chantier_durand) = deux_clients

    contenu = navigateur_martin.get(
        reverse('client_portal:project_list')).content.decode()

    assert chantier_martin.name in contenu
    assert chantier_durand.name not in contenu, (
        'un client voit le chantier d-un autre client de la meme entreprise')


def test_le_tableau_de_bord_ne_montre_que_ses_chantiers(deux_clients):
    (navigateur_martin, chantier_martin), (_n, chantier_durand) = deux_clients

    contenu = navigateur_martin.get(
        reverse('client_portal:dashboard')).content.decode()

    assert chantier_martin.name in contenu
    assert chantier_durand.name not in contenu


def test_le_chantier_d_un_autre_client_est_introuvable(deux_clients):
    (navigateur_martin, _c), (_n, chantier_durand) = deux_clients

    reponse = navigateur_martin.get(
        reverse('client_portal:project_detail', args=[chantier_durand.pk]))

    assert reponse.status_code == 404


def test_le_chantier_d_une_autre_entreprise_est_introuvable(client,
                                                            django_user_model,
                                                            deux_clients):
    (navigateur_martin, _c), _durand = deux_clients
    ailleurs = _entreprise('Ampere SA', 'ampere-sa')
    _navigateur, chantier_voisin = _client_du_portail(
        client, ailleurs, django_user_model, 'dupont@ampere.fr',
        nom='Dupont')

    reponse = navigateur_martin.get(
        reverse('client_portal:project_detail', args=[chantier_voisin.pk]))

    assert reponse.status_code == 404


# ─── Le balayage de TOUTES les URL du portail ─────────────────────────────

def _urls_du_portail_pour(chantier):
    """Toutes les routes du portail qui désignent un chantier.

    DÉCOUVERTES et non énumérées : une vue ajoutée demain sans le filtre
    fera échouer le test, sans que personne ait eu à l'inscrire ici.
    """
    import re

    from apps.portals import client_urls

    trouvees = []
    for motif in client_urls.urlpatterns:
        route = str(motif.pattern)
        if '<int:pk>' not in route:
            continue
        noms = re.findall(r'<int:(\w+)>', route)
        arguments = {nom: (chantier.pk if nom == 'pk' else 1)
                     for nom in noms}
        try:
            trouvees.append(
                (motif.name,
                 reverse('client_portal:%s' % motif.name, kwargs=arguments)))
        except Exception:                               # noqa: BLE001
            continue
    return trouvees


def test_aucune_url_du_portail_ne_laisse_passer_un_chantier_etranger(
        deux_clients):
    """LE test qui compte. Il découvre les routes au lieu de les lister."""
    (navigateur_martin, _c), (_n, chantier_durand) = deux_clients

    routes = _urls_du_portail_pour(chantier_durand)
    assert len(routes) >= 5, (
        'la decouverte des routes est cassee : %s' % routes)

    fuites = []
    for nom, url in routes:
        reponse = navigateur_martin.get(url)
        if reponse.status_code == 200:
            fuites.append('%s (%s)' % (nom, url))

    assert fuites == [], (
        'ces vues rendent le chantier d-un autre client : %s' % fuites)


# ─── La faille du courriel vide ───────────────────────────────────────────

def test_un_compte_sans_courriel_ne_voit_rien(client, django_user_model):
    """Sans ce garde-fou, il verrait TOUS les clients sans courriel.

    `Customer.email` est `blank=True` : un client cree au telephone n'en a
    souvent pas. Le filtre deviendrait `customer__email=''` et
    correspondrait a tous ceux-la d'un coup.
    """
    from apps.btp.models import BTPProject
    from apps.crm.models import Customer
    from apps.portals.models import ClientPortalAccount

    entreprise = _entreprise('Volt SARL', 'volt-sarl')

    # Un vrai client de l'entreprise, sans adresse email -- le cas courant.
    muet = Customer.objects.create(company=entreprise, name='Sans Email',
                                   email='')
    chantier_muet = BTPProject.objects.create(
        company=entreprise, name='Chantier confidentiel', customer=muet,
        start_date=date(2026, 3, 2))

    # Et un compte portail dont le courriel est vide.
    utilisateur = django_user_model.objects.create_user(
        username='compte-sans-courriel', password='motdepasse-test')
    ClientPortalAccount.objects.create(
        company=entreprise, user=utilisateur, email='',
        first_name='Anonyme', last_name='Anonyme')

    navigateur = client.__class__()
    navigateur.force_login(utilisateur)

    liste = navigateur.get(reverse('client_portal:project_list'))
    assert liste.status_code == 302, (
        'un compte sans courriel doit etre refuse, pas servi')
    assert chantier_muet.name not in liste.content.decode()

    detail = navigateur.get(
        reverse('client_portal:project_detail', args=[chantier_muet.pk]))
    assert detail.status_code == 302


def test_un_courriel_fait_d_espaces_ne_passe_pas_non_plus(client,
                                                          django_user_model):
    """« ' ' » n'est pas vide pour Python, et serait tout aussi dangereux."""
    from apps.portals.models import ClientPortalAccount

    entreprise = _entreprise('Volt SARL', 'volt-sarl')
    utilisateur = django_user_model.objects.create_user(
        username='compte-espaces', password='motdepasse-test')
    ClientPortalAccount.objects.create(
        company=entreprise, user=utilisateur, email='   ',
        first_name='Anonyme', last_name='Anonyme')

    navigateur = client.__class__()
    navigateur.force_login(utilisateur)

    assert navigateur.get(
        reverse('client_portal:project_list')).status_code == 302


def test_un_client_avec_courriel_voit_bien_son_chantier(deux_clients):
    """Le garde-fou ne doit pas fermer la porte aux comptes valides."""
    (navigateur_martin, chantier_martin), _durand = deux_clients

    reponse = navigateur_martin.get(
        reverse('client_portal:project_detail', args=[chantier_martin.pk]))

    assert reponse.status_code == 200
    assert chantier_martin.name in reponse.content.decode()
