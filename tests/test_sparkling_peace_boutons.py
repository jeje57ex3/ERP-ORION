# -*- coding: utf-8 -*-
"""« Demander un devis » et « Voir toutes nos réalisations » étaient invisibles.

QUEL SITE EST « s-peace.com », ET POURQUOI JE M'ÉTAIS TROMPÉ DEUX FOIS

C'est la vitrine ÉLECTRICITÉ : slug `sparkling-peace-electricite`, servie
par `electricite_public_views` sous `/sites/<slug>/electricite/`, habillée
par `static/css/sites/sparkling-peace.css`.

Je l'avais d'abord prise pour un site vitrine générique, puis pour la
vitrine étanchéité — parce que la fixture de `tests/test_domaine_vitrine.py`
monte la vitrine étanchéité avec le domaine « s-peace.com ». **Une fixture
de test n'est pas la production.** Ce qui a tranché est le HTML réellement
servi : ses liens internes pointent vers
`/sites/sparkling-peace-electricite/electricite/`, et ses boutons portent
les classes `sp-btn--or`, `sp-btn--clair`, `sp-btn--contour`, qui
n'existent que dans la feuille de ce site.

Ce fichier existe aussi pour que le prochain n'ait pas à le redécouvrir.

LE DÉFAUT, ET POURQUOI IL ÉTAIT INVISIBLE DANS CHAQUE FICHIER PRIS À PART

`sparkling-peace.css` écrit :

    .sp-btn--or { background: var(--site-primary); color: #26201A; }

Elle a été pensée pour un primaire DORÉ — la classe s'appelle « or » — et
sur l'or `#F5B93D` ce brun très sombre donne un contraste de 9,12.
Parfaitement lisible.

Mais `electricite/base.html` émet un bloc `<style>` en ligne qui ÉCRASE
`--site-primary` avec `theme.primary_color`, et le thème de ce site y met
`#0B1220`, un bleu nuit — l'or étant dans `accent_color`. Le bouton sortait
donc en bleu nuit sous un texte presque noir : **contraste 1,16**, quand
4,5 sont exigés pour du texte courant.

Chaque fichier était défendable seul. C'est leur rencontre qui ne l'était
pas, et aucune relecture de l'un ou de l'autre ne l'aurait montré — il
fallait regarder la page.

TROIS boutons portent cette classe : « Demander un devis » (en-tête),
« Demander un devis gratuit » et « Voir toutes nos réalisations ».

LE FOND N'EST PAS TOUCHÉ, et c'est un choix. Repeindre le bouton en or
restaurerait l'intention de la feuille, mais changerait le dessin du site :
ce n'est pas une décision de correction. Le fond reste la couleur du thème,
et c'est le texte qui en est déduit.
"""
import os
import re

import pytest

pytestmark = pytest.mark.django_db

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEUILLE = os.path.join(RACINE, 'static', 'css', 'sites',
                       'sparkling-peace.css')
ENTETE = os.path.join(RACINE, 'templates', 'websites', 'public',
                      'electricite', 'components', 'header.html')

#: Les couleurs du thème réel, lues dans le bloc `<style>` de la page en
#: ligne. Elles ne sont pas inventées pour le test : c'est la rencontre de
#: ces deux valeurs-là avec la feuille qui produisait le défaut.
PRIMAIRE_REELLE = '#0B1220'
ACCENT_REEL = '#F5B93D'


def _source(chemin):
    with open(chemin, encoding='utf-8') as fichier:
        return fichier.read()


def _site(primaire=PRIMAIRE_REELLE, accent=ACCENT_REEL, langues=5):
    from apps.core.models import Company
    from apps.translations.models import Language, WebsiteLanguageSettings
    from apps.websites.models import Website, WebsiteTheme

    entreprise = Company.objects.create(name='Sparkling Peace', slug='sp-e')
    theme = WebsiteTheme.objects.create(
        company=entreprise, name='Sparkling Peace',
        primary_color=primaire, accent_color=accent)
    site = Website.objects.create(
        company=entreprise, name='Sparkling Peace',
        slug='sparkling-peace-electricite', site_type='showcase',
        status='published', is_active=True, is_published=True, theme=theme)

    if langues:
        codes = ['fr', 'en', 'de', 'es', 'pt'][:langues]
        reglages, _cree = WebsiteLanguageSettings.objects.get_or_create(
            website=site)
        reglages.enabled_languages.set(
            Language.objects.filter(code__in=codes, is_active=True))
        reglages.default_language = Language.objects.filter(
            code='fr').first()
        reglages.save()
    return site


