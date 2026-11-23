# -*- coding: utf-8 -*-
"""La langue d'un client : son espace ET ses courriels, choisis à l'ouverture.

**LE PROBLÈME QUE CELA RÉSOUT.** Le courriel d'accès est composé pendant la
requête d'un SALARIÉ de l'ERP : la langue active est la sienne. Un exploitant
français qui ouvrait l'accès d'un client portugais lui envoyait donc du
français — et l'écran affichait « envoyé », donc rien ne le signalait. Côté
interface, l'espace client suivait le NAVIGATEUR du client, c'est-à-dire la
langue d'un appareil peut-être partagé ou mal réglé.

**UN SEUL CHAMP POUR LES DEUX.** `ClientPortalAccount.langue` gouverne
l'interface et les courriels. Deux réglages séparés finiraient par se
contredire, et un client qui lit son courriel en portugais puis trouve une
interface en français y verrait une erreur de l'entreprise.

**TROIS PIÈGES QUE CES TESTS GARDENT.**

1. `settings.LANGUAGES` déclare sept langues et `locale/` n'en contient que
   cinq : le néerlandais n'a **aucun catalogue**. L'offrir dans le sélecteur
   laisserait choisir une langue qui retombe en silence sur le français.
2. Les phrases du corps texte étaient écrites en français **en dur** :
   `override` n'avait aucune prise sur elles. Le gabarit HTML, lui, portait
   déjà ses `{% trans %}` — une moitié traduite et l'autre pas aurait donné
   un message bilingue.
3. Les `msgid` des `{% blocktrans %}` gardent leurs retours à la ligne et
   leur indentation, et le corps texte emploie des apostrophes
   typographiques là où le gabarit en emploie des droites. Un caractère de
   différence rend la traduction introuvable **sans aucun signal**.
"""
import pytest
from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, override_settings
from django.urls import reverse

from apps.core.models import Company
from apps.crm.models import Customer

pytestmark = pytest.mark.django_db

HOTES = ['testserver']


# ═══════════════════════════════════════════════════════════════════════════
#  Décor
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def entreprise(db):
    from apps.core import middleware
    middleware._setup_complete_cache = None
    societe = Company.objects.create(name='Elysiums', slug='elysiums-langue')
    yield societe
    middleware._setup_complete_cache = None


@pytest.fixture
def patron(entreprise, client):
    """Un administrateur, qui travaille en FRANÇAIS.

    C'est le point du test : sa langue ne doit pas décider de celle du
    client.
    """
    utilisateur = User.objects.create_user(
        username='patronne-langue', email='p@elysiums.test',
        password='tourbillon-de-sable-91')
    utilisateur.profile.role = 'admin'
    utilisateur.profile.companies.add(entreprise)
    utilisateur.profile.current_company = entreprise
    utilisateur.profile.save()
    client.force_login(utilisateur)
    return client


@pytest.fixture
def cliente(entreprise):
    return Customer.objects.create(
        company=entreprise, name='Obras Silva', email='silva@obras.pt',
        contact_name='João Silva')


def _ouvrir(client, cliente, langue):
    return client.post(
        reverse('portals:customer_portal_account_create', args=[cliente.pk]),
        {'langue': langue}, follow=True)


def _compte(cliente):
    from apps.portals.models import ClientPortalAccount

    return ClientPortalAccount.objects.get(email__iexact=cliente.email)


# ═══════════════════════════════════════════════════════════════════════════
#  1. Le sélecteur
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_selecteur_apparait_sur_la_fiche_client(patron, cliente):
    corps = patron.get(
        reverse('crm:customer_detail', args=[cliente.pk])).content.decode()

    assert 'name="langue"' in corps
    assert 'Langue du client' in corps
    assert 'Português' in corps


@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_selecteur_n_offre_pas_une_langue_sans_catalogue(patron, cliente):
    """LE NÉERLANDAIS EST DÉCLARÉ ET INTRADUISIBLE.

    `settings.LANGUAGES` le liste, `locale/nl/` n'existe pas. L'offrir
    laisserait l'exploitant croire qu'il a réglé la langue de son client,
    alors que celui-ci recevrait du français — et rien ne le dirait.
    """
    corps = patron.get(
        reverse('crm:customer_detail', args=[cliente.pk])).content.decode()

    assert 'Nederlands' not in corps
    assert '"nl"' not in corps


def test_les_langues_proposables_excluent_celles_sans_catalogue():
    from django.conf import settings

    from apps.portals.services.acces_portail import langues_proposables

    codes = {code for code, _nom in langues_proposables()}
    declares = {code for code, _nom in settings.LANGUAGES}

    assert 'fr' in codes, 'la langue source doit rester proposée'
    assert 'pt' in codes
    assert 'nl' not in codes
    assert codes < declares, (
        'aucune langue n’est écartée : le contrôle ne mesure rien')


