"""Associer matériaux, fournitures et actions, dès la création du devis.

Deux ajouts, deux propriétés à tenir.

**Une troisième nature : l'action.** Poser, déposer, raccorder. Elle vit
dans le MÊME catalogue que les matériaux et les fournitures — et non dans
la bibliothèque d'ouvrages (`btp.WorkLibrary`), qui n'a aucun écran : son
sélecteur serait vide en permanence. Les deux prix gardent un sens pour une
action : prix d'achat = coût horaire interne, prix de vente = taux facturé.

**Le détail se saisit dès la CRÉATION.** Un formset en ligne a besoin d'une
instance à laquelle rattacher ses lignes, et il n'y a pas encore de devis.
Il est donc construit sans instance, puis reçoit le devis enregistré avant
`save()` — `save_new()` relit `self.instance` au moment d'écrire, pas à la
construction. C'est le point le plus facile à casser sans s'en apercevoir,
d'où les tests qui suivent.

Le tout est enveloppé dans une transaction : un devis enregistré dont le
détail échouerait ensuite partirait au client amputé de ce qui justifie son
prix.
"""

from decimal import Decimal

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ── Terrain ─────────────────────────────────────────────────────────────────

@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Dupont SA', slug='dupont-sa')


@pytest.fixture
def client_crm(entreprise):
    from apps.crm.models import Customer
    return Customer.objects.create(company=entreprise, name='Client Test')


@pytest.fixture
def connecte(client, entreprise, django_user_model):
    user = django_user_model.objects.create_user(
        username='patron', password='motdepasse-test')
    user.profile.companies.add(entreprise)
    user.profile.current_company = entreprise
    user.profile.save()
    client.force_login(user)
    client.user = user
    return client


@pytest.fixture
def carrelage(entreprise):
    from apps.btp.models import Material
    return Material.objects.create(
        company=entreprise, kind='material', name='Carrelage 60x60',
        unit='m²', purchase_price=Decimal('18'), sale_price=Decimal('25'))


@pytest.fixture
def colle(entreprise):
    from apps.btp.models import Material
    return Material.objects.create(
        company=entreprise, kind='supply', name='Colle C2 25 kg',
        unit='sac', purchase_price=Decimal('14'), sale_price=Decimal('18.50'))


@pytest.fixture
def pose(entreprise):
    """Une ACTION du catalogue : coût horaire interne, taux facturé."""
    from apps.btp.models import Material
    return Material.objects.create(
        company=entreprise, kind='action', name='Pose de carrelage',
        unit='h', purchase_price=Decimal('28'), sale_price=Decimal('45'))


def _formset(lignes, total=None):
    """Les champs de gestion du formset, plus les lignes données."""
    nombre = total if total is not None else len(lignes)
    donnees = {
        'detail_lines-TOTAL_FORMS': str(nombre),
        'detail_lines-INITIAL_FORMS': '0',
        'detail_lines-MIN_NUM_FORMS': '0',
        'detail_lines-MAX_NUM_FORMS': '1000',
    }
    for index, ligne in enumerate(lignes):
        for champ in ('nature', 'material', 'designation', 'quantity', 'unit',
                      'unit_price'):
            donnees[f'detail_lines-{index}-{champ}'] = ligne.get(champ, '')
    for index in range(len(lignes), nombre):
        for champ in ('nature', 'material', 'designation', 'quantity', 'unit',
                      'unit_price'):
            donnees[f'detail_lines-{index}-{champ}'] = ''
    return donnees


def _devis(client_crm, **extra):
    base = {
        'customer': client_crm.pk, 'subject': 'Rénovation salle de bain',
        'issue_date': '2026-10-20', 'payment_terms': '30',
        'discount_rate': '0', 'status': 'draft',
        'cout_materiels': '0', 'cout_fournitures': '0',
        'cout_main_oeuvre': '0', 'taches_principales': '',
    }
    base.update(extra)
    return base


# ═══ LA TROISIÈME NATURE ════════════════════════════════════════════════════

def test_le_catalogue_accepte_une_action():
    from apps.btp.models import Material

    kinds = {k for k, _ in Material.KIND_CHOICES}
    assert 'action' in kinds


