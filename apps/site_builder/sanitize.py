"""Assainissement des réglages de sections de l'éditeur visuel.

Pourquoi un module à part : les réglages d'une section sont un `JSONField`
libre, remplis par l'éditeur et **relus par deux consommateurs très
différents** — le moteur de rendu Django (`renderer.py`) et le frontend
Next.js, qui reçoit le dictionnaire brut par l'API publique. Une règle
écrite dans un seul des deux laisserait l'autre ouvert.

Les trois défauts que ce module ferme, mesurés et non supposés :

**`html.escape` ne protège pas une URL.** Il échappe `& < > " '` ; il ne
connaît pas les schémas. `_esc('javascript:alert(1)')` rend la chaîne
**intacte**, et le moteur l'écrivait dans quatre `href`. Un compte ayant
accès à l'éditeur y déposait du JavaScript qui s'exécutait chez chaque
visiteur du site public — et le même réglage partait vers Next.js par
l'API publique.

**`html.escape` ne protège pas du CSS.** L'image de fond était écrite dans
`background-image:url('…')`, à l'intérieur d'un attribut `style`.
L'échappement transforme `'` en `&#x27;`, que l'analyseur HTML **redécode
en apostrophe** avant que le moteur CSS ne lise la déclaration : la valeur
sort du `url()`. On ne peut pas fermer l'attribut (`"` reste échappé),
mais on injecte des déclarations CSS, dont un `url()` vers un serveur
tiers qui relève l'adresse IP de chaque visiteur.

**`int()` sur un réglage libre lève.** `int('abc')` lève `ValueError`, et
cinq appels du moteur lisaient directement un réglage. Comme le réglage
est *enregistré*, la page d'édition, l'aperçu et le rendu public
renvoyaient 500 **durablement** : il fallait corriger en base.

Les valeurs refusées ne font pas échouer l'enregistrement. Un éditeur de
pages doit pardonner une faute de frappe : on retombe sur le défaut du
module, ce qui est visible à l'écran et corrigeable d'un clic.
"""

import re

# Schémas acceptés pour un lien. `data:` en est absent à dessein :
# `data:text/html,<script>…` dans un href est du script.
SCHEMAS_DE_LIEN = ('http', 'https', 'mailto', 'tel')

# Pour un média, `data:` est légitime (vignette en base64) mais seulement
# en image : `data:text/html` n'a rien à faire dans un src.
SCHEMAS_DE_MEDIA = ('http', 'https')

# Caractères qui permettraient de sortir d'un `url(...)` ou d'une
# déclaration CSS. Une vraie adresse d'image n'en contient aucun.
CARACTERES_INTERDITS_EN_CSS = '\'"();{}\\<>'

# Couleurs : #abc, #aabbcc, #aabbccdd, un nom CSS, rgb()/rgba(), hsl().
MOTIF_COULEUR = re.compile(
    r'^#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$'
    r'|^[a-zA-Z]{3,24}$'
    r'|^(?:rgb|rgba|hsl|hsla)\([0-9\s.,%/-]{1,60}\)$'
)

# Longueurs CSS : « 70vh », « 480px », « 100% », « auto ». Même raison
# que les couleurs — la valeur part dans un attribut `style`, où
# l'échappement HTML ne protège de rien.
MOTIF_LONGUEUR_CSS = re.compile(
    r'^(?:auto|0)$|^\d{1,5}(?:\.\d{1,3})?(?:px|%|vh|vw|rem|em|ch|vmin|vmax)$'
)

# Un texte de réglage n'a aucune raison de peser plus que ça. Sans borne,
# un seul POST stocke des mégaoctets que chaque rendu relit.
LONGUEUR_MAX_TEXTE = 20000

# Bornes des réglages numériques connus. Sans elles, `count: 100000`
# demande cent mille produits à chaque affichage de la page.
BORNES = {
    'count': (0, 48),
    'columns': (1, 6),
    'overlay_opacity': (0, 100),
    'height': (0, 600),
}


def _schema_de(valeur: str) -> str:
    """Le schéma d'une URL, lu comme un navigateur le lit.

    Les navigateurs ignorent les espaces et les caractères de contrôle à
    l'intérieur du schéma : « java\\tscript:alert(1) » s'exécute. Les
    retirer avant de comparer est la différence entre un contrôle réel et
    un contrôle qu'on contourne avec une tabulation.
    """
    avant = valeur.split(':', 1)[0]
    return ''.join(
        c for c in avant if not c.isspace() and ord(c) >= 0x20
    ).lower()


