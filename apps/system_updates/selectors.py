from apps.system_updates.models import (
    ServerActionLog,
    SystemUpdateCheck,
    SystemUpdateRun,
    SystemUpdateSettings,
)


def get_update_settings():
    return SystemUpdateSettings.get_solo()


def get_latest_update_check():
    return SystemUpdateCheck.objects.first()


def get_latest_update_run():
    return SystemUpdateRun.objects.first()


def get_recent_update_runs(limit=20):
    return SystemUpdateRun.objects.all()[:limit]


def has_update_running():
    return SystemUpdateRun.objects.filter(status='running').exists()


def get_recent_server_actions(limit=10):
    return ServerActionLog.objects.select_related('executed_by')[:limit]
