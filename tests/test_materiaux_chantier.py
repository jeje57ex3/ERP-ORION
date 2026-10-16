"""Matériaux et fournitures : catalogue, achats de chantier, lignes de devis.

**La propriété qui gouverne tout ce fichier est qu'il y a DEUX prix, et
qu'ils ne vont pas au même endroit.** `purchase_price` est ce que
l'entreprise paie : il part dans le coût du chantier. `sale_price` est ce
qu'elle facture : il part dans la ligne de devis. Les confondre coûte de
l'argent dans un sens (devis chiffré au prix d'achat, marge supprimée, coût
exposé au client) et fausse le suivi dans l'autre.

Deux autres garanties, chacune avec ses tests :

- **Le coût réel d'un chantier n'est jamais écrasé tout seul.** Le champ est
  saisi à la main et contient peut-être de la main-d'œuvre. Le report est une
  action explicite.
- **Un prix recopié ne bouge plus.** Un achat de mars garde le prix de mars,
  même si le catalogue change en septembre.
"""

from decimal import Decimal

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ── Terrain ─────────────────────────────────────────────────────────────────

@pytest.fixture
def client_crm(company):
    from apps.crm.models import Customer
    return Customer.objects.create(company=company, name='Dupont SARL')


@pytest.fixture
def chantier(company, client_crm):
    from apps.btp.models import BTPProject
    return BTPProject.objects.create(
        company=company, name='Villa Les Pins', code='CH-0001',
        customer=client_crm, estimated_budget=Decimal('50000'))


@pytest.fixture
def devis(company, client_crm, chantier):
    from apps.btp.models import BTPQuote
    return BTPQuote.objects.create(
        company=company, customer=client_crm, project=chantier,
        number='DEVBTP-0001')


@pytest.fixture
def ciment(company):
    """Un article du catalogue, avec les deux prix distincts."""
    from apps.btp.models import Material
    return Material.objects.create(
        company=company, kind='material', reference='CIM-35',
        name='Ciment CEM II 35 kg', category='Gros œuvre', unit='sac',
        purchase_price=Decimal('6.40'), sale_price=Decimal('9.60'),
        vat_rate=Decimal('20'))


@pytest.fixture
def connecte(client, company, django_user_model):
    user = django_user_model.objects.create_user(
        username='conducteur', password='motdepasse-test')
    user.profile.companies.add(company)
    user.profile.current_company = company
    user.profile.save()
    client.force_login(user)
    return client


@pytest.fixture
def autre_entreprise(company_b, django_user_model):
    """Une seconde entreprise, pour les tests d'isolation."""
    return company_b


# ═══ LE CATALOGUE ═══════════════════════════════════════════════════════════

def test_un_article_s_ajoute_au_catalogue(connecte, company):
    from apps.btp.models import Material

    reponse = connecte.post(reverse('btp:material_create'), {
        'kind': 'supply', 'reference': 'VIS-5X70',
        'name': 'Vis à bois 5x70 (boîte de 200)', 'category': 'Quincaillerie',
        'unit': 'boîte', 'purchase_price': '12.90', 'sale_price': '19.00',
        'vat_rate': '20', 'is_active': 'on',
    })

    assert reponse.status_code == 302
    article = Material.objects.get(reference='VIS-5X70')
    assert article.company == company
    assert article.kind == 'supply'
    assert article.sale_price == Decimal('19.0000')


def test_la_reference_en_double_est_refusee(company, ciment):
    """Deux articles de même référence rendraient le choix ambigu au moment
    de piocher dans le catalogue."""
    from apps.btp.forms import MaterialForm

    form = MaterialForm({
        'kind': 'material', 'reference': 'CIM-35', 'name': 'Autre ciment',
        'unit': 'sac', 'purchase_price': '7', 'sale_price': '10',
        'vat_rate': '20',
    }, company=company)

    assert not form.is_valid()
    assert 'reference' in form.errors


def test_la_reference_en_double_ignore_la_casse(company, ciment):
    from apps.btp.forms import MaterialForm

    form = MaterialForm({
        'kind': 'material', 'reference': 'cim-35', 'name': 'Ciment bis',
        'unit': 'sac', 'purchase_price': '7', 'sale_price': '10',
        'vat_rate': '20',
    }, company=company)
    assert not form.is_valid()


