"""Plusieurs moyens de paiement sur un même document.

CE QUI MANQUAIT, ET OÙ EXACTEMENT

Le modèle stocke `paiements` en liste. `tipos.valider_les_paiements`
parcourt cette liste et exige un montant dès le deuxième élément.
`saft.py` émet un bloc `Payment` par élément, et le XSD autorise
`Payment*`. Les trois couches basses acceptaient donc plusieurs moyens
depuis le premier jour.

Seul l'ÉCRAN n'en offrait qu'un — un `ChoiceField` unique dans
`RecuForm`, un `<select name="mecanisme">` unique sur la facture. Une
facture réglée moitié en espèces, moitié par carte, qui est une
situation ordinaire, était donc inatteignable depuis l'interface. Et
comme le défaut était dans le formulaire et non dans la règle, aucun
test de règle ne pouvait le voir : ils passaient tous des listes à la
main, c'est-à-dire précisément ce que personne ne pouvait faire.

C'EST POURQUOI LA MOITIÉ DE CE FICHIER MESURE DU HTML

Vérifier que `emettre_un_recu(moyens=[...])` accepte deux moyens ne
prouve rien sur ce qu'un utilisateur peut faire : c'est l'erreur qui a
laissé le défaut en place. Les tests d'écran ci-dessous passent par un
POST et par le HTML rendu.

LA RÈGLE N'EST PAS RECOPIÉE DANS LE FORMULAIRE

L'égalité « somme des moyens = total du document » reste au seul endroit
où le total du document est connu : l'émission, qui le calcule depuis les
lignes qu'elle vient de figer. Un contrôle dans le formulaire devrait
employer le cumul tenu par la facture de l'ERP — un autre nombre, qui
dérive d'un centime après une suppression de ligne. Au Portugal ce
centime est signé.
"""
from datetime import date
from decimal import Decimal
from xml.etree import ElementTree as ET

import pytest
from cryptography.fernet import Fernet
from django.urls import reverse

from apps.core.models import Company
from apps.crm.models import Customer
from apps.fiscal_pt import export, facturation, schema, tipos
from apps.fiscal_pt.models import (CleDeSignature, ParametresFiscauxPT,
                                   SerieFiscale)
from apps.sales.models import Invoice, InvoiceLine

ESPACE = '{urn:OECD:StandardAuditFile-Tax:PT_1.04_01}'

pytestmark = pytest.mark.django_db


@pytest.fixture
def chiffrement(settings):
    settings.ORION_SECRET_ENCRYPTION_KEY = Fernet.generate_key().decode()


@pytest.fixture
def entreprise(db):
    return Company.objects.create(name='Orion Lusitana', slug='orion-moyens')


@pytest.fixture
def cliente(entreprise):
    return Customer.objects.create(company=entreprise, name='Cliente Lda',
                                   nif='500000000', country='Portugal')


@pytest.fixture
def conformite(entreprise, chiffrement):
    parametres = ParametresFiscauxPT.de(entreprise)
    parametres.est_actif = True
    parametres.nif = '123456789'
    parametres.save()
    cle = CleDeSignature.creer(entreprise)

    codes = {'FT': 'CSDF7T5H', 'FR': 'RQD8L6DG', 'NC': 'KSMLFPQZ',
             'RG': 'JFFNVTC7'}
    return {type_document: SerieFiscale.objects.create(
                company=entreprise, type_document=type_document, nom='A',
                code_de_validation=code, cle=cle)
            for type_document, code in codes.items()}


def _facture(entreprise, cliente, numero='FAC-0001', prix=Decimal('80.00')):
    facture = Invoice.objects.create(
        company=entreprise, customer=cliente, number=numero,
        issue_date=date(2026, 3, 7), status='draft')
    InvoiceLine.objects.create(
        invoice=facture, description='Instalação elétrica',
        quantity=Decimal('1'), unit_price=prix, vat_rate=Decimal('23'))
    facture.refresh_from_db()
    return facture


@pytest.fixture
def facture_signee(entreprise, cliente, conformite):
    """98,40 € à encaisser, émise en « FT »."""
    facture = _facture(entreprise, cliente)
    facturation.emettre_pour_facture(facture)
    facture.refresh_from_db()
    return facture


# ═══ 1. L'ÉMISSION ACCEPTE PLUSIEURS MOYENS ════════════════════════════════

