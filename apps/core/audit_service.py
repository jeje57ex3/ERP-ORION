"""
apps/core/audit_service.py — Service d'audit centralisé Orion ERP

Utilisation :
    from apps.core.audit_service import log_action

    log_action(request, 'create', 'crm', obj=customer)
    log_action(request, 'delete', 'sales', obj=invoice, description="Facture supprimée par erreur")
    log_action(request, 'validate', 'accounting', obj=entry, old_values={'status':'draft'}, new_values={'status':'validated'})
"""
import logging
from typing import Optional

logger = logging.getLogger('orion')


def _get_ip(request) -> Optional[str]:
    if request is None:
        return None
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _get_user_agent(request) -> str:
    if request is None:
        return ''
    return request.META.get('HTTP_USER_AGENT', '')[:500]


def _obj_repr(obj) -> str:
    if obj is None:
        return ''
    try:
        return str(obj)[:200]
    except Exception:
        return repr(obj)[:200]


def _obj_id(obj) -> str:
    if obj is None:
        return ''
    try:
        return str(obj.pk)
    except Exception:
        return ''


def _model_name(obj) -> str:
    if obj is None:
        return ''
    try:
        return obj.__class__.__name__
    except Exception:
        return ''


def log_action(
    request,
    action: str,
    module: str = '',
    obj=None,
    old_values: dict = None,
    new_values: dict = None,
    description: str = '',
    company=None,
    user=None,
) -> None:
    """
    Enregistre une action dans le journal d'audit.

    Args:
        request:     requête Django (peut être None pour les tâches async)
        action:      code action (create/update/delete/login/validate/...)
        module:      module ERP (crm/sales/accounting/btp/...)
        obj:         instance du modèle concerné (optionnel)
        old_values:  dict des anciennes valeurs (pour update)
        new_values:  dict des nouvelles valeurs (pour update)
        description: texte libre complémentaire
        company:     entreprise (si non disponible via request)
        user:        utilisateur (si non disponible via request)
    """
    try:
        from apps.core.models import AuditLog

        resolved_user = user
        resolved_company = company

        if request is not None:
            if resolved_user is None and request.user.is_authenticated:
                resolved_user = request.user
            if resolved_company is None:
                resolved_company = getattr(request, 'current_company', None)

        AuditLog.objects.create(
            user=resolved_user,
            company=resolved_company,
            action=action,
            module=module,
            model_name=_model_name(obj),
            object_id=_obj_id(obj),
            object_repr=_obj_repr(obj),
            old_values=old_values,
            new_values=new_values,
            description=description,
            ip_address=_get_ip(request),
            user_agent=_get_user_agent(request),
        )
    except Exception as e:
        logger.warning("Échec enregistrement audit: %s", e)


def log_login(request, user):
    log_action(request, 'login', module='accounts', description=f"Connexion: {user.username}", user=user)


def log_logout(request, user):
    log_action(request, 'logout', module='accounts', description=f"Déconnexion: {user.username}", user=user)


def log_create(request, obj, module: str = ''):
    log_action(request, 'create', module=module, obj=obj)


def log_update(request, obj, old_values: dict = None, new_values: dict = None, module: str = ''):
    log_action(request, 'update', module=module, obj=obj, old_values=old_values, new_values=new_values)


def log_delete(request, obj, module: str = ''):
    log_action(request, 'delete', module=module, obj=obj, description=f"Supprimé: {_obj_repr(obj)}")


def log_validate(request, obj, module: str = ''):
    log_action(request, 'validate', module=module, obj=obj)


def log_payment(request, obj, amount=None, module: str = 'sales'):
    desc = f"Paiement: {amount}" if amount else ''
    log_action(request, 'payment', module=module, obj=obj, description=desc)


def log_export(request, module: str, description: str = ''):
    log_action(request, 'export', module=module, description=description)


def log_download(request, obj, module: str = 'documents'):
    log_action(request, 'download', module=module, obj=obj)


def log_upload(request, obj, module: str = 'documents'):
    log_action(request, 'upload', module=module, obj=obj)


def log_db_backup(company, filepath: str, user=None):
    log_action(None, 'db_backup', module='core', company=company, user=user,
               description=f"Sauvegarde: {filepath}")


def log_db_create(company, user=None):
    log_action(None, 'db_create', module='core', company=company, user=user,
               description=f"Base créée: {company.database_name}")
