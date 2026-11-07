"""apps/btp/views_etapes.py — étapes de chantier et modèles réutilisables.

Deux écrans et leur plomberie :

  * le PLANNING d'un chantier : ses étapes, et dans chaque étape les points
    à remplir (accès, nacelle, hauteur…)
  * les MODÈLES de chantier : étapes et points écrits une fois, appliqués à
    chaque nouveau chantier

Tout est pilotable depuis l'interface — aucune commande à taper. C'est une
contrainte explicite du projet et non une préférence : les modèles
s'écrivent, se réordonnent et se suppriment dans l'ERP.

Règle d'isolation, appliquée à chaque vue : un objet n'est atteint qu'en
remontant jusqu'à `company`. Un modèle par `company=company`, une étape par
`project__company=company`, un point par `step__project__company=company`.
Jamais par sa seule clé primaire : un identifiant recopié d'une autre
société passerait.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.media_access import servir_fichier_autorise

from . import services_etapes as svc
from .forms_etapes import (
    ChoisirUnModeleForm,
    EtapeDuChantierForm,
    PointsDeLEtapeForm,
    ProjectTemplateForm,
    ProjectTemplateItemForm,
    ProjectTemplateStepForm,
)
from .models import (
    BTPProject,
    ProjectPlanStep,
    ProjectStepItem,
    ProjectTemplate,
    ProjectTemplateItem,
    ProjectTemplateStep,
)


# ─── Planning d'un chantier ──────────────────────────────────────────────────

@login_required
def project_planning(request, pk):
    """Les étapes du chantier, avec l'avancement des points de chaque étape."""
    company = request.current_company
    project = get_object_or_404(BTPProject, pk=pk, company=company)

    etapes = (ProjectPlanStep.objects
              .filter(project=project)
              .prefetch_related('items')
              .select_related('responsible')
              .order_by('order', 'pk'))

    lignes = []
    manquants = []
    for etape in etapes:
        remplis, total = svc.avancement_des_points(etape)
        vides = [point for point in etape.items.all()
                 if point.is_required and not point.is_answered]
        lignes.append({
            'etape': etape,
            'remplis': remplis,
            'total': total,
            # Pas de division par zéro, et pas de barre à 0 % pour une
            # étape qui n'a aucun point à remplir : elle est complète par
            # construction.
            'pourcentage': 100 if total == 0 else int(remplis * 100 / total),
            'manquants': vides,
        })
        if vides:
            manquants.append({'etape': etape, 'points': vides})

    # Le bandeau d'avertissement est construit à partir de `lignes` et non
    # par un second `points_manquants(project)` : celui-ci refait les mêmes
    # requêtes pour recalculer ce qu'on vient de calculer.
    return render(request, 'btp/etapes/project_planning.html', {
        'project': project,
        'lignes': lignes,
        'manquants': manquants,
        'modeles': svc.modeles_disponibles(company),
        'page_title': f'Étapes — {project.name}',
        'active_module': 'btp',
        'active_subnav': 'projects',
    })


@login_required
def project_apply_template(request, pk):
    """Applique un modèle à un chantier depuis l'interface."""
    company = request.current_company
    project = get_object_or_404(BTPProject, pk=pk, company=company)

    if request.method == 'POST':
        form = ChoisirUnModeleForm(request.POST, company=company)
        if form.is_valid():
            cree = svc.appliquer_le_modele(
                project, form.cleaned_data['template'],
                remplacer=form.cleaned_data['remplacer'])
            if cree:
                messages.success(
                    request,
                    f'{cree} étape(s) créée(s) depuis le modèle '
                    f'« {form.cleaned_data["template"].name} ».')
            else:
                # appliquer_le_modele() ne fait rien plutôt que de doubler
                # les étapes. Le dire, sinon l'utilisateur croit à un bug.
                messages.warning(
                    request,
                    'Ce chantier a déjà des étapes. Cochez « Remplacer les '
                    'étapes existantes » pour repartir du modèle — les '
                    'réponses déjà saisies seront perdues.')
            return redirect('btp:project_planning', pk=project.pk)
    else:
        form = ChoisirUnModeleForm(company=company)
        modele = svc.modele_par_defaut(company)
        if modele:
            form.initial['template'] = modele.pk

    return render(request, 'btp/etapes/apply_template.html', {
        'project': project,
        'form': form,
        'a_deja_des_etapes': ProjectPlanStep.objects.filter(
            project=project).exists(),
        'page_title': 'Appliquer un modèle',
        'active_module': 'btp',
    })


