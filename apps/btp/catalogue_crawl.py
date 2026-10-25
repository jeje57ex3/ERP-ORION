"""
apps/btp/catalogue_crawl.py — Explorer le catalogue public d'un fabricant

Parcourt les pages de liste d'une gamme, visite chaque fiche produit, et en
tire des candidats à valider. Complète `catalogue_detection`, qui ne traite
qu'une page à la fois.

**Ce que les quatre sites donnent réellement.** Mesuré sur leurs pages,
HTML brut en main, et non supposé :

- **Hager** publie du JSON-LD `Product` + `Offer` : `name` (NRN425), `sku`
  (NRN4257), `price` (428.27), `priceCurrency`. Lecture exacte, sans
  heuristique. Son prix est **HT recommandé**.
- **Legrand** n'a pas de JSON-LD produit mais des microdonnées
  `schema.org/Product`, la référence dans le texte (CG0001) et l'EAN. Son
  prix est un **conseillé TTC**, prix de détail public.
- **Soprema** marque ses pages `og:type=product`, mais **ne publie aucun
  prix** : le seul montant du HTML est `0,00`, sur deux pages de deux
  domaines différents. On en tire la désignation et le code, pas de prix.
- **Schneider** ne sert pas ses fiches produit en HTML : l'URL d'une
  référence renvoie la page générique « tous les produits », et il n'y a
  aucune donnée produit côté serveur. Cette voie est **inopérante** pour
  se.com, et aucune expression régulière n'y changera rien.

**Le prix va dans `prix_indicatif`, jamais dans `purchase_price`.** C'est
le point le plus important de ce module. `purchase_price` est le prix HT
auquel l'entreprise achète, remise professionnelle comprise. Un prix de
détail public — TTC chez Legrand, HT recommandé chez Hager — n'est ni l'un
ni l'autre. L'y écrire fausserait toutes les marges calculées dessus, et
l'erreur ne se verrait qu'en lisant un devis parti chez un client. Une
case vide se complète ; un chiffre faux se facture.

**Le parcours est borné et temporisé.** Une limite de pages, un délai entre
requêtes, et un état repris d'une exécution à l'autre : un catalogue
complet représente des milliers de requêtes, et les envoyer en rafale
ferait tomber l'exploration sur un blocage — en plus de charger le serveur
du fabricant sans égard.
"""

import json
import re
import time
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import urljoin, urlparse

from apps.core.nombres import nombre_francais

from .catalogue_import import CatalogueError, telecharger_url

# Délai entre deux requêtes. Une seconde est un compromis : assez pour ne
# pas marteler, assez court pour qu'une gamme de 255 produits passe en une
# dizaine de minutes.
DELAI_PAR_DEFAUT = 1.0

# Taux de TVA servant a ramener un prix public TTC en HT. 20 % est le taux
# normal francais et le defaut du champ vat_rate de Material : les deux
# doivent concorder, sinon un article importe afficherait un prix HT
# incoherent avec son propre taux.
TAUX_TVA_DEFAUT = Decimal('20')

# Garde-fou de volume. Sans borne, une erreur de motif de lien ferait
# tourner l'exploration sur les pages de mentions légales jusqu'à
# épuisement.
PAGES_MAX_PAR_DEFAUT = 200
PRODUITS_MAX_PAR_DEFAUT = 2000


class ExplorationError(CatalogueError):
    """Le parcours ne peut pas commencer, ou le site n'est pas gérable."""


# ─── JSON-LD ──────────────────────────────────────────────────────────────────

MOTIF_JSONLD = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE)


def blocs_jsonld(html):
    """Les blocs JSON-LD lisibles de la page.

    Un bloc illisible est ignoré sans bruit : les sites en servent
    plusieurs, et l'un mal formé ne doit pas faire perdre les autres.
    """
    blocs = []
    for corps in MOTIF_JSONLD.findall(html):
        try:
            blocs.append(json.loads(corps.strip()))
        except Exception:
            continue
    return blocs


def _parcourir(noeud):
    """Tous les dictionnaires imbriqués, à plat.

    Un JSON-LD met souvent le Product sous @graph, sous un tableau, ou
    sous les deux. Chercher au premier niveau manquerait la moitié des
    pages.
    """
    if isinstance(noeud, dict):
        yield noeud
        for valeur in noeud.values():
            yield from _parcourir(valeur)
    elif isinstance(noeud, list):
        for element in noeud:
            yield from _parcourir(element)