def test_la_meme_reference_est_libre_dans_une_autre_entreprise(
        company_b, ciment):
    """Les catalogues sont propres à chaque société : une référence prise
    chez l'une ne doit rien interdire chez l'autre."""
    from apps.btp.forms import MaterialForm

    form = MaterialForm({
        'kind': 'material', 'reference': 'CIM-35', 'name': 'Ciment',
        'unit': 'sac', 'purchase_price': '6', 'sale_price': '9',
        'vat_rate': '20',
    }, company=company_b)
    assert form.is_valid(), form.errors


def test_plusieurs_articles_sans_reference_cohabitent(company, ciment):
    """La référence reste facultative : l'exiger obligerait à en inventer
    une pour chaque vis."""
    from apps.btp.forms import MaterialForm

    for nom in ('Sable 0/4', 'Gravier 10/20'):
        form = MaterialForm({
            'kind': 'material', 'reference': '', 'name': nom, 'unit': 't',
            'purchase_price': '30', 'sale_price': '45', 'vat_rate': '20',
        }, company=company)
        assert form.is_valid(), form.errors
        form.instance.company = company
        form.save()


def test_modifier_un_article_ne_se_plaint_pas_de_sa_propre_reference(
        company, ciment):
    """Le contrôle d'unicité doit s'exclure lui-même, sinon aucun article
    n'est plus modifiable."""
    from apps.btp.forms import MaterialForm

    form = MaterialForm({
        'kind': 'material', 'reference': 'CIM-35',
        'name': 'Ciment CEM II 35 kg', 'unit': 'sac',
        'purchase_price': '6.80', 'sale_price': '9.90', 'vat_rate': '20',
    }, instance=ciment, company=company)
    assert form.is_valid(), form.errors


# ── La marge ────────────────────────────────────────────────────────────────

def test_la_marge_est_inconnue_et_non_nulle_sans_prix_d_achat(company):
    """None et pas 0 : afficher « 0 % » laisserait croire qu'on vend à prix
    coûtant, alors qu'on ne sait simplement pas ce que ça coûte."""
    from apps.btp.models import Material

    article = Material.objects.create(
        company=company, name='Sable', sale_price=Decimal('45'))
    assert article.marge is None


def test_la_marge_se_calcule_sur_le_prix_d_achat(ciment):
    # 6,40 -> 9,60 : la moitie en plus.
    assert round(ciment.marge) == 50


def test_la_liste_signale_un_prix_de_vente_manquant(connecte, company):
    """Sans prix de vente, piocher l'article poserait une ligne à 0 € dans
    un devis. Le dire dans le catalogue, où la donnée se corrige, et non au
    moment où le devis part chez le client."""
    from apps.btp.models import Material

    Material.objects.create(company=company, name='Enduit de façade',
                            purchase_price=Decimal('18'), sale_price=0)

    corps = connecte.get(reverse('btp:material_list')).content.decode()
    assert 'renseigner' in corps


# ── Isolation et recherche ──────────────────────────────────────────────────

def test_la_liste_ignore_le_catalogue_d_une_autre_entreprise(
        connecte, company_b, ciment):
    from apps.btp.models import Material

    Material.objects.create(company=company_b, name='Article confidentiel')

    corps = connecte.get(reverse('btp:material_list')).content.decode()
    assert 'Ciment CEM II' in corps
    assert 'Article confidentiel' not in corps


def test_la_recherche_porte_aussi_sur_la_reference(connecte, company, ciment):
    from apps.btp.models import Material
    Material.objects.create(company=company, name='Plaque de plâtre BA13',
                            reference='BA13')

    corps = connecte.get(
        reverse('btp:material_list'), {'q': 'CIM'}).content.decode()
    assert 'Ciment CEM II' in corps
    assert 'BA13' not in corps


def test_un_article_d_une_autre_entreprise_est_introuvable(
        connecte, company_b):
    from apps.btp.models import Material

    etranger = Material.objects.create(company=company_b, name='Ailleurs')
    reponse = connecte.get(reverse('btp:material_edit', args=[etranger.pk]))
    assert reponse.status_code == 404


# ── Suppression ─────────────────────────────────────────────────────────────

