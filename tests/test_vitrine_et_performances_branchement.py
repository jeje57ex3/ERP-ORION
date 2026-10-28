"""Les deux dernières applications dormantes : vitrine et performances.

`apps.orion_website` est le site vitrine **public** du produit : onze
pages, treize gabarits, aucun modèle, aucune garde. Il n'était déclaré ni
dans `INSTALLED_APPS` ni dans les URLs — donc `/orion/telechargements/`,
`/orion/install/windows/`, `/orion/install/android/` et
`/orion/install/apple/` répondaient toutes 404. **Personne ne pouvait
récupérer l'application de bureau ni l'application mobile.**

`apps.performance_monitor` enregistre des mesures de performance
(`PerformanceEvent`) et les affiche à l'équipe technique.

Ce sont les deux seules de la série à ne pas être des modules
d'entreprise : la vitrine est publique par nature, et le moniteur est
réservé à l'équipe par `@staff_member_required`. Il n'y a donc pas de code
module à déclarer, et les tests portent sur l'accès — public d'un côté,
réservé de l'autre.
"""

import os

import pytest
from django.urls import reverse

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@pytest.fixture
def installation_faite(db):
    """Une entreprise existe, donc l'assistant de premier accès est passé.

    `SetupRequiredMiddleware` renvoie TOUT vers `/setup/` tant qu'aucune
    `Company` n'existe en base. Mes premiers tests l'avaient oublié et
    accusaient la vitrine de rediriger : c'est l'installation qui n'était
    pas faite.

    Ce comportement est le bon sur une appliance auto-hébergée — avant
    l'installation, il n'y a pas de visiteur à accueillir — et il n'est
    donc pas corrigé mais pris en compte.
    """
    from apps.core.models import Company

    return Company.objects.create(name='Vitrine SA', slug='vitrine-sa')


PAGES_PUBLIQUES = [
    'home',
    'modules',
    'apps',
    'downloads',
    'install_windows',
    'install_android',
    'install_apple',
    'security',
    'faq',
    'contact',
]


# ── 1. Les applications sont chargées ──────────────────────────────────────

@pytest.mark.parametrize('nom', ['apps.orion_website',
                                 'apps.performance_monitor'])
def test_l_application_est_enregistree(nom):
    from django.apps import apps

    assert apps.is_installed(nom)


def test_le_modele_de_mesure_est_connu():
    from django.apps import apps

    noms = {m.__name__
            for m in apps.get_app_config('performance_monitor').get_models()}
    assert 'PerformanceEvent' in noms


def test_la_migration_du_moniteur_existe_sur_le_disque():
    dossier = os.path.join(RACINE, 'apps', 'performance_monitor',
                           'migrations')
    fichiers = [f for f in os.listdir(dossier)
                if f.endswith('.py') and f != '__init__.py']
    assert fichiers, 'Aucune migration : la table des mesures n existera pas.'


def test_la_vitrine_n_a_deliberement_aucun_modele():
    """Sans ce test, l'absence de migration ressemblerait à un oubli."""
    from django.apps import apps

    assert list(apps.get_app_config('orion_website').get_models()) == []


# ── 2. La vitrine est publique ─────────────────────────────────────────────

@pytest.mark.django_db
@pytest.mark.parametrize('nom', PAGES_PUBLIQUES)
def test_chaque_page_de_la_vitrine_s_affiche_sans_compte(
        client, installation_faite, nom):
    """Public signifie SANS être connecté, et c'est tout l'enjeu ici.

    Un visiteur qui vient télécharger l'application n'a pas de compte. Si
    ces pages exigeaient une connexion, elles seraient aussi inutiles que
    lorsqu'elles répondaient 404.
    """
    reponse = client.get(reverse(f'orion_website:{nom}'))
    assert reponse.status_code == 200, (
        f'orion_website:{nom} rend {reponse.status_code}')


@pytest.mark.django_db
def test_les_pages_d_installation_sont_bien_atteignables(
        client, installation_faite):
    """La régression nommée : c'est par là qu'on récupère les applications.

    Ces quatre adresses répondaient 404 tant que l'application n'était pas
    montée, et aucun message ne l'expliquait — juste une page introuvable.
    """
    for nom in ('downloads', 'install_windows', 'install_android',
                'install_apple'):
        reponse = client.get(reverse(f'orion_website:{nom}'))
        assert reponse.status_code == 200, f'{nom} rend {reponse.status_code}'