def produit_jsonld(html):
    """Le premier objet de @type Product, à plat. None s'il n'y en a pas."""
    for bloc in blocs_jsonld(html):
        for noeud in _parcourir(bloc):
            types = noeud.get('@type')
            types = types if isinstance(types, list) else [types]
            if 'Product' in types:
                return noeud
    return None


def _prix_de(produit):
    """Le prix d'une offre, quelle que soit la forme du bloc."""
    for noeud in _parcourir(produit):
        for cle in ('price', 'lowPrice'):
            if cle in noeud and not isinstance(noeud[cle], (dict, list)):
                valeur = nombre_francais(noeud[cle])
                if valeur is not None and valeur > 0:
                    return valeur
    return None


# ─── OpenGraph et microdonnées, en repli ─────────────────────────────────────

MOTIF_OG = re.compile(
    r'<meta[^>]+(?:property|name)=["\']og:([a-z:]+)["\'][^>]*content='
    r'["\']([^"\']*)["\']', re.IGNORECASE)


def opengraph(html):
    return {cle.lower(): valeur for cle, valeur in MOTIF_OG.findall(html)}


def _detexte(valeur):
    """Décode les entités HTML et resserre les espaces.

    Les titres OpenGraph de Soprema arrivent entièrement encodés
    (`&#x20;` pour une espace) : sans décodage, la désignation serait
    illisible.
    """
    import html as _html

    if not valeur:
        return ''
    return re.sub(r'\s+', ' ', _html.unescape(valeur)).strip()


# ─── Extracteurs par site ─────────────────────────────────────────────────────

MOTIF_EAN = re.compile(r'(?<!\d)(\d{13})(?!\d)')
MOTIF_REF_LEGRAND = re.compile(r'\b([A-Z]{2}\d{4})\b')
MOTIF_REF_HAGER = re.compile(r'\b([A-Z]{2,4}\d{3,4})\b')
MOTIF_PRIX_TEXTE = re.compile(r'(\d{1,3}(?:[  ]\d{3})*,\d{2})\s*(?:€|&euro;)')


def _ean_plausible(html):
    """Un EAN apparaissant plusieurs fois, et pas un horodatage.

    Mesure faite sur se.com : des nombres à 13 chiffres y abondent, qui
    sont des horodatages JavaScript en millisecondes. Un EAN de produit,
    lui, est répété dans la page (fiche, données structurées, lien
    distributeur) et commence par un préfixe pays — jamais par 17.
    """
    from collections import Counter

    comptes = Counter(MOTIF_EAN.findall(html))
    for valeur, compte in comptes.most_common():
        if compte >= 2 and not valeur.startswith(('17', '00')):
            return valeur
    return ''


def extraire_hager(html, url):
    """Hager : JSON-LD Product complet. Rien à deviner.

    `name` porte la référence commerciale (NRN425) ; `sku` porte une
    variante à chiffre supplémentaire (NRN4257) qui n'est pas celle
    qu'un bon de commande emploie. On retient donc `name` comme
    référence, et la désignation vient du titre OpenGraph, plus parlant
    que le `name` réduit au code.
    """
    produit = produit_jsonld(html)
    if produit is None:
        return None

    og = opengraph(html)
    reference = _detexte(str(produit.get('name') or ''))[:30]
    titre = _detexte(og.get('title') or '')
    # « Disjoncteur 4P 25kA C-25A 4M • NRN425 | Hager » -> on retire la
    # queue de marque, qui n'apporte rien et mange la place.
    designation = re.split(r'\s*[|•]\s*', titre)[0].strip() or reference

    return {
        'reference': reference,
        'nom': designation[:200],
        'prix': _prix_de(produit),
        'prix_ht': True,
        'ean': _detexte(str(produit.get('gtin13') or '')) or _ean_plausible(html),
        'url': url,
        'origine': 'JSON-LD Product',
    }


