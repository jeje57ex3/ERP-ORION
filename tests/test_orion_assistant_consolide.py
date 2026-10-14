"""Consolidation des deux assistants en un seul.

`orion_assistant` (`/assistant/`, deux modèles) et `orion_ai` (sept modèles)
offraient le même service, avec deux entrées « Assistant Orion » au menu et
deux historiques séparés — rien n'expliquait la différence à l'utilisateur, et
une conversation commencée d'un côté était introuvable de l'autre.

`orion_ai` étant un surensemble strict, le doublon a été retiré. Ces tests
gardent les trois propriétés qui rendent ce retrait sans conséquence pour
l'utilisateur : son adresse répond toujours, son historique a été repris, et le
menu ne propose plus qu'un seul assistant.
"""

import io
import os

import pytest
from django.conf import settings
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_l_ancienne_adresse_redirige_vers_le_nouveau_module(client_logged_in, company):
    """Des liens et des favoris portent déjà /assistant/ : l'adresse ne doit
    pas répondre 404 au prétexte que le module a changé de nom."""
    reponse = client_logged_in.get('/assistant/')

    assert reponse.status_code in (301, 302), reponse.status_code
    assert reponse['Location'].endswith(
        reverse('orion_ai:assistant_dashboard')
    ), reponse['Location']


def test_la_redirection_n_est_pas_permanente(client_logged_in, company):
    """Un 301 serait mis en cache par les navigateurs sans moyen de revenir
    dessus : si l'adresse doit resservir un jour, elle serait perdue.

    La fixture `company` n'est pas decorative : sans entreprise en base,
    SetupRequiredMiddleware renvoie TOUTE requete vers /setup/, en 302. Ce
    test passait alors sans jamais atteindre la redirection qu'il verifie --
    un faux succes, plus trompeur qu'un echec.
    """
    reponse = client_logged_in.get('/assistant/')
    assert reponse['Location'].endswith(
        reverse('orion_ai:assistant_dashboard')
    ), 'la redirection ne mene pas au nouveau module : %s' % reponse['Location']
    assert reponse.status_code == 302, (
        'redirection permanente (301) : impossible à reprendre ensuite'
    )


def test_l_ancien_module_ne_declare_plus_aucun_modele():
    """Ses deux tables sont supprimées par orion_assistant.0002 ; un modèle
    encore déclaré ferait réapparaître la table au prochain makemigrations."""
    from django.apps import apps as registre

    modeles = registre.get_app_config('orion_assistant').get_models()
    assert list(modeles) == []


def test_l_ancien_module_garde_ses_migrations():
    """Les retirer laisserait les deux tables en place indéfiniment sur les
    installations existantes, et rendrait incohérent django_migrations."""
    dossier = os.path.join(
        settings.BASE_DIR, 'apps', 'orion_assistant', 'migrations')
    fichiers = sorted(
        nom for nom in os.listdir(dossier)
        if nom.endswith('.py') and nom != '__init__.py'
    )
    assert fichiers == [
        '0001_initial.py',
        '0002_supprimer_les_modeles_remplaces.py',
    ], fichiers


def test_la_suppression_depend_de_la_reprise():
    """L'ordre est la seule chose qui empêche la perte de l'historique : les
    tables ne doivent pas tomber avant d'avoir été lues."""
    chemin = os.path.join(
        settings.BASE_DIR, 'apps', 'orion_assistant', 'migrations',
        '0002_supprimer_les_modeles_remplaces.py')
    with io.open(chemin, encoding='utf-8') as fichier:
        contenu = fichier.read()
    assert "('orion_ai', '0004_reprendre_l_historique_de_orion_assistant')" \
        in contenu


def test_la_reprise_conserve_les_dates_d_origine():
    """auto_now_add écrase toute date fournie à la création : sans un update()
    qui contourne save(), tout l'historique repris paraîtrait daté du jour de
    la migration."""
    chemin = os.path.join(
        settings.BASE_DIR, 'apps', 'orion_ai', 'migrations',
        '0004_reprendre_l_historique_de_orion_assistant.py')
    with io.open(chemin, encoding='utf-8') as fichier:
        contenu = fichier.read()
    assert 'created_at=ancienne.created_at' in contenu
    assert 'updated_at=ancienne.updated_at' in contenu
    assert 'created_at=ancien_message.created_at' in contenu


def test_la_reprise_est_idempotente():
    """Une migration de données peut être rejouée (restauration, reprise d'un
    déploiement interrompu) : elle ne doit pas dupliquer l'historique."""
    chemin = os.path.join(
        settings.BASE_DIR, 'apps', 'orion_ai', 'migrations',
        '0004_reprendre_l_historique_de_orion_assistant.py')
    with io.open(chemin, encoding='utf-8') as fichier:
        contenu = fichier.read()
    assert 'deja_reprises' in contenu
    # Et elle doit survivre à une installation neuve, où l'ancien module n'a
    # jamais existé.
    assert 'except LookupError' in contenu


def test_le_menu_ne_propose_qu_un_seul_assistant():
    """Deux entrées menant au même service, c'est un défaut visible par
    l'utilisateur — et c'était le symptôme du doublon."""
    from apps.core import context_processors

    entrees = []
    for groupe in context_processors.NAV_MODULES:
        for entree in groupe.get('children', []) or []:
            cible = entree.get('url_name', '')
            if cible.startswith('orion_assistant:'):
                entrees.append(cible)
    assert entrees == [], (
        'le menu pointe encore vers le module retiré : %s' % entrees
    )
