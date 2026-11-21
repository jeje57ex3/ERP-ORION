"""apps/accounts/anti_force_brute.py — Limiter les essais de mot de passe.

CE QUI MANQUAIT

`UserProfile` porte deux colonnes depuis sa première migration :

    failed_login_attempts = models.PositiveIntegerField(default=0)
    locked_until          = models.DateTimeField(null=True, blank=True)

Aucune des deux n'était lue ni écrite nulle part. Quelqu'un avait prévu
la protection, créé la place pour elle, et elle n'a jamais été branchée.
L'écran de connexion de l'ERP acceptait donc **un nombre illimité**
d'essais de mot de passe, et rien n'en gardait trace au-delà d'une ligne
d'audit par échec.

Pour un ERP joignable par un domaine public, c'est la porte la plus
simple : pas de faille à trouver, pas de contournement à inventaire —
seulement du temps et une liste de mots de passe.

DEUX COMPTEURS, PARCE QU'UN SEUL SE CONTOURNE

    par compte      arrête celui qui s'acharne sur UN identifiant depuis
                    cent adresses — un réseau de machines, ou simplement
                    un service d'anonymisation.

    par adresse     arrête celui qui essaie UN mot de passe courant sur
                    cent identifiants depuis une adresse — le balayage,
                    qui ne déclenche jamais le compteur par compte
                    puisqu'il ne retente jamais le même.

Tenir l'un sans l'autre laisse passer exactement l'attaque que l'autre
arrête. C'est pourquoi il y en a deux, et non un réglage.

LE VERROU DE COMPTE EST EN BASE, LE COMPTEUR D'ADRESSE EN CACHE

Le verrou doit survivre à un vidage du cache : Redis redémarre à chaque
mise à jour, et un verrou qui s'ouvre au redémarrage est un verrou dont
l'attaquant choisit la durée. Il va donc dans `locked_until`.

Le compteur par adresse, lui, est volumineux et sans valeur passé son
délai — le cache est sa place. S'il disparaît, le verrou de compte reste.

LE VERROU EST TEMPORAIRE, ET C'EST UN CHOIX

Un verrou définitif transforme la protection en déni de service contre
l'utilisateur légitime : il suffit d'échouer trois fois sur le compte du
patron pour le mettre dehors jusqu'à ce qu'un administrateur intervienne.
La durée croît avec les échecs — une minute, puis cinq, puis quinze,
jusqu'à une heure — ce qui rend l'attaque sans intérêt tout en laissant
l'utilisateur reprendre la main seul.

LE MESSAGE NE DIT PAS SI LE COMPTE EXISTE

`est_verrouille` est interrogé avant toute authentification, donc pour
un identifiant qui peut ne correspondre à rien. Répondre « ce compte est
verrouillé » pour l'un et « identifiants incorrects » pour l'autre
donnerait la liste des comptes à qui prendrait la peine de comparer. Le
même texte sert dans les deux cas.
"""
import logging

from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger('orion')

#: Échecs tolérés sur un identifiant avant de le verrouiller.
ECHECS_PAR_COMPTE = 5

#: Échecs tolérés depuis une adresse, tous identifiants confondus. Plus
#: haut que le seuil par compte : un bureau partage une adresse, et
#: plusieurs personnes peuvent se tromper le même matin.
ECHECS_PAR_ADRESSE = 20

#: Durée pendant laquelle les échecs se cumulent. Au-delà, le compteur
#: repart : quelqu'un qui se trompe deux fois en mars et trois fois en
#: juin n'est pas une attaque.
FENETRE_SECONDES = 900

#: Durées de verrouillage successives, en secondes. La dernière se
#: répète : on ne verrouille jamais définitivement.
PALIERS_DE_VERROU = (60, 300, 900, 3600)

PREFIXE_ADRESSE = 'orion:connexion:adresse'
PREFIXE_COMPTE = 'orion:connexion:compte'

#: Le même texte dans tous les cas de refus — voir l'en-tête du module.
MESSAGE_DE_VERROU = (
    'Trop de tentatives de connexion. Pour protéger le compte, '
    'l’accès est suspendu {delai}. Réessayez ensuite, ou faites '
    'réinitialiser le mot de passe.'
)


def _delai_lisible(secondes):
    if secondes <= 90:
        return 'une minute'
    minutes = int(round(secondes / 60.0))
    if minutes < 60:
        return f'{minutes} minutes'
    heures = int(round(minutes / 60.0))
    return 'une heure' if heures <= 1 else f'{heures} heures'


def _profil(identifiant):
    """Le profil de cet identifiant, ou `None` s'il n'existe pas.

    On ne crée rien : un identifiant inventé ne doit pas laisser de
    trace en base, sans quoi la table grossirait au rythme de l'attaque.
    """
    if not identifiant:
        return None
    from apps.accounts.models import UserProfile

    return (UserProfile.objects
            .filter(user__username__iexact=identifiant)
            .select_related('user')
            .first())


def duree_du_verrou(echecs):
    """La durée à appliquer après `echecs` échecs."""
    if echecs < ECHECS_PAR_COMPTE:
        return 0
    rang = min(echecs - ECHECS_PAR_COMPTE, len(PALIERS_DE_VERROU) - 1)
    return PALIERS_DE_VERROU[rang]