def extraire_legrand(html, url):
    """Legrand : microdonnées et texte. Pas de JSON-LD produit.

    Le prix est un CONSEILLÉ TTC, prix de détail public — d'où
    `prix_ht=False`, qui empêche l'import de le confondre avec un prix
    d'achat.
    """
    og = opengraph(html)
    titre = _detexte(og.get('title') or '')
    designation = re.sub(r'\s*-\s*$', '', titre).strip()
    if not designation:
        return None

    # La référence vient de `itemprop="sku"`, en microdonnées :
    #   <span itemprop="sku" content="0 905 01">
    # C'est la reference OFFICIELLE, au format Legrand a dix chiffres
    # espaces, qu'on normalise en retirant les espaces.
    #
    # DEFAUT MESURE, et le pire des trois. Je cherchais d'abord « LG-xxxx »
    # dans l'og:image -- ce qui ne marche que pour les produits Celiane --
    # puis je retombais sur un motif « deux lettres et quatre chiffres »
    # cherche dans TOUTE la page. Or une fiche affiche des produits
    # VOISINS : la boite Batibox 090501 repartait avec la reference CG0001,
    # celle d'un interrupteur Celiane. Constate sur l'export : deux
    # articles differents sous la meme reference.
    #
    # Il n'y a plus de repli approximatif. Une reference absente est
    # honnete et le rapprochement se fait alors sur la designation ; une
    # reference FAUSSE fait collisionner deux produits distincts.
    reference = ''
    correspondance = re.search(
        r'itemprop=["\']sku["\'][^>]*content=["\']([^"\']+)["\']', html)
    if correspondance is None:
        correspondance = re.search(
            r'content=["\']([^"\']+)["\'][^>]*itemprop=["\']sku["\']', html)
    if correspondance:
        reference = re.sub(r'\s+', '', correspondance.group(1))

    if not reference:
        # Repli : le nom de l'image de LA fiche, qui porte son propre code
        # — « th_090501-LEGRAND.jpg » ou « th_LG-CG0001.jpg ». On ne lit
        # que l'og:image, jamais le corps de la page.
        image = og.get('image') or ''
        for motif in (r'LG-([A-Z0-9]{4,10})', r'th_(\d{6,10})-'):
            trouve = re.search(motif, image)
            if trouve:
                reference = trouve.group(1)
                break

    # Le prix est en MICRODONNEES, pas dans le texte :
    #   <span class="c-product-price__value" itemprop="price" content="14.67">
    # Mesure faite sur la fiche CG0001. Mon premier motif exigeait un « € »
    # juste apres le montant ; or le symbole est dans un <small> separe, et
    # l'extraction ne trouvait donc AUCUN prix sur les 1 704 fiches.
    # L'attribut content est en plus exact et deja normalise.
    prix = None
    correspondance = re.search(
        r'itemprop=["\']price["\'][^>]*content=["\']([\d.,]+)["\']', html)
    if correspondance is None:
        correspondance = re.search(
            r'content=["\']([\d.,]+)["\'][^>]*itemprop=["\']price["\']', html)
    if correspondance:
        prix = nombre_francais(correspondance.group(1))
    if prix is None:
        prix_textes = MOTIF_PRIX_TEXTE.findall(html)
        if prix_textes:
            prix = nombre_francais(prix_textes[0])

    return {
        'reference': reference[:30],
        'nom': designation[:200],
        'prix': prix,
        'prix_ht': False,          # conseillé TTC
        'ean': _ean_plausible(html),
        'url': url,
        'origine': 'microdonnées + texte',
    }


def extraire_soprema(html, url):
    """Soprema : désignation et code, AUCUN prix.

    Mesuré sur deux pages de deux domaines : le seul montant du HTML est
    « 0,00 ». Soprema ne publie pas ses prix. Inventer un prix, ou
    reprendre ce zéro, serait pire que de n'en mettre aucun — zéro est un
    prix, et un devis le facturerait.
    """
    og = opengraph(html)
    designation = _detexte(og.get('title') or '')
    if not designation:
        return None

    # Code article Soprema : huit chiffres A ZEROS DE TETE, parfois suivi
    # d'un suffixe (00105879, 00119750 VER).
    #
    # Les zeros de tete sont EXIGES, et ce n'est pas cosmetique : sans eux
    # le motif mordait sur « 16777619 », un identifiant interne de la page,
    # et rendait une reference introuvable au catalogue. Mesure faite sur
    # la fiche « Membrane d'Etancheite Ardoisee », dont le vrai code est
    # 00105879.
    correspondance = re.search(r'\b(00\d{6})(?:\s+([A-Z]{2,4}))?\b', html)
    reference = ''
    if correspondance:
        reference = correspondance.group(1)
        if correspondance.group(2):
            reference += ' ' + correspondance.group(2)

    return {
        'reference': reference[:30],
        'nom': designation[:200],
        'prix': None,              # Soprema n'en publie aucun
        'prix_ht': None,
        'ean': '',
        'url': url,
        'origine': 'OpenGraph (sans prix)',
    }


