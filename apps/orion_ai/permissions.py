def user_is_super_admin(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if getattr(user, 'role', None) == 'super_admin':
        return True
    if hasattr(user, 'company_accesses'):
        return user.company_accesses.filter(role='super_admin', is_active=True).exists()
    return False


def can_use_ai(user):
    if not user or not user.is_authenticated:
        return False
    if user_is_super_admin(user):
        return True
    if user.has_perm('orion_ai.use_ai_assistant'):
        return True
    return True


def can_use_ai_tools(user):
    if user_is_super_admin(user):
        return True
    if user.has_perm('orion_ai.use_ai_tools'):
        return True
    return False


def can_execute_ai_write_actions(user):
    if user_is_super_admin(user):
        return True
    if user.has_perm('orion_ai.execute_ai_write_actions'):
        return True
    return False


def can_execute_dangerous_ai_actions(user):
    if user_is_super_admin(user):
        return True
    if user.has_perm('orion_ai.execute_dangerous_ai_actions'):
        return True
    return False
