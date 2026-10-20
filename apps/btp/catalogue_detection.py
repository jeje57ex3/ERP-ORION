"""Détecter des matériaux et fournitures dans un PDF ou sur une page web.

**Le détecteur PROPOSE, l'exploitant VALIDE.** Rien n'entre au catalogue
sans avoir été coché. C'est ce qui rend l'exercice raisonnable : une
extraction qui se trompe se voit immédiatement dans le tableau d'aperçu, et
on ne coche rien. À l'inverse, une synchronisation automatique depuis des
pages web installerait des erreurs que personne ne surveille — c'est la
distinction qui compte, pas la technique employée.

**Les prix relevés sont des REPÈRES.** Ils sont marqués
`prix_indicatif=True` : un tarif public n'est pas le tarif négocié, et sans
cette marque rien ne distinguerait plus, six mois après, un prix confirmé
d'un prix recopié d'une page web.

**Côté web, on lit les données STRUCTURÉES, pas la mise en page.** JSON-LD
`@type: Product`, microdonnées schema.org, puis OpenGraph : trois formats
que les fabricants publient délibérément pour les moteurs de recherche.
Elles sont stables, normalisées, et ne bougent pas quand le site est
refondu — contrairement à des sélecteurs CSS, qui cassent à la première
refonte sans rien signaler.

**La limite qu'aucune bibliothèque ne lèvera ici :** beaucoup de sites
affichent prix et disponibilité APRÈS le chargement, par un appel que fait
le navigateur. On récupère alors la coquille HTML sans le contenu. Le
détecteur ne fait pas semblant : il dit qu'il n'a rien trouvé ET pourquoi,
au lieu de rendre une liste vide sans explication.

Aucune dépendance ajoutée : `pypdf` est déjà là, `html.parser` est dans la
bibliothèque standard. Sur une appliance, une dépendance de plus est une
installation de plus à réussir à chaque mise à jour.
"""

import json
import re
from html.parser import HTMLParser

from .catalogue_import import CatalogueError, _nombre, _texte

CANDIDATS_MAX = 500
"""Au-delà, ce n'est plus un aperçu qu'on relit mais une liste qu'on
accepte en aveugle — exactement ce que cet écran cherche à éviter."""

LONGUEUR_NOM_MIN = 4

MOTS_D_ENTETE = {
    'reference', 'référence', 'ref', 'designation', 'désignation',
    'libelle', 'libellé', 'prix', 'unite', 'unité', 'total', 'quantite',
    'quantité', 'tarif', 'page', 'code', 'article',
}
"""Les lignes qui ne sont que des en-têtes de tableau répétés en haut de
chaque page d'un PDF. Les importer créerait un article « Référence
Désignation Prix »."""


class Candidat(dict):
    """Un article possible. Un dict, pour voyager tel quel vers le gabarit."""

    @classmethod
    def creer(cls, nom, reference='', unite='', prix=None, origine=''):
        return cls(
            nom=_texte(nom)[:300],
            reference=_texte(reference)[:30],
            unite=_texte(unite)[:20],
            prix=str(prix) if prix is not None else '',
            origine=_texte(origine)[:200],
        )


def _plausible(candidat):
    """Vrai si ce candidat ressemble à un article, et non à du décor.

    Les trois refus correspondent à ce qu'un PDF de tarif produit en
    quantité : des en-têtes de colonnes répétés, des numéros de page, et
    des fragments trop courts pour désigner quoi que ce soit.
    """
    nom = candidat.get('nom') or ''
    if len(nom) < LONGUEUR_NOM_MIN:
        return False
    mots = {m.strip('.:;()').lower() for m in nom.split()}
    if mots and mots <= MOTS_D_ENTETE:
        return False
    if not re.search(r'[A-Za-zÀ-ÿ]{3}', nom):
        return False
    return True


