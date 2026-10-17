"""Devis : détail des matériels et fournitures, et signature automatique.

Trois propriétés gouvernent ce fichier.

**Le détail ne compte pas dans le prix.** `QuoteDetailLine` porte ce qui
sera mis en œuvre, imprimé pour justifier le prix ; `QuoteLine` porte ce qui
est facturé. Les mélanger ferait entrer le détail dans le total et
doublerait le devis.

**La nature n'a pas de valeur par défaut au formulaire.** Avec un défaut,
une fourniture laissée par inattention sur « Matériel » partirait dans le
mauvais bloc du devis sans que rien ne le signale.

**La signature est une IMAGE, pas du texte.** Elle se met à l'échelle en
gardant ses proportions — étirée à la largeur du cadre, elle ne ressemble
plus à la signature de personne. Et sa valeur texte étant vide par
construction, le filtre de `remplir_modele` devait apprendre à la garder :
il ne retenait que les champs porteurs de texte, et l'aurait écartée sans
jamais la dessiner.
"""

import io
import re
from decimal import Decimal

import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ── Terrain ─────────────────────────────────────────────────────────────────

def _pdf_vierge(pages=1, largeur=595, hauteur=842):
    from reportlab.pdfgen import canvas

    tampon = io.BytesIO()
    feuille = canvas.Canvas(tampon, pagesize=(largeur, hauteur))
    for _ in range(pages):
        feuille.setFont('Helvetica-Bold', 16)
        feuille.drawString(40, hauteur - 50, 'ENTREPRISE DUPONT')
        feuille.showPage()
    feuille.save()
    tampon.seek(0)
    return tampon.getvalue()