@login_required
def step_create(request, pk):
    """Ajouter une étape à la main, hors modèle."""
    company = request.current_company
    project = get_object_or_404(BTPProject, pk=pk, company=company)

    if request.method == 'POST':
        form = EtapeDuChantierForm(request.POST, company=company)
        if form.is_valid():
            etape = form.save(commit=False)
            etape.project = project
            etape.save()
            messages.success(request, f'Étape « {etape.name} » ajoutée.')
            return redirect('btp:project_planning', pk=project.pk)
    else:
        # L'étape nouvelle se place à la fin, et non en 0 où elle
        # remonterait devant tout le reste.
        dernier = (ProjectPlanStep.objects.filter(project=project)
                   .order_by('-order').values_list('order', flat=True).first())
        form = EtapeDuChantierForm(
            company=company, initial={'order': (dernier or 0) + 1})

    return render(request, 'btp/etapes/step_form.html', {
        'project': project,
        'form': form,
        'action': 'create',
        'page_title': 'Nouvelle étape',
        'active_module': 'btp',
    })


@login_required
def step_detail(request, pk):
    """Une étape : ses propriétés et ses points à remplir.

    Les deux formulaires sont sur la MÊME page et postés ensemble. Séparer
    « modifier l'étape » de « remplir les points » obligerait à deux
    allers-retours pour une visite sur place, carnet en main.
    """
    company = request.current_company
    etape = get_object_or_404(
        ProjectPlanStep.objects.select_related('project'),
        pk=pk, project__company=company)
    # select_related sur les deux fiches désignables : sans cela, afficher
    # « DEV-0012 — 4 300 € » part en une requête par point.
    points = list(etape.items
                  .select_related('answer_quote', 'answer_quote__customer',
                                  'answer_supplier')
                  .order_by('order', 'pk'))

    if request.method == 'POST':
        form_etape = EtapeDuChantierForm(
            request.POST, instance=etape, company=company)
        form_points = PointsDeLEtapeForm(
            request.POST, request.FILES, points=points,
            company=company, project=etape.project)

        if form_etape.is_valid() and form_points.is_valid():
            with transaction.atomic():
                form_etape.save()
                for point in points:
                    svc.enregistrer_la_reponse(
                        point, form_points.cleaned_data, user=request.user)

            # On AVERTIT, on ne bloque pas : l'étape est enregistrée, et
            # ce qui manque est rappelé. Refuser l'enregistrement ferait
            # perdre le reste de la saisie.
            vides = [point for point in points
                     if point.is_required and not point.is_answered]
            messages.success(request, 'Étape enregistrée.')
            if vides:
                liste = ', '.join(point.label for point in vides[:5])
                reste = len(vides) - 5
                if reste > 0:
                    liste += f' et {reste} autre(s)'
                messages.warning(
                    request,
                    f'{len(vides)} point(s) important(s) restent à '
                    f'renseigner : {liste}.')
            return redirect('btp:step_detail', pk=etape.pk)
    else:
        form_etape = EtapeDuChantierForm(instance=etape, company=company)
        form_points = PointsDeLEtapeForm(
            points=points, company=company, project=etape.project)

    return render(request, 'btp/etapes/step_detail.html', {
        'project': etape.project,
        'etape': etape,
        'form_etape': form_etape,
        'form_points': form_points,
        'page_title': etape.name,
        'active_module': 'btp',
    })


@login_required
@require_POST
def step_delete(request, pk):
    company = request.current_company
    etape = get_object_or_404(
        ProjectPlanStep.objects.select_related('project'),
        pk=pk, project__company=company)
    projet_pk = etape.project.pk
    nom = etape.name
    etape.delete()
    messages.success(request, f'Étape « {nom} » supprimée.')
    return redirect('btp:project_planning', pk=projet_pk)


@login_required
def step_item_photo(request, pk):
    """La photo d'un point de contrôle.

    Elle n'est pas servie par /media/ : voir `PREFIXES_INTERDITS` dans
    apps/core/media_access.py. La photo d'un local technique ou d'un tableau
    électrique montre l'intérieur de chez un client, et son chemin est
    devinable (un entier qui s'incrémente). Seule une vue qui remonte
    jusqu'à `company` peut décider qui a le droit de la lire.
    """
    company = request.current_company
    point = get_object_or_404(
        ProjectStepItem.objects.select_related('step__project'),
        pk=pk, step__project__company=company)
    if not point.answer_photo:
        from django.http import Http404
        raise Http404
    return servir_fichier_autorise(
        point.answer_photo, nom=point.label, afficher_si_image=True)


