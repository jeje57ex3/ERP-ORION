import json
from pathlib import Path

from config import DEFAULT_ERP_URL


APP_DIR = Path.home() / "AppData" / "Local" / "OrionERPDesktop"
SETTINGS_FILE = APP_DIR / "settings.json"


DEFAULT_SETTINGS = {
    "erp_url": DEFAULT_ERP_URL,
    "window_width": 1400,
    "window_height": 900,
    "start_maximized": True,
}


def ensure_app_dir():
    APP_DIR.mkdir(parents=True, exist_ok=True)


def load_settings():
    ensure_app_dir()

    if not SETTINGS_FILE.exists():
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()

    try:
        with SETTINGS_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        merged = DEFAULT_SETTINGS.copy()
        merged.update(data)
        return merged

    except Exception:
        save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()


def save_settings(settings):
    ensure_app_dir()

    with SETTINGS_FILE.open("w", encoding="utf-8") as file:
        json.dump(settings, file, indent=2, ensure_ascii=False)
