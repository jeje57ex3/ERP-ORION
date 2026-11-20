# -*- coding: utf-8 -*-
"""L'annulation d'un document émis, et la date que le schéma sépare.

CE QUI MANQUAIT POUR LA CERTIFICATION

`save()` refuse toute modification d'un document émis — sa signature porte
sur son contenu, et la chaîne de la série en dépend. L'état « A » ne
pouvait donc pas être posé sur un document existant : la seule voie de
correction était l'avoir, qui est légale, mais un programme certifié doit
aussi savoir annuler.

L'ANNULATION NE PASSE PAS PAR `save()`

Elle écrit trois colonnes par un `update()` de requête. L'interdiction de
modifier reste donc ABSOLUE — on ne l'assouplit pas, on ne la contourne
pas par un drapeau qu'il faudrait penser à remettre. Le contenu signé
n'est jamais touché, et la signature reste valable : elle couvre ce que le
document DISAIT, pas son état administratif, que le SAF-T porte à part
dans `DocumentStatus`.

DEUX DÉFAUTS QUE L'ANNULATION A RÉVÉLÉS, ET QUI NE POUVAIENT PAS SE VOIR
AVANT ELLE

1. `PaymentStatusDate`, `InvoiceStatusDate`, `MovementStatusDate` et
   `WorkStatusDate` recevaient tous l'horodatage d'ÉMISSION. Le schéma les
   distingue de `SystemEntryDate` : employer la même valeur pour les deux
   fait déclarer qu'un document annulé est NÉ annulé.

2. `export.py` passait `motif_rectification` comme `Reason` du
   `DocumentStatus`. Or ce champ dit pourquoi le document est dans cet
   état — pourquoi il a été annulé — et non pourquoi un avoir rectifie une
   facture. Deux informations différentes, déclarées au même endroit. La
   rectification garde sa place, dans le bloc `References` de la ligne.
"""
from datetime import date, datetime
from datetime import timezone as dt_timezone
from decimal import Decimal

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Company
from apps.crm.models import Customer
from apps.fiscal_pt import export, facturation
from apps.fiscal_pt.models import (CleDeSignature, DocumentFiscal,
                                   MouvementFiscal, ParametresFiscauxPT,
                                   RecuFiscal, SerieFiscale)
from apps.sales.models import Invoice, InvoiceLine

pytestmark = pytest.mark.django_db


@pytest.fixture
def chiffrement(settings):
    settings.ORION_SECRET_ENCRYPTION_KEY = Fernet.generate_key().decode()


@pytest.fixture
def entreprise(db):
    return Company.objects.create(name='Orion Lusitana', slug='orion-ann')


@pytest.fixture
def cliente(entreprise):
    return Customer.objects.create(company=entreprise, name='Cliente Lda',
                                   nif='500000000', country='Portugal')


@pytest.fixture
def series(entreprise, chiffrement):
    parametres = ParametresFiscauxPT.de(entreprise)
    parametres.est_actif = True
    parametres.nif = '123456789'
    parametres.save()
    cle = CleDeSignature.creer(entreprise)

    codes = {'FT': 'CSDF7T5H', 'NC': 'KSMLFPQZ', 'RG': 'JFFNVTC7',
             'GT': 'LMNOPQRS'}
    return {type_document: SerieFiscale.objects.create(
                company=entreprise, type_document=type_document, nom='A',
                code_de_validation=code, cle=cle)
            for type_document, code in codes.items()}


def facture_de(document):
    """La facture de l'ERP dont un document fiscal est issu."""
    return Invoice.objects.get(pk=document.source_id)


def _facture_signee(entreprise, cliente, series, numero='FAC-0001'):
    facture = Invoice.objects.create(
        company=entreprise, customer=cliente, number=numero,
        issue_date=date(2026, 3, 7), status='draft')
    InvoiceLine.objects.create(
        invoice=facture, description='Instalação elétrica',
        quantity=Decimal('1'), unit_price=Decimal('100.00'),
        vat_rate=Decimal('23'))
    facture.refresh_from_db()
    facturation.emettre_pour_facture(facture)
    facture.refresh_from_db()
    return DocumentFiscal.objects.get(source_id=facture.pk,
                                      source_modele='invoice')


