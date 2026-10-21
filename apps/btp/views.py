from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum
from django.views.decorators.http import require_POST

from .models import BTPProject, BTPQuote, SituationOfWorks, BTPTimesheet
from .forms import BTPProjectForm, BTPQuoteForm, SituationForm, BTPTimesheetForm
from apps.crm.models import Customer


@login_required
def index(request):
    return redirect('btp:project_list')


# --- Projects ---

@login_required
def project_list(request):
    company = request.current_company
    q = request.GET.get('q', '')
    status = request.GET.get('status', '')
    projects = BTPProject.objects.filter(company=company)
    if q:
        projects = projects.filter(Q(name__icontains=q) | Q(code__icontains=q) | Q(customer__name__icontains=q))
    if status:
        projects = projects.filter(status=status)
    ctx = {
        'projects': projects,
        'q': q,
        'status': status,
        'status_choices': BTPProject.STATUS_CHOICES,
        'count_active': BTPProject.objects.filter(company=company, status='in_progress').count(),
        'total_budget': BTPProject.objects.filter(company=company).aggregate(s=Sum('estimated_budget'))['s'] or 0,
        'page_title': 'Chantiers',
        'active_module': 'btp',
    }
    return render(request, 'btp/project_list.html', ctx)


@login_required
def project_detail(request, pk):
    company = request.current_company
    project = get_object_or_404(BTPProject, pk=pk, company=company)
    quotes = project.quotes.all()
    situations = project.situations.all().order_by('-period_end')
    timesheets = project.timesheets.all()[:20]
    phases = project.phases.all()
    # select_related sur les deux FK affichees : sans cela, une ligne par
    # achat part en requete pour le fournisseur et pour l'article.
    supplies = project.supplies.select_related('supplier', 'material')
    ctx = {
        'project': project,
        'quotes': quotes,
        'situations': situations,
        'timesheets': timesheets,
        'phases': phases,
        'supplies': supplies,
        'tab': request.GET.get('tab', 'info'),
    }
    return render(request, 'btp/project_detail.html', ctx)


@login_required
def project_create(request):
    company = request.current_company
    if request.method == 'POST':
        form = BTPProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.company = company
            count = BTPProject.objects.filter(company=company).count() + 1
            if not project.code:
                project.code = f'CH-{count:04d}'
            project.save()
            messages.success(request, f'Chantier "{project.name}" créé.')
            return redirect('btp:project_detail', pk=project.pk)
    else:
        form = BTPProjectForm()
        form.fields['customer'].queryset = Customer.objects.filter(company=company, is_active=True)
    return render(request, 'btp/project_form.html', {'form': form, 'action': 'create'})


@login_required
def project_edit(request, pk):
    company = request.current_company
    project = get_object_or_404(BTPProject, pk=pk, company=company)
    if request.method == 'POST':
        form = BTPProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, 'Chantier mis à jour.')
            return redirect('btp:project_detail', pk=project.pk)
    else:
        form = BTPProjectForm(instance=project)
        form.fields['customer'].queryset = Customer.objects.filter(company=company, is_active=True)
    return render(request, 'btp/project_form.html', {'form': form, 'project': project, 'action': 'edit'})


@login_required
def project_delete(request, pk):
    company = request.current_company
    project = get_object_or_404(BTPProject, pk=pk, company=company)
    if request.method == 'POST':
        name = project.name
        project.delete()
        messages.success(request, f'Chantier "{name}" supprimé.')
        return redirect('btp:project_list')
    return render(request, 'btp/project_confirm_delete.html', {'project': project})


# --- BTP Quotes ---

@login_required
def quote_list(request):
    company = request.current_company
    q = request.GET.get('q', '')
    status = request.GET.get('status', '')
    quotes = BTPQuote.objects.filter(company=company)
    if q:
        quotes = quotes.filter(Q(number__icontains=q) | Q(customer__name__icontains=q) | Q(subject__icontains=q))
    if status:
        quotes = quotes.filter(status=status)
    ctx = {
        'quotes': quotes,
        'q': q,
        'status': status,
        'status_choices': BTPQuote.STATUS_CHOICES,
        'total_ht': quotes.aggregate(s=Sum('total_ht'))['s'] or 0,
    }
    return render(request, 'btp/quote_list.html', ctx)