def test_un_article_utilise_est_desactive_et_non_supprime(
        connecte, chantier, ciment):
    """Les FK sont en SET_NULL : supprimer ne casserait rien, mais les
    lignes perdraient leur origine et un devis envoyé ne saurait plus d'où
    venait son prix."""
    from apps.btp.models import Material, ProjectSupply

    ProjectSupply.objects.create(
        project=chantier, material=ciment, description='Ciment',
        quantity=10, unit_price=Decimal('6.40'))

    connecte.post(reverse('btp:material_delete', args=[ciment.pk]))

    ciment.refresh_from_db()
    assert ciment.is_active is False
    assert Material.objects.filter(pk=ciment.pk).exists()


def test_un_article_jamais_utilise_est_bien_supprime(connecte, ciment):
    from apps.btp.models import Material

    connecte.post(reverse('btp:material_delete', args=[ciment.pk]))
    assert not Material.objects.filter(pk=ciment.pk).exists()


def test_la_suppression_refuse_un_GET(connecte, ciment):
    """Un GET destructeur se déclenche au survol d'un lien, à l'indexation,
    ou au passage d'un antivirus qui préfetche."""
    from apps.btp.models import Material

    reponse = connecte.get(reverse('btp:material_delete', args=[ciment.pk]))
    assert reponse.status_code == 405
    assert Material.objects.filter(pk=ciment.pk).exists()


# ═══ LES FOURNITURES D'UN CHANTIER ══════════════════════════════════════════

def test_un_achat_se_rattache_au_chantier(connecte, chantier, ciment):
    from apps.btp.models import ProjectSupply

    reponse = connecte.post(
        reverse('btp:project_supply_create', args=[chantier.pk]), {
            'material': ciment.pk, 'description': '', 'reference': '',
            'quantity': '30', 'unit': '', 'unit_price': '',
            'vat_rate': '20', 'purchase_date': '2026-03-12',
            'invoice_reference': 'FA-2026-0312',
        })

    assert reponse.status_code == 302
    achat = ProjectSupply.objects.get(project=chantier)
    assert achat.description == 'Ciment CEM II 35 kg'
    assert achat.unit == 'sac'
    assert achat.invoice_reference == 'FA-2026-0312'


def test_l_achat_reprend_le_prix_d_ACHAT_et_non_de_vente(
        connecte, chantier, ciment):
    """Le cœur de la distinction. Reprendre le prix de vente ferait croire
    qu'un chantier coûte ce qu'il rapporte, et la marge disparaîtrait des
    comptes."""
    from apps.btp.models import ProjectSupply

    connecte.post(reverse('btp:project_supply_create', args=[chantier.pk]), {
        'material': ciment.pk, 'description': '', 'reference': '',
        'quantity': '10', 'unit': '', 'unit_price': '', 'vat_rate': '20',
        'purchase_date': '2026-03-12', 'invoice_reference': '',
    })

    achat = ProjectSupply.objects.get(project=chantier)
    assert achat.unit_price == ciment.purchase_price == Decimal('6.4000')
    assert achat.unit_price != ciment.sale_price


def test_le_total_de_l_achat_se_calcule(chantier):
    from apps.btp.models import ProjectSupply

    achat = ProjectSupply.objects.create(
        project=chantier, description='Gravier', quantity=Decimal('2.5'),
        unit_price=Decimal('32.00'))
    assert achat.total_ht == Decimal('80.00')


def test_le_prix_saisi_prime_sur_celui_du_catalogue(
        connecte, chantier, ciment):
    """Une remise de négoce est le cas courant, pas l'exception : le prix
    tapé ne doit jamais être remplacé par celui du catalogue."""
    from apps.btp.models import ProjectSupply

    connecte.post(reverse('btp:project_supply_create', args=[chantier.pk]), {
        'material': ciment.pk, 'description': '', 'reference': '',
        'quantity': '100', 'unit': '', 'unit_price': '5.10',
        'vat_rate': '20', 'purchase_date': '2026-03-12',
        'invoice_reference': '',
    })

    achat = ProjectSupply.objects.get(project=chantier)
    assert achat.unit_price == Decimal('5.1000')
    assert achat.total_ht == Decimal('510.00')