# ═══ 1. CE QUE L'ANNULATION FAIT, ET CE QU'ELLE NE TOUCHE PAS ══════════════

def test_un_document_s_annule_avec_son_motif_et_sa_date(entreprise, cliente,
                                                        series):
    document = _facture_signee(entreprise, cliente, series)
    assert document.etat == 'N'

    document.annuler('Erreur de saisie sur le client')

    document.refresh_from_db()
    assert document.etat == 'A'
    assert document.motif_etat == 'Erreur de saisie sur le client'
    assert document.etat_change_le is not None


def test_le_contenu_signe_n_est_pas_touche(entreprise, cliente, series):
    """LA SIGNATURE RESTE VALABLE, et c'est tout l'intérêt du procédé.

    Elle couvre ce que le document DISAIT — sa date, son numéro, son
    total, la signature précédente — et non son état administratif, que le
    SAF-T déclare à part. Annuler sans re-signer laisse donc la chaîne de
    la série vérifiable d'un bout à l'autre.
    """
    document = _facture_signee(entreprise, cliente, series)
    signature = document.signature
    message = document.message_signe
    total = document.total

    document.annuler('Annulation demandée par le client')

    document.refresh_from_db()
    assert document.signature == signature
    assert document.message_signe == message
    assert document.total == total
    assert document.verifier() is True


def test_l_interdiction_de_modifier_reste_absolue(entreprise, cliente,
                                                  series):
    """On n'assouplit pas `save()` pour annuler.

    L'annulation écrit trois colonnes par un `update()` de requête, qui ne
    passe pas par `save()`. Un drapeau qui autoriserait temporairement la
    modification serait à remettre à chaque fois, et c'est le genre de
    chose qu'on oublie.
    """
    document = _facture_signee(entreprise, cliente, series)
    document.annuler('Erreur')

    document.total = Decimal('1.00')
    with pytest.raises(ValidationError):
        document.save()


# ═══ 2. CE QUI EST REFUSÉ ══════════════════════════════════════════════════

def test_une_annulation_sans_motif_est_refusee(entreprise, cliente, series):
    """Le schéma rend `Reason` optionnel. Nous non.

    Une annulation sans justification ne vaut rien pour un contrôle : le
    validateur accepte le fichier, et l'inspecteur demande pourquoi. Autant
    l'exiger au moment où quelqu'un sait répondre.
    """
    document = _facture_signee(entreprise, cliente, series)

    for motif in ('', '   ', None):
        with pytest.raises(ValidationError) as refus:
            document.annuler(motif)
        assert 'pourquoi' in str(refus.value)

    document.refresh_from_db()
    assert document.etat == 'N'


def test_un_document_deja_annule_ne_s_annule_pas_deux_fois(
        entreprise, cliente, series):
    document = _facture_signee(entreprise, cliente, series)
    document.annuler('Première annulation')

    with pytest.raises(ValidationError) as refus:
        document.annuler('Deuxième')
    assert 'déjà annulé' in str(refus.value)

    document.refresh_from_db()
    assert document.motif_etat == 'Première annulation'


def test_un_document_facture_ne_s_annule_pas(entreprise, cliente, series):
    """L'état « F » dit qu'une facture le reprend.

    L'annuler laisserait cette facture appuyée sur un document annulé. La
    voie est alors l'avoir, qui laisse la trace des deux.
    """
    document = _facture_signee(entreprise, cliente, series)
    DocumentFiscal.objects.filter(pk=document.pk).update(etat='F')
    document.refresh_from_db()

    with pytest.raises(ValidationError) as refus:
        document.annuler('Tentative')
    assert 'avoir' in str(refus.value)


def test_le_motif_est_borne_a_cinquante_caracteres(entreprise, cliente,
                                                   series):
    """Le schéma tronque `Reason` à 50. On borne ici plutôt que de laisser
    l'export couper une phrase en deux."""
    document = _facture_signee(entreprise, cliente, series)
    document.annuler('x' * 120)

    document.refresh_from_db()
    assert len(document.motif_etat) == 50


# ═══ 3. LES ÉTATS ANNULABLES DIFFÈRENT D'UNE TABLE À L'AUTRE ═══════════════

