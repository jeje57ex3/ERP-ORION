"""
apps/websites/templatetags/website_extras.py

Utilitaires de template pour relier une entreprise (apps.core.models.Company)
à son site public actif, notamment depuis des templates hors du namespace
public_websites (ex: le wizard legacy templates/electricity/).
"""
from django import template
from django.urls import reverse

register = template.Library()

# Vue d'accueil publique à utiliser selon le type de site.
_HOME_URL_NAME_BY_SITE_TYPE = {
    'btp': 'public_websites:btp_home',
    'electricite': 'public_websites:electricite_home',
}


@register.simple_tag
def company_public_url(company):
    """
    Retourne l'URL de la page d'accueil publique active de `company`
    (site BTP, Électricité, ou générique selon le type de site configuré),
    ou '/' si l'entreprise n'a aucun site public actif.
    """
    if not company:
        return '/'
    try:
        from apps.websites.models import Website

        site = Website.objects.filter(company=company, is_active=True).first()
        if not site:
            return '/'
        url_name = _HOME_URL_NAME_BY_SITE_TYPE.get(site.site_type, 'public_websites:home')
        return reverse(url_name, args=[company.slug])
    except Exception:
        return '/'


# ─── Lisibilité du texte sur un fond choisi dans l'interface ────────────────
#
# LE DÉFAUT. `WebsiteSection` porte DEUX champs, `bg_color` et `text_color`.
# `templates/websites/public/page.html` applique les deux. La page d'accueil
# n'appliquait que le fond, dans ses dix sections, et jetait la couleur de
# texte. On choisissait un fond bleu nuit et un texte clair dans l'éditeur de
# site, et le texte retombait sur `--site-text` — `#111827`, presque noir.
# Bleu nuit sur presque noir : illisible, et rien ne le signalait, puisque
# l'éditeur montrait bien la couleur qu'on venait de choisir.
#
# POURQUOI UNE COULEUR DÉDUITE, ET PAS SEULEMENT LE CHAMP. Honorer
# `text_color` ne suffit pas : il est facultatif, et quelqu'un qui choisit
# un fond sans toucher au texte retomberait dans le même piège. La couleur
# est donc déduite du fond quand elle n'est pas donnée. L'exploitant garde
# le dernier mot — un `text_color` renseigné l'emporte toujours.

#: Les deux couleurs entre lesquelles on tranche. Le sombre n'est pas noir
#: pur : `#111827` est la couleur de texte par défaut des thèmes, et garder
#: la même évite qu'une section au fond clair se distingue du reste de la
#: page par une nuance de noir.
TEXTE_SUR_FOND_SOMBRE = '#FFFFFF'
TEXTE_SUR_FOND_CLAIR = '#111827'

#: Seuil de luminance relative. 0,45 et non 0,5 : l'œil lit mieux du blanc
#: sur un fond moyen que du noir, donc on bascule vers le blanc un peu
#: avant le milieu. Vérifié sur `#2563EB`, le bleu primaire par défaut, qui
#: doit recevoir du texte blanc.
SEUIL_DE_BASCULE = 0.45


def _composantes(couleur):
    """Les trois composantes 0–255 d'une couleur hexadécimale, ou None.

    Rend None pour tout ce qui n'est pas un hexadécimal lisible —
    `var(--site-primary)`, `linear-gradient(...)`, `rgba(...)`, un mot-clé
    CSS, une chaîne vide. `bg_color` est un champ texte libre de cinquante
    caractères : il contient ce que l'exploitant a tapé, et la fonction doit
    répondre « je ne sais pas » plutôt que de deviner.
    """
    valeur = (couleur or '').strip()
    if not valeur.startswith('#'):
        return None
    valeur = valeur[1:]
    if len(valeur) in (3, 4):
        valeur = ''.join(c * 2 for c in valeur[:3])
    elif len(valeur) in (6, 8):
        valeur = valeur[:6]
    else:
        return None
    try:
        return tuple(int(valeur[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def luminance_relative(couleur):
    """La luminance relative WCAG d'une couleur, de 0 (noir) à 1 (blanc).

    Rend None si la couleur n'est pas déchiffrable. La formule est celle de
    WCAG 2.1 : chaque composante est linéarisée avant d'être pondérée, le
    vert comptant pour près des trois quarts du ressenti. Une moyenne simple
    des composantes jugerait `#0000FF` aussi clair que `#008000`, qui est
    pourtant bien plus lumineux à l'œil.
    """
    composantes = _composantes(couleur)
    if composantes is None:
        return None
    canaux = []
    for brut in composantes:
        proportion = brut / 255
        if proportion <= 0.04045:
            canaux.append(proportion / 12.92)
        else:
            canaux.append(((proportion + 0.055) / 1.055) ** 2.4)
    rouge, vert, bleu = canaux
    return 0.2126 * rouge + 0.7152 * vert + 0.0722 * bleu


@register.filter
def couleur_lisible(fond):
    """La couleur de texte qui se lit sur `fond` : blanche ou presque noire.

    Rend une chaîne VIDE quand le fond n'est pas déchiffrable, pour que le
    gabarit n'impose alors aucune couleur et laisse celle du thème agir.
    Imposer du blanc « au cas où » serait pire : sur un dégradé clair, on
    rendrait illisible ce qui l'était.
    """
    luminance = luminance_relative(fond)
    if luminance is None:
        return ''
    return (TEXTE_SUR_FOND_SOMBRE if luminance < SEUIL_DE_BASCULE
            else TEXTE_SUR_FOND_CLAIR)


@register.filter
def est_fond_sombre(fond):
    """Ce fond demande-t-il du texte clair ? Faux si on ne sait pas."""
    luminance = luminance_relative(fond)
    return luminance is not None and luminance < SEUIL_DE_BASCULE


@register.simple_tag
def style_de_section(section):
    """Les déclarations CSS d'une section : son fond, et un texte lisible.

    Rend une chaîne vide si la section n'impose pas de fond — le gabarit
    écrit alors `style=""`, ce qui ne change rien au rendu.

    **Rien n'est marqué sûr ici, volontairement.** La valeur rendue est
    réinjectée dans un attribut `style`, et `bg_color` est un champ texte
    libre. En laissant le gabarit l'échapper, un guillemet tapé dans
    l'éditeur de site devient `&quot;` et ne peut pas refermer l'attribut
    pour en ouvrir un autre. C'est aussi ce que faisait l'écriture
    d'origine, `{{ section.bg_color }}` : il ne faut pas perdre cette
    propriété en passant par une balise.
    """
    fond = (getattr(section, 'bg_color', '') or '').strip()
    if not fond:
        return ''
    texte = (getattr(section, 'text_color', '') or '').strip()
    if not texte:
        texte = couleur_lisible(fond)
    declarations = ['background:%s' % fond]
    if texte:
        declarations.append('color:%s' % texte)
    return ';'.join(declarations)
