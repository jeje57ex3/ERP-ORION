# -*- coding: utf-8 -*-
"""Le bouton de la fiche client : ouvrir un espace client, et renvoyer son code.

**POURQUOI CE FICHIER EXISTE, ET CE QU'IL GARDE.** Le bouton était écrit
mais invisible, et la cause valait d'être retenue : le gabarit
`templates/crm/customer_detail.html` était **commité**, et il gardait son
bouton derrière `{% if is_hr_admin %}` — une variable que seule
`crm.customer_detail` fournit. Tant que cette vue n'était pas livrée,
`is_hr_admin` était absent du contexte, donc faux, donc la branche n'était
jamais rendue : la fiche affichait « Ce client n'a pas encore d'accès à
l'espace client » et rien d'autre.

Aucune erreur, aucune trace. Un `{% url %}` vers une route inexistante
aurait au moins lever `NoReverseMatch` ; placé dans une branche jamais
prise, il ne s'évalue même pas. **Une moitié livrée sans l'autre ne casse
rien, elle efface** — et c'est plus difficile à voir qu'une panne.

D'où la forme de ces tests : ils demandent la fiche par le client HTTP et
cherchent le bouton dans le HTML rendu, puis suivent le POST jusqu'au
courriel réellement émis et jusqu'à une connexion réussie avec le code reçu.
"""
import re

import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.test import override_settings
from django.urls import reverse

from apps.core.models import Company
from apps.crm.models import Customer

pytestmark = pytest.mark.django_db

HOTES = ['testserver']

CREER = 'Créer un compte espace client'
RENVOYER = 'Renvoyer les identifiants'


# ═══════════════════════════════════════════════════════════════════════════
#  Décor
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def entreprise(db):
    """Sans entreprise, `SetupRequiredMiddleware` renvoie tout vers /setup/."""
    from apps.core import middleware
    middleware._setup_complete_cache = None
    societe = Company.objects.create(name='Elysiums', slug='elysiums-crm')
    yield societe
    middleware._setup_complete_cache = None


def _compte(entreprise, client, role, identifiant, superadmin=False):
    """Un compte ERP rattaché à l'entreprise, connecté.

    Le profil est modifié par `utilisateur.profile` et non par une instance
    obtenue séparément : `apps/accounts/signals.py` réenregistre le profil
    ENTIER à chaque sauvegarde de `User`, depuis l'instance mise en cache
    sur lui, et `force_login` met `last_login` à jour. Un rôle posé
    autrement serait réécrit par la valeur périmée du cache.
    """
    fabrique = (User.objects.create_superuser if superadmin
                else User.objects.create_user)
    utilisateur = fabrique(username=identifiant,
                           email='%s@elysiums.test' % identifiant,
                           password='tourbillon-de-sable-91')
    utilisateur.profile.role = role
    utilisateur.profile.companies.add(entreprise)
    utilisateur.profile.current_company = entreprise
    utilisateur.profile.save()
    client.force_login(utilisateur)
    return client


@pytest.fixture
def patron(entreprise, client):
    return _compte(entreprise, client, 'admin', 'patronne-crm')


@pytest.fixture
def salarie(entreprise):
    """UN NAVIGATEUR À LUI, et ce n'est pas un détail de confort.

    La fixture `client` de pytest-django est unique par test. Employée par
    `salarie` ET par `patron`, le second `force_login` écrase le premier :
    les deux fixtures rendent alors le MÊME objet, connecté en patronne.

    `test_un_salarie_ne_peut_pas_renvoyer` a échoué pour cette seule
    raison — il mesurait un envoi fait par l'administratrice en croyant
    mesurer un refus opposé au salarié. Un test qui demande les deux rôles
    doit leur donner deux sessions.
    """
    from django.test import Client

    return _compte(entreprise, Client(), 'user', 'salarie-crm')


