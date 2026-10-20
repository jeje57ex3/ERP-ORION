"""Détecter des articles dans un PDF ou sur une page web.

**Le détecteur PROPOSE, l'exploitant VALIDE.** Rien n'entre au catalogue
sans avoir été coché. C'est ce qui rend l'exercice acceptable là où une
synchronisation automatique depuis des pages web installerait des erreurs
que personne ne surveille : ici, une extraction qui se trompe se voit dans
le tableau, et on ne coche rien.

**Les prix relevés sont des REPÈRES**, marqués `prix_indicatif=True`. Un
tarif public n'est pas un tarif négocié. Sans cette marque, rien ne
distinguerait plus, six mois après, un prix confirmé d'un prix recopié
d'une page web — et un devis partirait avec le second en croyant le
premier.

**Côté web, on lit les données STRUCTURÉES**, pas la mise en page : JSON-LD,
microdonnées, OpenGraph. Trois formats que les fabricants publient
délibérément, normalisés, et qui survivent à une refonte du site.

**La limite est dite, pas masquée** : une page qui charge ses prix en
JavaScript ne livre rien, et le détecteur explique pourquoi au lieu de
rendre une liste vide sans raison.
"""

import io
import json
from decimal import Decimal

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ── Terrain ─────────────────────────────────────────────────────────────────

def _pdf_tarif(lignes=None, avec_entete=True):
    """Un PDF de tarif, tel qu'un négoce en publie."""
    from reportlab.pdfgen import canvas

    lignes = lignes if lignes is not None else [
        'A9F74216   Disjoncteur iC60N 2P 16A courbe C        u       38,90',
        'A9F74220   Disjoncteur iC60N 2P 20A courbe C        u       41,20',
        'ICTA-20    Gaine ICTA 3422 diametre 20 - 100m       ml       0,74',
    ]
    tampon = io.BytesIO()
    feuille = canvas.Canvas(tampon, pagesize=(595, 842))
    y = 800
    if avec_entete:
        feuille.setFont('Helvetica-Bold', 11)
        feuille.drawString(40, y, 'TARIF 2026 - APPAREILLAGE')
        y -= 20
        feuille.setFont('Helvetica-Bold', 9)
        feuille.drawString(40, y, 'Reference Designation Unite Prix HT')
        y -= 16
    feuille.setFont('Helvetica', 9)
    for ligne in lignes:
        feuille.drawString(40, y, ligne)
        y -= 14
    feuille.drawString(40, y - 20, 'Page 1')
    feuille.showPage()
    feuille.save()
    return tampon.getvalue()


def _pdf_sans_texte():
    """Un PDF qui ne porte qu'une image : le cas du document scanné."""
    from reportlab.pdfgen import canvas

    tampon = io.BytesIO()
    feuille = canvas.Canvas(tampon, pagesize=(595, 842))
    feuille.rect(50, 50, 200, 100, fill=1)
    feuille.showPage()
    feuille.save()
    return tampon.getvalue()


def _page_jsonld(nom='Disjoncteur iC60N 2P 16A courbe C', sku='A9F74216',
                 prix='38.90'):
    charge = {
        '@context': 'https://schema.org',
        '@type': 'Product',
        'name': nom,
        'sku': sku,
        'offers': {'@type': 'Offer', 'price': prix, 'priceCurrency': 'EUR'},
    }
    return (f'<html><head><script type="application/ld+json">'
            f'{json.dumps(charge)}</script></head><body>décor</body></html>')


@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Dupont SA', slug='dupont-sa')


@pytest.fixture
def connecte(client, entreprise, django_user_model):
    user = django_user_model.objects.create_user(
        username='patron', password='motdepasse-test')
    user.profile.companies.add(entreprise)
    user.profile.current_company = entreprise
    user.profile.save()
    client.force_login(user)
    return client


# ═══ LE PDF ═════════════════════════════════════════════════════════════════

