"""Explorer le catalogue public d'un fabricant.

Les extracteurs de ce module sont écrits sur le HTML RÉEL des quatre sites,
sondé page en main, et les fragments ci-dessous reproduisent ce qui y a été
mesuré — pas ce que ces pages sont censées contenir.

Ce que la mesure a donné :

- **Hager** publie du JSON-LD `Product` + `Offer` : `name` (NRN425), `sku`
  (NRN4257), `price` (428.27). Lecture exacte, sans heuristique, et son
  prix est HT recommandé.
- **Legrand** n'a aucun JSON-LD produit : microdonnées, référence dans le
  nom de l'image (`th_LG-CG0001`), EAN répété, et un prix **conseillé
  TTC**.
- **Soprema** marque `og:type=product` mais **ne publie aucun prix** : le
  seul montant du HTML est « 0,00 », vérifié sur deux pages de deux
  domaines.
- **Schneider** ne sert pas ses fiches en HTML : l'adresse d'une référence
  renvoie la page générique « tous les produits ».

**La propriété la plus importante : le prix ne va jamais dans
`purchase_price`.** Un prix de détail public — TTC chez Legrand, HT
recommandé chez Hager — n'est pas le prix auquel l'entreprise achète,
remise professionnelle comprise. L'y écrire fausserait toutes les marges, et
l'erreur ne se verrait qu'en lisant un devis parti chez un client. Une case
vide se complète ; un chiffre faux se facture.

Aucun test ne touche le réseau : les fragments sont locaux, et `dormir` est
injecté pour que la temporisation ne ralentisse pas la suite.
"""

import json
from decimal import Decimal

import pytest

from apps.btp.catalogue_crawl import (
    ExplorationError,
    SITES,
    extraire_hager,
    extraire_legrand,
    extraire_soprema,
    explorer,
    importer_candidats,
    liens_de,
    produit_jsonld,
    site_de,
)
from apps.btp.models import Material

pytestmark = pytest.mark.django_db


# ── Fragments reproduisant le HTML mesuré ───────────────────────────────────

JSONLD_HAGER = json.dumps({
    '@context': 'https://schema.org',
    '@type': 'Product',
    'name': 'NRN425',
    'sku': 'NRN4257',
    'brand': {'@type': 'Brand', 'name': 'Hager'},
    'offers': {'@type': 'Offer', 'price': '428.27', 'priceCurrency': 'EUR'},
})

HTML_HAGER = f"""<!doctype html><html><head>
<meta property="og:type" content="product">
<meta property="og:title" content="Disjoncteur 4P 25kA C-25A 4M &bull; NRN425 | Hager">
<script type="application/ld+json">{{"@type":"Organization","name":"Hager"}}</script>
<script type="application/ld+json">{JSONLD_HAGER}</script>
</head><body>
<span class="price">428,27 &euro; HT</span>
<span>3250614628184</span><span>3250614628184</span>
</body></html>"""

HTML_LEGRAND = """<!doctype html><html><head>
<meta property="og:locale" content="fr_FR">
<meta property="og:title" content="Interrupteur ou va-et-vient 10A C&eacute;liane avec plaque -">
<meta property="og:image" content="https://www.legrand.fr/sites/default/files/ecat/th_LG-CG0001.jpg">
<meta itemprop="sku" content="0 673 01">
<script type="application/ld+json">{"@type":"Organization"}</script>
</head><body itemtype="https://schema.org/Product">
<div class="c-product-price__content"><span class="c-product-price__value" itemprop="price" content="14.67" >14,67</span><small itemprop="priceCurrency">&euro;</small></div>
<p>CG0001 </p>
<span>3414972441445</span><span>3414972441445</span><span>3414972441445</span>
</body></html>"""

HTML_SOPREMA = """<!doctype html><html><head>
<meta property="og:type" content="product">
<meta property="og:title" content="Membrane&#x20;d&#x27;&#xC9;tanch&#xE9;it&#xE9;&#x20;Ardois&#xE9;e">
</head><body itemtype="https://schema.org/Product">
<p>R&eacute;f&eacute;rence 00105879</p>
<span class="price">0,00</span>
</body></html>"""


# ── 1. Hager : lecture exacte ───────────────────────────────────────────────

def test_le_jsonld_produit_est_trouve_sous_plusieurs_blocs():
    """Un site sert plusieurs blocs ; le Product n'est pas le premier.

    Chercher au premier niveau du premier bloc manquerait la moitié des
    pages.
    """
    produit = produit_jsonld(HTML_HAGER)
    assert produit is not None
    assert produit['name'] == 'NRN425'


