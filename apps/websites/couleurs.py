"""apps/websites/couleurs.py — Choisir un texte lisible sur un fond donné.

POURQUOI CE MODULE EXISTE

Les sites vitrines laissent l'exploitant choisir la couleur de fond depuis
le thème. Tant que le fond était clair, le texte sombre du thème convenait.
Dès qu'on choisit un bleu profond, un vert sapin ou une ardoise, ce même
texte sombre devient illisible — et rien ne le signale, parce que personne
ne relit une page dont il vient seulement de changer une couleur.

Le texte n'est donc plus choisi, il est DÉDUIT du fond.

LA MÉTHODE, ET POURQUOI CELLE-LÀ

La luminance relative de la recommandation WCAG, et non la moyenne des
trois composantes. L'œil ne perçoit pas les canaux également : un vert pur
paraît bien plus clair qu'un bleu pur de même valeur. Une moyenne naïve
jugerait « #0000FF » aussi clair que « #00FF00 » et placerait du texte
sombre sur un bleu nuit.

Le seuil de 0,5 n'est pas arbitraire non plus : c'est le point où le
contraste avec du blanc et le contraste avec du noir s'équilibrent.
"""

NOIR = '#1C2A33'
BLANC = '#FFFFFF'


def _composantes(couleur):
    """Les trois canaux 0-255 d'une couleur « #RRGGBB » ou « #RGB ».

    Rend None si la chaîne n'est pas lisible : une couleur absente ou mal
    saisie ne doit pas faire tomber une page publique.
    """
    if not couleur:
        return None
    valeur = str(couleur).strip().lstrip('#')
    if len(valeur) == 3:
        valeur = ''.join(caractere * 2 for caractere in valeur)
    if len(valeur) != 6:
        return None
    try:
        return tuple(int(valeur[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def luminance(couleur):
    """Luminance relative WCAG, de 0 (noir) à 1 (blanc). None si illisible."""
    composantes = _composantes(couleur)
    if composantes is None:
        return None

    canaux = []
    for brut in composantes:
        proportion = brut / 255
        # La correction gamma de sRGB : l'échelle n'est pas linéaire, et
        # l'ignorer surestime les tons moyens.
        canaux.append(proportion / 12.92 if proportion <= 0.04045
                      else ((proportion + 0.055) / 1.055) ** 2.4)

    rouge, vert, bleu = canaux
    return 0.2126 * rouge + 0.7152 * vert + 0.0722 * bleu


def est_sombre(couleur):
    """Ce fond appelle-t-il un texte clair ?

    Une couleur illisible est traitée comme CLAIRE, donc on garde un texte
    sombre : c'est le cas d'un thème vide, et le fond par défaut des pages
    est clair.
    """
    valeur = luminance(couleur)
    return valeur is not None and valeur < 0.5


def texte_lisible_sur(fond, texte_souhaite=None):
    """La couleur de texte à employer sur ce fond.

    `texte_souhaite` — celui du thème — est RESPECTÉ quand il contraste
    suffisamment. On ne remplace le choix de l'exploitant que lorsqu'il
    rendrait la page illisible : corriger une couleur qui convient serait
    s'arroger une décision de dessin.
    """
    fond_sombre = est_sombre(fond)

    if texte_souhaite:
        ecart = contraste(fond, texte_souhaite)
        if ecart is not None and ecart >= 4.5:
            return texte_souhaite

    return BLANC if fond_sombre else NOIR


def contraste(premiere, seconde):
    """Le rapport de contraste WCAG entre deux couleurs, de 1 à 21.

    4,5 est le seuil du texte courant, 3 celui des grands titres. Rend None
    si l'une des deux n'est pas lisible.
    """
    a, b = luminance(premiere), luminance(seconde)
    if a is None or b is None:
        return None
    clair, sombre = max(a, b), min(a, b)
    return (clair + 0.05) / (sombre + 0.05)