def test_un_tarif_pdf_est_decoupe_en_articles():
    from apps.btp.catalogue_detection import detecter_dans_pdf

    candidats, message = detecter_dans_pdf(_pdf_tarif())

    assert len(candidats) == 3, message
    premier = candidats[0]
    assert premier['reference'] == 'A9F74216'
    assert premier['nom'] == 'Disjoncteur iC60N 2P 16A courbe C'
    assert premier['unite'] == 'u'
    assert Decimal(premier['prix']) == Decimal('38.90')


def test_l_entete_de_colonnes_n_est_pas_un_article():
    """Répété en haut de chaque page, il créerait un article
    « Reference Designation Prix »."""
    from apps.btp.catalogue_detection import detecter_dans_pdf

    candidats, _ = detecter_dans_pdf(_pdf_tarif())
    noms = {c['nom'].lower() for c in candidats}
    assert not any('designation' in n for n in noms)


def test_le_numero_de_page_n_est_pas_un_article():
    from apps.btp.catalogue_detection import detecter_dans_pdf

    candidats, _ = detecter_dans_pdf(_pdf_tarif())
    assert not any(c['nom'].strip().lower() == 'page' for c in candidats)


def test_le_prix_est_pris_en_FIN_de_ligne():
    """« Tube 32 mm ... 4,15 » : chercher un nombre n'importe où prendrait
    le diamètre pour un prix."""
    from apps.btp.catalogue_detection import detecter_dans_pdf

    candidats, _ = detecter_dans_pdf(_pdf_tarif([
        'TUB-32   Tube PER 32 mm couronne 50 m        ml      4,15',
    ]))
    assert len(candidats) == 1
    assert Decimal(candidats[0]['prix']) == Decimal('4.15')


def test_une_ligne_sans_prix_n_est_pas_proposee():
    """Sans prix, la ligne n'apporte pas ce qu'on vient chercher."""
    from apps.btp.catalogue_detection import detecter_dans_pdf

    candidats, _ = detecter_dans_pdf(_pdf_tarif([
        'Nos conditions generales de vente sont disponibles sur demande',
    ]))
    assert candidats == []


def test_un_pdf_scanne_explique_pourquoi_il_ne_donne_rien():
    """« Rien trouvé » sans raison n'aide personne : un PDF scanné, un PDF
    sans texte et un PDF mal mis en page ne se corrigent pas pareil."""
    from apps.btp.catalogue_detection import detecter_dans_pdf

    candidats, message = detecter_dans_pdf(_pdf_sans_texte())

    assert candidats == []
    assert 'scann' in message.lower()
    assert 'CSV' in message or 'Excel' in message


def test_un_pdf_illisible_est_refuse_proprement():
    from apps.btp.catalogue_detection import detecter_dans_pdf
    from apps.btp.catalogue_import import CatalogueError

    with pytest.raises(CatalogueError):
        detecter_dans_pdf(b'ceci n-est pas un PDF')


def test_le_nombre_de_candidats_est_borne():
    """Au-delà, ce n'est plus un aperçu qu'on relit mais une liste qu'on
    accepte en aveugle — ce que cet écran cherche à éviter."""
    from apps.btp.catalogue_detection import CANDIDATS_MAX, detecter_dans_pdf

    lignes = [f'REF{n:04d}   Article numero {n} de la gamme   u   {n},50'
              for n in range(1, CANDIDATS_MAX + 60)]
    candidats, _ = detecter_dans_pdf(_pdf_tarif(lignes, avec_entete=False))
    assert len(candidats) <= CANDIDATS_MAX


# ═══ LA PAGE WEB ════════════════════════════════════════════════════════════

def test_le_jsonld_est_lu():
    """Le format que publient les fabricants pour les moteurs de
    recherche : normalisé, et stable à travers les refontes."""
    from apps.btp.catalogue_detection import detecter_dans_page

    candidats, message = detecter_dans_page(_page_jsonld())

    assert len(candidats) == 1
    assert candidats[0]['reference'] == 'A9F74216'
    assert Decimal(candidats[0]['prix']) == Decimal('38.90')
    assert 'JSON-LD' in message


