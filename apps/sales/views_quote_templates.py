"""Écrans des modèles de devis.

La mise en page du devis est fournie par l'exploitant sous forme de PDF, et
Orion y superpose les valeurs. Le pourquoi de ce choix est dans
apps/sales/quote_pdf.py ; on trouve ici les écrans qui le servent.

Module séparé de views.py, qui dépasse déjà le millier de lignes : un sujet
nouveau y serait noyé, et les imports de PDF n'ont rien à y faire.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.sales.forms import (
    QuoteFromTemplateForm,
    QuoteTemplateFieldFormSet,
    QuoteTemplateForm,
)
from apps.sales.models import Quote, QuoteTemplate
from apps.sales.quote_pdf import (
    ModeleDevisError,
    champs_de_formulaire_detectes,
    devis_exemple,
    generer_grille_de_calage,
    nombre_de_pages,
    remplir_modele,
)


def _entreprise(request):
    return getattr(request, 'current_company', None)


@login_required
def quote_template_list(request):
    company = _entreprise(request)
    modeles = QuoteTemplate.objects.filter(company=company)

    # Le nombre de pages est lu dans le PDF : l'afficher évite de placer un
    # champ en page 2 d'un modèle qui n'en a qu'une — erreur qui ne se verrait
    # autrement qu'à la première génération.
    details = [
        {'modele': m, 'pages': nombre_de_pages(m), 'champs': m.fields.count()}
        for m in modeles
    ]
    return render(request, 'sales/quote_template_list.html', {
        'page_title': 'Modèles de devis',
        'details': details,
    })


@login_required
def quote_template_create(request):
    company = _entreprise(request)
    if request.method == 'POST':
        form = QuoteTemplateForm(request.POST, request.FILES)
        if form.is_valid():
            modele = form.save(commit=False)
            modele.company = company
            modele.created_by = request.user
            modele.save()
            messages.success(
                request,
                f'Modèle « {modele.name} » enregistré. Téléchargez la grille '
                'de calage, puis placez les valeurs à écrire dessus.',
            )
            return redirect('sales:quote_template_edit', pk=modele.pk)
    else:
        form = QuoteTemplateForm()

    return render(request, 'sales/quote_template_form.html', {
        'page_title': 'Nouveau modèle de devis',
        'form': form,
        'action': 'create',
    })


@login_required
def quote_template_edit(request, pk):
    company = _entreprise(request)
    modele = get_object_or_404(QuoteTemplate, pk=pk, company=company)

    if request.method == 'POST':
        form = QuoteTemplateForm(request.POST, request.FILES, instance=modele)
        formset = QuoteTemplateFieldFormSet(request.POST, instance=modele)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'Modèle mis à jour.')
            return redirect('sales:quote_template_edit', pk=modele.pk)
    else:
        form = QuoteTemplateForm(instance=modele)
        formset = QuoteTemplateFieldFormSet(instance=modele)

    return render(request, 'sales/quote_template_form.html', {
        'page_title': f'Modèle — {modele.name}',
        'form': form,
        'formset': formset,
        'modele': modele,
        'pages': nombre_de_pages(modele),
        # Un PDF prepare comme formulaire porte des champs nommes. Les relever
        # permet de proposer un placement plutot que de faire saisir des
        # coordonnees pour rien. Vide pour un PDF plat, cas le plus courant.
        'champs_pdf': champs_de_formulaire_detectes(modele),
        'action': 'edit',
    })


@login_required
@require_POST
def quote_template_delete(request, pk):
    company = _entreprise(request)
    modele = get_object_or_404(QuoteTemplate, pk=pk, company=company)
    nom = modele.name
    modele.delete()
    messages.success(request, f'Modèle « {nom} » supprimé.')
    return redirect('sales:quote_template_list')


@login_required
def quote_template_grid(request, pk):
    """Le modèle avec un quadrillage coté, pour relever les coordonnées.

    Placer un champ demande des points PDF comptés depuis le BAS de la page.
    Les chercher par essais successifs — modifier, régénérer, regarder — prend
    un temps déraisonnable pour une quinzaine de champs. Cette grille les
    donne à lire.
    """
    company = _entreprise(request)
    modele = get_object_or_404(QuoteTemplate, pk=pk, company=company)
    try:
        tampon = generer_grille_de_calage(modele)
    except ModeleDevisError as exc:
        messages.error(request, str(exc))
        return redirect('sales:quote_template_edit', pk=pk)

    reponse = HttpResponse(tampon.getvalue(), content_type='application/pdf')
    reponse['Content-Disposition'] = (
        f'inline; filename="grille-calage-{modele.pk}.pdf"')
    return reponse


@login_required
def quote_template_preview(request, pk):
    """Le modèle rempli de valeurs d'exemple.

    On règle un modèle AVANT d'avoir un devis : prévisualiser avec de vraies
    données supposerait d'en créer un pour rien. L'exemple sert à vérifier le
    placement, pas les montants.
    """
    company = _entreprise(request)
    modele = get_object_or_404(QuoteTemplate, pk=pk, company=company)
    try:
        tampon = remplir_modele(devis_exemple(company), modele)
    except ModeleDevisError as exc:
        messages.error(request, str(exc))
        return redirect('sales:quote_template_edit', pk=pk)

    reponse = HttpResponse(tampon.getvalue(), content_type='application/pdf')
    reponse['Content-Disposition'] = (
        f'inline; filename="apercu-{modele.pk}.pdf"')
    return reponse


@login_required
def quote_pdf_download(request, pk):
    """Le PDF d'un vrai devis, posé sur son modèle."""
    company = _entreprise(request)
    quote = get_object_or_404(Quote, pk=pk, company=company)

    modeles = QuoteTemplate.objects.filter(company=company, is_active=True)
    demande = request.GET.get('modele')
    modele = None
    if demande:
        # Filtre sur l'entreprise par construction (le queryset l'est deja) :
        # un identifiant venu d'une autre societe ne designe rien.
        modele = modeles.filter(pk=demande).first()
    if modele is None:
        modele = modeles.filter(is_default=True).first() or modeles.first()

    if modele is None:
        messages.error(
            request,
            'Aucun modèle de devis actif. Déposez votre devis vierge en PDF '
            'dans Devis ▸ Modèles de devis.',
        )
        return redirect('sales:quote_detail', pk=pk)

    try:
        tampon = remplir_modele(quote, modele)
    except ModeleDevisError as exc:
        messages.error(request, str(exc))
        return redirect('sales:quote_detail', pk=pk)

    reponse = HttpResponse(tampon.getvalue(), content_type='application/pdf')
    reponse['Content-Disposition'] = (
        f'inline; filename="{quote.number or "devis"}.pdf"')
    return reponse


