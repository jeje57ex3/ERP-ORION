from django.conf import settings


def get_orion_public_context():
    return {
        "orion_login_url": getattr(settings, "ORION_PUBLIC_LOGIN_URL", "https://login.elysiums.fr/login/"),
        "windows_download_url": getattr(settings, "ORION_WINDOWS_APP_DOWNLOAD_URL", "#"),
        "android_download_url": getattr(settings, "ORION_ANDROID_APP_DOWNLOAD_URL", "#"),
        "apple_download_url": getattr(settings, "ORION_APPLE_APP_DOWNLOAD_URL", ""),
        "support_email": getattr(settings, "ORION_SUPPORT_EMAIL", "support@elysiums.fr"),
    }
