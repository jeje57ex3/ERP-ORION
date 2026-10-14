"""Bascule les réglages DÉJÀ EN BASE vers le fournisseur local.

La migration précédente ne faisait qu'AddField et AlterField : elle a changé
les valeurs par défaut des NOUVELLES lignes, pas celles déjà enregistrées. Sur
toute installation existante, la ligne de réglages gardait donc
`default_provider='openai'` et `default_model='gpt-4.1-mini'`, tout en
recevant `local_only=True` — l'état le plus mauvais possible : verrouillé en
local mais configuré sur un fournisseur externe, combinaison que
`get_ai_provider` refuse. L'assistant devenait inutilisable, et la page de
paramètres continuait d'afficher GPT.

Une valeur par défaut ne rattrape jamais les lignes existantes. C'est ce que
cette migration fait, explicitement.

Prudence sur ce qui est réécrit : seuls les modèles reconnaissables comme
externes sont remplacés, et seul le nom exactement égal à l'ancien défaut est
renommé. Un modèle ou un nom choisi délibérément par l'exploitant est
conservé.
"""

from django.db import migrations

MODELE_LOCAL = 'qwen2.5:3b-instruct'
FOURNISSEURS_EXTERNES = ('openai', 'anthropic')

# Préfixes des modèles manifestement externes. Un modèle servi par Ollama
# porte un nom de la forme « famille:taille », sans rapport avec ceux-ci.
PREFIXES_EXTERNES = ('gpt-', 'gpt4', 'o1-', 'o3-', 'claude-', 'text-davinci')

ANCIEN_NOM = 'Assistant Orion'
NOUVEAU_NOM = 'Orion'


def basculer_en_local(apps, schema_editor):
    Reglages = apps.get_model('orion_ai', 'OrionAISettings')

    for reglages in Reglages.objects.all():
        champs = []

        if reglages.local_only and reglages.default_provider in FOURNISSEURS_EXTERNES:
            reglages.default_provider = 'local'
            champs.append('default_provider')

            modele = (reglages.default_model or '').lower()
            if any(modele.startswith(p) for p in PREFIXES_EXTERNES):
                reglages.default_model = MODELE_LOCAL
                champs.append('default_model')

        # Seul l'ancien défaut exact est renommé : un nom choisi par
        # l'exploitant lui appartient.
        if reglages.ai_name == ANCIEN_NOM:
            reglages.ai_name = NOUVEAU_NOM
            champs.append('ai_name')

        if champs:
            reglages.save(update_fields=champs)


def revenir(apps, schema_editor):
    """Irréversible, et le dire plutôt que de deviner.

    La valeur précédente n'est pas conservée : la restaurer supposerait de
    choisir un fournisseur externe au hasard, et donc d'exposer les données de
    l'entreprise à un tiers sans décision. On ne touche à rien.
    """
    return None


class Migration(migrations.Migration):

    dependencies = [
        ('orion_ai', '0002_orion_local_uniquement'),
    ]

    operations = [
        migrations.RunPython(basculer_en_local, revenir),
    ]