def test_hager_est_lu_sans_heuristique():
    candidat = extraire_hager(HTML_HAGER, 'https://hager.com/fr/x')
    assert candidat['reference'] == 'NRN425'
    assert candidat['nom'] == 'Disjoncteur 4P 25kA C-25A 4M'
    assert candidat['prix'] == Decimal('428.27')
    assert candidat['prix_ht'] is True
    assert candidat['origine'] == 'JSON-LD Product'


def test_hager_retient_name_et_non_sku_comme_reference():
    """`sku` porte NRN4257, une variante à chiffre supplémentaire.

    Ce n'est pas la référence qu'un bon de commande emploie — c'est
    NRN425. Prendre `sku` parce qu'il s'appelle « sku » aurait donné une
    référence introuvable chez le distributeur.
    """
    candidat = extraire_hager(HTML_HAGER, 'https://hager.com/fr/x')
    assert candidat['reference'] == 'NRN425'
    assert candidat['reference'] != 'NRN4257'


def test_hager_sans_jsonld_ne_rend_rien():
    """Mieux vaut rien qu'un candidat deviné sur une page inattendue."""
    assert extraire_hager('<html><body>rien</body></html>',
                          'https://hager.com/fr/x') is None


# ── 2. Legrand : microdonnées et texte ──────────────────────────────────────

def test_legrand_lit_la_reference_officielle():
    """`itemprop="sku"` porte la référence Legrand, espaces retirés.

    « 0 673 01 » devient « 067301 », la forme qu'emploie un bon de
    commande.
    """
    candidat = extraire_legrand(HTML_LEGRAND,
                                'https://www.legrand.fr/catalogue/a/b')
    assert candidat['reference'] == '067301'


def test_legrand_ne_prend_jamais_la_reference_d_un_produit_voisin():
    """DÉFAUT MESURÉ, et le plus grave des trois.

    Une fiche Legrand affiche des produits VOISINS. Mon repli cherchait
    « deux lettres et quatre chiffres » dans TOUTE la page : la boîte
    Batibox 090501 repartait avec la référence CG0001, celle d'un
    interrupteur Céliane. Constaté sur l'export de 1 704 fiches — deux
    articles différents sous la même référence.

    Sans sku ni image exploitable, la référence reste VIDE. Le
    rapprochement se fait alors sur la désignation : une référence absente
    est honnête, une référence fausse fait collisionner deux produits.
    """
    html = ('<meta property="og:title" content="Bo&icirc;te Batibox">'
            '<meta property="og:image" content="/img/sans-code.jpg">'
            '<body>Voir aussi : CG0001, CG0111, CB9416</body>')
    candidat = extraire_legrand(html, 'https://www.legrand.fr/catalogue/a/b')
    assert candidat['reference'] == ''
    assert candidat['nom'] == 'Boîte Batibox'


def test_legrand_lit_le_code_numerique_de_son_image():
    """Repli : « th_090501-LEGRAND.jpg » porte le code de LA fiche.

    On ne lit que l'og:image, jamais le corps de la page — c'est
    précisément ce qui évitait la confusion avec un produit voisin.
    """
    html = ('<meta property="og:title" content="Bo&icirc;te Batibox">'
            '<meta property="og:image" content="/files/ecat/th_090501-LEGRAND.jpg">')
    candidat = extraire_legrand(html, 'https://www.legrand.fr/catalogue/a/b')
    assert candidat['reference'] == '090501'


def test_legrand_decode_les_entites_du_titre():
    candidat = extraire_legrand(HTML_LEGRAND,
                                'https://www.legrand.fr/catalogue/a/b')
    assert candidat['nom'] == 'Interrupteur ou va-et-vient 10A Céliane avec plaque'


def test_legrand_marque_son_prix_comme_ttc():
    """LE point qui empêche de le confondre avec un prix d'achat.

    14,67 € est un conseillé TTC, prix de détail public. L'entreprise, avec
    sa remise professionnelle, paie une fraction de ce montant.
    """
    candidat = extraire_legrand(HTML_LEGRAND,
                                'https://www.legrand.fr/catalogue/a/b')
    assert candidat['prix'] == Decimal('14.67')
    assert candidat['prix_ht'] is False


def test_legrand_lit_le_prix_dans_les_microdonnees():
    """DEFAUT MESURE : mon premier motif exigeait un « € » collé au montant.

    Or le symbole est dans un `<small>` séparé, et le prix vit dans
    `itemprop="price" content="14.67"`. L'extraction ne trouvait donc
    AUCUN prix sur les 1 704 fiches Legrand — vérifié en lançant
    l'exploration : 20 fiches lues, 20 produits, zéro prix.

    L'attribut `content` est en plus exact et déjà normalisé au point
    décimal.
    """
    candidat = extraire_legrand(HTML_LEGRAND,
                                'https://www.legrand.fr/catalogue/a/b')
    assert candidat['prix'] == Decimal('14.67')