def _png_signature(largeur=600, hauteur=150):
    """Une fausse signature : large et plate, comme une vraie, fond transparent."""
    from PIL import Image

    image = Image.new('RGBA', (largeur, hauteur), (0, 0, 0, 0))
    for x in range(0, largeur, 3):
        image.putpixel((x, hauteur // 2 + (x % 20)), (10, 20, 120, 255))
    tampon = io.BytesIO()
    image.save(tampon, 'PNG')
    return tampon.getvalue()


def _flux(octets_ou_tampon):
    """Le contenu de la première page, DÉCOMPRESSÉ.

    reportlab compresse : chercher un opérateur dans les octets bruts ne
    trouve jamais rien, et un test écrit ainsi passerait sans rien prouver.
    """
    from pypdf import PdfReader

    if isinstance(octets_ou_tampon, bytes):
        octets_ou_tampon = io.BytesIO(octets_ou_tampon)
    page = PdfReader(octets_ou_tampon).pages[0]
    return page.get_contents().get_data().decode('latin-1')


class Cadre:
    def __init__(self, **kw):
        defauts = dict(cle='objet', page=1, x=50, y=500, largeur=200,
                       hauteur=20, taille=10, gras=False, alignement='left',
                       couleur='#000000', multiligne=False, prefixe='',
                       suffixe='')
        defauts.update(kw)
        self.__dict__.update(defauts)


@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Dupont SA', slug='dupont-sa')


@pytest.fixture
def autre_entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Martin SA', slug='martin-sa')


@pytest.fixture
def client_crm(entreprise):
    from apps.crm.models import Customer
    return Customer.objects.create(company=entreprise, name='Client Test')


@pytest.fixture
def devis(entreprise, client_crm):
    from apps.sales.models import Quote
    return Quote.objects.create(
        company=entreprise, number='DEV-0042', customer=client_crm,
        total_ht=Decimal('1000'), total_tva=Decimal('200'),
        total_ttc=Decimal('1200'))


@pytest.fixture
def modele(entreprise):
    from apps.sales.models import QuoteTemplate
    objet = QuoteTemplate.objects.create(
        company=entreprise, name='Devis standard', is_default=True)
    objet.pdf.save('modele.pdf', ContentFile(_pdf_vierge()), save=True)
    return objet


@pytest.fixture
def carrelage(entreprise):
    from apps.btp.models import Material
    return Material.objects.create(
        company=entreprise, kind='material', reference='CAR-6060',
        name='Carrelage grès cérame 60x60', unit='m²',
        purchase_price=Decimal('18.00'), sale_price=Decimal('25.00'),
        vat_rate=Decimal('10'))


@pytest.fixture
def signataire(entreprise, django_user_model):
    user = django_user_model.objects.create_user(
        username='patron', password='motdepasse-test',
        first_name='Jean', last_name='Dupont')
    user.profile.companies.add(entreprise)
    user.profile.current_company = entreprise
    user.profile.signature.save('signature.png',
                                ContentFile(_png_signature()), save=True)
    user.profile.save()
    return user


@pytest.fixture
def connecte(client, signataire):
    client.force_login(signataire)
    return client


def _ligne(devis, nature='materiel', **kw):
    from apps.sales.models import QuoteDetailLine

    donnees = dict(designation='Article', quantity=Decimal('1'), unit='u',
                   unit_price=Decimal('10'))
    donnees.update(kw)
    return QuoteDetailLine.objects.create(quote=devis, nature=nature,
                                          **donnees)


# ═══ LES DEUX BLOCS DE DÉTAIL ═══════════════════════════════════════════════

def test_le_bloc_porte_designation_quantite_et_prix_unitaire(devis):
    from apps.sales.quote_pdf import valeurs_du_devis

    _ligne(devis, 'materiel', designation='Carrelage grès cérame 60x60',
           quantity=Decimal('40'), unit='m²', unit_price=Decimal('25'))

    bloc = valeurs_du_devis(devis)['designation_materiels']
    assert bloc == 'Carrelage grès cérame 60x60 — 40 m² × 25,00 €'


def test_chaque_nature_va_dans_son_propre_bloc(devis):
    from apps.sales.quote_pdf import valeurs_du_devis

    _ligne(devis, 'materiel', designation='Carrelage', quantity=Decimal('40'),
           unit='m²', unit_price=Decimal('25'))
    _ligne(devis, 'fourniture', designation='Colle C2 25 kg',
           quantity=Decimal('12'), unit='sac', unit_price=Decimal('18.50'))

    valeurs = valeurs_du_devis(devis)
    assert 'Carrelage' in valeurs['designation_materiels']
    assert 'Colle C2' not in valeurs['designation_materiels']
    assert 'Colle C2' in valeurs['designation_fournitures']
    assert 'Carrelage' not in valeurs['designation_fournitures']


def test_plusieurs_articles_font_plusieurs_lignes(devis):
    from apps.sales.quote_pdf import valeurs_du_devis

    _ligne(devis, 'materiel', designation='Carrelage', order=1)
    _ligne(devis, 'materiel', designation='Plinthes', order=2)

    bloc = valeurs_du_devis(devis)['designation_materiels']
    assert len(bloc.splitlines()) == 2


def test_la_quantite_perd_ses_decimales_inutiles(devis):
    """« 40,000 m² » sur un devis se lit comme une précision affectée."""
    from apps.sales.quote_pdf import valeurs_du_devis

    _ligne(devis, 'materiel', designation='Carrelage',
           quantity=Decimal('40.000'), unit='m²', unit_price=Decimal('25'))
    _ligne(devis, 'fourniture', designation='Sable',
           quantity=Decimal('2.500'), unit='t', unit_price=Decimal('30'))

    valeurs = valeurs_du_devis(devis)
    assert '40 m²' in valeurs['designation_materiels']
    assert '2,5 t' in valeurs['designation_fournitures']


def test_sans_detail_les_deux_blocs_restent_vides(devis):
    """Un cadre sans valeur n'imprime rien — mieux qu'un bloc vide encadré."""
    from apps.sales.quote_pdf import valeurs_du_devis

    valeurs = valeurs_du_devis(devis)
    assert valeurs['designation_materiels'] == ''
    assert valeurs['designation_fournitures'] == ''


def test_l_apercu_du_modele_ne_tombe_pas_en_panne(entreprise):
    """devis_exemple() n'est pas enregistré : interroger ses lignes lèverait
    « instance needs to have a primary key ». Déjà payé une fois sur le taux
    de TVA, donc prévu dès l'écriture cette fois."""
    from apps.sales.quote_pdf import devis_exemple, valeurs_du_devis

    valeurs = valeurs_du_devis(devis_exemple(entreprise))
    assert valeurs['designation_materiels'] == ''
    assert valeurs['designation_fournitures'] == ''


def test_les_caracteres_du_bloc_existent_dans_WinAnsi(devis):
    """Le tiret cadratin, le signe multiplié, l'euro et le m² doivent
    s'imprimer. U+202F, lui, donnait un carré noir — leçon déjà payée sur le
    séparateur de milliers, donc vérifiée ici sur le PDF rendu."""
    from apps.sales.quote_pdf import _page_de_texte, valeurs_du_devis

    _ligne(devis, 'materiel', designation='Carrelage',
           quantity=Decimal('40'), unit='m²', unit_price=Decimal('25'))
    valeurs = valeurs_du_devis(devis)

    cadre = Cadre(cle='designation_materiels', multiligne=True, largeur=400,
                  hauteur=60, taille=9)
    flux = _flux(_page_de_texte([cadre], valeurs, 595, 842))

    # Une seule ecriture : le texte n'a pas ete coupe par un glyphe absent.
    assert flux.count(') Tj') == 1
    b = chr(92)
    assert b + '227' in flux, 'tiret cadratin (0x97)'
    assert b + '327' in flux, 'signe multiplie (0xD7)'
    assert b + '200' in flux, 'euro (0x80)'
    assert b + '262' in flux, 'exposant deux (0xB2)'


def test_le_detail_n_entre_PAS_dans_les_totaux(devis):
    """La garantie qui évite de doubler un devis."""
    from apps.sales.models import QuoteLine

    QuoteLine.objects.create(quote=devis, description='Pose', quantity=1,
                             unit_price=Decimal('1000'),
                             vat_rate=Decimal('20'))
    _ligne(devis, 'materiel', designation='Carrelage', quantity=Decimal('40'),
           unit_price=Decimal('25'))

    devis.calculate_totals()
    devis.refresh_from_db()
    assert devis.total_ht == Decimal('1000.00')


def test_le_total_d_une_ligne_de_detail_se_calcule(devis):
    ligne = _ligne(devis, 'materiel', quantity=Decimal('40'),
                   unit_price=Decimal('25.50'))
    assert ligne.total_ht == Decimal('1020.000')


# ═══ LA SAISIE DU DÉTAIL ════════════════════════════════════════════════════

def test_la_nature_n_a_pas_de_valeur_par_defaut(entreprise):
    """Avec un défaut, une fourniture laissée sur « Matériel » partirait
    dans le mauvais bloc sans que rien ne le signale."""
    from apps.sales.forms import QuoteDetailLineForm

    form = QuoteDetailLineForm(company=entreprise)
    valeurs = [v for v, _ in form.fields['nature'].choices]
    assert valeurs[0] == '', valeurs


def test_une_ligne_sans_nature_est_refusee(entreprise):
    from apps.sales.forms import QuoteDetailLineForm

    form = QuoteDetailLineForm({
        'nature': '', 'designation': 'Carrelage', 'quantity': '40',
        'unit': 'm²', 'unit_price': '25',
    }, company=entreprise)
    assert not form.is_valid()
    assert 'nature' in form.errors


def test_l_article_du_catalogue_remplit_la_ligne(entreprise, carrelage):
    from apps.sales.forms import QuoteDetailLineForm

    form = QuoteDetailLineForm({
        'nature': 'materiel', 'material': carrelage.pk, 'designation': '',
        'quantity': '40', 'unit': '', 'unit_price': '',
    }, company=entreprise)

    assert form.is_valid(), form.errors
    assert form.cleaned_data['designation'] == 'Carrelage grès cérame 60x60'
    assert form.cleaned_data['unit'] == 'm²'
    # Prix de VENTE : ce bloc est imprime sur le devis remis au client.
    assert form.cleaned_data['unit_price'] == carrelage.sale_price
    assert form.cleaned_data['unit_price'] != carrelage.purchase_price


def test_le_prix_saisi_prime_sur_le_catalogue(entreprise, carrelage):
    from apps.sales.forms import QuoteDetailLineForm

    form = QuoteDetailLineForm({
        'nature': 'materiel', 'material': carrelage.pk, 'designation': '',
        'quantity': '40', 'unit': '', 'unit_price': '29.90',
    }, company=entreprise)

    assert form.is_valid(), form.errors
    assert form.cleaned_data['unit_price'] == Decimal('29.90')


def test_une_ligne_hors_catalogue_exige_une_designation(entreprise):
    from apps.sales.forms import QuoteDetailLineForm

    form = QuoteDetailLineForm({
        'nature': 'materiel', 'material': '', 'designation': '',
        'quantity': '1', 'unit': 'u', 'unit_price': '10',
    }, company=entreprise)
    assert not form.is_valid()
    assert 'designation' in form.errors


def test_un_article_d_une_autre_entreprise_est_refuse_a_la_VALIDATION(
        entreprise, autre_entreprise):
    """Borner la seule liste affichée laisserait passer un identifiant
    forgé."""
    from apps.btp.models import Material
    from apps.sales.forms import QuoteDetailLineForm

    etranger = Material.objects.create(
        company=autre_entreprise, name='Article voisin',
        sale_price=Decimal('99'))

    form = QuoteDetailLineForm({
        'nature': 'materiel', 'material': etranger.pk,
        'designation': 'Tentative', 'quantity': '1', 'unit': 'u',
        'unit_price': '99',
    }, company=entreprise)

    assert not form.is_valid()
    assert 'material' in form.errors


def test_l_ecran_de_modification_enregistre_le_detail(connecte, devis,
                                                      carrelage):
    from apps.sales.models import QuoteDetailLine

    reponse = connecte.post(reverse('sales:quote_edit', args=[devis.pk]), {
        'customer': devis.customer.pk, 'subject': 'Rénovation',
        'issue_date': '2026-10-17', 'payment_terms': '30',
        'discount_rate': '0', 'status': 'draft',
        'cout_materiels': '0', 'cout_fournitures': '0',
        'cout_main_oeuvre': '0', 'taches_principales': '',
        'detail_lines-TOTAL_FORMS': '3',
        'detail_lines-INITIAL_FORMS': '0',
        'detail_lines-MIN_NUM_FORMS': '0',
        'detail_lines-MAX_NUM_FORMS': '1000',
        'detail_lines-0-nature': 'materiel',
        'detail_lines-0-material': str(carrelage.pk),
        'detail_lines-0-designation': '',
        'detail_lines-0-quantity': '40',
        'detail_lines-0-unit': '',
        'detail_lines-0-unit_price': '',
        'detail_lines-1-nature': 'fourniture',
        'detail_lines-1-material': '',
        'detail_lines-1-designation': 'Colle C2 25 kg',
        'detail_lines-1-quantity': '12',
        'detail_lines-1-unit': 'sac',
        'detail_lines-1-unit_price': '18.50',
        'detail_lines-2-nature': '',
        'detail_lines-2-material': '',
        'detail_lines-2-designation': '',
        'detail_lines-2-quantity': '',
        'detail_lines-2-unit': '',
        'detail_lines-2-unit_price': '',
    })

    assert reponse.status_code == 302, reponse.context['detail'].errors
    lignes = QuoteDetailLine.objects.filter(quote=devis)
    # La troisieme ligne, vide, n'a rien cree.
    assert lignes.count() == 2
    materiel = lignes.get(nature='materiel')
    assert materiel.designation == 'Carrelage grès cérame 60x60'
    assert materiel.unit_price == Decimal('25.0000')


def test_l_ecran_de_modification_borne_le_client(connecte, devis,
                                                 autre_entreprise):
    """Cette ligne manquait à la modification alors qu'elle existait à la
    création : un identifiant forgé rattachait le devis au client d'une
    AUTRE entreprise."""
    from apps.crm.models import Customer

    etranger = Customer.objects.create(company=autre_entreprise,
                                       name='Client voisin')

    connecte.post(reverse('sales:quote_edit', args=[devis.pk]), {
        'customer': etranger.pk, 'issue_date': '2026-10-17',
        'payment_terms': '30', 'discount_rate': '0', 'status': 'draft',
        'cout_materiels': '0', 'cout_fournitures': '0',
        'cout_main_oeuvre': '0', 'taches_principales': '',
        'detail_lines-TOTAL_FORMS': '0',
        'detail_lines-INITIAL_FORMS': '0',
        'detail_lines-MIN_NUM_FORMS': '0',
        'detail_lines-MAX_NUM_FORMS': '1000',
    })

    devis.refresh_from_db()
    assert devis.customer != etranger


def test_la_fiche_du_devis_montre_le_detail(connecte, devis):
    _ligne(devis, 'materiel', designation='Carrelage grès cérame',
           quantity=Decimal('40'), unit='m²', unit_price=Decimal('25'))

    corps = connecte.get(
        reverse('sales:quote_detail', args=[devis.pk])).content.decode()
    assert 'Carrelage grès cérame' in corps
    assert '1000,00' in corps or '1000.00' in corps


# ═══ LA SIGNATURE ═══════════════════════════════════════════════════════════

def test_la_signature_vient_du_commercial(devis, signataire,
                                          django_user_model):
    """Même règle que pour le nom du commercial, afin que le nom imprimé et
    la signature apposée désignent toujours la même personne."""
    from apps.sales.quote_pdf import images_du_devis

    autre = django_user_model.objects.create_user(
        username='autre', password='motdepasse-test')
    devis.created_by = autre
    devis.salesperson = signataire
    devis.save()

    assert images_du_devis(devis)['signature'] is not None


def test_a_defaut_de_commercial_c_est_l_auteur_du_devis(devis, signataire):
    from apps.sales.quote_pdf import images_du_devis

    devis.salesperson = None
    devis.created_by = signataire
    devis.save()

    assert images_du_devis(devis)['signature'] is not None


def test_sans_signature_enregistree_le_cadre_reste_vide(devis,
                                                        django_user_model):
    """Un compte sans signature ne doit pas empêcher d'éditer un devis."""
    from apps.sales.quote_pdf import images_du_devis

    sans = django_user_model.objects.create_user(
        username='sans-signature', password='motdepasse-test')
    devis.salesperson = sans
    devis.save()

    assert images_du_devis(devis)['signature'] is None


def test_un_devis_sans_auteur_ne_casse_pas(devis):
    from apps.sales.quote_pdf import images_du_devis

    devis.salesperson = None
    devis.created_by = None
    devis.save()

    assert images_du_devis(devis)['signature'] is None


def test_la_signature_garde_ses_proportions():
    """Étirée à la largeur du cadre, une signature ne ressemble plus à la
    signature de personne."""
    from apps.sales.quote_pdf import _page_de_texte

    # 600x150, soit 4:1. Dans un cadre de 150x50, elle doit faire 150x37,5
    # et etre centree verticalement : 90 + (50 - 37,5) / 2 = 96,25.
    cadre = Cadre(cle='signature', x=380, y=90, largeur=150, hauteur=50)
    flux = _flux(_page_de_texte(
        [cadre], {'signature': ''}, 595, 842,
        images={'signature': io.BytesIO(_png_signature())}))

    matrices = re.findall(r'([\d.]+) 0 0 ([\d.]+) ([\d.]+) ([\d.]+) cm', flux)
    assert matrices, flux
    largeur, hauteur, x, y = (float(v) for v in matrices[-1])
    assert largeur == pytest.approx(150, abs=0.01)
    assert hauteur == pytest.approx(37.5, abs=0.01)
    assert y == pytest.approx(96.25, abs=0.01)
    assert ' Do' in flux


def test_un_fichier_illisible_ne_casse_pas_la_generation():
    """Un réglage douteux ne doit pas empêcher d'imprimer un devis."""
    from apps.sales.quote_pdf import _page_de_texte

    cadre = Cadre(cle='signature', largeur=150, hauteur=50)
    flux = _flux(_page_de_texte(
        [cadre], {'signature': ''}, 595, 842,
        images={'signature': io.BytesIO(b'ceci n-est pas une image')}))

    assert ' Do' not in flux


def test_un_cadre_de_taille_nulle_ne_dessine_rien():
    from apps.sales.quote_pdf import _page_de_texte

    cadre = Cadre(cle='signature', largeur=0, hauteur=0)
    flux = _flux(_page_de_texte(
        [cadre], {'signature': ''}, 595, 842,
        images={'signature': io.BytesIO(_png_signature())}))

    assert ' Do' not in flux


def test_le_devis_complet_porte_la_signature(devis, modele, signataire):
    """Le bout en bout. Le filtre de remplir_modele ne retenait que les
    champs porteurs de TEXTE : la signature, dont la valeur texte est vide
    par construction, aurait été écartée sans jamais être dessinée."""
    from apps.sales.models import QuoteTemplateField
    from apps.sales.quote_pdf import remplir_modele

    devis.salesperson = signataire
    devis.save()
    QuoteTemplateField.objects.create(
        template=modele, cle='signature', page=1, x=380, y=90,
        largeur=150, hauteur=50)

    flux = _flux(remplir_modele(devis, modele))
    assert ' Do' in flux


def test_sans_signature_le_devis_se_genere_quand_meme(devis, modele,
                                                      django_user_model):
    from apps.sales.models import QuoteTemplateField
    from apps.sales.quote_pdf import remplir_modele

    sans = django_user_model.objects.create_user(
        username='sans', password='motdepasse-test')
    devis.salesperson = sans
    devis.save()
    QuoteTemplateField.objects.create(
        template=modele, cle='signature', page=1, x=380, y=90,
        largeur=150, hauteur=50)

    tampon = remplir_modele(devis, modele)
    assert tampon.read(5).startswith(b'%PDF')


def test_le_profil_permet_de_deposer_sa_signature(connecte):
    from apps.accounts.forms import UserProfileForm

    assert 'signature' in UserProfileForm.base_fields
    corps = connecte.get(reverse('accounts:profile')).content.decode()
    assert 'name="signature"' in corps


# ═══ COHÉRENCE ══════════════════════════════════════════════════════════════

def test_les_cles_image_concordent_entre_le_module_et_le_modele():
    """Deux listes écrites séparément finissent par différer, et le dessin
    traiterait alors une image comme du texte."""
    from apps.sales.models import QuoteTemplateField
    from apps.sales.quote_pdf import CLES_IMAGE

    assert CLES_IMAGE == QuoteTemplateField.CLES_IMAGE


def test_les_trois_nouvelles_valeurs_sont_placables():
    from apps.sales.models import QuoteTemplateField

    cles = {cle for cle, _ in QuoteTemplateField.CLES}
    for attendue in ('designation_materiels', 'designation_fournitures',
                     'signature'):
        assert attendue in cles, attendue


def test_chaque_cle_placable_a_une_valeur(devis):
    from apps.sales.models import QuoteTemplateField
    from apps.sales.quote_pdf import valeurs_du_devis

    valeurs = valeurs_du_devis(devis)
    for cle, _ in QuoteTemplateField.CLES:
        assert cle in valeurs, cle


def test_l_editeur_propose_les_nouvelles_valeurs(connecte, modele):
    corps = connecte.get(
        reverse('sales:quote_template_editor', args=[modele.pk])
    ).content.decode()

    for cle in ('designation_materiels', 'designation_fournitures',
                'signature'):
        assert f'data-cle="{cle}"' in corps, cle
