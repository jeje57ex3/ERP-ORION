"""La saisie des lignes d'une facture.

CE QUI MANQUAIT

`InvoiceLine` était importé dans `apps/sales/forms.py` et instancié
**nulle part** dans l'application. Le modèle existait, le gabarit de
détail affichait `invoice.lines`, et aucun chemin de code n'en créait
jamais.

Le défaut ne se voyait pas : l'écran affichait fidèlement une liste
vide, et les totaux restaient à zéro sans qu'aucune erreur n'apparaisse.
C'est le genre de manque qui survit des années, parce que rien ne
proteste.

Au Portugal, c'était bloquant : le SAF-T exige au moins une ligne par
document, et aucune facture conforme n'était donc possible.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory
from django.urls import reverse

from apps.core.models import Company
from apps.crm.models import Customer
from apps.sales.models import Invoice, InvoiceLine


@pytest.fixture
def entreprise(db):
    return Company.objects.create(name='Orion Travaux', slug='orion-lignes')


@pytest.fixture
def cliente(entreprise):
    return Customer.objects.create(company=entreprise, name='Cliente Lda',
                                   is_active=True)


@pytest.fixture
def utilisateur(db, django_user_model):
    return django_user_model.objects.create_user(
        username='chef', password='mot-de-passe-de-test')


def _poster(chemin, donnees, entreprise, utilisateur, vue, *args):
    requete = RequestFactory().post(chemin, donnees)
    requete.user = utilisateur
    requete.current_company = entreprise
    requete.session = {}
    requete._messages = FallbackStorage(requete)
    reponse = vue(requete, *args)
    return reponse, [str(m) for m in requete._messages]


def _formset(lignes, total=None, initial=0):
    """Les champs d'un formset, tels que le navigateur les enverrait."""
    donnees = {
        'lines-TOTAL_FORMS': str(total if total is not None else len(lignes)),
        'lines-INITIAL_FORMS': str(initial),
        'lines-MIN_NUM_FORMS': '0',
        'lines-MAX_NUM_FORMS': '1000',
    }
    for rang, ligne in enumerate(lignes):
        for cle, valeur in ligne.items():
            donnees[f'lines-{rang}-{cle}'] = valeur
    return donnees


# ── La création ──────────────────────────────────────────────────────────────

def test_une_facture_se_cree_avec_ses_lignes(entreprise, cliente,
                                             utilisateur):
    from apps.sales.views import invoice_create

    donnees = {
        'customer': str(cliente.pk),
        'issue_date': '2026-03-07',
        'payment_terms': '30',
        'status': 'draft',
    }
    donnees.update(_formset([
        {'description': 'Instalação elétrica', 'quantity': '2',
         'unit': 'h', 'unit_price': '50.00', 'discount_rate': '0',
         'vat_rate': '23'},
        {'description': 'Material', 'quantity': '1', 'unit': 'u',
         'unit_price': '100.00', 'discount_rate': '0', 'vat_rate': '6'},
    ], total=3))

    reponse, _ = _poster(reverse('sales:invoice_create'), donnees,
                         entreprise, utilisateur, invoice_create)

    assert reponse.status_code == 302
    facture = Invoice.objects.get()
    assert facture.lines.count() == 2
    assert {l.description for l in facture.lines.all()} == {
        'Instalação elétrica', 'Material'}


def test_les_totaux_sont_recalcules_depuis_les_lignes(entreprise, cliente,
                                                      utilisateur):
    """Les totaux restaient à zéro sur toutes les factures, puisque rien ne
    créait de lignes. Ils se recalculent désormais à chaque
    enregistrement."""
    from apps.sales.views import invoice_create

    donnees = {
        'customer': str(cliente.pk), 'issue_date': '2026-03-07',
        'payment_terms': '30', 'status': 'draft',
    }
    donnees.update(_formset([
        {'description': 'Main d’œuvre', 'quantity': '2', 'unit': 'h',
         'unit_price': '50.00', 'discount_rate': '0', 'vat_rate': '23'},
        {'description': 'Material', 'quantity': '1', 'unit': 'u',
         'unit_price': '100.00', 'discount_rate': '0', 'vat_rate': '6'},
    ], total=2))

    _poster(reverse('sales:invoice_create'), donnees, entreprise,
            utilisateur, invoice_create)

    facture = Invoice.objects.get()
    assert facture.total_ht == Decimal('200.00')
    assert facture.total_tva == Decimal('29.00')   # 23 + 6
    assert facture.total_ttc == Decimal('229.00')