def test_legrand_recupere_l_ean():
    candidat = extraire_legrand(HTML_LEGRAND,
                                'https://www.legrand.fr/catalogue/a/b')
    assert candidat['ean'] == '3414972441445'


def test_un_horodatage_n_est_pas_pris_pour_un_ean():
    """Mesure faite sur se.com : des nombres à 13 chiffres y abondent, qui
    sont des horodatages JavaScript en millisecondes.

    Un EAN de produit est répété dans la page et ne commence pas par 17.
    """
    html = HTML_LEGRAND.replace('3414972441445', '1741703396768')
    candidat = extraire_legrand(html, 'https://www.legrand.fr/catalogue/a/b')
    assert candidat['ean'] == ''


# ── 3. Soprema : aucun prix, et c'est dit ───────────────────────────────────

def test_soprema_ne_rend_jamais_de_prix():
    """Le seul montant du HTML est « 0,00 », vérifié sur deux domaines.

    Reprendre ce zéro serait pire que de n'en mettre aucun : zéro est un
    prix, et un devis le facturerait.
    """
    candidat = extraire_soprema(HTML_SOPREMA,
                                'https://particuliers.soprema.fr/produits/x')
    assert candidat['prix'] is None
    assert candidat['prix_ht'] is None


def test_soprema_lit_sa_designation_entierement_encodee():
    """Les titres de Soprema arrivent encodés caractère par caractère."""
    candidat = extraire_soprema(HTML_SOPREMA,
                                'https://particuliers.soprema.fr/produits/x')
    assert candidat['nom'] == "Membrane d'Étanchéité Ardoisée"


def test_soprema_lit_son_code_article():
    candidat = extraire_soprema(HTML_SOPREMA,
                                'https://particuliers.soprema.fr/produits/x')
    assert candidat['reference'] == '00105879'


# ── 4. Schneider : refusé en nommant la cause ───────────────────────────────

@pytest.mark.parametrize('url', [
    'https://www.se.com/fr/fr/product/A9F74210/',
    'https://se.com/fr/fr/all-products/',
    'https://www.schneider-electric.fr/fr/product/A9F74210/',
])
def test_schneider_est_refuse_avec_sa_raison(url):
    """« Échec » n'est pas actionnable ; la raison l'est.

    L'adresse d'une référence renvoie la page générique « tous les
    produits », et les données produit sont construites par le navigateur.
    Lancer une exploration d'une heure pour ne rien rapporter serait pire
    qu'un refus immédiat.
    """
    with pytest.raises(ExplorationError) as echec:
        site_de(url)
    message = str(echec.value)
    assert 'navigateur' in message or 'HTML' in message
    assert 'tarif Excel' in message or 'Schneider' in message


def test_un_site_inconnu_est_refuse_en_listant_les_connus():
    with pytest.raises(ExplorationError) as echec:
        site_de('https://exemple-inconnu.fr/catalogue')
    assert 'legrand.fr' in str(echec.value)


@pytest.mark.parametrize('url,attendu', [
    ('https://www.legrand.fr/catalogue/x', 'Legrand'),
    ('https://hager.com/fr/catalogue/produits/y', 'Hager'),
    ('https://particuliers.soprema.fr/produits/z', 'Soprema'),
])
def test_les_sites_geres_sont_reconnus(url, attendu):
    assert site_de(url)['nom'] == attendu


# ── 5. Les liens suivis ─────────────────────────────────────────────────────

def test_seuls_les_liens_du_meme_hote_sont_suivis():
    """Un lien sortant vers un distributeur emmènerait l'exploration sur un
    site dont rien n'est su — ni le format, ni les prix."""
    html = ('<a href="/catalogue/a/b">ici</a>'
            '<a href="https://autre-site.fr/catalogue/a/b">ailleurs</a>')
    liens = liens_de(html, 'https://www.legrand.fr/catalogue/gamme',
                     SITES['legrand.fr']['liste'])
    assert liens == ['https://www.legrand.fr/catalogue/a/b']


def test_les_liens_hors_motif_sont_ignores():
    """Sans motif, l'exploration suivrait les mentions légales et le blog."""
    html = ('<a href="/catalogue/a/b">produit</a>'
            '<a href="/mentions-legales">legal</a>'
            '<a href="/blog/article">blog</a>')
    liens = liens_de(html, 'https://www.legrand.fr/catalogue/gamme',
                     SITES['legrand.fr']['liste'])
    assert liens == ['https://www.legrand.fr/catalogue/a/b']


def test_les_liens_sont_dedoublonnes_et_sans_ancre():
    html = ('<a href="/catalogue/a/b">x</a>'
            '<a href="/catalogue/a/b#bas">x</a>'
            '<a href="/catalogue/a/b">x</a>')
    liens = liens_de(html, 'https://www.legrand.fr/catalogue/g',
                     SITES['legrand.fr']['liste'])
    assert liens == ['https://www.legrand.fr/catalogue/a/b']


