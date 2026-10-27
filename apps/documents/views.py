from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from apps.core.media_access import servir_fichier_autorise
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
def document_download(request, pk):
    """Télécharge un document, borné à l'entreprise courante.

    `documents/` fait partie des préfixes que /media/ refuse : ces fichiers
    sont des contrats, des factures, des plans et des rapports
    d'entreprise, et certains sont marqués confidentiels. Une URL devinable
    les aurait rendus lisibles depuis n'importe quel compte, de n'importe
    quelle entreprise.

    Le bornage est celui de `document_detail`, qui affiche le lien — ni
    plus strict, ni plus permissif. Un bouton plus permissif que la page
    qui le porte serait une fuite d'autant plus discrète qu'aucun écran ne
    la montrerait.
    """
    company = request.current_company
    doc = get_object_or_404(Document, pk=pk, company=company)
    return servir_fichier_autorise(doc.file, doc.title)


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


