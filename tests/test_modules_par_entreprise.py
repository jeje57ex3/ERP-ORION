"""« Activation des modules par entreprise ne fonctionne pas. »

LA CAUSE, MESURÉE

`private_saas.services.seed_company_modules` s'appelle « seed » et
RÉINITIALISAIT : son dernier bloc forçait chaque module à la valeur par
défaut du secteur, y compris pour les lignes déjà existantes.

Or la vue des modules l'appelle au début de CHAQUE requête. Le déroulé
était donc :

  1. POST  → réinitialisation aux défauts du secteur ;
  2.         puis la boucle applique les cases cochées — correctement ;
  3.         « Modules mis à jour. », redirection ;
  4. GET   → réinitialisation AUX DÉFAUTS, qui efface le choix qu'on vient
             d'enregistrer, avant même l'affichage.

Tout fonctionnait sauf la dernière étape, et c'est la seule qu'on voyait.
Reproduit : après un POST ne cochant que « btp », la liste active était
identique aux douze défauts du secteur.

UNE FAUSSE PISTE, GARDÉE ICI POUR QU'ON NE LA REPRENNE PAS

Le premier diagnostic accusait la vue de passer un secteur là où une liste
de modules est attendue. C'était faux : DEUX fonctions `seed_company_modules`
coexistent, dans services.py et dans module_access.py, avec des signatures
incompatibles. La vue importe celle de services.py, qui attend bien un type
d'entreprise. C'est la reproduction qui a détrompé l'analyse — elle montrait
douze modules actifs là où la théorie en prédisait zéro.
"""
import pytest


@pytest.fixture
def entreprise(db):
    from apps.core.models import Company
    return Company.objects.create(
        name='Volt SARL', slug='volt-sarl', sector='btp')


@pytest.fixture
def patron(db, django_user_model):
    return django_user_model.objects.create_superuser(
        username='patron', password='motdepasse-test', email='p@volt.fr')


def _actifs(entreprise):
    from apps.private_saas.models import CompanyModule
    return sorted(CompanyModule.objects
                  .filter(company=entreprise, is_enabled=True)
                  .values_list('module_code', flat=True))


# ── 1. Le semis ne doit plus écraser ─────────────────────────────────────────

@pytest.mark.django_db
def test_le_semis_cree_les_lignes_manquantes(entreprise):
    """Le chemin qui aboutit : semer reste utile, c'est écraser qui ne l'est
    pas. Sans lui, un code module nouvellement ajouté n'aurait aucune ligne
    pour les entreprises existantes."""
    from apps.private_saas.models import ALL_MODULE_CODES, CompanyModule
    from apps.private_saas.services import seed_company_modules

    seed_company_modules(entreprise, 'btp')
    assert CompanyModule.objects.filter(
        company=entreprise).count() == len(ALL_MODULE_CODES)


@pytest.mark.django_db
def test_le_semis_ne_defait_pas_un_choix_d_exploitant(entreprise):
    """LE CŒUR DE LA CORRECTION.

    Une ligne qui existe porte une décision prise dans l'interface. La
    réécrire en affichant une page revient à annuler cette décision sans
    rien dire.
    """
    from apps.private_saas.models import CompanyModule
    from apps.private_saas.services import seed_company_modules

    seed_company_modules(entreprise, 'btp')

    # L'exploitant coupe un module que le secteur active, et en active un
    # que le secteur ne prévoit pas.
    coupe = CompanyModule.objects.filter(
        company=entreprise, is_enabled=True).first()
    ajoute = CompanyModule.objects.filter(
        company=entreprise, is_enabled=False).first()
    coupe.disable()
    ajoute.enable()

    seed_company_modules(entreprise, 'btp')

    coupe.refresh_from_db()
    ajoute.refresh_from_db()
    assert coupe.is_enabled is False, (
        'un module coupé à la main a été rallumé par le semis')
    assert ajoute.is_enabled is True, (
        'un module activé à la main a été éteint par le semis')