# ── 6. Le parcours ──────────────────────────────────────────────────────────

@pytest.fixture
def faux_reseau(monkeypatch):
    """Sert des pages locales, et compte les requêtes."""
    from apps.btp import catalogue_crawl

    pages = {
        'https://hager.com/fr/catalogue/gamme': (
            '<a href="/fr/catalogue/produits/nrn425">a</a>'
            '<a href="/fr/catalogue/produits/nfn216">b</a>'),
        'https://hager.com/fr/catalogue/produits/nrn425': HTML_HAGER,
        'https://hager.com/fr/catalogue/produits/nfn216': HTML_HAGER.replace(
            'NRN425', 'NFN216').replace('428.27', '112.75'),
    }
    journal = {'requetes': [], 'siestes': []}

    def faux_telecharger(url, session=None):
        journal['requetes'].append(url)
        if url not in pages:
            raise catalogue_crawl.CatalogueError(f'404 {url}')
        return pages[url].encode('utf-8')

    monkeypatch.setattr(catalogue_crawl, 'telecharger_url', faux_telecharger)
    return journal


def test_le_parcours_trouve_les_produits_de_la_gamme(faux_reseau):
    candidats, visitees, message = explorer(
        'https://hager.com/fr/catalogue/gamme', delai=0,
        dormir=lambda d: faux_reseau['siestes'].append(d))

    references = sorted(c['reference'] for c in candidats)
    assert references == ['NFN216', 'NRN425']
    assert len(visitees) == 3
    assert 'Hager' in message


def test_le_parcours_temporise_entre_les_requetes(faux_reseau):
    """Envoyer les requêtes en rafale fait tomber l'exploration sur un
    blocage — en plus de charger le serveur du fabricant sans égard."""
    explorer('https://hager.com/fr/catalogue/gamme', delai=1.5,
             dormir=lambda d: faux_reseau['siestes'].append(d))
    # Trois pages, deux attentes : pas d'attente avant la première.
    assert faux_reseau['siestes'] == [1.5, 1.5]


def test_le_parcours_respecte_la_borne_de_pages(faux_reseau):
    """Sans borne, une erreur de motif ferait tourner l'exploration jusqu'à
    épuisement."""
    candidats, visitees, message = explorer(
        'https://hager.com/fr/catalogue/gamme', pages_max=2, delai=0,
        dormir=lambda d: None)
    assert len(faux_reseau['requetes']) == 2
    assert 'restantes' in message


def test_le_parcours_reprend_ou_il_s_etait_arrete(faux_reseau):
    """Un catalogue complet ne passe pas en une fois.

    Recommencer à zéro chaque exécution rendrait la chose interminable.
    """
    candidats, _visitees, _m = explorer(
        'https://hager.com/fr/catalogue/gamme', delai=0,
        deja_vues=['https://hager.com/fr/catalogue/produits/nrn425'],
        dormir=lambda d: None)
    references = [c['reference'] for c in candidats]
    assert references == ['NFN216']
    assert 'https://hager.com/fr/catalogue/produits/nrn425' not in \
        faux_reseau['requetes']


def test_une_page_en_echec_ne_perd_pas_les_autres(faux_reseau):
    """Une fiche retirée du catalogue ne doit pas interrompre la gamme."""
    from apps.btp import catalogue_crawl

    pages_html = (
        '<a href="/fr/catalogue/produits/nrn425">bon</a>'
        '<a href="/fr/catalogue/produits/disparu">cassé</a>')

    def telecharger(url, session=None):
        if url.endswith('/gamme'):
            return pages_html.encode('utf-8')
        if url.endswith('/nrn425'):
            return HTML_HAGER.encode('utf-8')
        raise catalogue_crawl.CatalogueError('404')

    import pytest as _pytest
    _pytest.MonkeyPatch().setattr(catalogue_crawl, 'telecharger_url',
                                  telecharger)
    candidats, _v, _m = explorer('https://hager.com/fr/catalogue/gamme',
                                 delai=0, dormir=lambda d: None)
    assert [c['reference'] for c in candidats] == ['NRN425']


def test_les_liens_ne_sont_suivis_que_depuis_les_listes(faux_reseau):
    """Une fiche renvoie vers des dizaines de produits voisins.

    Les suivre ferait déborder le parcours hors de la gamme demandée.
    """
    explorer('https://hager.com/fr/catalogue/produits/nrn425', delai=0,
             dormir=lambda d: None)
    assert faux_reseau['requetes'] == [
        'https://hager.com/fr/catalogue/produits/nrn425']


# ── 7. L'import : le prix d'achat reste vide ────────────────────────────────

@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(name='Dupont SA', slug='dupont-sa')