def _dedoublonner(candidats):
    """Un même article peut sortir de deux formats de la même page.

    La clé est la référence si elle existe, sinon le nom : deux formats
    décrivent le même produit, pas deux produits.
    """
    vus = {}
    for candidat in candidats:
        cle = (candidat.get('reference') or '').lower() or \
            (candidat.get('nom') or '').lower()
        if cle in vus:
            # On garde celui qui porte un prix : c'est l'information rare.
            if not vus[cle].get('prix') and candidat.get('prix'):
                vus[cle] = candidat
            continue
        vus[cle] = candidat
    return list(vus.values())[:CANDIDATS_MAX]


# ─── Le PDF ──────────────────────────────────────────────────────────────────

MOTIF_REFERENCE = re.compile(r'^([A-Z0-9][A-Z0-9][A-Z0-9\-./_]{1,20})\s+')
"""Une référence en début de ligne : au moins trois caractères, commençant
par deux alphanumériques majuscules. Volontairement étroit — un motif large
prendrait le premier mot de chaque phrase pour une référence."""

MOTIF_PRIX = re.compile(
    r'(\d[\d  .,]*\d|\d)\s*(?:€|EUR|HT)?\s*$', re.IGNORECASE)
"""Un nombre en FIN de ligne. Dans un tarif, le prix est la dernière
colonne ; chercher n'importe où prendrait un diamètre ou une longueur
(« Tube 32 mm ») pour un prix."""

UNITES_CONNUES = {
    'u', 'un', 'pce', 'pc', 'ml', 'm', 'm2', 'm²', 'm3', 'm³', 'kg', 't',
    'l', 'sac', 'boite', 'boîte', 'lot', 'rouleau', 'paquet', 'h', 'jour',
}


def detecter_dans_pdf(octets):
    """Les articles trouvés dans un PDF de tarif, et le compte-rendu.

    Rend (candidats, message). Le message explique un résultat vide, car
    « rien trouvé » sans raison n'aide personne : un PDF scanné, un PDF
    sans texte extractible et un PDF dont les lignes ne ressemblent pas à
    un tarif ne se corrigent pas de la même façon.
    """
    try:
        from pypdf import PdfReader
    except ImportError:
        raise CatalogueError('Lecture des PDF indisponible sur ce serveur.')

    import io as _io

    try:
        lecteur = PdfReader(_io.BytesIO(octets))
        pages = lecteur.pages
    except Exception as exc:
        raise CatalogueError(f'PDF illisible : {exc}')

    texte_total = []
    for page in pages:
        try:
            texte_total.append(page.extract_text() or '')
        except Exception:
            # Une page illisible ne doit pas perdre les autres.
            continue

    texte = '\n'.join(texte_total)
    if not texte.strip():
        return [], (
            'Ce PDF ne contient aucun texte extractible. C’est le cas des '
            'documents scannés : ils ne portent qu’une image de la page. '
            'Demandez au fournisseur le même tarif en CSV ou en Excel.')

    candidats = []
    for ligne in texte.splitlines():
        candidat = _candidat_de_la_ligne(ligne)
        if candidat is not None and _plausible(candidat):
            candidats.append(candidat)

    candidats = _dedoublonner(candidats)
    if not candidats:
        return [], (
            f'Texte lu sur {len(pages)} page(s), mais aucune ligne ne '
            'ressemble à un article de tarif. Le détecteur cherche une '
            'désignation suivie d’un prix en fin de ligne. Si la mise en '
            'page est en colonnes séparées, le CSV ou l’Excel du '
            'fournisseur donnera un bien meilleur résultat.')

    return candidats, (
        f'{len(candidats)} article(s) détecté(s) sur {len(pages)} page(s).')