def test_un_transport_en_cours_s_annule(series):
    """« T » n'existe que dans la table 4.2, et il est annulable.

    Un transport interrompu en route doit pouvoir l'être : la marchandise
    revient. Aucune autre table ne connaît cet état.
    """
    mouvement = MouvementFiscal.emettre(
        serie=series['GT'], date_document=date(2026, 3, 8),
        lignes=[{'designation': 'Câble', 'quantite': Decimal('10'),
                 'prix_unitaire': Decimal('1.20')}],
        nif_emetteur='123456789', identifiant_client='C1',
        debut_transport=timezone.make_aware(datetime(2026, 3, 8, 7, 30)),
        etat='T')

    mouvement.annuler('Transport interrompu, retour au dépôt')

    mouvement.refresh_from_db()
    assert mouvement.etat == 'A'


def test_une_facture_en_etat_resume_ne_s_annule_pas(entreprise, cliente,
                                                    series):
    """Seul « N » est annulable pour un document de facturation.

    « R » — résumé d'autres documents — et « S » ne le sont pas : la liste
    `ETATS_ANNULABLES` est propre à chaque famille, comme les quatre
    listes d'états du schéma.
    """
    document = _facture_signee(entreprise, cliente, series)
    DocumentFiscal.objects.filter(pk=document.pk).update(etat='R')
    document.refresh_from_db()

    with pytest.raises(ValidationError):
        document.annuler('Tentative')


# ═══ 4. LE SAF-T : LA DATE D'ÉTAT, ET LE MOTIF AU BON ENDROIT ══════════════

ESPACE = '{urn:OECD:StandardAuditFile-Tax:PT_1.04_01}'


def test_le_fichier_porte_la_date_du_changement_et_non_celle_d_emission(
        entreprise, cliente, series):
    """LE DÉFAUT QUE L'ANNULATION A RÉVÉLÉ.

    Les quatre `*StatusDate` recevaient l'horodatage d'ÉMISSION. Le schéma
    les distingue de `SystemEntryDate` : la même valeur pour les deux fait
    déclarer qu'un document annulé est né annulé.

    LA DATE D'ANNULATION EST ÉCARTÉE DE L'ÉMISSION À DESSEIN. Une
    annulation prononcée dans la seconde qui suit l'émission donnerait
    deux horodatages égaux à la seconde, et le test passerait sur un code
    qui recopie l'un dans l'autre. Six jours plus tard, il ne reste aucune
    ambiguïté sur ce que le fichier déclare.
    """
    from xml.etree import ElementTree as ET

    document = _facture_signee(entreprise, cliente, series)
    annule_le = timezone.make_aware(datetime(2026, 3, 13, 9, 45, 12))
    document.annuler('Erreur de saisie', quand=annule_le)

    octets = export.composer(entreprise, date(2026, 3, 1),
                             date(2026, 3, 31))
    racine = ET.fromstring(octets)
    facture = racine.find(ESPACE + 'SourceDocuments/' + ESPACE
                          + 'SalesInvoices/' + ESPACE + 'Invoice')
    etat = facture.find(ESPACE + 'DocumentStatus')

    assert etat.find(ESPACE + 'InvoiceStatus').text == 'A'
    assert etat.find(ESPACE + 'Reason').text == 'Erreur de saisie'

    # LE FICHIER DÉCLARE L'HEURE UTC, ET C'EST COHÉRENT AVEC LA SIGNATURE.
    #
    # `assinatura._horodatage` retire le fuseau d'un `timezone.now()`, qui
    # est en UTC ; `saft._horodatage` lit la colonne, que Django rend
    # également en UTC. Les deux coïncident donc, et l'administration
    # retombe bien sur notre signature en recalculant depuis la valeur
    # exportée. 09:45:12 à Paris s'écrit 08:45:12 dans le fichier.
    attendue = annule_le.astimezone(dt_timezone.utc).strftime(
        '%Y-%m-%dT%H:%M:%S')
    assert etat.find(ESPACE + 'InvoiceStatusDate').text == attendue

    # Et celle d'émission, qui est autre chose, n'a pas bougé.
    assert facture.find(ESPACE + 'SystemEntryDate').text != attendue


