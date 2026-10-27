"""Les trois listes de modules doivent dire la même chose.

L'activation d'un module repose sur une chaîne de quatre pièces :

1. `ALL_MODULE_CODES` (private_saas/models.py) — `seed_company_modules`
   **boucle sur elle** pour créer les lignes `CompanyModule` ;
2. `DEFAULT_COMPANY_MODULES` (private_saas/module_access.py) — ceux qui
   sont actifs à la création d'une entreprise ;
3. `MODULE_LABELS` et `MODULE_NAV_IDS` — le nom affiché et les entrées de
   menu que le module commande ;
4. `require_company_module('code')` dans les vues — la garde.

**Le défaut que ce fichier empêche de revenir.** Ces listes vivent dans
deux fichiers et personne ne les comparait. `DEFAULT_COMPANY_MODULES`
réclamait **treize** codes absents de `ALL_MODULE_CODES`, et
`seed_company_modules` les ignorait en silence : aucune ligne créée, donc
`require_company_module` refusant toujours.

Mesuré : 28 vues de `work_planning`, 22 d'`internal_training`, 15 de
`site_customization` et 4 d'`orders` étaient inaccessibles **par
construction**. Rien ne le signalait — juste « module non activé », ce qui
ressemble à un réglage à cocher et non à un défaut.

Aucun test unitaire ne pouvait le voir : chaque fichier était cohérent
avec lui-même, et le désaccord vivait **entre** eux. C'est la même forme
de défaut que la clef de session 2FA que personne n'écrivait.
"""

import os
import re

import pytest

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MOTIF_GARDE = re.compile(r"require_company_module\(\s*['\"]([a-z_]+)['\"]")


def _codes_gardes_dans_le_code():
    """Les codes réellement exigés par un décorateur, lus dans les sources.

    Lus et non listés à la main : une liste écrite ici vieillirait, et
    c'est précisément le genre d'oubli que ce fichier doit attraper.
    """
    trouves = {}
    for dossier, sous, fichiers in os.walk(os.path.join(RACINE, 'apps')):
        sous[:] = [s for s in sous
                   if s not in ('__pycache__', 'migrations', '.claude')]
        for nom in fichiers:
            if not nom.endswith('.py'):
                continue
            chemin = os.path.join(dossier, nom)
            with open(chemin, encoding='utf-8', errors='replace') as fichier:
                for code in MOTIF_GARDE.findall(fichier.read()):
                    trouves.setdefault(code, []).append(
                        os.path.relpath(chemin, RACINE))
    return trouves


# ── 1. Le défaut mesuré ────────────────────────────────────────────────────

def test_les_modules_par_defaut_existent_tous():
    """LE test du défaut : DEFAULT doit être un sous-ensemble de ALL.

    `seed_company_modules` boucle sur ALL_MODULE_CODES. Un code présent
    dans DEFAULT et absent de ALL ne produit aucune ligne CompanyModule :
    il est ignoré sans un mot, et le module reste inactivable.
    """
    from apps.private_saas.models import ALL_MODULE_CODES
    from apps.private_saas.module_access import DEFAULT_COMPANY_MODULES

    fantomes = sorted(set(DEFAULT_COMPANY_MODULES) - set(ALL_MODULE_CODES))

    assert not fantomes, (
        'Ces codes sont demandés par DEFAULT_COMPANY_MODULES et absents de '
        'ALL_MODULE_CODES. seed_company_modules les ignorera en silence et '
        'require_company_module refusera toujours :\n  '
        + '\n  '.join(fantomes))


def test_chaque_garde_de_vue_repose_sur_un_code_reconnu():
    """Le test qui aurait attrapé le défaut, du côté des vues.

    Une garde posée sur un code inconnu de ALL_MODULE_CODES rend sa vue
    inaccessible pour toujours, et l'écran affiche « module non activé » —
    indiscernable d'un module simplement non souscrit.
    """
    from apps.private_saas.models import ALL_MODULE_CODES

    connus = set(ALL_MODULE_CODES)
    gardes = _codes_gardes_dans_le_code()

    assert gardes, 'Aucune garde trouvée : le test ne mesurerait rien.'

    inconnus = {code: fichiers for code, fichiers in gardes.items()
                if code not in connus}

    details = []
    for code in sorted(inconnus):
        fichiers = sorted(set(inconnus[code]))
        details.append(f'{code} ({len(inconnus[code])} garde(s)) '
                       f'— ex. {fichiers[0]}')

    assert not inconnus, (
        'Ces codes gardent des vues et ne figurent pas dans '
        'ALL_MODULE_CODES : ces vues sont inaccessibles par '
        'construction.\n  ' + '\n  '.join(details))


# ── 2. Les listes d'affichage ─────────────────────────────────────────────

def test_chaque_module_a_un_libelle():
    """Sans libellé, la case à cocher s'affiche avec son code technique."""
    from apps.private_saas.models import ALL_MODULE_CODES, MODULE_LABELS

    manquants = sorted(set(ALL_MODULE_CODES) - set(MODULE_LABELS))
    assert not manquants, (
        'Modules sans libellé lisible : ' + ', '.join(manquants))