@pytest.mark.django_db
def test_le_detail_d_un_module_s_affiche(client, installation_faite):
    """Route a argument libre : elle doit tenir sur un code inconnu.

    `module_detail` prend un code module en chaine. Un code inexistant
    doit rendre une page ou un 404 propre, et non une erreur serveur.
    """
    reponse = client.get(reverse('orion_website:module_detail',
                                 args=['crm']))
    assert reponse.status_code in (200, 404)


@pytest.mark.django_db
def test_un_code_de_module_inconnu_ne_casse_pas_la_page(
        client, installation_faite):
    reponse = client.get(reverse('orion_website:module_detail',
                                 args=['module-qui-nexiste-pas']))
    assert reponse.status_code in (200, 404), (
        f'Un code inconnu rend {reponse.status_code} : la page devrait '
        f'gerer le cas plutot que lever.')


def test_l_adresse_de_la_vitrine_ne_collisionne_pas_avec_l_administration():
    """« orion/ » et « orion-admin/ » sont deux segments distincts.

    Ils se ressemblent assez pour qu'on s'en inquiete ; ce test mesure que
    la vitrine ne capte pas les adresses d'administration.
    """
    from django.urls import resolve

    assert resolve('/orion/').app_name == 'orion_website'
    assert resolve('/orion-admin/').app_name != 'orion_website'


# ── 3. Le moniteur est réservé à l'équipe ─────────────────────────────────

@pytest.mark.django_db
def test_le_moniteur_s_affiche_pour_un_membre_de_l_equipe(client,
                                                          django_user_model):
    from apps.accounts.models import UserProfile
    from apps.core.models import Company

    entreprise = Company.objects.create(name='Perf SA', slug='perf-sa')
    utilisateur = django_user_model.objects.create_user(
        'technicien', password='x', is_staff=True, is_superuser=True)
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.role = 'superadmin'
    profil.save()
    profil.companies.add(entreprise)

    client.force_login(django_user_model.objects.get(pk=utilisateur.pk))
    session = client.session
    session['current_company_id'] = entreprise.pk
    session.save()

    reponse = client.get(reverse('performance_monitor:dashboard'))
    assert reponse.status_code == 200


@pytest.mark.django_db
def test_le_moniteur_refuse_un_utilisateur_ordinaire(client,
                                                     django_user_model):
    """Ces mesures renseignent sur l'infrastructure, pas sur une entreprise."""
    from apps.accounts.models import UserProfile
    from apps.core.models import Company

    entreprise = Company.objects.create(name='Perf Autre', slug='perf-autre')
    utilisateur = django_user_model.objects.create_user('simple', password='x')
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.companies.add(entreprise)
    client.force_login(django_user_model.objects.get(pk=utilisateur.pk))

    reponse = client.get(reverse('performance_monitor:dashboard'))
    assert reponse.status_code in (302, 403)


@pytest.mark.django_db
def test_le_moniteur_refuse_un_visiteur_anonyme(client, installation_faite):
    reponse = client.get(reverse('performance_monitor:dashboard'))
    assert reponse.status_code in (302, 403)


def test_la_navigation_mene_au_moniteur():
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

    assert 'performance_monitor:dashboard' in noms(NAV_MODULES)


# ── 4. Plus aucune application dormante ───────────────────────────────────

def test_aucune_application_ne_reste_dormante():
    """Le test qui clôt la série, et qui tient la porte fermée.

    Huit applications étaient sur le disque sans être déclarées. Une
    application non enregistrée est du code inerte : ses modèles ne se
    définissent même pas, ses tests ne peuvent pas tourner, et rien ne le
    signale — il faut compter les dossiers pour s'en apercevoir.

    Ce test échoue désormais dès qu'un dossier d'application apparaît sans
    être déclaré. Il n'interdit pas d'en ajouter une : il interdit de
    l'oublier.
    """
    from django.apps import apps as registre

    enregistrees = {c.name.split('.')[-1] for c in registre.get_app_configs()
                    if c.name.startswith('apps.')}

    dossier_apps = os.path.join(RACINE, 'apps')
    sur_le_disque = {
        nom for nom in os.listdir(dossier_apps)
        if os.path.isdir(os.path.join(dossier_apps, nom))
        and os.path.isfile(os.path.join(dossier_apps, nom, '__init__.py'))
    }

    dormantes = sorted(sur_le_disque - enregistrees)

    assert not dormantes, (
        'Ces applications sont sur le disque et absentes '
        'd INSTALLED_APPS. Leur code est inerte : les modeles ne se '
        'definissent pas, les tests ne tournent pas, et les vues sont '
        'injoignables.\n  ' + '\n  '.join(dormantes))


