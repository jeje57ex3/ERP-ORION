from pathlib import Path

from django.conf import settings


def _get_maintenance_file():
    return Path(settings.BASE_DIR) / 'maintenance.lock'


def enable_maintenance_mode():
    _get_maintenance_file().write_text('maintenance', encoding='utf-8')


def disable_maintenance_mode():
    path = _get_maintenance_file()
    if path.exists():
        path.unlink()


def is_maintenance_mode_enabled():
    return _get_maintenance_file().exists()
