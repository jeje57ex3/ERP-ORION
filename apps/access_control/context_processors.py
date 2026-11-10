"""
access_control/context_processors.py
Injecte les modules accessibles et permissions dans chaque template.
"""
from django.utils.functional import SimpleLazyObject

from .services import get_user_modules, get_user_sidebar_items


# POURQUOI CES TROIS VALEURS SONT DEVENUES PARESSEUSES
#
# Un processeur de contexte tourne a CHAQUE rendu de page. Celui-ci calculait
# ses trois variables immediatement, pour toutes les pages, qu'un gabarit les
# lise ou non.
#
# Compte des requetes SQL emises par les processeurs de contexte, mesure avec
# CaptureQueriesContext sur une base migree (et non estime) :
#
#     erp_context                        3 requetes
#     navigation_context                 1
#     brand_context                      0
#     available_modules                  8
#     current_company_permissions       72
#     ------------------------------------------
#     TOTAL avant que la vue ne demarre 84
#
# Le meme compte pour un superuser : 4. L'ecart vient des court-circuits de
# services.py (« if user.is_superuser: return True »), et il explique surtout
# pourquoi le defaut ne se voyait pas : l'exploitant qui essaie l'ERP est
# superuser, ses salaries ne le sont pas. Le ralentissement ne touchait donc
# que ceux qui ne peuvent pas le signaler utilement.
#
# Les 72 requetes de « perms_map » etaient integralement perdues : aucun
# gabarit, aucune vue, aucun test, aucun script ne lit cette variable --
# verifie sur tout le depot. Celles de « sidebar_items » aussi.
# « available_modules » n'est lu que par un seul gabarit,
# templates/notifications/notification_list.html.
#
# Et 8 est un PLANCHER, pas une valeur courante : le role mesure n'avait
# aucune permission, donc la boucle de get_user_sidebar_items n'a pas tourne
# une seule fois. Elle fait cinq appels a user_has_action_access par module
# accessible -- un salarie avec dix modules en paie bien davantage.
#
# POURQUOI PARESSEUX PLUTOT QUE SUPPRIME
#
# Retirer la variable du contexte aurait ete plus propre a lire, et c'est le
# choix dangereux. Dans un gabarit Django, une variable absente se resout en
# chaine vide, sans erreur : un « {% if perms_map.btp %} » ecrit plus tard, ou
# ailleurs dans un gabarit que je n'aurais pas trouve, deviendrait faux EN
# SILENCE et masquerait des boutons a leurs ayants droit. Un defaut
# d'affichage muet vaut moins qu'une variable inutile.
#
# SimpleLazyObject ne change rien a ce que recoit le gabarit -- meme
# iteration, meme test de verite, meme acces par cle, meme longueur : Django
# relaie ces operations vers l'objet enveloppe. Il ne change que le MOMENT du
# calcul, qui n'a plus lieu si personne ne lit la variable. Le contrat est
# donc intact, et le cout disparait.
#
# Les fonctions de services.py ne sont pas touchees : ce sont elles qui
# portent les regles de permission, et les tests les appellent directement.
# Ce fichier ne decide d'aucun droit, il choisit seulement quand demander.


# Les modules dont on expose un acces « rapide » aux gabarits. La liste etait
# ecrite dans le corps de la fonction ; elle est ici pour qu'un test puisse
# verifier que le dictionnaire paresseux porte bien les memes cles qu'avant.
MODULES_SURVEILLES = (
    'dashboard', 'crm', 'sales', 'accounting', 'purchases', 'inventory',
    'btp', 'hr', 'payroll', 'documents', 'support', 'ecommerce',
    'commerce', 'production', 'audio', 'websites', 'reporting', 'settings',
)


def available_modules(request):
    if not request.user.is_authenticated:
        return {'available_modules': [], 'sidebar_items': []}
    company = getattr(request, 'current_company', None)
    if not company:
        return {'available_modules': [], 'sidebar_items': []}

    # `request.user` est capture dans une variable locale : la fermeture ne
    # retient alors que l'utilisateur, et non la requete entiere.
    utilisateur = request.user
    return {
        'available_modules': SimpleLazyObject(
            lambda: get_user_modules(utilisateur, company)
        ),
        'sidebar_items': SimpleLazyObject(
            lambda: get_user_sidebar_items(utilisateur, company)
        ),
    }


def _calculer_perms_map(utilisateur, company):
    """Le dictionnaire d'acces par module, calcule a la demande."""
    from .services import user_has_module_access

    return {
        module: user_has_module_access(utilisateur, company, module)
        for module in MODULES_SURVEILLES
    }


def current_company_permissions(request):
    """Expose un dict de permissions rapides pour les templates."""
    if not request.user.is_authenticated:
        return {'perms_map': {}}
    company = getattr(request, 'current_company', None)
    if not company:
        return {'perms_map': {}}

    utilisateur = request.user
    return {
        'perms_map': SimpleLazyObject(
            lambda: _calculer_perms_map(utilisateur, company)
        )
    }
