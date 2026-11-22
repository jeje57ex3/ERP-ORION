"""Le plafond de taille d'un fichier téléversé, et pourquoi Django n'en posait aucun.

**Ce que les réglages laissaient croire.** `settings/base.py` portait, sous
le titre « Upload fichiers », deux lignes à 20 Mo :

    FILE_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024
    DATA_UPLOAD_MAX_MEMORY_SIZE = 20 * 1024 * 1024

Elles se lisent comme un plafond. Aucune des deux n'en est un.

`FILE_UPLOAD_MAX_MEMORY_SIZE` est le seuil au-delà duquel un fichier passe
de la mémoire à un fichier temporaire sur disque. Il décide *où* le fichier
atterrit, jamais s'il est accepté — le relever accepte autant, le baisser
aussi.

`DATA_UPLOAD_MAX_MEMORY_SIZE` borne bien le corps d'une requête, mais **les
parties « fichier » n'y sont pas comptées**. C'est vérifiable dans
`django/http/multipartparser.py` : la comptabilité d'octets
(`num_bytes_read`) et sa vérification sont toutes deux à l'intérieur de
`if item_type == FIELD:`. La branche `elif item_type == FILE:` ne contrôle
que `DATA_UPLOAD_MAX_NUMBER_FILES`, c'est-à-dire un *nombre* de fichiers,
pas leur taille.

Et aucun des soixante-cinq `FileField`/`ImageField` du projet ne porte de
`validators`. Il n'existait donc, nulle part, de limite de taille — alors
que la section de réglages intitulée « Upload fichiers » donnait à penser
que oui. Un réglage qui rassure sans protéger est pire qu'un réglage
absent : on ne cherche pas ce qu'on croit avoir.

**Pourquoi un gestionnaire de téléversement, et non un validateur de
champ.** Un validateur s'exécute quand le fichier est *déjà* écrit sur le
disque : il refuse l'enregistrement en base, pas la place occupée. Il
faudrait de plus l'ajouter à soixante-cinq champs, donc l'oublier sur le
soixante-sixième. Un gestionnaire voit passer les blocs *pendant* la
lecture, peut refuser avant d'avoir rien écrit, et se pose une seule fois
pour tout le projet — y compris l'admin Django et les API, que ni les
formulaires ni les sérialiseurs ne couvrent ensemble.

**Deux barrières, et il en faut deux.** `Content-Length` est annoncé par le
client : s'y fier seul laisse passer un corps plus gros que ce qu'il
déclare. On refuse donc d'emblée ce qui s'annonce trop gros — sans lire un
octet, ce qui est l'essentiel de la protection — et on recompte malgré tout
les blocs reçus, pour le cas où l'en-tête mentait.

**Pourquoi des chemins exemptés.** Quatre écrans téléversent légitimement
des fichiers énormes : l'import d'une sauvegarde portable (une base
complète plus les médias), les deux centres de sauvegarde, et le dépôt de
l'installeur Windows de l'application PC. Tous sont réservés au superadmin.
Ce plafond existe pour empêcher un salarié connecté de remplir le disque,
pas pour contrarier un superadmin qui restaure une base.

C'est un arbitrage, et il est délibéré : un plafond qui casse une
restauration serait désactivé à la première panne — et c'est ainsi qu'une
protection disparaît pour de bon.
"""

from django.conf import settings
from django.core.exceptions import RequestDataTooBig
from django.core.files.uploadhandler import FileUploadHandler

# 20 Mo : la valeur que les deux réglages ci-dessus affichaient déjà, et
# qu'on croyait donc appliquée. On la rend vraie plutôt que d'en changer.
PLAFOND_PAR_DEFAUT = 20 * 1024 * 1024

# Les chemins où un gros fichier est la fonction même de l'écran. Tous sont
# derrière un contrôle de superadmin (voir apps/backups/views.py et
# apps/system_updates/permissions.py).
CHEMINS_SANS_PLAFOND = (
    '/admin/',                        # Admin Django : dépôt de l'installeur
    '/sauvegardes/',                  # apps.backups — import d'une archive
    '/backups/',                      # apps.backup_center
    '/orion-admin/application-pc/',   # Versions de l'application de bureau
)