CANDIDATS = [
    {'reference': 'NRN425', 'nom': 'Disjoncteur 4P 25kA C-25A 4M',
     'prix': Decimal('428.27'), 'prix_ht': True, 'ean': '',
     'url': 'https://hager.com/fr/x', 'origine': 'JSON-LD Product'},
    {'reference': 'CG0001', 'nom': 'Interrupteur Céliane 10A',
     'prix': Decimal('14.67'), 'prix_ht': False, 'ean': '',
     'url': 'https://www.legrand.fr/y', 'origine': 'microdonnées'},
]


def test_le_prix_est_marque_indicatif(entreprise):
    """LE mécanisme du modèle, et il existait déjà.

    `prix_indicatif` est un BOOLÉEN — « Prix de repère relevé sur un site
    ou un PDF public, en attendant le tarif négocié. Décochez quand le prix
    est confirmé. » Le prix va donc dans `purchase_price`, marqué à
    confirmer. Un prix de repère visible et marqué vaut mieux qu'un champ
    vide ; c'est la marque qui rend la chose honnête.
    """
    importer_candidats(entreprise, CANDIDATS, a_blanc=False)
    for article in Material.objects.filter(company=entreprise):
        assert article.prix_indicatif is True, article
        assert article.purchase_price > 0


def test_un_prix_ht_est_repris_tel_quel(entreprise):
    """Hager publie du HT recommandé : rien à convertir."""
    importer_candidats(entreprise, CANDIDATS, a_blanc=False)
    assert Material.objects.get(
        reference='NRN425').purchase_price == Decimal('428.27')


def test_un_prix_ttc_est_ramene_en_ht(entreprise):
    """Le champ est libellé « Prix d'achat HT ».

    Legrand publie du conseillé TTC. L'y verser tel quel gonflerait le coût
    de chantier de vingt pour cent — 14,67 au lieu de 12,23.
    """
    importer_candidats(entreprise, CANDIDATS, a_blanc=False)
    article = Material.objects.get(reference='CG0001')
    assert article.purchase_price == Decimal('12.23')   # 14,67 / 1,20
    assert 'TTC ramené en HT' in article.description


def test_l_essai_a_blanc_n_ecrit_rien(entreprise):
    compteurs = importer_candidats(entreprise, CANDIDATS, a_blanc=True)
    assert compteurs['crees'] == 2
    assert Material.objects.count() == 0


def test_un_prix_confirme_a_la_main_est_intouchable(entreprise):
    """Un catalogue public ne doit pas pouvoir effacer un tarif négocié.

    `prix_indicatif` décoché signifie « ce prix est confirmé » : c'est
    précisément la marque que le modèle prévoit pour ça.
    """
    article = Material.objects.create(
        company=entreprise, name='Disjoncteur 4P 25kA C-25A 4M',
        reference='NRN425', kind='material',
        purchase_price=Decimal('210.00'), prix_indicatif=False)

    compteurs = importer_candidats(entreprise, CANDIDATS, a_blanc=False)

    article.refresh_from_db()
    assert article.purchase_price == Decimal('210.00')
    assert compteurs['proteges'] == 1


def test_un_prix_encore_indicatif_est_reactualise(entreprise):
    """Tant qu'il n'est pas confirmé, un relevé plus récent le remplace."""
    article = Material.objects.create(
        company=entreprise, name='Disjoncteur 4P 25kA C-25A 4M',
        reference='NRN425', kind='material',
        purchase_price=Decimal('399.00'), prix_indicatif=True)

    importer_candidats(entreprise, CANDIDATS, a_blanc=False)

    article.refresh_from_db()
    assert article.purchase_price == Decimal('428.27')
    assert article.prix_indicatif is True


def test_un_candidat_sans_prix_n_est_pas_marque_indicatif(entreprise):
    """Soprema n'en publie aucun.

    Cocher « prix indicatif » sur un article sans prix ferait croire à un
    chiffre à vérifier là où il n'y a rien.
    """
    importer_candidats(entreprise, [{
        'reference': '00105879', 'nom': "Membrane d'Étanchéité Ardoisée",
        'prix': None, 'prix_ht': None, 'ean': '',
        'url': 'https://particuliers.soprema.fr/x', 'origine': 'OpenGraph'}],
        nature='supply', a_blanc=False)

    article = Material.objects.get(reference='00105879')
    assert article.kind == 'supply'
    assert article.prix_indicatif is False
    assert article.purchase_price == Decimal('0')


def test_un_candidat_sans_nom_est_ignore(entreprise):
    compteurs = importer_candidats(
        entreprise, [{'reference': 'X', 'nom': '  ', 'prix': None}],
        a_blanc=False)
    assert compteurs['ignores'] == 1
    assert Material.objects.count() == 0