def _accueil(client, site):
    reponse = client.get('/sites/%s/electricite/' % site.slug)
    assert reponse.status_code == 200, reponse.status_code
    return reponse.content.decode('utf-8')


# ═══ 1. LE CONTRASTE, CHIFFRÉ ═══════════════════════════════════════════════

def test_le_defaut_mesure_sur_les_couleurs_reelles():
    """1,16 contre 9,12 : la même couleur de texte, deux fonds.

    Ce test ne vérifie pas la correction, il fixe le DÉFAUT. Sans lui, la
    correction ressemblerait à une préférence de goût.
    """
    from apps.websites.couleurs import contraste

    assert contraste(PRIMAIRE_REELLE, '#26201A') < 1.3
    assert contraste(ACCENT_REEL, '#26201A') > 9


def test_le_texte_devient_lisible_sur_le_bleu_nuit():
    from apps.websites.couleurs import contraste, texte_lisible_sur

    retenu = texte_lisible_sur(PRIMAIRE_REELLE, '#26201A')
    assert contraste(PRIMAIRE_REELLE, retenu) >= 4.5


def test_un_primaire_dore_garde_son_texte_sombre():
    """Aucun changement de dessin quand la couleur convient déjà.

    Si l'exploitant remet de l'or en primaire — l'intention d'origine de la
    feuille — le texte doit repasser au brun sombre tout seul.
    """
    from apps.websites.couleurs import texte_lisible_sur

    assert texte_lisible_sur(ACCENT_REEL, '#26201A') == '#26201A'


# ═══ 2. LA PAGE RÉELLEMENT SERVIE ═══════════════════════════════════════════

def test_la_page_pose_une_couleur_de_texte_lisible(client):
    """Mesuré sur la route réelle, avec le thème réel.

    C'est le seul niveau qui prouve quelque chose ici : le défaut naissait
    de la rencontre entre une feuille statique et un bloc `<style>` émis par
    un gabarit.
    """
    site = _site()
    html = _accueil(client, site)

    trouve = re.search(r'--sp-texte-sur-primaire:\s*([^;]+);', html)
    assert trouve is not None, (
        'la variable de couleur de texte des boutons n-est pas emise')
    assert trouve.group(1).strip().upper() == '#FFFFFF'


def test_les_trois_boutons_sont_bien_ceux_signales(client):
    """Les libellés, pour être sûr de corriger les bons boutons.

    La classe `sp-btn--or` porte « Demander un devis » et « Voir toutes nos
    réalisations ». Si un jour l'un d'eux change de classe, ce test le dit
    au lieu de laisser croire que la correction les couvre encore.
    """
    site = _site()
    html = _accueil(client, site)

    boutons = {}
    for trouve in re.finditer(
            r'<a[^>]*class="([^"]*sp-btn[^"]*)"[^>]*>(.*?)</a>', html, re.S):
        texte = ' '.join(re.sub(r'<[^>]+>', ' ', trouve.group(2)).split())
        boutons.setdefault(trouve.group(1).strip(), []).append(texte)

    dores = boutons.get('sp-btn sp-btn--or', [])
    assert any('Demander un devis' in texte for texte in dores)
    assert any('réalisations' in texte for texte in dores)


def test_plus_aucune_couleur_de_texte_en_dur_dans_la_feuille():
    """La garde qui survivra à ce travail.

    Le défaut n'était pas une faute de frappe mais un réflexe : écrire une
    couleur de texte en dur sous un fond que l'exploitant choisit. Ce test
    échoue si la règle y revient.
    """
    feuille = _source(FEUILLE)

    for regle in ('.sp-btn--or {', '.sp-site a.sp-btn--or {'):
        debut = feuille.index(regle)
        bloc = feuille[debut:debut + 220]
        assert 'var(--sp-texte-sur-primaire' in bloc, (
            '%s ecrit sa couleur de texte en dur : le fond vient du theme, '
            'le texte doit en etre deduit.' % regle)


