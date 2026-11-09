# -*- coding: utf-8 -*-
"""Miniatures d'images, fabriquées une fois et gardées sur le disque.

POURQUOI DE VRAIES MINIATURES, ET NON UNE IMAGE RÉDUITE PAR LE NAVIGATEUR.

Mettre `style="width:150px"` sur la photo d'origine donne le même résultat à
l'écran et ne change rien au problème : le client télécharge quand même
quatre mégaoctets par photo. Sur un chantier de vingt photos, ouvrir la page
depuis un téléphone en 4G coûte quatre-vingts mégaoctets et une minute
d'attente. Une miniature de 480 pixels pèse une trentaine de kilooctets.

OÙ ELLES SONT RANGÉES, ET POURQUOI ÇA COMPTE.

Sous `MEDIA_ROOT/miniatures/`. Ce préfixe ne figure PAS dans les listes
d'`apps/core/media_access.py`, donc `/media/miniatures/...` rend 404 : une
miniature n'est jamais servie directement, toujours par une vue qui a
vérifié les droits. C'est délibéré — une miniature d'un document
confidentiel reste un document confidentiel, et une URL devinable
contournerait tout le contrôle de la vue qui la produit.

CE QUE CE MODULE REFUSE DE FAIRE.

Il ne traite que les extensions que Pillow lit sans greffon. Le HEIC des
iPhone en est exclu : Pillow ne l'ouvre pas sans `pillow-heif`, et tenter
puis échouer afficherait une vignette cassée — exactement le défaut que la
galerie du chantier vient de corriger. Mieux vaut annoncer d'avance qu'il
n'y aura pas d'aperçu que d'en promettre un qui ne viendra pas.

Il ne lève jamais non plus : une image illisible, un fichier tronqué, un
disque plein rendent None. Une miniature est un confort ; son échec ne doit
pas faire tomber la page qui liste les documents.
"""

import hashlib
import os
from pathlib import Path

from django.conf import settings

# Les extensions que Pillow lit de façon fiable sans greffon.
#
# Ni HEIC ni HEIF ni AVIF : voir l'en-tête. L'appelant doit tester
# `peut_etre_miniaturee()` AVANT d'émettre une balise <img>, pour ne jamais
# afficher une vignette cassée.
EXTENSIONS_MINIATURABLES = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')

LARGEUR_PAR_DEFAUT = 480
QUALITE = 80
DOSSIER = 'miniatures'

# Garde-fou contre une image « bombe » : un PNG de quelques kilooctets peut
# se décompresser en plusieurs gigaoctets de pixels et épuiser la mémoire du
# serveur. Pillow avertit au-delà d'un seuil ; on refuse franchement.
PIXELS_MAXIMUM = 80_000_000


def peut_etre_miniaturee(nom_de_fichier):
    """Vrai si une miniature de ce fichier est possible, sans l'ouvrir."""
    if not nom_de_fichier:
        return False
    extension = os.path.splitext(str(nom_de_fichier))[1].lower()
    return extension in EXTENSIONS_MINIATURABLES


def dossier_des_miniatures():
    return Path(settings.MEDIA_ROOT) / DOSSIER


def _empreinte(fichier, largeur):
    """Ce qui identifie une miniature : la source et la largeur demandée.

    La TAILLE du fichier entre dans l'empreinte. Django suffixe les
    homonymes, donc un nom ne devrait jamais être réutilisé pour un autre
    contenu — mais une restauration de sauvegarde ou un déplacement manuel
    peuvent le faire, et une miniature périmée servie à la place de la
    bonne photo serait pire qu'une miniature absente.
    """
    try:
        taille = fichier.size
    except Exception:                                   # noqa: BLE001
        taille = 0
    graine = '%s|%s|%s' % (fichier.name, taille, largeur)
    return hashlib.sha256(graine.encode('utf-8')).hexdigest()[:32]


def miniature(fichier, largeur=LARGEUR_PAR_DEFAUT):
    """Le chemin disque de la miniature, fabriquée si besoin. None si refus.

    `fichier` est un `FieldFile`. Le résultat est un chemin absolu vers un
    JPEG, ou None — l'appelant rend alors 404 plutôt que de servir une
    image cassée.
    """
    if fichier is None or not getattr(fichier, 'name', ''):
        return None
    if not peut_etre_miniaturee(fichier.name):
        return None

    cible = dossier_des_miniatures() / ('%s.jpg' % _empreinte(fichier, largeur))
    if cible.exists():
        return str(cible)

    return _fabriquer(fichier, cible, largeur)


def _fabriquer(fichier, cible, largeur):
    """Produit le JPEG. Rend son chemin, ou None sur le moindre obstacle."""
    try:
        from PIL import Image, ImageOps
    except ImportError:
        return None

    try:
        cible.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None

    try:
        with fichier.open('rb') as source:
            with Image.open(source) as image:
                if (image.width * image.height) > PIXELS_MAXIMUM:
                    return None

                # L'orientation EXIF, et ce n'est pas un détail sur un
                # chantier : une photo prise au téléphone en portrait est
                # stockée en paysage avec une étiquette de rotation. Sans
                # cette ligne, la moitié des miniatures seraient couchées.
                image = ImageOps.exif_transpose(image)

                # L'aplatissement sur fond blanc. Un PNG transparent
                # converti directement en RGB donne un fond NOIR, ce qui
                # rend méconnaissable un plan ou un logo sur fond clair.
                if image.mode in ('RGBA', 'LA', 'P'):
                    image = image.convert('RGBA')
                    fond = Image.new('RGBA', image.size, (255, 255, 255, 255))
                    image = Image.alpha_composite(fond, image)

                image = image.convert('RGB')
                image.thumbnail((largeur, largeur), Image.LANCZOS)
                image.save(str(cible), 'JPEG', quality=QUALITE, optimize=True)
    except Exception:                                   # noqa: BLE001
        # Image tronquée, format menteur, disque plein, droits manquants.
        # Une miniature est un confort : son échec ne fait pas tomber la
        # page qui liste les documents.
        try:
            if cible.exists():
                cible.unlink()
        except OSError:
            pass
        return None

    return str(cible)