def test_un_second_passage_ne_duplique_pas(entreprise):
    importer_candidats(entreprise, CANDIDATS, a_blanc=False)
    compteurs = importer_candidats(entreprise, CANDIDATS, a_blanc=False)
    assert compteurs['crees'] == 0
    assert compteurs['inchanges'] == 2
    assert Material.objects.filter(company=entreprise).count() == 2


def test_les_articles_d_une_autre_entreprise_ne_sont_pas_vus(entreprise):
    """Le rapprochement par référence doit rester cloisonné."""
    from apps.core.models import Company

    autre = Company.objects.create(name='Martin SA', slug='martin-sa')
    Material.objects.create(company=autre, name='Déjà là',
                            reference='NRN425', kind='material')

    compteurs = importer_candidats(entreprise, CANDIDATS, a_blanc=False)
    assert compteurs['crees'] == 2
    assert Material.objects.filter(company=entreprise,
                                    reference='NRN425').count() == 1


# ── 8. L'énumération par sitemap ────────────────────────────────────────────
#
# Mesure qui a changé la conception : ramper dans la navigation ne marche
# pas. Chaque page porte le menu complet du site, et un parcours parti de
# la gamme Céliane se retrouvait quatorze pages plus loin dans les tableaux
# électriques sans avoir vu une seule fiche produit.
#
# Les sitemaps énumèrent directement ce qu'on cherche — 1 704 fiches chez
# Legrand, 6 706 chez Hager, mesuré — et c'est aussi beaucoup plus
# respectueux du serveur : on ne visite que ce que le fabricant a lui-même
# déclaré.

SITEMAP_INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://hager.com/fr/plan-a.xml</loc></sitemap>
  <sitemap><loc>https://hager.com/fr/plan-b.xml</loc></sitemap>
</sitemapindex>"""

SITEMAP_A = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://hager.com/fr/catalogue/produits/nrn425-x</loc></url>
  <url><loc>https://hager.com/fr/actualites/un-article</loc></url>
</urlset>"""