def test_le_repli_garde_la_valeur_d_origine():
    """Une page servie hors de cette vue ne doit pas changer d'aspect.

    La variable n'est posée que par `electricite/base.html`. Ailleurs, le
    repli `#26201A` rend exactement ce que la feuille rendait avant.
    """
    feuille = _source(FEUILLE)
    assert 'var(--sp-texte-sur-primaire, #26201A)' in feuille


# ═══ 3. LE BOUTON DE TRADUCTION ═════════════════════════════════════════════

def test_le_selecteur_de_langue_est_rendu(client):
    """Il n'existait pas sur ce site.

    Tout le reste était en place : le style du composant vient de
    `orion-site-theme.css`, son ouverture de `orion-site.js`, et les
    langues du contexte de `_base_context`. Seule l'inclusion manquait.
    """
    site = _site()
    html = _accueil(client, site)

    assert 'siteLangSwitcher' in html
    langues = re.findall(r'hreflang="(\w+)"', html)
    assert set(langues) == {'fr', 'en', 'de', 'es', 'pt'}


def test_l_entete_inclut_le_composant_partage():
    """Et ne recopie pas son balisage.

    Une correction d'accessibilité faite sur le composant doit profiter aux
    trois sites qui l'emploient.
    """
    entete = _source(ENTETE)

    assert 'components/language_switcher.html' in entete
    assert 'id="siteLangMenu"' not in entete, (
        'le balisage du selecteur est recopie au lieu d-etre inclus.')


def test_le_menu_de_langue_echappe_au_piege_de_specificite():
    """LE MÊME PIÈGE QUE LE LOGO ET LE SECOND BOUTON, DÉJÀ DOCUMENTÉ ICI.

    Le corps porte `class="orion-site elec-brand sp-site"`, et
    `orion-site-theme.css` pose `.orion-site a { color: inherit }`, de
    spécificité 0,1,1. La règle du composant, `.site-lang-item`, n'en pèse
    que 0,1,0 : « inherit » l'emporte quel que soit l'ordre de chargement.
    Les entrées auraient hérité du blanc de l'en-tête — posé sur la photo du
    héros — sur un panneau blanc.
    """
    feuille = _source(FEUILLE)

    assert '.sp-site .site-lang-menu a.site-lang-item' in feuille, (
        'sans regle qualifiee, « .orion-site a { color: inherit } » rend '
        'les entrees du menu de langue invisibles sur leur panneau blanc.')


def test_sans_langue_proposee_aucun_bouton_n_apparait(client):
    """Le composant se garde lui-même, et c'est le bon comportement.

    Un site dans une seule langue n'a pas besoin d'un sélecteur, et un
    bouton qui n'offre rien inquiète plus qu'il n'aide.
    """
    from apps.translations.models import WebsiteLanguageSettings

    site = _site(langues=0)
    WebsiteLanguageSettings.objects.filter(website=site).delete()
    reglages = WebsiteLanguageSettings.objects.create(website=site)
    reglages.enabled_languages.clear()
    reglages.show_language_switcher = False
    reglages.save()

    html = _accueil(client, site)
    assert 'siteLangSwitcher' not in html


# ═══ 4. QUEL SITE EST s-peace, ÉCRIT NOIR SUR BLANC ════════════════════════

def test_la_route_de_ce_site_rend_bien_sa_propre_feuille(client):
    """Pour que personne ne cherche ce site au mauvais endroit.

    Je l'ai cherché deux fois ailleurs — dans les gabarits génériques, puis
    dans la vitrine étanchéité — sur la foi d'une fixture de test. Ce test
    attache le slug, la route et la feuille les uns aux autres.
    """
    site = _site()
    html = _accueil(client, site)

    assert 'css/sites/sparkling-peace' in html
    assert 'sp-btn' in html
    # Et PAS les classes des deux autres familles de vitrines, qui m-ont
    # fait perdre deux tours.
    assert 'btn-sable' not in html       # vitrine etancheite
    assert 'ws-fond-sombre' not in html  # vitrines generiques