def test_une_ligne_vide_du_formset_n_est_pas_une_erreur(entreprise, cliente,
                                                        utilisateur):
    """Le formset propose trois lignes d’avance. Celles qu’on ne remplit
    pas ne doivent pas lever « ce champ est obligatoire »."""
    from apps.sales.views import invoice_create

    donnees = {
        'customer': str(cliente.pk), 'issue_date': '2026-03-07',
        'payment_terms': '30', 'status': 'draft',
    }
    donnees.update(_formset([
        {'description': 'Une seule ligne', 'quantity': '1', 'unit': 'u',
         'unit_price': '10.00', 'discount_rate': '0', 'vat_rate': '23'},
        {'description': '', 'quantity': '', 'unit': '', 'unit_price': '',
         'discount_rate': '', 'vat_rate': ''},
        {'description': '', 'quantity': '', 'unit': '', 'unit_price': '',
         'discount_rate': '', 'vat_rate': ''},
    ], total=3))

    reponse, _ = _poster(reverse('sales:invoice_create'), donnees,
                         entreprise, utilisateur, invoice_create)

    assert reponse.status_code == 302
    assert Invoice.objects.get().lines.count() == 1


def test_une_ligne_sans_quantite_prend_un_par_defaut(entreprise, cliente,
                                                     utilisateur):
    """Les défauts du MODÈLE ne s’appliquent pas à un champ laissé vide
    dans un formulaire : `quantity` vaudrait None, et le calcul de
    `total_ht` lèverait au premier enregistrement."""
    from apps.sales.views import invoice_create

    donnees = {
        'customer': str(cliente.pk), 'issue_date': '2026-03-07',
        'payment_terms': '30', 'status': 'draft',
    }
    donnees.update(_formset([
        {'description': 'Forfait', 'quantity': '', 'unit': '',
         'unit_price': '250.00', 'discount_rate': '', 'vat_rate': ''},
    ], total=1))

    reponse, _ = _poster(reverse('sales:invoice_create'), donnees,
                         entreprise, utilisateur, invoice_create)

    assert reponse.status_code == 302
    ligne = InvoiceLine.objects.get()
    assert ligne.quantity == Decimal('1')
    assert ligne.unit == 'u'
    assert ligne.total_ht == Decimal('250.00')


def test_une_ligne_sans_designation_mais_avec_un_prix_est_refusee(
        entreprise, cliente, utilisateur):
    from apps.sales.views import invoice_create

    donnees = {
        'customer': str(cliente.pk), 'issue_date': '2026-03-07',
        'payment_terms': '30', 'status': 'draft',
    }
    donnees.update(_formset([
        {'description': '', 'quantity': '1', 'unit': 'u',
         'unit_price': '99.00', 'discount_rate': '0', 'vat_rate': '23'},
    ], total=1))

    reponse, _ = _poster(reverse('sales:invoice_create'), donnees,
                         entreprise, utilisateur, invoice_create)

    assert reponse.status_code == 200      # le formulaire est réaffiché
    assert Invoice.objects.count() == 0


def test_la_remise_est_prise_en_compte(entreprise, cliente, utilisateur):
    from apps.sales.views import invoice_create

    donnees = {
        'customer': str(cliente.pk), 'issue_date': '2026-03-07',
        'payment_terms': '30', 'status': 'draft',
    }
    donnees.update(_formset([
        {'description': 'Avec remise', 'quantity': '1', 'unit': 'u',
         'unit_price': '100.00', 'discount_rate': '10', 'vat_rate': '23'},
    ], total=1))

    _poster(reverse('sales:invoice_create'), donnees, entreprise,
            utilisateur, invoice_create)

    assert Invoice.objects.get().total_ht == Decimal('90.00')


# ── L'étanchéité entre entreprises ───────────────────────────────────────────

def test_un_client_d_une_autre_entreprise_est_refuse(entreprise, cliente,
                                                     utilisateur):
    """LA FUITE QUE CE TEST FERME.

    Le client n’était borné à l’entreprise qu’à l’AFFICHAGE. Un
    identifiant forgé dans la requête désignait le client d’une AUTRE
    entreprise, et la facture lui était rattachée. La vue des devis, juste
    au-dessus dans le même fichier, appelle cela « la règle centrale de
    cet ERP » — et le contrôle manquait ici.
    """
    from apps.sales.views import invoice_create

    autre = Company.objects.create(name='Autre SA', slug='autre-lignes')
    etranger = Customer.objects.create(company=autre, name='Pas a nous',
                                       is_active=True)

    donnees = {
        'customer': str(etranger.pk), 'issue_date': '2026-03-07',
        'payment_terms': '30', 'status': 'draft',
    }
    donnees.update(_formset([
        {'description': 'Travaux', 'quantity': '1', 'unit': 'u',
         'unit_price': '100.00', 'discount_rate': '0', 'vat_rate': '23'},
    ], total=1))

    reponse, _ = _poster(reverse('sales:invoice_create'), donnees,
                         entreprise, utilisateur, invoice_create)

    assert reponse.status_code == 200
    assert Invoice.objects.count() == 0


# ── La modification ──────────────────────────────────────────────────────────

