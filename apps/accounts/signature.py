"""Signature tracée à l'écran : décodage et contrôle avant enregistrement.

La signature se dessine dans un cadre, au doigt ou à la souris, et le
navigateur en renvoie un PNG encodé en base64. Tout ce qui arrive ainsi est
une donnée de requête : rien n'est pris sur parole.

**Le contrôle qui compte est le refus d'une signature VIDE.** Une toile sur
laquelle rien n'a été tracé produit un PNG parfaitement valide, entièrement
transparent. Enregistré, il ferait dire à l'écran « signature enregistrée »
alors que les devis sortiraient sans rien à l'emplacement prévu — un défaut
qui ne se voit qu'à l'impression, chez le client. Le contrôle est donc
fait ICI, côté serveur, et non seulement dans le navigateur qu'on peut
contourner.

Le fond reste transparent, et c'est voulu : posée sur un modèle de devis,
une signature à fond blanc masquerait ce qui se trouve dessous.
"""

import base64
import io

PREFIXE = 'data:image/png;base64,'

OCTETS_MAX = 2 * 1024 * 1024
"""2 Mo. Un tracé de signature en PNG pèse quelques dizaines de kilooctets ;
au-delà, ce n'est pas une signature."""

LARGEUR_MAX = 2400
HAUTEUR_MAX = 1000
"""Bornes de l'image acceptée. La toile fait 900x300 ; ces bornes laissent
de la marge pour un écran à forte densité sans accepter une photographie."""

ENCRE_MINIMALE = 50
"""Nombre minimal de pixels encrés pour qu'un tracé compte comme signature.

Un point posé par accident sur la toile ne doit pas devenir une signature.
Un trait, même court, dépasse largement ce seuil sur une toile de 900x300.
"""

SEUIL_ALPHA = 16
"""En dessous, le pixel est considéré transparent : les bords d'un trait
lissé portent une opacité résiduelle qui ne doit pas compter comme encre."""


class SignatureInvalide(ValueError):
    """Ce qui a été envoyé ne peut pas servir de signature."""


def decoder_signature(donnees):
    """Les octets PNG d'une signature tracée, ou SignatureInvalide.

    Les vérifications sont faites dans cet ordre précis — du moins coûteux
    au plus coûteux — pour qu'une requête absurde soit écartée avant qu'on
    ne décode une image :

    1. le préfixe annoncé,
    2. la taille, avant de décoder le base64,
    3. le décodage base64,
    4. l'ouverture par Pillow, qui seule dit si c'est vraiment un PNG,
    5. les dimensions,
    6. la présence d'encre.
    """
    from PIL import Image, UnidentifiedImageError

    if not donnees or not isinstance(donnees, str):
        raise SignatureInvalide('Aucune signature reçue.')

    if not donnees.startswith(PREFIXE):
        # Le prefixe ne PROUVE rien -- Pillow s'en chargera -- mais il
        # ecarte tout de suite ce qui n'a meme pas la bonne forme.
        raise SignatureInvalide('Format de signature inattendu.')

    charge = donnees[len(PREFIXE):]
    # 4 caracteres de base64 pour 3 octets : on borne AVANT de decoder,
    # sinon une chaine de 100 Mo serait decodee avant d'etre refusee.
    if len(charge) > OCTETS_MAX * 4 // 3 + 4:
        raise SignatureInvalide('Signature trop volumineuse.')

    try:
        octets = base64.b64decode(charge, validate=True)
    except (ValueError, TypeError):
        raise SignatureInvalide('Signature illisible.')

    if not octets:
        raise SignatureInvalide('Signature vide.')
    if len(octets) > OCTETS_MAX:
        raise SignatureInvalide('Signature trop volumineuse.')

    try:
        image = Image.open(io.BytesIO(octets))
        image.load()
    except (UnidentifiedImageError, OSError, ValueError):
        raise SignatureInvalide('Ce n’est pas une image lisible.')

    if image.format != 'PNG':
        # Un JPEG renomme passerait le prefixe mais pas ceci. Et un JPEG
        # n'a pas de couche alpha : le fond serait blanc, donc masquant.
        raise SignatureInvalide('La signature doit être un PNG.')

    if image.width > LARGEUR_MAX or image.height > HAUTEUR_MAX:
        raise SignatureInvalide('Signature aux dimensions inattendues.')

    if not _contient_de_l_encre(image):
        raise SignatureInvalide(
            'Le cadre est vide : tracez votre signature avant '
            'd’enregistrer.')

    return octets


def _contient_de_l_encre(image):
    """Vrai si l'image porte un tracé, et pas seulement du vide.

    Sur la couche alpha, car le fond est transparent : mesurer la
    luminosité prendrait le vide pour du noir sur une image RGB sans alpha.
    """
    alpha = image.convert('RGBA').getchannel('A')
    if alpha.getbbox() is None:
        return False

    # getcolors rend des couples (nombre_de_pixels, valeur) -- dans cet
    # ordre, et non l'inverse. Une couche 8 bits compte au plus 256 valeurs
    # distinctes, donc maxcolors=256 ne rend jamais None ici.
    couleurs = alpha.getcolors(maxcolors=256)
    if couleurs is None:
        return True
    encres = sum(nombre for nombre, valeur in couleurs
                 if valeur > SEUIL_ALPHA)
    return encres >= ENCRE_MINIMALE
