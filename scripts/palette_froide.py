"""Bascule la palette de l'interface ERP du chaud vers le froid.

POURQUOI UN SCRIPT, ET PAS UNE FEUILLE DE SURCHARGE

La barre laterale bleue a pu etre posee dans une feuille a part, chargee en
dernier : elle ne redefinissait que des JETONS (`--orion-menu-bg`,
`--orion-primary`). Ici, c'est impossible. 1218 couleurs chaudes sont
ecrites en hexadecimal DIRECTEMENT dans les regles, reparties sur
214 fichiers. Les surcharger une par une demanderait de recopier chaque
regle -- c'est-a-dire de reecrire les feuilles, mais en double.

La conversion est donc faite a la source. Elle s'annule par un
`git revert` du commit, pas par la suppression d'une ligne.

CE QUI EST CONVERTI, ET CE QUI NE L'EST PAS

Converti : l'identite Orion -- sable, brun, or, gris chauds. C'est le
decor : on le REGARDE.

Preserve : tout ce qui encode un etat -- les gammes rouge, ambre, orange,
jaune de Tailwind et de Bootstrap. Ca se LIT. Un ambre d'alerte devenu
cyan ne previent plus de rien.

Preserve aussi : les teintes uniques des palettes categorielles. Dans
`templates/hr/planning/_palette.html`, « maladie » est code en or
(#F7E7C6 / #845213) et « conge » en bleu (#D6E7F1 / #27566A). Rabattre
l'or vers le cyan rendrait les deux categories quasi indistinguables sur
le planning. Ces teintes n'apparaissent QUE la, et ne figurent donc pas
dans la table.

C'est pourquoi la table est une LISTE BLANCHE et non une liste
d'exclusions : ce que je n'ai pas explicitement decide reste tel quel. Le
risque devient « une teinte chaude oubliee » -- visible, cosmetique,
corrigible -- et non « un statut qui a perdu son sens ».

COMMENT LES COULEURS CIBLES SONT CALCULEES

A luminance relative WCAG CONSTANTE. Pour chaque couleur on cherche la
clarte qui, sur la teinte froide visee, redonne exactement la meme
luminance qu'avant. C'est la propriete de securite du lot : aucun rapport
de contraste ne peut se degrader, donc aucun des 527 ecrans ne peut
devenir illisible. Changer la teinte sans cela aurait suffi a faire
disparaitre du texte -- le vert pese 0.72 dans la luminance, le bleu
0.07 : un or et un azur de meme clarte HSL n'ont pas du tout la meme
luminance.

Usage :
    python scripts/palette_froide.py            # rapport seul
    python scripts/palette_froide.py --ecrire   # applique
"""
from __future__ import annotations

import argparse
import colorsys
import re
import sys
from pathlib import Path

# ════════════════════════════════════════════════════════════════════════
#  PERIMETRE
# ════════════════════════════════════════════════════════════════════════

RACINES = [
    Path("templates"),
    Path("static/css"),
    Path("static/js"),
    Path("apps"),
]

# Reprise de la frontiere deja posee par scripts/check_internal_theme_colors.py
# plutot qu'une neuvieme definition maison. Le depot y classe le portail
# client et les emails comme surfaces « publiques/hybrides » : ils ont leur
# propre identite et ne suivent pas le theme interne.
EXCLUS = [
    # Sites publics et vitrines -- identites distinctes
    "templates/store",
    "templates/public",
    "templates/siecle",
    "templates/lunea",
    "templates/websites/public",
    "templates/electricity",
    "templates/websites/website_preview.html",
    "static/css/sites",
    "static/js/sites",
    # Site vitrine d'Orion lui-meme : une page commerciale, pas l'ERP
    "templates/orion_website",
    # Previsualisations : le depot exclut deja websites/website_preview.html
    # au motif que « le fond blanc simule un vrai navigateur ». Ces deux-la
    # font la meme chose et meritent la meme exception.
    "templates/site_builder/preview.html",
    "templates/site_customization/preview.html",
    # Portail client et emails -- surfaces publiques/hybrides (cf. depot)
    "templates/client_portal",
    "templates/emails",
    "templates/errors",
    "templates/accounts/login.html",
    # Marques tierces
    "apps/lunea",
    "apps/siecle",
    "static/lunea",
    "static/siecle",
    "static/orion_website",
    "static/neostructura-site",
    "static/site_builder",
    # Deja froide : la feuille de la barre. Son seul hexa chaud est le
    # #3A2A1A cite dans un COMMENTAIRE, qui documente l'ancienne valeur.
    # Le convertir effacerait la trace de ce qu'on peut restaurer.
    "static/css/orion-barre-bleue.css",
    # Artefacts de compilation
    "/dist/",
    "node_modules",
]