@pytest.fixture
def cliente(entreprise):
    return Customer.objects.create(
        company=entreprise, name='Maçonnerie Durand',
        email='contact@durand.fr', contact_name='Alice Durand')


def _fiche(client, cliente):
    return client.get(
        reverse('crm:customer_detail', args=[cliente.pk])).content.decode()


def _cliquer(client, cliente):
    return client.post(
        reverse('portals:customer_portal_account_create', args=[cliente.pk]),
        follow=True)


def _code_du_courriel(message):
    trouve = re.search(r'Code provisoire\s*:\s*(\S+)', message.body)
    assert trouve, 'aucun code dans le corps :\n%s' % message.body
    return trouve.group(1)


def _messages(reponse):
    return [str(m) for m in reponse.context['messages']]


# ═══════════════════════════════════════════════════════════════════════════
#  1. Le bouton est VISIBLE
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_bouton_de_creation_apparait_sur_la_fiche(patron, cliente):
    """LE DÉFAUT EXACT : il était écrit, et personne ne le voyait.

    `is_hr_admin` manquait au contexte, donc la branche du gabarit n'était
    jamais rendue. Mesuré ici sur le HTML, parce que c'est ce que
    l'exploitant a sous les yeux.
    """
    corps = _fiche(patron, cliente)
    assert CREER in corps
    assert reverse('portals:customer_portal_account_create',
                   args=[cliente.pk]) in corps


@override_settings(ALLOWED_HOSTS=HOTES)
def test_un_client_sans_adresse_n_a_pas_de_bouton_mais_une_explication(
        patron, entreprise):
    """Un bouton qui échoue vaut moins qu'une phrase qui dit quoi faire.

    L'adresse est le seul chemin du code : sans elle, le compte créé serait
    muet.
    """
    muette = Customer.objects.create(
        company=entreprise, name='Client au téléphone', email='')
    corps = _fiche(patron, muette)

    assert CREER not in corps
    assert 'Ajoutez d’abord un email' in corps or 'Ajoutez d\'abord un email' in corps


@override_settings(ALLOWED_HOSTS=HOTES)
def test_un_salarie_ordinaire_ne_voit_pas_le_bouton(salarie, cliente):
    """Ouvrir un accès est une action d'administration.

    Et la vue refuse aussi le POST : garder le seul affichage laisserait
    l'action ouverte à qui connaît l'adresse.
    """
    assert CREER not in _fiche(salarie, cliente)


@override_settings(ALLOWED_HOSTS=HOTES)
def test_un_salarie_ordinaire_ne_peut_pas_non_plus_poster(salarie, cliente):
    """C'est le POST qui compte : lui seul crée le compte."""
    from apps.portals.models import ClientPortalAccount

    mail.outbox = []
    _cliquer(salarie, cliente)

    assert not ClientPortalAccount.objects.filter(
        email__iexact=cliente.email).exists()
    assert mail.outbox == []


@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_superadmin_voit_le_bouton(entreprise, client, cliente):
    """L'exploitant de l'installation passe, comme partout ailleurs."""
    navigateur = _compte(entreprise, client, 'user', 'ops-crm',
                         superadmin=True)
    assert CREER in _fiche(navigateur, cliente)


# ═══════════════════════════════════════════════════════════════════════════
#  2. Le clic envoie identifiant et code, et ils fonctionnent
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_clic_envoie_un_courriel_au_client(patron, cliente):
    mail.outbox = []
    reponse = _cliquer(patron, cliente)

    assert len(mail.outbox) == 1, mail.outbox
    assert mail.outbox[0].to == ['contact@durand.fr']
    assert any('code provisoire a été envoyé' in m
               for m in _messages(reponse)), _messages(reponse)


