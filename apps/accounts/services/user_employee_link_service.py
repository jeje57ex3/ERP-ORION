"""
accounts/services/user_employee_link_service.py
Service de liaison utilisateur ↔ salarié.

Règles :
- superuser, is_staff, rôle superadmin/admin → exemptés (pas besoin de fiche salarié)
- profil marqué « compte sans fiche salarié » → exempté lui aussi
- tous les autres utilisateurs internes → doivent avoir une fiche Employee liée
- un Employee ne peut être lié qu'à un seul User (OneToOne côté Employee)
- un User ne peut être lié qu'à un seul Employee

Tous les comptes ne sont pas des salariés : un prestataire, un
expert-comptable externe, un compte de service ont besoin d'accéder à l'ERP
sans figurer au registre du personnel. Le profil porte donc une case
`without_employee_record` qui distingue ce choix délibéré d'un OUBLI de
rattachement -- distinction que perdrait une simple suppression de la
validation.
"""
from django.core.exceptions import ValidationError
from django.db import transaction


# ---------------------------------------------------------------------------
# Détection exemption
# ---------------------------------------------------------------------------

EXEMPT_ROLES = ('superadmin', 'admin')


def is_user_exempt_from_employee_link(user):
    """Retourne True si l'utilisateur n'est PAS obligé d'avoir une fiche salarié."""
    if user is None or not getattr(user, 'pk', None):
        return True
    if getattr(user, 'is_superuser', False):
        return True
    if getattr(user, 'is_staff', False):
        return True
    try:
        profil = user.profile
    except Exception:
        return False
    # Case cochee a la creation du compte : l'absence de fiche est voulue.
    if getattr(profil, 'without_employee_record', False):
        return True
    return profil.role in EXEMPT_ROLES


def user_requires_employee(user):
    return not is_user_exempt_from_employee_link(user)


# ---------------------------------------------------------------------------
# Accès
# ---------------------------------------------------------------------------

def get_user_employee(user):
    """Retourne la fiche Employee liée à cet utilisateur, ou None."""
    if user is None:
        return None
    try:
        return user.employee_profile
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Salariés rattachables, et pourquoi il n'y en a pas
# ---------------------------------------------------------------------------

def salaries_rattachables(company):
    """Les salariés de cette entreprise qu'on peut encore lier à un compte.

    Trois conditions, et chacune en exclut pour une raison différente :
    l'entreprise (Employee.company), l'activité (is_active), et le fait de
    ne pas être DÉJÀ lié — `Employee.user` est un OneToOne, un salarié ne
    peut donc pas porter deux comptes.
    """
    from apps.hr.models import Employee

    if company is None:
        # Sans entreprise courante, lister les salariés de TOUTES les
        # sociétés : c'est ce que faisait l'écran, et c'était une fuite.
        # Mieux vaut une liste vide, que le diagnostic explique.
        return Employee.objects.none()
    return Employee.objects.filter(
        company=company, is_active=True, user__isnull=True,
    ).order_by('last_name', 'first_name')


def diagnostic_rattachement(company):
    """Pourquoi la liste des salariés est vide, quand elle l'est.

    Un `<select>` vide sans un mot d'explication envoie chercher la cause
    dans la base de données. Les trois raisons n'ont pas du tout le même
    remède : créer des fiches salarié, changer d'entreprise courante, ou
    constater que tout le monde a déjà un compte.

    Retourne un dict, toujours les mêmes clés, pour que le gabarit n'ait
    pas à tester l'existence de chacune.
    """
    from apps.hr.models import Employee

    infos = {
        'cause': None,
        'rattachables': 0,
        'deja_rattaches': 0,
        'desactives': 0,
        'total': 0,
        'company': company,
    }

    if company is None:
        infos['cause'] = 'sans_entreprise'
        return infos

    tous = Employee.objects.filter(company=company)
    infos['total'] = tous.count()
    infos['rattachables'] = salaries_rattachables(company).count()
    infos['desactives'] = tous.filter(is_active=False).count()
    infos['deja_rattaches'] = tous.filter(
        is_active=True, user__isnull=False).count()

    if infos['rattachables']:
        return infos
    if infos['total'] == 0:
        infos['cause'] = 'aucun_salarie'
    elif infos['deja_rattaches'] and not infos['desactives']:
        infos['cause'] = 'tous_rattaches'
    elif infos['desactives'] and not infos['deja_rattaches']:
        infos['cause'] = 'tous_desactives'
    else:
        infos['cause'] = 'rattaches_ou_desactives'
    return infos


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_user_employee_link(user, employee=None):
    """
    Lève ValidationError si l'utilisateur n'est pas exempté ET n'a pas de fiche
    salarié (ni celle fournie, ni une existante).
    """
    if is_user_exempt_from_employee_link(user):
        return True
    if employee or get_user_employee(user):
        return True
    raise ValidationError(
        "Cet utilisateur doit être lié à une fiche salarié."
    )


