"""
access_control/views.py — Interface ERP de gestion des accès.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Count, Q
from .decorators import administration_requise
from .models import (
    ERPModule, ERPView, ERPAction, Role, RolePermission,
    UserCompanyAccess, UserPermissionOverride, AccessLog,
)


def _company(request):
    return request.current_company


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@login_required
@administration_requise
def access_dashboard(request):
    company = _company(request)
    context = {
        'roles_count': Role.objects.filter(company=company).count() + Role.objects.filter(company=None, is_system_role=True).count(),
        'users_count': UserCompanyAccess.objects.filter(company=company, is_active=True).count(),
        'modules_count': ERPModule.objects.filter(is_active=True).count(),
        'log_count': AccessLog.objects.filter(company=company).count(),
        'recent_logs': AccessLog.objects.filter(company=company).order_by('-created_at')[:20],
        'denied_count': AccessLog.objects.filter(company=company, allowed=False).count(),
    }
    return render(request, 'access_control/dashboard.html', context)


# ─── MODULES ──────────────────────────────────────────────────────────────────

@login_required
@administration_requise
def module_list(request):
    modules = ERPModule.objects.all().order_by('order')
    return render(request, 'access_control/module_list.html', {'modules': modules})


# ─── RÔLES ────────────────────────────────────────────────────────────────────

@login_required
@administration_requise
def role_list(request):
    company = _company(request)
    roles = Role.objects.filter(company=company).annotate(users=Count('user_accesses')) | \
            Role.objects.filter(company=None, is_system_role=True).annotate(users=Count('user_accesses'))
    roles = roles.order_by('name')
    return render(request, 'access_control/role_list.html', {'roles': roles})


@login_required
@administration_requise
def role_create(request):
    company = _company(request)
    if request.method == 'POST':
        role = Role.objects.create(
            company=company,
            name=request.POST.get('name', ''),
            code=request.POST.get('code', '').lower().replace(' ', '_'),
            description=request.POST.get('description', ''),
        )
        messages.success(request, f'Rôle « {role.name} » créé.')
        return redirect('access_control:role_permissions', pk=role.pk)
    return render(request, 'access_control/role_form.html', {})


@login_required
@administration_requise
def role_permissions(request, pk):
    # L'ENTREPRISE ÉTAIT LUE ET NON EMPLOYÉE. `company` était calculé à la
    # ligne suivante et le rôle cherché par sa seule clé primaire : un
    # compte de l'entreprise A pouvait donc ouvrir et MODIFIER les
    # permissions d'un rôle de l'entreprise B. Sur un écran de contrôle
    # d'accès, c'est une élévation de privilège d'un locataire à l'autre.
    company = _company(request)
    # BORNE STRICTE, et le role systeme est volontairement exclu.
    #
    # `Role.company` est nullable : un role sans entreprise est un role
    # SYSTEME, partage par toutes. En modifier les permissions depuis cet
    # ecran les changerait pour TOUS les locataires -- ce serait une
    # ecriture inter-entreprises, pire que la lecture qu'on ferme ici. Un
    # 404 explicite vaut mieux qu'un ecran qui laisse un locataire
    # reconfigurer les droits des autres.
    #
    # Le choix differe de celui de `websites.theme_apply`, qui accepte un
    # theme partage : la, on modifie le SITE et non le theme, donc lire un
    # modele commun est sans consequence. Deux bornages, deux raisons.
    role = get_object_or_404(Role, pk=pk, company=company)
    modules = ERPModule.objects.filter(is_active=True).order_by('order')
    actions = ERPAction.objects.all().order_by('name')

    if request.method == 'POST':
        action_type = request.POST.get('action_type', 'save')
        if action_type == 'full_access':
            for module in modules:
                for action in actions:
                    RolePermission.objects.update_or_create(
                        role=role, module=module, view=None, action=action,
                        defaults={'allowed': True}
                    )
            messages.success(request, 'Accès complet accordé.')
        elif action_type == 'readonly':
            RolePermission.objects.filter(role=role).delete()
            view_action = actions.filter(code='view').first()
            if view_action:
                for module in modules:
                    RolePermission.objects.get_or_create(
                        role=role, module=module, view=None, action=view_action,
                        defaults={'allowed': True}
                    )
            messages.success(request, 'Permissions en lecture seule appliquées.')
        elif action_type == 'clear':
            RolePermission.objects.filter(role=role).delete()
            messages.success(request, 'Toutes les permissions supprimées.')
        else:
            # Save checkboxes
            RolePermission.objects.filter(role=role).delete()
            for module in modules:
                for action in actions:
                    key = f'{module.code}__{action.code}'
                    if request.POST.get(key):
                        RolePermission.objects.create(
                            role=role, module=module, view=None, action=action, allowed=True
                        )
            messages.success(request, 'Permissions enregistrées.')
        return redirect('access_control:role_permissions', pk=pk)

    # Construire la matrice des permissions
    existing = set()
    for perm in RolePermission.objects.filter(role=role, view=None, allowed=True).select_related('module', 'action'):
        if perm.action:
            existing.add(f'{perm.module.code}__{perm.action.code}')

    return render(request, 'access_control/role_permissions.html', {
        'role': role, 'modules': modules, 'actions': actions, 'existing': existing,
    })


@login_required
@administration_requise
def role_duplicate(request, pk):
    # BORNE A L'ENTREPRISE, et elle manquait.
    #
    # Le role original etait cherche par sa seule cle primaire, puis copie
    # dans l'entreprise de l'appelant avec SA MATRICE DE PERMISSIONS
    # COMPLETE. En changeant le numero dans l'URL, un compte de
    # l'entreprise A lisait donc le nom, le code, la description et tous
    # les droits d'un role de l'entreprise B -- c'est-a-dire la maniere
    # dont un autre locataire organise ses acces.
    #
    # C'est le meme defaut que `role_permissions` juste au-dessus, corrige
    # lui le mois dernier : la ligne `company = _company(request)` etait
    # presente dans les deux, et n'etait employee que par l'une.
    #
    # Les roles SYSTEME (company=None) sont volontairement dupliquables :
    # ils sont partages par toutes les entreprises et servent de modeles,
    # et copier un modele commun ne revele rien de personne.
    #
    # ECRIT AVEC UN Q, ET NON `company__in=[company, None]`. Cette seconde
    # forme produit `company_id IN (5, NULL)`, et SQL ne fait JAMAIS
    # correspondre NULL par `IN` : la condition rend « inconnu » sur les
    # lignes sans entreprise. Les roles systeme -- precisement ceux que
    # cette ligne entend autoriser -- auraient donc tous rendu 404.
    company = _company(request)
    original = get_object_or_404(
        Role.objects.filter(Q(company=company) | Q(company__isnull=True)),
        pk=pk)
    new_role = Role.objects.create(
        company=company,
        name=f'Copie de {original.name}',
        code=f'copy_{original.code}_{Role.objects.count()}',
        description=original.description,
    )
    for perm in RolePermission.objects.filter(role=original):
        RolePermission.objects.create(
            role=new_role, module=perm.module, view=perm.view,
            action=perm.action, allowed=perm.allowed,
        )
    messages.success(request, f'Rôle dupliqué : {new_role.name}')
    return redirect('access_control:role_permissions', pk=new_role.pk)


# ─── ACCÈS UTILISATEURS ───────────────────────────────────────────────────────

@login_required
@administration_requise
def user_access_list(request):
    company = _company(request)
    accesses = UserCompanyAccess.objects.filter(company=company).select_related('user', 'role').order_by('user__last_name')
    roles = Role.objects.filter(company=company) | Role.objects.filter(company=None, is_system_role=True)
    return render(request, 'access_control/user_access_list.html', {
        'accesses': accesses, 'roles': roles.order_by('name'),
    })


@login_required
@administration_requise
def user_access_create(request):
    company = _company(request)
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        role_id = request.POST.get('role_id')
        try:
            user = User.objects.get(pk=user_id)
            role = Role.objects.get(pk=role_id) if role_id else None
            access, created = UserCompanyAccess.objects.update_or_create(
                user=user, company=company,
                defaults={
                    'role': role,
                    'is_active': True,
                    'can_switch_company': bool(request.POST.get('can_switch')),
                }
            )
            messages.success(request, f'Accès {"créé" if created else "mis à jour"} pour {user.get_full_name() or user.username}.')
        except User.DoesNotExist:
            messages.error(request, 'Utilisateur introuvable.')
        return redirect('access_control:user_access_list')
    all_users = User.objects.all().order_by('last_name')
    roles = (Role.objects.filter(company=company) | Role.objects.filter(company=None, is_system_role=True)).order_by('name')
    return render(request, 'access_control/user_access_form.html', {'all_users': all_users, 'roles': roles})


@login_required
@administration_requise
def user_access_delete(request, pk):
    access = get_object_or_404(UserCompanyAccess, pk=pk, company=_company(request))
    if request.method == 'POST':
        name = access.user.get_full_name() or access.user.username
        access.delete()
        messages.success(request, f'Accès de {name} supprimé.')
    return redirect('access_control:user_access_list')


# ─── OVERRIDES ────────────────────────────────────────────────────────────────

@login_required
@administration_requise
def override_list(request):
    company = _company(request)
    overrides = UserPermissionOverride.objects.filter(company=company).select_related('user', 'module', 'action').order_by('-created_at')
    return render(request, 'access_control/override_list.html', {'overrides': overrides})


@login_required
@administration_requise
def override_create(request):
    company = _company(request)
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        module_code = request.POST.get('module_code')
        action_code = request.POST.get('action_code')
        allowed = request.POST.get('allowed') == '1'
        try:
            user = User.objects.get(pk=user_id)
            module = ERPModule.objects.get(code=module_code)
            action = ERPAction.objects.get(code=action_code) if action_code else None
            UserPermissionOverride.objects.create(
                user=user, company=company, module=module, action=action,
                allowed=allowed, reason=request.POST.get('reason', ''), created_by=request.user,
            )
            messages.success(request, 'Override créé.')
        except Exception as e:
            messages.error(request, f'Erreur : {e}')
        return redirect('access_control:override_list')
    users = UserCompanyAccess.objects.filter(company=company).select_related('user')
    modules = ERPModule.objects.filter(is_active=True)
    actions = ERPAction.objects.all()
    return render(request, 'access_control/override_form.html', {
        'users': users, 'modules': modules, 'actions': actions,
    })


@login_required
@administration_requise
def override_delete(request, pk):
    override = get_object_or_404(UserPermissionOverride, pk=pk, company=_company(request))
    if request.method == 'POST':
        override.delete()
        messages.success(request, 'Override supprimé.')
    return redirect('access_control:override_list')


# ─── JOURNAL DES ACCÈS ────────────────────────────────────────────────────────

@login_required
@administration_requise
def access_log_list(request):
    company = _company(request)
    logs = AccessLog.objects.filter(company=company).select_related('user').order_by('-created_at')[:500]
    return render(request, 'access_control/access_log.html', {'logs': logs})
