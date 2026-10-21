"""
apps/hr/views_planning.py — Les écrans du planning

Quatre écrans, et une seule source de vérité derrière eux
(`planning_service`) :

- `planning_equipe` — la grille du mois, tous les salariés en lignes
- `planning_employe` — le mois d'un salarié, jour par jour
- `mon_planning` — le même, pour le salarié connecté, sans droit particulier
- les CRUD du rythme hebdomadaire et des arrêts de travail

Le planning ne stocke rien : congés, maladie et heures pointées sont lus là
où ils vivent déjà. C'est pourquoi on ne trouvera ici aucune vue de création
de congé — elle existe depuis toujours sous `hr:leave_create`.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms_planning import WorkScheduleForm, WorkStoppageForm
from .models import Employee, WorkSchedule, WorkStoppage
from .planning_service import (
    annee_mois_demandes,
    mois_precedent,
    mois_suivant,
    planning_employe_vide,
    planning_du_mois,
    planning_equipe,
)

MOIS_FR = (
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet',
    'août', 'septembre', 'octobre', 'novembre', 'décembre',
)


def _navigation(annee, mois):
    """Mois précédent et suivant, pour les flèches de l'en-tête."""
    precedent = mois_precedent(annee, mois)
    suivant = mois_suivant(annee, mois)
    return {
        'annee': annee, 'mois': mois,
        'libelle_mois': f'{MOIS_FR[mois - 1]} {annee}',
        'precedent': {'annee': precedent[0], 'mois': precedent[1]},
        'suivant': {'annee': suivant[0], 'mois': suivant[1]},
    }


def _est_encadrant(request):
    """Qui voit le planning de TOUTE l'équipe.

    Un salarié voit le sien sans droit particulier (mon_planning) ; voir
    celui des autres expose des arrêts de travail et des motifs de congé,
    c'est-à-dire des données de santé.
    """
    if request.user.is_superuser:
        return True
    profil = getattr(request.user, 'profile', None)
    role = getattr(profil, 'role', '') or ''
    return role in ('admin', 'superadmin', 'manager', 'hr_manager')


# ─── Grille d'équipe ──────────────────────────────────────────────────────────

@login_required
def planning_equipe_view(request):
    company = request.current_company
    if not _est_encadrant(request):
        messages.error(request, (
            'Le planning de l\'équipe est réservé à l\'encadrement : il '
            'montre les arrêts de travail et les motifs d\'absence. Votre '
            'planning personnel est accessible depuis « Mon planning ».'))
        return redirect('hr:mon_planning')

    annee, mois = annee_mois_demandes(request)
    planning = planning_equipe(company, annee, mois)

    return render(request, 'hr/planning/equipe.html', {
        'planning': planning,
        'nav': _navigation(annee, mois),
        'page_title': f'Planning — {MOIS_FR[mois - 1]} {annee}',
        'active_module': 'hr',
    })


# ─── Un salarié ───────────────────────────────────────────────────────────────

@login_required
def planning_employe_view(request, pk):
    company = request.current_company
    employee = get_object_or_404(Employee, pk=pk, company=company)

    # Son propre planning est toujours accessible ; celui d'un autre
    # demande d'encadrer.
    propre = employee.user_id == request.user.pk
    if not propre and not _est_encadrant(request):
        messages.error(request, 'Accès refusé.')
        return redirect('hr:mon_planning')

    annee, mois = annee_mois_demandes(request)
    planning = planning_du_mois(employee, annee, mois)

    return render(request, 'hr/planning/employe.html', {
        'planning': planning,
        'employee': employee,
        'nav': _navigation(annee, mois),
        'peut_encadrer': _est_encadrant(request),
        'page_title': f'{employee.full_name} — {MOIS_FR[mois - 1]} {annee}',
        'active_module': 'hr',
    })


@login_required
def mon_planning(request):
    """Le planning du salarié connecté, sans droit particulier.

    Un compte sans fiche salarié n'a pas de planning — et ce n'est pas une
    erreur : prestataire, expert-comptable externe, compte de service. On
    l'explique plutôt que de renvoyer une page vide ou un 404.
    """
    employee = Employee.objects.filter(user=request.user).first()
    annee, mois = annee_mois_demandes(request)

    if employee is None:
        return render(request, 'hr/planning/employe.html', {
            'planning': planning_employe_vide(annee, mois),
            'employee': None,
            'nav': _navigation(annee, mois),
            'peut_encadrer': _est_encadrant(request),
            'sans_fiche': True,
            'page_title': 'Mon planning',
            'active_module': 'hr',
        })

    return render(request, 'hr/planning/employe.html', {
        'planning': planning_du_mois(employee, annee, mois),
        'employee': employee,
        'nav': _navigation(annee, mois),
        'peut_encadrer': _est_encadrant(request),
        'page_title': f'Mon planning — {MOIS_FR[mois - 1]} {annee}',
        'active_module': 'hr',
    })


# ─── Rythmes hebdomadaires ────────────────────────────────────────────────────

@login_required
def schedule_list(request):
    company = request.current_company
    if not _est_encadrant(request):
        messages.error(request, 'Accès refusé.')
        return redirect('hr:mon_planning')

    rythmes = WorkSchedule.objects.filter(
        company=company).select_related('employee').order_by(
            'employee__last_name', 'employee__first_name')

    # Les salariés encore sans rythme : le planning leur applique un
    # lundi-vendredi par défaut, ce qui est raisonnable mais muet. Les
    # nommer évite de croire que tout le monde est renseigné.
    sans_rythme = Employee.objects.filter(
        company=company, is_active=True, work_schedule__isnull=True
    ).order_by('last_name', 'first_name')

    return render(request, 'hr/planning/rythme_list.html', {
        'rythmes': rythmes,
        'sans_rythme': sans_rythme,
        'page_title': 'Rythmes de travail',
        'active_module': 'hr',
    })