SITEMAP_B = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://hager.com/fr/catalogue/produits/nfn216-y</loc></url>
</urlset>"""


@pytest.fixture
def faux_sitemap(monkeypatch):
    from apps.btp import catalogue_crawl

    pages = {
        'https://hager.com/sitemap-index.xml': SITEMAP_INDEX,
        'https://hager.com/fr/plan-a.xml': SITEMAP_A,
        'https://hager.com/fr/plan-b.xml': SITEMAP_B,
        'https://hager.com/fr/catalogue/produits/nrn425-x': HTML_HAGER,
        'https://hager.com/fr/catalogue/produits/nfn216-y': HTML_HAGER.replace(
            'NRN425', 'NFN216'),
    }
    journal = {'requetes': []}

    def faux_telecharger(url, session=None):
        journal['requetes'].append(url)
        if url not in pages:
            raise catalogue_crawl.CatalogueError(f'404 {url}')
        return pages[url].encode('utf-8')

    monkeypatch.setattr(catalogue_crawl, 'telecharger_url', faux_telecharger)
    monkeypatch.setitem(catalogue_crawl.SITES['hager.com'], 'sitemap',
                        'https://hager.com/sitemap-index.xml')
    return journal


def test_un_index_de_sitemap_est_suivi(faux_sitemap):
    """Hager sert un index de 65 sous-plans ; lire l'index seul ne donnerait
    aucune URL de fiche."""
    from apps.btp.catalogue_crawl import urls_du_sitemap

    urls = urls_du_sitemap('https://hager.com/sitemap-index.xml', delai=0,
                           dormir=lambda d: None)
    assert 'https://hager.com/fr/catalogue/produits/nrn425-x' in urls
    assert 'https://hager.com/fr/catalogue/produits/nfn216-y' in urls


def test_le_filtre_ecarte_ce_qui_n_est_pas_une_fiche(faux_sitemap):
    """Sans filtre, on récupérerait les 38 968 URL de Legrand — blog,
    questions fréquentes, pages pro — pour 1 704 fiches utiles."""
    from apps.btp.catalogue_crawl import SITES, fiches_du_sitemap

    fiches = fiches_du_sitemap(SITES['hager.com'], delai=0,
                               dormir=lambda d: None)
    assert all('/catalogue/produits/' in f for f in fiches)
    assert not any('actualites' in f for f in fiches)
    assert len(fiches) == 2


def test_le_parcours_par_sitemap_trouve_les_produits(faux_sitemap):
    from apps.btp.catalogue_crawl import explorer_sitemap

    candidats, vues, message = explorer_sitemap(
        'https://hager.com/fr/catalogue/produits/nrn425-x', delai=0,
        dormir=lambda d: None)
    references = sorted(c['reference'] for c in candidats)
    assert references == ['NFN216', 'NRN425']
    assert 'sitemap' in message


def test_le_parcours_par_sitemap_reprend_ou_il_s_etait_arrete(faux_sitemap):
    """8 410 fiches pour Legrand et Hager réunis : ça ne passe pas en une
    fois, et recommencer à zéro rendrait la chose interminable."""
    from apps.btp.catalogue_crawl import explorer_sitemap

    candidats, _vues, _m = explorer_sitemap(
        'https://hager.com/fr/catalogue/produits/nrn425-x', delai=0,
        deja_vues=['https://hager.com/fr/catalogue/produits/nrn425-x'],
        dormir=lambda d: None)
    assert [c['reference'] for c in candidats] == ['NFN216']


def test_le_parcours_par_sitemap_respecte_la_borne(faux_sitemap):
    from apps.btp.catalogue_crawl import explorer_sitemap

    candidats, _vues, message = explorer_sitemap(
        'https://hager.com/fr/catalogue/produits/nrn425-x', pages_max=1,
        delai=0, dormir=lambda d: None)
    assert len(candidats) == 1
    assert 'restantes' in message


def test_un_site_sans_sitemap_le_dit(monkeypatch):
    """Soprema n'en déclare pas d'exploitable : le refus doit être clair,
    pas un parcours vide."""
    from apps.btp import catalogue_crawl
    from apps.btp.catalogue_crawl import ExplorationError, explorer_sitemap

    monkeypatch.setitem(catalogue_crawl.SITES['soprema.fr'], 'sitemap', None)
    with pytest.raises(ExplorationError) as echec:
        explorer_sitemap('https://www.soprema.fr/produits-et-systemes/x')
    assert 'sitemap' in str(echec.value)


# ── 9. Le mode « liste d'adresses » ─────────────────────────────────────────
#
# Seule voie pour Soprema. Mesure faite, et sans appel :
#   /sitemap.xml renvoie une IMAGE PNG (octets 89 50 4e 47), sur
#   www.soprema.fr comme sur particuliers.soprema.fr ;
#   /produits ne porte QU'UN lien produit — la liste est construite par le
#   navigateur ;
#   /produits-et-systemes répond 404 sur www.
#
# Il n'y a donc rien à énumérer automatiquement. Les fiches individuelles,
# elles, se lisent très bien : code 00105879, désignation complète. D'où ce
# mode, qui part d'une liste d'adresses fournie.

def test_la_liste_fournie_est_visitee(monkeypatch):
    from apps.btp import catalogue_crawl
    from apps.btp.catalogue_crawl import explorer_liste

    pages = {
        'https://particuliers.soprema.fr/produits/a': HTML_SOPREMA,
        'https://hager.com/fr/catalogue/produits/b': HTML_HAGER,
    }
    monkeypatch.setattr(
        catalogue_crawl, 'telecharger_url',
        lambda url, session=None: pages[url].encode('utf-8'))

    candidats, vues, message = explorer_liste(
        list(pages), delai=0, dormir=lambda d: None)
    assert len(candidats) == 2
    assert 'Liste fournie' in message


def test_la_liste_peut_melanger_les_fabricants(monkeypatch):
    """Le site est déterminé adresse par adresse, pas une fois pour toutes."""
    from apps.btp import catalogue_crawl
    from apps.btp.catalogue_crawl import explorer_liste

    pages = {
        'https://particuliers.soprema.fr/produits/a': HTML_SOPREMA,
        'https://hager.com/fr/catalogue/produits/b': HTML_HAGER,
    }
    monkeypatch.setattr(
        catalogue_crawl, 'telecharger_url',
        lambda url, session=None: pages[url].encode('utf-8'))

    candidats, _vues, _m = explorer_liste(list(pages), delai=0,
                                          dormir=lambda d: None)
    references = sorted(c['reference'] for c in candidats)
    assert references == ['00105879', 'NRN425']


def test_une_adresse_refusee_ne_perd_pas_les_autres(monkeypatch):
    """Une ligne Schneider au milieu d'une liste ne doit pas tout arrêter."""
    from apps.btp import catalogue_crawl
    from apps.btp.catalogue_crawl import explorer_liste

    monkeypatch.setattr(
        catalogue_crawl, 'telecharger_url',
        lambda url, session=None: HTML_HAGER.encode('utf-8'))

    candidats, _vues, message = explorer_liste(
        ['https://www.se.com/fr/fr/product/A9F74210/',
         'https://hager.com/fr/catalogue/produits/b'],
        delai=0, dormir=lambda d: None)
    assert [c['reference'] for c in candidats] == ['NRN425']
    assert 'refusee' in message


