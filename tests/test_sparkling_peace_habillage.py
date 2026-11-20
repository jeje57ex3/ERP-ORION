"""« Fais le site Sparkling Peace avec l'apparence de la maquette. »

CE QUE CES TESTS SURVEILLENT

Pas le dessin — un test ne juge pas d'une maquette. Ils surveillent les
quatre choses qui le font SILENCIEUSEMENT échouer :

1. L'ORDRE ET LA SPÉCIFICITÉ DES FEUILLES. « orion-site-theme.css » pose
   « .orion-site a { color: inherit } », de spécificité 0,1,1. Mes règles
   « .sp-logo » n'en pesaient que 0,1,0 : malgré l'ordre de chargement,
   c'est « inherit » qui l'emportait et le nom de la marque sortait en
   sombre sur un en-tête noir. Invisible, sans erreur nulle part.

2. LA POLICE SÉRIF. C'est le trait le plus visible du dessin et le plus
   facile à perdre : une sans-serif à la place, et tout le caractère tombe
   sans qu'on sache dire pourquoi.

3. LE REPLI DES VISUELS. Aucune photo n'est livrée : elles viennent du
   catalogue de l'exploitant. Chaque emplacement doit tenir sans elles.

4. LA LISIBILITÉ SUR LES BANDES SOMBRES, mesurée et non supposée.
"""
from pathlib import Path

import pytest

FEUILLE = Path('static/css/sites/sparkling-peace.css')
BASE = Path('templates/websites/public/electricite/base.html')
ENTETE = Path('templates/websites/public/electricite/components/header.html')
ACCUEIL = Path('templates/websites/public/electricite/home.html')


def test_la_feuille_se_charge_apres_la_feuille_commune():
    """Chargée AVANT, elle serait écrasée par le bleu et l'orange qui
    habillent les autres vitrines de l'ERP."""
    texte = BASE.read_text(encoding='utf-8')

    commune = texte.index('orion-site-theme.css')
    propre = texte.index('sparkling-peace.css')

    assert propre > commune, (
        'la feuille de Sparkling Peace doit etre chargee apres la commune')


def test_les_couleurs_de_lien_sont_qualifiees_assez():
    """LE DÉFAUT RENCONTRÉ AU RENDU.

    « .orion-site a { color: inherit } » pèse 0,1,1. Une règle « .sp-logo »
    (0,1,0) perd malgré l'ordre de chargement. L'ordre ne suffit pas : il
    faut nommer la spécificité.
    """
    css = FEUILLE.read_text(encoding='utf-8')

    for selecteur in ('.sp-site a.sp-logo', '.sp-site .sp-nav a',
                      '.sp-site a.sp-btn--clair'):
        assert selecteur in css, (
            f'{selecteur} manque — le texte ressortira dans la couleur du '
            'corps, donc sombre sur un en-tete noir')


def test_les_titres_sont_en_serif():
    css = FEUILLE.read_text(encoding='utf-8')
    base = BASE.read_text(encoding='utf-8')

    assert '--sp-serif' in css
    assert 'serif' in css[css.index('--sp-serif'):css.index('--sp-serif') + 120]
    assert 'Playfair+Display' in base, 'la police n’est pas chargée'


def test_chaque_visuel_a_son_repli():
    """Une vitrine qui se vide parce qu'une photo manque est une panne ;
    une page sobre n'en est pas une."""
    css = FEUILLE.read_text(encoding='utf-8')

    for classe in ('.sp-hero', '.sp-carte__visuel', '.sp-photo'):
        bloc = css[css.index(classe):css.index(classe) + 420]
        assert 'gradient' in bloc or 'background:' in bloc, (
            f'{classe} n’a pas de fond de repli')


def test_le_gabarit_rend_les_quatre_bandes():
    page = ACCUEIL.read_text(encoding='utf-8')

    for bande in ('sp-hero', 'sp-confiance', 'sp-cartes', 'sp-realisations'):
        assert bande in page, f'la bande « {bande} » manque'


