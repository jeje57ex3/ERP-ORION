from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q

from django.http import FileResponse, Http404
from django.utils import timezone
from .models import Employee, LeaveRequest, EmployeePrivateFolder, EmployeePrivateDocument, EmployeeDocumentAccessLog
from .forms import EmployeeForm, LeaveRequestForm


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
    ctx = {'employee': employee, 'leaves': leaves, 'tab': request.GET.get('tab', 'info')}
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
        form = LeaveRequestForm(request.POST)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.company = company
            leave.save()
            messages.success(request, 'Demande de congé enregistrée.')
            return redirect('hr:leave_list')
    else:
        form = LeaveRequestForm()
        form.fields['employee'].queryset = Employee.objects.filter(company=company, is_active=True)
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