def _est_relative(valeur: str) -> bool:
    """Une adresse interne au site : /collections, #ancre, ?p=1, ./x.

    Sans schéma et sans `:` avant le premier `/`, il n'y a pas de schéma à
    contrôler. On teste l'absence de `:` AVANT le premier séparateur,
    sinon « collections:8000/x » passerait pour relative.
    """
    if valeur.startswith(('/', '#', '?', './', '../')):
        return True
    premier_separateur = len(valeur)
    for marque in ('/', '?', '#'):
        position = valeur.find(marque)
        if position != -1:
            premier_separateur = min(premier_separateur, position)
    return ':' not in valeur[:premier_separateur]


def url_de_lien(valeur, defaut: str = '') -> str:
    """Une URL utilisable dans un `href`.

    Rend `defaut` (vide par défaut) pour tout ce qui n'est pas un schéma
    accepté : c'est ici que `javascript:` tombe.
    """
    brut = str(valeur or '').strip()
    if not brut:
        return defaut
    if _est_relative(brut):
        return brut
    if _schema_de(brut) in SCHEMAS_DE_LIEN:
        return brut
    return defaut


def url_de_media(valeur, defaut: str = '') -> str:
    """Une URL utilisable dans un `src` d'image.

    Plus étroit que `url_de_lien` : ni `mailto:` ni `tel:` n'ont de sens
    pour une image, et une `data:` n'est acceptée qu'en image.
    """
    brut = str(valeur or '').strip()
    if not brut:
        return defaut
    if _est_relative(brut):
        return brut
    schema = _schema_de(brut)
    if schema in SCHEMAS_DE_MEDIA:
        return brut
    if schema == 'data' and brut[:30].lower().startswith('data:image/'):
        return brut
    return defaut


def url_dans_du_css(valeur, defaut: str = '') -> str:
    """Une URL utilisable à l'intérieur d'un `url(...)` CSS.

    Volontairement plus strict que `url_de_media` : on refuse tout
    caractère qui permettrait de sortir du `url()` ou de la déclaration,
    et aussi les espaces. Une vraie adresse d'image n'en contient aucun,
    et une URL légitime qui en contiendrait doit être encodée en
    pourcents de toute façon.
    """
    brut = url_de_media(valeur, '')
    if not brut:
        return defaut
    if any(c in brut for c in CARACTERES_INTERDITS_EN_CSS):
        return defaut
    if any(c.isspace() for c in brut):
        return defaut
    return brut


def couleur(valeur, defaut: str = '') -> str:
    """Une couleur CSS, ou le défaut.

    Même raison que `url_dans_du_css` : la valeur part dans un attribut
    `style`, où l'échappement HTML ne protège pas.
    """
    brut = str(valeur or '').strip()
    if not brut:
        return defaut
    return brut if MOTIF_COULEUR.match(brut) else defaut


def longueur_css(valeur, defaut: str = '') -> str:
    """Une longueur CSS (« 70vh », « 480px »), ou le défaut.

    `min_height` était écrit tel quel dans `min-height:…;` à l'intérieur
    d'un attribut `style` : le même défaut que les couleurs, par une
    troisième porte.
    """
    brut = str(valeur or '').strip()
    if not brut:
        return defaut
    return brut if MOTIF_LONGUEUR_CSS.match(brut) else defaut


def entier(valeur, defaut: int, cle: str = '') -> int:
    """Un entier borné, qui ne lève jamais.

    `int()` levait `ValueError` sur un réglage libre, et le réglage étant
    enregistré, le 500 était durable.

    Accepte « 8 », « 8.0 » et 8 : l'éditeur envoie du JSON, où un nombre
    saisi dans un champ texte arrive en chaîne.
    """
    try:
        nombre = int(float(str(valeur).strip()))
    except (TypeError, ValueError):
        return defaut
    mini, maxi = BORNES.get(cle, (None, None))
    if mini is not None:
        nombre = max(mini, nombre)
    if maxi is not None:
        nombre = min(maxi, nombre)
    return nombre


def texte(valeur, defaut: str = '') -> str:
    """Un texte borné en longueur.

    Pas d'échappement ici : l'échappement appartient au moment du rendu,
    qui seul sait s'il écrit dans du HTML, un attribut ou du JSON.
    Échapper au stockage produirait des « &amp;amp; » au deuxième
    enregistrement.
    """
    if valeur is None:
        return defaut
    if isinstance(valeur, (int, float, bool)):
        return str(valeur)
    if not isinstance(valeur, str):
        return defaut
    return valeur[:LONGUEUR_MAX_TEXTE]


