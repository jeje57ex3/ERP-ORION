"""Le reçu, du bouton jusqu'au fichier remis à l'administration.

POURQUOI CES TESTS PASSENT PAR LA BASE ET PAR LES ÉCRANS

`tests/test_fiscal_pt_recu_regles.py` mesure les règles. Ce fichier-ci
mesure le CHEMIN : qu'une série de reçus se numérote sans trou, qu'un
reçu soit signé et figé, qu'il arrive dans la table 4.4 du SAF-T sans
casser ni le schéma ni la cohérence, et qu'un utilisateur puisse
réellement l'émettre depuis un écran.

CE QUE LE REÇU N'EST PAS

Ce n'est pas une facture, ni un document rectificatif. Il ne corrige
rien et ne remplace rien : il atteste de l'argent reçu sur un document
déjà émis. Le confondre avec une facture-reçu « FR » est l'erreur que
plusieurs de ces tests ferment — la « FR » vaut quittance de SON TOTAL et
de rien d'autre, ce qui la rend inutilisable pour un acompte.
"""
from datetime import date
from decimal import Decimal
from xml.etree import ElementTree as ET

import pytest
from cryptography.fernet import Fernet
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.core.models import Company
from apps.crm.models import Customer
from apps.fiscal_pt import coherence, export, facturation, schema, tipos
from apps.fiscal_pt.models import (CleDeSignature, DocumentFiscal,
                                   ParametresFiscauxPT, RecuFiscal,
                                   SerieFiscale)
from apps.sales.models import Invoice, InvoiceLine

ESPACE = '{urn:OECD:StandardAuditFile-Tax:PT_1.04_01}'


@pytest.fixture
def chiffrement(settings):
    settings.ORION_SECRET_ENCRYPTION_KEY = Fernet.generate_key().decode()


@pytest.fixture
def entreprise(db):
    return Company.objects.create(name='Orion Lusitana', slug='orion-recus')


@pytest.fixture
def cliente(entreprise):
    return Customer.objects.create(company=entreprise, name='Cliente Lda',
                                   nif='500000000', country='Portugal')


@pytest.fixture
def conformite(entreprise, chiffrement):
    """L'entreprise prête à émettre, avec la série de reçus."""
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
    """98,40 € à payer, émise en « FT »."""
    facture = _facture(entreprise, cliente)
    facturation.emettre_pour_facture(facture)
    facture.refresh_from_db()
    return facture


# ── L'émission ───────────────────────────────────────────────────────────────

def test_un_recu_s_emet_sur_une_facture_signee(facture_signee):
    recu = facturation.emettre_un_recu(facture_signee, 'TB')

    assert recu.numero == 'RG A/1'
    assert recu.atcud == 'JFFNVTC7-1'
    assert recu.total == Decimal('98.40')
    assert recu.au_debit is False
    assert recu.verifier() is True


def test_le_recu_designe_le_document_qu_il_solde(facture_signee):
    recu = facturation.emettre_un_recu(facture_signee, 'TB')

    assert len(recu.affectations) == 1
    affectation = recu.affectations[0]
    assert affectation['document'] == 'FT A/1'
    assert affectation['date'] == '2026-03-07'
    assert affectation['montant'] == '98.40'
    assert affectation['au_debit'] is False


def test_le_montant_du_moyen_de_paiement_vient_du_recu_et_de_nulle_part(
        facture_signee):
    """Le total n'existe qu'en un seul endroit, et c'est délibéré.

    La facture-reçu a déjà montré ce que coûte un montant tenu à deux
    endroits : l'écran prenait le sien dans `invoice.total_ttc`, un cumul
    tenu à part qui valait zéro. Ici le montant du paiement n'est jamais
    passé : il est rempli avec le total calculé depuis les affectations.
    """
    recu = facturation.emettre_un_recu(facture_signee, 'TB')

    assert recu.paiements[0]['montant'] == '98.40'
    assert recu.paiements[0]['mecanisme'] == 'TB'


