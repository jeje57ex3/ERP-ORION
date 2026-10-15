"""Écrans des modèles de devis.

La mise en page du devis est fournie par l'exploitant sous forme de PDF, et
Orion y superpose les valeurs. Le pourquoi de ce choix est dans
apps/sales/quote_pdf.py ; on trouve ici les écrans qui le servent.

Module séparé de views.py, qui dépasse déjà le millier de lignes : un sujet
nouveau y serait noyé, et les imports de PDF n'ont rien à y faire.
"""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.sales.forms import (
    QuoteFromTemplateForm,
    QuoteTemplateFieldFormSet,
    QuoteTemplateForm,
)
from apps.sales.models import Quote, QuoteTemplate
from apps.sales.quote_pdf import (
    ModeleDevisError,
    dimensions_des_pages,
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


# ─── Éditeur visuel : poser des cadres sur la page ───────────────────────────

@login_required
def quote_template_page_image(request, pk, page):
    """La page du modèle, en PNG, servant de fond à l'éditeur."""
    from apps.sales.quote_pdf import rendre_page_en_png

    company = _entreprise(request)
    modele = get_object_or_404(QuoteTemplate, pk=pk, company=company)
    try:
        tampon, _largeur, _hauteur = rendre_page_en_png(modele, page)
    except ModeleDevisError as exc:
        return HttpResponse(str(exc), status=404, content_type='text/plain')

    reponse = HttpResponse(tampon.getvalue(), content_type='image/png')
    # L'image ne change que si le PDF change. On laisse le navigateur la
    # garder le temps d'une session de placement -- sans quoi chaque
    # changement de page la retelecharge.
    reponse['Cache-Control'] = 'private, max-age=600'
    return reponse


@login_required
def quote_template_editor(request, pk):
    """Placer les cadres à l'écran, sur le vrai document.

    Remplace la saisie de coordonnées. Les points PDF comptés depuis le bas de
    la page sont justes mais inhumains : personne ne les devine, et les
    trouver par essais successifs prend un temps déraisonnable. Ici on pose un
    cadre là où il doit être, et la conversion est faite par la machine — qui
    ne se trompe pas de sens.
    """
    from apps.sales.quote_pdf import ECHELLE_EDITEUR, dimensions_des_pages
    from apps.sales.models import QuoteTemplateField

    company = _entreprise(request)
    modele = get_object_or_404(QuoteTemplate, pk=pk, company=company)
    pages = dimensions_des_pages(modele)

    cadres = [
        {
            'id': champ.pk,
            'cle': champ.cle,
            'libelle': champ.get_cle_display(),
            'page': champ.page,
            'x': float(champ.x),
            'y': float(champ.y),
            'largeur': float(champ.largeur),
            'hauteur': float(champ.hauteur),
            'taille': champ.taille,
            'gras': champ.gras,
            'alignement': champ.alignement,
            'prefixe': champ.prefixe,
            'suffixe': champ.suffixe,
        }
        for champ in modele.fields.all()
    ]

    valeurs = [
        {'cle': cle, 'libelle': str(libelle)}
        for cle, libelle in QuoteTemplateField.CLES
    ]

    # Un gabarit d'adresse avec un jeton a substituer cote navigateur : le
    # resolveur d'URL de Django reste la seule source des adresses, et le
    # JavaScript n'en fabrique aucune a la main.
    url_image = reverse(
        'sales:quote_template_page_image', args=[modele.pk, 0],
    ).replace('/page/0.png', '/page/__PAGE__.png')

    return render(request, 'sales/quote_template_editor.html', {
        'page_title': f'Placer les cadres — {modele.name}',
        'modele': modele,
        'pages': pages,
        'echelle': ECHELLE_EDITEUR,
        'cadres_json': json.dumps(cadres, ensure_ascii=False),
        'pages_json': json.dumps(pages, ensure_ascii=False),
        'valeurs_json': json.dumps(valeurs, ensure_ascii=False),
        'valeurs': valeurs,
        'url_image': url_image,
    })


@login_required
@require_POST
def quote_template_save_frames(request, pk):
    """Enregistre les cadres posés par l'éditeur.

    Reçoit la liste complète et la substitue à l'ancienne : un enregistrement
    différentiel demanderait de suivre les identifiants côté navigateur et de
    distinguer création, modification et suppression — trois chemins pour un
    écran où l'on pose et déplace librement. Remplacer est plus simple, et
    simple veut dire vérifiable.
    """
    from apps.sales.models import QuoteTemplateField

    company = _entreprise(request)
    modele = get_object_or_404(QuoteTemplate, pk=pk, company=company)

    try:
        charge = json.loads(request.body.decode('utf-8') or '{}')
        cadres = charge.get('cadres')
        if not isinstance(cadres, list):
            raise ValueError('« cadres » doit être une liste.')
    except (ValueError, UnicodeDecodeError) as exc:
        return JsonResponse({'erreur': f'Requête illisible : {exc}'},
                            status=400)

    cles_connues = {cle for cle, _ in QuoteTemplateField.CLES}
    alignements = {'left', 'right', 'center'}
    nombre_pages = len(dimensions_des_pages(modele)) or 1

    a_creer = []
    for index, cadre in enumerate(cadres, start=1):
        if not isinstance(cadre, dict):
            return JsonResponse(
                {'erreur': f'Cadre {index} illisible.'}, status=400)

        cle = cadre.get('cle')
        if cle not in cles_connues:
            # Une cle inconnue viendrait d'une version plus recente de
            # l'ecran, ou d'une requete forgee : l'accepter enregistrerait un
            # cadre qui n'ecrira jamais rien.
            return JsonResponse(
                {'erreur': f'Valeur inconnue : {cle}'}, status=400)

        try:
            page = int(cadre.get('page', 1))
            x = float(cadre.get('x', 0))
            y = float(cadre.get('y', 0))
            largeur = float(cadre.get('largeur', 160))
            hauteur = float(cadre.get('hauteur', 16))
            taille = int(cadre.get('taille', 10))
        except (TypeError, ValueError):
            return JsonResponse(
                {'erreur': f'Cadre {index} : nombre invalide.'}, status=400)

        if not 1 <= page <= nombre_pages:
            return JsonResponse(
                {'erreur': f'Cadre {index} : page {page} inexistante.'},
                status=400)
        if largeur <= 0 or hauteur <= 0:
            return JsonResponse(
                {'erreur': f'Cadre {index} : cadre de taille nulle.'},
                status=400)

        a_creer.append(QuoteTemplateField(
            template=modele,
            cle=cle,
            page=page,
            x=round(x, 2),
            y=round(y, 2),
            largeur=round(largeur, 2),
            hauteur=round(hauteur, 2),
            taille=max(5, min(72, taille)),
            gras=bool(cadre.get('gras')),
            alignement=(
                cadre.get('alignement')
                if cadre.get('alignement') in alignements else 'left'
            ),
            prefixe=str(cadre.get('prefixe') or '')[:40],
            suffixe=str(cadre.get('suffixe') or '')[:40],
        ))

    # Tout ou rien : une substitution a moitie faite laisserait le modele sans
    # ses anciens cadres et sans les nouveaux.
    with transaction.atomic():
        modele.fields.all().delete()
        QuoteTemplateField.objects.bulk_create(a_creer)

    return JsonResponse({'enregistres': len(a_creer)})
