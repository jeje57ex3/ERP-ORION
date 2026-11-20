# -*- coding: utf-8 -*-
"""« Les boutons sont illisibles, et il n'y a pas de bouton de traduction. »

CE SITE N'EST PAS CELUI QUE JE CROYAIS

La vitrine « s-peace.com » est la vitrine ÉTANCHÉITÉ, reconnue à son slug
par `domaine_vitrine_middleware` et servie par ses propres adresses et ses
propres gabarits — `templates/websites/public/etancheite/`. Elle ne rend
donc ni `public/base.html` ni `public/home.html`, où un tour précédent avait
corrigé un défaut de contraste. Le travail était juste et portait sur les
sites vitrines GÉNÉRIQUES ; il ne touchait pas celui-ci.

LES BOUTONS

`.btn-sable` prend son FOND dans `theme.button_color` et prenait son TEXTE
dans `theme.primary_color`. Deux couleurs du thème, et rien ne garantit
qu'elles contrastent. Avec la palette d'origine — sable clair sur ardoise —
le contraste atteint 10,6 et tout allait bien. Avec un thème dont le bouton
et le primaire se rapprochent, le texte disparaît dans son propre fond :
pour deux couleurs identiques, le contraste vaut 1,00.

Cette seule classe porte les deux boutons signalés : « Demander un devis »
(en-tête, héros, appel final) et « Nos réalisations » (bloc réalisations).

`.btn-ardoise` et `.bande-sombre` avaient le défaut symétrique : fond pris
dans le thème, texte fixé à `#fff`. Un primaire clair les rendait illisibles.

LE BOUTON DE TRADUCTION

Le gabarit n'en portait aucun — seul `<html lang>` suivait la langue. Le
contexte fournissait pourtant déjà `website_languages`, et un composant
partagé existait, inclus jusqu'ici par le seul en-tête BTP.

LA TRADUCTION, ET POURQUOI ELLE PARAISSAIT ABSENTE

Deux raisons superposées. `_sections()` ne passait jamais par
`_translated()` : les menus se traduisaient, les titres, textes et libellés
de boutons restaient en français. Et sur les 48 chaînes traduisibles des
gabarits de cette vitrine, 25 seulement figuraient dans les catalogues
anglais, espagnol et portugais — 9 en allemand. La moitié du site restait
donc en français dans TOUTES les langues, ce qui se lit comme « la
traduction ne marche pas » plutôt que comme « ces chaînes-là manquent ».
"""
import os
import re

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GABARIT_BASE = os.path.join(RACINE, 'templates', 'websites', 'public',
                            'etancheite', 'base.html')


def _source(chemin):
    with open(chemin, encoding='utf-8') as fichier:
        return fichier.read()


# ═══ 1. LE CONTRASTE DES BOUTONS ════════════════════════════════════════════

def test_deux_couleurs_identiques_ne_restent_pas_identiques():
    """LE DÉFAUT, chiffré.

    `.btn-sable` peignait son texte avec `primary_color` sur un fond
    `button_color`. Quand les deux coïncident — c'est le cas d'un thème
    Orion par défaut, où les deux valent `#2563EB` — le contraste vaut
    1,00 : le texte est invisible, pas seulement difficile à lire.
    """
    from apps.websites.couleurs import contraste, texte_lisible_sur

    assert contraste('#2563EB', '#2563EB') == pytest.approx(1.0)

    retenu = texte_lisible_sur('#2563EB', '#2563EB')
    assert contraste('#2563EB', retenu) >= 4.5


def test_un_choix_qui_contraste_assez_est_conserve():
    """On ne corrige que ce qui serait illisible.

    La palette d'origine de cette vitrine — sable `#E8D9BE` sur ardoise
    `#1C2A33` — atteint 10,6. Changer cette couleur serait s'arroger une
    décision de dessin qui ne nous appartient pas.
    """
    from apps.websites.couleurs import contraste, texte_lisible_sur

    assert contraste('#E8D9BE', '#1C2A33') > 10
    assert texte_lisible_sur('#E8D9BE', '#1C2A33') == '#1C2A33'


@pytest.mark.parametrize('fond,voulu', [
    ('#2563EB', '#2563EB'),   # identiques
    ('#1C2A33', '#2E3F4A'),   # deux sombres proches
    ('#E8D9BE', '#FBF8F3'),   # deux clairs proches
])
def test_aucune_paire_ne_reste_sous_le_seuil(fond, voulu):
    """Quelle que soit la collision, on remonte au-dessus de 4,5."""
    from apps.websites.couleurs import contraste, texte_lisible_sur

    retenu = texte_lisible_sur(fond, voulu)
    assert contraste(fond, retenu) >= 4.5


