"""
apps/accounts/services/user_deletion_service.py — Suppression d'un compte

Supprimer un utilisateur n'est pas supprimer une ligne. Mesure faite sur ce
projet : 164 relations pointent vers `User`, dont **29 en CASCADE**. Parmi
elles, des données qui ne sont pas des préférences d'affichage — les heures
pointées sur les chantiers (`btp.BTPTimesheet`), les comptes de fidélité et
les abonnements des clientes Lunea, les accès au portail client. Un simple
`user.delete()` les emporte sans un mot.

Les 135 autres relations sont en SET_NULL : un devis, une facture, un
mouvement de stock conservent leur ligne, et perdent seulement le nom de
leur auteur. C'est la bonne nouvelle, et c'est aussi ce qui rend la
suppression tentante alors qu'elle reste destructrice ailleurs.

D'où la forme de ce module : on ne demande jamais de confirmer dans le vide.
`inventaire_cascade()` interroge le collecteur de Django — celui qu'utilise
l'admin — pour dire ce qui va réellement disparaître, avec les comptes
exacts. Ce n'est pas une estimation : c'est la liste que Django s'apprête à
effacer.

La désactivation (`is_active = False`) reste l'opération à préférer dans la
quasi-totalité des cas : elle ferme l'accès immédiatement et ne détruit
rien.
"""

from django.contrib.auth.models import User
from django.db import router, transaction

# Modèles dont la perte est une perte de données d'exploitation, et non d'un
# réglage personnel. Le reste de l'inventaire est affiché aussi ; ceux-ci
# sont signalés, parce que personne ne lit une liste de trente lignes sans
# qu'on lui dise où regarder.
#
# Les libellés servent de phrase dans l'avertissement : ils doivent décrire
# ce que l'utilisateur perd, pas nommer une table.
MODELES_SENSIBLES = {
    'btp.BTPTimesheet': 'heures pointées sur les chantiers',
    'lunea.LoyaltyAccount': 'compte de fidélité et points acquis',
    'lunea.BeautySubscription': 'abonnements en cours',
    'lunea.CustomerSkinDiagnostic': 'diagnostics de peau enregistrés',
    'lunea.CustomerBeautyProfile': 'profil beauté de la cliente',
    'lunea.CustomerShadeProfile': 'profil de teintes de la cliente',
    'lunea.CustomerWishlistItem': 'liste d\'envies',
    'portals.ClientPortalAccount': 'accès au portail client',
    'accounts.UserActivity': 'journal d\'activité du compte',
    'admin.LogEntry': 'journal des modifications faites via l\'admin',
}

ROLES_AUTORISES = ('admin', 'superadmin')


def _role(utilisateur) -> str:
    """Le rôle, ou '' si le compte n'a pas de profil.

    Un `User` sans `UserProfile` existe : création via createsuperuser, ou
    profil supprimé à la main. Lire `.profile.role` lèverait
    RelatedObjectDoesNotExist et ferait planter la page au lieu de refuser
    proprement.
    """
    profil = getattr(utilisateur, 'profile', None)
    return getattr(profil, 'role', '') or ''


def peut_supprimer(auteur, cible, company=None) -> tuple[bool, str]:
    """Dit si `auteur` a le droit de supprimer `cible`, et sinon pourquoi.

    Fonction unique et appelée DEUX fois : à l'affichage de la page de
    confirmation, et à nouveau au moment d'agir. Un droit vérifié seulement
    à l'affichage se contourne en rejouant le POST — c'est la même erreur
    que de restreindre une liste déroulante sans borner le queryset qui la
    valide.

    Retourne (autorisé, raison). La raison est destinée à l'utilisateur.
    """
    if not auteur.is_superuser and _role(auteur) not in ROLES_AUTORISES:
        return False, (
            'Seul un administrateur peut supprimer un compte. Un responsable '
            'peut consulter la liste des utilisateurs, pas les effacer.')

    # Avant tout contrôle de hiérarchie : se supprimer soi-même détruit la
    # session en cours, et si le compte était le dernier administrateur,
    # plus personne ne peut rentrer. L'erreur serait irréparable depuis
    # l'interface.
    if cible.pk == auteur.pk:
        return False, (
            'Vous ne pouvez pas supprimer votre propre compte. Demandez-le à '
            'un autre administrateur.')

    if cible.is_superuser and not auteur.is_superuser:
        return False, (
            'Ce compte est super administrateur : seul un autre super '
            'administrateur peut le supprimer.')

    # Même un super administrateur ne peut pas retirer le dernier. Sans ce
    # garde-fou, l'ERP se retrouve sans personne capable de rouvrir un
    # accès, et le rattrapage passe par la ligne de commande du serveur.
    if cible.is_superuser:
        restants = User.objects.filter(
            is_superuser=True, is_active=True).exclude(pk=cible.pk).count()
        if restants == 0:
            return False, (
                'C\'est le dernier super administrateur actif. Le supprimer '
                'laisserait l\'ERP sans compte capable d\'en recréer un. '
                'Nommez d\'abord un autre super administrateur.')

    # Cloisonnement. Un administrateur d'entreprise ne voit que ses propres
    # utilisateurs (voir user_list) ; il ne doit pas non plus pouvoir en
    # supprimer un autre en forgeant un identifiant dans l'URL.
    if not auteur.is_superuser:
        if company is None:
            return False, 'Aucune entreprise active : suppression impossible.'
        appartient = User.objects.filter(
            pk=cible.pk, profile__companies=company).exists()
        if not appartient:
            return False, (
                'Ce compte n\'appartient pas à l\'entreprise active.')

    return True, ''


