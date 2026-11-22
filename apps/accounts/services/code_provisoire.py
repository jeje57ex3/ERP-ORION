"""Le code provisoire d'un compte neuf : l'engendrer, le poser, l'envoyer.

**Ce que ce module remplace.** L'écran de création d'utilisateur demandait
un mot de passe à l'administrateur, qu'il devait ensuite transmettre au
nouvel arrivant — de vive voix, par message, sur un papier. Trois défauts
à la fois : l'administrateur connaît le mot de passe de quelqu'un d'autre,
le mot de passe transite par un canal que personne ne maîtrise, et rien
n'oblige jamais à le changer. Un compte créé en janvier gardait en octobre
le mot de passe tapé par son patron.

Désormais : un code aléatoire, envoyé à l'adresse saisie sur le compte, et
un changement obligatoire à la première connexion.

**Ce que ce code est, et ce qu'il n'est pas.** C'est un mot de passe à
usage unique, pas un jeton de vérification à six chiffres. Il est donc
posé par `set_password()` — haché comme n'importe quel mot de passe — et
sert à la connexion normale. Aucun chemin de connexion nouveau n'est
créé, donc aucun chemin nouveau à sécuriser : la limitation d'essais, le
verrou de compte et la 2FA s'appliquent déjà.

**Pourquoi 14 caractères et un alphabet réduit.** Le code est lu dans un
courriel puis recopié à la main. `O`/`0` et `I`/`l`/`1` se confondent à la
lecture, et une faute de recopie se lit comme « mon compte ne marche
pas » — une protection qu'on ne sait pas utiliser se fait contourner. Les
retirer coûte un peu d'entropie : 14 caractères sur 49 valent environ 78
bits, très au-delà de ce que la limitation d'essais laisse tenter.

**Le code n'est JAMAIS montré à l'administrateur, ni journalisé.** C'est
le point de tout le dispositif : si l'écran l'affichait « au cas où », il
serait recopié, transmis par message, et le courriel ne servirait plus à
rien. La seule issue en cas d'échec d'envoi est d'en renvoyer un autre
(`accounts:user_renvoyer_le_code`), ce qui invalide le précédent.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string

journal = logging.getLogger('orion')

# Sans O, 0, I, l, 1 — les caractères qu'on recopie de travers.
ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789'
LONGUEUR = 14


def engendrer_un_code():
    """Un code provisoire. `get_random_string` tire dans `secrets`."""
    return get_random_string(LONGUEUR, allowed_chars=ALPHABET)


def poser_un_code(utilisateur, code=None):
    """Pose le code comme mot de passe et marque le compte à changer.

    Les deux écritures vont ensemble : un code posé sans le drapeau serait
    un mot de passe permanent engendré par la machine, que personne ne
    serait jamais invité à changer — c'est-à-dire le défaut d'avant, en
    pire, puisque son porteur ne le choisirait même pas.
    """
    code = code or engendrer_un_code()
    utilisateur.set_password(code)
    utilisateur.save(update_fields=['password'])

    profil = utilisateur.profile
    profil.doit_changer_de_mot_de_passe = True
    profil.code_provisoire_envoye_le = timezone.now()
    profil.save(update_fields=['doit_changer_de_mot_de_passe',
                               'code_provisoire_envoye_le'])
    return code


def _adresse_de_connexion(request):
    """L'adresse complète de l'écran de connexion, pour le courriel.

    Un courriel se lit ailleurs que dans l'ERP : un lien relatif n'y mène
    nulle part. Sans `request` — un envoi depuis une tâche de fond — on
    retombe sur le premier hôte admis, ce qui vaut mieux qu'un lien cassé.
    """
    chemin = reverse('accounts:login')
    if request is not None:
        return request.build_absolute_uri(chemin)

    hotes = [h for h in getattr(settings, 'ALLOWED_HOSTS', []) if h != '*']
    if hotes:
        return 'https://%s%s' % (hotes[0], chemin)
    return chemin


def corps_du_message(utilisateur, code, request=None):
    """Le texte envoyé. Séparé pour être lisible et testable isolément."""
    nom = (utilisateur.get_full_name() or utilisateur.username).strip()
    return (
        'Bonjour %s,\n\n'
        'Un compte vient d’être créé pour vous sur Orion ERP.\n\n'
        'Identifiant : %s\n'
        'Code provisoire : %s\n\n'
        'Connectez-vous ici : %s\n\n'
        'Ce code ne sert qu’une fois : dès votre première connexion, '
        'l’application vous demandera de choisir votre propre mot de '
        'passe. Personne d’autre que vous ne connaît ce code — pas même '
        'l’administrateur qui a créé le compte.\n\n'
        'Si vous n’attendiez pas ce message, ignorez-le et signalez-le à '
        'votre administrateur : le compte restera inutilisable tant que '
        'personne ne s’y connecte.\n'
        % (nom, utilisateur.username, code, _adresse_de_connexion(request))
    )


def envoyer_le_code(utilisateur, code, request=None):
    """Envoie le code. Rend (envoyé, motif de l'échec).

    `fail_silently=False` À DESSEIN, et l'exception est rattrapée ici. Un
    envoi silencieusement perdu laisserait un compte dont le code n'est
    nulle part : ni dans une boîte, ni à l'écran, ni dans un journal. On
    veut donc le motif, pour l'afficher à l'administrateur et lui
    permettre de renvoyer un code.
    """
    if not utilisateur.email:
        return False, 'aucune adresse de courriel sur ce compte'

    try:
        envoyes = send_mail(
            subject='Votre accès à Orion ERP',
            message=corps_du_message(utilisateur, code, request),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            recipient_list=[utilisateur.email],
            fail_silently=False,
        )
    except Exception as exc:
        journal.warning(
            'Code provisoire non envoyé à %s (compte %s) : %s',
            utilisateur.email, utilisateur.username, exc)
        return False, str(exc)

    if not envoyes:
        # Le backend n'a lévé aucune erreur et n'a rien envoyé. C'est le
        # cas de `fail_silently` posé plus bas dans la pile : on refuse de
        # le lire comme un succès.
        journal.warning(
            'Code provisoire : le serveur de courriel n’a accepté aucun '
            'destinataire pour %s (compte %s).',
            utilisateur.email, utilisateur.username)
        return False, 'le serveur de courriel n’a accepté aucun destinataire'

    return True, ''


def creer_et_envoyer(utilisateur, request=None):
    """Engendre un code, le pose, l'envoie. Rend (envoyé, motif).

    L'ORDRE COMPTE, et il est délibérément celui-ci : le code est posé
    AVANT d'être envoyé. Si l'envoi échoue, le compte porte un code que
    personne ne connaît — donc inutilisable, ce qui est l'état sûr. Dans
    l'autre ordre, un envoi réussi suivi d'une écriture échouée laisserait
    un code valide dans une boîte de courriel et un compte qui ne le
    reconnaît pas : le pire des deux, car l'administrateur aurait vu
    « envoyé » et n'aurait aucune raison de recommencer.
    """
    code = poser_un_code(utilisateur)
    return envoyer_le_code(utilisateur, code, request)