def test_le_prix_d_un_achat_ne_bouge_pas_si_le_catalogue_change(
        chantier, ciment):
    """Recopié, pas référencé. Sinon le coût d'un chantier de mars
    changerait rétroactivement en septembre, et les comptes d'une affaire
    clôturée ne seraient plus reproductibles."""
    from apps.btp.models import ProjectSupply

    achat = ProjectSupply.objects.create(
        project=chantier, material=ciment, description='Ciment',
        quantity=10, unit_price=ciment.purchase_price)

    ciment.purchase_price = Decimal('11.00')
    ciment.save()

    achat.refresh_from_db()
    assert achat.unit_price == Decimal('6.4000')
    assert achat.total_ht == Decimal('64.00')


def test_un_achat_hors_catalogue_exige_une_designation(company):
    """Sans article ni désignation, la ligne n'apprend rien à personne."""
    from apps.btp.forms import ProjectSupplyForm

    form = ProjectSupplyForm({
        'material': '', 'description': '', 'quantity': '1', 'unit': 'u',
        'unit_price': '10', 'vat_rate': '20', 'purchase_date': '2026-03-12',
    }, company=company)
    assert not form.is_valid()
    assert 'description' in form.errors


def test_un_achat_hors_catalogue_passe_avec_une_designation(
        connecte, chantier):
    """Un achat d'appoint chez le négoce du coin n'a pas à entrer au
    catalogue pour être compté."""
    from apps.btp.models import ProjectSupply

    connecte.post(reverse('btp:project_supply_create', args=[chantier.pk]), {
        'material': '', 'description': 'Raccord cuivre 16 (dépannage)',
        'reference': '', 'quantity': '4', 'unit': 'u', 'unit_price': '3.20',
        'vat_rate': '20', 'purchase_date': '2026-03-12',
        'invoice_reference': 'TICKET-884',
    })

    achat = ProjectSupply.objects.get(project=chantier)
    assert achat.material is None
    assert achat.total_ht == Decimal('12.80')


def test_un_article_d_une_autre_entreprise_est_refuse_a_la_VALIDATION(
        company, company_b):
    """Borner la seule liste affichée laisserait passer un identifiant
    forgé : le chantier d'une société se retrouverait chargé d'un article
    d'une autre."""
    from apps.btp.forms import ProjectSupplyForm
    from apps.btp.models import Material

    etranger = Material.objects.create(company=company_b, name='Ailleurs',
                                       purchase_price=Decimal('5'))

    form = ProjectSupplyForm({
        'material': etranger.pk, 'description': 'Tentative', 'quantity': '1',
        'unit': 'u', 'unit_price': '5', 'vat_rate': '20',
        'purchase_date': '2026-03-12',
    }, company=company)

    assert not form.is_valid()
    assert 'material' in form.errors


def test_le_chantier_d_une_autre_entreprise_est_inaccessible(
        connecte, company_b):
    from apps.btp.models import BTPProject
    from apps.crm.models import Customer

    client_b = Customer.objects.create(company=company_b, name='Autre client')
    etranger = BTPProject.objects.create(
        company=company_b, name='Chantier voisin', customer=client_b)

    reponse = connecte.get(
        reverse('btp:project_supply_create', args=[etranger.pk]))
    assert reponse.status_code == 404


# ── Le coût du chantier ─────────────────────────────────────────────────────

def test_le_total_additionne_les_achats(chantier):
    from apps.btp.models import ProjectSupply

    ProjectSupply.objects.create(project=chantier, description='Ciment',
                                 quantity=10, unit_price=Decimal('6.40'))
    ProjectSupply.objects.create(project=chantier, description='Sable',
                                 quantity=2, unit_price=Decimal('30.00'))

    assert chantier.total_fournitures == Decimal('124.00')


def test_un_chantier_sans_achat_totalise_zero_et_non_None(chantier):
    """None ferait planter chaque affichage et chaque addition."""
    assert chantier.total_fournitures == Decimal('0')


def test_le_cout_reel_n_est_PAS_ecrase_par_un_achat(connecte, chantier):
    """La garantie qui protège une donnée saisie à la main : actual_cost
    contient peut-être déjà de la main-d'œuvre ou de la sous-traitance.
    L'écraser à chaque achat détruirait un chiffre que personne n'a demandé
    de remplacer."""
    chantier.actual_cost = Decimal('12000.00')
    chantier.save()

    connecte.post(reverse('btp:project_supply_create', args=[chantier.pk]), {
        'material': '', 'description': 'Ciment', 'reference': '',
        'quantity': '10', 'unit': 'sac', 'unit_price': '6.40',
        'vat_rate': '20', 'purchase_date': '2026-03-12',
        'invoice_reference': '',
    })

    chantier.refresh_from_db()
    assert chantier.actual_cost == Decimal('12000.00')
    assert chantier.total_fournitures == Decimal('64.00')


