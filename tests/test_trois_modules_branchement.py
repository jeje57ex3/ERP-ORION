"""Les trois derniers modules d'entreprise dormants, branchés.

`site_customization` (quinze vues, quatre modèles),
`apps.domain_manager` (six vues, un modèle) et `apps.orders` (quatre vues,
sans modèle propre) étaient sur le disque sans être déclarées ni montées,
et sans aucun test.

**Un défaut trouvé au premier chargement.**
`apps/domain_manager/views.py` importait `require_active_company` depuis
`apps/private_saas/decorators.py`, qui n'expose que `super_admin_required`
et `require_company_module`. Ce nom n'existe nulle part dans le projet.
L'application n'étant pas déclarée, cet import n'avait jamais été exécuté :
il levait `ImportError` dès la première tentative. Il n'était de plus
utilisé par aucune vue, d'où son retrait plutôt que l'invention d'un
décorateur que rien n'appelle.

**Deux faux doublons, vérifiés et non supposés.** `apps.orders` ressemble
à `ecommerce:order_list` et n'en est pas un : il sert les `StoreOrder` de
la boutique SIÈCLE, là où l'entrée voisine liste des `CreationOrder`, des
commandes de créations sur mesure. De même, `domain_manager` cohabite avec
« Domaines » (les domaines des sites) et avec `domain_diagnostics` (qui
interroge Cloudflare) : lui gère le rattachement et la VÉRIFICATION de
domaines personnalisés — jetons, CNAME, A, TXT. Trois choses distinctes.
"""

import os

import pytest
from django.urls import reverse

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── Fixtures ───────────────────────────────────────────────────────────────

def _entreprise(slug, codes=('site_customization', 'domains', 'orders'),
                actif=True):
    from apps.core.models import Company
    from apps.private_saas.models import CompanyModule

    entreprise = Company.objects.create(name='Trois SA', slug=slug)
    for code in codes:
        CompanyModule.objects.update_or_create(
            company=entreprise, module_code=code,
            defaults={'is_enabled': actif})
    return entreprise


def _connecte(client, django_user_model, entreprise, nom, superadmin=True):
    from apps.accounts.models import UserProfile

    utilisateur = django_user_model.objects.create_user(
        nom, password='x', is_superuser=superadmin, is_staff=superadmin)
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.role = 'superadmin' if superadmin else 'user'
    profil.save()
    profil.companies.add(entreprise)

    client.force_login(django_user_model.objects.get(pk=utilisateur.pk))
    session = client.session
    session['current_company_id'] = entreprise.pk
    session.save()
    return utilisateur


@pytest.fixture
def decor(client, django_user_model):
    from apps.domain_manager.models import CustomDomain
    from apps.site_customization.models import (
        SiteContentBlock, SitePageCustomization, SitePageSection,
        SiteThemeSettings)
    from apps.websites.models import StoreOrder, Website

    entreprise = _entreprise('trois-sa')
    utilisateur = _connecte(client, django_user_model, entreprise, 'patron3')

    # La boutique SIECLE : apps.orders la cherche par slug='siecle' et
    # site_type='ecommerce'. Sans elle, la liste de commandes s'affiche
    # vide -- ce qui est un cas valide et teste separement.
    site = Website.objects.create(
        company=entreprise, name='Boutique SIÈCLE', slug='siecle',
        site_type='ecommerce', is_active=True)

    theme = SiteThemeSettings.objects.create(company=entreprise,
                                             website=site)
    page = SitePageCustomization.objects.create(
        company=entreprise, website=site, title='Accueil')
    section = SitePageSection.objects.create(page=page, title='Bandeau')
    bloc = SiteContentBlock.objects.create(section=section)
    domaine = CustomDomain.objects.create(company=entreprise,
                                          domain='boutique.exemple.fr')
    commande = StoreOrder.objects.create(
        website=site, company=entreprise, order_number='CMD-0001',
        customer_name='Jean Dupont', customer_email='jean@exemple.fr')

    return {
        'entreprise': entreprise, 'utilisateur': utilisateur, 'site': site,
        'theme': theme, 'page': page, 'section': section, 'bloc': bloc,
        'domaine': domaine, 'commande': commande,
    }


# ── 1. Les trois applications sont chargées ───────────────────────────────