def test_un_recu_partiel_laisse_un_reste(facture_signee):
    recu = facturation.emettre_un_recu(facture_signee, 'NU',
                                       montant=Decimal('30.00'))

    assert recu.total == Decimal('30.00')
    assert facturation.reste_a_encaisser(facture_signee) == Decimal('68.40')


def test_deux_recus_soldent_la_facture(facture_signee):
    facturation.emettre_un_recu(facture_signee, 'NU', montant=Decimal('30.00'))
    second = facturation.emettre_un_recu(facture_signee, 'TB')

    assert second.numero == 'RG A/2'
    assert second.total == Decimal('68.40')
    assert facturation.reste_a_encaisser(facture_signee) == Decimal('0')


def test_un_recu_qui_depasse_le_reste_est_refuse(facture_signee):
    """Des reçus qui dépassent la créance attestent un argent que personne
    ne devait, et chacun pris séparément est parfaitement régulier."""
    facturation.emettre_un_recu(facture_signee, 'NU', montant=Decimal('90.00'))

    with pytest.raises(ValidationError) as erreur:
        facturation.emettre_un_recu(facture_signee, 'TB',
                                    montant=Decimal('20.00'))

    assert 'reste' in str(erreur.value)


def test_le_refus_ne_consomme_pas_de_numero(facture_signee, conformite):
    """Une série ne doit sauter aucun numéro, et l'AT le vérifie."""
    avant = SerieFiscale.objects.get(pk=conformite['RG'].pk).prochain_numero

    with pytest.raises(ValidationError):
        facturation.emettre_un_recu(facture_signee, 'TB',
                                    montant=Decimal('9999.00'))

    apres = SerieFiscale.objects.get(pk=conformite['RG'].pk).prochain_numero
    assert apres == avant
    assert RecuFiscal.objects.count() == 0


def test_un_recu_sur_une_facture_non_signee_est_refuse(entreprise, cliente,
                                                       conformite):
    brouillon = _facture(entreprise, cliente, 'FAC-0009')

    with pytest.raises(ValidationError) as erreur:
        facturation.emettre_un_recu(brouillon, 'TB')

    assert 'n’a pas été signée' in str(erreur.value)


def test_un_recu_sur_une_facture_recu_est_refuse(entreprise, cliente,
                                                 conformite):
    """Elle vaut DÉJÀ quittance de son total.

    Un reçu de plus attesterait une seconde fois le même règlement, et les
    deux documents seraient réguliers pris séparément — c'est-à-dire que
    rien ne le signalerait.
    """
    facture = _facture(entreprise, cliente, 'FAC-0010')
    facturation.emettre_pour_facture(
        facture, 'FR',
        paiements=[{'mecanisme': 'TB', 'date': date(2026, 3, 7)}])
    facture.refresh_from_db()

    with pytest.raises(ValidationError) as erreur:
        facturation.emettre_un_recu(facture, 'TB')

    assert 'vaut déjà quittance' in str(erreur.value)


def test_le_remboursement_d_un_avoir_va_au_debit(facture_signee, entreprise):
    """Encaisser et rembourser sont deux mouvements opposés.

    Le sens vient du document réglé, et non d'une saisie : un avoir rend
    l'argent, donc la ligne du reçu va au débit.
    """
    avoir = facturation.emettre_une_note_de_credit(facture_signee, 'Anulação')
    recu = RecuFiscal.emettre(
        serie=SerieFiscale.objects.get(company=entreprise,
                                       type_document='RG'),
        date_document=date(2026, 3, 20),
        affectations=[{'document': avoir.numero,
                       'date': avoir.date_document,
                       'montant': avoir.total,
                       'type_du_document': 'NC'}],
        nif_emetteur='123456789',
        nif_acquereur='500000000',
        paiements=[{'mecanisme': 'TB', 'date': date(2026, 3, 20)}],
    )

    assert recu.au_debit is True
    assert recu.affectations[0]['au_debit'] is True


# ── L'immuabilité et la chaîne ───────────────────────────────────────────────

def test_un_recu_emis_ne_se_modifie_plus(facture_signee):
    recu = facturation.emettre_un_recu(facture_signee, 'TB')
    recu.total = Decimal('1.00')

    with pytest.raises(ValidationError) as erreur:
        recu.save()

    assert 'déjà émis' in str(erreur.value)