def plafond_configure():
    """Le plafond en octets. 0 signifie « aucun plafond ».

    Lu à chaque requête et non une fois au chargement : `override_settings`
    doit pouvoir le changer dans un test, et un exploitant doit pouvoir le
    relever dans `.env` sans qu'on retouche au code.
    """
    valeur = getattr(settings, 'ORION_TAILLE_MAX_TELEVERSEMENT',
                     PLAFOND_PAR_DEFAUT)
    try:
        valeur = int(valeur)
    except (TypeError, ValueError):
        # Un réglage illisible ne doit pas DÉSACTIVER la protection : c'est
        # le sens du défaut qui décide de ce qui arrive quand on se trompe.
        return PLAFOND_PAR_DEFAUT
    return valeur if valeur > 0 else 0


def chemin_exempte(chemin):
    """Vrai si ce chemin a le droit de recevoir un fichier sans plafond."""
    chemin = str(chemin or '')
    return any(chemin.startswith(prefixe) for prefixe in CHEMINS_SANS_PLAFOND)


def plafond_pour(request):
    """Le plafond applicable à cette requête. 0 : aucun."""
    if chemin_exempte(getattr(request, 'path', '')):
        return 0
    return plafond_configure()


class PlafondDeTaille(FileUploadHandler):
    """Refuse un fichier trop gros, pendant la lecture et non après.

    Doit être le PREMIER de `FILE_UPLOAD_HANDLERS` : les gestionnaires
    reçoivent les blocs dans l'ordre, et celui-ci doit décider avant que
    `TemporaryFileUploadHandler` ait écrit quoi que ce soit sur le disque.

    Lève `RequestDataTooBig`, et non `StopUpload`. `MultiPartParser.parse`
    rattrape `StopUpload` et poursuit : la vue verrait alors un champ
    fichier *vide* et répondrait « ce champ est obligatoire », ce qui
    n'apprend rien à qui vient d'envoyer un fichier de 300 Mo.
    `RequestDataTooBig` dérive de `SuspiciousOperation` et remonte jusqu'au
    gestionnaire d'exceptions de Django, qui rend un 400 et le journalise —
    une cause lisible dans les deux sens.
    """

    def __init__(self, request=None):
        super().__init__(request)
        self.plafond = 0
        self.recu = 0

    def handle_raw_input(self, input_data, META, content_length, boundary,
                         encoding=None):
        """Première barrière : ce qui s'annonce trop gros n'est pas lu.

        Rendre `None` laisse le parseur suivre son cours normal ; c'est le
        contrat de cette méthode, et c'est pour cela qu'elle sert ici de
        simple point d'entrée.
        """
        self.plafond = plafond_pour(self.request)
        self.recu = 0

        if self.plafond:
            try:
                annonce = int(content_length or 0)
            except (TypeError, ValueError):
                annonce = 0
            # Le corps multipart porte aussi les frontières et les en-têtes
            # de parties : on tolère une marge avant de refuser, pour ne pas
            # rejeter un fichier qui tient tout juste dans le plafond.
            if annonce > self.plafond + 8192:
                raise RequestDataTooBig(
                    'Fichier trop volumineux : %d octets annoncés pour un '
                    'plafond de %d.' % (annonce, self.plafond))
        return None

    def new_file(self, *args, **kwargs):
        super().new_file(*args, **kwargs)
        # Remis à zéro PAR FICHIER, et non par requête : deux pièces jointes
        # de 15 Mo dans le même formulaire sont deux fichiers acceptables.
        # C'est `Content-Length` ci-dessus qui borne le total.
        self.recu = 0

    def receive_data_chunk(self, raw_data, start):
        """Seconde barrière : on recompte, au cas où l'en-tête aurait menti.

        Rend `raw_data` tel quel — rendre `None` indiquerait aux
        gestionnaires suivants qu'il n'y a plus rien à écrire, et le fichier
        arriverait vide au lieu d'être refusé.
        """
        if self.plafond:
            self.recu += len(raw_data)
            if self.recu > self.plafond:
                raise RequestDataTooBig(
                    'Fichier trop volumineux : plafond de %d octets dépassé.'
                    % self.plafond)
        return raw_data

    def file_complete(self, file_size):
        """Ce gestionnaire ne produit aucun fichier : il ne fait que compter."""
        return None