def test_un_document_non_annule_porte_toujours_sa_date_d_emission(
        entreprise, cliente, series):
    """LA CONTREPARTIE, sans laquelle la correction précédente serait une
    régression.

    `InvoiceStatusDate` est OBLIGATOIRE dans le schéma. Un document jamais
    annulé n'a pas de date de changement d'état : si l'export se contentait
    de la lire, il émettrait un élément vide et le fichier serait refusé.
    C'est pourquoi l'horodatage d'émission reste le repli — il est juste,
    dans ce cas-là : l'état « N » date bien de l'émission.
    """
    from xml.etree import ElementTree as ET

    document = _facture_signee(entreprise, cliente, series)
    assert document.etat_change_le is None

    octets = export.composer(entreprise, date(2026, 3, 1),
                             date(2026, 3, 31))
    racine = ET.fromstring(octets)
    facture = racine.find(ESPACE + 'SourceDocuments/' + ESPACE
                          + 'SalesInvoices/' + ESPACE + 'Invoice')
    etat = facture.find(ESPACE + 'DocumentStatus')

    assert (etat.find(ESPACE + 'InvoiceStatusDate').text
            == facture.find(ESPACE + 'SystemEntryDate').text)
    assert etat.find(ESPACE + 'InvoiceStatus').text == 'N'


def test_le_motif_de_rectification_n_est_plus_declare_comme_motif_d_etat(
        entreprise, cliente, series):
    """DEUX INFORMATIONS DIFFÉRENTES, DÉCLARÉES AU MÊME ENDROIT.

    `export.py` passait `motif_rectification` comme `Reason` du
    `DocumentStatus`. Un avoir déclarait donc sa raison de rectifier comme
    étant la raison de son état — alors qu'il n'avait changé d'état en
    rien. La rectification garde sa place dans le bloc `References` de la
    ligne, où `saft.references()` la pose.

    LA FENÊTRE D'EXPORT COUVRE L'ANNÉE, et non le mois de la facture :
    l'avoir est daté du jour de son émission, pas de celui du document
    qu'il rectifie.
    """
    from xml.etree import ElementTree as ET

    facture = _facture_signee(entreprise, cliente, series)
    avoir = facturation.emettre_une_note_de_credit(
        facture_de(facture), motif='Remise commerciale accordée')

    octets = export.composer(entreprise, date(2026, 1, 1),
                             date(2026, 12, 31))
    racine = ET.fromstring(octets)

    trouve = None
    for element in racine.iter(ESPACE + 'Invoice'):
        if element.find(ESPACE + 'InvoiceNo').text == avoir.numero:
            trouve = element
            break

    assert trouve is not None, 'l’avoir n’est pas dans le fichier'

    motif = trouve.find(ESPACE + 'DocumentStatus/' + ESPACE + 'Reason')
    # L'avoir n'a pas changé d'état : son `DocumentStatus` ne porte aucun
    # motif, puisque `motif_etat` est vide.
    assert motif is None or not (motif.text or '').strip(), (
        'le motif de rectification est déclaré comme motif d’état')

    # Et la rectification, elle, est bien portée par la ligne.
    texte = ET.tostring(trouve, encoding='unicode')
    assert 'Remise commerciale' in texte
    assert facture.numero in texte


def test_un_document_annule_est_compte_mais_pas_additionne(
        entreprise, cliente, series):
    """La Portaria 302/2016 pose les deux règles sur les mêmes documents.

    `NumberOfEntries` les COMPTE — la série ne doit sauter aucun numéro —
    et `TotalDebit`/`TotalCredit` les EXCLUENT.
    """
    from xml.etree import ElementTree as ET

    vivante = _facture_signee(entreprise, cliente, series, 'FAC-0001')
    annulee = _facture_signee(entreprise, cliente, series, 'FAC-0002')
    annulee.annuler('Doublon')

    octets = export.composer(entreprise, date(2026, 3, 1),
                             date(2026, 3, 31))
    racine = ET.fromstring(octets)
    ventes = racine.find(ESPACE + 'SourceDocuments/' + ESPACE
                         + 'SalesInvoices')

    assert ventes.find(ESPACE + 'NumberOfEntries').text == '2'
    assert (Decimal(ventes.find(ESPACE + 'TotalCredit').text)
            == vivante.total_base)