@pytest.mark.django_db
def test_la_reinitialisation_reste_possible_mais_explicite(entreprise):
    """L'ancien comportement n'est pas supprimé, il devient un geste
    volontaire — pour qui veut vraiment remettre une entreprise aux défauts
    de son secteur."""
    from apps.private_saas.models import CompanyModule
    from apps.private_saas.services import seed_company_modules

    seed_company_modules(entreprise, 'btp')
    defauts = _actifs(entreprise)

    CompanyModule.objects.filter(company=entreprise).update(is_enabled=False)
    assert _actifs(entreprise) == []

    seed_company_modules(entreprise, 'btp', reinitialiser=True)
    assert _actifs(entreprise) == defauts


# ── 2. Le parcours réel, par la page ─────────────────────────────────────────

@pytest.mark.django_db
def test_cocher_un_module_l_active_vraiment(client, entreprise, patron):
    """LE SYMPTÔME RAPPORTÉ.

    On coche, on enregistre, et l'écran revient avec les défauts du
    secteur. Ce test suit exactement ce parcours, redirection comprise :
    c'est le GET d'après qui effaçait tout.
    """
    from apps.private_saas.module_access import company_has_module

    client.force_login(patron)
    url = f'/orion-admin/entreprises/{entreprise.pk}/modules/'
    client.get(url)

    reponse = client.post(url, {'module_btp': 'on', 'module_crm': 'on'},
                          follow=True)
    assert reponse.status_code == 200

    assert _actifs(entreprise) == ['btp', 'crm'], (
        'les cases cochées n’ont pas survécu à la redirection')
    assert company_has_module(entreprise, 'btp') is True
    assert company_has_module(entreprise, 'crm') is True


@pytest.mark.django_db
def test_decocher_un_module_le_desactive_vraiment(client, entreprise, patron):
    """La contrepartie : sans elle, un correctif qui n'activerait jamais
    rien passerait aussi le test précédent."""
    client.force_login(patron)
    url = f'/orion-admin/entreprises/{entreprise.pk}/modules/'
    client.get(url)

    client.post(url, {'module_btp': 'on', 'module_crm': 'on'}, follow=True)
    assert _actifs(entreprise) == ['btp', 'crm']

    client.post(url, {'module_btp': 'on'}, follow=True)
    assert _actifs(entreprise) == ['btp'], (
        'décocher n’a pas désactivé le module')


@pytest.mark.django_db
def test_le_choix_survit_a_un_simple_affichage(client, entreprise, patron):
    """Recharger la page ne doit rien changer. C'est précisément ce que
    faisait l'ancien semis."""
    client.force_login(patron)
    url = f'/orion-admin/entreprises/{entreprise.pk}/modules/'

    client.get(url)
    client.post(url, {'module_hr': 'on'}, follow=True)
    attendu = _actifs(entreprise)

    for _ in range(3):
        client.get(url)

    assert _actifs(entreprise) == attendu == ['hr']


@pytest.mark.django_db
def test_tout_decocher_est_possible(client, entreprise, patron):
    """Un formulaire sans aucune case cochée doit tout couper, et non être
    interprété comme « rien à faire »."""
    client.force_login(patron)
    url = f'/orion-admin/entreprises/{entreprise.pk}/modules/'
    client.get(url)

    client.post(url, {}, follow=True)
    assert _actifs(entreprise) == []


# ── 3. Un module activé doit se voir dans le menu ────────────────────────────

@pytest.mark.django_db
def test_un_module_active_apparait_dans_la_navigation(entreprise,
                                                       django_user_model):
    from apps.core.context_processors import NAV_MODULES
    from apps.private_saas.module_access import enable_company_module
    from apps.private_saas.permissions import filter_nav_modules

    salarie = django_user_model.objects.create_user(
        username='salarie', password='motdepasse-test', email='s@volt.fr')
    enable_company_module(entreprise, 'btp')

    visibles = [m['id'] for m in
                filter_nav_modules(NAV_MODULES, entreprise, user=salarie)]
    assert 'btp' in visibles


