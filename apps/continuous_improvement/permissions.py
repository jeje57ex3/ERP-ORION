from .models import PDCACycle


def can_view_pdca(user, cycle: PDCACycle) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, 'is_super_admin', False):
        return True
    if cycle.owner_id == user.pk or cycle.created_by_id == user.pk:
        return True
    if hasattr(user, 'profile') and getattr(user.profile, 'company', None) == cycle.company:
        return True
    return False


def can_edit_pdca(user, cycle: PDCACycle) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, 'is_super_admin', False):
        return True
    if cycle.status in ('completed', 'cancelled', 'closed'):
        return False
    if cycle.owner_id == user.pk or cycle.created_by_id == user.pk:
        return True
    return False


def can_advance_stage(user, cycle: PDCACycle) -> bool:
    return can_edit_pdca(user, cycle)


def can_close_pdca(user, cycle: PDCACycle) -> bool:
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, 'is_super_admin', False):
        return True
    return cycle.owner_id == user.pk


def can_manage_templates(user) -> bool:
    return user and user.is_authenticated and (
        user.is_superuser or getattr(user, 'is_super_admin', False)
    )