def _classe_de_la_cle(cle: str, defaut_du_module):
    """Ce qu'une clé de réglage est censée contenir.

    Déduit de la clé et du défaut déclaré dans le registre, et non d'une
    liste écrite à la main : un module ajouté demain avec un
    « banner_url » sera protégé sans qu'on y pense.
    """
    bas = cle.lower()
    if isinstance(defaut_du_module, bool):
        return 'booleen'
    if isinstance(defaut_du_module, (int, float)):
        return 'entier'
    if bas.endswith('_color') or bas.endswith('_colour'):
        return 'couleur'
    if bas.endswith(('_height', '_width', '_size', '_radius', '_gap')):
        return 'longueur'
    if bas == 'image' or bas.endswith('_image') or bas.endswith('_img'):
        return 'media'
    if bas.endswith('_url') or bas == 'url' or bas.endswith('_href'):
        return 'lien'
    return 'texte'


def assainir_reglages(module_type: str, reglages) -> dict:
    """Les réglages d'une section, rendus sûrs pour ses deux lecteurs.

    Appliqué à l'ENREGISTREMENT, pour que l'API publique ne serve jamais
    un `javascript:` au frontend Next.js — qui ne passe pas par le moteur
    de rendu Django et ne bénéficierait d'aucune protection faite là-bas.

    Les clés inconnues du registre sont conservées, assainies d'après leur
    nom : l'éditeur envoie parfois des clés qu'un module plus récent
    utilise, et les jeter ferait perdre du travail de mise en page.
    """
    from .registry import BUILDER_MODULES

    if not isinstance(reglages, dict):
        return {}

    defauts = (BUILDER_MODULES.get(module_type, {}) or {}).get('defaults', {})
    propre = {}

    for cle, valeur in reglages.items():
        if not isinstance(cle, str) or len(cle) > 80:
            continue
        defaut = defauts.get(cle)
        classe = _classe_de_la_cle(cle, defaut)

        if classe == 'booleen':
            propre[cle] = bool(valeur)
        elif classe == 'entier':
            propre[cle] = entier(valeur, int(defaut or 0), cle)
        elif classe == 'couleur':
            propre[cle] = couleur(valeur, str(defaut or ''))
        elif classe == 'longueur':
            propre[cle] = longueur_css(valeur, str(defaut or ''))
        elif classe == 'media':
            propre[cle] = url_de_media(valeur, '')
        elif classe == 'lien':
            propre[cle] = url_de_lien(valeur, '')
        elif isinstance(valeur, (list, dict)):
            # Les modules « gallery » et « faq » portent des listes. On les
            # garde, en bornant leur taille : une liste de dix mille
            # entrees serait relue a chaque rendu.
            propre[cle] = _assainir_structure(valeur)
        else:
            propre[cle] = texte(valeur, str(defaut or ''))

    return propre


def _assainir_structure(valeur, profondeur: int = 0):
    """Listes et dictionnaires imbriqués, bornés en taille et en profondeur.

    La profondeur est bornée parce que le JSON vient du réseau : un
    imbriquement de dix mille niveaux suffit à faire tomber la
    sérialisation du rendu.
    """
    if profondeur > 4:
        return None
    if isinstance(valeur, list):
        return [_assainir_structure(v, profondeur + 1) for v in valeur[:60]]
    if isinstance(valeur, dict):
        resultat = {}
        for cle, sous_valeur in list(valeur.items())[:60]:
            if not isinstance(cle, str) or len(cle) > 80:
                continue
            classe = _classe_de_la_cle(cle, None)
            if classe == 'couleur':
                resultat[cle] = couleur(sous_valeur, '')
            elif classe == 'media':
                resultat[cle] = url_de_media(sous_valeur, '')
            elif classe == 'lien':
                resultat[cle] = url_de_lien(sous_valeur, '')
            elif isinstance(sous_valeur, (list, dict)):
                resultat[cle] = _assainir_structure(sous_valeur,
                                                    profondeur + 1)
            elif isinstance(sous_valeur, bool):
                resultat[cle] = sous_valeur
            elif isinstance(sous_valeur, (int, float)):
                resultat[cle] = sous_valeur
            else:
                resultat[cle] = texte(sous_valeur, '')
        return resultat
    if isinstance(valeur, bool) or isinstance(valeur, (int, float)):
        return valeur
    return texte(valeur, '')