@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_courriel_porte_l_identifiant_et_le_code(patron, cliente):
    """« identifiant et mot de passe » : les deux, et le lien de connexion.

    Sans l'identifiant, le client essaie son nom. Sans lien absolu, il ne
    sait pas où aller — un courriel se lit ailleurs que dans l'ERP.
    """
    mail.outbox = []
    _cliquer(patron, cliente)
    message = mail.outbox[0]

    assert 'contact@durand.fr' in message.body, 'identifiant absent'
    assert _code_du_courriel(message)
    assert 'http' in message.body, 'aucun lien absolu'


@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_code_recu_ouvre_vraiment_l_espace_client(patron, cliente, client):
    """Le code émis et le code reconnu doivent être le même.

    Deux écritures séparées — `set_password` d'un côté, le corps du message
    de l'autre — peuvent parfaitement porter deux valeurs différentes.
    """
    from apps.portals.models import ClientPortalAccount

    mail.outbox = []
    _cliquer(patron, cliente)
    code = _code_du_courriel(mail.outbox[0])

    compte = ClientPortalAccount.objects.get(email__iexact=cliente.email)
    frais = client.__class__()
    assert frais.login(username=compte.user.username, password=code) is True


@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_client_doit_changer_a_sa_premiere_connexion(patron, cliente):
    from apps.portals.models import ClientPortalAccount

    _cliquer(patron, cliente)
    compte = ClientPortalAccount.objects.get(email__iexact=cliente.email)

    assert compte.user.profile.doit_changer_de_mot_de_passe is True
    assert compte.user.profile.code_provisoire_envoye_le is not None


@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_code_n_est_jamais_affiche_a_l_exploitant(patron, cliente):
    """Le point central du dispositif.

    Affiché « au cas où », il serait recopié et transmis par message, et le
    courriel ne servirait plus à rien.
    """
    mail.outbox = []
    reponse = _cliquer(patron, cliente)
    code = _code_du_courriel(mail.outbox[0])

    assert code not in reponse.content.decode()
    assert not any(code in m for m in _messages(reponse))


@override_settings(ALLOWED_HOSTS=HOTES)
def test_un_client_d_une_autre_entreprise_est_hors_de_portee(patron, db):
    """Le bornage par entreprise, sur une action qui ouvre un accès.

    Sans lui, un administrateur changeant le numéro dans l'URL ouvrirait un
    espace client chez un autre locataire — et enverrait un courriel en son
    nom.
    """
    autre = Company.objects.create(name='Voisine', slug='voisine-crm')
    etrangere = Customer.objects.create(
        company=autre, name='Client voisin', email='voisin@ailleurs.fr')

    mail.outbox = []
    reponse = patron.post(
        reverse('portals:customer_portal_account_create',
                args=[etrangere.pk]))

    assert reponse.status_code == 404
    assert mail.outbox == []


# ═══════════════════════════════════════════════════════════════════════════
#  3. Renvoyer les identifiants
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_bouton_de_renvoi_apparait_quand_le_compte_existe(patron, cliente):
    """Il n'y avait AUCUN bouton dans ce cas, seulement un badge d'état.

    Le code n'étant montré à personne, un courriel perdu laissait le client
    dehors sans recours depuis l'interface.
    """
    _cliquer(patron, cliente)
    corps = _fiche(patron, cliente)

    assert RENVOYER in corps
    assert CREER not in corps, (
        'les deux boutons s’affichent en même temps : lequel cliquer ?')


@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_renvoi_envoie_un_nouveau_code_et_annule_l_ancien(patron, cliente,
                                                             client):
    """Deux codes valides à la fois doubleraient la surface pour rien.

    Et un ancien courriel qui continuerait d'ouvrir le compte est exactement
    ce qu'on veut éviter quand on renvoie un code parce que le premier a
    fuité.
    """
    from apps.portals.models import ClientPortalAccount

    mail.outbox = []
    _cliquer(patron, cliente)
    premier = _code_du_courriel(mail.outbox[0])

    mail.outbox = []
    reponse = _cliquer(patron, cliente)
    second = _code_du_courriel(mail.outbox[0])

    assert premier != second
    assert any('NOUVEAU code' in m for m in _messages(reponse)), _messages(
        reponse)

    compte = ClientPortalAccount.objects.get(email__iexact=cliente.email)
    frais = client.__class__()
    assert frais.login(username=compte.user.username, password=premier) is False
    assert frais.login(username=compte.user.username, password=second) is True


