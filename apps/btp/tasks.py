# -*- coding: utf-8 -*-
"""Tâches de fond du module BTP.

Pour l'instant une seule : la purge de la corbeille des photos de chantier.
"""

from celery import shared_task


@shared_task(
    name='btp.purger_la_corbeille_photos',
    queue='maintenance',
)
def purger_la_corbeille_photos():
    """Détruit définitivement les photos à la corbeille depuis 14 jours.

    LA PURGE TOURNE AUSSI SANS CETTE TÂCHE, et c'est voulu : l'ouverture de
    l'écran de corbeille l'appelle également. La promesse faite à
    l'utilisateur — « supprimée définitivement au bout de deux semaines » —
    ne doit pas dépendre d'un planificateur que personne n'a configuré.

    Ce dépôt a déjà livré trois choses que rien n'activait : le middleware
    de performance, les règles sudo et l'assistant de préparation des
    disques. Une purge dans ce cas garderait les fichiers indéfiniment,
    pendant que l'écran afficherait « 0 jour restant ».

    Cette tâche-ci existe pour le cas inverse : une installation dont
    personne n'ouvre jamais la corbeille, et où les fichiers resteraient
    alors sur le disque sans que rien ne les reprenne. Les deux chemins se
    complètent ; aucun des deux ne suffit seul.

    À planifier depuis l'écran des tâches périodiques de l'ERP, une fois
    par jour. Elle est sans effet s'il n'y a rien à purger.
    """
    from apps.btp import services_photos

    return services_photos.purger_la_corbeille()