def test_un_recu_porte_deux_moyens_de_paiement(facture_signee):
    """Moitié en espèces, moitié par carte — et les deux sont figés."""
    recu = facturation.emettre_un_recu(facture_signee, moyens=[
        {'mecanisme': 'NU', 'montant': Decimal('50.00')},
        {'mecanisme': 'CC', 'montant': Decimal('48.40')},
    ])

    assert recu.total == Decimal('98.40')
    assert len(recu.paiements) == 2
    assert [p['mecanisme'] for p in recu.paiements] == ['NU', 'CC']
    assert [Decimal(p['montant']) for p in recu.paiements] == [
        Decimal('50.00'), Decimal('48.40')]


def test_le_moyen_unique_sans_montant_vaut_toujours_le_total(facture_signee):
    """LA CONTREPARTIE, sans laquelle l'ajout serait une régression.

    C'est le cas courant, et son montant n'est pas saisi : l'émission y
    met le total qu'elle vient de calculer depuis les affectations. Le
    faire saisir ferait entrer ici le cumul tenu par la facture de l'ERP,
    qui n'est pas le même nombre.
    """
    recu = facturation.emettre_un_recu(facture_signee, 'TB')

    assert len(recu.paiements) == 1
    assert Decimal(recu.paiements[0]['montant']) == Decimal('98.40')


def test_un_seul_moyen_passe_aussi_par_moyens(facture_signee):
    """Les deux chemins — `mecanisme` et `moyens` — aboutissent au même."""
    recu = facturation.emettre_un_recu(facture_signee,
                                       moyens=[{'mecanisme': 'TB'}])

    assert len(recu.paiements) == 1
    assert recu.paiements[0]['mecanisme'] == 'TB'
    assert Decimal(recu.paiements[0]['montant']) == Decimal('98.40')


def test_une_somme_qui_ne_fait_pas_le_total_est_refusee(facture_signee):
    """La règle vit au seul endroit où le total du document est connu.

    Et son message donne les DEUX nombres : « 90 € au lieu de 98,40 € »
    envoie corriger la saisie, là où « montant invalide » envoie chercher.
    """
    with pytest.raises(Exception) as refus:
        facturation.emettre_un_recu(facture_signee, moyens=[
            {'mecanisme': 'NU', 'montant': Decimal('50.00')},
            {'mecanisme': 'CC', 'montant': Decimal('40.00')},
        ])

    message = str(refus.value)
    # Les DEUX nombres figurent au message : « 90,00 € au lieu de
    # 98,40 € » envoie corriger la saisie, la ou « montant invalide »
    # envoie chercher. Et ils portent leurs centimes -- un message sur un
    # ecart d'argent qui ecrirait « 98.4 » ferait chercher quarante
    # centimes la ou l'ecart est de huit euros quarante.
    assert '90,00' in message, message
    assert '98,40' in message, message


def test_le_deuxieme_moyen_doit_porter_son_montant(facture_signee):
    """« Le total » réparti sur plusieurs moyens n'a pas de sens.

    Le schéma rend `PaymentAmount` obligatoire ; le défaut « le total »
    ne peut donc valoir que pour un moyen unique.
    """
    with pytest.raises(Exception) as refus:
        facturation.emettre_un_recu(facture_signee, moyens=[
            {'mecanisme': 'NU', 'montant': Decimal('50.00')},
            {'mecanisme': 'CC'},
        ])

    assert 'montant' in str(refus.value)


def test_un_code_de_moyen_inconnu_est_refuse_sur_chaque_rangee(
        facture_signee):
    """Le contrôle porte sur TOUTES les rangées, pas sur la première.

    Un contrôle posé sur `paiements[0]` seul — ce que faisait l'écran de
    la facture — laisserait passer un code inventé en deuxième position,
    sur un document qui serait signé avant que le fichier ne le refuse.
    """
    with pytest.raises(Exception) as refus:
        facturation.emettre_un_recu(facture_signee, moyens=[
            {'mecanisme': 'NU', 'montant': Decimal('50.00')},
            {'mecanisme': 'XX', 'montant': Decimal('48.40')},
        ])

    assert 'XX' in str(refus.value)


# ═══ 2. LE FICHIER REMIS À L'ADMINISTRATION ════════════════════════════════

def test_le_saf_t_porte_un_bloc_par_moyen(entreprise, facture_signee):
    """Deux moyens, deux `Payment` — avec leur code et leur montant."""
    facturation.emettre_un_recu(facture_signee, moyens=[
        {'mecanisme': 'NU', 'montant': Decimal('50.00')},
        {'mecanisme': 'CC', 'montant': Decimal('48.40')},
    ])

    octets = export.composer(entreprise, date(2026, 1, 1),
                             date(2026, 12, 31))
    racine = ET.fromstring(octets)
    recu = racine.find(ESPACE + 'SourceDocuments/' + ESPACE + 'Payments/'
                       + ESPACE + 'Payment')

    paiements = recu.findall(ESPACE + 'PaymentMethod')
    assert len(paiements) == 2
    assert [p.find(ESPACE + 'PaymentMechanism').text
            for p in paiements] == ['NU', 'CC']
    assert [p.find(ESPACE + 'PaymentAmount').text
            for p in paiements] == ['50.00', '48.40']