def _candidat_de_la_ligne(ligne):
    """Un article à partir d'une ligne de texte, ou None."""
    ligne = (ligne or '').strip()
    if len(ligne) < LONGUEUR_NOM_MIN:
        return None

    correspondance_prix = MOTIF_PRIX.search(ligne)
    if not correspondance_prix:
        # Sans prix, la ligne n'apporte pas ce qu'on vient chercher. On
        # prefere ne rien proposer qu'un article a tarifer a la main.
        return None

    prix = _nombre(correspondance_prix.group(1))
    if prix is None or prix <= 0:
        return None

    reste = ligne[:correspondance_prix.start()].strip(' .…-\t')
    if not reste:
        return None

    reference = ''
    correspondance_ref = MOTIF_REFERENCE.match(reste)
    if correspondance_ref:
        reference = correspondance_ref.group(1)
        reste = reste[correspondance_ref.end():].strip()

    unite = ''
    mots = reste.split()
    if mots and mots[-1].lower().strip('.') in UNITES_CONNUES:
        unite = mots[-1].strip('.')
        reste = ' '.join(mots[:-1]).strip()

    if not reste:
        return None

    return Candidat.creer(nom=reste, reference=reference, unite=unite,
                          prix=prix, origine=ligne)


# ─── La page web ─────────────────────────────────────────────────────────────

