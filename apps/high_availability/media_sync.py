"""Synchronisation des fichiers téléversés entre serveurs.

La base se réplique, les fichiers non. Or une facture dont le PDF manque, un
devis sans son plan joint ou un produit sans photo sont des données
incomplètes : après une bascule, l'ERP afficherait des enregistrements
corrects pointant vers des fichiers absents. Les champs `media_sync_status` et
`media_last_sync_at` existaient sur le modèle et étaient affichés dans
l'administration, mais rien ne les écrivait — aucune synchronisation n'avait
jamais eu lieu.

Sens de la copie : toujours **depuis le serveur actif vers les autres**. Le
serveur actif est le seul à recevoir des téléversements, puisque la protection
en écriture refuse les requêtes modifiantes ailleurs. Copier dans l'autre sens
écraserait des fichiers récents par des anciens.

La construction de la commande est une fonction pure, séparée de son
exécution : c'est ce qui permet de vérifier les options choisies — et
notamment l'absence de `--delete` — sans rien copier.
"""

import shlex
import subprocess

from django.conf import settings
from django.utils import timezone

from apps.high_availability.mesh import MeshConfigError, adresse_overlay
from apps.high_availability.models import OrionHANode, OrionHASettings

DELAI_SECONDES = 1800


def construire_commande(destination, *, source_dir, dest_dir, cle_ssh='', port=22):
    """Commande rsync pour pousser les médias vers `destination`.

    Choix d'options, chacun pour une raison précise :

    - `-a` conserve droits, dates et liens symboliques. Les dates comptent :
      c'est sur elles que rsync décide quoi recopier.
    - `--partial` reprend un transfert interrompu au lieu de recommencer. Sur
      un lien entre sites et des téléversements de plusieurs centaines de Mo,
      la différence est considérable.
    - **PAS de `--delete`**, volontairement. Un fichier absent de la source
      n'est pas forcément à détruire sur la destination : il peut provenir
      d'une bascule précédente, où l'autre serveur a reçu des téléversements.
      Supprimer serait irréversible, et ce qu'on gagnerait en place ne vaut
      pas ce qu'on risquerait de perdre.
    - `-e ssh` avec un port explicite : sur le réseau privé, ssh suffit et
      évite d'exposer un démon rsync.
    """
    source = source_dir.rstrip('/') + '/'
    transport = f'ssh -p {int(port)} -o BatchMode=yes -o StrictHostKeyChecking=accept-new'
    if cle_ssh:
        transport += f' -i {shlex.quote(cle_ssh)}'

    return [
        'rsync', '-a', '--partial', '--compress',
        '--timeout', '600',
        '-e', transport,
        source,
        f'orion@{destination}:{dest_dir.rstrip("/")}/',
    ]


def cibles_de_synchronisation(settings_obj=None):
    """Serveurs vers lesquels pousser, et pourquoi les autres sont écartés.

    Ne retourne des cibles que si CE serveur est l'actif : lui seul reçoit des
    téléversements, et pousser depuis un passif écraserait du récent par de
    l'ancien.
    """
    settings_obj = settings_obj or OrionHASettings.get_solo()
    notre_id = getattr(settings, 'ORION_NODE_ID', '')

    actif = OrionHANode.objects.filter(is_current_active=True).first()
    if not actif:
        return [], 'Aucun serveur actif : rien à synchroniser.'
    if actif.node_id != notre_id:
        return [], (
            f'Ce serveur ({notre_id or "?"}) n\'est pas l\'actif '
            f'({actif.node_id}) : la copie ne part que de l\'actif.'
        )

    cibles = []
    for node in OrionHANode.objects.filter(is_enabled=True).exclude(node_id=notre_id):
        if not node.priority:
            continue
        try:
            adresse = adresse_overlay(settings_obj, node.priority)
        except MeshConfigError:
            continue
        cibles.append({'node': node, 'adresse': adresse})

    if not cibles:
        return [], 'Aucun autre serveur joignable par le réseau privé.'
    return cibles, ''


def synchroniser(settings_obj=None, executer=True):
    """Pousse les médias vers chaque autre serveur et consigne le résultat.

    `executer=False` construit tout sans rien copier : sert aux essais et au
    diagnostic.
    """
    settings_obj = settings_obj or OrionHASettings.get_solo()

    if not settings_obj.media_sync_enabled:
        return {'skipped': True, 'reason': 'Synchronisation des médias désactivée.', 'resultats': []}

    cibles, motif = cibles_de_synchronisation(settings_obj)
    if not cibles:
        return {'skipped': True, 'reason': motif, 'resultats': []}

    source_dir = str(getattr(settings, 'MEDIA_ROOT', '') or '')
    if not source_dir:
        return {'skipped': True, 'reason': 'MEDIA_ROOT non défini.', 'resultats': []}

    resultats = []
    for cible in cibles:
        node = cible['node']
        commande = construire_commande(
            cible['adresse'],
            source_dir=source_dir,
            dest_dir=source_dir,
            cle_ssh=getattr(settings, 'ORION_MEDIA_SYNC_SSH_KEY', ''),
        )

        ligne = {'node_id': node.node_id, 'adresse': cible['adresse'], 'commande': commande}

        if not executer:
            ligne.update({'ok': None, 'detail': 'Non exécuté (mode constat).'})
            resultats.append(ligne)
            continue

        try:
            proc = subprocess.run(
                commande, capture_output=True, text=True, timeout=DELAI_SECONDES,
            )
            ligne['ok'] = proc.returncode == 0
            ligne['detail'] = (
                (proc.stderr or proc.stdout or '').strip()[:500]
                or 'Synchronisation terminée.'
            )
        except subprocess.TimeoutExpired:
            ligne['ok'] = False
            ligne['detail'] = f'Délai de {DELAI_SECONDES} s dépassé.'
        except FileNotFoundError:
            ligne['ok'] = False
            ligne['detail'] = "rsync n'est pas installé sur ce serveur."

        # Le statut est écrit sur le nœud DESTINATION : c'est son contenu qui
        # est à jour ou non, et c'est ce que la page affiche par serveur.
        node.media_sync_status = 'ok' if ligne['ok'] else 'error'
        if ligne['ok']:
            node.media_last_sync_at = timezone.now()
        node.save(update_fields=['media_sync_status', 'media_last_sync_at', 'updated_at'])

        resultats.append(ligne)

    return {'skipped': False, 'reason': '', 'resultats': resultats}