@pytest.mark.parametrize('saisi', ['nl', 'xx', '', '  ', 'PT ', None])
def test_une_langue_non_servable_retombe_sur_le_defaut(saisi):
    """Un code forgé dans le POST ne doit pas casser l'envoi.

    « PT » en majuscules est accepté et normalisé : refuser une casse
    différente serait un refus que personne ne comprendrait.
    """
    from apps.portals.services.acces_portail import langue_valable

    attendu = 'pt' if (saisi or '').strip().lower() == 'pt' else 'fr'
    assert langue_valable(saisi) == attendu


# ═══════════════════════════════════════════════════════════════════════════
#  2. La langue choisie est enregistrée et gouverne le courriel
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(ALLOWED_HOSTS=HOTES)
def test_la_langue_choisie_est_enregistree(patron, cliente):
    _ouvrir(patron, cliente, 'pt')
    assert _compte(cliente).langue == 'pt'


@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_courriel_part_dans_la_langue_du_client_et_non_de_l_exploitant(
        patron, cliente):
    """LE DÉFAUT CENTRAL.

    Le message est composé pendant la requête de l'administratrice, qui
    travaille en français. Sans `override`, le client portugais recevait du
    français et l'écran disait « envoyé ».
    """
    mail.outbox = []
    _ouvrir(patron, cliente, 'pt')

    message = mail.outbox[0]
    assert 'A sua área de cliente' in message.subject, message.subject
    assert 'Olá' in message.body
    assert 'Código provisório' in message.body
    assert 'Code provisoire' not in message.body


@override_settings(ALLOWED_HOSTS=HOTES)
def test_la_version_html_suit_la_meme_langue(patron, cliente):
    """En omettre une donnerait un message BILINGUE.

    Pire que pas de traduction : le client y verrait une erreur de
    l'entreprise. Le gabarit HTML portait déjà ses `{% trans %}` quand le
    corps texte était en dur.
    """
    mail.outbox = []
    _ouvrir(patron, cliente, 'pt')

    message = mail.outbox[0]
    assert message.alternatives, 'aucune version HTML'
    html = message.alternatives[0][0]
    assert 'A sua área de cliente está aberta' in html
    assert 'Código provisório' in html
    assert 'Votre espace client' not in html


@override_settings(ALLOWED_HOSTS=HOTES)
def test_l_allemand_fonctionne_aussi(patron, cliente):
    """Le catalogue allemand est le plus incomplet du projet (361 entrées
    contre 4614) : une vérification faite en portugais seulement aurait pu
    le laisser de côté."""
    mail.outbox = []
    _ouvrir(patron, cliente, 'de')

    message = mail.outbox[0]
    assert 'Ihr Kundenbereich' in message.subject
    assert 'Vorläufiger Code' in message.body


@override_settings(ALLOWED_HOSTS=HOTES)
def test_en_francais_le_message_reste_celui_d_avant(patron, cliente):
    """La traduction ne doit pas abîmer la langue d'origine — celle que
    personne ne pense à revérifier après coup."""
    mail.outbox = []
    _ouvrir(patron, cliente, 'fr')

    message = mail.outbox[0]
    assert 'Votre espace client' in message.subject
    assert 'Code provisoire' in message.body


@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_code_reste_identique_quelle_que_soit_la_langue(patron, cliente,
                                                           client):
    """La traduction ne doit pas toucher au code lui-même.

    Il est engendré dans un alphabet fixe ; un formatage localisé des
    nombres ou une casse « corrigée » le rendrait inutilisable.
    """
    import re

    mail.outbox = []
    _ouvrir(patron, cliente, 'pt')
    code = re.search(r':\s*(\S{14})\s*$',
                     [l for l in mail.outbox[0].body.splitlines()
                      if 'provisório' in l][0]).group(1)

    compte = _compte(cliente)
    frais = Client()
    assert frais.login(username=compte.user.username, password=code) is True


# ═══════════════════════════════════════════════════════════════════════════
#  3. L'interface du client suit la même langue
# ═══════════════════════════════════════════════════════════════════════════

def _langue_servie(navigateur, chemin, **extra):
    """La langue que le middleware a retenue, lue sur `Content-Language`.

    On mesure sa DÉCISION et non une supposition : l'en-tête est posé par
    `OrionLanguageMiddleware` depuis la langue qu'il a activée.
    """
    reponse = navigateur.get(chemin, **extra)
    return reponse.get('Content-Language')


@override_settings(ALLOWED_HOSTS=HOTES)
def test_l_interface_du_client_suit_la_langue_de_son_compte(patron, cliente):
    """Sans cette étape, l'espace client suivait le NAVIGATEUR du client.

    Il n'a ni `UserLanguagePreference` — celle-ci dépend de l'entreprise
    courante, nulle pour lui — ni sélecteur de langue dans le portail. Le
    choix de l'exploitant ne gouvernait donc que les courriels.
    """
    import re

    mail.outbox = []
    _ouvrir(patron, cliente, 'pt')
    code = re.search(r'(\S{14})\s*$',
                     [l for l in mail.outbox[0].body.splitlines()
                      if 'provisório' in l][0]).group(1)

    compte = _compte(cliente)
    navigateur = Client()
    assert navigateur.login(username=compte.user.username, password=code)

    assert _langue_servie(navigateur,
                          reverse('client_portal:changer_mot_de_passe')) == 'pt'


