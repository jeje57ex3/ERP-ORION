"""« Vérifie que les textes ne sont pas illisibles avec les fonds bleu. »

DEUX FAMILLES DE DÉFAUTS, ET LA SECONDE EST DE MON FAIT

1. DANS L'ERP. Des encadrés posaient un fond OPAQUE — un bleu clair, un
   gris clair — sans fixer la couleur du texte, qui reste héritée de la
   page : sombre en thème clair, CLAIRE en thème sombre. Du clair sur
   clair, donc, et seulement dans un thème sur deux : invisible à la
   relecture.

   Pire, « --orion-code-bg » n'est défini NULLE PART dans les feuilles de
   style : le repli gris clair s'appliquait toujours, quel que soit le
   thème.

2. SUR LE SITE VITRINE. En rendant le fond des pages pilotable par le
   thème, on a permis de choisir un bleu profond sous un texte resté
   sombre. Le texte est désormais DÉDUIT de la luminance du fond.

LA MESURE PLUTÔT QUE L'ŒIL

Le contraste est calculé selon la recommandation WCAG : 4,5 pour le texte
courant, 3 pour les grands titres. Un test qui se contenterait de regarder
si « une couleur est écrite » ne dirait rien de la lisibilité.
"""
import pytest

from apps.websites.couleurs import (contraste, est_sombre, luminance,
                                    texte_lisible_sur)


SEUIL_TEXTE = 4.5


# ── 1. Le calcul lui-même ────────────────────────────────────────────────────

def test_la_luminance_suit_la_perception_et_non_la_moyenne():
    """LE PIÈGE QUE CE MODULE ÉVITE.

    L'œil ne perçoit pas les trois canaux également : un vert pur paraît
    bien plus clair qu'un bleu pur de même valeur. Une moyenne naïve
    jugerait « #0000FF » aussi clair que « #00FF00 » et poserait du texte
    sombre sur un bleu nuit.
    """
    assert luminance('#00FF00') > luminance('#0000FF') * 5


def test_un_bleu_profond_est_vu_comme_sombre():
    for bleu in ('#0B1220', '#1D4ED8', '#123456', '#0000FF', '#2563EB'):
        assert est_sombre(bleu) is True, f'{bleu} jugé clair à tort'


def test_un_bleu_clair_est_vu_comme_clair():
    for bleu in ('#E0F2FE', '#DBEAFE', '#eef4ff'):
        assert est_sombre(bleu) is False, f'{bleu} jugé sombre à tort'


def test_une_couleur_illisible_ne_fait_rien_tomber():
    """Un thème vide ou une saisie fautive ne doit pas casser une page
    publique. On retombe alors sur un fond clair, qui est le défaut."""
    for valeur in ('', None, 'bleu', '#ZZZ', '#12345'):
        assert luminance(valeur) is None
        assert est_sombre(valeur) is False


def test_les_ecritures_courtes_sont_acceptees():
    assert luminance('#fff') == pytest.approx(luminance('#FFFFFF'))


def test_le_contraste_est_symetrique_et_borne():
    assert contraste('#000000', '#FFFFFF') == pytest.approx(21, abs=.1)
    assert contraste('#FFFFFF', '#000000') == pytest.approx(21, abs=.1)
    assert contraste('#777777', '#777777') == pytest.approx(1, abs=.01)


# ── 2. Le choix du texte ─────────────────────────────────────────────────────

@pytest.mark.parametrize('fond', [
    '#0B1220', '#1C2A33', '#1D4ED8', '#123456', '#0000FF',
    '#FBF8F3', '#FFFFFF', '#E0F2FE', '#F5B93D',
])
def test_le_texte_deduit_est_toujours_lisible(fond):
    """LA GARANTIE CENTRALE : quel que soit le fond, le texte se lit."""
    texte = texte_lisible_sur(fond)
    ecart = contraste(fond, texte)
    assert ecart >= SEUIL_TEXTE, (
        f'contraste {ecart:.1f} sur {fond} — en dessous de {SEUIL_TEXTE}')


def test_un_choix_d_exploitant_qui_convient_est_respecte():
    """On ne corrige que ce qui serait illisible.

    Remplacer une couleur qui convient serait s'arroger une décision de
    dessin : un gris anthracite sur fond sable est un choix, pas une
    erreur.
    """
    souhaite = '#333333'
    assert texte_lisible_sur('#FBF8F3', souhaite) == souhaite


def test_un_choix_d_exploitant_illisible_est_corrige():
    """Texte sombre sur bleu nuit : c'est le cas signalé."""
    resultat = texte_lisible_sur('#0B1220', '#1C2A33')
    assert resultat != '#1C2A33'
    assert contraste('#0B1220', resultat) >= SEUIL_TEXTE


# ── 3. Le site vitrine, page par page ────────────────────────────────────────