def test_un_recu_emis_ne_se_supprime_pas(facture_signee):
    recu = facturation.emettre_un_recu(facture_signee, 'TB')

    with pytest.raises(ValidationError) as erreur:
        recu.delete()

    assert 'aucun ne manque' in str(erreur.value)


def test_la_chaine_des_recus_est_la_leur_et_non_celle_des_factures(
        facture_signee):
    """Chaque série a sa chaîne. Les mélanger rendrait la vérification
    d'une série dépendante d'une autre table."""
    premier = facturation.emettre_un_recu(facture_signee, 'NU',
                                          montant=Decimal('30.00'))
    second = facturation.emettre_un_recu(facture_signee, 'TB')

    assert premier.signature_precedente == ''
    assert second.signature_precedente == premier.signature
    assert premier.verifier() is True
    assert second.verifier() is True


def test_le_recu_ne_touche_pas_au_numero_de_la_facture(facture_signee):
    """Le reçu est un document à part : il ne renomme rien."""
    facturation.emettre_un_recu(facture_signee, 'TB')
    facture_signee.refresh_from_db()

    assert facture_signee.number == 'FT A/1'


# ── Le code QR et les mentions ───────────────────────────────────────────────

def test_le_code_qr_du_recu_porte_son_type_et_un_espace_fiscal_a_zero(
        facture_signee):
    """Spécifications de l'AT, champ I1 : « no caso de documento sem
    indicação da taxa de IVA, que deva constar na tabela 4.2, 4.3 ou 4.4
    do SAF-T(PT), preencher com "0" ». La table 4.4 est celle des reçus.
    """
    recu = facturation.emettre_un_recu(facture_signee, 'TB')
    champs = dict(partie.split(':', 1)
                  for partie in recu.contenu_qr.split('*'))

    assert champs['D'] == 'RG'
    assert champs['E'] == 'N'
    assert champs['I1'] == '0'
    assert champs['N'] == '0.00'
    assert champs['O'] == '98.40'
    assert champs['G'] == 'RG A/1'
    assert champs['H'] == 'JFFNVTC7-1'
    assert 'I2' not in champs
    assert 'I7' not in champs


def test_le_champ_q_du_code_qr_vient_de_la_signature_du_recu(facture_signee):
    """Le champ Q est OBLIGATOIRE et vaut quatre caractères du Hash.

    La loi dispense les reçus de signature ; les spécifications du code QR
    ne prévoient pourtant aucune exception pour le champ Q. On signe donc
    le reçu pour pouvoir le remplir, et ce test vérifie que les quatre
    caractères sont bien ceux de SA signature — et non recopiés d'ailleurs.
    """
    from apps.fiscal_pt import assinatura

    recu = facturation.emettre_un_recu(facture_signee, 'TB')
    champs = dict(partie.split(':', 1)
                  for partie in recu.contenu_qr.split('*'))

    assert champs['Q'] == assinatura.caracteres_imprimes(recu.signature)
    assert len(champs['Q']) == 4


def test_le_recu_porte_les_deux_mentions_du_despacho(facture_signee):
    recu = facturation.emettre_un_recu(facture_signee, 'TB')
    mentions = recu.mentions_legales('1234')

    assert mentions == [
        'Emitido por programa certificado n.º 1234/AT',
        'Este documento não serve de fatura',
    ]


# ── Le SAF-T ─────────────────────────────────────────────────────────────────

def _fichier(entreprise, debut=date(2026, 3, 1), fin=date(2026, 3, 31)):
    racine = ET.fromstring(export.composer(entreprise, debut, fin))
    return racine, schema.valider(racine), coherence.verifier(racine)