def test_un_jsonld_imbrique_dans_un_graphe_est_trouve():
    """Les pages imbriquent de plusieurs façons. On parcourt plutôt que de
    deviner la forme."""
    from apps.btp.catalogue_detection import detecter_dans_page

    charge = {'@context': 'https://schema.org', '@graph': [
        {'@type': 'BreadcrumbList'},
        {'@type': 'Product', 'name': 'Gaine ICTA 20', 'sku': 'ICTA20',
         'offers': {'price': '0.74'}},
    ]}
    html = (f'<html><head><script type="application/ld+json">'
            f'{json.dumps(charge)}</script></head></html>')

    candidats, _ = detecter_dans_page(html)
    assert len(candidats) == 1
    assert candidats[0]['nom'] == 'Gaine ICTA 20'


def test_une_liste_de_produits_donne_plusieurs_articles():
    from apps.btp.catalogue_detection import detecter_dans_page

    charge = [
        {'@type': 'Product', 'name': 'Disjoncteur 16A',
         'offers': {'price': '38.90'}},
        {'@type': 'Product', 'name': 'Disjoncteur 20A',
         'offers': {'price': '41.20'}},
    ]
    html = (f'<html><head><script type="application/ld+json">'
            f'{json.dumps(charge)}</script></head></html>')

    candidats, _ = detecter_dans_page(html)
    assert len(candidats) == 2


def test_un_bloc_jsonld_casse_ne_perd_pas_les_autres():
    from apps.btp.catalogue_detection import detecter_dans_page

    html = ('<html><head>'
            '<script type="application/ld+json">{ceci n est pas du json'
            '</script>'
            '<script type="application/ld+json">'
            '{"@type":"Product","name":"Article valide",'
            '"offers":{"price":"10"}}</script>'
            '</head></html>')

    candidats, _ = detecter_dans_page(html)
    assert len(candidats) == 1
    assert candidats[0]['nom'] == 'Article valide'


def test_le_prix_se_trouve_dans_une_priceSpecification():
    from apps.btp.catalogue_detection import detecter_dans_page

    charge = {'@type': 'Product', 'name': 'Cable R2V 3G2,5',
              'offers': {'priceSpecification': {'price': '1.96'}}}
    html = (f'<html><head><script type="application/ld+json">'
            f'{json.dumps(charge)}</script></head></html>')

    candidats, _ = detecter_dans_page(html)
    assert Decimal(candidats[0]['prix']) == Decimal('1.96')


def test_les_microdonnees_servent_de_second_recours():
    from apps.btp.catalogue_detection import detecter_dans_page

    html = ('<html><body itemscope itemtype="https://schema.org/Product">'
            '<meta itemprop="name" content="Interrupteur differentiel 40A">'
            '<meta itemprop="sku" content="A9R11240">'
            '<meta itemprop="price" content="104,50">'
            '</body></html>')

    candidats, message = detecter_dans_page(html)
    assert len(candidats) == 1
    assert candidats[0]['reference'] == 'A9R11240'
    assert Decimal(candidats[0]['prix']) == Decimal('104.50')
    assert 'microdonn' in message


def test_l_opengraph_sert_de_dernier_recours():
    from apps.btp.catalogue_detection import detecter_dans_page

    html = ('<html><head>'
            '<meta property="og:title" content="Gaine ICTA 3422 D20">'
            '<meta property="product:price:amount" content="24,50">'
            '</head></html>')

    candidats, message = detecter_dans_page(html)
    assert len(candidats) == 1
    assert Decimal(candidats[0]['prix']) == Decimal('24.50')
    assert 'OpenGraph' in message


def test_le_jsonld_a_la_priorite_sur_l_opengraph():
    """Le plus fiable d'abord : l'OpenGraph d'une page produit porte
    souvent le titre commercial, pas la désignation technique."""
    from apps.btp.catalogue_detection import detecter_dans_page

    html = ('<html><head>'
            '<meta property="og:title" content="Titre marketing accrocheur">'
            '<script type="application/ld+json">'
            '{"@type":"Product","name":"Designation technique exacte",'
            '"offers":{"price":"38.90"}}</script>'
            '</head></html>')

    candidats, _ = detecter_dans_page(html)
    assert len(candidats) == 1
    assert candidats[0]['nom'] == 'Designation technique exacte'


