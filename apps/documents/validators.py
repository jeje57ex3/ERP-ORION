"""
apps/documents/validators.py — Validation sécurisée des fichiers uploadés

Utilisation dans un modèle :
    from apps.documents.validators import validate_document_file
    file = models.FileField(validators=[validate_document_file])
"""
import os
import re
import logging
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger('orion')

ALLOWED_EXTENSIONS = {
    'pdf', 'jpg', 'jpeg', 'png', 'gif', 'webp',
    'doc', 'docx', 'xls', 'xlsx', 'csv', 'txt',
    'odt', 'ods', 'ppt', 'pptx', 'zip',
}

SENSITIVE_EXTENSIONS = {'exe', 'bat', 'cmd', 'sh', 'ps1', 'js', 'php', 'py', 'rb'}

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 Mo par défaut
MAX_SENSITIVE_FILE_SIZE = 50 * 1024 * 1024  # 50 Mo pour documents comptables/RH

DANGEROUS_NAME_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _get_extension(filename: str) -> str:
    """Retourne l'extension en minuscules sans le point."""
    return os.path.splitext(filename)[-1].lstrip('.').lower()


def validate_file_extension(value, allowed: set = None):
    """Valide l'extension du fichier."""
    ext = _get_extension(value.name)
    allowed = allowed or ALLOWED_EXTENSIONS

    if ext in SENSITIVE_EXTENSIONS:
        raise ValidationError(
            _("Les fichiers exécutables ne sont pas autorisés (.%(ext)s)."),
            params={'ext': ext},
        )
    if ext not in allowed:
        raise ValidationError(
            _("Extension .%(ext)s non autorisée. Formats acceptés : %(allowed)s."),
            params={'ext': ext, 'allowed': ', '.join(sorted(allowed))},
        )


def validate_file_size(value, max_size: int = MAX_FILE_SIZE):
    """Valide la taille du fichier."""
    if hasattr(value, 'size') and value.size > max_size:
        raise ValidationError(
            _("Fichier trop volumineux (%(size)s). Taille maximale : %(max)s."),
            params={
                'size': _human_size(value.size),
                'max': _human_size(max_size),
            },
        )


def validate_filename(value):
    """Valide le nom du fichier (caractères dangereux)."""
    name = os.path.basename(value.name)
    if DANGEROUS_NAME_PATTERN.search(name):
        raise ValidationError(_("Le nom du fichier contient des caractères non autorisés."))
    if len(name) > 255:
        raise ValidationError(_("Le nom du fichier est trop long (255 caractères max)."))


def validate_document_file(value):
    """Validateur complet pour les documents métier standard."""
    validate_filename(value)
    validate_file_extension(value)
    validate_file_size(value)


def validate_image_file(value):
    """Validateur pour les images."""
    validate_filename(value)
    validate_file_extension(value, allowed={'jpg', 'jpeg', 'png', 'gif', 'webp'})
    validate_file_size(value, max_size=5 * 1024 * 1024)  # 5 Mo


def validate_sensitive_document(value):
    """Validateur pour documents sensibles (RH, comptabilité)."""
    validate_filename(value)
    validate_file_extension(value, allowed={'pdf', 'doc', 'docx', 'xls', 'xlsx', 'jpg', 'jpeg', 'png'})
    validate_file_size(value, max_size=MAX_SENSITIVE_FILE_SIZE)


def _human_size(size: int) -> str:
    """Convertit une taille en octets en format lisible."""
    for unit in ['o', 'Ko', 'Mo', 'Go']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} To"
