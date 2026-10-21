from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q

from django.http import FileResponse, Http404
from django.utils import timezone
from .models import (
    Employee, LeaveRequest, EmployeePrivateFolder, EmployeePrivateDocument, EmployeeDocumentAccessLog,
    EmployeeSkill, EmployeeCertification,
)
from .forms import EmployeeForm, LeaveRequestForm, EmployeeSkillForm, EmployeeCertificationForm


from apps.core.models import AuditLog
from .certification_service import (
    JOURS_PROCHE,
    certifications_a_surveiller,
    compter_par_statut,
    peut_voir_certification,
)


def _is_hr_admin(request):
    """Qui peut agir sur les donnees RH d'un salarie.

    « hr_manager » a ete AJOUTE. Le role « Responsable RH » existe dans
    ROLE_CHOICES et etait pourtant exclu : il ne pouvait ni saisir une
    competence, ni enregistrer une habilitation, alors que c'est
    exactement le role fait pour cela. Seul un administrateur general le
    pouvait -- ce qui obligeait a donner les droits d'administration a qui
    n'avait besoin que des siens.

    getattr et non hasattr+acces : un User sans UserProfile existe
    (createsuperuser, profil supprime a la main), et l'ancienne forme
    levait RelatedObjectDoesNotExist sur hasattr dans certains cas de
    cache.
    """
    if request.user.is_superuser:
        return True
    profil = getattr(request.user, 'profile', None)
    role = getattr(profil, 'role', '') or ''
    return role in ('admin', 'superadmin', 'hr_manager')


@login_required
def index(request):
    return redirect('hr:employee_list')


@login_required
def employee_list(request):
    company = request.current_company
    q = request.GET.get('q', '')
    dept = request.GET.get('dept', '')
    employees = Employee.objects.filter(company=company)
    if q:
        employees = employees.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(job_title__icontains=q) | Q(employee_number__icontains=q))
    if dept:
        employees = employees.filter(department__icontains=dept)
    departments = Employee.objects.filter(company=company).values_list('department', flat=True).distinct().order_by('department')
    ctx = {
        'employees': employees,
        'q': q,
        'dept': dept,
        'departments': [d for d in departments if d],
        'count_active': Employee.objects.filter(company=company, is_active=True).count(),
        'page_title': 'Employés',
        'active_module': 'hr',
    }
    return render(request, 'hr/employee_list.html', ctx)


@login_required
def employee_detail(request, pk):
    company = request.current_company
    employee = get_object_or_404(Employee, pk=pk, company=company)
    leaves = employee.leave_requests.all()[:10]
    ctx = {
        'employee': employee,
        'leaves': leaves,
        'tab': request.GET.get('tab', 'info'),
        'skills': employee.skills.all(),
        'certifications': employee.certifications.all(),
        'is_hr_admin': _is_hr_admin(request),
    }
    return render(request, 'hr/employee_detail.html', ctx)


@login_required
def employee_create(request):
    company = request.current_company
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            emp = form.save(commit=False)
            emp.company = company
            emp.save()
            messages.success(request, f'{emp.first_name} {emp.last_name} ajouté(e).')
            return redirect('hr:employee_detail', pk=emp.pk)
    else:
        form = EmployeeForm()
        form.fields['manager'].queryset = Employee.objects.filter(company=company, is_active=True)
    return render(request, 'hr/employee_form.html', {'form': form, 'action': 'create'})


@login_required
def employee_edit(request, pk):
    company = request.current_company
    employee = get_object_or_404(Employee, pk=pk, company=company)
    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, 'Salarié mis à jour.')
            return redirect('hr:employee_detail', pk=employee.pk)
    else:
        form = EmployeeForm(instance=employee)
        form.fields['manager'].queryset = Employee.objects.filter(company=company, is_active=True).exclude(pk=pk)
    return render(request, 'hr/employee_form.html', {'form': form, 'employee': employee, 'action': 'edit'})


@login_required
def employee_delete(request, pk):
    company = request.current_company
    employee = get_object_or_404(Employee, pk=pk, company=company)
    if request.method == 'POST':
        name = str(employee)
        employee.delete()
        messages.success(request, f'Salarié {name} supprimé.')
        return redirect('hr:employee_list')
    return render(request, 'hr/employee_confirm_delete.html', {'employee': employee})