def test_le_saft_porte_la_table_des_recus_et_reste_conforme(facture_signee,
                                                            entreprise):
    facturation.emettre_un_recu(facture_signee, 'TB',
                                montant=Decimal('60.00'),
                                date_encaissement=date(2026, 3, 20))

    racine, erreurs, anomalies = _fichier(entreprise)

    assert erreurs == []
    assert anomalies == []

    table = racine.find(f'{ESPACE}SourceDocuments/{ESPACE}Payments')
    assert table is not None
    assert table.find(f'{ESPACE}NumberOfEntries').text == '1'
    assert table.find(f'{ESPACE}TotalCredit').text == '60.00'
    assert table.find(f'{ESPACE}TotalDebit').text == '0.00'


def test_le_recu_ne_porte_pas_de_signature_dans_le_fichier(facture_signee,
                                                           entreprise):
    """Le Despacho 8632/2014 (1.1) exclut les reçus de l'obligation de
    signature, et la table 4.4 n'a aucun champ pour la porter. Le reçu est
    signé en interne pour le code QR ; la signature ne sort pas."""
    facturation.emettre_un_recu(facture_signee, 'TB',
                                date_encaissement=date(2026, 3, 20))

    racine, erreurs, _ = _fichier(entreprise)
    recu = racine.find(f'{ESPACE}SourceDocuments/{ESPACE}Payments/'
                       f'{ESPACE}Payment')

    assert erreurs == []
    assert recu.find(f'{ESPACE}Hash') is None
    assert recu.find(f'{ESPACE}HashControl') is None
    assert recu.find(f'{ESPACE}ATCUD').text == 'JFFNVTC7-1'


def test_le_moyen_de_paiement_d_un_recu_s_appelle_PaymentMethod(
        facture_signee, entreprise):
    """Le même type du schéma, sous deux noms d'élément.

    Dans les totaux d'une facture il s'appelle « Payment » ; au niveau
    d'un reçu, « PaymentMethod ». Composer un reçu par analogie avec la
    facture donne un élément inconnu à cet endroit, et fait refuser le
    fichier entier pour un nom.
    """
    facturation.emettre_un_recu(facture_signee, 'TB',
                                date_encaissement=date(2026, 3, 20))

    racine, _, _ = _fichier(entreprise)
    recu = racine.find(f'{ESPACE}SourceDocuments/{ESPACE}Payments/'
                       f'{ESPACE}Payment')

    assert recu.find(f'{ESPACE}PaymentMethod') is not None
    assert recu.find(f'{ESPACE}Payment') is None


def test_les_totaux_du_recu_sont_dans_l_ordre_de_la_table_4_4(facture_signee,
                                                              entreprise):
    """`Settlement` vient AVANT `Currency` ici, et après dans la table 4.1.

    Rien ne le justifie, le schéma ne s'en explique pas, et réemployer
    l'ordre des factures produit un fichier dont seul l'ordre de deux
    éléments optionnels diffère — refusé en entier.
    """
    facturation.emettre_un_recu(facture_signee, 'TB',
                                date_encaissement=date(2026, 3, 20))

    racine, erreurs, _ = _fichier(entreprise)

    assert erreurs == []
    from apps.fiscal_pt import saft
    assert saft.ORDRE_TOTAUX_DE_RECU.index('Settlement') < \
        saft.ORDRE_TOTAUX_DE_RECU.index('Currency')
    assert saft.ORDRE_TOTAUX.index('Currency') < \
        saft.ORDRE_TOTAUX.index('Settlement')


def test_un_fichier_sans_recu_n_annonce_pas_la_table(facture_signee,
                                                     entreprise):
    """Une table annoncée à zéro enregistrement se lirait comme une
    déclaration là où il n'y a rien à déclarer."""
    racine, erreurs, anomalies = _fichier(entreprise)

    assert erreurs == []
    assert anomalies == []
    assert racine.find(f'{ESPACE}SourceDocuments/{ESPACE}Payments') is None


def test_le_client_du_recu_est_celui_de_la_facture(facture_signee,
                                                   entreprise):
    """Un `CustomerID` que `MasterFiles` ne déclare pas fait rejeter le
    fichier, et le motif parle de référentiel, pas de reçu."""
    facturation.emettre_un_recu(facture_signee, 'TB',
                                date_encaissement=date(2026, 3, 20))

    racine, _, anomalies = _fichier(entreprise)
    recu = racine.find(f'{ESPACE}SourceDocuments/{ESPACE}Payments/'
                       f'{ESPACE}Payment')
    facture = racine.find(f'{ESPACE}SourceDocuments/{ESPACE}SalesInvoices/'
                          f'{ESPACE}Invoice')

    assert anomalies == []
    assert recu.find(f'{ESPACE}CustomerID').text == \
        facture.find(f'{ESPACE}CustomerID').text


