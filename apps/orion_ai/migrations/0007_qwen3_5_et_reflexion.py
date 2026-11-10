# -*- coding: utf-8 -*-
"""Qwen3.5 devient le modèle local par défaut, et la réflexion est coupée.

DEUX CHANGEMENTS DE SCHÉMA, ET UNE ABSENCE ASSUMÉE.

Le nom par défaut passe de `qwen2.5:3b-instruct` à `qwen3.5:4b-q4_K_M`. Il ne
se déduit pas de l'ancien : qwen3.5 a abandonné le suffixe « -instruct » et
n'a pas de taille « 3b » (ses tailles sont 0.8b, 2b, 4b, 9b). Un simple
remplacement de « 2.5 » par « 3.5 » aurait produit un nom qui n'existe pas, et
Ollama répond 404 sur chaque question pour un nom inconnu.

`local_thinking` arrive à FAUX. Qwen3.5 sait raisonner avant de répondre, et
ses jetons de réflexion sont pris sur le plafond de génération : à 600 jetons,
un modèle qui réfléchit peut les dépenser entièrement et renvoyer une réponse
vide. Le défaut inverse serait donc un assistant muet sur une machine lente.

CE QUE CETTE MIGRATION NE FAIT PAS, ET POURQUOI.

Elle ne renomme AUCUNE ligne existante. C'est l'inverse de la migration 0003,
qui réécrivait les réglages en base, et le choix est délibéré : une valeur par
défaut ne décrit qu'un souhait, alors qu'un nom de modèle en base décrit un
FICHIER PRÉSENT SUR LE DISQUE.

Renommer la ligne pendant la mise à jour aurait fait pointer l'assistant vers
un modèle non téléchargé — le téléchargement fait plusieurs gigaoctets et ne
peut pas se produire pendant un `migrate`. L'assistant aurait donc échoué à
chaque question immédiatement après une mise à jour réussie, et la cause
— « le modèle a changé de nom tout seul » — serait la dernière qu'on irait
chercher.

Le changement de modèle reste donc une décision d'exploitant, prise dans
`Paramètres IA`, où la liste des modèles réellement présents sur le serveur
est désormais affichée, et où un nom absent du disque est signalé en rouge.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('orion_ai', '0006_trace_de_suppression_de_conversation'),
    ]

    operations = [
        migrations.AlterField(
            model_name='orionaisettings',
            name='default_model',
            field=models.CharField(
                default='qwen3.5:4b-q4_K_M',
                help_text='Modele servi par Ollama sur ce serveur.',
                max_length=120,
            ),
        ),
        migrations.AddField(
            model_name='orionaisettings',
            name='local_thinking',
            field=models.BooleanField(
                default=False,
                help_text='Améliore les réponses aux questions de '
                          'raisonnement, au prix d’un temps d’attente bien '
                          'plus long — la réflexion ne s’affiche pas, et ses '
                          'jetons sont pris sur la longueur maximale de la '
                          'réponse. À n’activer que si le débit mesuré par '
                          '« orion-ai.sh bench » est confortable.',
                verbose_name='Laisser le modèle réfléchir avant de répondre',
            ),
        ),
    ]