# ─── Modèles de chantier ─────────────────────────────────────────────────────

@login_required
def template_list(request):
    from .modeles_prets import catalogue_pour_affichage

    company = request.current_company
    modeles = (ProjectTemplate.objects
               .filter(company=company)
               .annotate(nb_etapes=Count('steps', distinct=True))
               .order_by('-is_default', 'name'))
    return render(request, 'btp/etapes/template_list.html', {
        'modeles': modeles,
        # Les modèles prêts à l'emploi sont proposés MÊME quand
        # l'entreprise en a déjà : on installe l'électricité en janvier et
        # l'étanchéité en mars. Les réserver à la page vide les rendait
        # inatteignables dès le premier modèle créé.
        'catalogue': catalogue_pour_affichage(),
        'page_title': 'Modèles de chantier',
        'active_module': 'btp',
        'active_subnav': 'templates',
    })


@login_required
def template_create(request):
    company = request.current_company
    if request.method == 'POST':
        form = ProjectTemplateForm(request.POST, company=company)
        if form.is_valid():
            modele = form.save(commit=False)
            modele.company = company
            modele.save()
            messages.success(request, f'Modèle « {modele.name} » créé. '
                                      'Ajoutez-lui des étapes.')
            return redirect('btp:template_detail', pk=modele.pk)
    else:
        form = ProjectTemplateForm(company=company)
    return render(request, 'btp/etapes/template_form.html', {
        'form': form,
        'action': 'create',
        'page_title': 'Nouveau modèle de chantier',
        'active_module': 'btp',
    })


@login_required
def template_detail(request, pk):
    company = request.current_company
    modele = get_object_or_404(ProjectTemplate, pk=pk, company=company)
    etapes = (modele.steps
              .prefetch_related(Prefetch(
                  'items',
                  queryset=ProjectTemplateItem.objects.order_by('order', 'pk')))
              .order_by('order', 'pk'))
    return render(request, 'btp/etapes/template_detail.html', {
        'modele': modele,
        'etapes': etapes,
        'page_title': modele.name,
        'active_module': 'btp',
        'active_subnav': 'templates',
    })


