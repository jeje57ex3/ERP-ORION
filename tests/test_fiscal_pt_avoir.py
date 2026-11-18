"""La note de crédit : la seule voie légale de correction.

POURQUOI CE FICHIER EXISTE

`DocumentFiscal.save()` refuse de modifier un document émis, et son
message dit « Émettez une note de crédit pour le corriger ». Tant que
cette fonction n'existait pas, ce message désignait quelque chose
d'inexistant — et la seule voie légale de correction était fermée.

CE QUE CES TESTS DÉFENDENT

1. Qu'un avoir désigne TOUJOURS le document qu'il rectifie. Un avoir sans
   référence reste orphelin dans le SAF-T : le fichier est valide au
   schéma, et le contrôle relève l'incohérence.
2. Qu'un avoir porte son motif. C'est lui qui distingue un geste
   commercial d'une erreur de facturation.
3. Qu'on ne puisse pas créditer deux fois le même montant. Deux avoirs
   complets sont parfaitement valides pris séparément — rien dans la
   chaîne de signatures ne les dénoncerait.
"""
from datetime import date
from decimal import Decimal
from xml.etree import ElementTree as ET

import pytest
from cryptography.fernet import Fernet
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from django.urls import reverse

from apps.core.models import Company
from apps.crm.models import Customer
from apps.fiscal_pt import export, facturation
from apps.fiscal_pt.models import (CleDeSignature, DocumentFiscal,
                                   ParametresFiscauxPT, SerieFiscale)
from apps.sales.models import Invoice, InvoiceLine

ESPACE = '{urn:OECD:StandardAuditFile-Tax:PT_1.04_01}'


@pytest.fixture
def chiffrement(settings):
    settings.ORION_SECRET_ENCRYPTION_KEY = Fernet.generate_key().decode()


@pytest.fixture
def entreprise(db):
    return Company.objects.create(name='Orion Lusitana', slug='orion-avoir')


@pytest.fixture
def cliente(entreprise):
    return Customer.objects.create(company=entreprise, name='Cliente Lda',
                                   nif='500000000', country='Portugal')


@pytest.fixture
def facture(entreprise, cliente):
    facture = Invoice.objects.create(
        company=entreprise, customer=cliente, number='FAC-2026-0001',
        issue_date=date(2026, 3, 7), status='draft')
    InvoiceLine.objects.create(
        invoice=facture, description='Instalação elétrica',
        quantity=Decimal('1'), unit_price=Decimal('100.00'),
        vat_rate=Decimal('23'))
    facture.refresh_from_db()
    return facture


@pytest.fixture
def conformite(entreprise, chiffrement):
    """L'entreprise prête à émettre, avec ses DEUX séries."""
    parametres = ParametresFiscauxPT.de(entreprise)
    parametres.est_actif = True
    parametres.nif = '123456789'
    parametres.save()
    cle = CleDeSignature.creer(entreprise)

    factures = SerieFiscale.objects.create(
        company=entreprise, type_document='FT', nom='A',
        code_de_validation='CSDF7T5H', cle=cle)
    avoirs = SerieFiscale.objects.create(
        company=entreprise, type_document='NC', nom='A',
        code_de_validation='RQD8L6DG', cle=cle)
    return factures, avoirs


@pytest.fixture
def signee(facture, conformite):
    return facturation.emettre_pour_facture(facture)


# ── L'émission ───────────────────────────────────────────────────────────────

def test_un_avoir_rectifie_la_facture_signee(facture, signee):
    avoir = facturation.emettre_une_note_de_credit(
        facture, 'Devolução de mercadoria')

    assert avoir.numero == 'NC A/1'
    assert avoir.document_rectifie == signee
    assert avoir.motif_rectification == 'Devolução de mercadoria'
    assert avoir.verifier() is True


def test_l_avoir_reprend_le_montant_de_la_facture(facture, signee):
    avoir = facturation.emettre_une_note_de_credit(facture, 'Erro')

    assert avoir.total == signee.total
    assert avoir.total_base == signee.total_base
    assert avoir.total_taxes == signee.total_taxes