@pytest.mark.parametrize('nom', ['apps.site_customization',
                                 'apps.domain_manager', 'apps.orders'])
def test_l_application_est_enregistree(nom):
    from django.apps import apps

    assert apps.is_installed(nom)


def test_le_decorateur_inexistant_n_est_plus_importe():
    """Le défaut trouvé au premier chargement, verrouillé.

    `require_active_company` n'existe nulle part dans le projet. Tant que
    l'application n'était pas déclarée, cet import n'était jamais exécuté
    et le défaut restait invisible.
    """
    chemin = os.path.join(RACINE, 'apps', 'domain_manager', 'views.py')
    with open(chemin, encoding='utf-8') as fichier:
        contenu = fichier.read()

    # Seules les lignes d'import comptent : le nom reste cite dans un
    # commentaire qui explique le defaut, et le proscrire du fichier
    # entier interdirait de le documenter.
    lignes_d_import = [l for l in contenu.splitlines()
                       if l.startswith('from') or l.startswith('import')]
    assert not any('require_active_company' in l for l in lignes_d_import), (
        'require_active_company est reimporte : il n existe pas, et '
        'l application ne se chargera plus.')


def test_les_decorateurs_importes_existent_vraiment():
    """Le garde-fou general : la cause, et non le seul symptome.

    Un decorateur importe et absent ne leve qu'au CHARGEMENT du module.
    Pour une application non declaree, cela n'arrive jamais -- et le
    defaut attend le jour du branchement.
    """
    from apps.private_saas import decorators

    for nom in ('super_admin_required', 'require_company_module'):
        assert hasattr(decorators, nom), f'{nom} a disparu du module.'


@pytest.mark.parametrize('application,modeles', [
    ('site_customization', {'SiteThemeSettings', 'SitePageCustomization',
                            'SitePageSection', 'SiteContentBlock'}),
    ('domain_manager', {'CustomDomain'}),
])
def test_les_modeles_sont_connus(application, modeles):
    from django.apps import apps

    noms = {m.__name__ for m in apps.get_app_config(application).get_models()}
    assert modeles <= noms, 'Modèles absents : ' + ', '.join(
        sorted(modeles - noms))


@pytest.mark.parametrize('application', ['site_customization',
                                          'domain_manager'])
def test_la_migration_existe_sur_le_disque(application):
    dossier = os.path.join(RACINE, 'apps', application, 'migrations')
    fichiers = [f for f in os.listdir(dossier)
                if f.endswith('.py') and f != '__init__.py']
    assert fichiers, f'{application} : aucune migration, tables absentes.'


def test_orders_n_a_pas_de_modele_propre():
    """Et c'est voulu : elle lit les StoreOrder de apps.websites.

    Sans ce test, l'absence de migration pour `orders` ressemblerait a un
    oubli du meme genre que ceux corriges ici.
    """
    from django.apps import apps

    assert list(apps.get_app_config('orders').get_models()) == []


# ── 2. Les pages s'affichent ──────────────────────────────────────────────

@pytest.mark.django_db
@pytest.mark.parametrize('nom', ['dashboard', 'page_list', 'page_create'])
def test_les_pages_de_personnalisation_s_affichent(client, decor, nom):
    reponse = client.get(reverse(f'site_customization:{nom}'))
    assert reponse.status_code == 200, (
        f'site_customization:{nom} rend {reponse.status_code}')


@pytest.mark.django_db
def test_la_modification_du_theme_s_affiche(client, decor):
    reponse = client.get(reverse('site_customization:theme_edit',
                                 args=[decor['site'].pk]))
    assert reponse.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize('nom', ['page_detail', 'page_edit', 'page_preview'])
def test_les_pages_d_une_page_personnalisee_s_affichent(client, decor, nom):
    reponse = client.get(reverse(f'site_customization:{nom}',
                                 args=[decor['page'].pk]))
    assert reponse.status_code == 200, (
        f'site_customization:{nom} rend {reponse.status_code}')


@pytest.mark.django_db
def test_la_creation_d_une_section_s_affiche(client, decor):
    reponse = client.get(reverse('site_customization:section_create',
                                 args=[decor['page'].pk]))
    assert reponse.status_code == 200


@pytest.mark.django_db
def test_la_modification_d_une_section_s_affiche(client, decor):
    reponse = client.get(reverse('site_customization:section_edit',
                                 args=[decor['section'].pk]))
    assert reponse.status_code == 200


