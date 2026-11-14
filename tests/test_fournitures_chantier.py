"""« L'ajout de fournitures dans un chantier ne fonctionne pas : le bouton
sauvegarde me ramène à la même page. »

LA CAUSE, MESURÉE ET NON DEVINÉE

Un « <input type="date"> » n'accepte sa valeur initiale qu'au format ISO,
« AAAA-MM-JJ ». C'est la norme HTML, et le navigateur n'est pas tolérant.
Or Django rend les dates au format de la langue active ; en français, le
champ sortait ainsi :

    <input type="date" name="purchase_date" value="14/11/2026" required>

Le navigateur REFUSE cette valeur et affiche le champ vide. Le champ étant
obligatoire (`purchase_date` a un `default=timezone.now` mais pas de
`blank=True`), l'enregistrement échouait, et l'écran revenait identique.

POURQUOI LE DÉFAUT A SURVÉCU

Il ne se voit pas sur un champ sans valeur initiale. Il n'apparaît qu'en
modification, ou quand le modèle fournit un défaut — comme ici. Les
cinquante-cinq champs date de l'ERP, dans douze fichiers, étaient dans ce
cas : aucun ne précisait son format.

Le premier test de ce fichier regarde donc les OCTETS du champ rendu.
"""
from decimal import Decimal

import pytest
from django.urls import reverse


@pytest.fixture
def chantier(db, client, django_user_model):
    from apps.accounts.models import UserProfile
    from apps.btp.models import BTPProject, Material
    from apps.core.models import Company
    from apps.crm.models import Customer
    from apps.private_saas.models import ALL_MODULE_CODES, CompanyModule

    entreprise = Company.objects.create(name='Martin SA', slug='martin-sa')
    for code in ALL_MODULE_CODES:
        CompanyModule.objects.update_or_create(
            company=entreprise, module_code=code, defaults={'is_enabled': True})

    personne = django_user_model.objects.create_user(
        'chef', password='x', is_superuser=True, is_staff=True)
    profil, _ = UserProfile.objects.get_or_create(user=personne)
    profil.role = 'superadmin'
    profil.save()
    profil.companies.add(entreprise)
    client.force_login(django_user_model.objects.get(pk=personne.pk))
    session = client.session
    session['current_company_id'] = entreprise.pk
    session.save()

    client_erp = Customer.objects.create(company=entreprise, name='Client')
    projet = BTPProject.objects.create(
        company=entreprise, name='Rénovation Metz', customer=client_erp)

    article = Material.objects.create(
        company=entreprise, kind='supply', name='Plaque de plâtre BA13',
        reference='BA13', category='Cloison', unit='m²',
        purchase_price=Decimal('4.2000'), vat_rate=Decimal('20'))

    return {'client': client, 'entreprise': entreprise, 'projet': projet,
            'article': article}


# ── 1. La cause, dans les octets ─────────────────────────────────────────────

def test_le_champ_date_est_rendu_au_format_ISO():
    """LA PREUVE MATÉRIELLE.

    « 14/11/2026 » dans un « type=date » est refusé par le navigateur, qui
    affiche alors un champ vide — et le formulaire, obligatoire, refuse.
    """
    from apps.btp.forms import ProjectSupplyForm

    rendu = str(ProjectSupplyForm(company=None)['purchase_date'])

    assert 'type="date"' in rendu
    assert 'value="' in rendu
    valeur = rendu.split('value="')[1].split('"')[0]
    assert valeur.count('-') == 2 and '/' not in valeur, (
        f'valeur « {valeur} » : un <input type=date> exige AAAA-MM-JJ')


def test_plus_aucun_champ_date_ne_laisse_son_format_au_hasard():
    """LE GARDE-FOU GÉNÉRAL.

    Le défaut n'était pas propre aux fournitures : il touchait les 55 champs
    date de l'ERP. Interdire « forms.DateInput » force à passer par le
    widget partagé, qui impose le format ISO — la prochaine saisie de date
    ne pourra plus retomber dans le piège.
    """
    import subprocess

    resultat = subprocess.run(
        ['git', 'grep', '-n', '--', 'forms.DateInput', 'apps/'],
        capture_output=True, text=True)

    # Le widget partage HERITE de forms.DateInput : c'est son role, et
    # c'est le seul endroit ou cette classe doit apparaitre.
    lignes = [l for l in resultat.stdout.splitlines()
              if l.strip() and not l.startswith('apps/core/form_widgets.py')]
    assert not lignes, (
        'employez DateISO (apps/core/form_widgets.py) plutot que '
        f'forms.DateInput : {lignes[:5]}')


# ── 2. L'enregistrement, de bout en bout ─────────────────────────────────────

