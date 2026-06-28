from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .models import Document, DocumentCategory
from .forms import DocumentForm


@login_required
def index(request):
    return redirect('documents:document_list')


@login_required
def document_list(request):
    company = request.current_company
    qs = Document.objects.filter(company=company)
    doc_type = request.GET.get('type', '')
    search = request.GET.get('q', '')
    if doc_type:
        qs = qs.filter(document_type=doc_type)
    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(tags__icontains=search))
    return render(request, 'documents/document_list.html', {
        'documents': qs, 'doc_type': doc_type, 'search': search,
        'type_choices': Document.DOCUMENT_TYPES,
        'page_title': 'Documents', 'active_module': 'documents',
    })


@login_required
def document_detail(request, pk):
    company = request.current_company
    doc = get_object_or_404(Document, pk=pk, company=company)
    return render(request, 'documents/document_detail.html', {'doc': doc})


@login_required
def document_create(request):
    company = request.current_company
    form = DocumentForm(company=company)
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES, company=company)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.company = company
            doc.uploaded_by = request.user
            if doc.file:
                doc.file_size = doc.file.size
            doc.save()
            messages.success(request, 'Document ajouté avec succès.')
            return redirect('documents:document_detail', pk=doc.pk)
    return render(request, 'documents/document_form.html', {'form': form, 'action': 'create'})


@login_required
def document_edit(request, pk):
    company = request.current_company
    doc = get_object_or_404(Document, pk=pk, company=company)
    form = DocumentForm(instance=doc, company=company)
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES, instance=doc, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Document mis à jour.')
            return redirect('documents:document_detail', pk=pk)
    return render(request, 'documents/document_form.html', {'form': form, 'doc': doc, 'action': 'edit'})


@login_required
def document_delete(request, pk):
    company = request.current_company
    doc = get_object_or_404(Document, pk=pk, company=company)
    if request.method == 'POST':
        doc.delete()
        messages.success(request, 'Document supprimé.')
        return redirect('documents:document_list')
    return render(request, 'documents/document_confirm_delete.html', {'doc': doc})