@pytest.mark.django_db
def test_les_sauvegardes_sont_enfin_gouvernees_par_un_module(
        entreprise, django_user_model):
    """L'entrée « Sauvegardes » n'était activée par AUCUN code module : sa
    liste était vide alors que « backups_module » existe. Elle restait donc
    invisible à un salarié quoi qu'on coche."""
    from apps.core.context_processors import NAV_MODULES
    from apps.private_saas.module_access import enable_company_module
    from apps.private_saas.permissions import filter_nav_modules

    salarie = django_user_model.objects.create_user(
        username='salarie', password='motdepasse-test', email='s@volt.fr')
    enable_company_module(entreprise, 'backups_module')

    visibles = [m['id'] for m in
                filter_nav_modules(NAV_MODULES, entreprise, user=salarie)]
    assert 'backups' in visibles


# Les entrées de menu qu'aucun code module ne gouverne encore.
#
# ON LES FIGE PLUTÔT QUE D'INVENTER DES CORRESPONDANCES. Décider quel module
# commande « Audio / AV » ou « Qualité & Conformité » est un choix de
# conception, pas une déduction : se tromper rendrait une section visible à
# des entreprises qui n'y ont pas droit. Cette liste empêche la situation
# d'empirer en silence, et chaque ligne retirée est un progrès.
ORPHELINS_CONNUS = {
    'audio',
    'competitor_intelligence',
    'lunea_beauty_profile',
    'qualite',
    # « siecle_creations » a quitte cette liste le 13/11/2026 : le module du
    # meme nom la gouverne desormais, et le menu peut enfin s'activer depuis
    # l'interface. Six orphelines restent.
    'smart',
    'support',
}


def test_aucune_nouvelle_entree_de_menu_sans_module():
    """Une entrée que rien n'active est invisible pour tout salarié.

    Le test ne demande pas que la liste soit vide — elle ne l'est pas — mais
    qu'elle ne GROSSISSE pas sans qu'on s'en aperçoive.
    """
    from apps.core.context_processors import NAV_MODULES
    from apps.private_saas.models import MODULE_NAV_IDS

    couverts = set()
    for identifiants in MODULE_NAV_IDS.values():
        couverts |= set(identifiants)
    toujours_visibles = {'dashboard', 'erp_overview', 'settings'}
    super_admin_only = {'private_saas'}

    orphelins = {
        module['id'] for module in NAV_MODULES
        if module['id'] not in couverts
        and module['id'] not in toujours_visibles
        and module['id'] not in super_admin_only
    }

    nouveaux = orphelins - ORPHELINS_CONNUS
    assert not nouveaux, (
        f'Entrée(s) de menu qu’aucun module n’active : {sorted(nouveaux)}. '
        f'Elles seront invisibles à tout salarié non super-admin. Ajoutez '
        f'leur identifiant à MODULE_NAV_IDS sous le code module qui doit '
        f'les gouverner.')

    reparés = ORPHELINS_CONNUS - orphelins
    assert not reparés, (
        f'Bonne nouvelle : {sorted(reparés)} sont désormais gouvernées par '
        f'un module. Retirez-les de ORPHELINS_CONNUS.')


# ── 4. Les deux homonymes ────────────────────────────────────────────────────

def test_les_deux_fonctions_homonymes_sont_signalees():
    """Elles ont déjà produit un diagnostic faux.

    Tant qu'elles coexistent avec des signatures incompatibles, chacune doit
    porter l'avertissement — passer un type d'entreprise à celle qui attend
    une liste parcourt la chaîne lettre par lettre et n'active rien, sans
    lever la moindre erreur.
    """
    import inspect

    from apps.private_saas import module_access, services

    par_liste = inspect.signature(module_access.seed_company_modules)
    par_type = inspect.signature(services.seed_company_modules)

    assert list(par_liste.parameters)[1] == 'enabled_modules'
    assert list(par_type.parameters)[1] == 'company_type'

    for fonction in (module_access.seed_company_modules,
                     services.seed_company_modules):
        assert 'HOMONYME' in (fonction.__doc__ or ''), (
            f'{fonction.__module__} ne signale plus l’homonyme')