# ── Les écrans ───────────────────────────────────────────────────────────────

@pytest.fixture
def utilisateur(db, django_user_model):
    return django_user_model.objects.create_user(
        username='pedro', password='mot-de-passe-de-test', is_staff=True)


@pytest.fixture
def navigateur(client, utilisateur, entreprise, monkeypatch):
    client.force_login(utilisateur)
    from apps.fiscal_pt import views
    monkeypatch.setattr(views, '_company', lambda request: entreprise)
    return client


def test_l_ecran_d_emission_annonce_le_reste_a_encaisser(navigateur,
                                                         facture_signee):
    reponse = navigateur.get(
        reverse('fiscal_pt:recu_sur_facture', args=[facture_signee.pk]))
    html = reponse.content.decode()

    assert reponse.status_code == 200
    assert 'Émettre le reçu' in html
    assert '98.40' in html
    assert 'FT A/1' in html


def test_l_ecran_refuse_poliment_une_facture_non_signee(navigateur,
                                                        entreprise, cliente,
                                                        conformite):
    brouillon = _facture(entreprise, cliente, 'FAC-0020')

    reponse = navigateur.get(
        reverse('fiscal_pt:recu_sur_facture', args=[brouillon.pk]))
    html = reponse.content.decode()

    assert reponse.status_code == 200
    assert 'pas été signée' in html
    assert 'Émettre le reçu' not in html


def test_l_ecran_emet_le_recu_et_redirige_vers_lui(navigateur,
                                                   facture_signee):
    # LE MOYEN DE PAIEMENT EST MAINTENANT UN JEU DE RANGEES, parce qu'un
    # encaissement peut arriver par plusieurs moyens a la fois. Le cas a
    # un seul moyen -- celui-ci -- laisse son montant vide : l'emission y
    # met le total du recu, calcule depuis les affectations.
    reponse = navigateur.post(
        reverse('fiscal_pt:recu_sur_facture', args=[facture_signee.pk]),
        {'montant': '40.00', 'date_encaissement': '2026-03-20',
         'description': 'Acompte',
         'moyens-TOTAL_FORMS': '3', 'moyens-INITIAL_FORMS': '0',
         'moyens-MIN_NUM_FORMS': '0', 'moyens-MAX_NUM_FORMS': '1000',
         'moyens-0-mecanisme': 'NU', 'moyens-0-montant': '',
         'moyens-1-mecanisme': '', 'moyens-1-montant': '',
         'moyens-2-mecanisme': '', 'moyens-2-montant': ''})

    recu = RecuFiscal.objects.get()
    assert reponse.status_code == 302
    assert reponse.url == reverse('fiscal_pt:recu_detail', args=[recu.pk])
    assert recu.total == Decimal('40.00')
    assert recu.affectations[0]['description'] == 'Acompte'


def test_l_ecran_de_detail_montre_les_deux_mentions_et_le_code_qr(
        navigateur, facture_signee):
    recu = facturation.emettre_un_recu(facture_signee, 'TB')

    reponse = navigateur.get(
        reverse('fiscal_pt:recu_detail', args=[recu.pk]))
    html = reponse.content.decode()

    assert reponse.status_code == 200
    assert 'Emitido por programa certificado' in html
    assert 'Este documento não serve de fatura' in html
    assert reverse('fiscal_pt:recu_qr', args=[recu.pk]) in html


def test_le_code_qr_du_recu_se_telecharge_en_png(navigateur, facture_signee):
    recu = facturation.emettre_un_recu(facture_signee, 'TB')

    reponse = navigateur.get(reverse('fiscal_pt:recu_qr', args=[recu.pk]))

    assert reponse.status_code == 200
    assert reponse['Content-Type'] == 'image/png'