def test_la_vue_fournit_les_couleurs_de_bouton():
    """Sans ces deux clés de contexte, le gabarit retomberait sur ses
    valeurs par défaut et le thème ne piloterait plus rien."""
    source = _source(os.path.join(RACINE, 'apps', 'websites',
                                  'etancheite_public_views.py'))

    assert "'texte_sur_bouton'" in source
    assert "'texte_sur_primaire'" in source


def test_aucun_bouton_ne_fixe_plus_sa_couleur_de_texte():
    """La garde qui survivra à ce travail.

    Le défaut n'est pas dans une règle mais dans un réflexe : écrire
    `color: #fff` sous un fond que l'exploitant choisit. Ce test échoue si
    l'une des trois règles de bouton revient à une couleur fixe.
    """
    source = _source(GABARIT_BASE)

    for regle in ('.btn-sable', '.btn-ardoise'):
        debut = source.index(regle + ' {')
        bloc = source[debut:debut + 240]
        assert 'var(--texte-' in bloc, (
            '%s ne deduit plus sa couleur de texte : son fond vient du '
            'theme, son texte doit en etre deduit.' % regle)

    # La bande sombre porte du texte sur le primaire du theme, comme
    # `.btn-ardoise`.
    debut = source.index('.bande-sombre {')
    bloc = source[debut:debut + 200]
    assert 'var(--texte-primaire)' in bloc


# ═══ 2. LE BOUTON DE TRADUCTION ═════════════════════════════════════════════

def test_le_selecteur_de_langue_est_dans_l_en_tete():
    """Il n'y en avait aucun : seul `<html lang>` suivait la langue."""
    source = _source(GABARIT_BASE)

    inclusion = ('{% include "websites/public/components/'
                 'language_switcher.html" %}')
    assert inclusion in source

    # Dans l'en-tête, et non en pied : on change de langue avant de lire.
    #
    # On cherche l'INCLUSION et non le nom du fichier : ce nom figure aussi
    # dans le commentaire qui explique d'où vient le style du composant, et
    # ce commentaire précède l'en-tête. Première version de ce test, qui
    # mesurait donc la position d'un commentaire.
    position_entete = source.index('<header class="entete">')
    position_switcher = source.index(inclusion)
    position_fin_entete = source.index('</header>')
    assert position_entete < position_switcher < position_fin_entete


def test_le_balisage_du_selecteur_n_est_pas_recopie():
    """On inclut le composant partagé plutôt que d'en copier le balisage.

    Une correction d'accessibilité faite sur le composant doit profiter aux
    deux sites qui l'emploient. Du balisage recopié se corrige une fois sur
    deux — c'est la famille de défauts que ce dépôt rencontre le plus.
    """
    source = _source(GABARIT_BASE)

    assert 'id="siteLangMenu"' not in source, (
        'le balisage du selecteur est recopie dans le gabarit au lieu '
        'd-etre inclus depuis le composant partage.')


def test_le_selecteur_a_son_style_et_son_comportement():
    """Le composant seul ne suffit pas ici.

    Son style vit dans `static/css/sites/orion-site-theme.css`, qui
    s'appuie sur des variables `--site-*` que cette vitrine ne définit
    pas : importer cette feuille romprait sa palette. Les règles et le
    comportement sont donc écrits dans ce gabarit, qui est volontairement
    autonome.
    """
    source = _source(GABARIT_BASE)

    assert '.site-lang-menu {' in source
    assert '.site-lang-item {' in source
    assert "getElementById('siteLangToggle')" in source
    # Fermeture au clic extérieur et à Échap : sans elles, un menu ouvert
    # sur un téléphone masque la navigation.
    assert "'Escape'" in source


# ═══ 3. LA TRADUCTION DU CONTENU ════════════════════════════════════════════

def test_les_sections_passent_par_la_traduction():
    """Les menus étaient traduits, les sections non.

    Le résultat à l'écran était un mélange : navigation traduite, titres et
    boutons en français. Un visiteur en conclut que la traduction ne
    fonctionne pas.
    """
    source = _source(os.path.join(RACINE, 'apps', 'websites',
                                  'etancheite_public_views.py'))

    debut = source.index('def _sections(site):')
    corps = source[debut:debut + 1600]
    assert '_translated(' in corps, (
        '_sections rend les sections brutes : le contenu du site ne sera '
        'traduit dans aucune langue.')