@login_required
def quote_detail(request, pk):
    company = request.current_company
    quote = get_object_or_404(BTPQuote, pk=pk, company=company)
    lines = quote.lines.all()
    ctx = {'quote': quote, 'lines': lines}
    return render(request, 'btp/quote_detail.html', ctx)


@login_required
def quote_create(request):
    company = request.current_company
    if request.method == 'POST':
        form = BTPQuoteForm(request.POST)
        if form.is_valid():
            quote = form.save(commit=False)
            quote.company = company
            quote.created_by = request.user
            count = BTPQuote.objects.filter(company=company).count() + 1
            quote.number = f'DEVBTP-{count:04d}'
            quote.save()
            messages.success(request, f'Devis BTP {quote.number} créé.')
            return redirect('btp:quote_detail', pk=quote.pk)
    else:
        form = BTPQuoteForm()
        form.fields['customer'].queryset = Customer.objects.filter(company=company, is_active=True)
        form.fields['project'].queryset = BTPProject.objects.filter(company=company)
    return render(request, 'btp/quote_form.html', {'form': form, 'action': 'create'})


@login_required
def quote_edit(request, pk):
    company = request.current_company
    quote = get_object_or_404(BTPQuote, pk=pk, company=company)
    if request.method == 'POST':
        form = BTPQuoteForm(request.POST, instance=quote)
        if form.is_valid():
            form.save()
            messages.success(request, 'Devis BTP mis à jour.')
            return redirect('btp:quote_detail', pk=quote.pk)
    else:
        form = BTPQuoteForm(instance=quote)
        form.fields['customer'].queryset = Customer.objects.filter(company=company, is_active=True)
        form.fields['project'].queryset = BTPProject.objects.filter(company=company)
    return render(request, 'btp/quote_form.html', {'form': form, 'quote': quote, 'action': 'edit'})


@login_required
def quote_delete(request, pk):
    company = request.current_company
    quote = get_object_or_404(BTPQuote, pk=pk, company=company)
    if request.method == 'POST':
        quote.delete()
        messages.success(request, 'Devis BTP supprimé.')
        return redirect('btp:quote_list')
    return render(request, 'btp/quote_confirm_delete.html', {'quote': quote})


# --- Situations ---

@login_required
def situation_list(request):
    company = request.current_company
    project_id = request.GET.get('project', '')
    situations = SituationOfWorks.objects.filter(company=company)
    if project_id:
        situations = situations.filter(project_id=project_id)
    projects = BTPProject.objects.filter(company=company, status='in_progress')
    ctx = {'situations': situations, 'projects': projects, 'project_id': project_id}
    return render(request, 'btp/situation_list.html', ctx)


@login_required
def situation_detail(request, pk):
    company = request.current_company
    situation = get_object_or_404(SituationOfWorks, pk=pk, company=company)
    ctx = {'situation': situation}
    return render(request, 'btp/situation_detail.html', ctx)


@login_required
def situation_create(request):
    company = request.current_company
    if request.method == 'POST':
        form = SituationForm(request.POST)
        if form.is_valid():
            sit = form.save(commit=False)
            sit.company = company
            sit.period_amount = sit.cumulative_amount - sit.previous_amount
            if sit.project.retention_rate:
                sit.retention_amount = sit.period_amount * sit.project.retention_rate / 100
            sit.save()
            messages.success(request, f'Situation n°{sit.number} créée.')
            return redirect('btp:situation_detail', pk=sit.pk)
    else:
        form = SituationForm()
        form.fields['project'].queryset = BTPProject.objects.filter(company=company)
    return render(request, 'btp/situation_form.html', {'form': form, 'action': 'create'})


@login_required
def situation_delete(request, pk):
    company = request.current_company
    situation = get_object_or_404(SituationOfWorks, pk=pk, company=company)
    if request.method == 'POST':
        situation.delete()
        messages.success(request, 'Situation supprimée.')
        return redirect('btp:situation_list')
    return render(request, 'btp/situation_confirm_delete.html', {'situation': situation})


# --- Timesheets ---

@login_required
def timesheet_list(request):
    company = request.current_company
    project_id = request.GET.get('project', '')
    timesheets = BTPTimesheet.objects.filter(company=company)
    if project_id:
        timesheets = timesheets.filter(project_id=project_id)
    projects = BTPProject.objects.filter(company=company)
    ctx = {
        'timesheets': timesheets[:100],
        'projects': projects,
        'project_id': project_id,
    }
    return render(request, 'btp/timesheet_list.html', ctx)


