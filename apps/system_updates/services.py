from apps.system_updates.git_service import (
    fetch_remote,
    get_changelog,
    get_commits_behind_ahead,
    get_current_branch,
    get_current_commit,
    get_remote_commit,
)
from apps.system_updates.models import SystemUpdateCheck


def get_current_version():
    try:
        from core.version import ORION_VERSION
        return ORION_VERSION
    except Exception:
        return ''


def check_for_updates(user=None):
    check = SystemUpdateCheck.objects.create(
        status='checking',
        current_version=get_current_version(),
        current_commit=get_current_commit(),
        branch=get_current_branch(),
        checked_by=user,
    )

    fetch_result = fetch_remote()

    if not fetch_result['ok']:
        check.status = 'failed'
        check.error_message = fetch_result['stderr'] or fetch_result['stdout']
        check.raw_payload = {'fetch': fetch_result}
        check.save()
        return check

    remote_commit = get_remote_commit()
    behind, ahead = get_commits_behind_ahead()
    changelog = get_changelog()

    check.remote_commit = remote_commit
    check.commits_behind = behind
    check.commits_ahead = ahead
    check.changelog = changelog
    check.raw_payload = {'fetch': fetch_result}
    check.status = 'update_available' if behind > 0 else 'up_to_date'
    check.save()
    return check