def test_la_ligne_de_detail_accepte_une_action():
    from apps.sales.models import QuoteDetailLine

    natures = {n for n, _ in QuoteDetailLine.NATURES}
    assert natures == {'materiel', 'fourniture', 'action'}


def test_le_catalogue_affiche_les_actions(connecte, pose):
    corps = connecte.get(reverse('btp:material_list')).content.decode()
    assert 'Pose de carrelage' in corps
    assert 'Action' in corps


def test_le_catalogue_se_filtre_sur_les_actions(connecte, carrelage, pose):
    corps = connecte.get(reverse('btp:material_list'),
                         {'kind': 'action'}).content.decode()
    assert 'Pose de carrelage' in corps
    assert 'Carrelage 60x60' not in corps


def test_les_deux_prix_gardent_un_sens_pour_une_action(pose):
    """Coût horaire interne contre taux facturé : la marge se calcule comme
    pour un matériau."""
    assert pose.purchase_price == Decimal('28.0000')
    assert pose.sale_price == Decimal('45.0000')
    assert round(pose.marge) == 61


def test_les_actions_ont_leur_propre_bloc_sur_le_devis(entreprise,
                                                       client_crm):
    from apps.sales.models import Quote, QuoteDetailLine
    from apps.sales.quote_pdf import valeurs_du_devis

    devis = Quote.objects.create(company=entreprise, customer=client_crm,
                                 number='DEV-1')
    QuoteDetailLine.objects.create(
        quote=devis, nature='materiel', designation='Carrelage',
        quantity=Decimal('40'), unit='m²', unit_price=Decimal('25'))
    QuoteDetailLine.objects.create(
        quote=devis, nature='action', designation='Pose de carrelage',
        quantity=Decimal('14'), unit='h', unit_price=Decimal('45'))

    valeurs = valeurs_du_devis(devis)
    assert 'Pose de carrelage' in valeurs['designation_actions']
    assert 'Carrelage' not in valeurs['designation_actions']
    assert 'Pose de carrelage' not in valeurs['designation_materiels']


def test_le_bloc_des_actions_est_placable():
    from apps.sales.models import QuoteTemplateField

    cles = {cle for cle, _ in QuoteTemplateField.CLES}
    assert 'designation_actions' in cles


def test_chaque_cle_placable_a_toujours_une_valeur(entreprise, client_crm):
    """Un cadre posé sur une clé sans valeur n'écrirait jamais rien."""
    from apps.sales.models import Quote, QuoteTemplateField
    from apps.sales.quote_pdf import valeurs_du_devis

    devis = Quote.objects.create(company=entreprise, customer=client_crm)
    valeurs = valeurs_du_devis(devis)
    for cle, _ in QuoteTemplateField.CLES:
        assert cle in valeurs, cle


# ═══ LA NATURE SE DÉDUIT DE L'ARTICLE ═══════════════════════════════════════

def test_une_nature_vide_se_comble_depuis_l_article(entreprise, pose):
    """Oublier la nature après avoir choisi un article ne doit pas bloquer
    la saisie pour rien."""
    from apps.sales.forms import QuoteDetailLineForm

    form = QuoteDetailLineForm({
        'nature': '', 'material': pose.pk, 'designation': '',
        'quantity': '14', 'unit': '', 'unit_price': '',
    }, company=entreprise)

    assert form.is_valid(), form.errors
    assert form.cleaned_data['nature'] == 'action'
    assert form.cleaned_data['designation'] == 'Pose de carrelage'
    assert form.cleaned_data['unit'] == 'h'
    assert form.cleaned_data['unit_price'] == Decimal('45.0000')


@pytest.mark.parametrize('kind,nature', [
    ('material', 'materiel'),
    ('supply', 'fourniture'),
    ('action', 'action'),
])
def test_la_correspondance_couvre_les_trois_natures(entreprise, kind,
                                                    nature):
    from apps.btp.models import Material
    from apps.sales.forms import QuoteDetailLineForm

    article = Material.objects.create(
        company=entreprise, kind=kind, name='Article', unit='u',
        sale_price=Decimal('10'))

    form = QuoteDetailLineForm({
        'nature': '', 'material': article.pk, 'designation': '',
        'quantity': '1', 'unit': '', 'unit_price': '',
    }, company=entreprise)

    assert form.is_valid(), form.errors
    assert form.cleaned_data['nature'] == nature