def test_l_entete_distingue_la_page_a_photo_des_autres():
    """Sur l'accueil il est posé sur la photo, donc transparent avec du
    texte clair. Ailleurs il n'y a pas de photo : il doit redevenir opaque,
    sans quoi ce même texte clair se poserait sur du clair."""
    entete = ENTETE.read_text(encoding='utf-8')

    assert 'entete_sur_photo' in entete
    assert 'sp-entete--opaque' in entete


def test_le_logo_livre_avec_le_site_existe():
    """Le repli employé tant qu'aucun logo n'est téléversé depuis l'ERP."""
    logo = Path('static/img/sites/sparkling-peace-logo.png')

    assert logo.exists()
    assert logo.stat().st_size < 400 * 1024, (
        'un logo de plus de 400 Ko se telecharge a chaque page')
    assert "{% static 'img/sites/sparkling-peace-logo.png' %}" in \
        ENTETE.read_text(encoding='utf-8')


@pytest.mark.parametrize('fond, texte, seuil', [
    ('#222220', '#FFFFFF', 4.5),      # titres et texte sur l'anthracite
    ('#222220', '#C8A47C', 4.5),      # le surtitre or sur l'anthracite
    ('#EDE5DC', '#1C1A18', 4.5),      # la bande de confiance
    ('#EDE5DC', '#66615A', 4.5),      # son texte secondaire
    ('#FBF9F6', '#66615A', 4.5),      # et sur le fond general
    ('#C8A47C', '#26201A', 4.5),      # le texte des boutons or
    ('#F4EFE8', '#221F1B', 4.5),      # la pastille de filtre active
])
def test_les_couleurs_retenues_sont_lisibles(fond, texte, seuil):
    """MESURÉ, pas supposé. Le contraste d'un or sur un anthracite se juge
    très mal à l'œil — c'est exactement là qu'on se trompe."""
    from apps.websites.couleurs import contraste

    ecart = contraste(fond, texte)
    assert ecart >= seuil, (
        f'{texte} sur {fond} : contraste {ecart:.1f}, en dessous de {seuil}')


# ── Les photographies livrées avec le site ───────────────────────────────────

"""Neuf photos accompagnent le site (Pexels, licence libre). Elles ne sont
qu'un REPLI : dès qu'un service ou une réalisation porte sa propre image,
c'est elle qui s'affiche. L'exploitant les remplace une par une depuis
l'ERP, sans jamais passer par le code — et sans qu'une page reste vide en
attendant."""

PHOTOS = Path('static/img/sites/sparkling-peace')


def test_les_neuf_photos_sont_livrees():
    from apps.websites.electricite_public_views import (PHOTOS_DE_REALISATION,
                                                        PHOTOS_DE_SERVICE)

    attendues = ['hero-villa.jpg'] + PHOTOS_DE_SERVICE + PHOTOS_DE_REALISATION
    manquantes = [n for n in attendues if not (PHOTOS / n).exists()]

    assert not manquantes, manquantes


