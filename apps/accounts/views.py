"""
apps/accounts/views.py — Authentification, profil, gestion utilisateurs
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .forms import LoginForm, UserForm, UserProfileForm, UserCreateForm
from .models import UserProfile
from apps.core.models import Company, AuditLog
from apps.accounts.services.user_employee_link_service import (
    link_user_to_employee,
    get_user_employee,
    is_user_exempt_from_employee_link,
)


def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    form = LoginForm(request, data=request.POST or None)

    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        remember = form.cleaned_data.get('remember_me')

        if not remember:
            request.session.set_expiry(0)

        login(request, user)

        AuditLog.objects.create(
            user=user,
            action='login',
            description=f'Connexion utilisateur : {user.username}',
            ip_address=_get_ip(request),
        )

        next_url = request.GET.get('next', 'core:dashboard')
        return redirect(next_url)

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    if request.user.is_authenticated:
        AuditLog.objects.create(
            user=request.user,
            action='logout',
            description=f'Déconnexion : {request.user.username}',
        )
    logout(request)
    messages.info(request, 'Vous avez été déconnecté.')
    return redirect('accounts:login')


@login_required
def profile(request):
    """Profil et préférences de l'utilisateur connecté."""
    user_form = UserForm(request.POST or None, instance=request.user)
    profile_form = UserProfileForm(request.POST or None, request.FILES or None, instance=request.user.profile)

    if request.method == 'POST':
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Profil mis à jour avec succès.')
            return redirect('accounts:profile')

    return render(request, 'accounts/profile.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'page_title': 'Mon profil',
    })


@login_required
@require_POST
def signature_save(request):
    """Enregistre la signature tracée dans le cadre.

    POST seulement : un GET qui modifie le compte se déclencherait au
    survol d'un lien, à l'indexation ou au passage d'un antivirus.

    L'ancien fichier est supprimé AVANT d'écrire le nouveau : sans cela, le
    stockage de Django renomme le nouveau (« signature-3_a8f2.png ») et les
    anciens s'accumulent indéfiniment sur le disque, un par
    réenregistrement.
    """
    from django.core.files.base import ContentFile

    from apps.accounts.signature import SignatureInvalide, decoder_signature

    try:
        octets = decoder_signature(request.POST.get('signature') or '')
    except SignatureInvalide as exc:
        # Le refus est renvoye tel quel : le cadre vide et le fichier
        # illisible n'ont pas le meme remede, et « erreur » ne le dirait pas.
        return JsonResponse({'erreur': str(exc)}, status=400)

    profil = request.user.profile
    if profil.signature:
        try:
            profil.signature.delete(save=False)
        except OSError:
            # Un fichier verrouille ou deja disparu ne doit PAS empecher
            # d'enregistrer la nouvelle signature : la consequence a
            # accepter est un fichier orphelin, bien preferable a un refus
            # d'enregistrement que l'utilisateur ne saurait pas contourner.
            # Rencontre sous Windows, ou une poignee encore ouverte fait
            # echouer os.remove (WinError 32).
            pass
    profil.signature.save(f'signature-{request.user.pk}.png',
                          ContentFile(octets), save=True)

    return JsonResponse({'url': profil.signature.url,
                         'message': 'Signature enregistrée.'})


@login_required
@require_POST
def signature_delete(request):
    """Retire la signature enregistrée.

    Le fichier est supprimé du disque, et pas seulement détaché : une
    signature manuscrite est une donnée personnelle, la laisser traîner
    après un retrait explicite serait difficile à justifier.
    """
    profil = request.user.profile
    if profil.signature:
        profil.signature.delete(save=True)
        messages.success(request, 'Signature retirée.')
    return redirect('accounts:profile')