@override_settings(ALLOWED_HOSTS=HOTES)
def test_la_langue_du_compte_bat_le_navigateur(patron, cliente):
    """L'exploitant qui connaît son client sait mieux qu'un en-tête
    `Accept-Language` d'un appareil peut-être partagé."""
    import re

    mail.outbox = []
    _ouvrir(patron, cliente, 'pt')
    code = re.search(r'(\S{14})\s*$',
                     [l for l in mail.outbox[0].body.splitlines()
                      if 'provisório' in l][0]).group(1)

    compte = _compte(cliente)
    navigateur = Client(HTTP_ACCEPT_LANGUAGE='de-DE,de;q=0.9')
    assert navigateur.login(username=compte.user.username, password=code)

    assert _langue_servie(
        navigateur, reverse('client_portal:changer_mot_de_passe')) == 'pt'


@override_settings(ALLOWED_HOSTS=HOTES)
def test_un_choix_explicite_du_client_l_emporte(patron, cliente):
    """L'ARBITRAGE DE L'ORDRE, et il est délibéré.

    Le réglage de l'exploitant est un DÉFAUT : un choix explicite du client
    — la session, « ?lang= », un futur sélecteur dans le portail — passe
    devant. Sans quoi un client ne pourrait jamais lire son espace dans la
    langue qu'il préfère.
    """
    import re

    mail.outbox = []
    _ouvrir(patron, cliente, 'pt')
    code = re.search(r'(\S{14})\s*$',
                     [l for l in mail.outbox[0].body.splitlines()
                      if 'provisório' in l][0]).group(1)

    compte = _compte(cliente)
    navigateur = Client()
    assert navigateur.login(username=compte.user.username, password=code)

    session = navigateur.session
    session['_language'] = 'es'
    session.save()

    assert _langue_servie(
        navigateur, reverse('client_portal:changer_mot_de_passe')) == 'es'


@override_settings(ALLOWED_HOSTS=HOTES)
def test_un_salarie_n_est_pas_affecte(patron, cliente):
    """La nouvelle étape ne doit pas déborder sur les comptes de l'ERP.

    Elle ne s'applique qu'aux porteurs d'un `portal_account`.
    """
    assert _langue_servie(patron, reverse('accounts:profile')) in (None, 'fr')


# ═══════════════════════════════════════════════════════════════════════════
#  4. Le renvoi
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_renvoi_sans_changement_garde_la_langue(patron, cliente):
    """Renvoyer un code ne doit pas réinitialiser la langue du client."""
    _ouvrir(patron, cliente, 'pt')
    mail.outbox = []
    _ouvrir(patron, cliente, 'pt')

    assert _compte(cliente).langue == 'pt'
    assert 'A sua área de cliente' in mail.outbox[0].subject


@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_renvoi_permet_de_corriger_la_langue(patron, cliente):
    """Un compte créé depuis un devis prend la langue du NAVIGATEUR du
    visiteur, qui peut être fausse. Sans ce sélecteur au renvoi, la seule
    façon de corriger serait une requête en base."""
    _ouvrir(patron, cliente, 'pt')
    mail.outbox = []
    _ouvrir(patron, cliente, 'de')

    assert _compte(cliente).langue == 'de'
    assert 'Ihr Kundenbereich' in mail.outbox[0].subject


@override_settings(ALLOWED_HOSTS=HOTES)
def test_un_champ_langue_absent_ne_touche_a_rien(patron, cliente):
    """Un POST sans le champ — un appel programmatique, un ancien gabarit en
    cache — ne doit pas ramener le client au français."""
    _ouvrir(patron, cliente, 'pt')
    patron.post(
        reverse('portals:customer_portal_account_create', args=[cliente.pk]),
        {}, follow=True)

    assert _compte(cliente).langue == 'pt'


# ═══════════════════════════════════════════════════════════════════════════
#  5. Le chemin public prend la langue du visiteur
# ═══════════════════════════════════════════════════════════════════════════

def test_un_compte_ouvert_depuis_un_devis_prend_la_langue_du_visiteur(
        entreprise):
    """Personne ne la choisit pour lui sur ce chemin.

    Il vient de remplir quatre écrans dans une langue : c'est celle qu'il
    lit. La prendre évite de lui envoyer son code en français parce que
    l'installation est française.
    """
    from django.utils.translation import override

    from apps.portals.services.acces_portail import (
        creer_un_compte_depuis_un_devis,
    )

    mail.outbox = []
    with override('pt'):
        compte, envoye, motif = creer_un_compte_depuis_un_devis(
            entreprise, {'email': 'visiteur@obras.pt',
                         'first_name': 'Maria', 'last_name': 'Costa'})

    assert envoye, motif
    assert compte.langue == 'pt'
    assert 'A sua área de cliente' in mail.outbox[0].subject