@login_required
def schedule_create(request):
    company = request.current_company
    if not _est_encadrant(request):
        messages.error(request, 'Accès refusé.')
        return redirect('hr:mon_planning')

    if request.method == 'POST':
        form = WorkScheduleForm(request.POST, company=company)
        if form.is_valid():
            rythme = form.save(commit=False)
            # L'entreprise vient du salarié, pas de la session : les deux
            # doivent coïncider, et le salarié est déjà borné par le
            # formulaire. La déduire évite un champ de plus à tenir juste.
            rythme.company = rythme.employee.company
            rythme.save()
            messages.success(request, (
                f'Rythme enregistré pour {rythme.employee.full_name} — '
                f'{rythme.heures_hebdomadaires} h par semaine.'))
            return redirect('hr:schedule_list')
    else:
        form = WorkScheduleForm(company=company)

    return render(request, 'hr/planning/rythme_form.html', {
        'form': form, 'action': 'create',
        'page_title': 'Nouveau rythme de travail',
        'active_module': 'hr',
    })


@login_required
def schedule_edit(request, pk):
    company = request.current_company
    if not _est_encadrant(request):
        messages.error(request, 'Accès refusé.')
        return redirect('hr:mon_planning')

    rythme = get_object_or_404(WorkSchedule, pk=pk, company=company)
    if request.method == 'POST':
        form = WorkScheduleForm(request.POST, instance=rythme,
                                company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Rythme mis à jour.')
            return redirect('hr:schedule_list')
    else:
        form = WorkScheduleForm(instance=rythme, company=company)

    return render(request, 'hr/planning/rythme_form.html', {
        'form': form, 'action': 'edit', 'rythme': rythme,
        'page_title': f'Rythme — {rythme.employee.full_name}',
        'active_module': 'hr',
    })


@login_required
@require_POST
def schedule_delete(request, pk):
    company = request.current_company
    if not _est_encadrant(request):
        messages.error(request, 'Accès refusé.')
        return redirect('hr:mon_planning')

    rythme = get_object_or_404(WorkSchedule, pk=pk, company=company)
    nom = rythme.employee.full_name
    rythme.delete()
    messages.success(request, (
        f'Rythme de {nom} supprimé. Le planning lui applique désormais un '
        f'lundi-vendredi de sept heures par défaut.'))
    return redirect('hr:schedule_list')


# ─── Arrêts de travail ────────────────────────────────────────────────────────

@login_required
def stoppage_list(request):
    company = request.current_company
    if not _est_encadrant(request):
        messages.error(request, 'Accès refusé.')
        return redirect('hr:mon_planning')

    arrets = WorkStoppage.objects.filter(company=company).select_related(
        'employee', 'prolongation_de', 'declared_by')

    # Un arrêt sans date de fin est celui dont il faut s'occuper : on ne
    # sait pas quand le salarié revient, et le planning le compte absent
    # indéfiniment.
    en_cours = [arret for arret in arrets if arret.est_en_cours()]

    return render(request, 'hr/planning/arret_list.html', {
        'arrets': arrets,
        'en_cours': en_cours,
        'page_title': 'Arrêts de travail',
        'active_module': 'hr',
    })


@login_required
def stoppage_create(request):
    company = request.current_company
    if not _est_encadrant(request):
        messages.error(request, 'Accès refusé.')
        return redirect('hr:mon_planning')

    if request.method == 'POST':
        form = WorkStoppageForm(request.POST, company=company)
        if form.is_valid():
            arret = form.save(commit=False)
            arret.company = arret.employee.company
            arret.declared_by = request.user
            arret.save()
            messages.success(request, 'Arrêt de travail enregistré.')
            return redirect('hr:stoppage_list')
    else:
        form = WorkStoppageForm(company=company)

    return render(request, 'hr/planning/arret_form.html', {
        'form': form, 'action': 'create',
        'page_title': 'Déclarer un arrêt de travail',
        'active_module': 'hr',
    })


@login_required
def stoppage_edit(request, pk):
    company = request.current_company
    if not _est_encadrant(request):
        messages.error(request, 'Accès refusé.')
        return redirect('hr:mon_planning')

    arret = get_object_or_404(WorkStoppage, pk=pk, company=company)
    if request.method == 'POST':
        form = WorkStoppageForm(request.POST, instance=arret, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Arrêt mis à jour.')
            return redirect('hr:stoppage_list')
    else:
        form = WorkStoppageForm(instance=arret, company=company)

    return render(request, 'hr/planning/arret_form.html', {
        'form': form, 'action': 'edit', 'arret': arret,
        'page_title': f'Arrêt — {arret.employee.full_name}',
        'active_module': 'hr',
    })


@login_required
@require_POST
def stoppage_delete(request, pk):
    company = request.current_company
    if not _est_encadrant(request):
        messages.error(request, 'Accès refusé.')
        return redirect('hr:mon_planning')

    arret = get_object_or_404(WorkStoppage, pk=pk, company=company)
    arret.delete()
    messages.success(request, 'Arrêt supprimé.')
    return redirect('hr:stoppage_list')