def test_les_photos_restent_legeres():
    """Elles partent sur chaque page d'accueil : une seule photo lourde se
    paie à chaque visite, et d'abord par ceux qui sont en 4G."""
    lourdes = [(f.name, f.stat().st_size // 1024)
               for f in PHOTOS.glob('*.jpg') if f.stat().st_size > 350 * 1024]

    assert not lourdes, f'photo(s) de plus de 350 Ko : {lourdes}'

    total = sum(f.stat().st_size for f in PHOTOS.glob('*.jpg'))
    assert total < 1600 * 1024, f'{total // 1024} Ko au total, c’est trop'


def test_la_provenance_est_tracee():
    """Une image sans source devient inutilisable le jour où quelqu'un
    demande d'où elle vient."""
    credits = (PHOTOS / 'CREDITS.md').read_text(encoding='utf-8')

    assert 'pexels.com/license' in credits
    assert 'Attribution facultative' in credits


@pytest.mark.django_db
def test_l_image_de_l_exploitant_prime_sur_la_notre():
    """LE CONTRAT : nos photos comblent un vide, elles ne l'occupent pas."""
    from apps.websites.electricite_public_views import _cartes_de_services

    class FauxService:
        title = 'Dépannage 24/7'
        description = 'Intervention rapide.'
        icon = 'bi-tools'

        class image:
            url = '/media/websites/services/depannage.jpg'

    cartes = _cartes_de_services([FauxService()], [])

    assert cartes[0]['image'] == '/media/websites/services/depannage.jpg'
    assert cartes[0]['titre'] == 'Dépannage 24/7'


@pytest.mark.django_db
def test_sans_rien_les_quatre_cartes_tiennent_quand_meme():
    """Un site neuf doit montrer ce que l'entreprise sait faire, pas un
    blanc."""
    from apps.websites.electricite_public_views import (ELECTRICITE_SERVICES,
                                                        _cartes_de_services)

    cartes = _cartes_de_services([], ELECTRICITE_SERVICES)

    assert len(cartes) == 4
    assert all(c['image'] and c['titre'] for c in cartes)


# ── L'ordre des regles d'ecran ───────────────────────────────────────────────

def test_aucune_regle_de_base_apres_le_premier_media():
    """LA FAUTE COMMISE DEUX FOIS DANS CE FICHIER.

    Une retouche ajoutee APRES un bloc « @media » l'emporte sur lui a
    specificite egale — en CSS, c'est la derniere regle qui gagne. La
    bascule mobile ne s'appliquait donc pas : la page de telephone gardait
    la grille de bureau et debordait de l'ecran.

    La seconde fois, c'etait le bouton de menu lui-meme : son
    « display: none » de base passait apres le « display: inline-flex » de
    la regle d'ecran, et le bouton restait invisible au telephone — c'est
    a dire que la navigation n'existait plus du tout.

    Le remede n'est pas la vigilance, c'est l'ordre. Ce test le tient.
    """
    import re

    css = FEUILLE.read_text(encoding='utf-8')
    if '@media' not in css:
        pytest.skip('aucune regle d’ecran')

    apres = css[css.index('@media'):]
    # On retire les blocs @media eux-memes, puis les commentaires.
    sans_blocs = re.sub(r'@media[^{]*\{(?:[^{}]|\{[^{}]*\})*\}', '', apres)
    reste = re.sub(r'/\*.*?\*/', '', sans_blocs, flags=re.S).strip()

    assert not reste, (
        'regle(s) de base apres le premier @media — elles annuleront la '
        f'bascule mobile : {reste[:160]}')


def test_les_grilles_mobiles_emploient_minmax():
    """« 1fr » vaut « minmax(auto, 1fr) » : la piste ne descend pas sous la
    largeur minimale de son contenu. Une bande de filtres en « nowrap »
    elargissait ainsi la colonne au-dela de l'ecran, et TOUTE la page
    glissait avec elle."""
    import re

    css = FEUILLE.read_text(encoding='utf-8')
    apres = css[css.index('@media'):]

    fautifs = [l.strip() for l in apres.splitlines()
               if 'grid-template-columns' in l and 'minmax' not in l]

    assert not fautifs, (
        f'piste(s) sans minmax(0, …) dans une regle d’ecran : {fautifs}')


def test_le_menu_mobile_existe():
    """« display: none » sur la navigation sans rien a la place rendait
    toutes les pages du site inatteignables depuis un telephone."""
    entete = ENTETE.read_text(encoding='utf-8')
    css = FEUILLE.read_text(encoding='utf-8')

    assert 'sp-burger' in entete and 'sp-burger' in css
    assert 'aria-expanded' in entete, 'un bouton dont rien ne dit l’effet'
    assert '.sp-entete.ouvert .sp-nav' in css, 'le menu ne s’ouvre jamais'