def _produit_par_url(motif):
    """Classement sur la forme de l'URL. Suffisant quand elle discrimine."""
    def decider(url, _candidat):
        return bool(motif.match(urlparse(url).path))
    return decider


def _produit_legrand(url, candidat):
    """Chez Legrand, seule l'EXTRACTION distingue une fiche d'une gamme.

    Les deux ont la même forme d'URL — deux segments sous /catalogue/ :
    « /catalogue/interrupteurs-et-prises/celiane » est une gamme,
    « /catalogue/interrupteur/interrupteur-ou-va-et-vient-... » une fiche.

    Mesure faite : la page de gamme était prise pour un produit, aucun lien
    n'était suivi, et le « produit » extrait était le titre de la catégorie
    avec une référence ramassée au hasard. Une fiche porte une référence
    ET un prix ; une gamme porte un titre et aucun prix. C'est donc la
    présence des deux qui tranche.
    """
    if not SITES['legrand.fr']['produit'].match(urlparse(url).path):
        return False
    return bool(candidat and candidat.get('reference')
                and candidat.get('prix') is not None)


# Motif des liens de fiche produit, par site. Sans lui, l'exploration
# suivrait les mentions légales et les articles de blog.
SITES = {
    'legrand.fr': {
        'nom': 'Legrand',
        'extracteur': extraire_legrand,
        'produit': re.compile(r'^/catalogue/[^/]+/[^/]+$'),
        'liste': re.compile(r'^/catalogue/'),
        'est_produit': _produit_legrand,
        'sitemap': 'https://www.legrand.fr/sitemap.xml',
        # Mesure : 1 749 URL en /catalogue/<x>/<y>, dont une poignee de
        # rubriques dont <x> est un pluriel de rayon. On les ecarte.
        'exclure_sitemap': re.compile(
            r'^/catalogue/(?:[a-z-]+s-et-[a-z-]+|gammes)/'),
    },
    'hager.com': {
        'nom': 'Hager',
        'extracteur': extraire_hager,
        'produit': re.compile(r'^/fr/catalogue/produits/[^/]+$'),
        'liste': re.compile(r'^/fr/catalogue/'),
        # L'URL discrimine : /produits/<slug> n'est jamais une liste.
        'est_produit': None,
        'sitemap': 'https://hager.com/fr/catalogue/deep/sitemap_fr.xml',
    },
    'soprema.fr': {
        'nom': 'Soprema',
        'extracteur': extraire_soprema,
        'produit': re.compile(r'^/(?:produits|produits-et-systemes)/[^/]+'),
        'liste': re.compile(r'^/(?:produits|produits-et-systemes|fr)/'),
        'est_produit': None,
    },
}

# Les sites dont l'URL suffit reçoivent leur classifieur ici, et non dans
# le dictionnaire ci-dessus : il aurait fallu que le motif soit défini
# avant d'être refermé dessus.
for _configuration in SITES.values():
    if _configuration['est_produit'] is None:
        _configuration['est_produit'] = _produit_par_url(
            _configuration['produit'])

# Sites dont la voie publique est inopérante, avec la raison. Les refuser
# en nommant la cause vaut mieux qu'une exploration qui tourne une heure
# pour ne rien rapporter.
SITES_IMPOSSIBLES = {
    'se.com': (
        'Schneider Electric ne sert pas ses fiches produit en HTML : '
        'l\'adresse d\'une référence renvoie la page générique « tous les '
        'produits », et les données produit sont construites par le '
        'navigateur. Mesuré sur se.com/fr/fr/product/A9F74210/. Passez par '
        'le tarif Excel de votre portail distributeur et le dépôt de '
        'fichier.'),
    'schneider-electric.fr': (
        'Voir se.com : les fiches produit Schneider ne sont pas '
        'exploitables depuis le HTML public.'),
}