def test_la_liste_des_recus_les_montre_avec_leur_sens(navigateur,
                                                      facture_signee):
    facturation.emettre_un_recu(facture_signee, 'TB')

    reponse = navigateur.get(reverse('fiscal_pt:recus'))
    html = reponse.content.decode()

    assert reponse.status_code == 200
    assert 'RG A/1' in html
    assert 'argent reçu' in html


def test_l_etat_de_conformite_reclame_une_serie_de_recus(navigateur,
                                                         entreprise,
                                                         chiffrement):
    """Sans série « RG », aucun reçu ne peut être numéroté — et le refus
    n'arriverait qu'au moment de l'émission."""
    cle = CleDeSignature.creer(entreprise)
    SerieFiscale.objects.create(company=entreprise, type_document='FT',
                                nom='A', code_de_validation='CSDF7T5H',
                                cle=cle)

    reponse = navigateur.get(reverse('fiscal_pt:index'))
    html = reponse.content.decode()

    assert 'Manquants' in html
    assert 'RG' in html


def test_l_ecran_de_la_facture_propose_le_recu_et_liste_ceux_emis(
        facture_signee, utilisateur, client, monkeypatch, entreprise):
    """Le bouton doit être dans le HTML rendu, et pas seulement écrit.

    Un bouton de ce dépôt se trouvait déjà enfermé dans une condition qui
    le masquait précisément quand il servait.
    """
    from django.contrib.messages.storage.fallback import FallbackStorage
    from django.test import RequestFactory

    from apps.sales.views import invoice_detail

    def _afficher():
        requete = RequestFactory().get('/x/')
        requete.user = utilisateur
        requete.current_company = entreprise
        requete.session = {}
        requete._messages = FallbackStorage(requete)
        return invoice_detail(requete, facture_signee.pk).content.decode()

    avant = _afficher()
    assert reverse('fiscal_pt:recu_sur_facture',
                   args=[facture_signee.pk]) in avant

    recu = facturation.emettre_un_recu(facture_signee, 'TB')
    apres = _afficher()

    assert recu.numero in apres
    # La facture est soldée : le bouton disparaît, puisque l'émission le
    # refuserait désormais.
    assert reverse('fiscal_pt:recu_sur_facture',
                   args=[facture_signee.pk]) not in apres


# ── La vérification des chaînes ──────────────────────────────────────────────

def test_la_verification_regarde_vraiment_la_table_des_recus(navigateur,
                                                             facture_signee):
    """Une série de reçus ne doit pas être déclarée intacte sans examen.

    Les reçus vivent dans leur propre table. Une boucle qui ne regarderait
    que les documents de facturation trouverait la série « RG A » VIDE —
    zéro document, aucune rupture, aucun trou — et l'afficherait donc
    « intacte ». L'écran dirait que tout va bien de ce qu'il n'a pas
    regardé.
    """
    facturation.emettre_un_recu(facture_signee, 'NU',
                                montant=Decimal('30.00'))
    facturation.emettre_un_recu(facture_signee, 'TB')

    reponse = navigateur.get(reverse('fiscal_pt:verification'))
    rapport = {ligne['serie'].type_document: ligne
               for ligne in reponse.context['rapport']}

    assert rapport['RG']['nombre'] == 2
    assert rapport['RG']['intacte'] is True


def test_un_recu_altere_en_base_est_signale(navigateur, facture_signee):
    """On contourne `save()` avec `update()`, comme le ferait quelqu'un qui
    passerait par la base — c'est précisément ce que la chaîne détecte."""
    recu = facturation.emettre_un_recu(facture_signee, 'TB')
    RecuFiscal.objects.filter(pk=recu.pk).update(total=Decimal('1.00'),
                                                 signature='X' * 172)

    reponse = navigateur.get(reverse('fiscal_pt:verification'))
    rapport = {ligne['serie'].type_document: ligne
               for ligne in reponse.context['rapport']}

    assert rapport['RG']['intacte'] is False
    assert any('signature invalide' in rupture
               for rupture in rapport['RG']['ruptures'])
