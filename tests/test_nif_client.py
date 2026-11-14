"""« Une case pour le NIF de chaque client, et un cadre dans les modèles de devis. »

LE NIF EST FACULTATIF, ET C'EST UN PIÈGE CONNU

Le champ porte `blank=True`. C'est CELA qui le rend facultatif au
formulaire — pas une valeur par défaut, qui ne fournit que la valeur
initiale et laisserait le champ obligatoire. Ce piège a déjà coûté trois
formulaires dans cet ERP : la saisie est refusée, et l'écran revient
identique sans que rien n'explique pourquoi.

Le premier test de ce fichier enregistre donc un client SANS NIF.

LE CADRE SUR LE MODÈLE DE DEVIS

Un modèle de devis est le PDF de l'exploitant ; Orion écrit par-dessus aux
emplacements déclarés. Ajouter « le NIF » veut dire : offrir la clé
`nif_client` dans la liste des valeurs posables, et savoir la calculer.
Une clé proposée mais sans valeur donnerait un cadre vide, ce qui ne se
verrait qu'à l'impression — exactement le genre de défaut que ce dépôt a
déjà rencontré sur les devis.
"""
from decimal import Decimal

import pytest


@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Martin SA', slug='martin-sa')


@pytest.fixture
def client_erp(entreprise):
    from apps.crm.models import Customer
    return Customer.objects.create(
        company=entreprise, code='CLI-0042', name='Entreprise Exemple SARL',
        contact_name='Jean Dupont', address='12 rue des Artisans',
        zip_code='57000', city='Metz', email='contact@exemple.fr',
        phone='03 87 00 00 00', nif='PT509442908',
    )


# ── 1. Le champ sur la fiche client ──────────────────────────────────────────

@pytest.mark.django_db
def test_le_nif_se_conserve(client_erp):
    from apps.crm.models import Customer
    assert Customer.objects.get(pk=client_erp.pk).nif == 'PT509442908'


def test_le_champ_est_facultatif():
    """LE PIÈGE : seul `blank=True` rend un champ facultatif au formulaire.

    Un champ laissé obligatoire ferait refuser tout client sans NIF — et le
    formulaire reviendrait identique, sans message pour qui ne lit pas
    l'erreur.
    """
    from apps.crm.models import Customer

    champ = Customer._meta.get_field('nif')
    assert champ.blank is True, 'le NIF serait obligatoire a la saisie'


def test_la_longueur_ne_suppose_pas_un_seul_pays():
    """Neuf chiffres au Portugal et en Espagne, davantage ailleurs. Calibrer
    sur un seul pays obligerait a migrer des qu'on en ajoute un."""
    from apps.crm.models import Customer

    assert Customer._meta.get_field('nif').max_length >= 20


@pytest.mark.django_db
def test_un_client_sans_nif_est_accepte_par_le_formulaire(entreprise):
    """LA VÉRIFICATION QUI COMPTE : on soumet vraiment le formulaire."""
    from apps.crm.forms import CustomerForm

    formulaire = CustomerForm(data={
        'customer_type': 'company', 'name': 'Client sans NIF',
        'country': 'France', 'payment_terms': 30, 'discount_rate': '0',
    })

    assert formulaire.is_valid(), formulaire.errors
    assert 'nif' not in formulaire.errors


@pytest.mark.django_db
def test_le_formulaire_enregistre_le_nif_saisi(entreprise):
    from apps.crm.forms import CustomerForm

    formulaire = CustomerForm(data={
        'customer_type': 'company', 'name': 'Client avec NIF',
        'country': 'France', 'payment_terms': 30, 'discount_rate': '0',
        'nif': 'PT123456789',
    })
    assert formulaire.is_valid(), formulaire.errors

    client = formulaire.save(commit=False)
    client.company = entreprise
    client.save()

    assert client.nif == 'PT123456789'


def test_le_champ_est_propose_par_le_formulaire():
    """Un champ present sur le modele mais absent du formulaire ne serait
    saisissable que par l'admin Django — autant dire : pas saisissable."""
    from apps.crm.forms import CustomerForm

    assert 'nif' in CustomerForm().fields


