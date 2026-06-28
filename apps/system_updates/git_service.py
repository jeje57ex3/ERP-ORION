import subprocess
from pathlib import Path

from django.conf import settings


def run_command(command, cwd=None, timeout=300):
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
        'command': command,
    }


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
    return run_command(f'git fetch {remote}', cwd=get_project_root(), timeout=600)


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


def pull_latest():
    remote = getattr(settings, 'ORION_GIT_REMOTE', 'origin')
    branch = getattr(settings, 'ORION_GIT_BRANCH', 'main')
    return run_command(f'git pull {remote} {branch}', cwd=get_project_root(), timeout=1200)


def hard_reset_to_commit(commit):
    return run_command(f'git reset --hard {commit}', cwd=get_project_root(), timeout=600)