def test_le_fichier_a_deux_moyens_reste_conforme_au_schema(entreprise,
                                                           facture_signee):
    """La preuve qui compte : le XSD de l'AT accepte le fichier."""
    facturation.emettre_un_recu(facture_signee, moyens=[
        {'mecanisme': 'NU', 'montant': Decimal('50.00')},
        {'mecanisme': 'CC', 'montant': Decimal('48.40')},
    ])

    octets = export.composer(entreprise, date(2026, 1, 1),
                             date(2026, 12, 31))
    anomalies = schema.valider(octets)

    assert not anomalies, anomalies


def test_une_facture_recu_a_deux_moyens_est_conforme(entreprise, cliente,
                                                     conformite):
    """La table 4.1 aussi : la facture-reçu porte ses moyens dans
    `Invoice`, et non dans la table des paiements."""
    facture = _facture(entreprise, cliente, 'FAC-0002')
    document = facturation.emettre_pour_facture(
        facture, type_document='FR', paiements=[
            # LA DATE EST EXIGÉE, ET LA RÈGLE LE DIT.
            #
            # `emettre_pour_facture` ne l'invente pas : le schéma rend
            # `PaymentDate` obligatoire, et une date devinée sur une
            # quittance serait signée. L'écran la fournit depuis le champ
            # de l'encaissement ; un appel direct doit en faire autant.
            {'mecanisme': 'NU', 'montant': Decimal('50.00'),
             'date': date(2026, 3, 7)},
            {'mecanisme': 'MB', 'montant': Decimal('48.40'),
             'date': date(2026, 3, 7)},
        ])

    assert len(document.paiements) == 2

    octets = export.composer(entreprise, date(2026, 1, 1),
                             date(2026, 12, 31))
    assert not schema.valider(octets), schema.valider(octets)

    racine = ET.fromstring(octets)
    for element in racine.iter(ESPACE + 'Invoice'):
        if element.find(ESPACE + 'InvoiceNo').text == document.numero:
            totaux = element.find(ESPACE + 'DocumentTotals')
            assert len(totaux.findall(ESPACE + 'Payment')) == 2
            break
    else:
        pytest.fail('la facture-reçu n’est pas dans le fichier')


# ═══ 3. L'ÉCRAN DU REÇU ════════════════════════════════════════════════════

@pytest.fixture
def navigateur(client, django_user_model, entreprise, monkeypatch):
    utilisateur = django_user_model.objects.create_user(
        username='pedro', password='mot-de-passe-de-test', is_staff=True)
    client.force_login(utilisateur)

    from apps.fiscal_pt import views
    monkeypatch.setattr(views, '_company', lambda request: entreprise)
    return client


def _poste(**extra):
    """Le POST du formulaire de reçu, formset compris."""
    donnees = {
        'montant': '98.40',
        'date_encaissement': '2026-03-10',
        'description': '',
        'moyens-TOTAL_FORMS': '3',
        'moyens-INITIAL_FORMS': '0',
        'moyens-MIN_NUM_FORMS': '0',
        'moyens-MAX_NUM_FORMS': '1000',
        'moyens-0-mecanisme': '',
        'moyens-0-montant': '',
        'moyens-1-mecanisme': '',
        'moyens-1-montant': '',
        'moyens-2-mecanisme': '',
        'moyens-2-montant': '',
    }
    donnees.update(extra)
    return donnees


def test_l_ecran_emet_un_recu_a_deux_moyens(navigateur, facture_signee):
    """LA MESURE QUI COMPTE : un POST, et deux moyens figés.

    C'est cette voie-là qui manquait. Le reste — modèle, règle, SAF-T —
    l'acceptait déjà.
    """
    from apps.fiscal_pt.models import RecuFiscal

    navigateur.post(
        reverse('fiscal_pt:recu_sur_facture', args=[facture_signee.pk]),
        _poste(**{'moyens-0-mecanisme': 'NU', 'moyens-0-montant': '50.00',
                  'moyens-1-mecanisme': 'CC', 'moyens-1-montant': '48.40'}))

    recu = RecuFiscal.objects.get(company=facture_signee.company)
    assert len(recu.paiements) == 2
    assert [p['mecanisme'] for p in recu.paiements] == ['NU', 'CC']


