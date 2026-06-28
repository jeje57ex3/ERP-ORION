"""apps/crm/views.py — Vues CRUD CRM"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Sum
from .models import Customer, Prospect, Opportunity, Contact, CRMActivity
from .forms import CustomerForm, ProspectForm, OpportunityForm, ContactForm, ActivityForm


# ─────────────────────────────────────────────────────────────
# CUSTOMERS
# ─────────────────────────────────────────────────────────────

@login_required
def customer_list(request):
    company = request.current_company
    qs = Customer.objects.filter(company=company)

    q = request.GET.get('q', '')
    status = request.GET.get('status', '')
    ctype = request.GET.get('type', '')

    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(email__icontains=q) | Q(city__icontains=q) | Q(code__icontains=q))
    if status == 'active':
        qs = qs.filter(is_active=True)
    elif status == 'inactive':
        qs = qs.filter(is_active=False)
    if ctype:
        qs = qs.filter(customer_type=ctype)

    total = qs.count()
    active = qs.filter(is_active=True).count()

    return render(request, 'crm/customer_list.html', {
        'page_title': 'Clients',
        'customers': qs.select_related('salesperson'),
        'total': total,
        'active': active,
        'q': q,
        'status': status,
        'ctype': ctype,
    })


@login_required
def customer_detail(request, pk):
    company = request.current_company
    customer = get_object_or_404(Customer, pk=pk, company=company)
    contacts = customer.contacts.all()
    activities = customer.activities.order_by('-date')[:10]
    quotes = customer.quotes.all().order_by('-created_at')[:5] if hasattr(customer, 'quotes') else []
    invoices = customer.invoices.all().order_by('-created_at')[:5] if hasattr(customer, 'invoices') else []

    return render(request, 'crm/customer_detail.html', {
        'page_title': customer.name,
        'customer': customer,
        'contacts': contacts,
        'activities': activities,
        'quotes': quotes,
        'invoices': invoices,
        'active_tab': request.GET.get('tab', 'info'),
    })


@login_required
def customer_create(request):
    company = request.current_company
    if request.method == 'POST':
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.company = company
            customer.created_by = request.user
            customer.save()
            messages.success(request, f'Client "{customer.name}" créé avec succès.')
            return redirect('crm:customer_detail', pk=customer.pk)
    else:
        form = CustomerForm()

    return render(request, 'crm/customer_form.html', {
        'page_title': 'Nouveau client',
        'form': form,
        'action': 'create',
    })


@login_required
def customer_edit(request, pk):
    company = request.current_company
    customer = get_object_or_404(Customer, pk=pk, company=company)
    if request.method == 'POST':
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(request, 'Client mis à jour avec succès.')
            return redirect('crm:customer_detail', pk=customer.pk)
    else:
        form = CustomerForm(instance=customer)

    return render(request, 'crm/customer_form.html', {
        'page_title': f'Modifier — {customer.name}',
        'form': form,
        'customer': customer,
        'action': 'edit',
    })


@login_required
def customer_delete(request, pk):
    company = request.current_company
    customer = get_object_or_404(Customer, pk=pk, company=company)
    if request.method == 'POST':
        name = customer.name
        customer.delete()
        messages.success(request, f'Client "{name}" supprimé.')
        return redirect('crm:customer_list')
    return render(request, 'crm/customer_confirm_delete.html', {
        'page_title': 'Supprimer le client',
        'customer': customer,
    })


# ─────────────────────────────────────────────────────────────
# PROSPECTS
# ─────────────────────────────────────────────────────────────

@login_required
def prospect_list(request):
    company = request.current_company
    qs = Prospect.objects.filter(company=company)

    q = request.GET.get('q', '')
    status = request.GET.get('status', '')

    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(email__icontains=q) | Q(contact_name__icontains=q))
    if status:
        qs = qs.filter(status=status)

    return render(request, 'crm/prospect_list.html', {
        'page_title': 'Prospects',
        'prospects': qs.select_related('salesperson'),
        'q': q,
        'status': status,
        'status_choices': Prospect.STATUS_CHOICES,
        'counts': {s: qs.filter(status=s).count() for s, _ in Prospect.STATUS_CHOICES},
    })


@login_required
def prospect_detail(request, pk):
    company = request.current_company
    prospect = get_object_or_404(Prospect, pk=pk, company=company)
    contacts = prospect.contacts.all()
    activities = prospect.activities.order_by('-date')[:10]
    opportunities = prospect.opportunities.all()

    return render(request, 'crm/prospect_detail.html', {
        'page_title': prospect.name,
        'prospect': prospect,
        'contacts': contacts,
        'activities': activities,
        'opportunities': opportunities,
        'active_tab': request.GET.get('tab', 'info'),
    })


@login_required
def prospect_create(request):
    company = request.current_company
    if request.method == 'POST':
        form = ProspectForm(request.POST)
        if form.is_valid():
            prospect = form.save(commit=False)
            prospect.company = company
            prospect.save()
            messages.success(request, f'Prospect "{prospect.name}" créé avec succès.')
            return redirect('crm:prospect_detail', pk=prospect.pk)
    else:
        form = ProspectForm()

    return render(request, 'crm/prospect_form.html', {
        'page_title': 'Nouveau prospect',
        'form': form,
        'action': 'create',
    })


@login_required
def prospect_edit(request, pk):
    company = request.current_company
    prospect = get_object_or_404(Prospect, pk=pk, company=company)
    if request.method == 'POST':
        form = ProspectForm(request.POST, instance=prospect)
        if form.is_valid():
            form.save()
            messages.success(request, 'Prospect mis à jour.')
            return redirect('crm:prospect_detail', pk=prospect.pk)
    else:
        form = ProspectForm(instance=prospect)

    return render(request, 'crm/prospect_form.html', {
        'page_title': f'Modifier — {prospect.name}',
        'form': form,
        'prospect': prospect,
        'action': 'edit',
    })


@login_required
def prospect_delete(request, pk):
    company = request.current_company
    prospect = get_object_or_404(Prospect, pk=pk, company=company)
    if request.method == 'POST':
        name = prospect.name
        prospect.delete()
        messages.success(request, f'Prospect "{name}" supprimé.')
        return redirect('crm:prospect_list')
    return render(request, 'crm/prospect_confirm_delete.html', {
        'page_title': 'Supprimer le prospect',
        'prospect': prospect,
    })


@login_required
def prospect_convert(request, pk):
    """Convertit un prospect en client."""
    company = request.current_company
    prospect = get_object_or_404(Prospect, pk=pk, company=company)
    if request.method == 'POST':
        customer = Customer.objects.create(
            company=company,
            name=prospect.name,
            contact_name=prospect.contact_name,
            email=prospect.email,
            phone=prospect.phone,
            city=prospect.city,
            created_by=request.user,
        )
        prospect.status = 'won'
        prospect.converted_to_customer = customer
        prospect.save()
        messages.success(request, f'"{prospect.name}" converti en client avec succès.')
        return redirect('crm:customer_detail', pk=customer.pk)
    return render(request, 'crm/prospect_convert.html', {
        'page_title': 'Convertir en client',
        'prospect': prospect,
    })


# ─────────────────────────────────────────────────────────────
# OPPORTUNITIES
# ─────────────────────────────────────────────────────────────

@login_required
def opportunity_list(request):
    company = request.current_company
    qs = Opportunity.objects.filter(company=company)

    q = request.GET.get('q', '')
    stage = request.GET.get('stage', '')

    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(customer__name__icontains=q))
    if stage:
        qs = qs.filter(stage=stage)

    total_revenue = sum(o.expected_revenue or 0 for o in qs)
    weighted = sum(o.weighted_revenue for o in qs)

    return render(request, 'crm/opportunity_list.html', {
        'page_title': 'Opportunités',
        'opportunities': qs.select_related('customer', 'prospect', 'salesperson'),
        'q': q,
        'stage': stage,
        'stage_choices': Opportunity.STAGE_CHOICES,
        'total_revenue': total_revenue,
        'weighted': weighted,
    })


@login_required
def opportunity_detail(request, pk):
    company = request.current_company
    opp = get_object_or_404(Opportunity, pk=pk, company=company)
    activities = opp.activities.order_by('-date')[:10]

    return render(request, 'crm/opportunity_detail.html', {
        'page_title': opp.name,
        'opp': opp,
        'activities': activities,
        'active_tab': request.GET.get('tab', 'info'),
    })


@login_required
def opportunity_create(request):
    company = request.current_company
    if request.method == 'POST':
        form = OpportunityForm(request.POST)
        if form.is_valid():
            opp = form.save(commit=False)
            opp.company = company
            opp.save()
            messages.success(request, f'Opportunité "{opp.name}" créée.')
            return redirect('crm:opportunity_detail', pk=opp.pk)
    else:
        form = OpportunityForm()
        # Filtre les listes déroulantes sur l'entreprise courante
        form.fields['customer'].queryset = Customer.objects.filter(company=company)
        form.fields['prospect'].queryset = Prospect.objects.filter(company=company)

    return render(request, 'crm/opportunity_form.html', {
        'page_title': 'Nouvelle opportunité',
        'form': form,
        'action': 'create',
    })


@login_required
def opportunity_edit(request, pk):
    company = request.current_company
    opp = get_object_or_404(Opportunity, pk=pk, company=company)
    if request.method == 'POST':
        form = OpportunityForm(request.POST, instance=opp)
        if form.is_valid():
            form.save()
            messages.success(request, 'Opportunité mise à jour.')
            return redirect('crm:opportunity_detail', pk=opp.pk)
    else:
        form = OpportunityForm(instance=opp)
        form.fields['customer'].queryset = Customer.objects.filter(company=company)
        form.fields['prospect'].queryset = Prospect.objects.filter(company=company)

    return render(request, 'crm/opportunity_form.html', {
        'page_title': f'Modifier — {opp.name}',
        'form': form,
        'opp': opp,
        'action': 'edit',
    })


@login_required
def opportunity_delete(request, pk):
    company = request.current_company
    opp = get_object_or_404(Opportunity, pk=pk, company=company)
    if request.method == 'POST':
        name = opp.name
        opp.delete()
        messages.success(request, f'Opportunité "{name}" supprimée.')
        return redirect('crm:opportunity_list')
    return render(request, 'crm/opportunity_confirm_delete.html', {
        'page_title': 'Supprimer l\'opportunité',
        'opp': opp,
    })


@login_required
def opportunity_mark_won(request, pk):
    company = request.current_company
    opp = get_object_or_404(Opportunity, pk=pk, company=company)
    opp.stage = 'closed_won'
    opp.probability = 100
    opp.save()
    messages.success(request, f'Opportunité "{opp.name}" marquée comme gagnée !')
    return redirect('crm:opportunity_detail', pk=opp.pk)


@login_required
def opportunity_mark_lost(request, pk):
    company = request.current_company
    opp = get_object_or_404(Opportunity, pk=pk, company=company)
    opp.stage = 'closed_lost'
    opp.probability = 0
    opp.save()
    messages.warning(request, f'Opportunité "{opp.name}" marquée comme perdue.')
    return redirect('crm:opportunity_detail', pk=opp.pk)


# ─────────────────────────────────────────────────────────────
# CONTACTS
# ─────────────────────────────────────────────────────────────

@login_required
def contact_list(request):
    company = request.current_company
    qs = Contact.objects.filter(company=company)

    q = request.GET.get('q', '')
    if q:
        qs = qs.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) |
            Q(email__icontains=q) | Q(job_title__icontains=q)
        )

    return render(request, 'crm/contact_list.html', {
        'page_title': 'Contacts',
        'contacts': qs.select_related('customer', 'prospect'),
        'q': q,
    })


@login_required
def contact_create(request):
    company = request.current_company
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            contact = form.save(commit=False)
            contact.company = company
            contact.save()
            messages.success(request, 'Contact créé avec succès.')
            return redirect('crm:contact_list')
    else:
        form = ContactForm()
        form.fields['customer'].queryset = Customer.objects.filter(company=company)
        form.fields['prospect'].queryset = Prospect.objects.filter(company=company)

    return render(request, 'crm/contact_form.html', {
        'page_title': 'Nouveau contact',
        'form': form,
        'action': 'create',
    })


@login_required
def contact_edit(request, pk):
    company = request.current_company
    contact = get_object_or_404(Contact, pk=pk, company=company)
    if request.method == 'POST':
        form = ContactForm(request.POST, instance=contact)
        if form.is_valid():
            form.save()
            messages.success(request, 'Contact mis à jour.')
            return redirect('crm:contact_list')
    else:
        form = ContactForm(instance=contact)
        form.fields['customer'].queryset = Customer.objects.filter(company=company)
        form.fields['prospect'].queryset = Prospect.objects.filter(company=company)

    return render(request, 'crm/contact_form.html', {
        'page_title': f'Modifier — {contact}',
        'form': form,
        'contact': contact,
        'action': 'edit',
    })


@login_required
def contact_delete(request, pk):
    company = request.current_company
    contact = get_object_or_404(Contact, pk=pk, company=company)
    if request.method == 'POST':
        contact.delete()
        messages.success(request, 'Contact supprimé.')
        return redirect('crm:contact_list')
    return render(request, 'crm/contact_confirm_delete.html', {
        'page_title': 'Supprimer le contact',
        'contact': contact,
    })


# index
@login_required
def index(request):
    return redirect('crm:customer_list')

def _stub(request, *args, **kwargs):
    from django.http import HttpResponse
    return HttpResponse('<h3 style="font-family:sans-serif;padding:2rem">Fonctionnalit� en cours de d�veloppement.</h3>')

customer_export = login_required(_stub)
customer_import = login_required(_stub)
contact_export = login_required(_stub)
opportunity_export = login_required(_stub)
prospect_export = login_required(_stub)
prospect_convert_bulk = login_required(_stub)