@login_required
def timesheet_create(request):
    company = request.current_company
    if request.method == 'POST':
        # company= passe aussi au POST : c'est tout l'objet du bornage dans
        # __init__. L'omettre ici reproduirait exactement la fuite corrigee.
        form = BTPTimesheetForm(request.POST, company=company)
        if form.is_valid():
            ts = form.save(commit=False)
            ts.company = company
            ts.save()
            messages.success(request, 'Pointage enregistré.')
            return redirect('btp:timesheet_list')
    else:
        form = BTPTimesheetForm(company=company)
    return render(request, 'btp/timesheet_form.html', {'form': form, 'action': 'create'})


# ─── Validation des pointages ─────────────────────────────────────────────────
#
# Ces quatre vues etaient des _stub renvoyant « En cours de developpement »,
# alors que templates/btp/timesheet_list.html affichait de vrais boutons
# « Valider » et « Refuser » qui pointaient dessus. Le champ is_validated
# existait sur le modele et rien ne l'ecrivait jamais : des boutons casses,
# et un indicateur toujours faux.


def _peut_valider(request):
    """Valider les heures d'autrui demande d'encadrer.

    Sans ce controle, un salarie validerait ses propres heures, et la
    validation ne vaudrait plus rien -- autant retirer la colonne.
    """
    if request.user.is_superuser:
        return True
    profil = getattr(request.user, 'profile', None)
    role = getattr(profil, 'role', '') or ''
    return role in ('admin', 'superadmin', 'manager', 'hr_manager')


@login_required
@require_POST
def timesheet_validate(request, pk):
    company = request.current_company
    if not _peut_valider(request):
        messages.error(request, 'Seul un responsable peut valider des heures.')
        return redirect('btp:timesheet_list')
    ts = get_object_or_404(BTPTimesheet, pk=pk, company=company)
    ts.is_validated = True
    ts.validated_by = request.user
    ts.save(update_fields=['is_validated', 'validated_by'])
    messages.success(request, 'Pointage validé.')
    return redirect('btp:timesheet_list')


@login_required
@require_POST
def timesheet_reject(request, pk):
    """Retire la validation. Ne supprime pas le pointage.

    Un pointage « refuse » doit rester visible pour etre corrige : le
    detruire effacerait la seule trace de ce que le salarie avait declare,
    et la discussion n'aurait plus d'objet.
    """
    company = request.current_company
    if not _peut_valider(request):
        messages.error(request, 'Seul un responsable peut refuser des heures.')
        return redirect('btp:timesheet_list')
    ts = get_object_or_404(BTPTimesheet, pk=pk, company=company)
    ts.is_validated = False
    ts.validated_by = None
    ts.save(update_fields=['is_validated', 'validated_by'])
    messages.info(request, 'Validation retirée : le pointage reste à corriger.')
    return redirect('btp:timesheet_list')


@login_required
@require_POST
def timesheet_validate_bulk(request):
    company = request.current_company
    if not _peut_valider(request):
        messages.error(request, 'Seul un responsable peut valider des heures.')
        return redirect('btp:timesheet_list')

    # Les identifiants viennent du formulaire : le filtre sur company est
    # ce qui empeche de valider, par identifiant forge, les heures d'une
    # autre entreprise.
    ids = [valeur for valeur in request.POST.getlist('timesheet_ids') if valeur.isdigit()]
    if not ids:
        messages.warning(request, 'Aucun pointage sélectionné.')
        return redirect('btp:timesheet_list')

    nombre = BTPTimesheet.objects.filter(
        company=company, pk__in=ids, is_validated=False
    ).update(is_validated=True, validated_by=request.user)
    messages.success(request, f'{nombre} pointage(s) validé(s).')
    return redirect('btp:timesheet_list')


@login_required
def timesheet_detail(request, pk):
    company = request.current_company
    ts = get_object_or_404(
        BTPTimesheet.objects.select_related('project', 'employee', 'validated_by'),
        pk=pk, company=company)
    return render(request, 'btp/timesheet_detail.html', {
        'ts': ts,
        'peut_valider': _peut_valider(request),
        'page_title': f'Pointage du {ts.work_date:%d/%m/%Y}',
    })


def _stub(request, *args, **kwargs):
    from django.http import HttpResponse
    return HttpResponse('<h3 style="font-family:sans-serif;padding:2rem">En cours de developpement.</h3>')
quote_send = login_required(_stub)
quote_convert = login_required(_stub)

