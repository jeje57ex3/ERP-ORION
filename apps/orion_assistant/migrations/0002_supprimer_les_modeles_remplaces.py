"""Retire les deux modèles remplacés par `orion_ai`.

L'historique a été repris juste avant par
orion_ai.0004_reprendre_l_historique_de_orion_assistant, dont cette migration
dépend explicitement : sans cet ordre, les tables seraient supprimées avant
d'avoir été lues, et les conversations déjà tenues perdues sans retour.

L'application reste déclarée dans INSTALLED_APPS, réduite à ses migrations.
Ce n'est pas un oubli : Django a besoin de retrouver cet historique pour que
les enregistrements de django_migrations restent cohérents, et c'est ce qui
garantit que les anciennes tables sont bien supprimées sur les installations
existantes — les retirer du code sans cette migration les y laisserait
indéfiniment.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('orion_assistant', '0001_initial'),
        # L'historique doit avoir été repris AVANT toute suppression.
        ('orion_ai', '0004_reprendre_l_historique_de_orion_assistant'),
    ]

    operations = [
        # Le message d'abord : sa clé étrangère pointe vers la conversation.
        migrations.DeleteModel(name='AssistantMessage'),
        migrations.DeleteModel(name='AssistantConversation'),
    ]