def test_les_lignes_se_modifient_et_les_totaux_suivent(entreprise, cliente,
                                                       utilisateur):
    from apps.sales.views import invoice_edit

    facture = Invoice.objects.create(
        company=entreprise, customer=cliente, number='FAC-0001',
        issue_date=date(2026, 3, 7))
    ligne = InvoiceLine.objects.create(
        invoice=facture, description='Avant', quantity=Decimal('1'),
        unit_price=Decimal('100.00'), vat_rate=Decimal('23'))

    donnees = {
        'customer': str(cliente.pk), 'issue_date': '2026-03-07',
        'payment_terms': '30', 'status': 'draft',
    }
    donnees.update(_formset([
        {'id': str(ligne.pk), 'invoice': str(facture.pk),
         'description': 'Apres', 'quantity': '2', 'unit': 'u',
         'unit_price': '100.00', 'discount_rate': '0', 'vat_rate': '23'},
    ], total=1, initial=1))

    reponse, _ = _poster(
        reverse('sales:invoice_edit', args=[facture.pk]), donnees,
        entreprise, utilisateur, invoice_edit, facture.pk)

    assert reponse.status_code == 302
    facture.refresh_from_db()
    assert facture.lines.get().description == 'Apres'
    assert facture.total_ht == Decimal('200.00')
    assert facture.total_ttc == Decimal('246.00')


def test_supprimer_une_ligne_recalcule_le_total(entreprise, cliente,
                                                utilisateur):
    """Un cumul tenu à part « au passage » dériverait ici. Au Portugal ce
    centime est signé : la preuve cesserait de correspondre au
    document."""
    from apps.sales.views import invoice_edit

    facture = Invoice.objects.create(
        company=entreprise, customer=cliente, number='FAC-0002',
        issue_date=date(2026, 3, 7))
    gardee = InvoiceLine.objects.create(
        invoice=facture, description='Gardee', quantity=Decimal('1'),
        unit_price=Decimal('100.00'), vat_rate=Decimal('23'))
    retiree = InvoiceLine.objects.create(
        invoice=facture, description='Retiree', quantity=Decimal('1'),
        unit_price=Decimal('50.00'), vat_rate=Decimal('23'))

    donnees = {
        'customer': str(cliente.pk), 'issue_date': '2026-03-07',
        'payment_terms': '30', 'status': 'draft',
    }
    donnees.update(_formset([
        {'id': str(gardee.pk), 'invoice': str(facture.pk),
         'description': 'Gardee', 'quantity': '1', 'unit': 'u',
         'unit_price': '100.00', 'discount_rate': '0', 'vat_rate': '23'},
        {'id': str(retiree.pk), 'invoice': str(facture.pk),
         'description': 'Retiree', 'quantity': '1', 'unit': 'u',
         'unit_price': '50.00', 'discount_rate': '0', 'vat_rate': '23',
         'DELETE': 'on'},
    ], total=2, initial=2))

    _poster(reverse('sales:invoice_edit', args=[facture.pk]), donnees,
            entreprise, utilisateur, invoice_edit, facture.pk)

    facture.refresh_from_db()
    assert facture.lines.count() == 1
    assert facture.total_ht == Decimal('100.00')
    assert facture.total_ttc == Decimal('123.00')


# ── Le motif d'exonération à l'écran ─────────────────────────────────────────

def test_le_motif_d_exoneration_se_saisit_sur_la_ligne(entreprise, cliente,
                                                       utilisateur):
    from apps.sales.views import invoice_create

    donnees = {
        'customer': str(cliente.pk), 'issue_date': '2026-09-01',
        'payment_terms': '30', 'status': 'draft',
    }
    donnees.update(_formset([
        {'description': 'Sous-traitance de construction', 'quantity': '1',
         'unit': 'u', 'unit_price': '1000.00', 'discount_rate': '0',
         'vat_rate': '0', 'code_exoneration': 'M31'},
    ], total=1))

    reponse, _ = _poster(reverse('sales:invoice_create'), donnees,
                         entreprise, utilisateur, invoice_create)

    assert reponse.status_code == 302
    assert InvoiceLine.objects.get().code_exoneration == 'M31'


def test_la_liste_des_motifs_est_proposee_a_l_ecran(entreprise, cliente,
                                                    utilisateur, client):
    """Un champ dont les choix ne s’affichent pas est un champ qu’on
    remplit à la main, donc de travers."""
    from apps.sales.forms import InvoiceLineFormSet

    rendu = str(InvoiceLineFormSet().forms[0]['code_exoneration'])

    assert 'M31' in rendu
    assert 'M07' in rendu
    assert 'M08' not in rendu     # ce code n’existe pas


def test_un_motif_hors_table_est_refuse_a_l_ecran(entreprise, cliente,
                                                  utilisateur):
    """M08 se devine entre M07 et M09, et n’existe pas."""
    from apps.sales.views import invoice_create

    donnees = {
        'customer': str(cliente.pk), 'issue_date': '2026-03-07',
        'payment_terms': '30', 'status': 'draft',
    }
    donnees.update(_formset([
        {'description': 'Travaux', 'quantity': '1', 'unit': 'u',
         'unit_price': '100.00', 'discount_rate': '0', 'vat_rate': '0',
         'code_exoneration': 'M08'},
    ], total=1))

    reponse, _ = _poster(reverse('sales:invoice_create'), donnees,
                         entreprise, utilisateur, invoice_create)

    assert reponse.status_code == 200
    assert Invoice.objects.count() == 0