def test_chaque_module_a_une_entree_de_navigation():
    """Même vide, l'entrée doit EXISTER.

    `MODULE_NAV_IDS.get(code)` rendrait None pour un code absent, ce qui ne
    se distingue pas d'une liste vide volontaire — un module qui ne
    commande aucun menu. La différence compte : l'une est une décision,
    l'autre un oubli.
    """
    from apps.private_saas.models import ALL_MODULE_CODES, MODULE_NAV_IDS

    manquants = sorted(set(ALL_MODULE_CODES) - set(MODULE_NAV_IDS))
    assert not manquants, (
        'Modules sans entrée dans MODULE_NAV_IDS : ' + ', '.join(manquants))


def test_aucun_libelle_ni_nav_orphelin():
    """L'inverse : un libellé pour un code qui n'existe plus est un reste.

    Inoffensif, mais trompeur à la lecture — on croit le module géré.
    """
    from apps.private_saas.models import (
        ALL_MODULE_CODES, MODULE_LABELS, MODULE_NAV_IDS)

    connus = set(ALL_MODULE_CODES)
    assert not sorted(set(MODULE_LABELS) - connus), (
        'Libellés sans code correspondant : '
        + ', '.join(sorted(set(MODULE_LABELS) - connus)))
    assert not sorted(set(MODULE_NAV_IDS) - connus), (
        'Entrées de navigation sans code correspondant : '
        + ', '.join(sorted(set(MODULE_NAV_IDS) - connus)))


def test_les_identifiants_de_navigation_existent_vraiment():
    """Un identifiant de menu inventé masque le module au lieu de le montrer.

    `MODULE_NAV_IDS` désigne des entrées de `NAV_MODULES` par leur `id`.
    Un identifiant qui ne correspond à rien ne lève aucune erreur : le
    module s'active, et son menu n'apparaît pas.
    """
    from apps.core.context_processors import NAV_MODULES
    from apps.private_saas.models import MODULE_NAV_IDS

    def tous_les_ids(entrees):
        rendu = set()
        for entree in entrees:
            if isinstance(entree, dict):
                if entree.get('id'):
                    rendu.add(entree['id'])
                rendu |= tous_les_ids(entree.get('children') or [])
        return rendu

    existants = tous_les_ids(NAV_MODULES)
    assert existants, 'Aucun identifiant de menu lu : test sans valeur.'

    inventes = []
    for code, identifiants in MODULE_NAV_IDS.items():
        for identifiant in identifiants:
            if identifiant not in existants:
                inventes.append(f'{code} → {identifiant}')

    assert not inventes, (
        'Ces identifiants de navigation ne correspondent à aucune entrée de '
        'NAV_MODULES : le module s\'activerait sans que son menu '
        'apparaisse.\n  ' + '\n  '.join(inventes))


# ── 3. La preuve que les gardes mordent ──────────────────────────────────

@pytest.mark.django_db
def test_un_module_reconnu_produit_bien_une_ligne():
    """Sans celui-ci, tous les tests ci-dessus pourraient passer sur des
    listes cohérentes mais inertes.

    On sème les modules d'une entreprise neuve et on vérifie que chaque
    code par défaut a bien reçu sa ligne, active.
    """
    from apps.core.models import Company
    from apps.private_saas.models import CompanyModule
    from apps.private_saas.module_access import (
        DEFAULT_COMPANY_MODULES, seed_company_modules)

    entreprise = Company.objects.create(name='Semis SA', slug='semis-sa')
    seed_company_modules(entreprise)

    actifs = set(CompanyModule.objects.filter(
        company=entreprise, is_enabled=True).values_list(
            'module_code', flat=True))

    assert set(DEFAULT_COMPANY_MODULES) <= actifs, (
        'Ces modules par défaut n\'ont pas été activés : '
        + ', '.join(sorted(set(DEFAULT_COMPANY_MODULES) - actifs)))


@pytest.mark.django_db
def test_les_quatre_modules_dormants_peuvent_desormais_s_activer():
    """La régression nommée, pour que l'échec se lise sans enquête.

    Ces quatre codes gardent 69 vues à eux quatre. Avant correction, ils
    étaient absents de ALL_MODULE_CODES : aucune ligne, aucune activation
    possible, et 69 vues mortes.
    """
    from apps.core.models import Company
    from apps.private_saas.models import CompanyModule
    from apps.private_saas.module_access import seed_company_modules

    entreprise = Company.objects.create(name='Dormants SA',
                                        slug='dormants-sa')
    seed_company_modules(entreprise)

    attendus = {'work_planning', 'internal_training', 'site_customization',
                'orders'}
    presents = set(CompanyModule.objects.filter(
        company=entreprise, module_code__in=attendus).values_list(
            'module_code', flat=True))

    assert presents == attendus, (
        'Modules sans ligne CompanyModule, donc inactivables : '
        + ', '.join(sorted(attendus - presents)))