# ═══ 5. L'ÉCRAN ════════════════════════════════════════════════════════════

@pytest.fixture
def navigateur(client, django_user_model, entreprise, monkeypatch):
    """Un client authentifié dont l'entreprise courante est fixée.

    `request.current_company` est posé par un middleware qui dépend du
    rattachement de l'utilisateur. On le force ici pour tester l'écran et
    non le middleware, qui a ses propres tests — c'est le motif déjà
    employé par `tests/test_fiscal_pt_vues.py`.
    """
    utilisateur = django_user_model.objects.create_user(
        username='pedro', password='mot-de-passe-de-test', is_staff=True)
    client.force_login(utilisateur)

    from apps.fiscal_pt import views
    monkeypatch.setattr(views, '_company', lambda request: entreprise)
    return client


def test_l_ecran_annule_en_POST(navigateur, entreprise, cliente, series):
    document = _facture_signee(entreprise, cliente, series)

    navigateur.post(
        reverse('fiscal_pt:document_annuler', args=[document.pk]),
        {'motif': 'Erreur de saisie'})

    document.refresh_from_db()
    assert document.etat == 'A'
    assert document.motif_etat == 'Erreur de saisie'


def test_un_GET_n_annule_rien(navigateur, entreprise, cliente, series):
    """Un GET qui annulerait un document fiscal partirait au survol d'un
    lien, à l'indexation, ou au passage d'un antivirus."""
    document = _facture_signee(entreprise, cliente, series)

    reponse = navigateur.get(
        reverse('fiscal_pt:document_annuler', args=[document.pk]))

    assert reponse.status_code == 405
    document.refresh_from_db()
    assert document.etat == 'N'


def test_le_document_d_une_autre_entreprise_ne_s_annule_pas(
        client, django_user_model, entreprise, cliente, series, monkeypatch):
    """LE BORNAGE PAR ENTREPRISE, SUR UNE ACTION IRRÉVERSIBLE.

    Une annulation ne se défait pas : l'état « A » est définitif, et le
    document reste au fichier. Un `pk` seul dans la recherche laisserait
    annuler le document d'une autre société en changeant un chiffre dans
    l'adresse.
    """
    document = _facture_signee(entreprise, cliente, series)

    autre = Company.objects.create(name='Autre SA', slug='autre-ann')
    utilisateur = django_user_model.objects.create_user(
        username='intrus', password='mot-de-passe-de-test', is_staff=True)
    client.force_login(utilisateur)

    from apps.fiscal_pt import views
    monkeypatch.setattr(views, '_company', lambda request: autre)

    reponse = client.post(
        reverse('fiscal_pt:document_annuler', args=[document.pk]),
        {'motif': 'Tentative'})

    assert reponse.status_code == 404
    document.refresh_from_db()
    assert document.etat == 'N'


def test_l_ecran_refuse_sans_motif_et_le_dit(navigateur, entreprise, cliente,
                                             series):
    document = _facture_signee(entreprise, cliente, series)

    reponse = navigateur.post(
        reverse('fiscal_pt:document_annuler', args=[document.pk]),
        {'motif': ''}, follow=True)

    document.refresh_from_db()
    assert document.etat == 'N'
    assert any('pourquoi' in str(message)
               for message in reponse.context['messages'])


# ═══ 6. LE REÇU, DONT LA TABLE N'A QUE DEUX ÉTATS ══════════════════════════

def test_un_recu_s_annule_aussi(entreprise, cliente, series):
    facture = Invoice.objects.create(
        company=entreprise, customer=cliente, number='FAC-0010',
        issue_date=date(2026, 3, 7), status='draft')
    InvoiceLine.objects.create(
        invoice=facture, description='Travaux', quantity=Decimal('1'),
        unit_price=Decimal('100.00'), vat_rate=Decimal('23'))
    facture.refresh_from_db()
    facturation.emettre_pour_facture(facture)
    facture.refresh_from_db()

    recu = facturation.emettre_un_recu(facture, 'TB')
    recu.annuler('Encaissement rejeté par la banque')

    recu.refresh_from_db()
    assert recu.etat == 'A'
    assert recu.motif_etat == 'Encaissement rejeté par la banque'
    assert recu.verifier() is True

