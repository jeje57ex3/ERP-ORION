def user_is_super_admin(user):
    """Vrai pour un super-administrateur de l'ERP.

    La derniere branche filtrait « role='super_admin' » sur
    UserCompanyAccess.role, qui est une CLE ETRANGERE vers Role : Django
    tentait donc de convertir « super_admin » en identifiant entier et levait
    « ValueError: invalid literal for int() with base 10: 'super_admin' ».

    Consequence, et elle etait grave : cette fonction est appelee par
    can_use_ai(), donc par CHAQUE page et chaque requete de l'assistant. Tout
    utilisateur authentifie qui n'est ni superuser ni porteur d'un attribut
    « role » egal a super_admin tombait dans cette branche -- c'est-a-dire
    l'employe ordinaire, exactement celui que l'assistant doit guider. Il
    recevait une erreur 500. Le defaut restait invisible pour un
    administrateur, qui sort des la premiere branche.

    La requete corrigee porte sur le CODE du role (role__code), seule
    designation textuelle du modele Role. Ce chemin n'avait donc jamais
    fonctionne : le corriger plutot que le supprimer rend enfin utilisable un
    super-admin designe par son role, tout en reglant le plantage.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    if getattr(user, 'role', None) == 'super_admin':
        return True
    if hasattr(user, 'company_accesses'):
        return user.company_accesses.filter(
            role__code='super_admin', is_active=True,
        ).exists()
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