def test_une_nature_choisie_n_est_JAMAIS_ecrasee(entreprise, carrelage):
    """Le menu affiché reste ce qui sera enregistré. On peut vouloir
    compter en fourniture un article catalogué comme matériau."""
    from apps.sales.forms import QuoteDetailLineForm

    form = QuoteDetailLineForm({
        'nature': 'fourniture', 'material': carrelage.pk, 'designation': '',
        'quantity': '1', 'unit': '', 'unit_price': '',
    }, company=entreprise)

    assert form.is_valid(), form.errors
    assert form.cleaned_data['nature'] == 'fourniture'


def test_sans_article_ni_nature_c_est_refuse(entreprise):
    from apps.sales.forms import QuoteDetailLineForm

    form = QuoteDetailLineForm({
        'nature': '', 'material': '', 'designation': 'Quelque chose',
        'quantity': '1', 'unit': 'u', 'unit_price': '10',
    }, company=entreprise)

    assert not form.is_valid()
    assert 'nature' in form.errors
    # Le message doit nommer la sortie, pas seulement constater.
    assert 'catalogue' in ' '.join(form.errors['nature'])


# ═══ DÈS LA CRÉATION ════════════════════════════════════════════════════════

def test_l_ecran_de_creation_offre_le_tableau(connecte):
    corps = connecte.get(reverse('sales:quote_create')).content.decode()

    assert 'detail_lines-TOTAL_FORMS' in corps
    assert 'detail_lines-0-nature' in corps


def test_les_trois_natures_s_associent_a_la_creation(connecte, client_crm,
                                                     carrelage, colle, pose):
    """Le cas demandé, de bout en bout."""
    from apps.sales.models import Quote, QuoteDetailLine

    donnees = _devis(client_crm)
    donnees.update(_formset([
        {'nature': '', 'material': str(carrelage.pk), 'quantity': '40'},
        {'nature': '', 'material': str(colle.pk), 'quantity': '12'},
        {'nature': '', 'material': str(pose.pk), 'quantity': '14'},
    ]))

    reponse = connecte.post(reverse('sales:quote_create'), donnees)
    assert reponse.status_code == 302, reponse.context['detail'].errors

    devis = Quote.objects.get(customer=client_crm)
    lignes = QuoteDetailLine.objects.filter(quote=devis)
    assert lignes.count() == 3
    assert {l.nature for l in lignes} == {'materiel', 'fourniture', 'action'}


def test_les_lignes_sont_bien_rattachees_au_devis_cree(connecte, client_crm,
                                                       pose):
    """Le point fragile : le formset est construit SANS instance, et ne la
    reçoit qu'après l'enregistrement du devis. Si le rattachement se faisait
    à la construction, les lignes seraient orphelines — ou perdues."""
    from apps.sales.models import Quote, QuoteDetailLine

    donnees = _devis(client_crm)
    donnees.update(_formset([
        {'nature': 'action', 'material': str(pose.pk), 'quantity': '14'},
    ]))

    connecte.post(reverse('sales:quote_create'), donnees)

    devis = Quote.objects.get(customer=client_crm)
    ligne = QuoteDetailLine.objects.get()
    assert ligne.quote_id == devis.pk
    assert not QuoteDetailLine.objects.filter(quote__isnull=True).exists()


def test_le_devis_se_cree_toujours_sans_aucune_ligne(connecte, client_crm):
    """Le détail est facultatif : un devis sans rien à détailler doit
    continuer de se créer comme avant."""
    from apps.sales.models import Quote, QuoteDetailLine

    donnees = _devis(client_crm)
    donnees.update(_formset([], total=3))

    reponse = connecte.post(reverse('sales:quote_create'), donnees)

    assert reponse.status_code == 302
    assert Quote.objects.filter(customer=client_crm).exists()
    assert not QuoteDetailLine.objects.exists()