def test_le_report_est_explicite_et_remplace_le_cout_reel(connecte, chantier):
    from apps.btp.models import ProjectSupply

    chantier.actual_cost = Decimal('12000.00')
    chantier.save()
    ProjectSupply.objects.create(project=chantier, description='Ciment',
                                 quantity=10, unit_price=Decimal('6.40'))

    connecte.post(reverse('btp:project_report_supplies', args=[chantier.pk]))

    chantier.refresh_from_db()
    assert chantier.actual_cost == Decimal('64.00')


def test_le_report_refuse_un_GET(connecte, chantier):
    reponse = connecte.get(
        reverse('btp:project_report_supplies', args=[chantier.pk]))
    assert reponse.status_code == 405


def test_l_onglet_fournitures_montre_les_achats(connecte, chantier, ciment):
    from apps.btp.models import ProjectSupply

    ProjectSupply.objects.create(
        project=chantier, material=ciment, description='Ciment CEM II 35 kg',
        quantity=30, unit='sac', unit_price=Decimal('6.40'),
        invoice_reference='FA-2026-0312')

    corps = connecte.get(reverse('btp:project_detail', args=[chantier.pk]),
                         {'tab': 'supplies'}).content.decode()
    assert 'Ciment CEM II 35 kg' in corps
    assert 'FA-2026-0312' in corps
    assert '192' in corps  # 30 x 6,40


# ═══ LES LIGNES DE DEVIS BTP ════════════════════════════════════════════════

def test_une_ligne_reprend_le_prix_de_VENTE(connecte, devis, ciment):
    """L'autre moitié de la distinction. Chiffrer un devis au prix d'achat
    supprime la marge et expose le coût au client."""
    from apps.btp.models import BTPQuoteLine

    connecte.post(reverse('btp:quote_line_create', args=[devis.pk]), {
        'material': ciment.pk, 'work_item': '', 'phase': '',
        'description': '', 'unit': '', 'quantity': '30', 'unit_price': '',
        'vat_rate': '',
    })

    ligne = BTPQuoteLine.objects.get(quote=devis)
    assert ligne.unit_price == ciment.sale_price == Decimal('9.6000')
    assert ligne.unit_price != ciment.purchase_price
    assert ligne.description == 'Ciment CEM II 35 kg'
    assert ligne.unit == 'sac'
    assert ligne.total_ht == Decimal('288.00')


def test_l_ecran_du_devis_ne_montre_pas_le_prix_d_achat(
        connecte, devis, ciment):
    """Cet écran sert à relire un devis destiné au client. Le prix d'achat
    et le fournisseur sont des données internes : la ligne porte le nom de
    l'article, jamais son coût."""
    from apps.btp.models import BTPQuoteLine

    BTPQuoteLine.objects.create(
        quote=devis, material=ciment, description='Ciment CEM II 35 kg',
        unit='sac', quantity=30, unit_price=ciment.sale_price)

    corps = connecte.get(reverse('btp:quote_detail',
                                 args=[devis.pk])).content.decode()
    assert '9.60' in corps or '9,60' in corps
    assert '6.40' not in corps and '6,40' not in corps


def test_les_totaux_du_devis_se_recalculent(connecte, devis, ciment):
    """Ce modèle stockait total_ht / total_tva / total_ttc sans que rien ne
    les calcule jamais : un devis BTP affichait 0 € quelles que soient ses
    lignes."""
    connecte.post(reverse('btp:quote_line_create', args=[devis.pk]), {
        'material': ciment.pk, 'work_item': '', 'phase': '',
        'description': '', 'unit': '', 'quantity': '30', 'unit_price': '',
        'vat_rate': '',
    })

    devis.refresh_from_db()
    assert devis.total_ht == Decimal('288.00')
    assert devis.total_tva == Decimal('57.60')
    assert devis.total_ttc == Decimal('345.60')