def test_une_page_en_javascript_explique_pourquoi_elle_ne_donne_rien():
    """La cause la plus fréquente d'un résultat vide. Le détecteur ne doit
    pas laisser attribuer à une panne ce qui est une limite."""
    from apps.btp.catalogue_detection import detecter_dans_page

    candidats, message = detecter_dans_page(
        '<html><body><div id="app"></div></body></html>')

    assert candidats == []
    assert 'APRÈS' in message or 'après' in message
    assert 'navigateur' in message


def test_un_doublon_entre_deux_formats_est_fusionne():
    """Deux formats décrivent le même produit, pas deux produits."""
    from apps.btp.catalogue_detection import detecter_dans_page

    html = ('<html><head>'
            '<script type="application/ld+json">'
            '{"@type":"Product","name":"Article unique","sku":"REF1",'
            '"offers":{"price":"10"}}</script>'
            '<script type="application/ld+json">'
            '{"@type":"Product","name":"Article unique","sku":"REF1"}'
            '</script></head></html>')

    candidats, _ = detecter_dans_page(html)
    assert len(candidats) == 1
    # Celui qui porte un prix est garde : c'est l'information rare.
    assert candidats[0]['prix']


def test_la_detection_par_url_passe_par_la_garde_reseau(monkeypatch):
    """Même règle que l'import de catalogue : l'adresse vient de
    l'utilisateur, et c'est le serveur qui la récupère. Deux chemins de
    téléchargement, c'est un chemin qui finit sans garde."""
    from apps.btp.catalogue_detection import detecter_depuis_url
    from apps.btp.catalogue_import import CatalogueError

    with pytest.raises(CatalogueError) as echec:
        detecter_depuis_url('http://127.0.0.1/produit')
    assert 'interne' in str(echec.value)


def test_la_detection_par_url_lit_la_page(monkeypatch):
    from apps.btp import catalogue_detection

    monkeypatch.setattr(
        catalogue_detection, 'detecter_dans_page',
        lambda html: ([{'nom': 'depuis le reseau'}], 'ok'))
    monkeypatch.setattr(
        'apps.btp.catalogue_import.telecharger_url',
        lambda url, session=None: _page_jsonld().encode('utf-8'))

    candidats, message = catalogue_detection.detecter_depuis_url(
        'https://exemple.test/p')
    assert candidats[0]['nom'] == 'depuis le reseau'


# ═══ LE FORMULAIRE ══════════════════════════════════════════════════════════

def test_une_adresse_ET_un_pdf_ensemble_sont_refuses():
    """Trancher en silence ferait analyser l'un en ignorant l'autre."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.btp.forms_catalogue import DetectionForm

    form = DetectionForm(
        {'url': 'https://exemple.test/p'},
        {'fichier': SimpleUploadedFile('t.pdf', _pdf_tarif(),
                                       content_type='application/pdf')})
    assert not form.is_valid()
    assert 'fichier' in form.errors


def test_ni_adresse_ni_pdf_est_refuse():
    from apps.btp.forms_catalogue import DetectionForm

    form = DetectionForm({'url': ''}, {})
    assert not form.is_valid()
    assert 'url' in form.errors


def test_un_faux_pdf_est_refuse():
    """L'extension ne prouve rien : un .docx renommé passerait."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.btp.forms_catalogue import DetectionForm

    form = DetectionForm({}, {'fichier': SimpleUploadedFile(
        'faux.pdf', b'PK\x03\x04 pas un pdf',
        content_type='application/pdf')})
    assert not form.is_valid()
    assert 'fichier' in form.errors


# ═══ L'ÉCRAN ET L'ENREGISTREMENT ════════════════════════════════════════════