def test_les_lignes_vides_et_commentees_sont_ignorees(monkeypatch):
    from apps.btp import catalogue_crawl
    from apps.btp.catalogue_crawl import explorer_liste

    appels = []

    def telecharger(url, session=None):
        appels.append(url)
        return HTML_HAGER.encode('utf-8')

    monkeypatch.setattr(catalogue_crawl, 'telecharger_url', telecharger)
    explorer_liste(['', '   ', '# un commentaire',
                    'https://hager.com/fr/catalogue/produits/b'],
                   delai=0, dormir=lambda d: None)
    assert appels == ['https://hager.com/fr/catalogue/produits/b']


def test_la_liste_reprend_ou_elle_s_etait_arretee(monkeypatch):
    from apps.btp import catalogue_crawl
    from apps.btp.catalogue_crawl import explorer_liste

    appels = []

    def telecharger(url, session=None):
        appels.append(url)
        return HTML_HAGER.encode('utf-8')

    monkeypatch.setattr(catalogue_crawl, 'telecharger_url', telecharger)
    explorer_liste(['https://hager.com/fr/catalogue/produits/a',
                    'https://hager.com/fr/catalogue/produits/b'],
                   deja_vues=['https://hager.com/fr/catalogue/produits/a'],
                   delai=0, dormir=lambda d: None)
    assert appels == ['https://hager.com/fr/catalogue/produits/b']


# ── 10. L'écriture au fil de l'eau ──────────────────────────────────────────
#
# DÉFAUT CONSTATÉ, ET COÛTEUX. Le résultat n'était rendu qu'à la fin du
# parcours : un passage de 1 519 pages Legrand a été interrompu, et tout a
# été perdu — pas une ligne, pas même l'état de reprise. Vingt minutes de
# requêtes pour rien.
#
# Ce n'était pas qu'un délai d'attente mal choisi : un parcours de vingt
# minutes DOIT rendre ses résultats au fur et à mesure, parce qu'il est
# assez long pour être interrompu. Le rappel `au_fil` est appelé dès qu'une
# fiche est lue, et l'appelant l'écrit immédiatement.

def test_le_rappel_est_appele_des_qu_une_fiche_est_lue(faux_reseau):
    """Et non à la fin : c'est toute la différence."""
    from apps.btp.catalogue_crawl import explorer

    vus = []
    candidats, _visitees, _m = explorer(
        'https://hager.com/fr/catalogue/gamme', delai=0,
        dormir=lambda d: None, au_fil=vus.append)

    assert len(vus) == len(candidats) == 2
    assert sorted(c['reference'] for c in vus) == ['NFN216', 'NRN425']


def test_le_rappel_precede_la_fin_du_parcours(faux_reseau):
    """Mesure du grain : le premier candidat est rendu AVANT le second.

    Si le rappel n'était appelé qu'une fois la boucle terminée, les deux
    arriveraient ensemble et une interruption au milieu perdrait tout.
    """
    from apps.btp.catalogue_crawl import explorer

    ordre = []

    def au_fil(candidat):
        ordre.append(('candidat', candidat['reference']))

    def journal(url, genre, detail):
        ordre.append((genre, url.rsplit('/', 1)[-1]))

    explorer('https://hager.com/fr/catalogue/gamme', delai=0,
             dormir=lambda d: None, journal=journal, au_fil=au_fil)

    genres = [g for g, _ in ordre]
    # Un candidat est rendu entre deux pages, pas après toutes.
    premier = genres.index('candidat')
    assert 'produit' in genres[premier:], (
        'le rappel doit être appelé pendant le parcours, pas après')
    assert genres.count('candidat') == 2


def test_le_rappel_est_appele_aussi_par_le_sitemap(faux_sitemap):
    from apps.btp.catalogue_crawl import explorer_sitemap

    vus = []
    explorer_sitemap('https://hager.com/fr/catalogue/produits/nrn425-x',
                     delai=0, dormir=lambda d: None, au_fil=vus.append)
    assert len(vus) == 2


def test_le_rappel_est_appele_aussi_par_la_liste(monkeypatch):
    from apps.btp import catalogue_crawl
    from apps.btp.catalogue_crawl import explorer_liste

    monkeypatch.setattr(
        catalogue_crawl, 'telecharger_url',
        lambda url, session=None: HTML_HAGER.encode('utf-8'))

    vus = []
    explorer_liste(['https://hager.com/fr/catalogue/produits/a'], delai=0,
                   dormir=lambda d: None, au_fil=vus.append)
    assert len(vus) == 1


def test_les_trois_parcours_acceptent_le_rappel():
    """Un parcours ajouté sans `au_fil` reperdrait tout en silence."""
    import inspect

    from apps.btp.catalogue_crawl import (
        explorer, explorer_liste, explorer_sitemap,
    )

    for fonction in (explorer, explorer_liste, explorer_sitemap):
        parametres = inspect.signature(fonction).parameters
        assert 'au_fil' in parametres, fonction.__name__