def site_de(url):
    """La configuration du site, ou une erreur qui nomme la raison."""
    hote = (urlparse(url).hostname or '').lower()
    for interdit, raison in SITES_IMPOSSIBLES.items():
        if hote == interdit or hote.endswith('.' + interdit):
            raise ExplorationError(raison)
    for domaine, configuration in SITES.items():
        if hote == domaine or hote.endswith('.' + domaine):
            return configuration
    raise ExplorationError(
        f'Site non géré : {hote or url}. Sites connus : '
        f'{", ".join(sorted(SITES))}.')


# ─── Les sitemaps : la bonne voie ────────────────────────────────────────────
#
# MESURE QUI A CHANGE LA CONCEPTION. Ramper dans la navigation ne marche
# pas : chaque page porte le menu complet du site, et un parcours parti de
# la gamme Celiane se retrouvait au bout de quatorze pages dans les
# tableaux electriques, sans avoir vu une seule fiche produit.
#
# Les sitemaps enumerent directement ce qu'on cherche :
#   Legrand  sitemap.xml -> 38 968 URL, dont 1 749 fiches /catalogue/<x>/<y>
#   Hager    sitemap-index.xml -> 65 sous-plans, dont le catalogue francais
#
# C'est aussi beaucoup plus respectueux du serveur du fabricant : on visite
# ce qu'il a lui-meme declare vouloir voir visite, et rien d'autre.

MOTIF_LOC = re.compile(r'<loc>\s*([^<\s]+)\s*</loc>', re.IGNORECASE)
MOTIF_INDEX = re.compile(r'<sitemapindex', re.IGNORECASE)


def urls_du_sitemap(url, limite=60000, profondeur=2, dormir=time.sleep,
                    delai=0.5):
    """Les URL d'un sitemap, en suivant les index. Rend une liste.

    `profondeur` borne la recursion : un index qui se referencerait
    lui-meme ferait tourner la lecture sans fin.
    """
    try:
        octets = telecharger_url(url)
    except CatalogueError:
        return []

    xml = octets.decode('utf-8', errors='replace')
    liens = MOTIF_LOC.findall(xml)

    if MOTIF_INDEX.search(xml) and profondeur > 0:
        sortie = []
        for sous_plan in liens:
            if len(sortie) >= limite:
                break
            if delai:
                dormir(delai)
            sortie.extend(urls_du_sitemap(
                sous_plan, limite=limite - len(sortie),
                profondeur=profondeur - 1, dormir=dormir, delai=delai))
        return sortie

    return liens[:limite]


def fiches_du_sitemap(configuration, dormir=time.sleep, delai=0.5,
                      limite=60000):
    """Les URL de FICHES PRODUIT declarees par le sitemap du site.

    Le filtre est celui du site : sans lui, on recupererait les 38 968 URL
    de Legrand -- articles de blog, questions frequentes, pages pro --
    pour 1 749 fiches reellement utiles.
    """
    plan = configuration.get('sitemap')
    if not plan:
        return []
    toutes = urls_du_sitemap(plan, limite=limite, dormir=dormir, delai=delai)
    motif = configuration['produit']
    exclus = configuration.get('exclure_sitemap')
    gardees = []
    for lien in toutes:
        chemin = urlparse(lien).path
        if not motif.match(chemin):
            continue
        if exclus and exclus.search(chemin):
            continue
        gardees.append(lien)
    return gardees