@pytest.mark.django_db
def test_une_fourniture_s_enregistre_vraiment(chantier):
    """LA PANNE RAPPORTÉE : le bouton devait enregistrer, pas recharger."""
    from apps.btp.models import ProjectSupply

    reponse = chantier['client'].post(
        reverse('btp:project_supply_create',
                kwargs={'project_pk': chantier['projet'].pk}),
        {
            'material': chantier['article'].pk,
            'quantity': '12',
            'purchase_date': '2026-11-14',
            'description': '', 'unit': '', 'unit_price': '', 'vat_rate': '',
            'reference': '', 'supplier': '', 'invoice_reference': '',
            'notes': '',
        })

    assert reponse.status_code == 302, (
        'le formulaire a refuse et reaffiche la page — exactement le '
        'symptome rapporte')

    achat = ProjectSupply.objects.get(project=chantier['projet'])
    assert achat.description == 'Plaque de plâtre BA13'
    assert achat.unit == 'm²'
    assert achat.unit_price == Decimal('4.2000')
    assert achat.total_ht == Decimal('50.40')


@pytest.mark.django_db
def test_la_date_du_jour_suffit_sans_etre_retapee(chantier):
    """Le champ est pré-rempli : sa valeur doit être ACCEPTÉE telle quelle.

    C'est le scénario réel — l'utilisateur ne retape pas la date, il
    enregistre avec celle qui s'affiche.
    """
    from apps.btp.forms import ProjectSupplyForm
    from apps.btp.models import ProjectSupply

    affichee = str(ProjectSupplyForm(company=chantier['entreprise'])
                   ['purchase_date']).split('value="')[1].split('"')[0]

    reponse = chantier['client'].post(
        reverse('btp:project_supply_create',
                kwargs={'project_pk': chantier['projet'].pk}),
        {'material': chantier['article'].pk, 'quantity': '1',
         'purchase_date': affichee, 'description': '', 'unit': '',
         'unit_price': '', 'vat_rate': '', 'reference': '', 'supplier': '',
         'invoice_reference': '', 'notes': ''})

    assert reponse.status_code == 302
    assert ProjectSupply.objects.filter(project=chantier['projet']).exists()


@pytest.mark.django_db
def test_un_refus_est_affiche_et_non_silencieux(chantier):
    """Si le formulaire refuse, il doit DIRE pourquoi. Un écran qui revient
    identique sans message est lu comme une panne — c'est toute l'histoire
    de ce ticket."""
    reponse = chantier['client'].post(
        reverse('btp:project_supply_create',
                kwargs={'project_pk': chantier['projet'].pk}),
        {'material': '', 'description': '', 'quantity': '1',
         'purchase_date': '2026-11-14', 'unit': '', 'unit_price': '',
         'vat_rate': '', 'reference': '', 'supplier': '',
         'invoice_reference': '', 'notes': ''})

    assert reponse.status_code == 200
    assert reponse.context['form'].errors
    assert 'désignation' in reponse.content.decode().lower()


# ── 3. La recherche et le remplissage ────────────────────────────────────────

@pytest.mark.django_db
def test_chaque_article_porte_ses_valeurs_dans_la_page(chantier):
    """Le remplissage automatique n'interroge pas le serveur : les valeurs
    voyagent avec la page, en attributs « data- »."""
    from apps.btp.forms import ProjectSupplyForm

    rendu = str(ProjectSupplyForm(company=chantier['entreprise'])['material'])

    assert 'data-designation="Plaque de plâtre BA13"' in rendu
    assert 'data-unite="m²"' in rendu
    assert 'data-prix="4.2000"' in rendu
    assert 'data-tva="20.00"' in rendu
    assert 'data-recherche="' in rendu


@pytest.mark.django_db
def test_la_recherche_porte_sur_plus_que_la_designation(chantier):
    """Chercher « cloison » ou une référence doit trouver l'article : c'est
    ainsi qu'on cherche sur un chantier, pas par le libellé exact."""
    from apps.btp.forms import ProjectSupplyForm

    rendu = str(ProjectSupplyForm(company=chantier['entreprise'])['material'])
    cible = rendu.split('data-recherche="')[1].split('"')[0]

    assert 'ba13' in cible
    assert 'cloison' in cible


@pytest.mark.django_db
def test_le_prix_de_vente_ne_part_pas_dans_la_page(chantier):
    """Le prix d'ACHAT suffit à la saisie d'un coût de chantier. Exposer le
    prix de vente et la marge dans un écran ouvert à tout salarié serait un
    choix, pas un oubli."""
    from apps.btp.forms import ProjectSupplyForm

    chantier['article'].sale_price = Decimal('9.9900')
    chantier['article'].save()

    rendu = str(ProjectSupplyForm(company=chantier['entreprise'])['material'])

    assert '9.99' not in rendu


def test_la_page_porte_une_barre_de_recherche():
    from pathlib import Path

    gabarit = Path('templates/btp/project_supply_form.html').read_text(
        encoding='utf-8')

    assert 'id="recherche-article"' in gabarit
    assert 'data-recherche' in gabarit, 'le filtre doit chercher sur ces valeurs'
    assert "addEventListener('change', remplir)" in gabarit, \
        'le choix d’un article doit remplir le formulaire'