def test_une_section_n_est_pas_comptee_dans_le_total(connecte, devis, ciment):
    """Une ligne de section porte un intitulé de sous-total, pas un montant.
    La compter doublerait le devis."""
    from apps.btp.models import BTPQuoteLine

    BTPQuoteLine.objects.create(quote=devis, description='Gros œuvre',
                                is_section=True, total_ht=Decimal('9999'))
    BTPQuoteLine.objects.create(quote=devis, description='Ciment', quantity=10,
                                unit_price=Decimal('9.60'))

    devis.calculate_totals()
    devis.refresh_from_db()
    assert devis.total_ht == Decimal('96.00')


def test_un_ouvrage_et_un_article_ensemble_sont_refuses(devis, company,
                                                        ciment):
    """Les deux rempliraient la même ligne avec deux prix différents.
    Trancher en silence tromperait sur le montant du devis."""
    from apps.btp.forms import BTPQuoteLineForm
    from apps.btp.models import WorkLibrary

    ouvrage = WorkLibrary.objects.create(
        company=company, name='Dalle béton', unit='m²',
        unit_price=Decimal('85'))

    form = BTPQuoteLineForm({
        'material': ciment.pk, 'work_item': ouvrage.pk, 'phase': '',
        'description': '', 'unit': '', 'quantity': '1', 'unit_price': '',
        'vat_rate': '20',
    }, quote=devis)

    assert not form.is_valid()
    assert 'work_item' in form.errors


def test_un_ouvrage_remplit_la_ligne(connecte, devis, company):
    from apps.btp.models import BTPQuoteLine, WorkLibrary

    ouvrage = WorkLibrary.objects.create(
        company=company, code='GO-01', name='Dalle béton 15 cm', unit='m²',
        unit_price=Decimal('85.00'))

    connecte.post(reverse('btp:quote_line_create', args=[devis.pk]), {
        'material': '', 'work_item': ouvrage.pk, 'phase': '',
        'description': '', 'unit': '', 'quantity': '40', 'unit_price': '',
        'vat_rate': '20',
    })

    ligne = BTPQuoteLine.objects.get(quote=devis)
    assert ligne.description == 'Dalle béton 15 cm'
    assert ligne.unit_price == Decimal('85.0000')
    assert ligne.total_ht == Decimal('3400.00')


def test_une_ligne_libre_exige_une_designation(devis):
    from apps.btp.forms import BTPQuoteLineForm

    form = BTPQuoteLineForm({
        'material': '', 'work_item': '', 'phase': '', 'description': '',
        'unit': 'u', 'quantity': '1', 'unit_price': '50', 'vat_rate': '20',
    }, quote=devis)
    assert not form.is_valid()
    assert 'description' in form.errors


def test_les_lignes_s_empilent_dans_l_ordre_d_ajout(connecte, devis):
    """Repartir de 0 empilerait toutes les lignes au même rang, et l'ordre
    d'un devis n'est pas décoratif."""
    from apps.btp.models import BTPQuoteLine

    for nom in ('Première', 'Deuxième', 'Troisième'):
        connecte.post(reverse('btp:quote_line_create', args=[devis.pk]), {
            'material': '', 'work_item': '', 'phase': '', 'description': nom,
            'unit': 'u', 'quantity': '1', 'unit_price': '10',
            'vat_rate': '20',
        })

    noms = list(BTPQuoteLine.objects.filter(quote=devis)
                .order_by('order').values_list('description', flat=True))
    assert noms == ['Première', 'Deuxième', 'Troisième']


def test_supprimer_une_ligne_recalcule_le_total(connecte, devis):
    """Sans recalcul après coup, le devis garderait le montant de la ligne
    retirée."""
    from apps.btp.models import BTPQuoteLine

    ligne = BTPQuoteLine.objects.create(
        quote=devis, description='À retirer', quantity=1,
        unit_price=Decimal('500'))
    devis.calculate_totals()
    devis.refresh_from_db()
    assert devis.total_ht == Decimal('500.00')

    connecte.post(reverse('btp:quote_line_delete', args=[ligne.pk]))

    devis.refresh_from_db()
    assert devis.total_ht == Decimal('0.00')


def test_la_suppression_d_une_ligne_refuse_un_GET(connecte, devis):
    from apps.btp.models import BTPQuoteLine

    ligne = BTPQuoteLine.objects.create(quote=devis, description='Ligne',
                                        quantity=1, unit_price=Decimal('10'))
    reponse = connecte.get(reverse('btp:quote_line_delete', args=[ligne.pk]))
    assert reponse.status_code == 405
    assert BTPQuoteLine.objects.filter(pk=ligne.pk).exists()