def test_l_ecran_de_detection_s_affiche(connecte):
    corps = connecte.get(reverse('btp:catalogue_detection')).content.decode()
    assert 'Détecter' in corps
    # La limite est dite sur l'ecran, pas seulement dans le code.
    assert 'navigateur' in corps


def test_deposer_un_pdf_affiche_l_apercu(connecte):
    from django.core.files.uploadedfile import SimpleUploadedFile

    reponse = connecte.post(reverse('btp:catalogue_detection'), {
        'url': '',
        'fichier': SimpleUploadedFile('tarif.pdf', _pdf_tarif(),
                                       content_type='application/pdf'),
    })
    corps = reponse.content.decode()

    assert 'A9F74216' in corps
    assert 'Disjoncteur iC60N 2P 16A courbe C' in corps
    assert 'retenu' in corps


def test_seuls_les_articles_coches_sont_enregistres(connecte, entreprise):
    from apps.btp.models import Material

    connecte.post(reverse('btp:catalogue_detection_import'), {
        'nature': 'supply', 'cible_prix': 'achat',
        'retenu': ['0', '2'],
        'nom_0': 'Disjoncteur 16A', 'reference_0': 'A9F74216',
        'unite_0': 'u', 'prix_0': '38.90',
        'nom_1': 'Disjoncteur 20A', 'reference_1': 'A9F74220',
        'unite_1': 'u', 'prix_1': '41.20',
        'nom_2': 'Gaine ICTA 20', 'reference_2': 'ICTA20',
        'unite_2': 'ml', 'prix_2': '0.74',
    })

    references = set(Material.objects.values_list('reference', flat=True))
    assert references == {'A9F74216', 'ICTA20'}
    assert 'A9F74220' not in references


def test_les_articles_detectes_sont_marques_INDICATIFS(connecte, entreprise):
    """La garantie centrale : un tarif public n'est pas un tarif négocié."""
    from apps.btp.models import Material

    connecte.post(reverse('btp:catalogue_detection_import'), {
        'nature': 'material', 'cible_prix': 'achat', 'retenu': ['0'],
        'nom_0': 'Disjoncteur 16A', 'reference_0': 'A9F74216',
        'unite_0': 'u', 'prix_0': '38.90',
    })

    article = Material.objects.get()
    assert article.prix_indicatif is True
    assert article.purchase_price == Decimal('38.9000')
    # Le prix de vente reste a l'exploitant.
    assert article.sale_price == Decimal('0')


def test_le_prix_releve_peut_aller_en_prix_de_VENTE(connecte, entreprise):
    """Une page fabricant publie un tarif public, plus proche d'un prix de
    vente que d'un coût d'achat négocié : l'exploitant tranche."""
    from apps.btp.models import Material

    connecte.post(reverse('btp:catalogue_detection_import'), {
        'nature': 'material', 'cible_prix': 'vente', 'retenu': ['0'],
        'nom_0': 'Disjoncteur 16A', 'reference_0': 'A9F74216',
        'unite_0': 'u', 'prix_0': '38.90',
    })

    article = Material.objects.get()
    assert article.sale_price == Decimal('38.9000')
    assert article.purchase_price == Decimal('0')
    assert article.prix_indicatif is True


def test_un_article_deja_au_catalogue_n_est_pas_ecrase(connecte, entreprise):
    """Écraser un prix ferme par un prix de repère serait exactement
    l'inverse de ce qu'on cherche."""
    from apps.btp.models import Material

    Material.objects.create(
        company=entreprise, reference='A9F74216', name='Disjoncteur 16A',
        purchase_price=Decimal('31.20'), prix_indicatif=False)

    connecte.post(reverse('btp:catalogue_detection_import'), {
        'nature': 'material', 'cible_prix': 'achat', 'retenu': ['0'],
        'nom_0': 'Disjoncteur 16A autre libelle',
        'reference_0': 'A9F74216', 'unite_0': 'u', 'prix_0': '99.00',
    })

    assert Material.objects.count() == 1
    article = Material.objects.get()
    assert article.purchase_price == Decimal('31.2000')
    assert article.prix_indicatif is False


