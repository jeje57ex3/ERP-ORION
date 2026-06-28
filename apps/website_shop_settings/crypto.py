from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def get_fernet():
    key = getattr(settings, 'ORION_SECRET_ENCRYPTION_KEY', None)
    if not key:
        raise RuntimeError('ORION_SECRET_ENCRYPTION_KEY manquante dans les settings.')
    return Fernet(key.encode())


def encrypt_secret(value):
    if not value:
        return ''
    return get_fernet().encrypt(value.encode()).decode()


def decrypt_secret(value):
    if not value:
        return ''
    try:
        return get_fernet().decrypt(value.encode()).decode()
    except (InvalidToken, Exception):
        return ''
