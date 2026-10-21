"""Matériaux et fournitures : le catalogue, les achats de chantier, les lignes de devis.

Trois écrans qui tiennent par le même fil :

1. Un **catalogue** que l'entreprise alimente elle-même. Deux prix par
   article — ce qu'on paie, ce qu'on facture.
2. Sur le **chantier**, les fournitures et le matériel réellement achetés,
   au prix d'achat. C'est ce qui rend le coût d'un chantier vérifiable
   plutôt que estimé de mémoire.
3. Dans le **devis BTP**, des lignes piochées dans ce catalogue, au prix de
   vente.

**Le prix d'achat, le fournisseur et la marge ne sortent pas d'ici.** Ils
s'affichent dans le catalogue et sur la fiche chantier, qui sont des écrans
internes ; ils n'ont rien à faire dans un devis remis au client ni dans le
portail client. Les lignes de devis recopient le prix de VENTE et ne
traversent jamais `line.material.purchase_price`.

Deuxième règle, qui revient à chaque vue : **tout est borné à
`request.current_company`**, y compris en passant par une relation
(`project__company`, `quote__company`). Un identifiant forgé dans l'URL ne
doit pas atteindre le chantier d'une autre société.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import BTPQuoteLineForm, MaterialForm, ProjectSupplyForm
from .models import BTPProject, BTPQuote, BTPQuoteLine, Material, ProjectSupply


def _retour_fournitures(project_pk):
    """L'onglet des fournitures sur la fiche chantier.

    Par reverse() et non en dur : ce module est monte sous « btp/ » et non
    sous « erp/btp/ ». Une adresse ecrite a la main ici renverrait un 404
    que seul un clic revelerait -- deja vu dans ce depot.
    """
    adresse = reverse('btp:project_detail', args=[project_pk])
    return f'{adresse}?tab=supplies'


# ─── Le catalogue ────────────────────────────────────────────────────────────

@login_required
def material_list(request):
    company = request.current_company
    q = (request.GET.get('q') or '').strip()
    kind = request.GET.get('kind') or ''
    category = request.GET.get('category') or ''

    articles = Material.objects.filter(company=company).select_related('supplier')
    if q:
        articles = articles.filter(
            Q(name__icontains=q)
            | Q(reference__icontains=q)
            | Q(category__icontains=q)
            | Q(supplier_reference__icontains=q)
        )
    if kind:
        articles = articles.filter(kind=kind)
    if category:
        articles = articles.filter(category=category)
    # « A tarifer » : les articles dont le prix est encore un repere. Sans
    # ce filtre, retrouver ce qui attend un vrai tarif demanderait de
    # parcourir tout le catalogue a l'oeil.
    indicatif = request.GET.get('indicatif') == '1'
    if indicatif:
        articles = articles.filter(prix_indicatif=True)

    # Les catégories proposées au filtre sont celles réellement utilisées :
    # une liste figée se désynchronise de ce que l'entreprise saisit.
    categories = (Material.objects.filter(company=company)
                  .exclude(category='')
                  .values_list('category', flat=True)
                  .distinct().order_by('category'))

    return render(request, 'btp/material_list.html', {
        'page_title': 'Catalogue : matériaux, fournitures et actions',
        'articles': articles,
        'q': q,
        'kind': kind,
        'category': category,
        'categories': categories,
        'kind_choices': Material.KIND_CHOICES,
        'indicatif': indicatif,
        'active_subnav': 'materials',
    })


@login_required
def material_create(request):
    company = request.current_company
    form = MaterialForm(request.POST or None, company=company)
    if request.method == 'POST' and form.is_valid():
        article = form.save(commit=False)
        article.company = company
        article.save()
        messages.success(request, f'« {article.name} » ajouté au catalogue.')
        # Enchaîner les saisies : on alimente un catalogue par lots, pas un
        # article à la fois.
        if request.POST.get('enchainer'):
            return redirect('btp:material_create')
        return redirect('btp:material_list')
    return render(request, 'btp/material_form.html', {
        'page_title': 'Nouveau matériau / fourniture',
        'form': form,
        'action': 'create',
        'active_subnav': 'materials',
    })


@login_required
def material_edit(request, pk):
    company = request.current_company
    article = get_object_or_404(Material, pk=pk, company=company)
    form = MaterialForm(request.POST or None, instance=article, company=company)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'« {article.name} » mis à jour.')
        return redirect('btp:material_list')
    return render(request, 'btp/material_form.html', {
        'page_title': article.name,
        'form': form,
        'article': article,
        'action': 'edit',
        'active_subnav': 'materials',
    })


@login_required
@require_POST
def material_delete(request, pk):
    """Retire un article du catalogue, ou le désactive s'il est déjà utilisé.

    Désactiver plutôt que supprimer quand des achats ou des lignes de devis
    le citent : les FK sont en SET_NULL, donc la suppression ne casserait
    rien — mais les lignes perdraient leur origine, et un devis envoyé ne
    saurait plus d'où venait son prix.
    """
    company = request.current_company
    article = get_object_or_404(Material, pk=pk, company=company)
    nom = article.name

    utilise = (article.project_supplies.exists()
               or article.quote_lines.exists())
    if utilise:
        article.is_active = False
        article.save(update_fields=['is_active'])
        messages.info(
            request,
            f'« {nom} » est utilisé par des achats ou des devis : il a été '
            'désactivé plutôt que supprimé, pour ne pas leur faire perdre '
            'leur origine.')
    else:
        article.delete()
        messages.success(request, f'« {nom} » supprimé du catalogue.')
    return redirect('btp:material_list')


# ─── Les achats d'un chantier ────────────────────────────────────────────────

@login_required
def project_supply_create(request, project_pk):
    company = request.current_company
    project = get_object_or_404(BTPProject, pk=project_pk, company=company)
    form = ProjectSupplyForm(request.POST or None, company=company)

    if request.method == 'POST' and form.is_valid():
        achat = form.save(commit=False)
        achat.project = project
        achat.created_by = request.user
        achat.save()
        messages.success(
            request,
            f'{achat.description} — {achat.total_ht:.2f} € HT ajouté au '
            f'chantier.')
        if request.POST.get('enchainer'):
            return redirect('btp:project_supply_create', project_pk=project.pk)
        return redirect(_retour_fournitures(project.pk))

    return render(request, 'btp/project_supply_form.html', {
        'page_title': 'Ajouter une fourniture',
        'form': form,
        'project': project,
        'action': 'create',
    })


@login_required
def project_supply_edit(request, pk):
    company = request.current_company
    achat = get_object_or_404(ProjectSupply, pk=pk, project__company=company)
    form = ProjectSupplyForm(request.POST or None, instance=achat,
                             company=company)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Achat mis à jour.')
        return redirect(_retour_fournitures(achat.project.pk))
    return render(request, 'btp/project_supply_form.html', {
        'page_title': achat.description,
        'form': form,
        'project': achat.project,
        'achat': achat,
        'action': 'edit',
    })


@login_required
@require_POST
def project_supply_delete(request, pk):
    company = request.current_company
    achat = get_object_or_404(ProjectSupply, pk=pk, project__company=company)
    project_pk = achat.project.pk
    achat.delete()
    messages.success(request, 'Achat retiré du chantier.')
    return redirect(_retour_fournitures(project_pk))


@login_required
@require_POST
def project_report_supplies(request, pk):
    """Recopie le total des fournitures dans le coût réel du chantier.

    Action explicite, et c'est volontaire : `actual_cost` est saisi à la
    main et contient peut-être déjà de la main-d'œuvre ou de la
    sous-traitance. Le mettre à jour automatiquement à chaque achat
    écraserait un chiffre que personne n'a demandé de remplacer — d'où ce
    bouton, dont le libellé dit ce qu'il remplace.
    """
    company = request.current_company
    project = get_object_or_404(BTPProject, pk=pk, company=company)
    ancien = project.actual_cost
    project.actual_cost = project.total_fournitures
    project.save(update_fields=['actual_cost'])
    messages.success(
        request,
        f'Coût réel passé de {ancien:.2f} € à {project.actual_cost:.2f} € HT '
        f'(total des fournitures et du matériel).')
    return redirect(_retour_fournitures(project.pk))


# ─── Les lignes d'un devis BTP ───────────────────────────────────────────────

@login_required
def quote_line_create(request, quote_pk):
    company = request.current_company
    quote = get_object_or_404(BTPQuote, pk=quote_pk, company=company)
    form = BTPQuoteLineForm(request.POST or None, quote=quote)

    if request.method == 'POST' and form.is_valid():
        ligne = form.save(commit=False)
        ligne.quote = quote
        # En fin de devis : l'ordre d'ajout est l'ordre voulu, et repartir
        # de 0 empilerait toutes les lignes au même rang.
        dernier = quote.lines.order_by('-order').values_list(
            'order', flat=True).first()
        ligne.order = (dernier or 0) + 1
        ligne.save()
        quote.calculate_totals()
        messages.success(request, 'Ligne ajoutée.')
        if request.POST.get('enchainer'):
            return redirect('btp:quote_line_create', quote_pk=quote.pk)
        return redirect('btp:quote_detail', pk=quote.pk)

    return render(request, 'btp/quote_line_form.html', {
        'page_title': 'Ajouter une ligne',
        'form': form,
        'quote': quote,
        'action': 'create',
    })


@login_required
def quote_line_edit(request, pk):
    company = request.current_company
    ligne = get_object_or_404(BTPQuoteLine, pk=pk, quote__company=company)
    form = BTPQuoteLineForm(request.POST or None, instance=ligne,
                            quote=ligne.quote)
    if request.method == 'POST' and form.is_valid():
        form.save()
        ligne.quote.calculate_totals()
        messages.success(request, 'Ligne mise à jour.')
        return redirect('btp:quote_detail', pk=ligne.quote.pk)
    return render(request, 'btp/quote_line_form.html', {
        'page_title': 'Modifier la ligne',
        'form': form,
        'quote': ligne.quote,
        'ligne': ligne,
        'action': 'edit',
    })


@login_required
@require_POST
def quote_line_delete(request, pk):
    company = request.current_company
    ligne = get_object_or_404(BTPQuoteLine, pk=pk, quote__company=company)
    quote = ligne.quote
    ligne.delete()
    # Après suppression, sinon le devis garde le total de la ligne retirée.
    quote.calculate_totals()
    messages.success(request, 'Ligne supprimée.')
    return redirect('btp:quote_detail', pk=quote.pk)