def est_verrouille(request, identifiant):
    """`(verrouille, message)` — le message est déjà rédigé, ou vide.

    Interrogé AVANT l'authentification : l'identifiant peut ne
    correspondre à aucun compte, et la réponse ne doit pas le révéler.
    """
    from apps.core.client_ip import ip_du_client

    maintenant = timezone.now()

    # Le verrou de compte, en base — il survit à un vidage du cache.
    profil = _profil(identifiant)
    if profil and profil.locked_until and profil.locked_until > maintenant:
        reste = int((profil.locked_until - maintenant).total_seconds())
        return True, MESSAGE_DE_VERROU.format(
            delai=f'pendant encore {_delai_lisible(reste)}')

    # Le compteur par adresse, en cache.
    adresse = ip_du_client(request)
    echecs = cache.get(f'{PREFIXE_ADRESSE}:{adresse}', 0)
    if echecs >= ECHECS_PAR_ADRESSE:
        return True, MESSAGE_DE_VERROU.format(
            delai=f'pendant {_delai_lisible(FENETRE_SECONDES)}')

    return False, ''


def enregistrer_un_echec(request, identifiant):
    """Compte un échec, et verrouille le compte si le seuil est franchi.

    Rend le message à afficher si le verrou vient de se poser, sinon une
    chaîne vide — l'appelant garde alors son message d'identifiants
    incorrects.
    """
    from apps.core.client_ip import ip_du_client

    adresse = ip_du_client(request)

    # UN `cache.add` PUIS `incr`, ET NON UN `get` PUIS `set`.
    #
    # Deux requêtes simultanées qui lisent 4 et écrivent 5 toutes les
    # deux perdent un échec. `incr` est atomique côté Redis ; `add` ne
    # pose la valeur que si la clef n'existe pas, donc ne remet jamais
    # un compteur en cours à zéro.
    cle_adresse = f'{PREFIXE_ADRESSE}:{adresse}'
    cache.add(cle_adresse, 0, FENETRE_SECONDES)
    try:
        cache.incr(cle_adresse)
    except ValueError:
        # La clef a expiré entre l'`add` et l'`incr`.
        cache.set(cle_adresse, 1, FENETRE_SECONDES)

    profil = _profil(identifiant)
    if profil is None:
        # Identifiant inconnu : seul le compteur d'adresse le retient.
        # C'est lui qui arrête le balayage, qui ne cible aucun compte
        # existant.
        logger.info('Connexion refusée : identifiant inconnu depuis %s',
                    adresse)
        return ''

    # Le compteur de compte, en base, par un `F()` pour la même raison
    # d'atomicité que ci-dessus.
    from django.db.models import F
    from apps.accounts.models import UserProfile

    UserProfile.objects.filter(pk=profil.pk).update(
        failed_login_attempts=F('failed_login_attempts') + 1)
    profil.refresh_from_db(fields=['failed_login_attempts'])

    duree = duree_du_verrou(profil.failed_login_attempts)
    if not duree:
        return ''

    jusqu_a = timezone.now() + timezone.timedelta(seconds=duree)
    UserProfile.objects.filter(pk=profil.pk).update(locked_until=jusqu_a)

    logger.warning(
        'Compte « %s » verrouillé %d s après %d échecs (adresse %s)',
        profil.user.username, duree, profil.failed_login_attempts, adresse)

    _journaliser(profil.user, request, duree)

    return MESSAGE_DE_VERROU.format(
        delai=f'pendant {_delai_lisible(duree)}')


def _journaliser(utilisateur, request, duree):
    """Trace le verrouillage parmi les événements de sécurité.

    Enveloppé : `apps.user_security` tient sa propre table, et un défaut
    d'écriture là-bas ne doit pas empêcher le verrou — qui est, lui, déjà
    posé en base.
    """
    try:
        from apps.user_security.services import log_security_event

        log_security_event(utilisateur, 'account_locked', request,
                           {'duree_secondes': duree})
    except Exception:
        logger.exception('Verrou posé, mais non journalisé')


def effacer_les_echecs(request, identifiant):
    """Remet les compteurs à zéro après une connexion réussie.

    LE COMPTEUR D'ADRESSE EST EFFACÉ LUI AUSSI, et c'est discutable : un
    attaquant qui connaît un compte pourrait s'en servir pour remettre
    son quota à zéro. Mais le cas inverse est bien plus fréquent — un
    bureau derrière une seule adresse, où les essais ratés d'une personne
    bloqueraient ses collègues — et une connexion réussie est la preuve
    la plus forte qu'on ait que l'adresse est légitime.
    """
    from apps.core.client_ip import ip_du_client

    cache.delete(f'{PREFIXE_ADRESSE}:{ip_du_client(request)}')
    cache.delete(f'{PREFIXE_COMPTE}:{identifiant}')

    profil = _profil(identifiant)
    if profil and (profil.failed_login_attempts or profil.locked_until):
        from apps.accounts.models import UserProfile

        UserProfile.objects.filter(pk=profil.pk).update(
            failed_login_attempts=0, locked_until=None)


def deverrouiller(profil):
    """Lève le verrou d'un compte depuis l'interface d'administration.

    Existe pour que personne n'ait besoin d'un terminal : un verrou qu'on
    ne peut lever qu'en base est un verrou qui finit par être levé en
    désactivant la protection.
    """
    from apps.accounts.models import UserProfile

    UserProfile.objects.filter(pk=profil.pk).update(
        failed_login_attempts=0, locked_until=None)
