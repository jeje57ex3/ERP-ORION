"""Module remplace par `orion_ai`.

`orion_assistant` offrait un assistant conversationnel (deux modeles) et
`orion_ai` un surensemble strict : memes conversations et memes messages, plus
les appels d'outils, les actions proposees, la memoire, le journal d'audit et
les reglages. Deux entrees « Assistant Orion » figuraient au menu, menant a
deux historiques separes sans que rien n'explique la difference.

Il ne reste ici que l'historique des migrations, et c'est voulu :
orion_assistant.0002 supprime les deux tables, apres que
orion_ai.0004 en a repris le contenu. Retirer l'application du code sans
conserver ces migrations laisserait ces tables en place indefiniment sur les
installations existantes, et rendrait incoherents les enregistrements de
django_migrations.

L'adresse /assistant/ reste servie, en redirection vers le nouveau module
(voir erp_btp/urls.py).
"""