@login_required
def leave_list(request):
    company = request.current_company
    status = request.GET.get('status', '')
    leaves = LeaveRequest.objects.filter(company=company)
    if status:
        leaves = leaves.filter(status=status)
    ctx = {
        'leaves': leaves,
        'status': status,
        'status_choices': LeaveRequest.STATUS_CHOICES,
        'count_pending': LeaveRequest.objects.filter(company=company, status='pending').count(),
    }
    return render(request, 'hr/leave_list.html', ctx)


@login_required
def leave_create(request):
    company = request.current_company
    if request.method == 'POST':
        # company= passe aussi au POST : c'est tout l'objet du bornage dans
        # __init__. L'omettre ici reproduirait exactement la fuite corrigee.
        form = LeaveRequestForm(request.POST, company=company)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.company = company
            leave.save()
            messages.success(request, 'Demande de congé enregistrée.')
            return redirect('hr:leave_list')
    else:
        form = LeaveRequestForm(company=company)
    return render(request, 'hr/leave_form.html', {'form': form, 'action': 'create'})


@login_required
def leave_approve(request, pk):
    company = request.current_company
    leave = get_object_or_404(LeaveRequest, pk=pk, company=company)
    if request.method == 'POST':
        leave.status = 'approved'
        leave.approved_by = request.user
        leave.save()
        messages.success(request, 'Congé approuvé.')
    return redirect('hr:leave_list')


@login_required
def leave_refuse(request, pk):
    company = request.current_company
    leave = get_object_or_404(LeaveRequest, pk=pk, company=company)
    if request.method == 'POST':
        leave.status = 'refused'
        leave.save()
        messages.success(request, 'Congé refusé.')
    return redirect('hr:leave_list')


@login_required
def expense_list(request):
    company = request.current_company
    ctx = {'company': company}
    return render(request, 'hr/expense_list.html', ctx)


# ─── DOSSIERS PRIVÉS SALARIÉS ─────────────────────────────────────────────────

@login_required
def private_folder_list(request):
    company = request.current_company
    employees = Employee.objects.filter(company=company, is_active=True)
    folders = []
    for emp in employees:
        folder, _ = EmployeePrivateFolder.objects.get_or_create(
            company=company, employee=emp,
            defaults={'folder_name': f'Dossier privé — {emp.first_name} {emp.last_name}'}
        )
        folders.append({'employee': emp, 'folder': folder})

    # Dashboard alertes
    from datetime import date, timedelta
    today = date.today()
    threshold = today + timedelta(days=30)
    expiring = EmployeePrivateDocument.objects.filter(
        company=company, expires_at__lte=threshold, expires_at__gte=today
    ).count()
    expired = EmployeePrivateDocument.objects.filter(company=company, expires_at__lt=today).count()
    pending_sig = EmployeePrivateDocument.objects.filter(
        company=company, requires_signature=True, signed_at__isnull=True
    ).count()

    return render(request, 'hr/private_folder_list.html', {
        'folders': folders, 'expiring': expiring, 'expired': expired, 'pending_sig': pending_sig,
    })


@login_required
def private_folder_detail(request, employee_pk):
    company = request.current_company
    employee = get_object_or_404(Employee, pk=employee_pk, company=company)
    folder, _ = EmployeePrivateFolder.objects.get_or_create(
        company=company, employee=employee,
        defaults={'folder_name': f'Dossier privé — {employee.first_name} {employee.last_name}'}
    )
    doc_type_filter = request.GET.get('doc_type', '')
    docs = EmployeePrivateDocument.objects.filter(company=company, employee=employee)
    if doc_type_filter:
        docs = docs.filter(document_type=doc_type_filter)
    recent_logs = EmployeeDocumentAccessLog.objects.filter(
        document__employee=employee
    ).select_related('user', 'document').order_by('-created_at')[:20]
    return render(request, 'hr/private_folder_detail.html', {
        'employee': employee, 'folder': folder, 'documents': docs,
        'doc_type_choices': EmployeePrivateDocument.DOC_TYPE_CHOICES,
        'doc_type_filter': doc_type_filter,
        'recent_logs': recent_logs,
    })