EXTENSIONS = (".html", ".css", ".js")


def hors_perimetre(chemin: Path) -> bool:
    p = chemin.as_posix()
    return any(x.strip("/") in p for x in EXCLUS)


# ════════════════════════════════════════════════════════════════════════
#  LES TEINTES A CONVERTIR  (liste blanche)
# ════════════════════════════════════════════════════════════════════════
#
# Relevees par frequence sur les 214 fichiers de l'interface. Chaque
# famille porte son role, parce qu'un hexa seul ne dit pas ce qu'il fait.

BRUNS = [
    # Fonds sombres, texte principal, degrades d'entete
    "2B2118", "1A0E05", "1C120A", "3A2A1A", "241A12", "2B1808",
    "24180F", "2B1A0F", "2E2016", "1A110A", "1F1711", "4D3A26",
    "5A3E28", "1A1208", "2E2820", "2D1A08", "1A1207", "120B05",
    "1B1410", "5A3E2B", "0B0B0D", "2A221C",
    # Bruns PRESQUE NEUTRES. Un premier passage les avait manques : filtrer
    # sur « chroma >= 12 » les laissait dehors. Or #1F1B18 (chroma 7) porte
    # `--orion-text` et #14110F (chroma 5) porte `--orion-sidebar` : les
    # deux jetons les plus vus de l'ERP. Un brun presque neutre reste un
    # brun, et c'est en se posant a cote d'une ardoise qu'il se trahit.
    "1F1B18", "14110F", "1E1A17", "0F0A06", "14100C", "2E2924",
    "2B2620", "272019", "1F1A15", "1E1A15", "171310", "16130F",
]

ORS = [
    # L'accent de marque. #C6A15B a lui seul : 168 occurrences.
    "C6A15B", "8F7042", "D4A843", "D6B36A", "9D7A3F", "C9A24D",
    "B89B6B", "A8895A", "B88A44", "DEC07D", "D4AE62", "C9B896",
    "E8D8B0", "E8D49A", "C6A15C", "B88A45", "C8B89D",
]

SABLES = [
    # Fonds clairs, bordures, surfaces alternees
    "F8F3EA", "EBE0CC", "D8C9B0", "F6F1E6", "EFE7D5", "E3D5BD",
    "EFE2CD", "F7F2E7", "E3D5BE", "D1C4B3", "F0EBE3", "F2EDE4",
    "E4DED4", "ECE7DE", "C9C4BB", "E5D9CC", "EBE6DE", "F1ECE4",
    "E8DDD2", "F5EDD8", "FDF8F0", "FEF9EC", "E8E0D4", "EEE8DA",
    "EDE7DA", "E4DECE", "E8D9C0", "F7F4ED", "FBF7F0", "FBFAF7",
    "F6F3EE",
    # Blancs casses, chaleur a peine mesurable mais bien la
    "FBF8F2", "FFFDF8", "F1EFEA", "FAF9F7", "F8F5EF", "F6F4F0",
]

GRIS_CHAUDS = [
    # Texte secondaire, libelles, mentions
    "7A6A58", "A09A8A", "B9B2A3", "5F5750", "6F675C", "9C9284",
    "7D736A", "8C7C66", "8B8177", "9E8E7C", "8B7355", "7E786E",
]