def explorer_sitemap(depart, pages_max=PAGES_MAX_PAR_DEFAUT,
                     produits_max=PRODUITS_MAX_PAR_DEFAUT,
                     delai=DELAI_PAR_DEFAUT, deja_vues=(), journal=None,
                     dormir=time.sleep, au_fil=None):
    """Parcourt les fiches declarees par le sitemap du site de `depart`.

    Rend (candidats, visitees, message), comme `explorer`, pour que la
    commande n'ait pas a distinguer les deux modes dans son compte-rendu.
    """
    configuration = site_de(depart)
    if not configuration.get('sitemap'):
        raise ExplorationError(
            f'{configuration["nom"]} ne declare pas de sitemap exploitable : '
            f'utilisez le parcours par liens.')

    fiches = fiches_du_sitemap(configuration, dormir=dormir, delai=delai)
    if not fiches:
        raise ExplorationError(
            f'Le sitemap de {configuration["nom"]} ne donne aucune fiche '
            f'produit. Son format a peut-etre change.')

    vues = set(deja_vues)
    a_voir = [lien for lien in fiches if lien not in vues]
    if journal:
        journal(configuration['sitemap'], 'liste',
                f'{len(fiches)} fiche(s) declaree(s), {len(a_voir)} a voir')

    candidats = []
    pages = 0
    extracteur = configuration['extracteur']

    for url in a_voir:
        if pages >= pages_max or len(candidats) >= produits_max:
            break
        if delai and pages:
            dormir(delai)
        try:
            octets = telecharger_url(url)
        except CatalogueError as exc:
            vues.add(url)
            if journal:
                journal(url, 'echec', str(exc))
            continue

        pages += 1
        vues.add(url)
        candidat = extracteur(octets.decode('utf-8', errors='replace'), url)
        if candidat and candidat.get('nom'):
            candidats.append(candidat)
            # Ecrit IMMEDIATEMENT par l'appelant. Un parcours de 1 700
            # fiches dure une vingtaine de minutes : assez pour etre
            # interrompu, et tout perdre si le resultat n'etait rendu qu'a
            # la fin. Constate -- 1 519 pages parcourues, zero ligne
            # ecrite, meme pas l'etat de reprise.
            if au_fil:
                au_fil(candidat)
            if journal:
                journal(url, 'produit', candidat['nom'])
        elif journal:
            journal(url, 'echec', 'aucune donnee exploitable sur cette fiche')

    restantes = len(fiches) - len(vues & set(fiches))
    message = (f'{configuration["nom"]} (sitemap) : {pages} fiche(s) lue(s), '
               f'{len(candidats)} produit(s) trouve(s)')
    if restantes > 0:
        message += f', {restantes} fiche(s) restantes — relancez pour continuer'
    return candidats, vues, message + '.'


def explorer_liste(urls, pages_max=PAGES_MAX_PAR_DEFAUT,
                   produits_max=PRODUITS_MAX_PAR_DEFAUT,
                   delai=DELAI_PAR_DEFAUT, deja_vues=(), journal=None,
                   dormir=time.sleep, au_fil=None):
    """Visite une liste d'adresses fournie, sans rien decouvrir.

    Seule voie pour Soprema. Mesure faite : leur page /produits ne porte
    QU'UN lien produit -- la liste est construite par le navigateur -- et
    /sitemap.xml renvoie une image PNG, sur les deux domaines. Il n'y a
    donc rien a enumerer automatiquement, alors que les fiches
    individuelles, elles, se lisent tres bien.

    Le site de chaque adresse est determine separement : une liste peut
    melanger des fabricants.

    Rend (candidats, visitees, message), comme les autres parcours.
    """
    vues = set(deja_vues)
    candidats = []
    pages = 0
    refuses = []

    for url in urls:
        if pages >= pages_max or len(candidats) >= produits_max:
            break
        url = (url or '').strip()
        if not url or url.startswith('#') or url in vues:
            continue

        try:
            configuration = site_de(url)
        except ExplorationError as exc:
            refuses.append(str(exc)[:80])
            vues.add(url)
            if journal:
                journal(url, 'echec', str(exc))
            continue

        if delai and pages:
            dormir(delai)
        try:
            octets = telecharger_url(url)
        except CatalogueError as exc:
            vues.add(url)
            if journal:
                journal(url, 'echec', str(exc))
            continue

        pages += 1
        vues.add(url)
        candidat = configuration['extracteur'](
            octets.decode('utf-8', errors='replace'), url)
        if candidat and candidat.get('nom'):
            candidats.append(candidat)
            # Ecrit IMMEDIATEMENT par l'appelant. Un parcours de 1 700
            # fiches dure une vingtaine de minutes : assez pour etre
            # interrompu, et tout perdre si le resultat n'etait rendu qu'a
            # la fin. Constate -- 1 519 pages parcourues, zero ligne
            # ecrite, meme pas l'etat de reprise.
            if au_fil:
                au_fil(candidat)
            if journal:
                journal(url, 'produit', candidat['nom'])
        elif journal:
            journal(url, 'echec', 'aucune donnee exploitable')

    message = (f'Liste fournie : {pages} adresse(s) lue(s), '
               f'{len(candidats)} produit(s) trouve(s)')
    if refuses:
        message += f', {len(refuses)} adresse(s) refusee(s)'
    return candidats, vues, message + '.'