def test_l_ecran_garde_le_cas_courant_a_un_moyen(navigateur, facture_signee):
    from apps.fiscal_pt.models import RecuFiscal

    navigateur.post(
        reverse('fiscal_pt:recu_sur_facture', args=[facture_signee.pk]),
        _poste(**{'moyens-0-mecanisme': 'TB'}))

    recu = RecuFiscal.objects.get(company=facture_signee.company)
    assert len(recu.paiements) == 1
    assert Decimal(recu.paiements[0]['montant']) == Decimal('98.40')


def test_un_montant_sans_moyen_ne_disparait_pas_en_silence(navigateur,
                                                           facture_signee):
    """LE PIÈGE DES RANGÉES FACULTATIVES.

    Trois rangées sont offertes sans être imposées, donc les vides sont
    ignorées. Mais une rangée où quelqu'un a tapé 40 € en oubliant de
    choisir le moyen ne doit pas être ignorée comme les autres : la somme
    serait alors inférieure au total, et le refus parlerait d'un écart de
    40 € sans dire d'où il vient.
    """
    from apps.fiscal_pt.models import RecuFiscal

    reponse = navigateur.post(
        reverse('fiscal_pt:recu_sur_facture', args=[facture_signee.pk]),
        _poste(**{'moyens-0-mecanisme': 'NU', 'moyens-0-montant': '58.40',
                  'moyens-1-montant': '40.00'}))

    assert not RecuFiscal.objects.filter(
        company=facture_signee.company).exists()
    assert 'moyen de paiement' in reponse.content.decode('utf-8')


def test_l_ecran_du_recu_offre_bien_plusieurs_rangees(navigateur,
                                                      facture_signee):
    """LA GARDE CONTRE LE DÉFAUT QU'ON VIENT DE FERMER.

    Un formset branché dans la vue et absent du gabarit laisse l'écran
    exactement comme avant — et c'est la forme qu'a prise ce défaut-ci
    plusieurs fois dans ce dépôt. On mesure donc le HTML rendu : le
    formulaire de gestion, et trois champs de montant.
    """
    html = navigateur.get(
        reverse('fiscal_pt:recu_sur_facture',
                args=[facture_signee.pk])).content.decode('utf-8')

    assert 'moyens-TOTAL_FORMS' in html
    assert html.count('name="moyens-') >= 6
    assert 'moyens-2-mecanisme' in html


def test_les_rangees_ne_sont_pas_pre_remplies(navigateur, facture_signee):
    """LE DÉFAUT QUE LE FORMSET A FAILLI INTRODUIRE.

    `initial='TB'` sur un champ de formset s'applique à CHAQUE rangée. Les
    trois arrivaient donc pré-sélectionnées au virement, et un utilisateur
    qui ne remplit que la première aurait émis un reçu portant TROIS
    moyens — dont deux sans montant, ce que la règle refuse. L'écran
    aurait été inutilisable dans son cas le plus courant.

    On mesure le HTML : aucune option « selected », et un choix vide en
    tête de chaque menu.
    """
    html = navigateur.get(
        reverse('fiscal_pt:recu_sur_facture',
                args=[facture_signee.pk])).content.decode('utf-8')

    import re

    debut = html.index('name="moyens-0-mecanisme"')
    fin = html.index('name="moyens-2-montant"')
    bloc = html[debut:fin]

    # C'est l'option VIDE qui porte « selected », et c'est le but : aucun
    # moyen réel n'est pré-choisi. On mesure donc l'absence de « selected »
    # sur une option qui porte un code, et non son absence totale.
    pre_choisis = re.findall(r'<option value="(\w+)"[^>]*selected', bloc)
    assert not pre_choisis, (
        'ces moyens arrivent pré-remplis : %s — trois rangées pré-remplies '
        'font trois paiements' % pre_choisis)
    assert bloc.count('Choisir le moyen') == 3


def test_aucun_moyen_choisi_est_refuse(navigateur, facture_signee):
    """« Au moins un » est posé sur le JEU, pas sur une rangée.

    Rendre le champ obligatoire rangée par rangée en imposerait trois ;
    le laisser facultatif partout sans contrôle d'ensemble laisserait
    émettre une quittance qui ne dit pas comment la somme est arrivée.
    """
    from apps.fiscal_pt.models import RecuFiscal

    reponse = navigateur.post(
        reverse('fiscal_pt:recu_sur_facture', args=[facture_signee.pk]),
        _poste())

    assert not RecuFiscal.objects.filter(
        company=facture_signee.company).exists()
    assert 'au moins un moyen' in reponse.content.decode('utf-8')


