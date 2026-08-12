"""
apps/system_updates/server_actions.py — Redémarrage / extinction du serveur
hôte (VM Proxmox) depuis Orion ERP.

Programme l'action avec un court délai (1 minute par défaut) plutôt que de
l'exécuter immédiatement : `sudo reboot`/`shutdown -h now` couperait
gunicorn avant même que la réponse HTTP de confirmation ne parte, laissant
l'admin devant une page qui ne charge jamais sans savoir si l'action a
réellement été prise en compte.
"""
import platform

from apps.system_updates.git_service import run_command


class ServerActionError(Exception):
    pass


def _require_linux():
    if platform.system() != 'Linux':
        raise ServerActionError(
            "Action serveur disponible uniquement sur l'appliance Linux, "
            "pas sur ce poste de développement."
        )


def schedule_reboot(delay_minutes=1):
    _require_linux()
    result = run_command(f'sudo shutdown -r +{delay_minutes}', timeout=15)
    if not result['ok']:
        raise ServerActionError(result['stderr'] or result['stdout'] or 'Commande shutdown échouée.')
    return result


def schedule_shutdown(delay_minutes=1):
    _require_linux()
    result = run_command(f'sudo shutdown -h +{delay_minutes}', timeout=15)
    if not result['ok']:
        raise ServerActionError(result['stderr'] or result['stdout'] or 'Commande shutdown échouée.')
    return result


def cancel_scheduled_action():
    _require_linux()
    result = run_command('sudo shutdown -c', timeout=15)
    if not result['ok']:
        raise ServerActionError(result['stderr'] or result['stdout'] or 'Commande shutdown -c échouée.')
    return result
