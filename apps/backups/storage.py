"""
apps/backups/storage.py — Envoi/lecture des fichiers de sauvegarde vers/depuis
une destination externe (autre disque local, ou partage réseau SMB/CIFS).

Les commandes de sauvegarde (mysqldump, zip) écrivent toujours d'abord un
fichier temporaire local (storage/backups/... — disque toujours disponible,
pas de dépendance réseau pendant l'opération elle-même) ; ce module se
charge ensuite de le publier vers la destination configurée par défaut, si
une destination active existe.

Le partage SMB utilise smbprotocol (client SMB2/3 pur Python, pas de
montage OS requis — fonctionne identiquement en dev Windows et sur
l'appliance Proxmox/Linux en production).
"""
import os
import shutil
import logging
from pathlib import Path

logger = logging.getLogger('backups')


def get_default_destination():
    from .models import BackupDestination
    return BackupDestination.objects.filter(is_active=True, is_default=True).first()


def _smb_session(destination):
    import smbclient
    smbclient.register_session(
        destination.smb_server,
        username=destination.smb_username or None,
        password=destination.smb_password or None,
        # smbprotocol accepte "DOMAIN\\user" — plus simple de laisser le
        # domaine dans smb_username que d'ajouter un paramètre non standard.
    )
    return smbclient


def _smb_remote_path(destination, filename):
    sub = destination.smb_path.strip('\\/').replace('/', '\\')
    base = f'\\\\{destination.smb_server}\\{destination.smb_share}'
    return f'{base}\\{sub}\\{filename}' if sub else f'{base}\\{filename}'


def publish(local_path: str, destination=None) -> str:
    """Envoie le fichier local vers la destination (si configurée) et
    retourne le chemin final à stocker dans BackupJob.file_path. Supprime
    le fichier temporaire local une fois transféré. Si aucune destination
    n'est configurée, laisse le fichier en place et retourne son chemin
    inchangé."""
    destination = destination if destination is not None else get_default_destination()
    if destination is None:
        return local_path

    filename = Path(local_path).name

    if destination.destination_type == 'local':
        dest_dir = Path(destination.local_path)
        dest_dir.mkdir(parents=True, exist_ok=True)
        final_path = dest_dir / filename
        shutil.move(local_path, final_path)
        return str(final_path)

    if destination.destination_type == 'smb':
        smbclient = _smb_session(destination)
        remote_dir = _smb_remote_path(destination, '').rstrip('\\')
        smbclient.makedirs(remote_dir, exist_ok=True)
        remote_path = _smb_remote_path(destination, filename)
        with open(local_path, 'rb') as src, smbclient.open_file(remote_path, mode='wb') as dst:
            shutil.copyfileobj(src, dst)
        os.remove(local_path)
        return remote_path

    return local_path


def open_read(job):
    """Fichier ouvert en lecture binaire pour un BackupJob, quelle que soit
    sa destination (utilisé par le téléchargement et la restauration)."""
    if job.destination_id and job.destination.destination_type == 'smb':
        smbclient = _smb_session(job.destination)
        return smbclient.open_file(job.file_path, mode='rb')
    return open(job.file_path, 'rb')


def path_exists(job) -> bool:
    if not job.file_path:
        return False
    if job.destination_id and job.destination.destination_type == 'smb':
        try:
            smbclient = _smb_session(job.destination)
            return smbclient.path.exists(job.file_path)
        except Exception:
            return False
    return os.path.exists(job.file_path)


def delete_file(job):
    if not job.file_path:
        return
    if job.destination_id and job.destination.destination_type == 'smb':
        try:
            smbclient = _smb_session(job.destination)
            smbclient.remove(job.file_path)
        except Exception:
            logger.exception('Suppression SMB impossible pour %s', job.file_path)
        return
    try:
        if os.path.exists(job.file_path):
            os.remove(job.file_path)
    except OSError:
        logger.exception('Suppression locale impossible pour %s', job.file_path)


def test_destination(destination):
    """Écrit puis supprime un petit fichier témoin. Retourne (ok, message)."""
    probe_name = '.orion_backup_test'
    try:
        if destination.destination_type == 'local':
            dest_dir = Path(destination.local_path)
            dest_dir.mkdir(parents=True, exist_ok=True)
            probe = dest_dir / probe_name
            probe.write_text('orion backup connectivity test')
            probe.unlink()
            return True, f'Écriture OK dans {destination.local_path}.'

        if destination.destination_type == 'smb':
            smbclient = _smb_session(destination)
            remote_dir = _smb_remote_path(destination, '').rstrip('\\')
            smbclient.makedirs(remote_dir, exist_ok=True)
            remote_probe = _smb_remote_path(destination, probe_name)
            with smbclient.open_file(remote_probe, mode='wb') as f:
                f.write(b'orion backup connectivity test')
            smbclient.remove(remote_probe)
            return True, f'Connexion et écriture OK sur {destination.smb_unc_root}.'

        return False, 'Type de destination inconnu.'
    except Exception as exc:
        return False, str(exc)
