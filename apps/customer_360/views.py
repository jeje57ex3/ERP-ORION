from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from apps.crm.models import Customer
from .models import CustomerScore, CustomerTimelineEvent
from .services import get_customer_360_data, compute_customer_scores, add_timeline_event


@login_required
def customer_360(request, customer_pk):
    company = request.current_company
    if not company:
        return redirect('core:dashboard')
    customer = get_object_or_404(Customer, pk=customer_pk, company=company)
    data = get_customer_360_data(company, customer)
    return render(request, 'customer_360/customer_360.html', {
        'page_title': f'Vue 360 — {customer.name}',
        'customer': customer,
        **data,
    })


@login_required
@require_POST
def refresh_scores(request, customer_pk):
    company = request.current_company
    customer = get_object_or_404(Customer, pk=customer_pk, company=company)
    scores = compute_customer_scores(company, customer)
    return JsonResponse({'success': True, 'scores': scores})


@login_required
@require_POST
def add_note(request, customer_pk):
    company = request.current_company
    customer = get_object_or_404(Customer, pk=customer_pk, company=company)
    note_text = request.POST.get('note', '').strip()
    if note_text:
        add_timeline_event(
            company, customer, 'note', 'Note interne',
            description=note_text,
        )
    return redirect('customer_360:view', customer_pk=customer_pk)