# ─── Le parcours ──────────────────────────────────────────────────────────────

MOTIF_LIEN = re.compile(r'<a[^>]+href=["\']([^"\'#]+)', re.IGNORECASE)


def liens_de(html, base, motif):
    """Les liens de la page qui vérifient le motif, dédoublonnés, absolus.

    On reste sur l'hôte de départ : un lien sortant vers un distributeur
    emmènerait l'exploration sur un site dont rien n'est su.
    """
    hote_base = (urlparse(base).hostname or '').lower()
    vus, sortie = set(), []
    for brut in MOTIF_LIEN.findall(html):
        absolu = urljoin(base, brut)
        morceaux = urlparse(absolu)
        if morceaux.scheme not in ('http', 'https'):
            continue
        if (morceaux.hostname or '').lower() != hote_base:
            continue
        if not motif.match(morceaux.path):
            continue
        propre = f'{morceaux.scheme}://{morceaux.netloc}{morceaux.path}'
        if propre not in vus:
            vus.add(propre)
            sortie.append(propre)
    return sortie


def explorer(depart, pages_max=PAGES_MAX_PAR_DEFAUT,
             produits_max=PRODUITS_MAX_PAR_DEFAUT, delai=DELAI_PAR_DEFAUT,
             deja_vues=(), journal=None, dormir=time.sleep, au_fil=None):
    """Parcourt à partir de `depart` et rend (candidats, visitees, message).

    `deja_vues` permet de REPRENDRE : un catalogue complet se parcourt en
    plusieurs exécutions, et recommencer à zéro chaque fois rendrait la
    chose interminable.

    `journal` est appelé à chaque page, pour que la commande puisse rendre
    compte en direct d'un parcours qui dure une heure.

    `dormir` est injecté pour que les tests ne patientent pas réellement :
    une suite qui attend une seconde par page ne serait jamais lancée.
    """
    configuration = site_de(depart)
    extracteur = configuration['extracteur']

    a_voir = [depart]
    visitees = set(deja_vues)
    candidats = []
    pages = 0
    premiere = True

    while a_voir and pages < pages_max and len(candidats) < produits_max:
        url = a_voir.pop(0)
        if url in visitees:
            continue
        visitees.add(url)

        # Le délai AVANT la requête, sauf la première : sinon la dernière
        # page du parcours ferait attendre pour rien.
        if not premiere and delai:
            dormir(delai)
        premiere = False

        try:
            octets = telecharger_url(url)
        except CatalogueError as exc:
            if journal:
                journal(url, 'echec', str(exc))
            continue

        pages += 1
        html = octets.decode('utf-8', errors='replace')

        # Le classement produit / liste ne peut pas reposer sur la seule
        # forme de l'URL : voir _produit_legrand. On extrait d'abord, le
        # site tranche ensuite — l'extraction elle-même est parfois le
        # seul indice disponible.
        candidat = extracteur(html, url)
        est_produit = configuration['est_produit'](url, candidat)
        if not est_produit:
            candidat = None

        if candidat and candidat.get('nom'):
            candidats.append(candidat)
            # Ecrit IMMEDIATEMENT par l'appelant. Un parcours de 1 700
            # fiches dure une vingtaine de minutes : assez pour etre
            # interrompu, et tout perdre si le resultat n'etait rendu qu'a
            # la fin. Constate -- 1 519 pages parcourues, zero ligne
            # ecrite, meme pas l'etat de reprise.
            if au_fil:
                au_fil(candidat)
            if journal:
                journal(url, 'produit', candidat['nom'])
        elif journal:
            journal(url, 'liste', f'{len(a_voir)} en attente')

        # On ne suit les liens que depuis les pages de LISTE : une fiche
        # produit renvoie vers des dizaines de produits voisins, et suivre
        # tout ferait déborder le parcours hors de la gamme demandée.
        if not est_produit:
            for lien in liens_de(html, url, configuration['liste']):
                if lien not in visitees and lien not in a_voir:
                    a_voir.append(lien)

    message = (
        f'{configuration["nom"]} : {pages} page(s) visitée(s), '
        f'{len(candidats)} produit(s) trouvé(s)')
    if a_voir:
        message += (f', {len(a_voir)} page(s) restantes — relancez pour '
                    f'continuer')
    return candidats, visitees, message + '.'