class _Extracteur(HTMLParser):
    """Récolte les données structurées d'une page : JSON-LD, microdonnées, OG.

    HTMLParser de la bibliothèque standard, et non un analyseur de DOM :
    on ne cherche pas à comprendre la mise en page, seulement à relever
    trois formats déclaratifs. Pour cela, un analyseur événementiel suffit
    et n'ajoute aucune dépendance.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocs_jsonld = []
        self.metas = {}
        self.microdonnees = []
        self._dans_jsonld = False
        self._tampon = []

    def handle_starttag(self, balise, attributs):
        attrs = {cle.lower(): (valeur or '') for cle, valeur in attributs}

        if balise == 'script' and \
                'ld+json' in attrs.get('type', '').lower():
            self._dans_jsonld = True
            self._tampon = []
            return

        if balise == 'meta':
            nom = (attrs.get('property') or attrs.get('name') or '').lower()
            if nom:
                self.metas[nom] = attrs.get('content', '')

        # Microdonnees : la valeur est tantot dans content=, tantot dans le
        # texte de la balise. On releve ce qui est portatif ici.
        prop = attrs.get('itemprop', '').lower()
        if prop and attrs.get('content'):
            self.microdonnees.append((prop, attrs['content']))

    def handle_endtag(self, balise):
        if balise == 'script' and self._dans_jsonld:
            self._dans_jsonld = False
            self.blocs_jsonld.append(''.join(self._tampon))
            self._tampon = []

    def handle_data(self, donnees):
        if self._dans_jsonld:
            self._tampon.append(donnees)


def _produits_du_jsonld(blocs):
    """Les produits déclarés en JSON-LD.

    Les pages imbriquent de plusieurs façons : un Product seul, un @graph,
    une liste, un ItemList de produits. On parcourt récursivement plutôt
    que de deviner la forme.
    """
    trouves = []

    def parcourir(noeud):
        if isinstance(noeud, list):
            for element in noeud:
                parcourir(element)
            return
        if not isinstance(noeud, dict):
            return

        types = noeud.get('@type') or ''
        types = types if isinstance(types, list) else [types]
        if any(str(t).lower() == 'product' for t in types):
            trouves.append(noeud)

        for valeur in noeud.values():
            if isinstance(valeur, (dict, list)):
                parcourir(valeur)

    for bloc in blocs:
        try:
            parcourir(json.loads(bloc))
        except ValueError:
            # Un bloc JSON-LD casse ne doit pas perdre les autres.
            continue
    return trouves


def _prix_de_l_offre(produit):
    """Le prix d'un produit JSON-LD, où qu'il soit rangé."""
    offres = produit.get('offers') or produit.get('offer') or {}
    if isinstance(offres, list):
        offres = offres[0] if offres else {}
    if not isinstance(offres, dict):
        return None

    for cle in ('price', 'lowPrice', 'highPrice'):
        if offres.get(cle) not in (None, ''):
            return _nombre(offres[cle])

    spec = offres.get('priceSpecification') or {}
    if isinstance(spec, list):
        spec = spec[0] if spec else {}
    if isinstance(spec, dict) and spec.get('price') not in (None, ''):
        return _nombre(spec['price'])
    return None


def detecter_dans_page(html):
    """Les articles trouvés sur une page web, et le compte-rendu.

    Trois formats essayés dans l'ordre de fiabilité décroissante. Le
    message dit lequel a servi : savoir que la page ne publie que de
    l'OpenGraph explique pourquoi un seul article sort d'une page de
    catégorie.
    """
    extracteur = _Extracteur()
    try:
        extracteur.feed(html or '')
        extracteur.close()
    except Exception as exc:
        raise CatalogueError(f'Page illisible : {exc}')

    candidats = []
    formats = []

    # 1. JSON-LD : le plus fiable, et celui que publient les fabricants.
    produits = _produits_du_jsonld(extracteur.blocs_jsonld)
    for produit in produits:
        nom = _texte(produit.get('name'))
        if not nom:
            continue
        candidats.append(Candidat.creer(
            nom=nom,
            reference=_texte(produit.get('sku') or produit.get('mpn')
                             or produit.get('productID')),
            prix=_prix_de_l_offre(produit),
            origine='JSON-LD',
        ))
    if produits:
        formats.append(f'JSON-LD ({len(produits)})')

    # 2. Microdonnees schema.org.
    if not candidats:
        valeurs = dict(extracteur.microdonnees)
        nom = _texte(valeurs.get('name'))
        if nom:
            candidats.append(Candidat.creer(
                nom=nom, reference=_texte(valeurs.get('sku')),
                prix=_nombre(valeurs.get('price')), origine='microdonnées'))
            formats.append('microdonnées')

    # 3. OpenGraph : le moins precis, un seul article par page.
    if not candidats:
        metas = extracteur.metas
        nom = _texte(metas.get('og:title') or metas.get('title'))
        prix = _nombre(metas.get('product:price:amount')
                       or metas.get('og:price:amount'))
        if nom:
            candidats.append(Candidat.creer(
                nom=nom, prix=prix, origine='OpenGraph'))
            formats.append('OpenGraph')

    candidats = [c for c in candidats if _plausible(c)]
    candidats = _dedoublonner(candidats)

    if not candidats:
        return [], (
            'Aucune donnée structurée de produit sur cette page. La cause '
            'la plus fréquente : le site affiche ses prix APRÈS le '
            'chargement, par un appel que fait le navigateur — la page '
            'reçue ne contient alors que la mise en page, sans les '
            'produits. Le détecteur ne peut pas exécuter ce code. '
            'Essayez la fiche d’UN produit plutôt qu’une page de '
            'catégorie, ou le tarif PDF du fournisseur.')

    rendu = f'{len(candidats)} article(s) détecté(s)'
    if formats:
        rendu += f' — source : {", ".join(formats)}'
    sans_prix = sum(1 for c in candidats if not c.get('prix'))
    if sans_prix:
        rendu += f', dont {sans_prix} sans prix'
    return candidats, rendu + '.'


def detecter_depuis_url(url, session=None):
    """Télécharge une page et y détecte les articles.

    Réutilise le contrôle d'adresse de l'import de catalogue : la même
    règle s'applique, l'adresse vient de l'utilisateur et c'est le serveur
    qui la récupère.
    """
    from .catalogue_import import telecharger_url

    octets = telecharger_url(url, session=session)
    for encodage in ('utf-8', 'cp1252', 'latin-1'):
        try:
            return detecter_dans_page(octets.decode(encodage))
        except UnicodeDecodeError:
            continue
    raise CatalogueError('Encodage de la page non reconnu.')