def test_les_ecrans_du_client_portent_le_nif():
    """Le champ doit etre AFFICHE, pas seulement declare : un formulaire qui
    ne rend pas son champ le laisse vide a chaque enregistrement."""
    from pathlib import Path

    saisie = Path('templates/crm/customer_form.html').read_text(encoding='utf-8')
    fiche = Path('templates/crm/customer_detail.html').read_text(encoding='utf-8')

    assert 'form.nif' in saisie, 'aucune case de saisie pour le NIF'
    assert 'customer.nif' in fiche, 'la fiche client n’affiche pas le NIF'


# ── 2. Le cadre sur les modèles de devis ─────────────────────────────────────

def test_le_nif_est_posable_sur_un_modele_de_devis():
    from apps.sales.models import QuoteTemplateField

    cles = dict(QuoteTemplateField.CLES)
    assert 'nif_client' in cles
    assert cles['nif_client'] == 'NIF du client'


@pytest.mark.django_db
def test_la_valeur_ecrite_sur_le_devis_est_celle_du_client(entreprise, client_erp):
    """LA GARANTIE CENTRALE : la clé proposée sait produire sa valeur.

    Une clé offerte dans la liste mais absente du calcul donnerait un cadre
    vide — et cela ne se verrait qu'à l'impression.
    """
    from apps.sales.models import Quote
    from apps.sales.quote_pdf import valeurs_du_devis

    devis = Quote.objects.create(
        company=entreprise, customer=client_erp, number='DEV-2026-0042',
        subject='Rénovation', total_ht=Decimal('100.00'),
        total_tva=Decimal('20.00'), total_ttc=Decimal('120.00'))

    valeurs = valeurs_du_devis(devis)

    assert valeurs['nif_client'] == 'PT509442908'


@pytest.mark.django_db
def test_un_client_sans_nif_n_imprime_pas_None(entreprise):
    """Un cadre sans valeur doit rester VIDE. « None » imprimé sur un devis
    envoyé à un client serait pire qu'un blanc."""
    from apps.crm.models import Customer
    from apps.sales.models import Quote
    from apps.sales.quote_pdf import valeurs_du_devis

    sans_nif = Customer.objects.create(
        company=entreprise, name='Client sans NIF')
    devis = Quote.objects.create(
        company=entreprise, customer=sans_nif, number='DEV-2026-0043',
        total_ht=Decimal('0'), total_tva=Decimal('0'), total_ttc=Decimal('0'))

    valeurs = valeurs_du_devis(devis)

    assert valeurs['nif_client'] == ''
    assert 'None' not in str(valeurs['nif_client'])


def test_chaque_cle_proposee_sait_produire_une_valeur(db):
    """LE GARDE-FOU GÉNÉRAL, au-delà du NIF.

    Ajouter une clé à CLES sans l'ajouter au calcul est une faute qui ne se
    voit qu'à l'impression d'un vrai devis. Le test relie les deux listes,
    pour que la prochaine clé oubliée tombe ici.
    """
    from apps.core.models import Company
    from apps.crm.models import Customer
    from apps.sales.models import Quote, QuoteTemplateField
    from apps.sales.quote_pdf import valeurs_du_devis

    societe = Company.objects.create(name='Test SA', slug='test-sa')
    client = Customer.objects.create(company=societe, name='Client')
    devis = Quote.objects.create(
        company=societe, customer=client, number='DEV-0001',
        total_ht=Decimal('0'), total_tva=Decimal('0'), total_ttc=Decimal('0'))

    valeurs = valeurs_du_devis(devis)
    # La signature est une IMAGE, elle ne passe pas par le dictionnaire des
    # textes : elle est traitee a part par le dessin.
    attendues = {cle for cle, _ in QuoteTemplateField.CLES} - QuoteTemplateField.CLES_IMAGE

    manquantes = attendues - set(valeurs)
    assert not manquantes, (
        f'cle(s) posables sur un modele mais sans valeur calculee : '
        f'{sorted(manquantes)} — elles donneraient un cadre vide')