@pytest.fixture
def site(db):
    from apps.core.models import Company
    from apps.websites.vitrine_etancheite import creer_le_site

    entreprise = Company.objects.create(name='Volt SARL', slug='volt-sarl')
    site, _ = creer_le_site(entreprise)
    return site


PAGES = ['', 'services/', 'realisations/', 'entreprise/', 'contact/',
         'devis/']


@pytest.mark.django_db
@pytest.mark.parametrize('chemin', PAGES)
@pytest.mark.parametrize('fond', ['#0B1220', '#1D4ED8', '#FBF8F3'])
def test_chaque_page_reste_lisible_quel_que_soit_le_fond(client, site,
                                                          chemin, fond):
    """Le cas rapporté : un fond bleu choisi dans le thème.

    On relit la couleur que la page s'est donnée et on MESURE son
    contraste avec le fond — plutôt que de supposer qu'elle convient.
    """
    import re

    site.theme.background_color = fond
    site.theme.text_color = '#1C2A33'      # le sombre d'origine
    site.theme.save()

    reponse = client.get(f'/sites/{site.slug}/etancheite/{chemin}')
    assert reponse.status_code == 200
    contenu = reponse.content.decode()

    trouve = re.search(r'--texte:\s*(#[0-9A-Fa-f]{3,6})', contenu)
    assert trouve, 'la page ne déclare pas sa couleur de texte'

    ecart = contraste(fond, trouve.group(1))
    assert ecart >= SEUIL_TEXTE, (
        f'/{chemin} sur {fond} : contraste {ecart:.1f}, texte illisible')


@pytest.mark.django_db
def test_l_entete_et_le_pied_ont_leur_propre_texte(client, site):
    """Trois surfaces peuvent être colorées indépendamment. Déduire un seul
    texte pour les trois rendrait l'une des deux autres illisible."""
    import re

    site.theme.background_color = '#FFFFFF'
    site.theme.header_bg_color = '#0B1220'   # en-tête sombre
    site.theme.footer_bg_color = '#FFFFFF'   # pied clair
    site.theme.save()

    contenu = client.get(
        f'/sites/{site.slug}/etancheite/').content.decode()

    for variable, fond in (('--texte-entete', '#0B1220'),
                           ('--texte-pied', '#FFFFFF')):
        trouve = re.search(variable + r':\s*(#[0-9A-Fa-f]{3,6})', contenu)
        assert trouve, f'{variable} absente'
        ecart = contraste(fond, trouve.group(1))
        assert ecart >= SEUIL_TEXTE, (
            f'{variable} sur {fond} : contraste {ecart:.1f}')


# ── 4. Les encadrés de l'ERP ─────────────────────────────────────────────────

def test_aucun_fond_opaque_sans_couleur_de_texte():
    """LE DÉFAUT DE L'ERP, ET SON GARDE-FOU.

    Un fond opaque fige une luminosité ; le texte, lui, est hérité et
    change avec le thème. Un voile NEUTRE TRANSLUCIDE, au contraire,
    assombrit une surface claire et éclaircit une surface sombre : le
    contraste est conservé sans avoir à connaître le thème.

    Le test n'interdit pas les fonds — il interdit les fonds opaques posés
    sans fixer la couleur du texte qui ira dessus.
    """
    import re
    from pathlib import Path

    surveilles = [
        'apps/core/templates/core/reglages_mail.html',
        'apps/system_health/templates/system_health/proxmox_reglages.html',
        'apps/system_health/templates/system_health/controle_installation.html',
        'apps/system_health/templates/system_health/'
        '_ajouter_un_disque_hyperviseur.html',
    ]

    fautifs = []
    for nom in surveilles:
        for numero, ligne in enumerate(
                Path(nom).read_text(encoding='utf-8').splitlines(), 1):
            if 'background' not in ligne:
                continue
            # Un voile translucide est sûr : il suit la surface du dessous.
            if 'rgba(' in ligne:
                continue
            # Un fond opaque n'est admis que si la couleur du texte est
            # fixée sur le même élément.
            if re.search(r'background[^;"]*:\s*(#|var\()', ligne) \
                    and 'color:' not in ligne:
                fautifs.append(f'{Path(nom).name}:{numero}')

    assert not fautifs, (
        'fond opaque sans couleur de texte — illisible dans un thème sur '
        f'deux : {fautifs}')


def test_la_variable_de_fond_de_code_n_est_plus_employee():
    """« --orion-code-bg » n'est définie dans AUCUNE feuille de style : son
    repli gris clair s'appliquait donc toujours, thème sombre compris."""
    import subprocess

    resultat = subprocess.run(
        ['git', 'grep', '-l', '--', 'orion-code-bg'],
        capture_output=True, text=True)
    fichiers = [f for f in resultat.stdout.splitlines()
                if f.endswith('.html')]
    assert not fichiers, (
        f'variable jamais définie encore employée : {fichiers}')
