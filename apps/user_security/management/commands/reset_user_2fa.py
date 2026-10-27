"""Porte de sortie : rend son compte a quelqu'un qui ne peut plus entrer.

Telephone perdu, application d'authentification effacee, horloge de
l'appareil decalee : la 2FA protege le compte et, ce jour-la, elle en
interdit l'acces a son proprietaire. Cette commande est le seul recours,
et elle s'execute depuis le serveur -- donc par quelqu'un qui a deja
l'acces, ce qui est la garantie qu'elle n'ouvre rien a un inconnu.

    manage.py reset_user_2fa jessy
    manage.py reset_user_2fa jessy@exemple.fr
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from apps.user_security.models import (
    TrustedDevice,
    UserRecoveryCode,
    UserTwoFactorSettings,
)
from apps.user_security.services import _refleter_sur_le_profil


class Command(BaseCommand):
    help = "Réinitialise la double authentification d'un utilisateur."

    def add_arguments(self, parser):
        parser.add_argument("username_or_email", type=str)

    def handle(self, *args, **options):
        value = options["username_or_email"]
        User = get_user_model()
        user = (
            User.objects.filter(username=value).first()
            or User.objects.filter(email=value).first()
        )
        if not user:
            # CommandError et non un message sur stderr suivi d'un retour :
            # celui qui appelle cette commande depuis un script doit pouvoir
            # distinguer « compte rendu » de « rien fait, nom inconnu ».
            raise CommandError(
                f"Aucun utilisateur nomme « {value} », ni par identifiant "
                f"ni par courriel. Rien n'a ete modifie."
            )
        UserTwoFactorSettings.objects.filter(user=user).delete()
        UserRecoveryCode.objects.filter(user=user).delete()
        TrustedDevice.objects.filter(user=user).delete()
        # Le champ accounts.UserProfile.two_factor_enabled reflete l'etat
        # reel de la 2FA. Sans cette ligne, il resterait a True sur un
        # compte qui ne l'a plus -- le champ qui mentait a nouveau, et
        # c'est precisement ce que le reflet existe pour empecher.
        _refleter_sur_le_profil(user, False)
        self.stdout.write(self.style.SUCCESS(f"2FA reinitialisee pour {user}."))