@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_renvoi_ne_cree_pas_un_second_compte(patron, cliente):
    from apps.portals.models import ClientPortalAccount

    _cliquer(patron, cliente)
    _cliquer(patron, cliente)

    assert ClientPortalAccount.objects.filter(
        email__iexact=cliente.email).count() == 1


@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_renvoi_repose_l_obligation_de_changer(patron, cliente, client):
    """Un client qui a déjà choisi son mot de passe et redemande un accès
    doit en rechoisir un : le code renvoyé est provisoire comme le premier.

    Sans cela, le compte resterait sur le code engendré par la machine.
    """
    from apps.portals.models import ClientPortalAccount

    mail.outbox = []
    _cliquer(patron, cliente)
    code = _code_du_courriel(mail.outbox[0])
    compte = ClientPortalAccount.objects.get(email__iexact=cliente.email)

    # Le client choisit son mot de passe : l'obligation tombe.
    navigateur = client.__class__()
    navigateur.login(username=compte.user.username, password=code)
    navigateur.post(reverse('client_portal:changer_mot_de_passe'), {
        'old_password': code,
        'new_password1': 'bourrasque-de-platre-74',
        'new_password2': 'bourrasque-de-platre-74',
    })
    compte.user.profile.refresh_from_db()
    assert compte.user.profile.doit_changer_de_mot_de_passe is False

    # Puis l'exploitant renvoie un code : elle revient.
    _cliquer(patron, cliente)
    compte.user.profile.refresh_from_db()
    assert compte.user.profile.doit_changer_de_mot_de_passe is True


@override_settings(ALLOWED_HOSTS=HOTES)
def test_un_salarie_ne_peut_pas_renvoyer(salarie, patron, cliente):
    """Renvoyer remplace le mot de passe d'autrui : c'est une action
    d'administration autant que la création."""
    _cliquer(patron, cliente)

    mail.outbox = []
    _cliquer(salarie, cliente)
    assert mail.outbox == []


# ═══════════════════════════════════════════════════════════════════════════
#  4. Quand le courriel ne part pas
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(ALLOWED_HOSTS=HOTES)
def test_un_envoi_qui_echoue_est_dit_en_clair(patron, cliente, monkeypatch):
    """Le message disait « un email d'activation a été envoyé » quoi qu'il
    arrive, parce que `signup_service._send_email` passe `fail_silently=True`
    et rattrape toute exception : l'appelant ne pouvait pas savoir."""
    from apps.portals.services import acces_portail

    def refuse(*args, **kwargs):
        raise OSError('serveur SMTP injoignable')

    monkeypatch.setattr(acces_portail, 'send_mail', refuse)

    reponse = _cliquer(patron, cliente)
    textes = _messages(reponse)

    assert any('PAS pu être envoyé' in m for m in textes), textes
    assert any('SMTP' in m for m in textes), textes


@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_compte_reste_cree_malgre_l_echec(patron, cliente, monkeypatch):
    """ARBITRAGE ASSUMÉ : le défaire ferait perdre la saisie pour un serveur
    momentanément muet. Le compte reste, fermé, et le bouton de renvoi est
    là pour quand le courriel remarchera."""
    from apps.portals.models import ClientPortalAccount
    from apps.portals.services import acces_portail

    monkeypatch.setattr(acces_portail, 'send_mail',
                        lambda *a, **k: (_ for _ in ()).throw(OSError('muet')))

    _cliquer(patron, cliente)
    assert ClientPortalAccount.objects.filter(
        email__iexact=cliente.email).exists()