# ─── Import des candidats ─────────────────────────────────────────────────────

def _en_ht(prix, prix_ht, taux=TAUX_TVA_DEFAUT):
    """Ramène un prix à du HT, puisque le champ est du HT.

    `purchase_price` est libellé « Prix d'achat HT » : y poser un prix TTC
    le gonflerait de vingt pour cent, et le coût de chantier calculé dessus
    serait faux d'autant. Legrand publie du conseillé TTC, Hager du HT
    recommandé — la distinction n'est donc pas théorique.

    Rend None si le prix est absent : zéro n'est pas une absence de prix,
    c'est un prix, et un devis le facturerait.
    """
    if prix is None:
        return None
    if prix_ht:
        return prix
    # Mode d'arrondi EXPLICITE. Le defaut de Decimal est ROUND_HALF_EVEN,
    # l'arrondi au pair le plus proche : 12,225 y devient 12,22 alors que
    # l'usage commercial francais donne 12,23. Laisser ce choix implicite
    # sur de l'argent, c'est le laisser au hasard du contexte decimal.
    return (prix / (Decimal('1') + Decimal(taux) / Decimal('100'))).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)


def importer_candidats(company, candidats, supplier=None, nature='material',
                       a_blanc=True):
    """Crée ou met à jour les articles depuis les candidats trouvés.

    **Le prix va dans `purchase_price`, avec `prix_indicatif` coché.**
    C'est le mécanisme que porte déjà le modèle : « Prix de repère relevé
    sur un site ou un PDF public, en attendant le tarif négocié. Décochez
    quand le prix est confirmé. » Un prix de repère visible et marqué vaut
    mieux qu'un champ vide — à condition que la marque existe, et elle
    existe.

    **Les prix TTC sont ramenés en HT**, parce que le champ est du HT.
    Legrand publie du conseillé TTC ; l'y verser tel quel gonflerait le
    coût de chantier de vingt pour cent.

    **Un article déjà présent ne voit jamais son prix écrasé s'il est
    confirmé.** Seuls les articles encore marqués « indicatif » sont
    réactualisés : un catalogue public ne doit pas pouvoir effacer un tarif
    négocié saisi à la main.

    Rend un dictionnaire de compteurs.
    """
    from .models import Material

    compteurs = {'crees': 0, 'mis_a_jour': 0, 'inchanges': 0, 'ignores': 0,
                 'proteges': 0}

    for candidat in candidats:
        nom = (candidat.get('nom') or '').strip()
        if not nom:
            compteurs['ignores'] += 1
            continue

        reference = (candidat.get('reference') or '').strip()
        prix = _en_ht(candidat.get('prix'), candidat.get('prix_ht'))

        existant = None
        if reference:
            existant = Material.objects.filter(
                company=company, reference=reference).first()
        if existant is None:
            existant = Material.objects.filter(company=company,
                                               name=nom).first()

        origine = f'Relevé sur {candidat.get("url", "")}'
        if candidat.get('prix') is not None and not candidat.get('prix_ht'):
            origine += (f' — prix public {candidat["prix"]} TTC ramené en HT '
                        f'à {TAUX_TVA_DEFAUT} %')

        if existant is None:
            if not a_blanc:
                Material.objects.create(
                    company=company, name=nom[:200], reference=reference[:30],
                    kind=nature,
                    purchase_price=prix if prix is not None else Decimal('0'),
                    # Coché seulement s'il y a un prix : sans prix, il n'y a
                    # rien a confirmer, et la case cochee ferait croire a un
                    # chiffre a verifier.
                    prix_indicatif=prix is not None,
                    supplier=supplier,
                    description=origine[:500])
            compteurs['crees'] += 1
            continue

        # Un prix confirmé à la main est intouchable.
        if prix is not None and not existant.prix_indicatif                 and existant.purchase_price:
            compteurs['proteges'] += 1
            continue

        champs = []
        if prix is not None and existant.purchase_price != prix:
            existant.purchase_price = prix
            existant.prix_indicatif = True
            champs += ['purchase_price', 'prix_indicatif']
        if not existant.reference and reference:
            existant.reference = reference[:30]
            champs.append('reference')

        if champs:
            if not a_blanc:
                existant.save(update_fields=champs)
            compteurs['mis_a_jour'] += 1
        else:
            compteurs['inchanges'] += 1

    return compteurs