def test_l_apercu_signale_les_doublons_sans_les_masquer(connecte,
                                                        entreprise):
    """Les masquer ferait douter de la détection elle-même."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.btp.models import Material

    Material.objects.create(company=entreprise, reference='A9F74216',
                            name='Deja la')

    reponse = connecte.post(reverse('btp:catalogue_detection'), {
        'url': '',
        'fichier': SimpleUploadedFile('tarif.pdf', _pdf_tarif(),
                                       content_type='application/pdf'),
    })
    corps = reponse.content.decode()
    assert 'A9F74216' in corps
    assert 'déjà au catalogue' in corps


def test_une_nature_forgee_est_refusee(connecte, entreprise):
    from apps.btp.models import Material

    connecte.post(reverse('btp:catalogue_detection_import'), {
        'nature': 'n-importe-quoi', 'retenu': ['0'],
        'nom_0': 'Article', 'prix_0': '10',
    })
    assert not Material.objects.exists()


def test_un_prix_forge_ne_casse_pas_l_enregistrement(connecte, entreprise):
    """Les champs cachés viennent du navigateur : revalidés côté serveur."""
    from apps.btp.models import Material

    connecte.post(reverse('btp:catalogue_detection_import'), {
        'nature': 'material', 'cible_prix': 'achat', 'retenu': ['0'],
        'nom_0': 'Article', 'reference_0': '', 'unite_0': 'u',
        'prix_0': 'pas un prix',
    })

    article = Material.objects.get()
    assert article.purchase_price == Decimal('0')


def test_rien_de_coche_ne_cree_rien(connecte, entreprise):
    from apps.btp.models import Material

    reponse = connecte.post(reverse('btp:catalogue_detection_import'), {
        'nature': 'material', 'cible_prix': 'achat',
    })
    assert reponse.status_code == 302
    assert not Material.objects.exists()


def test_l_enregistrement_refuse_un_GET(connecte):
    reponse = connecte.get(reverse('btp:catalogue_detection_import'))
    assert reponse.status_code == 405


def test_les_ecrans_exigent_une_connexion(client, entreprise):
    for nom in ('btp:catalogue_detection',
                'btp:catalogue_detection_import'):
        assert client.get(reverse(nom)).status_code in (302, 405)


# ═══ RETROUVER CE QUI ATTEND UN VRAI TARIF ══════════════════════════════════

def test_le_catalogue_signale_un_prix_indicatif(connecte, entreprise):
    from apps.btp.models import Material

    Material.objects.create(
        company=entreprise, name='Disjoncteur releve', unit='u',
        purchase_price=Decimal('38.90'), prix_indicatif=True)

    corps = connecte.get(reverse('btp:material_list')).content.decode()
    assert 'indicatif' in corps


def test_le_catalogue_se_filtre_sur_les_prix_a_confirmer(connecte,
                                                          entreprise):
    """Sans ce filtre, retrouver ce qui attend un vrai tarif demanderait de
    parcourir tout le catalogue à l'œil."""
    from apps.btp.models import Material

    Material.objects.create(company=entreprise, name='Prix a confirmer',
                            prix_indicatif=True)
    Material.objects.create(company=entreprise, name='Prix ferme negocie',
                            prix_indicatif=False)

    corps = connecte.get(reverse('btp:material_list'),
                         {'indicatif': '1'}).content.decode()
    assert 'Prix a confirmer' in corps
    assert 'Prix ferme negocie' not in corps


def test_le_formulaire_permet_de_confirmer_un_prix(connecte, entreprise):
    """Décocher la case est le geste qui fait passer l'article de
    « à tarifer » à « ferme »."""
    from apps.btp.forms import MaterialForm

    assert 'prix_indicatif' in MaterialForm.base_fields
    corps = connecte.get(reverse('btp:material_create')).content.decode()
    assert 'prix_indicatif' in corps