# ---------------------------------------------------------------------------
# Liaison
# ---------------------------------------------------------------------------

@transaction.atomic
def link_user_to_employee(user, employee):
    """
    Lie user à employee.
    - Vérifie que l'employee n'est pas déjà lié à un autre user.
    - Vérifie que le user n'est pas déjà lié à un autre employee.
    - Complète les champs manquants de l'employee depuis le user.
    """
    if not user:
        raise ValidationError("Utilisateur manquant.")
    if not employee:
        raise ValidationError("Salarié manquant.")

    if employee.user_id and employee.user_id != user.pk:
        raise ValidationError("Ce salarié est déjà lié à un autre compte utilisateur.")

    existing = get_user_employee(user)
    if existing and existing.pk != employee.pk:
        raise ValidationError("Cet utilisateur est déjà lié à un autre salarié.")

    employee.user = user

    # Compléter les champs vides depuis le compte utilisateur
    if not employee.email and getattr(user, 'email', None):
        employee.email = user.email
    if not employee.first_name and getattr(user, 'first_name', None):
        employee.first_name = user.first_name
    if not employee.last_name and getattr(user, 'last_name', None):
        employee.last_name = user.last_name

    employee.save()

    # Le compte a désormais une fiche : la déclaration « sans fiche salarié »
    # devient fausse. La laisser exempterait définitivement ce compte des
    # contrôles de rattachement, alors qu'il est rattaché.
    try:
        profil = user.profile
    except Exception:
        profil = None
    if profil is not None and profil.without_employee_record:
        profil.without_employee_record = False
        profil.save(update_fields=['without_employee_record'])

    return employee


@transaction.atomic
def unlink_user_from_employee(user):
    """
    Détache l'employee du user.
    Interdit si le user n'est pas exempté (non-admin sans salarié = état invalide).
    """
    employee = get_user_employee(user)
    if not employee:
        return None
    if user_requires_employee(user):
        raise ValidationError(
            "Impossible de détacher ce salarié : l'utilisateur n'est pas administrateur."
        )
    employee.user = None
    employee.save(update_fields=['user'])
    return employee


# ---------------------------------------------------------------------------
# Création automatique
# ---------------------------------------------------------------------------

@transaction.atomic
def create_employee_for_user(user, company, extra_data=None):
    """
    Crée une fiche Employee minimale pour un utilisateur non exempté.
    Ne fait rien si l'utilisateur est exempté ou a déjà un salarié.
    """
    from apps.hr.models import Employee

    if is_user_exempt_from_employee_link(user):
        return None

    existing = get_user_employee(user)
    if existing:
        return existing

    data = extra_data or {}
    employee = Employee.objects.create(
        company=company,
        user=user,
        first_name=data.get('first_name') or getattr(user, 'first_name', '') or 'Utilisateur',
        last_name=data.get('last_name') or getattr(user, 'last_name', '') or '',
        email=data.get('email') or getattr(user, 'email', ''),
        job_title=data.get('job_title', ''),
        department=data.get('department', ''),
    )
    return employee