def test_l_avoir_a_sa_propre_chaine_de_signatures(facture, signee,
                                                  conformite):
    """Une chaîne par série. L'avoir ne suit pas la facture : il ouvre la
    chaîne de la série NC."""
    avoir = facturation.emettre_une_note_de_credit(facture, 'Erro')

    assert avoir.signature_precedente == ''
    assert avoir.serie.type_document == 'NC'
    assert avoir.atcud == 'RQD8L6DG-1'


def test_l_avoir_reprend_les_lignes_figees_et_non_la_facture(facture, signee):
    """La facture a pu changer depuis. Un avoir doit créditer ce qui a
    RÉELLEMENT été facturé, pas l'état actuel du dossier."""
    ligne = facture.lines.first()
    ligne.unit_price = Decimal('999.00')
    ligne.description = 'Modifiée après coup'
    ligne.save()

    avoir = facturation.emettre_une_note_de_credit(facture, 'Erro')

    assert avoir.lignes[0]['description'] == 'Instalação elétrica'
    assert avoir.lignes[0]['base'] == '100.00'
    assert avoir.total == Decimal('123.00')


def test_l_avoir_conserve_l_acquereur(facture, signee):
    avoir = facturation.emettre_une_note_de_credit(facture, 'Erro')

    assert avoir.nif_acquereur == '500000000'
    assert '*B:500000000*' in avoir.contenu_qr


# ── Ce qui est refusé ────────────────────────────────────────────────────────

def test_un_avoir_sans_motif_est_refuse(facture, signee):
    """Le motif distingue un geste commercial d'une erreur de
    facturation, et le SAF-T le transporte dans « Reason »."""
    for vide in ('', '   ', None):
        with pytest.raises(ValidationError, match='motif'):
            facturation.emettre_une_note_de_credit(facture, vide)

    assert DocumentFiscal.objects.filter(serie__type_document='NC').count() == 0


def test_un_avoir_sur_une_facture_non_signee_est_refuse(facture, conformite):
    """Une facture encore en brouillon se modifie directement : il n'y a
    rien à rectifier."""
    with pytest.raises(ValidationError, match='pas été signée'):
        facturation.emettre_une_note_de_credit(facture, 'Erro')


def test_sans_serie_nc_l_emission_le_dit(facture, conformite):
    """Message exploitable plutôt qu'échec obscur : il faut déclarer une
    série de type NC avant de pouvoir corriger quoi que ce soit."""
    facturation.emettre_pour_facture(facture)
    conformite[1].est_active = False
    conformite[1].save()

    with pytest.raises(ValidationError, match='série active'):
        facturation.emettre_une_note_de_credit(facture, 'Erro')


def test_un_second_avoir_complet_rend_le_premier(facture, signee):
    """CE QUE CE CONTRÔLE ÉVITE.

    Deux avoirs complets créditeraient deux fois le client. Pris
    séparément, les deux documents sont parfaitement valides et leurs
    signatures impeccables : rien dans la chaîne ne le dénoncerait.
    """
    premier = facturation.emettre_une_note_de_credit(facture, 'Erro')
    second = facturation.emettre_une_note_de_credit(facture, 'Erro encore')

    assert premier.pk == second.pk
    assert DocumentFiscal.objects.filter(
        serie__type_document='NC').count() == 1


def test_une_facture_ne_peut_pas_rectifier_une_autre(facture, signee,
                                                     conformite):
    """Un document de type FT ne rectifie rien. Sans ce contrôle, un avoir
    pourrait être émis dans la série des factures, et le SAF-T le
    compterait au crédit."""
    with pytest.raises(ValidationError, match='ne rectifie rien'):
        DocumentFiscal.emettre(
            serie=conformite[0], date_document=date(2026, 3, 8),
            lignes=[{'description': 'X', 'base': Decimal('10'),
                     'taux': Decimal('23'), 'tva': Decimal('2.30')}],
            nif_emetteur='123456789', document_rectifie=signee)


def test_une_note_de_credit_sans_document_rectifie_est_refusee(conformite):
    with pytest.raises(ValidationError, match='doit désigner'):
        DocumentFiscal.emettre(
            serie=conformite[1], date_document=date(2026, 3, 8),
            lignes=[{'description': 'X', 'base': Decimal('10'),
                     'taux': Decimal('23'), 'tva': Decimal('2.30')}],
            nif_emetteur='123456789')


