import keyring

KEYRING_SERVICE = "OrionERPDesktop"
_KEY_USERNAME = "username"
_KEY_PASSWORD = "password"


def save_credentials(username: str, password: str):
    keyring.set_password(KEYRING_SERVICE, _KEY_USERNAME, username)
    keyring.set_password(KEYRING_SERVICE, _KEY_PASSWORD, password)


def get_username() -> str:
    return keyring.get_password(KEYRING_SERVICE, _KEY_USERNAME) or ""


def get_password() -> str:
    return keyring.get_password(KEYRING_SERVICE, _KEY_PASSWORD) or ""


def has_credentials() -> bool:
    return bool(get_username())


def clear_credentials():
    try:
        keyring.delete_password(KEYRING_SERVICE, _KEY_USERNAME)
    except Exception:
        pass
    try:
        keyring.delete_password(KEYRING_SERVICE, _KEY_PASSWORD)
    except Exception:
        pass