TANS = [
    # Pastilles decoratives de widgets. Pas une gamme categorielle :
    # chacune vit seule dans sa carte, rien ne les compare entre elles.
    "C4936A", "C8956B", "FDF4EC", "E8B89A",
]

A_CONVERTIR = BRUNS + ORS + SABLES + GRIS_CHAUDS + TANS

# Ancres : les rares couleurs posees a la main plutot que calculees.
#
# IL Y EN AVAIT DEUX DE PLUS, ET ELLES CASSAIENT QUELQUE CHOSE.
#
# `E3D5BD -> DCE3EE` et `F8F3EA -> F2F5FA` eclaircissaient leur ton de 8 et
# de 1 pour cent. Mesure sur orion-design-system.css : une carte peinte en
# `--orion-sand-200` et bordee de `--orion-sand-300` passait d'un rapport
# de 1.12 a 1.01 entre les deux. La bordure DISPARAISSAIT -- et pas de
# facon visible a la relecture du diff, seulement a l'oeil, sur un ecran,
# en se demandant pourquoi les cartes n'ont plus de contour.
#
# Les deux ancres sont donc retirees, et la luminance decide partout sur
# les surfaces. Les valeurs reellement obtenues sont un peu plus sombres
# que celles annoncees -- c'est le prix pour que les 527 ecrans gardent
# exactement les ecarts qu'ils avaient.
#
# Les trois qui restent ameliorent le contraste au lieu de le degrader :
# chacune rend sa couleur plus SOMBRE, donc plus lisible sur blanc comme
# sous du texte blanc.
ANCRES = {
    "2B2118": "16243A",   # texte principal -> ardoise  (15.75 -> 15.58)
    "7A6A58": "5A6B82",   # texte secondaire            ( 5.21 ->  5.44)
    "C6A15B": "00A5C4",   # l'or de marque -> cyan      ( 2.43 ->  2.93)
}

# ════════════════════════════════════════════════════════════════════════
#  LES DEUX ECHELLES
# ════════════════════════════════════════════════════════════════════════
#
# Premiere tentative : rabattre le chroma d'origine vers une teinte froide.
# Resultat mesure : #EBE0CC -> #E0E1E2, #F6F1E6 -> #F1F1F2. Du GRIS. Les
# sables et les bruns ont un chroma faible ; le reduire encore ne laisse
# rien. L'ERP aurait ete gris, pas ardoise.
#
# Deux echelles publiees, donc, et chaque couleur se pose sur le barreau de
# meme luminance. Tous les neutres de l'ERP viennent alors d'UNE SEULE
# gamme : c'est ce qui fait qu'un ensemble se tient, plus que le choix de
# la teinte.
#
# Les six couleurs annoncees sont des barreaux de ces echelles :
# ardoise 50 / 200 / 600 / 900, azur 500.

ARDOISE = [
    "050A12", "0D1726", "16243A", "2C3850", "44526A", "5A6B82",
    "6E7F99", "97A6BC", "C3CEDD", "DCE3EE", "E8EDF5", "F2F5FA", "FFFFFF",
]

AZUR = [
    "041F28", "062C38", "0F4454", "0A5668", "006E86", "0089A6",
    "00A5C4", "2FAACE", "6FC5DF", "A8DCEC", "D3EDF6", "ECF7FB", "FFFFFF",
]


# ════════════════════════════════════════════════════════════════════════
#  COLORIMETRIE
# ════════════════════════════════════════════════════════════════════════

def vers_rgb(h: str) -> tuple[int, int, int]:
    h = h.lower()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _lineaire(canal: float) -> float:
    return canal / 12.92 if canal <= 0.03928 else ((canal + 0.055) / 1.055) ** 2.4