def test_une_facture_d_une_autre_entreprise_ne_peut_pas_etre_rectifiee(
        signee, conformite, chiffrement):
    autre = Company.objects.create(name='Autre SA', slug='autre-avoir')
    cle = CleDeSignature.creer(autre)
    serie = SerieFiscale.objects.create(company=autre, type_document='NC',
                                        nom='A', cle=cle)

    with pytest.raises(ValidationError, match='autre entreprise'):
        DocumentFiscal.emettre(
            serie=serie, date_document=date(2026, 3, 8),
            lignes=[{'description': 'X', 'base': Decimal('10'),
                     'taux': Decimal('23'), 'tva': Decimal('2.30')}],
            nif_emetteur='500000000', document_rectifie=signee)


# ── Le SAF-T ─────────────────────────────────────────────────────────────────

def test_le_saft_designe_le_document_rectifie(facture, signee, entreprise):
    """Sans cette référence, l'avoir reste orphelin : le fichier est
    valide au schéma, et le contrôle relève l'incohérence."""
    facturation.emettre_une_note_de_credit(facture, 'Devolução')

    racine = ET.fromstring(export.composer(
        entreprise, date(2026, 1, 1), date(2026, 12, 31)))
    documents = racine.findall(
        f'{ESPACE}SourceDocuments/{ESPACE}SalesInvoices/{ESPACE}Invoice')

    avoir = [d for d in documents
             if d.find(f'{ESPACE}InvoiceType').text == 'NC'][0]
    ligne = avoir.find(f'{ESPACE}Line')

    assert ligne.find(
        f'{ESPACE}References/{ESPACE}Reference').text == 'FT A/1'
    assert ligne.find(
        f'{ESPACE}References/{ESPACE}Reason').text == 'Devolução'


def test_l_avoir_va_au_debit_et_la_facture_au_credit(facture, signee,
                                                     entreprise):
    """Les inverser donne un fichier qui s'équilibre à l'envers, et le
    validateur l'accepte sans rien dire."""
    facturation.emettre_une_note_de_credit(facture, 'Devolução')

    racine = ET.fromstring(export.composer(
        entreprise, date(2026, 1, 1), date(2026, 12, 31)))
    ventes = racine.find(f'{ESPACE}SourceDocuments/{ESPACE}SalesInvoices')

    assert ventes.find(f'{ESPACE}NumberOfEntries').text == '2'
    assert ventes.find(f'{ESPACE}TotalCredit').text == '100.00'
    assert ventes.find(f'{ESPACE}TotalDebit').text == '100.00'


def test_le_motif_figure_aussi_dans_l_etat_du_document(facture, signee,
                                                       entreprise):
    """`DocumentStatus/Reason` et `Line/References/Reason` : le schéma
    attend le motif aux deux endroits."""
    facturation.emettre_une_note_de_credit(facture, 'Erro de faturação')

    racine = ET.fromstring(export.composer(
        entreprise, date(2026, 1, 1), date(2026, 12, 31)))
    avoir = [d for d in racine.findall(
        f'{ESPACE}SourceDocuments/{ESPACE}SalesInvoices/{ESPACE}Invoice')
        if d.find(f'{ESPACE}InvoiceType').text == 'NC'][0]

    assert avoir.find(
        f'{ESPACE}DocumentStatus/{ESPACE}Reason').text == 'Erro de faturação'


def test_le_saft_refuse_un_avoir_sans_reference():
    """Le garde-fou de `saft` lui-même, indépendamment des modèles : un
    avoir composé à la main sans référence doit être refusé."""
    from apps.fiscal_pt import saft

    with pytest.raises(saft.ErreurSAFT, match='rectifie'):
        saft.ligne(1, {'code_produit': 'P1', 'description': 'X',
                       'date': date(2026, 3, 7), 'montant': Decimal('10'),
                       'taux': Decimal('23'), 'code_de_taux': 'NOR'},
                   type_document='NC')


# ── L'écran ──────────────────────────────────────────────────────────────────

def _ouvrir(chemin, entreprise, utilisateur, pk, donnees=None):
    from apps.fiscal_pt.views import note_de_credit

    fabrique = RequestFactory()
    requete = (fabrique.post(chemin, donnees) if donnees is not None
               else fabrique.get(chemin))
    requete.user = utilisateur
    requete.current_company = entreprise
    requete.session = {}
    requete._messages = FallbackStorage(requete)
    reponse = note_de_credit(requete, pk)
    return reponse, [str(m) for m in requete._messages]


