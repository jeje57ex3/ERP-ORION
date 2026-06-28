from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from .models import SmartDocument
from .services import search_documents, get_expiring_documents


@login_required
def document_list(request):
    company = request.current_company
    if not company:
        return redirect('core:dashboard')
    q = request.GET.get('q', '')
    doc_type = request.GET.get('type', '')
    brand_key = request.GET.get('brand', '')
    qs = search_documents(company, q=q, document_type=doc_type, brand_key=brand_key)
    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get('page', 1))
    expiring = get_expiring_documents(company, days_ahead=30)[:5]
    return render(request, 'smart_documents/document_list.html', {
        'page_title': 'Documents intelligents',
        'documents': page, 'expiring': expiring,
        'q': q, 'filter_type': doc_type,
    })


@login_required
def document_detail(request, pk):
    company = request.current_company
    doc = get_object_or_404(SmartDocument, pk=pk, company=company)
    return render(request, 'smart_documents/document_detail.html', {
        'page_title': doc.title, 'document': doc,
        'signature_requests': doc.signature_requests.all().order_by('-created_at'),
    })