@login_required
def template_edit(request, pk):
    company = request.current_company
    modele = get_object_or_404(ProjectTemplate, pk=pk, company=company)
    if request.method == 'POST':
        form = ProjectTemplateForm(request.POST, instance=modele,
                                   company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Modèle mis à jour.')
            return redirect('btp:template_detail', pk=modele.pk)
    else:
        form = ProjectTemplateForm(instance=modele, company=company)
    return render(request, 'btp/etapes/template_form.html', {
        'form': form,
        'modele': modele,
        'action': 'edit',
        'page_title': f'Modifier — {modele.name}',
        'active_module': 'btp',
    })


@login_required
def template_delete(request, pk):
    company = request.current_company
    modele = get_object_or_404(ProjectTemplate, pk=pk, company=company)
    if request.method == 'POST':
        nom = modele.name
        modele.delete()
        messages.success(request, f'Modèle « {nom} » supprimé.')
        return redirect('btp:template_list')
    return render(request, 'btp/etapes/template_confirm_delete.html', {
        'modele': modele,
        # Les chantiers déjà créés ne sont PAS touchés : leurs étapes sont
        # des copies. Le dire, sinon la suppression fait peur à juste titre.
        'page_title': f'Supprimer — {modele.name}',
        'active_module': 'btp',
    })


@login_required
def template_duplicate(request, pk):
    """Copier un modèle entier, étapes et points compris.

    Écrire une variante depuis zéro — « rénovation » à partir de « neuf » —
    redemanderait de retaper trente questions. La copie se fait en base et
    non à la main.
    """
    company = request.current_company
    modele = get_object_or_404(ProjectTemplate, pk=pk, company=company)

    if request.method != 'POST':
        return render(request, 'btp/etapes/template_confirm_duplicate.html', {
            'modele': modele,
            'page_title': f'Dupliquer — {modele.name}',
            'active_module': 'btp',
        })

    with transaction.atomic():
        # Un nom libre : `unique_together ['company', 'name']` refuserait
        # « Copie de X » si l'on duplique deux fois.
        base = f'Copie de {modele.name}'[:150]
        nom = base
        rang = 2
        while ProjectTemplate.objects.filter(company=company,
                                             name=nom).exists():
            suffixe = f' ({rang})'
            nom = base[:150 - len(suffixe)] + suffixe
            rang += 1

        copie = ProjectTemplate.objects.create(
            company=company, name=nom, description=modele.description,
            is_default=False, is_active=modele.is_active)

        for etape in modele.steps.all().order_by('order', 'pk'):
            nouvelle = ProjectTemplateStep.objects.create(
                template=copie, name=etape.name, step_type=etape.step_type,
                order=etape.order, offset_days=etape.offset_days,
                visible_to_client=etape.visible_to_client,
                client_can_validate=etape.client_can_validate)
            ProjectTemplateItem.objects.bulk_create([
                ProjectTemplateItem(
                    step=nouvelle, label=point.label,
                    help_text=point.help_text, answer_type=point.answer_type,
                    unit=point.unit, options=list(point.options or []),
                    is_required=point.is_required, order=point.order)
                for point in etape.items.all().order_by('order', 'pk')
            ])

    messages.success(request, f'Modèle dupliqué sous « {copie.name} ».')
    return redirect('btp:template_detail', pk=copie.pk)


# ─── Étapes d'un modèle ──────────────────────────────────────────────────────

@login_required
def template_step_create(request, pk):
    company = request.current_company
    modele = get_object_or_404(ProjectTemplate, pk=pk, company=company)
    if request.method == 'POST':
        form = ProjectTemplateStepForm(request.POST)
        if form.is_valid():
            etape = form.save(commit=False)
            etape.template = modele
            etape.save()
            messages.success(request, f'Étape « {etape.name} » ajoutée.')
            return redirect('btp:template_detail', pk=modele.pk)
    else:
        dernier = (modele.steps.order_by('-order')
                   .values_list('order', flat=True).first())
        form = ProjectTemplateStepForm(initial={'order': (dernier or 0) + 1})
    return render(request, 'btp/etapes/template_step_form.html', {
        'modele': modele,
        'form': form,
        'action': 'create',
        'page_title': 'Nouvelle étape du modèle',
        'active_module': 'btp',
    })


@login_required
def template_step_edit(request, pk):
    company = request.current_company
    etape = get_object_or_404(
        ProjectTemplateStep.objects.select_related('template'),
        pk=pk, template__company=company)
    if request.method == 'POST':
        form = ProjectTemplateStepForm(request.POST, instance=etape)
        if form.is_valid():
            form.save()
            messages.success(request, 'Étape mise à jour.')
            return redirect('btp:template_detail', pk=etape.template.pk)
    else:
        form = ProjectTemplateStepForm(instance=etape)
    return render(request, 'btp/etapes/template_step_form.html', {
        'modele': etape.template,
        'etape': etape,
        'form': form,
        'action': 'edit',
        'page_title': f'Modifier — {etape.name}',
        'active_module': 'btp',
    })


@login_required
@require_POST
def template_step_delete(request, pk):
    company = request.current_company
    etape = get_object_or_404(
        ProjectTemplateStep.objects.select_related('template'),
        pk=pk, template__company=company)
    modele_pk = etape.template.pk
    nom = etape.name
    etape.delete()
    messages.success(request, f'Étape « {nom} » supprimée du modèle.')
    return redirect('btp:template_detail', pk=modele_pk)


@login_required
@require_POST
def template_step_move(request, pk):
    """Monter ou descendre une étape, par échange de rangs.

    L'échange porte sur les rangs des deux étapes et non sur un
    décrément : plusieurs étapes peuvent partager le même rang — rien ne
    l'interdit, et un modèle importé ou dupliqué en produit — et un simple
    `order -= 1` ne les séparerait pas.
    """
    company = request.current_company
    etape = get_object_or_404(
        ProjectTemplateStep.objects.select_related('template'),
        pk=pk, template__company=company)
    sens = request.POST.get('sens')

    voisines = list(etape.template.steps.order_by('order', 'pk'))
    position = next((i for i, e in enumerate(voisines) if e.pk == etape.pk),
                    None)

    if position is not None:
        cible = position - 1 if sens == 'haut' else position + 1
        if 0 <= cible < len(voisines):
            voisine = voisines[cible]
            with transaction.atomic():
                etape.order, voisine.order = voisine.order, etape.order
                if etape.order == voisine.order:
                    # Rangs égaux : l'échange n'a rien changé, et le tri
                    # retomberait sur « pk ». On écarte d'un cran.
                    #
                    # Vers le haut on décrémente, vers le bas on INCRÉMENTE.
                    # Décrémenter la voisine dans les deux cas ne marche pas
                    # quand les deux rangs valent 0 : `max(0, -1)` vaut 0, et
                    # l'étape ne descend jamais.
                    if sens == 'haut':
                        etape.order = max(0, voisine.order - 1)
                    else:
                        etape.order = voisine.order + 1
                etape.save(update_fields=['order'])
                voisine.save(update_fields=['order'])

    return redirect('btp:template_detail', pk=etape.template.pk)


# ─── Points d'une étape de modèle ────────────────────────────────────────────

@login_required
def template_item_create(request, pk):
    company = request.current_company
    etape = get_object_or_404(
        ProjectTemplateStep.objects.select_related('template'),
        pk=pk, template__company=company)
    if request.method == 'POST':
        form = ProjectTemplateItemForm(request.POST)
        if form.is_valid():
            point = form.save(commit=False)
            point.step = etape
            point.save()
            messages.success(request, 'Point ajouté.')
            return redirect('btp:template_detail', pk=etape.template.pk)
    else:
        dernier = (etape.items.order_by('-order')
                   .values_list('order', flat=True).first())
        form = ProjectTemplateItemForm(initial={'order': (dernier or 0) + 1})
    return render(request, 'btp/etapes/template_item_form.html', {
        'modele': etape.template,
        'etape': etape,
        'form': form,
        'action': 'create',
        'page_title': 'Nouveau point à remplir',
        'active_module': 'btp',
    })


@login_required
def template_item_edit(request, pk):
    company = request.current_company
    point = get_object_or_404(
        ProjectTemplateItem.objects.select_related('step__template'),
        pk=pk, step__template__company=company)
    if request.method == 'POST':
        form = ProjectTemplateItemForm(request.POST, instance=point)
        if form.is_valid():
            form.save()
            messages.success(request, 'Point mis à jour.')
            return redirect('btp:template_detail', pk=point.step.template.pk)
    else:
        form = ProjectTemplateItemForm(instance=point)
    return render(request, 'btp/etapes/template_item_form.html', {
        'modele': point.step.template,
        'etape': point.step,
        'point': point,
        'form': form,
        'action': 'edit',
        'page_title': f'Modifier — {point.label}',
        'active_module': 'btp',
    })


@login_required
@require_POST
def template_item_delete(request, pk):
    company = request.current_company
    point = get_object_or_404(
        ProjectTemplateItem.objects.select_related('step__template'),
        pk=pk, step__template__company=company)
    modele_pk = point.step.template.pk
    point.delete()
    messages.success(request, 'Point supprimé du modèle.')
    return redirect('btp:template_detail', pk=modele_pk)


# --- Recherche dans les points de controle -----------------------------------

@login_required
def points_search(request):
    """Retrouver les chantiers d'apres une reponse.

    C'est le gain concret des colonnes TYPEES, et la raison pour laquelle
    les reponses ne sont pas dans un JSON : « quels chantiers demandent une
    nacelle ? » est un filtre SQL ici, et serait une lecture de toutes les
    lignes la-bas.
    """
    company = request.current_company
    question = (request.GET.get('q') or '').strip()
    reponse = request.GET.get('reponse') or ''

    points = ProjectStepItem.objects.none()
    if question:
        points = (ProjectStepItem.objects
                  .filter(step__project__company=company,
                          label__icontains=question)
                  .select_related('step', 'step__project',
                                  'step__project__customer',
                                  'answer_quote', 'answer_quote__customer',
                                  'answer_supplier'))
        if reponse == 'oui':
            points = points.filter(answer_boolean=True)
        elif reponse == 'non':
            points = points.filter(answer_boolean=False)
        elif reponse == 'vide':
            # Non renseigne : pour un oui/non, c'est NULL. Les autres types
            # n'ont pas de « vide » commun -- un texte vide est '' et un
            # nombre vide est NULL -- donc ce filtre ne porte que sur les
            # oui/non, et l'etiquette le dit.
            points = points.filter(answer_type='yes_no',
                                   answer_boolean__isnull=True)
        points = points.order_by('step__project__name', 'order')[:200]

    return render(request, 'btp/etapes/points_search.html', {
        'points': points,
        'q': question,
        'reponse': reponse,
        'page_title': 'Rechercher dans les points de chantier',
        'active_module': 'btp',
        'active_subnav': 'templates',
    })


@login_required
@require_POST
def template_install_starter(request):
    """Installe un modele pret a l'emploi, d'un bouton.

    PAS de commande de gestion : la contrainte du projet est que
    l'administration se pilote entierement depuis l'interface. Un modele
    utile fait une quarantaine de questions, et exiger de les retaper avant
    de pouvoir se servir de la fonctionnalite reviendrait a ne pas la
    livrer.
    """
    from .modeles_prets import CATALOGUE_DES_MODELES, installer_un_modele_pret

    company = request.current_company
    cle = request.POST.get('cle') or ''

    if cle not in CATALOGUE_DES_MODELES:
        # La cle vient du formulaire : on la verifie contre le catalogue au
        # lieu de la passer telle quelle.
        messages.error(request, 'Modele inconnu.')
        return redirect('btp:template_list')

    modele = installer_un_modele_pret(company, cle)
    messages.success(
        request,
        f'Modele « {modele.name} » installe : '
        f'{modele.steps.count()} etapes et {modele.nombre_de_points} points. '
        'Adaptez-le a vos habitudes, il vous appartient maintenant.')
    return redirect('btp:template_detail', pk=modele.pk)


@login_required
def project_fill_all(request, pk):
    """Tous les points du chantier, etape par etape, dans UN formulaire.

    Le createur du chantier remplit les details AVANT le demarrage : c'est
    la facon de travailler voulue, et le modele Etancheite compte 143
    points sur douze etapes. Lui faire ouvrir douze pages pour cela
    travaille contre lui -- on abandonne a la cinquieme, et les questions
    qui restent sont precisement celles qu'on voulait ne pas oublier.

    Cette page ne touche PAS aux proprietes des etapes (dates, statut,
    responsable) : elles se modifient une par une, ou elles encombreraient
    un ecran deja long. Ici, seules les reponses.

    Un seul formulaire pour tout le chantier est possible parce que les
    champs sont nommes « point_<pk> » : la cle primaire est unique sur
    l'ensemble de la base, donc deux etapes ne peuvent pas se marcher
    dessus. Un prefixe par etape serait inutile.
    """
    company = request.current_company
    project = get_object_or_404(BTPProject, pk=pk, company=company)

    etapes = list(ProjectPlanStep.objects
                  .filter(project=project)
                  .prefetch_related(Prefetch(
                      'items',
                      queryset=ProjectStepItem.objects.select_related(
                          'answer_quote', 'answer_quote__customer',
                          'answer_supplier').order_by('order', 'pk')))
                  .order_by('order', 'pk'))

    blocs = []
    for etape in etapes:
        points = sorted(etape.items.all(), key=lambda p: (p.order, p.pk))
        if not points:
            # Une etape sans point n'a rien a montrer ici : l'afficher
            # vide donnerait l'impression d'un bug.
            continue
        blocs.append({'etape': etape, 'points': points})

    if request.method == 'POST':
        for bloc in blocs:
            bloc['form'] = PointsDeLEtapeForm(
                request.POST, request.FILES, points=bloc['points'],
                company=company, project=project)

        # TOUS validés avant d'en enregistrer un seul : une erreur de saisie
        # a l'etape 9 ne doit pas laisser les etapes 1 a 8 ecrites et le
        # reste perdu, l'utilisateur ne sachant plus ce qui est passe.
        if all(bloc['form'].is_valid() for bloc in blocs):
            with transaction.atomic():
                for bloc in blocs:
                    for point in bloc['points']:
                        svc.enregistrer_la_reponse(
                            point, bloc['form'].cleaned_data,
                            user=request.user)

            restants = svc.compter_les_points_manquants(project)
            messages.success(request, 'Points enregistrés.')
            if restants:
                messages.warning(
                    request,
                    f'{restants} point(s) important(s) restent à renseigner. '
                    'Le chantier peut démarrer, mais ils sont à combler.')
            else:
                messages.success(
                    request,
                    'Tous les points importants sont renseignés : le '
                    'chantier peut démarrer sans angle mort.')
            return redirect('btp:project_planning', pk=project.pk)
    else:
        for bloc in blocs:
            bloc['form'] = PointsDeLEtapeForm(
                points=bloc['points'], company=company, project=project)

    total = sum(len(bloc['points']) for bloc in blocs)
    remplis = sum(1 for bloc in blocs for point in bloc['points']
                  if point.is_answered)

    return render(request, 'btp/etapes/project_fill_all.html', {
        'project': project,
        'blocs': blocs,
        'total': total,
        'remplis': remplis,
        'manquants': svc.compter_les_points_manquants(project),
        'page_title': f'Tout remplir — {project.name}',
        'active_module': 'btp',
        'active_subnav': 'projects',
    })
