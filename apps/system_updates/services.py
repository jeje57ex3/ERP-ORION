from django.conf import settings

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
    check.changelog = changelog
    check.raw_payload = {'fetch': fetch_result}

    # NE PAS SAVOIR N'EST PAS ETRE A JOUR.
    #
    # `get_commits_behind_ahead` rendait (0, 0) quand sa commande echouait,
    # et cette ligne concluait « up_to_date ». L'ERP affirmait donc etre a
    # jour alors qu'il ne pouvait pas le dire -- le pire des messages,
    # puisqu'il dissuade d'aller voir.
    if behind is None:
        check.status = 'failed'
        check.error_message = (
            'Comparaison impossible avec %s/%s. Le depot a bien ete '
            "recupere, mais git n'a pas pu dire ou en est cette "
            'installation. Verifiez la branche suivie : cette machine est '
            'sur « %s ».' % (
                getattr(settings, 'ORION_GIT_REMOTE', 'origin'),
                getattr(settings, 'ORION_GIT_BRANCH', 'main'),
                check.branch or 'inconnue'))
        check.save()
        return check

    check.commits_behind = behind
    check.commits_ahead = ahead

    # La branche SUIVIE et la branche COMPAREE doivent etre la meme, sans
    # quoi la reponse porte sur autre chose que ce que la mise a jour
    # tirera. Une machine sur « APPA » comparee a « main » peut se croire a
    # jour tout en recevant un autre code.
    branche_attendue = getattr(settings, 'ORION_GIT_BRANCH', 'main')
    if check.branch and check.branch != branche_attendue:
        check.status = 'failed'
        check.error_message = (
            'Cette installation suit la branche « %s », mais la '
            'comparaison porte sur « %s ». Le resultat ne dirait rien de '
            'ce que la mise a jour tirerait reellement.'
            % (check.branch, branche_attendue))
        check.save()
        return check

    check.status = 'update_available' if behind > 0 else 'up_to_date'
    check.save()
    return check