@pytest.mark.django_db
def test_une_section_traduite_s_affiche_dans_la_langue_active():
    """Mesuré sur le résultat, et non sur la présence d'un appel."""
    from django.utils import translation

    from apps.core.models import Company
    from apps.websites.etancheite_public_views import _sections
    from apps.websites.models import (
        Website, WebsitePage, WebsiteSection, WebsiteSectionTranslation)

    entreprise = Company.objects.create(name='Sparkling Peace', slug='sp-et')
    site = Website.objects.create(
        company=entreprise, name='Sparkling Peace',
        slug='electricite-etancheite', domain='s-peace.com',
        site_type='showcase', status='published', is_active=True)
    page = WebsitePage.objects.create(
        website=site, title='Accueil', slug='accueil', is_homepage=True,
        status='published')
    section = WebsiteSection.objects.create(
        page=page, section_type='hero', title='Étanchéité et électricité',
        button_text='Demander un devis', order=0, is_visible=True)
    WebsiteSectionTranslation.objects.create(
        section=section, language='pt', title='Impermeabilização e eletricidade',
        button_text='Pedir orçamento')

    with translation.override('pt'):
        blocs = _sections(site)
        assert blocs['hero'].title == 'Impermeabilização e eletricidade'
        assert blocs['hero'].button_text == 'Pedir orçamento'

    # Et en français, l'objet est rendu inchangé : aucune écriture en base.
    with translation.override('fr'):
        assert _sections(site)['hero'].title == 'Étanchéité et électricité'
    section.refresh_from_db()
    assert section.title == 'Étanchéité et électricité'


# ═══ 4. LA COUVERTURE DES CHAÎNES DU SITE ═══════════════════════════════════

def _chaines_du_gabarit_etancheite():
    """Les chaînes traduisibles des gabarits de cette vitrine.

    Lues sur les gabarits et non recopiées : une liste écrite à la main se
    périmerait au premier texte ajouté, et c'est précisément ce qu'on
    cherche à éviter.
    """
    motif = re.compile(r"""\{%\s*(?:trans|translate)\s+(["'])(.+?)\1""",
                       re.S)
    dossier = os.path.dirname(GABARIT_BASE)
    chaines = set()
    for nom in sorted(os.listdir(dossier)):
        if not nom.endswith('.html'):
            continue
        with open(os.path.join(dossier, nom), encoding='utf-8',
                  errors='replace') as fichier:
            for _quote, texte in motif.findall(fichier.read()):
                chaines.add(texte.strip())
    return chaines


@pytest.mark.parametrize('langue', ['en', 'es', 'pt', 'de'])
def test_toutes_les_chaines_du_site_sont_traduites(langue):
    """LA MOITIÉ MANQUAIT, et rien ne le disait.

    25 chaînes sur 48 figuraient dans en/es/pt, 9 sur 48 en allemand. Une
    chaîne sans traduction retombe sur le français : la page s'affiche, et
    le visiteur lit un site à moitié traduit sans qu'aucune erreur ne soit
    levée. C'est exactement le genre de défaut qu'un test doit porter,
    parce que personne ne relit 48 chaînes dans quatre langues.
    """
    chaines = _chaines_du_gabarit_etancheite()
    assert chaines, 'aucune chaine trouvee : ce test ne garderait rien.'

    chemin = os.path.join(RACINE, 'locale', langue, 'LC_MESSAGES',
                          'django.po')
    assert os.path.exists(chemin), 'catalogue %s absent' % langue
    catalogue = _source(chemin)

    absentes = [chaine for chaine in sorted(chaines)
                if 'msgid "%s"' % chaine.replace('"', '\\"')
                not in catalogue]

    assert not absentes, (
        '%d chaine(s) de la vitrine etancheite absente(s) du catalogue '
        '%s. Elles retomberont sur le francais, sans erreur :\n  %s'
        % (len(absentes), langue, '\n  '.join(absentes[:12])))


def test_les_cas_ambigus_sont_traduits_chacun_pour_soi():
    """Plusieurs chaînes se ressemblent, et ne disent pas la même chose.

    « Tous » est un filtre de réalisations ; « Tous droits réservés. » est
    une mention légale. « Services » est une rubrique de menu ; « Nos
    services » un titre de section. Une correspondance approximative les
    confondrait, et la confusion ne se verrait que dans une langue, sur un
    écran.
    """
    from django.utils import translation

    with translation.override('de'):
        assert translation.gettext('Tous') == 'Alle'
        assert translation.gettext('Tous droits réservés.') == (
            'Alle Rechte vorbehalten.')
        assert translation.gettext('Services') == 'Leistungen'
        assert translation.gettext('Nos services') == 'Unsere Leistungen'
        assert translation.gettext('Contact') == 'Kontakt'
        assert translation.gettext('CONTACT') == 'KONTAKT'