def luminance(rgb: tuple[int, int, int]) -> float:
    """Luminance relative WCAG. Le vert pese 0.72, le bleu 0.07."""
    r, g, b = (_lineaire(c / 255) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def est_accent(rgb: tuple[int, int, int]) -> bool:
    """Un or (teinte >= 34, chroma >= 45) va sur l'azur ; le reste, ardoise.

    La teinte compte autant que le chroma : #5A3E28 et #8F7042 ont des
    chromas voisins, mais le premier est un brun (teinte 26) et le second
    un or sombre (teinte 36). Les envoyer tous deux vers l'azur aurait
    donne des bruns turquoise.
    """
    r, g, b = rgb
    chroma = max(rgb) - min(rgb)
    teinte = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)[0] * 360
    return chroma >= 45 and teinte >= 34


def _vers_lineaire(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    return tuple(_lineaire(c / 255) for c in rgb)


def _depuis_lineaire(lin: tuple[float, float, float]) -> tuple[int, int, int]:
    def gamma(c: float) -> float:
        c = max(0.0, min(1.0, c))
        return c * 12.92 if c <= 0.00304 else 1.055 * (c ** (1 / 2.4)) - 0.055
    return tuple(round(gamma(c) * 255) for c in lin)


def _sur_echelle(echelle: list[str], cible_y: float) -> str:
    """Le point de l'echelle dont la luminance vaut exactement cible_y.

    L'interpolation se fait en LUMIERE LINEAIRE, et non sur les octets :
    la luminance y est une somme ponderee des composantes, donc lineaire.
    Choisir t = (Y - Y1) / (Y2 - Y1) rend alors la cible EXACTEMENT, sans
    recherche ni tolerance. Interpoler sur les valeurs sRGB aurait assombri
    le resultat -- c'est la meme erreur que de moyenner des octets pour
    fondre deux images.
    """
    lums = [luminance(vers_rgb(h)) for h in echelle]
    if cible_y <= lums[0]:
        return echelle[0]
    if cible_y >= lums[-1]:
        return echelle[-1]
    for i in range(len(echelle) - 1):
        y1, y2 = lums[i], lums[i + 1]
        if y1 <= cible_y <= y2:
            t = 0.0 if y2 == y1 else (cible_y - y1) / (y2 - y1)
            a = _vers_lineaire(vers_rgb(echelle[i]))
            b = _vers_lineaire(vers_rgb(echelle[i + 1]))
            melange = tuple(a[k] + t * (b[k] - a[k]) for k in range(3))
            return "%02X%02X%02X" % _depuis_lineaire(melange)
    return echelle[-1]


def convertir(hexa: str) -> str:
    """Rend l'equivalent froid, a luminance relative IDENTIQUE."""
    cle = hexa.upper()
    if cle in ANCRES:
        return ANCRES[cle]
    rgb = vers_rgb(hexa)
    echelle = AZUR if est_accent(rgb) else ARDOISE
    return _sur_echelle(echelle, luminance(rgb))


def contraste(a: str, b: str) -> float:
    ya, yb = luminance(vers_rgb(a)), luminance(vers_rgb(b))
    clair, sombre = max(ya, yb), min(ya, yb)
    return (clair + 0.05) / (sombre + 0.05)


# ════════════════════════════════════════════════════════════════════════
#  TABLE ET APPLICATION
# ════════════════════════════════════════════════════════════════════════

def table() -> dict[str, str]:
    return {h.upper(): convertir(h) for h in A_CONVERTIR}


def fichiers() -> list[Path]:
    trouves = []
    for racine in RACINES:
        if not racine.exists():
            continue
        for p in racine.rglob("*"):
            if p.is_file() and p.suffix in EXTENSIONS and not hors_perimetre(p):
                trouves.append(p)
    return sorted(trouves)


def appliquer(ecrire: bool) -> tuple[int, int, dict[str, int], dict[str, int]]:
    """Deux passes : l'hexadecimal, puis la notation rgb().

    La seconde n'est pas un raffinement. 190 couleurs de marque sont
    ecrites `rgba(198,161,91,.3)` -- l'or -- dans des OMBRES et des voiles
    translucides. Une table hexadecimale seule les aurait toutes laissees
    dorees : chaque relief de l'ERP serait reste chaud sous une interface
    froide, et le defaut ne se verrait qu'en lumiere rasante.
    """
    corr = table()
    # Le « # » fait partie du motif plutot que d'etre verifie apres coup :
    # un hexa precede de rien n'est pas une couleur, et un #RRGGBBAA voit
    # son alpha preserve puisqu'on ne touche que les six premiers chiffres.
    motif_hexa = re.compile(
        "#(" + "|".join(re.escape(h) for h in corr) + ")", re.IGNORECASE)
    par_composantes = {vers_rgb(h): c for h, c in corr.items()}
    motif_rgb = re.compile(
        r"(rgba?\(\s*)(\d{1,3})(\s*,\s*)(\d{1,3})(\s*,\s*)(\d{1,3})")

    touches = total = 0
    hexa_par_teinte: dict[str, int] = {}
    rgb_par_teinte: dict[str, int] = {}

    for p in fichiers():
        brut = p.read_text(encoding="utf-8", errors="surrogateescape")
        n = [0]

        def remplace_hexa(m):
            trouve = m.group(1)
            cible = corr[trouve.upper()]
            hexa_par_teinte[trouve.upper()] = hexa_par_teinte.get(trouve.upper(), 0) + 1
            n[0] += 1
            # La casse d'origine est respectee : un diff qui change aussi la
            # casse de 639 lignes se relit beaucoup moins bien.
            return "#" + (cible.lower() if trouve.islower() else cible)

        def remplace_rgb(m):
            avant, r, s1, g, s2, b = m.groups()
            composantes = (int(r), int(g), int(b))
            cible = par_composantes.get(composantes)
            if cible is None:
                return m.group(0)
            cle = "%02X%02X%02X" % composantes
            rgb_par_teinte[cle] = rgb_par_teinte.get(cle, 0) + 1
            n[0] += 1
            nr, ng, nb = vers_rgb(cible)
            # Les separateurs d'origine sont conserves : les feuilles
            # melangent « 198,161,91 » et « 198, 161, 91 ».
            return "%s%d%s%d%s%d" % (avant, nr, s1, ng, s2, nb)

        neuf = motif_rgb.sub(remplace_rgb, motif_hexa.sub(remplace_hexa, brut))
        if n[0]:
            touches += 1
            total += n[0]
            if ecrire:
                p.write_text(neuf, encoding="utf-8", errors="surrogateescape")

    return touches, total, hexa_par_teinte, rgb_par_teinte


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ecrire", action="store_true", help="applique la conversion")
    args = ap.parse_args()

    corr = table()
    print("TABLE DE CONVERSION  (%d teintes)" % len(corr))
    print()
    print("  avant     apres     luminance avant/apres   ecart contraste sur blanc")
    for famille, nom in ((BRUNS, "BRUNS"), (ORS, "ORS"),
                         (SABLES, "SABLES"), (GRIS_CHAUDS, "GRIS CHAUDS"),
                         (TANS, "TANS")):
        print("\n  -- %s --" % nom)
        for h in famille:
            a, b = h.upper(), corr[h.upper()]
            ca, cb = contraste(a, "FFFFFF"), contraste(b, "FFFFFF")
            print("  #%s -> #%s   %.4f / %.4f    %5.2f -> %5.2f  (%+.2f)"
                  % (a, b, luminance(vers_rgb(a)), luminance(vers_rgb(b)),
                     ca, cb, cb - ca))

    touches, total, en_hexa, en_rgb = appliquer(args.ecrire)
    print()
    print("PERIMETRE : %d fichiers examines" % len(fichiers()))
    print("  en hexadecimal : %d occurrences" % sum(en_hexa.values()))
    print("  en rgb()       : %d occurrences  (ombres et voiles)"
          % sum(en_rgb.values()))
    print("%s : %d occurrences dans %d fichiers"
          % ("APPLIQUE" if args.ecrire else "A CONVERTIR", total, touches))
    if not args.ecrire:
        print("\n(rapport seul -- relancer avec --ecrire pour appliquer)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
