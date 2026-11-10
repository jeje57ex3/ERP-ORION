# -*- coding: utf-8 -*-
"""« À jour » ne doit jamais vouloir dire « je n'ai pas pu savoir ».

RAPPORTÉ DEPUIS L'ÉCRAN : « le système me dit qu'il est à jour » — alors
que l'ERP servait du code vieux de plusieurs lots, et qu'un bouton livré
la veille n'apparaissait nulle part.

LA CHAÎNE. `check_for_updates` récupère bien le dépôt, et un échec de
`fetch` est correctement signalé. Mais ensuite :

    behind, ahead = get_commits_behind_ahead()
    check.status = 'update_available' if behind > 0 else 'up_to_date'

et `get_commits_behind_ahead` rendait **(0, 0)** dès que sa commande
échouait. Zéro commit de retard, donc à jour.

C'est la même faute que le script de mise à jour qui annonçait « schéma
migré » trois lignes sous un traceback MySQL : une incertitude rapportée
comme un succès. Elle coûte d'autant plus cher ici que la page sert
précisément à décider s'il faut agir — et qu'un « à jour » **dissuade
d'aller voir**.

Le second défaut est plus discret : la comparaison porte sur une branche
fixée par un réglage, alors que la mise à jour tire la branche SUIVIE par
le dépôt. Une machine sur « APPA » comparée à « main » peut se croire à
jour tout en recevant un autre code.
"""

import pytest

pytestmark = pytest.mark.django_db


def _preparer(monkeypatch, behind, ahead, branche='main',
              branche_reglee='main'):
    """Remplace les appels à git : ce sont eux qu'on simule, pas le dépôt."""
    from apps.system_updates import services

    monkeypatch.setattr(services, 'get_current_version', lambda: '1.0.0')
    monkeypatch.setattr(services, 'get_current_commit', lambda: 'abc1234')
    monkeypatch.setattr(services, 'get_current_branch', lambda: branche)
    monkeypatch.setattr(services, 'fetch_remote',
                        lambda: {'ok': True, 'stdout': '', 'stderr': ''})
    monkeypatch.setattr(services, 'get_remote_commit', lambda: 'def5678')
    monkeypatch.setattr(services, 'get_commits_behind_ahead',
                        lambda: (behind, ahead))
    monkeypatch.setattr(services, 'get_changelog', lambda: '')
    monkeypatch.setattr(
        'django.conf.settings.ORION_GIT_BRANCH', branche_reglee,
        raising=False)
    return services


# ─── Le défaut central ────────────────────────────────────────────────────

def test_une_comparaison_impossible_n_est_pas_un_succes(monkeypatch):
    """LE test. Avant, ce cas rendait « up_to_date »."""
    services = _preparer(monkeypatch, behind=None, ahead=None)

    check = services.check_for_updates()

    assert check.status == 'failed', (
        'ne pas savoir a ete rapporte comme etre a jour')
    assert 'Comparaison impossible' in check.error_message


def test_le_message_nomme_la_branche_suivie(monkeypatch):
    """Sans elle, on ne sait pas où chercher.

    C'est la première chose à vérifier quand la comparaison échoue : le
    dépôt peut suivre une branche qui n'est pas celle qu'on interroge.
    """
    services = _preparer(monkeypatch, behind=None, ahead=None,
                         branche='APPA', branche_reglee='APPA')

    check = services.check_for_updates()

    assert 'APPA' in check.error_message


def test_une_branche_suivie_differente_est_signalee(monkeypatch):
    """Comparer « main » quand la machine tire « APPA » ne dit rien d'utile.

    La réponse porterait sur autre chose que ce que la mise à jour
    installerait réellement — et elle serait rassurante.
    """
    services = _preparer(monkeypatch, behind=0, ahead=0,
                         branche='APPA', branche_reglee='main')

    check = services.check_for_updates()

    assert check.status == 'failed'
    assert 'APPA' in check.error_message
    assert 'main' in check.error_message


# ─── Et les cas normaux, qui doivent continuer de marcher ────────────────

def test_du_retard_annonce_une_mise_a_jour(monkeypatch):
    services = _preparer(monkeypatch, behind=3, ahead=0)

    check = services.check_for_updates()

    assert check.status == 'update_available'
    assert check.commits_behind == 3


def test_aucun_retard_annonce_a_jour(monkeypatch):
    services = _preparer(monkeypatch, behind=0, ahead=0)

    check = services.check_for_updates()

    assert check.status == 'up_to_date'


def test_un_fetch_en_echec_reste_un_echec(monkeypatch):
    """Ce cas-là était déjà correct : on vérifie qu'il le reste."""
    services = _preparer(monkeypatch, behind=0, ahead=0)
    monkeypatch.setattr(
        services, 'fetch_remote',
        lambda: {'ok': False, 'stdout': '', 'stderr': 'reseau injoignable'})

    check = services.check_for_updates()

    assert check.status == 'failed'
    assert 'reseau injoignable' in check.error_message


# ─── La fonction de comparaison elle-même ─────────────────────────────────

def _git_qui_repond(monkeypatch, ok, sortie=''):
    from apps.system_updates import git_service

    monkeypatch.setattr(
        git_service, 'run_command',
        lambda *a, **k: {'ok': ok, 'stdout': sortie, 'stderr': ''})
    return git_service


def test_une_commande_en_echec_rend_inconnu(monkeypatch):
    git_service = _git_qui_repond(monkeypatch, ok=False)

    assert git_service.get_commits_behind_ahead() == (None, None)


def test_une_sortie_malformee_rend_inconnu(monkeypatch):
    """Deux nombres étaient attendus ; tout le reste est une incertitude."""
    for sortie in ('', '3', '3 4 5', 'pas des nombres'):
        git_service = _git_qui_repond(monkeypatch, ok=True, sortie=sortie)
        assert git_service.get_commits_behind_ahead() == (None, None), sortie


def test_une_sortie_correcte_est_lue_dans_le_bon_sens(monkeypatch):
    """`--left-right --count` rend « avance retard » : l'ordre compte.

    Les inverser annoncerait une mise à jour disponible à chaque commit
    local, et aucune quand il y en a vraiment une.
    """
    git_service = _git_qui_repond(monkeypatch, ok=True, sortie='2\t5')

    behind, ahead = git_service.get_commits_behind_ahead()

    assert (behind, ahead) == (5, 2)