@pytest.fixture
def utilisateur(db, django_user_model):
    return django_user_model.objects.create_user(
        username='pedro', password='mot-de-passe-de-test')


def test_l_ecran_d_avoir_s_affiche(facture, signee, entreprise, utilisateur):
    chemin = reverse('fiscal_pt:note_de_credit', args=[facture.pk])
    reponse, _ = _ouvrir(chemin, entreprise, utilisateur, facture.pk)

    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert signee.numero in contenu
    assert 'Motif de la rectification' in contenu


def test_l_avoir_s_emet_depuis_l_ecran(facture, signee, entreprise,
                                       utilisateur):
    chemin = reverse('fiscal_pt:note_de_credit', args=[facture.pk])
    reponse, messages = _ouvrir(chemin, entreprise, utilisateur, facture.pk,
                                {'motif': 'Devolução de mercadoria'})

    assert reponse.status_code == 302
    avoir = DocumentFiscal.objects.get(serie__type_document='NC')
    assert avoir.motif_rectification == 'Devolução de mercadoria'
    assert any(avoir.numero in m for m in messages)


def test_l_ecran_refuse_un_motif_vide_sans_perdre_la_saisie(facture, signee,
                                                            entreprise,
                                                            utilisateur):
    chemin = reverse('fiscal_pt:note_de_credit', args=[facture.pk])
    reponse, messages = _ouvrir(chemin, entreprise, utilisateur, facture.pk,
                                {'motif': ''})

    assert reponse.status_code == 200
    assert DocumentFiscal.objects.filter(
        serie__type_document='NC').count() == 0
    assert any('motif' in m for m in messages)


def test_l_ecran_d_une_facture_non_signee_l_explique(facture, conformite,
                                                     entreprise, utilisateur):
    chemin = reverse('fiscal_pt:note_de_credit', args=[facture.pk])
    reponse, _ = _ouvrir(chemin, entreprise, utilisateur, facture.pk)

    assert reponse.status_code == 200
    assert 'rien à rectifier' in reponse.content.decode()


def test_une_facture_d_une_autre_entreprise_est_introuvable(facture, signee,
                                                            utilisateur):
    autre = Company.objects.create(name='Autre SA', slug='autre-avoir-2')
    chemin = reverse('fiscal_pt:note_de_credit', args=[facture.pk])

    from django.http import Http404
    with pytest.raises(Http404):
        _ouvrir(chemin, autre, utilisateur, facture.pk)


# ── L'ambiguite du lien source ───────────────────────────────────────────────

def test_la_facture_garde_son_propre_document_apres_un_avoir(facture, signee):
    """LE DEFAUT QUE CE TEST FERME, ET IL ETAIT SERIEUX.

    Un avoir porte le MEME lien source que la facture qu'il rectifie --
    c'est voulu, pour la tracabilite. `document_pour` rendait donc le plus
    recent, c'est-a-dire l'avoir.

    Mesure : un deuxieme avoir sur la meme facture donnait « NC A/2 »
    rectifiant « NC A/1 », au lieu de rendre le premier. Les deux
    documents etaient parfaitement signes, leur chaine impeccable, et le
    client etait credite deux fois. L'ecran de la facture affichait de
    surcroit l'avoir comme sa propre preuve.
    """
    facturation.emettre_une_note_de_credit(facture, 'Devolução')

    assert facturation.document_pour(facture) == signee
    assert facturation.document_pour(facture).serie.type_document == 'FT'


def test_les_rectifications_se_listent_a_part(facture, signee):
    premier = facturation.emettre_une_note_de_credit(facture, 'Devolução')

    rectifications = list(facturation.rectifications_de(facture))

    assert rectifications == [premier]
    assert signee not in rectifications


def test_un_avoir_ne_rectifie_jamais_un_avoir(facture, signee):
    """Consequence directe du defaut precedent : la cible d'un avoir doit
    toujours etre la facture, jamais l'avoir qui l'a precede."""
    premier = facturation.emettre_une_note_de_credit(facture, 'Devolução')
    second = facturation.emettre_une_note_de_credit(facture, 'Autre motif')

    assert second.pk == premier.pk
    assert premier.document_rectifie == signee
    assert premier.document_rectifie.serie.type_document == 'FT'