def test_le_numero_est_bien_attribue_malgre_la_transaction(connecte,
                                                           client_crm, pose):
    """La numérotation atomique tourne maintenant DANS une transaction
    englobante : elle doit continuer de produire un numéro."""
    from apps.sales.models import Quote

    donnees = _devis(client_crm)
    donnees.update(_formset([
        {'nature': 'action', 'material': str(pose.pk), 'quantity': '2'},
    ]))

    connecte.post(reverse('sales:quote_create'), donnees)

    devis = Quote.objects.get(customer=client_crm)
    assert devis.number
    assert devis.number != ''


def test_une_ligne_invalide_empeche_la_creation_du_devis(connecte,
                                                         client_crm):
    """Tout ou rien : un devis enregistré dont le détail échouerait partirait
    au client amputé de ce qui justifie son prix."""
    from apps.sales.models import Quote

    donnees = _devis(client_crm)
    donnees.update(_formset([
        # Ni article ni designation : la ligne est refusee.
        {'nature': 'materiel', 'material': '', 'designation': '',
         'quantity': '1', 'unit': 'u', 'unit_price': '5'},
    ]))

    reponse = connecte.post(reverse('sales:quote_create'), donnees)

    assert reponse.status_code == 200
    assert not Quote.objects.filter(customer=client_crm).exists()


def test_un_article_d_une_autre_entreprise_est_refuse_a_la_creation(
        connecte, client_crm, entreprise):
    from apps.btp.models import Material
    from apps.core.models import Company
    from apps.sales.models import Quote

    autre = Company.objects.create(name='Martin SA', slug='martin-sa')
    etranger = Material.objects.create(
        company=autre, kind='action', name='Action voisine',
        sale_price=Decimal('99'))

    donnees = _devis(client_crm)
    donnees.update(_formset([
        {'nature': 'action', 'material': str(etranger.pk), 'quantity': '1'},
    ]))

    reponse = connecte.post(reverse('sales:quote_create'), donnees)

    assert reponse.status_code == 200
    assert not Quote.objects.filter(customer=client_crm).exists()


def test_le_detail_n_entre_pas_dans_le_total_a_la_creation(connecte,
                                                           client_crm, pose):
    from apps.sales.models import Quote

    donnees = _devis(client_crm)
    donnees.update(_formset([
        {'nature': 'action', 'material': str(pose.pk), 'quantity': '14'},
    ]))

    connecte.post(reverse('sales:quote_create'), donnees)

    devis = Quote.objects.get(customer=client_crm)
    # Aucune ligne de PRESTATION : le total reste a zero, les 630 EUR
    # d'actions ne le gonflent pas.
    assert devis.total_ht == Decimal('0.00')


# ═══ LA MODIFICATION CONTINUE DE FONCTIONNER ════════════════════════════════

def test_la_modification_accepte_aussi_les_actions(connecte, entreprise,
                                                   client_crm, pose):
    from apps.sales.models import Quote, QuoteDetailLine

    devis = Quote.objects.create(company=entreprise, customer=client_crm,
                                 number='DEV-9')

    donnees = _devis(client_crm)
    donnees.update(_formset([
        {'nature': 'action', 'material': str(pose.pk), 'quantity': '6'},
    ]))

    reponse = connecte.post(reverse('sales:quote_edit', args=[devis.pk]),
                            donnees)

    assert reponse.status_code == 302, reponse.context['detail'].errors
    ligne = QuoteDetailLine.objects.get(quote=devis)
    assert ligne.nature == 'action'
    assert ligne.total_ht == Decimal('270.000')


def test_la_fiche_du_devis_montre_les_trois_groupes(connecte, entreprise,
                                                    client_crm):
    from apps.sales.models import Quote, QuoteDetailLine

    devis = Quote.objects.create(company=entreprise, customer=client_crm,
                                 number='DEV-8')
    for nature, nom in (('materiel', 'Carrelage gres'),
                        ('fourniture', 'Colle C2'),
                        ('action', 'Pose carrelage')):
        QuoteDetailLine.objects.create(
            quote=devis, nature=nature, designation=nom,
            quantity=Decimal('1'), unit='u', unit_price=Decimal('10'))

    corps = connecte.get(
        reverse('sales:quote_detail', args=[devis.pk])).content.decode()
    for nom in ('Carrelage gres', 'Colle C2', 'Pose carrelage'):
        assert nom in corps, nom
    assert 'Action' in corps