@login_required
def private_document_add(request, employee_pk):
    company = request.current_company
    employee = get_object_or_404(Employee, pk=employee_pk, company=company)
    folder, _ = EmployeePrivateFolder.objects.get_or_create(
        company=company, employee=employee,
        defaults={'folder_name': f'Dossier privé — {employee.first_name} {employee.last_name}'}
    )
    if request.method == 'POST' and request.FILES.get('file'):
        doc = EmployeePrivateDocument.objects.create(
            company=company,
            employee=employee,
            folder=folder,
            document_type=request.POST.get('document_type', 'other'),
            title=request.POST.get('title', ''),
            file=request.FILES['file'],
            description=request.POST.get('description', ''),
            confidentiality_level=request.POST.get('confidentiality_level', 'confidential'),
            visible_to_employee=bool(request.POST.get('visible_to_employee')),
            requires_signature=bool(request.POST.get('requires_signature')),
            expires_at=request.POST.get('expires_at') or None,
            uploaded_by=request.user,
        )
        EmployeeDocumentAccessLog.objects.create(
            document=doc, user=request.user, action='upload',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        messages.success(request, f'Document « {doc.title} » ajouté.')
        return redirect('hr:private_folder_detail', employee_pk=employee_pk)
    return render(request, 'hr/private_document_form.html', {
        'employee': employee,
        'doc_type_choices': EmployeePrivateDocument.DOC_TYPE_CHOICES,
        'confidentiality_choices': EmployeePrivateDocument.CONFIDENTIALITY_CHOICES,
    })


@login_required
def private_document_delete(request, pk):
    company = request.current_company
    doc = get_object_or_404(EmployeePrivateDocument, pk=pk, company=company)
    employee_pk = doc.employee_id
    if request.method == 'POST':
        EmployeeDocumentAccessLog.objects.create(
            document=doc, user=request.user, action='delete',
            ip_address=request.META.get('REMOTE_ADDR'),
        )
        doc.delete()
        messages.success(request, 'Document supprimé.')
    return redirect('hr:private_folder_detail', employee_pk=employee_pk)


@login_required
def private_document_download(request, pk):
    company = request.current_company
    doc = get_object_or_404(EmployeePrivateDocument, pk=pk, company=company)
    EmployeeDocumentAccessLog.objects.create(
        document=doc, user=request.user, action='download',
        ip_address=request.META.get('REMOTE_ADDR'),
    )
    try:
        return FileResponse(doc.file.open('rb'), as_attachment=True, filename=doc.file.name.split('/')[-1])
    except Exception:
        raise Http404


@login_required
def my_private_documents(request):
    """Vue salarié — mes documents visibles."""
    company = request.current_company
    try:
        employee = Employee.objects.get(company=company, user=request.user)
    except Employee.DoesNotExist:
        messages.warning(request, 'Aucun dossier salarié associé à votre compte.')
        return redirect('core:dashboard')
    docs = EmployeePrivateDocument.objects.filter(
        company=company, employee=employee, visible_to_employee=True
    )
    return render(request, 'hr/my_private_documents.html', {
        'employee': employee, 'documents': docs,
    })


# ─── COMPÉTENCES ET CERTIFICATIONS ────────────────────────────────────────────

@login_required
def skill_create(request, employee_pk):
    company = request.current_company
    employee = get_object_or_404(Employee, pk=employee_pk, company=company)
    if not _is_hr_admin(request):
        messages.error(request, 'Action réservée aux administrateurs.')
        return redirect('hr:employee_detail', pk=employee_pk)
    if request.method == 'POST':
        form = EmployeeSkillForm(request.POST)
        if form.is_valid():
            skill = form.save(commit=False)
            skill.employee = employee
            skill.save()
            messages.success(request, f'Compétence « {skill.name} » ajoutée.')
            return redirect('hr:employee_detail', pk=employee_pk)
    else:
        form = EmployeeSkillForm()
    return render(request, 'hr/skill_form.html', {'form': form, 'employee': employee, 'action': 'create'})


@login_required
def skill_edit(request, pk):
    company = request.current_company
    skill = get_object_or_404(EmployeeSkill, pk=pk, employee__company=company)
    if not _is_hr_admin(request):
        messages.error(request, 'Action réservée aux administrateurs.')
        return redirect('hr:employee_detail', pk=skill.employee_id)
    if request.method == 'POST':
        form = EmployeeSkillForm(request.POST, instance=skill)
        if form.is_valid():
            form.save()
            messages.success(request, 'Compétence mise à jour.')
            return redirect('hr:employee_detail', pk=skill.employee_id)
    else:
        form = EmployeeSkillForm(instance=skill)
    return render(request, 'hr/skill_form.html', {'form': form, 'employee': skill.employee, 'skill': skill, 'action': 'edit'})


@login_required
def skill_delete(request, pk):
    company = request.current_company
    skill = get_object_or_404(EmployeeSkill, pk=pk, employee__company=company)
    employee_pk = skill.employee_id
    if not _is_hr_admin(request):
        messages.error(request, 'Action réservée aux administrateurs.')
        return redirect('hr:employee_detail', pk=employee_pk)
    if request.method == 'POST':
        name = skill.name
        skill.delete()
        messages.success(request, f'Compétence « {name} » supprimée.')
        return redirect('hr:employee_detail', pk=employee_pk)
    return render(request, 'hr/skill_confirm_delete.html', {'skill': skill})


@login_required
def certification_create(request, employee_pk):
    company = request.current_company
    employee = get_object_or_404(Employee, pk=employee_pk, company=company)
    if not _is_hr_admin(request):
        messages.error(request, 'Action réservée aux administrateurs.')
        return redirect('hr:employee_detail', pk=employee_pk)
    if request.method == 'POST':
        form = EmployeeCertificationForm(request.POST, request.FILES)
        if form.is_valid():
            cert = form.save(commit=False)
            cert.employee = employee
            cert.save()
            messages.success(request, f'Certification « {cert.name} » ajoutée.')
            return redirect('hr:employee_detail', pk=employee_pk)
    else:
        form = EmployeeCertificationForm()
    return render(request, 'hr/certification_form.html', {'form': form, 'employee': employee, 'action': 'create'})


@login_required
def certification_edit(request, pk):
    company = request.current_company
    cert = get_object_or_404(EmployeeCertification, pk=pk, employee__company=company)
    if not _is_hr_admin(request):
        messages.error(request, 'Action réservée aux administrateurs.')
        return redirect('hr:employee_detail', pk=cert.employee_id)
    if request.method == 'POST':
        form = EmployeeCertificationForm(request.POST, request.FILES, instance=cert)
        if form.is_valid():
            form.save()
            messages.success(request, 'Certification mise à jour.')
            return redirect('hr:employee_detail', pk=cert.employee_id)
    else:
        form = EmployeeCertificationForm(instance=cert)
    return render(request, 'hr/certification_form.html', {'form': form, 'employee': cert.employee, 'certification': cert, 'action': 'edit'})


@login_required
def certification_delete(request, pk):
    company = request.current_company
    cert = get_object_or_404(EmployeeCertification, pk=pk, employee__company=company)
    employee_pk = cert.employee_id
    if not _is_hr_admin(request):
        messages.error(request, 'Action réservée aux administrateurs.')
        return redirect('hr:employee_detail', pk=employee_pk)
    if request.method == 'POST':
        name = cert.name
        cert.delete()
        messages.success(request, f'Certification « {name} » supprimée.')
        return redirect('hr:employee_detail', pk=employee_pk)
    return render(request, 'hr/certification_confirm_delete.html', {'certification': cert})


@login_required
def certification_download(request, pk):
    """Sert le scan d'une habilitation. La seule façon d'y accéder.

    Le gabarit pointait vers « cert.file.url », soit
    /media/employee_certifications/..., et PERSONNE ne sert /media/ en
    production : le static(MEDIA_URL) d'erp_btp/urls.py est derriere
    « if settings.DEBUG », nginx proxifie /media/ vers gunicorn au lieu de
    le servir depuis le disque, et WhiteNoise ne sert que STATIC_ROOT.
    L'envoi fonctionnait, le trombone s'affichait, et le clic rendait 404.

    Le correctif facile aurait ete d'ajouter un « location /media/ » qui
    sert le disque -- et de rendre du meme coup tous les scans de CACES
    lisibles par quiconque devine l'URL, sans authentification. D'ou cette
    vue, qui verifie QUI demande.
    """
    company = request.current_company
    certification = get_object_or_404(
        EmployeeCertification.objects.select_related('employee'),
        pk=pk, employee__company=company)

    if not peut_voir_certification(request.user, certification, company):
        raise Http404

    if not certification.file:
        messages.warning(request, 'Aucun document joint à cette habilitation.')
        return redirect('hr:employee_detail', pk=certification.employee_id)

    # Trace d'acces. EmployeeDocumentAccessLog est attache a
    # EmployeePrivateDocument par cle etrangere et ne peut pas accueillir
    # une certification sans changement de schema ; AuditLog porte deja ce
    # qu'il faut, et sert le meme but.
    try:
        AuditLog.objects.create(
            user=request.user, company=company, action='download',
            module='hr', model_name='EmployeeCertification',
            object_id=str(certification.pk),
            object_repr=f'{certification.name} — {certification.employee}'[:200],
            description=(
                f'Téléchargement du document de l\'habilitation '
                f'« {certification.name} » de {certification.employee}.'),
            ip_address=request.META.get('REMOTE_ADDR') or None,
        )
    except Exception:
        pass

    try:
        return FileResponse(
            certification.file.open('rb'), as_attachment=True,
            filename=certification.file.name.split('/')[-1])
    except FileNotFoundError:
        # Le fichier a disparu du disque : restauration partielle, media non
        # sauvegarde. Dire lequel vaut mieux qu'un 404 muet.
        messages.error(request, (
            f'Le document de « {certification.name} » est introuvable sur '
            f'le serveur. La fiche le référence toujours : il a été perdu, '
            f'pas supprimé.'))
        return redirect('hr:employee_detail', pk=certification.employee_id)
    except Exception:
        raise Http404


@login_required
def certification_expiring(request):
    """Les habilitations expirées ou proches de l'être, pour l'entreprise.

    L'écran qui manquait. is_expired et expires_soon existaient depuis le
    début, mais ne servaient qu'à colorer une ligne sur la fiche d'un
    salarié : il fallait ouvrir les fiches une par une pour découvrir
    qu'un CACES etait perime. Pour une habilitation, le besoin est
    l'inverse -- le savoir avant que la personne arrive sur chantier.
    """
    company = request.current_company
    if not _is_hr_admin(request):
        messages.error(request, (
            'Cet écran est réservé à l\'encadrement RH : il liste les '
            'habilitations de tous les salariés.'))
        return redirect('hr:my_skills_certifications')

    try:
        jours = int(request.GET.get('jours', JOURS_PROCHE))
    except (TypeError, ValueError):
        jours = JOURS_PROCHE
    # Borne haute : « jours=100000 » chargerait tout l'historique et
    # produirait une page que personne ne peut lire.
    jours = max(0, min(jours, 365))

    lignes = certifications_a_surveiller(company, jours=jours)

    return render(request, 'hr/certification_expiring.html', {
        'lignes': lignes,
        'compteurs': compter_par_statut(lignes),
        'jours': jours,
        'page_title': 'Habilitations à renouveler',
        'active_module': 'hr',
    })


@login_required
def my_skills_certifications(request):
    """Vue salarié — mes compétences et certifications (lecture seule)."""
    company = request.current_company
    try:
        employee = Employee.objects.get(company=company, user=request.user)
    except Employee.DoesNotExist:
        messages.warning(request, 'Aucun dossier salarié associé à votre compte.')
        return redirect('core:dashboard')
    return render(request, 'hr/my_skills_certifications.html', {
        'employee': employee,
        'skills': employee.skills.all(),
        'certifications': employee.certifications.all(),
    })