@login_required
def user_list(request):
    """Liste des utilisateurs (admin seulement)."""
    company = request.current_company

    # employee_profile est charge avec le reste : sans cela, la colonne de
    # rattachement couterait une requete par ligne.
    if request.user.is_superuser:
        users = User.objects.select_related(
            'profile', 'employee_profile').order_by('username')
    elif company and request.user.profile.role in ['admin', 'manager']:
        users = User.objects.filter(
            profile__companies=company
        ).select_related('profile', 'employee_profile').order_by('username')
    else:
        messages.error(request, 'Accès refusé.')
        return redirect('core:dashboard')

    return render(request, 'accounts/user_list.html', {
        'users': users,
        'page_title': 'Gestion des utilisateurs',
    })


def _entier_ou_none(valeur):
    """Convertit un parametre d'URL en entier, ou rend None.

    Filtrer sur pk='abc' leve ValueError AVANT toute requete : .first() ne
    rattrape rien, c'est la preparation du filtre qui echoue. L'ancien code
    s'en sortait par un « except Exception » large ; en le retirant j'ai
    casse ce cas, et un test l'a attrape.
    """
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return None


@login_required
def user_create(request):
    """Créer un utilisateur avec liaison salarié obligatoire pour les non-admins."""
    if not (request.user.is_superuser or request.user.profile.role in ['admin', 'superadmin']):
        messages.error(request, 'Accès refusé.')
        return redirect('accounts:user_list')

    company = getattr(request, 'current_company', None)

    # Pré-sélection d'un salarié depuis ?employee=<pk>
    #
    # Le filtre d'entreprise manquait : « ?employee=<pk> » désignant le
    # salarié d'une AUTRE société le pré-sélectionnait, et affichait son nom.
    # La validation l'aurait refusé ensuite, mais le nom avait déjà fuité.
    employee_prefill = None
    employee_pk = _entier_ou_none(request.GET.get('employee'))
    if employee_pk and company:
        from apps.hr.models import Employee
        employee_prefill = Employee.objects.filter(
            pk=employee_pk, company=company, user__isnull=True).first()

    form = UserCreateForm(
        request.POST or None,
        company=company,
        employee_prefill=employee_prefill,
    )

    if form.is_valid():
        user = form.save()
        # Rôle et entreprise
        profil = user.profile
        if company:
            profil.companies.add(company)
        profil.role = form.cleaned_data.get('role', 'user')
        # Enregistre AVANT la liaison : si la liaison échoue, le compte reste
        # dans un état cohérent, et un compte déclaré sans salarié n'est pas
        # signalé à tort comme un rattachement oublié.
        profil.without_employee_record = bool(
            form.cleaned_data.get('without_employee_record'))
        profil.save()

        # Liaison salarié
        employee = form.cleaned_data.get('employee')
        if employee:
            try:
                link_user_to_employee(user, employee)
                messages.success(request, f'Utilisateur "{user.username}" créé et lié à {employee.full_name}.')
            except Exception as exc:
                messages.warning(request, f'Utilisateur créé mais liaison salarié échouée : {exc}')
        elif profil.without_employee_record:
            messages.success(
                request,
                f'Utilisateur "{user.username}" créé, sans fiche salarié.')
        else:
            messages.success(request, f'Utilisateur "{user.username}" créé.')

        return redirect('accounts:user_detail', pk=user.pk)

    return render(request, 'accounts/user_form.html', {
        'form': form,
        'page_title': 'Nouvel utilisateur',
        'employee_prefill': employee_prefill,
        'diagnostic_salaries': form.diagnostic_salaries,
    })


@login_required
def user_detail(request, pk):
    user_obj = get_object_or_404(User, pk=pk)
    return render(request, 'accounts/user_detail.html', {
        'user_obj': user_obj,
        'page_title': user_obj.get_full_name() or user_obj.username,
    })


@login_required
def missing_employee(request):
    """Page affichée quand un utilisateur non-admin n'a pas de fiche salarié."""
    return render(request, 'accounts/missing_employee.html', {
        'page_title': 'Compte non lié à un salarié',
    })


def _get_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')