# -- 5. Le lien Android absent, tolere plutot que fatal --------------------


def test_le_lien_android_rend_none_sans_le_module():
    """`apps.mobile_app` n'existe pas, et la page doit tenir quand meme.

    La vue importait `apps.mobile_app.models.MobileRelease` : ni ce
    module, ni ce modele, ni la route /mobile/telecharger/ n'existent dans
    le projet. L'application n'etant pas declaree, cet import n'avait
    jamais ete execute -- la page des telechargements levait
    ModuleNotFoundError des la premiere visite.

    L'import est tolere plutot que supprime : le gabarit sait deja
    afficher « Bientot disponible », et le lien reapparaitra de lui-meme
    le jour ou ce module existera.
    """
    from apps.orion_website.views import _lien_de_telechargement_android

    assert _lien_de_telechargement_android() is None


@pytest.mark.django_db
def test_la_page_annonce_le_mobile_comme_a_venir(client, installation_faite):
    """Le symptome vu par le visiteur, et non seulement la fonction.

    Sans lien, la carte Android doit annoncer « Bientot disponible » et
    non proposer un bouton mort.
    """
    reponse = client.get(reverse('orion_website:downloads'))

    assert reponse.status_code == 200
    contenu = reponse.content.decode()
    assert 'Bient' in contenu
    assert '/mobile/telecharger/' not in contenu


# -- 6. Le garde du moniteur, aligne sur celui de ses voisines -------------


@pytest.mark.django_db
def test_un_super_admin_sans_drapeau_equipe_accede_au_moniteur(
        client, django_user_model, installation_faite):
    """LE test du defaut : cette page seule resistait a un super-admin.

    Elle employait `staff_member_required`, qui exige `is_staff`, alors que
    TOUTES ses voisines du menu Super Admin exigent `is_superuser`. Un
    super-administrateur sans le drapeau « equipe » se voyait refuser cette
    page et cette page seulement.

    Pire : en cas de refus, `staff_member_required` redirige vers
    `admin:login` -- la connexion de l'admin Django -- au lieu de ramener au
    tableau de bord avec un message. D'ou l'impression d'une page cassee
    plutot que d'un acces refuse.

    Le compte de ce test est donc deliberement is_superuser SANS is_staff.
    """
    from apps.accounts.models import UserProfile

    utilisateur = django_user_model.objects.create_user(
        'patron-sans-equipe', password='x', is_superuser=True, is_staff=False)
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.role = 'superadmin'
    profil.save()
    profil.companies.add(installation_faite)

    client.force_login(django_user_model.objects.get(pk=utilisateur.pk))
    session = client.session
    session['current_company_id'] = installation_faite.pk
    session.save()

    reponse = client.get(reverse('performance_monitor:dashboard'))
    assert reponse.status_code == 200, (
        f'Un super-administrateur sans is_staff recoit '
        f'{reponse.status_code} sur la page des performances.')


@pytest.mark.django_db
def test_un_refus_ne_renvoie_pas_vers_la_connexion_de_l_admin(
        client, django_user_model, installation_faite):
    """Un acces refuse doit le DIRE, pas deguiser la page en panne.

    `staff_member_required` renvoyait vers /admin/login/, ce qui ressemble
    a un dysfonctionnement. `super_admin_required` ramene au tableau de
    bord avec un message explicite.
    """
    from apps.accounts.models import UserProfile

    utilisateur = django_user_model.objects.create_user('simple-perf',
                                                        password='x')
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.companies.add(installation_faite)
    client.force_login(django_user_model.objects.get(pk=utilisateur.pk))

    reponse = client.get(reverse('performance_monitor:dashboard'))

    assert reponse.status_code == 302
    assert '/admin/login' not in reponse['Location'], (
        'Le refus renvoie vers la connexion de l admin Django : '
        'indiscernable d une page cassee.')