def inventaire_cascade(cible) -> dict:
    """Ce qui serait réellement détruit avec ce compte.

    Utilise le collecteur de Django — le même que la page de confirmation de
    l'admin. `NestedObjects` désactive volontairement la suppression rapide
    afin que TOUT soit chargé en mémoire et donc dénombrable ; sans cela,
    les suppressions par lot n'apparaîtraient nulle part et l'inventaire
    mentirait par omission.

    Retourne {lignes, total, sensibles, traces_conservees}.
    """
    from django.contrib.admin.utils import NestedObjects

    collecteur = NestedObjects(using=router.db_for_write(User, instance=cible))
    collecteur.collect([cible])

    lignes = []
    total = 0
    for modele, objets in collecteur.data.items():
        label = modele._meta.label
        nombre = len(objets)
        if label == 'auth.User':
            # Le compte lui-même : ce n'est pas une perte collatérale, c'est
            # l'objet de l'opération. Le compter ici ferait croire à une
            # suppression en chaîne là où il n'y en a pas.
            continue
        total += nombre
        lignes.append({
            'label': label,
            'nom': str(modele._meta.verbose_name_plural).capitalize(),
            'total': nombre,
            'sensible': label in MODELES_SENSIBLES,
            'motif': MODELES_SENSIBLES.get(label, ''),
        })

    # Les sensibles d'abord : c'est la seule partie de la liste sur laquelle
    # une décision se prend.
    lignes.sort(key=lambda ligne: (not ligne['sensible'], -ligne['total'],
                                   ligne['label']))

    traces = sum(len(objets) for objets in collecteur.field_updates.values())

    return {
        'lignes': lignes,
        'total': total,
        'sensibles': [ligne for ligne in lignes if ligne['sensible']],
        'traces_conservees': traces,
    }


def supprimer_utilisateur(auteur, cible, company=None, ip=None) -> tuple[bool, str]:
    """Supprime le compte, après journalisation. Retourne (succès, message).

    Le journal est écrit AVANT la suppression, et c'est voulu : une fois
    l'objet parti, son identité n'est plus lisible, et `AuditLog.user` ne
    retiendrait qu'un NULL. Le nom et l'identifiant sont donc recopiés en
    texte dans l'entrée, qui survit à l'objet.
    """
    autorise, raison = peut_supprimer(auteur, cible, company)
    if not autorise:
        return False, raison

    from apps.core.models import AuditLog

    identite = {
        'pk': cible.pk,
        'username': cible.username,
        'email': cible.email,
        'nom_complet': cible.get_full_name(),
        'role': _role(cible),
        'is_superuser': cible.is_superuser,
        'is_active': cible.is_active,
    }
    inventaire = inventaire_cascade(cible)
    etiquette = cible.get_full_name() or cible.username

    with transaction.atomic():
        AuditLog.objects.create(
            user=auteur,
            company=company,
            action='delete',
            module='accounts',
            model_name='User',
            object_id=str(cible.pk),
            object_repr=etiquette[:200],
            old_values=identite,
            new_values={
                'objets_lies_supprimes': inventaire['total'],
                'detail': [
                    {'modele': ligne['label'], 'nombre': ligne['total']}
                    for ligne in inventaire['lignes']
                ],
            },
            description=(
                f'Suppression du compte « {cible.username} » par '
                f'{auteur.username} — {inventaire["total"]} objet(s) lié(s) '
                f'supprimé(s) en cascade.'),
            ip_address=ip or None,
        )
        cible.delete()

    return True, f'Le compte « {etiquette} » a été supprimé.'


def desactiver_utilisateur(auteur, cible, company=None, ip=None) -> tuple[bool, str]:
    """Ferme l'accès sans rien détruire. L'opération à préférer.

    Mêmes contrôles d'autorisation que la suppression — se désactiver
    soi-même revient à se verrouiller dehors, et retirer le dernier super
    administrateur actif a exactement la même conséquence qu'en le
    supprimant.
    """
    autorise, raison = peut_supprimer(auteur, cible, company)
    if not autorise:
        return False, raison

    if not cible.is_active:
        return True, 'Ce compte était déjà désactivé.'

    from apps.core.models import AuditLog

    etiquette = cible.get_full_name() or cible.username
    with transaction.atomic():
        cible.is_active = False
        cible.save(update_fields=['is_active'])
        AuditLog.objects.create(
            user=auteur,
            company=company,
            action='update',
            module='accounts',
            model_name='User',
            object_id=str(cible.pk),
            object_repr=etiquette[:200],
            old_values={'is_active': True},
            new_values={'is_active': False},
            description=(
                f'Désactivation du compte « {cible.username} » par '
                f'{auteur.username}.'),
            ip_address=ip or None,
        )

    return True, (
        f'Le compte « {etiquette} » est désactivé : l\'accès est fermé et '
        f'aucune donnée n\'a été supprimée.')
