import base64
import subprocess
from pathlib import Path

from django.conf import settings


def run_command(command, cwd=None, timeout=300, display_command=None):
    result = subprocess.run(
        command,
        cwd=cwd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {
        'returncode': result.returncode,
        'stdout': result.stdout.strip(),
        'stderr': result.stderr.strip(),
        'ok': result.returncode == 0,
        'command': display_command if display_command is not None else command,
    }


def _github_token():
    try:
        from apps.system_updates.models import SystemUpdateSettings
        from apps.website_shop_settings.crypto import decrypt_secret
    except Exception:
        return ''
    obj = SystemUpdateSettings.get_solo()
    return decrypt_secret(obj.github_token_encrypted) if obj.github_token_encrypted else ''


def _authenticated_git_command(subcommand):
    """Construit une commande git authentifiée (dépôt privé) sans jamais écrire le
    jeton sur disque (.git/config) ni dans l'URL — un en-tête HTTP temporaire, valable
    uniquement pour cette invocation, via `-c http.extraheader`.
    Retourne (commande réelle à exécuter, commande à journaliser/afficher — sans jeton).
    """
    display = f'git {subcommand}'
    token = _github_token()
    if not token:
        return display, display
    basic = base64.b64encode(f'x-access-token:{token}'.encode()).decode()
    real = f'git -c http.extraheader="AUTHORIZATION: basic {basic}" {subcommand}'
    return real, display


def get_project_root():
    configured = getattr(settings, 'ORION_PROJECT_ROOT', '')
    if configured:
        p = Path(configured)
        if p.exists() and p.is_dir():
            return p
    return Path(settings.BASE_DIR)


def get_current_commit():
    result = run_command('git rev-parse HEAD', cwd=get_project_root())
    return result['stdout'] if result['ok'] else ''


def get_current_branch():
    result = run_command('git rev-parse --abbrev-ref HEAD', cwd=get_project_root())
    return result['stdout'] if result['ok'] else ''


def fetch_remote():
    remote = getattr(settings, 'ORION_GIT_REMOTE', 'origin')
    real, display = _authenticated_git_command(f'fetch {remote}')
    return run_command(real, cwd=get_project_root(), timeout=600, display_command=display)


def get_remote_commit():
    remote = getattr(settings, 'ORION_GIT_REMOTE', 'origin')
    branch = getattr(settings, 'ORION_GIT_BRANCH', 'main')
    result = run_command(f'git rev-parse {remote}/{branch}', cwd=get_project_root())
    return result['stdout'] if result['ok'] else ''


def get_commits_behind_ahead():
    remote = getattr(settings, 'ORION_GIT_REMOTE', 'origin')
    branch = getattr(settings, 'ORION_GIT_BRANCH', 'main')
    result = run_command(
        f'git rev-list --left-right --count HEAD...{remote}/{branch}',
        cwd=get_project_root(),
    )
    if not result['ok']:
        return 0, 0
    parts = result['stdout'].split()
    if len(parts) != 2:
        return 0, 0
    return int(parts[1]), int(parts[0])  # behind, ahead


def get_changelog(max_count=20):
    remote = getattr(settings, 'ORION_GIT_REMOTE', 'origin')
    branch = getattr(settings, 'ORION_GIT_BRANCH', 'main')
    result = run_command(
        f'git log --oneline HEAD..{remote}/{branch} -n {max_count}',
        cwd=get_project_root(),
    )
    return result['stdout'] if result['ok'] else ''


def build_pull_command(remote=None, branch=None):
    """Retourne (commande réelle, commande à journaliser) pour `git pull` — utilisé
    ici et par update_runner.py, pour ne construire la logique d'auth qu'à un seul
    endroit."""
    remote = remote or getattr(settings, 'ORION_GIT_REMOTE', 'origin')
    branch = branch or getattr(settings, 'ORION_GIT_BRANCH', 'main')
    return _authenticated_git_command(f'pull {remote} {branch}')


def pull_latest():
    real, display = build_pull_command()
    return run_command(real, cwd=get_project_root(), timeout=1200, display_command=display)


def hard_reset_to_commit(commit):
    return run_command(f'git reset --hard {commit}', cwd=get_project_root(), timeout=600)
