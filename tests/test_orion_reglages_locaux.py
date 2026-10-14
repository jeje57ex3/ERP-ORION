"""Bascule des réglages IA déjà en base vers le fournisseur local.

Une valeur par défaut ne rattrape **jamais** les lignes existantes. La
migration précédente ne faisait qu'`AddField` et `AlterField` : sur toute
installation existante, la ligne de réglages gardait « openai » et
« gpt-4.1-mini » tout en recevant `local_only=True` — verrouillée en local
mais configurée sur un fournisseur externe, combinaison que
`get_ai_provider` refuse. L'assistant devenait inutilisable, et la page de
paramètres continuait d'afficher GPT.
"""

import importlib

import pytest

pytestmark = pytest.mark.django_db

# Le module de migration commence par un chiffre : il n'est pas importable
# par la syntaxe normale, d'où importlib.
_MIGRATION = importlib.import_module(
    'apps.orion_ai.migrations.0003_basculer_les_reglages_existants_en_local'
)


def _basculer():
    """Rejoue la fonction de la migration sur l'état courant."""
    from django.apps import apps as registre

    _MIGRATION.basculer_en_local(registre, None)


def test_un_fournisseur_externe_verrouille_est_bascule_en_local():
    from apps.orion_ai.models import OrionAISettings

    reglages = OrionAISettings.objects.create(
        is_global=True, company=None,
        local_only=True, default_provider='openai',
        default_model='gpt-4.1-mini',
    )
    _basculer()
    reglages.refresh_from_db()

    assert reglages.default_provider == 'local'
    assert reglages.default_model == 'qwen2.5:3b-instruct'


def test_un_modele_local_deja_choisi_est_conserve():
    """Un modèle choisi par l'exploitant lui appartient."""
    from apps.orion_ai.models import OrionAISettings

    reglages = OrionAISettings.objects.create(
        is_global=True, company=None,
        local_only=True, default_provider='openai',
        default_model='mistral:7b-instruct',
    )
    _basculer()
    reglages.refresh_from_db()

    assert reglages.default_provider == 'local'
    assert reglages.default_model == 'mistral:7b-instruct'


def test_un_verrou_leve_n_est_pas_touche():
    """Qui a explicitement levé le verrou a décidé : on ne revient pas
    dessus."""
    from apps.orion_ai.models import OrionAISettings

    reglages = OrionAISettings.objects.create(
        is_global=True, company=None,
        local_only=False, default_provider='openai',
        default_model='gpt-4.1-mini',
    )
    _basculer()
    reglages.refresh_from_db()

    assert reglages.default_provider == 'openai'
    assert reglages.default_model == 'gpt-4.1-mini'


def test_l_ancien_nom_par_defaut_devient_orion():
    from apps.orion_ai.models import OrionAISettings

    reglages = OrionAISettings.objects.create(
        is_global=True, company=None, ai_name='Assistant Orion',
    )
    _basculer()
    reglages.refresh_from_db()
    assert reglages.ai_name == 'Orion'


def test_un_nom_personnalise_est_conserve():
    from apps.orion_ai.models import OrionAISettings

    reglages = OrionAISettings.objects.create(
        is_global=True, company=None, ai_name='Assistant Dupont',
    )
    _basculer()
    reglages.refresh_from_db()
    assert reglages.ai_name == 'Assistant Dupont'


def test_l_etat_contradictoire_ne_subsiste_pas():
    """La propriété qui compte : après bascule, aucun réglage verrouillé en
    local ne pointe vers un fournisseur externe."""
    from apps.orion_ai.models import OrionAISettings
    from apps.orion_ai.providers import FOURNISSEURS_EXTERNES

    OrionAISettings.objects.create(
        is_global=True, company=None,
        local_only=True, default_provider='anthropic',
        default_model='claude-3-5-sonnet',
    )
    _basculer()

    for reglages in OrionAISettings.objects.all():
        if reglages.local_only:
            assert reglages.default_provider not in FOURNISSEURS_EXTERNES


def test_le_fournisseur_devient_utilisable_apres_bascule():
    """Vérification de bout en bout : avant, `get_ai_provider` refusait."""
    from apps.orion_ai.models import OrionAISettings
    from apps.orion_ai.providers import AIProviderError, get_ai_provider

    reglages = OrionAISettings.objects.create(
        is_global=True, company=None,
        local_only=True, default_provider='openai',
        default_model='gpt-4.1-mini',
    )

    with pytest.raises(AIProviderError):
        get_ai_provider(reglages.default_provider, local_only=reglages.local_only)

    _basculer()
    reglages.refresh_from_db()
    assert get_ai_provider(reglages.default_provider, local_only=reglages.local_only)


def test_la_migration_est_declaree_irreversible_sans_deviner():
    """Restaurer supposerait de choisir un fournisseur externe au hasard, donc
    d'exposer les données de l'entreprise sans décision."""
    assert _MIGRATION.revenir(None, None) is None