def test_une_ligne_d_un_devis_d_une_autre_entreprise_est_inaccessible(
        connecte, company_b):
    from apps.btp.models import BTPQuote, BTPQuoteLine
    from apps.crm.models import Customer

    client_b = Customer.objects.create(company=company_b, name='Autre')
    devis_b = BTPQuote.objects.create(company=company_b, customer=client_b,
                                      number='DEVBTP-B')
    ligne_b = BTPQuoteLine.objects.create(quote=devis_b, description='Secret',
                                          quantity=1,
                                          unit_price=Decimal('10'))

    assert connecte.get(
        reverse('btp:quote_line_edit', args=[ligne_b.pk])).status_code == 404
    assert connecte.post(
        reverse('btp:quote_line_delete', args=[ligne_b.pk])).status_code == 404
    assert BTPQuoteLine.objects.filter(pk=ligne_b.pk).exists()


def test_retirer_un_article_du_catalogue_ne_vide_pas_le_devis(devis, ciment):
    """SET_NULL et pas CASCADE : un devis déjà envoyé ne doit pas perdre ses
    lignes parce qu'on a nettoyé le catalogue."""
    from apps.btp.models import BTPQuoteLine

    ligne = BTPQuoteLine.objects.create(
        quote=devis, material=ciment, description='Ciment CEM II 35 kg',
        unit='sac', quantity=30, unit_price=Decimal('9.60'))

    ciment.delete()

    ligne.refresh_from_db()
    assert ligne.material is None
    assert ligne.description == 'Ciment CEM II 35 kg'
    assert ligne.unit_price == Decimal('9.6000')


def test_les_phases_proposees_sont_celles_de_CE_chantier(devis, company,
                                                         client_crm):
    """Proposer les phases de tous les chantiers rattacherait une ligne à la
    phase d'une autre affaire."""
    from apps.btp.forms import BTPQuoteLineForm
    from apps.btp.models import BTPPhase, BTPProject

    phase_du_devis = BTPPhase.objects.create(project=devis.project,
                                             name='Fondations')
    autre_chantier = BTPProject.objects.create(
        company=company, name='Autre chantier', customer=client_crm)
    phase_etrangere = BTPPhase.objects.create(project=autre_chantier,
                                              name='Charpente')

    form = BTPQuoteLineForm(quote=devis)
    proposees = set(form.fields['phase'].queryset)
    assert phase_du_devis in proposees
    assert phase_etrangere not in proposees


# ═══ LES ÉCRANS SONT ATTEIGNABLES ═══════════════════════════════════════════

def test_le_catalogue_figure_dans_le_menu():
    """Une fonctionnalité qu'on ne trouve pas n'existe pas pour l'utilisateur."""
    from apps.core.context_processors import NAV_MODULES

    groupe = next(m for m in NAV_MODULES if m['id'] == 'btp')
    cibles = [e['url_name'] for e in groupe['children']]
    assert 'btp:material_list' in cibles


def test_le_devis_offre_le_bouton_d_ajout_de_ligne(connecte, devis):
    """Le gabarit disait « modifiez le devis pour ajouter des ouvrages »
    alors qu'aucun écran ne le permettait."""
    corps = connecte.get(reverse('btp:quote_detail',
                                 args=[devis.pk])).content.decode()
    assert reverse('btp:quote_line_create', args=[devis.pk]) in corps


def test_le_chantier_offre_le_bouton_d_ajout_de_fourniture(connecte,
                                                           chantier):
    corps = connecte.get(reverse('btp:project_detail', args=[chantier.pk]),
                         {'tab': 'supplies'}).content.decode()
    assert reverse('btp:project_supply_create', args=[chantier.pk]) in corps


def test_les_ecrans_exigent_une_connexion(client, company, chantier, devis):
    for nom, args in (
        ('btp:material_list', []),
        ('btp:material_create', []),
        ('btp:project_supply_create', [chantier.pk]),
        ('btp:quote_line_create', [devis.pk]),
    ):
        reponse = client.get(reverse(nom, args=args))
        assert reponse.status_code == 302, nom