# ═══ 4. L'ÉCRAN DE LA FACTURE-REÇU ═════════════════════════════════════════

@pytest.fixture
def ventes(client, django_user_model, entreprise, monkeypatch):
    """Un client authentifié sur l'écran des ventes."""
    from apps.accounts.models import UserProfile

    utilisateur = django_user_model.objects.create_user(
        username='ana', password='mot-de-passe-de-test', is_staff=True,
        is_superuser=True)
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    if hasattr(profil, 'companies'):
        profil.companies.add(entreprise)
    if hasattr(profil, 'current_company'):
        profil.current_company = entreprise
        profil.save()

    client.force_login(utilisateur)
    session = client.session
    session['current_company_id'] = entreprise.pk
    session.save()
    return client


def test_l_ecran_de_la_facture_emet_une_FR_a_deux_moyens(ventes, entreprise,
                                                         cliente, conformite):
    from apps.fiscal_pt.models import DocumentFiscal

    facture = _facture(entreprise, cliente, 'FAC-0003')

    ventes.post(reverse('sales:invoice_send', args=[facture.pk]), {
        'type_document': 'FR',
        'mecanisme': ['NU', 'MB', ''],
        'montant_paiement': ['50.00', '48.40', ''],
        'date_encaissement': '2026-03-07',
    })

    document = DocumentFiscal.objects.get(source_id=facture.pk,
                                          source_modele='invoice')
    assert len(document.paiements) == 2
    assert [p['mecanisme'] for p in document.paiements] == ['NU', 'MB']


def test_l_ecran_de_la_facture_garde_le_cas_a_un_moyen(ventes, entreprise,
                                                       cliente, conformite):
    """Un seul moyen, montant vide : l'émission y met le total."""
    from apps.fiscal_pt.models import DocumentFiscal

    facture = _facture(entreprise, cliente, 'FAC-0004')

    ventes.post(reverse('sales:invoice_send', args=[facture.pk]), {
        'type_document': 'FR',
        'mecanisme': ['TB', '', ''],
        'montant_paiement': ['', '', ''],
        'date_encaissement': '2026-03-07',
    })

    document = DocumentFiscal.objects.get(source_id=facture.pk,
                                          source_modele='invoice')
    assert len(document.paiements) == 1
    assert Decimal(document.paiements[0]['montant']) == document.total


def test_un_montant_sans_moyen_est_refuse_sur_la_facture_aussi(
        ventes, entreprise, cliente, conformite):
    from apps.fiscal_pt.models import DocumentFiscal

    facture = _facture(entreprise, cliente, 'FAC-0005')

    ventes.post(reverse('sales:invoice_send', args=[facture.pk]), {
        'type_document': 'FR',
        'mecanisme': ['NU', '', ''],
        'montant_paiement': ['58.40', '40.00', ''],
        'date_encaissement': '2026-03-07',
    })

    assert not DocumentFiscal.objects.filter(source_id=facture.pk).exists()
    facture.refresh_from_db()
    assert facture.status == 'draft', (
        'la facture a été marquée envoyée alors que rien n’a été signé')


def test_l_ecran_de_la_facture_offre_bien_plusieurs_rangees(
        ventes, entreprise, cliente, conformite):
    """La même garde, sur l'autre écran.

    Le champ `montant_paiement` existe dans la vue. S'il n'existe pas
    dans le HTML, aucun utilisateur ne peut s'en servir — et c'est
    précisément la forme du défaut d'origine.
    """
    facture = _facture(entreprise, cliente, 'FAC-0006')

    html = ventes.get(reverse('sales:invoice_detail',
                              args=[facture.pk])).content.decode('utf-8')

    assert html.count('name="mecanisme"') == 3
    assert html.count('name="montant_paiement"') == 3


# ═══ 5. CE QUE LES QUATORZE CODES AUTORISENT ═══════════════════════════════

def test_les_quatorze_codes_du_schema_sont_tous_offerts(navigateur,
                                                        facture_signee):
    """Un code absent du menu est un moyen de paiement qu'on ne peut pas
    déclarer — et c'est l'administration qui en fixe la liste, pas nous."""
    html = navigateur.get(
        reverse('fiscal_pt:recu_sur_facture',
                args=[facture_signee.pk])).content.decode('utf-8')

    for code, _libelle in tipos.MECANISMES_DE_PAIEMENT:
        assert f'value="{code}"' in html, code