@pytest.mark.django_db
def test_la_creation_d_un_bloc_s_affiche(client, decor):
    reponse = client.get(reverse('site_customization:block_create',
                                 args=[decor['section'].pk]))
    assert reponse.status_code == 200


@pytest.mark.django_db
def test_la_modification_d_un_bloc_s_affiche(client, decor):
    reponse = client.get(reverse('site_customization:block_edit',
                                 args=[decor['bloc'].pk]))
    assert reponse.status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize('nom', ['list', 'create'])
def test_les_pages_de_domaines_s_affichent(client, decor, nom):
    reponse = client.get(reverse(f'domain_manager:{nom}'))
    assert reponse.status_code == 200, (
        f'domain_manager:{nom} rend {reponse.status_code}')


@pytest.mark.django_db
def test_le_detail_d_un_domaine_s_affiche(client, decor):
    reponse = client.get(reverse('domain_manager:detail',
                                 args=[decor['domaine'].pk]))
    assert reponse.status_code == 200


@pytest.mark.django_db
def test_la_liste_des_commandes_boutique_s_affiche(client, decor):
    reponse = client.get(reverse('orders:order_list'))
    assert reponse.status_code == 200


@pytest.mark.django_db
def test_le_detail_d_une_commande_s_affiche(client, decor):
    """Route par NUMERO de commande et non par identifiant technique."""
    reponse = client.get(reverse('orders:order_detail',
                                 args=[decor['commande'].order_number]))
    assert reponse.status_code == 200


@pytest.mark.django_db
def test_la_liste_des_commandes_tient_sans_boutique(client,
                                                    django_user_model):
    """Cas valide : une entreprise sans boutique SIÈCLE.

    `apps.orders` cherche un site de slug « siecle » ; s'il n'existe pas,
    la page doit s'afficher vide et non lever.
    """
    entreprise = _entreprise('sans-boutique')
    _connecte(client, django_user_model, entreprise, 'sans-boutique-user')

    reponse = client.get(reverse('orders:order_list'))
    assert reponse.status_code == 200


# ── 3. Les modules commandent l'accès ─────────────────────────────────────

@pytest.mark.django_db
@pytest.mark.parametrize('route,code', [
    ('site_customization:dashboard', 'site_customization'),
    ('domain_manager:list', 'domains'),
    ('orders:order_list', 'orders'),
])
def test_sans_le_module_la_page_est_refusee(client, django_user_model,
                                            route, code):
    """Mesuré avec un utilisateur ORDINAIRE : le décorateur exempte les
    superutilisateurs, et un test mené avec un superadmin ne dirait rien."""
    entreprise = _entreprise(f'sans-{code}', codes=(code,), actif=False)
    _connecte(client, django_user_model, entreprise, f'sans-{code}-user',
              superadmin=False)

    reponse = client.get(reverse(route))
    assert reponse.status_code != 200


@pytest.mark.django_db
@pytest.mark.parametrize('route,code', [
    ('site_customization:dashboard', 'site_customization'),
    ('domain_manager:list', 'domains'),
    ('orders:order_list', 'orders'),
])
def test_avec_le_module_un_utilisateur_ordinaire_entre(client,
                                                       django_user_model,
                                                       route, code):
    """L'autre moitié : une garde qui refuse tout est une panne."""
    entreprise = _entreprise(f'avec-{code}', codes=(code,), actif=True)
    _connecte(client, django_user_model, entreprise, f'avec-{code}-user',
              superadmin=False)

    reponse = client.get(reverse(route))
    assert reponse.status_code == 200


# ── 4. On y arrive depuis l'interface ─────────────────────────────────────

def test_la_navigation_mene_aux_trois_modules():
    from apps.core.context_processors import NAV_MODULES

    def noms(entrees):
        rendu = set()
        for e in entrees:
            if not isinstance(e, dict):
                continue
            if e.get('url_name'):
                rendu.add(e['url_name'])
            rendu |= noms(e.get('children') or [])
        return rendu

    cibles = noms(NAV_MODULES)
    for attendu in ('site_customization:dashboard', 'domain_manager:list',
                    'orders:order_list'):
        assert attendu in cibles, f'Aucune entrée de menu vers {attendu}.'