@login_required
def quote_create_from_template(request):
    """Crée un devis en choisissant un modèle et un client.

    Le modèle porte la mise en page et l'emplacement des valeurs, pas les
    lignes : celles-ci restent à saisir, ou viennent d'ailleurs
    (configurateur, devis guidé BTP). Ce qui est automatique ici, c'est le
    numéro, la date, le rattachement au client et le rendu final.
    """
    from apps.core.numbering import next_number

    company = _entreprise(request)
    if request.method == 'POST':
        form = QuoteFromTemplateForm(request.POST, company=company)
        if form.is_valid():
            modele = form.cleaned_data['template']
            quote = Quote.objects.create(
                company=company,
                customer=form.cleaned_data['customer'],
                subject=form.cleaned_data['subject'] or modele.name,
                # Numerotation atomique, et non un comptage : deux devis crees
                # en meme temps recevaient le meme numero.
                number=next_number(company, 'quote') or '',
                created_by=request.user,
            )
            messages.success(
                request,
                f'Devis {quote.number} créé depuis « {modele.name} ». '
                'Ajoutez les lignes, puis générez le PDF.',
            )
            return redirect('sales:quote_detail', pk=quote.pk)
    else:
        form = QuoteFromTemplateForm(company=company)

    return render(request, 'sales/quote_from_template.html', {
        'page_title': 'Nouveau devis depuis un modèle',
        'form': form,
    })
