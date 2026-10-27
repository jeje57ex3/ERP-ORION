"""
apps/system_health/views.py — Section Santé du système (Super Admin, section 16).
"""
import json
import csv
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Count, Q, Avg
from django.http import JsonResponse, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET

from apps.private_saas.decorators import super_admin_required

from .forms import (
    AlertThresholdForm, ErrorCommentForm, HealthPermissionForm,
    IncidentStatusForm, IncidentTimelineForm, PostIncidentReportForm,
    RiskRegisterForm, SystemErrorForm, SystemErrorTriageForm, SystemIncidentForm,
)
from .models import (
    AlertThreshold, ErrorComment, HealthAuditLog, HealthPermission,
    IncidentTimeline, PostIncidentReport, RiskRegister, SensorReading,
    SystemError, SystemIncident,
)
from .permissions import _audit, has_health_perm
from .services import (
    compute_global_health, get_disk_allocations, get_disk_summary,
    get_latest_sensor_readings, get_snapshot_history, get_storage_breakdown,
)


# ─── Accès combiné : superuser OU permission granulaire ───────────────────────

def _require_perm(perm):
    """Décorateur combinant super_admin_required ET permission granulaire."""
    def decorator(view_func):
        from functools import wraps
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                from django.conf import settings
                return redirect(f'{settings.LOGIN_URL}?next={request.path}')
            if not has_health_perm(request.user, perm):
                return HttpResponseForbidden(
                    "Accès refusé : permission insuffisante pour la section Santé du système."
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# ──────────────────────────────────────────────────────────────────────────────
# 16.1 — Tableau de bord global
# ──────────────────────────────────────────────────────────────────────────────

@_require_perm('can_view_health')
def dashboard(request):
    health = compute_global_health()
    _audit(request, 'view_dashboard')

    recent_errors    = SystemError.objects.filter(status__in=['new', 'confirmed']).order_by('-last_seen')[:5]
    open_incidents   = SystemIncident.objects.filter(status__in=['open', 'investigating', 'identified'])
    critical_risks   = RiskRegister.objects.filter(status__in=['identified', 'assessed', 'treating'])
    readings         = health['readings']

    # Statistiques 24h
    since_24h = timezone.now() - timedelta(hours=24)
    errors_24h = SystemError.objects.filter(created_at__gte=since_24h).count()

    return render(request, 'system_health/dashboard.html', {
        'health':          health,
        'readings':        readings,
        'recent_errors':   recent_errors,
        'open_incidents':  open_incidents,
        'critical_risks':  critical_risks,
        'errors_24h':      errors_24h,
        'disks':           get_disk_summary(),
        'can_view_errors':    has_health_perm(request.user, 'can_view_errors'),
        'can_view_technical': has_health_perm(request.user, 'can_view_technical'),
        'can_view_risks':     has_health_perm(request.user, 'can_view_risks'),
        'can_manage_incidents': has_health_perm(request.user, 'can_manage_incidents'),
    })


# ──────────────────────────────────────────────────────────────────────────────
# 16.2 — Rapports d'erreurs
# ──────────────────────────────────────────────────────────────────────────────

@_require_perm('can_view_errors')
def error_list(request):
    _audit(request, 'view_errors')
    qs = SystemError.objects.all()

    severity = request.GET.get('severity')
    status   = request.GET.get('status')
    module   = request.GET.get('module')
    q        = request.GET.get('q', '').strip()

    if severity:  qs = qs.filter(severity=severity)
    if status:    qs = qs.filter(status=status)
    if module:    qs = qs.filter(module=module)
    if q:
        qs = qs.filter(Q(error_type__icontains=q) | Q(user_message__icontains=q)
                       | Q(module__icontains=q) | Q(fingerprint__icontains=q))

    paginator = Paginator(qs.order_by('-last_seen'), 30)
    page = paginator.get_page(request.GET.get('page'))

    modules = SystemError.objects.values_list('module', flat=True).distinct().order_by('module')

    # Export CSV
    if request.GET.get('export') == 'csv' and has_health_perm(request.user, 'can_export_reports'):
        return _export_errors_csv(qs, request)

    return render(request, 'system_health/error_list.html', {
        'page': page,
        'modules': modules,
        'filters': {'severity': severity, 'status': status, 'module': module, 'q': q},
        'can_export': has_health_perm(request.user, 'can_export_reports'),
    })


@_require_perm('can_view_errors')
def error_detail(request, pk):
    error = get_object_or_404(SystemError, pk=pk)
    can_sensitive = has_health_perm(request.user, 'can_view_sensitive')
    if can_sensitive:
        _audit(request, 'sensitive_view', 'SystemError', pk)
    _audit(request, 'view_errors', 'SystemError', pk)

    triage_form  = SystemErrorTriageForm(request.POST or None, instance=error)
    comment_form = ErrorCommentForm(request.POST if request.POST.get('comment') else None)

    if request.method == 'POST':
        if 'triage' in request.POST and triage_form.is_valid():
            err = triage_form.save(commit=False)
            if err.status == 'resolved' and not err.resolved_at:
                err.resolved_at = timezone.now()
            err.save()
            _audit(request, 'status_change', 'SystemError', pk,
                   f"Statut → {err.get_status_display()}")
            messages.success(request, 'Erreur mise à jour.')
            return redirect('system_health:error_detail', pk=pk)

        if 'comment' in request.POST and comment_form.is_valid():
            c = comment_form.save(commit=False)
            c.error = error
            c.author = request.user
            c.save()
            return redirect('system_health:error_detail', pk=pk)

    similar = SystemError.objects.filter(
        fingerprint=error.fingerprint, status__in=['new', 'confirmed', 'in_progress']
    ).exclude(pk=pk)[:5]

    return render(request, 'system_health/error_detail.html', {
        'error':         error,
        'triage_form':   triage_form,
        'comment_form':  comment_form,
        'can_sensitive': can_sensitive,
        'similar':       similar,
    })


def _export_errors_csv(qs, request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="erreurs_systeme.csv"'
    response.write('﻿')  # BOM UTF-8
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['UID', 'Gravité', 'Module', 'Type', 'Statut', 'Occurrences',
                     'Première vue', 'Dernière vue', 'Message utilisateur'])
    can_sensitive = has_health_perm(request.user, 'can_view_sensitive')
    for e in qs:
        writer.writerow([
            str(e.uid), e.get_severity_display(), e.module, e.error_type,
            e.get_status_display(), e.occurrence_count,
            e.first_seen.strftime('%Y-%m-%d %H:%M'),
            e.last_seen.strftime('%Y-%m-%d %H:%M'),
            e.user_message if can_sensitive else '[masqué]',
        ])
    _audit(request, 'export', 'SystemError', '', 'Export CSV erreurs')
    return response


# ──────────────────────────────────────────────────────────────────────────────
# 16.3 — Capteurs en temps réel (AJAX polling)
# ──────────────────────────────────────────────────────────────────────────────

@_require_perm('can_view_technical')
def sensor_dashboard(request):
    return render(request, 'system_health/sensor_dashboard.html', {
        'sensor_types': SensorReading._meta.get_field('sensor_type').choices,
    })


@require_GET
@_require_perm('can_view_technical')
def sensor_api(request):
    """Endpoint AJAX pour les lectures courantes de tous les capteurs."""
    health = compute_global_health()
    readings_data = {}
    for sensor_type, reading in health['readings'].items():
        readings_data[sensor_type] = {
            'value':  reading.value,
            'status': reading.status,
            'status_label': reading.get_status_display(),
            'collected_at': reading.collected_at.isoformat(),
        }
    return JsonResponse({
        'global_status': health['status'],
        'global_score':  health['score'],
        'breakdown':     health['breakdown'],
        'readings':      readings_data,
        'critical':      health['critical'],
        'warnings':      health['warnings'],
        'timestamp':     health['timestamp'].isoformat(),
    })


@require_GET
@_require_perm('can_view_technical')
def sensor_history_api(request, sensor_type):
    """Historique d'un capteur sur les dernières 24h (pour sparkline)."""
    hours = int(request.GET.get('hours', 24))
    hours = min(hours, 168)  # max 7 jours
    since = timezone.now() - timedelta(hours=hours)
    readings = (SensorReading.objects
                .filter(sensor_type=sensor_type, collected_at__gte=since)
                .order_by('collected_at')
                .values('value', 'status', 'collected_at'))
    data = [
        {'value': r['value'], 'status': r['status'],
         'ts': r['collected_at'].isoformat()}
        for r in readings
    ]
    return JsonResponse({'sensor_type': sensor_type, 'data': data})


# ──────────────────────────────────────────────────────────────────────────────
# 16.14 — Disques & stockage
# ──────────────────────────────────────────────────────────────────────────────

@_require_perm('can_view_technical')
def disk_dashboard(request):
    _audit(request, 'view_dashboard', description='Consultation disques & stockage')
    # allocations : agencement physique (partitions, espace non alloué), vide
    # hors Linux. breakdown : où vont réellement les données, mis en cache
    # côté service car il parcourt des dizaines de milliers de fichiers.
    from .storage_service import commandes_de_migration, emplacements, volumes

    # Le placement par catégorie : quel réglage, quel chemin réel, quel
    # volume. Sans tailles, parce que `breakdown` les donne déjà et les met
    # en cache cinq minutes — les recalculer ici doublerait le parcours de
    # dizaines de milliers de fichiers à chaque affichage.
    placements = emplacements(mesurer_tailles=False)

    # Plan de migration, seulement si l'administrateur a choisi une cible.
    # Rédigé, jamais exécuté : voir l'en-tête de storage_service.
    plan = None
    categorie = request.GET.get('categorie', '')
    cible = request.GET.get('volume', '')
    if categorie and cible:
        connus = {v['point_de_montage'] for v in volumes()}
        if cible not in connus:
            # Un volume inventé dans l'URL ne doit pas produire des
            # commandes qui créeraient un dossier sur le disque système.
            messages.error(
                request,
                f'Volume inconnu : {cible}. Choisissez-en un dans la liste.')
        else:
            try:
                plan = commandes_de_migration(categorie, cible)
            except ValueError as exc:
                messages.error(request, str(exc))

    return render(request, 'system_health/disk_dashboard.html', {
        'disks': get_disk_summary(),
        'allocations': get_disk_allocations(),
        'breakdown': get_storage_breakdown(),
        'placements': placements,
        'volumes': volumes(),
        'plan': plan,
        'categorie_choisie': categorie,
        'volume_choisi': cible,
        **_contexte_de_stockage(),
    })


# ── Allocation, déplacement, ajout de disques : exécuté, plus seulement guidé ──
#
# `storage_service.commandes_de_migration` rédige les commandes ; les vues
# ci-dessous les exécutent. Trois principes, parce que ces actions touchent
# des données :
#
# 1. AUCUN CHEMIN N'EST REÇU. L'interface propose les volumes détectés, et
#    le dossier cible est calculé par `chemin_propose`. Il n'y a donc rien
#    à valider contre une traversée de répertoire, puisque rien ne vient du
#    navigateur sinon le choix d'un volume, comparé à la liste réelle.
# 2. RIEN N'EST SUPPRIMÉ EN SUITE D'AUTRE CHOSE. Une copie s'arrête à
#    « vérifiée » ; libérer l'ancien emplacement est une action séparée.
# 3. TOUT PASSE PAR UNE OPÉRATION EN BASE, exécutée par Celery. Une copie
#    de plusieurs gigaoctets ne tient pas dans une requête HTTP, et son
#    avancement doit survivre à la fermeture de l'onglet.

def _contexte_de_stockage():
    """Ce que l'écran des disques doit savoir pour proposer des actions."""
    from .models import OperationDeStockage
    from . import stockage_actions, stockage_privilegie

    disques_physiques, erreur_assistant = [], ''
    if stockage_privilegie.est_disponible():
        try:
            disques_physiques = stockage_privilegie.lister_les_disques().get(
                'disques', [])
        except (stockage_privilegie.StockagePrivilegieIndisponible,
                stockage_privilegie.ActionPrivilegieeRefusee) as exc:
            erreur_assistant = str(exc)
    else:
        erreur_assistant = (
            'L\'assistant de préparation des disques n\'est pas installé sur '
            'ce serveur. La détection et le déplacement fonctionnent ; seuls '
            'le partitionnement et le montage d\'un disque neuf en ont '
            'besoin.')

    # L'etat de chaque categorie est lu sur le DISQUE : est-ce deja un lien,
    # et vers ou pointe-t-il. Aucune table ne double cette information.
    etats = []
    for cle, _reglage in stockage_actions.REGLAGE_PAR_CATEGORIE.items():
        try:
            etats.append({
                'cle': cle,
                'canonique': stockage_actions.canonique(cle),
                'reel': stockage_actions.cible_actuelle(cle),
                'est_un_lien': stockage_actions.est_deja_un_lien(cle),
            })
        except stockage_actions.ErreurDeStockage as exc:
            etats.append({'cle': cle, 'erreur': str(exc)})

    return {
        'disques_physiques': disques_physiques,
        'erreur_assistant': erreur_assistant,
        'assistant_disponible': stockage_privilegie.est_disponible(),
        'etats_de_stockage': etats,
        'operations': OperationDeStockage.objects.all()[:15],
        'operation_en_cours': OperationDeStockage.objects.filter(
            etat__in=('en_attente', 'en_cours')).first(),
        'categories_deplacables': dict(
            OperationDeStockage.CATEGORIE_CHOICES),
    }


DELAI_DE_MISE_EN_FILE = 3
"""Secondes accordées pour joindre le courtier depuis une requête HTTP.

Au-delà, on rend la main avec un message plutôt que de faire patienter.
Joindre un Redis local prend quelques millisecondes ; trois secondes
laissent déjà beaucoup de marge.
"""


def _mettre_en_file(tache, operation):
    """Met la tâche en file sans jamais suspendre la requête.

    **Mesuré, et non estimé.** Un `.delay()` lancé alors que Redis est
    arrêté met **64 secondes** à rendre la main. L'utilisateur ne voit
    qu'une page qui ne revient pas, puis le délai de gunicorn, et rien
    n'explique quoi que ce soit.

    Et `retry=False` n'y change rien : le délai ne vient pas de la
    connexion mais des RÉESSAIS d'acquisition de connexion, gouvernés par
    `broker_connection_max_retries` (défaut 100), que ce drapeau ne touche
    pas. Les délais de socket dans les settings n'y changent rien non plus
    — ils bornent une connexion établie, pas une série de tentatives.

    La connexion est donc acquise ici avec `max_retries=0` : une tentative,
    et un échec dicible en deux secondes au lieu de soixante-quatre.

    L'opération est alors marquée en échec sur-le-champ. Une ligne « en
    attente » que rien ne fera avancer serait pire qu'un échec : elle
    bloquerait en plus le verrou « une seule opération à la fois ».

    Défaut trouvé en neutralisant un garde-fou pour vérifier qu'un test
    mordait — la suite de tests s'est bloquée, parce qu'aucun test
    n'atteignait jusque-là cet appel.
    """
    from django.utils import timezone

    from erp_btp.celery import app

    try:
        with app.connection_for_write() as connexion:
            connexion.ensure_connection(max_retries=0,
                                        timeout=DELAI_DE_MISE_EN_FILE)
            tache.apply_async(args=[operation.pk], retry=False,
                              connection=connexion)
        return True
    except Exception as exc:                        # noqa: BLE001
        operation.etat = 'echouee'
        operation.message = (
            'Le service de tâches de fond est injoignable, rien n\'a été '
            'lancé.')[:300]
        operation.fini_le = timezone.now()
        operation.ajouter_au_journal(
            f'Mise en file impossible : {exc}. Vérifiez que Redis et '
            f'orion-celery sont démarrés.')
        operation.save(update_fields=['etat', 'message', 'fini_le',
                                      'journal'])
        return False


def _refuser_si_une_operation_tourne():
    """Une seule opération de stockage à la fois.

    Deux copies simultanées vers le même volume rempliraient le disque sans
    que ni l'une ni l'autre n'aboutisse, et deux bascules concurrentes sur
    la même catégorie laisseraient le lien dans un état que personne ne
    peut prévoir. Le verrou est volontairement grossier : il n'y a aucune
    raison de mener deux de ces opérations en parallèle.
    """
    from .models import OperationDeStockage

    return OperationDeStockage.objects.filter(
        etat__in=('en_attente', 'en_cours')).first()


@require_POST
@_require_perm('can_administrate')
def stockage_preparer_disque(request):
    """Partitionne, formate et monte un disque neuf."""
    from .models import OperationDeStockage
    from . import stockage_privilegie, tasks

    occupe = _refuser_si_une_operation_tourne()
    if occupe:
        messages.error(request, f'Une opération est déjà en cours : {occupe}.')
        return redirect('system_health:disk_dashboard')

    peripherique = request.POST.get('peripherique', '')
    etiquette = request.POST.get('etiquette', '')
    numero_de_serie = request.POST.get('numero_de_serie', '')

    if request.POST.get('confirmation') != peripherique:
        messages.error(
            request,
            'Confirmation incorrecte. Pour formater un disque, recopiez son '
            'nom exact : cette étape existe parce que l\'opération efface '
            'tout son contenu sans retour possible.')
        return redirect('system_health:disk_dashboard')

    # Le peripherique et l'etiquette ne sont PAS valides ici : le script
    # root le fait, et c'est le seul controle qui compte -- ce code tourne
    # sous le compte meme qu'on cherche a contenir.
    if not stockage_privilegie.est_disponible():
        messages.error(
            request,
            'L\'assistant de préparation des disques n\'est pas installé. '
            'Voir deployment/proxmox-appliance/scripts/orion-stockage.')
        return redirect('system_health:disk_dashboard')

    operation = OperationDeStockage.objects.create(
        type_operation='preparer_disque',
        peripherique=peripherique,
        volume_cible=etiquette,
        # Le numero de serie affiche voyage dans « message » jusqu'a la
        # tache, qui le renvoie au script root : si le materiel present
        # sous ce nom a change, le script s'arrete.
        message=numero_de_serie,
        demandee_par=request.user)

    if not _mettre_en_file(tasks.preparer_un_disque, operation):
        messages.error(
            request,
            'Le service de tâches de fond est injoignable : rien n\'a été '
            'lancé, et aucun disque n\'a été touché. Vérifiez Redis et '
            'orion-celery.')
        return redirect('system_health:disk_dashboard')

    _audit(request, 'status_change',
           description=f'Préparation du disque {peripherique} demandée')
    messages.success(
        request,
        f'Préparation de {peripherique} lancée. Le formatage peut prendre '
        f'plusieurs minutes ; l\'avancement s\'affiche ci-dessous.')
    return redirect('system_health:disk_dashboard')


@require_POST
@_require_perm('can_administrate')
def stockage_deplacer(request):
    """Bascule une catégorie vers un volume, avec ou sans copie."""
    from .models import OperationDeStockage
    from . import stockage_actions, tasks

    occupe = _refuser_si_une_operation_tourne()
    if occupe:
        messages.error(request, f'Une opération est déjà en cours : {occupe}.')
        return redirect('system_health:disk_dashboard')

    categorie = request.POST.get('categorie', '')
    point_de_montage = request.POST.get('volume', '')
    mode = request.POST.get('mode', '')

    if mode not in ('basculer', 'copier_basculer'):
        messages.error(request, 'Mode de déplacement inconnu.')
        return redirect('system_health:disk_dashboard')

    if categorie not in stockage_actions.REGLAGE_PAR_CATEGORIE:
        messages.error(request, f'Catégorie non déplaçable : {categorie}.')
        return redirect('system_health:disk_dashboard')

    # Le volume doit figurer dans la liste REELLE des volumes montes.
    # C'est ce qui empeche une requete forgee de faire ecrire ailleurs.
    if stockage_actions.volume_autorise(point_de_montage) is None:
        messages.error(
            request,
            f'Volume inconnu : {point_de_montage}. Choisissez-en un dans la '
            f'liste proposée.')
        return redirect('system_health:disk_dashboard')

    cible = stockage_actions.chemin_propose(point_de_montage, categorie)
    if cible == stockage_actions.cible_actuelle(categorie):
        messages.info(
            request,
            f'« {categorie} » se trouve déjà là. Rien à faire.')
        return redirect('system_health:disk_dashboard')

    operation = OperationDeStockage.objects.create(
        type_operation=mode,
        categorie=categorie,
        volume_cible=point_de_montage,
        chemin_source=stockage_actions.cible_actuelle(categorie),
        chemin_cible=cible,
        demandee_par=request.user)

    tache = (tasks.basculer_une_categorie if mode == 'basculer'
             else tasks.copier_puis_basculer)
    if not _mettre_en_file(tache, operation):
        messages.error(
            request,
            'Le service de tâches de fond est injoignable : rien n\'a été '
            'déplacé. Vérifiez Redis et orion-celery.')
        return redirect('system_health:disk_dashboard')

    if mode == 'basculer':
        messages.success(
            request,
            f'Bascule de « {categorie} » vers {cible} lancée. Les fichiers '
            f'déjà écrits restent où ils sont.')
    else:
        messages.success(
            request,
            f'Copie de « {categorie} » vers {cible} lancée. Chaque fichier '
            f'écrit sera relu pour contrôle, et l\'ancien emplacement sera '
            f'conservé jusqu\'à ce que vous demandiez sa suppression.')

    _audit(request, 'status_change',
           description=f'Déplacement de {categorie} vers {cible} ({mode})')
    return redirect('system_health:disk_dashboard')


@require_POST
@_require_perm('can_administrate')
def stockage_liberer_la_source(request, pk):
    """Supprime l'ancien emplacement d'une opération vérifiée."""
    from .models import OperationDeStockage
    from . import tasks

    operation = get_object_or_404(OperationDeStockage, pk=pk)

    # Seule une operation VERIFIEE donne ce droit : la copie a ete relue
    # fichier par fichier, et la bascule est faite. Avant cela, l'ancien
    # emplacement est peut-etre le seul exemplaire des donnees.
    if operation.etat != 'verifiee':
        messages.error(
            request,
            'Seule une copie vérifiée permet de libérer l\'ancien '
            'emplacement. Cette opération est à l\'état '
            f'« {operation.get_etat_display()} ».')
        return redirect('system_health:disk_dashboard')

    if request.POST.get('confirmation') != 'SUPPRIMER':
        messages.error(
            request,
            'Confirmation incorrecte : saisissez SUPPRIMER pour effacer '
            'définitivement l\'ancien emplacement.')
        return redirect('system_health:disk_dashboard')

    operation.etat = 'en_attente'
    operation.type_operation = 'supprimer_source'
    operation.fini_le = None
    operation.ajouter_au_journal(
        f'Suppression de {operation.chemin_source} demandée par '
        f'{request.user}.')
    operation.save(update_fields=['etat', 'type_operation', 'fini_le',
                                  'journal'])

    if not _mettre_en_file(tasks.supprimer_l_ancien_emplacement, operation):
        messages.error(
            request,
            'Le service de tâches de fond est injoignable : rien n\'a été '
            'supprimé. Vérifiez Redis et orion-celery.')
        return redirect('system_health:disk_dashboard')

    _audit(request, 'delete',
           description=f'Suppression de l\'ancien emplacement '
                       f'{operation.chemin_source}')
    messages.success(request,
                     'Suppression lancée. L\'espace sera libéré sous peu.')
    return redirect('system_health:disk_dashboard')


@require_GET
@_require_perm('can_view_technical')
def stockage_operation_api(request, pk):
    """L'avancement d'une opération, pour la barre de progression."""
    from .models import OperationDeStockage

    operation = get_object_or_404(OperationDeStockage, pk=pk)
    return JsonResponse({
        'id': operation.pk,
        'etat': operation.etat,
        'etat_libelle': operation.get_etat_display(),
        'en_cours': operation.est_en_cours,
        'progression': operation.progression,
        'fichiers_traites': operation.fichiers_traites,
        'fichiers_total': operation.fichiers_total,
        'octets_traites': operation.octets_traites,
        'octets_total': operation.octets_total,
        'message': operation.message,
        'journal': operation.journal[-4000:],
    })


@require_GET
@_require_perm('can_view_technical')
def disk_api(request):
    """Endpoint AJAX pour le rafraîchissement de l'état des disques."""
    return JsonResponse(get_disk_summary())


# ──────────────────────────────────────────────────────────────────────────────
# 16.7 — Registre des risques
# ──────────────────────────────────────────────────────────────────────────────

@_require_perm('can_view_risks')
def risk_list(request):
    qs = RiskRegister.objects.all()
    category = request.GET.get('category')
    status   = request.GET.get('status')
    level    = request.GET.get('level')
    if category: qs = qs.filter(category=category)
    if status:   qs = qs.filter(status=status)

    risks = list(qs.select_related('owner'))
    if level:
        risks = [r for r in risks if r.criticality_level == level]

    if request.GET.get('export') == 'csv' and has_health_perm(request.user, 'can_export_reports'):
        return _export_risks_csv(risks, request)

    return render(request, 'system_health/risk_list.html', {
        'risks':      risks,
        'filters':    {'category': category, 'status': status, 'level': level},
        'categories': RiskRegister.CATEGORY_CHOICES,
        'statuses':   RiskRegister.RISK_STATUS_CHOICES,
        'can_export': has_health_perm(request.user, 'can_export_reports'),
        'can_edit':   request.user.is_superuser or has_health_perm(request.user, 'can_administrate'),
    })


@_require_perm('can_view_risks')
def risk_detail(request, pk):
    risk = get_object_or_404(RiskRegister, pk=pk)
    can_edit = request.user.is_superuser or has_health_perm(request.user, 'can_administrate')
    form = RiskRegisterForm(request.POST or None, instance=risk) if can_edit else None

    if request.method == 'POST' and can_edit and form and form.is_valid():
        form.save()
        _audit(request, 'risk_edit', 'RiskRegister', pk)
        messages.success(request, 'Risque mis à jour.')
        return redirect('system_health:risk_detail', pk=pk)

    return render(request, 'system_health/risk_detail.html', {
        'risk': risk, 'form': form, 'can_edit': can_edit,
    })


@super_admin_required
def risk_create(request):
    form = RiskRegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        risk = form.save(commit=False)
        risk.created_by = request.user
        risk.save()
        _audit(request, 'risk_edit', 'RiskRegister', risk.pk, 'Création')
        messages.success(request, f'Risque {risk.uid} créé.')
        return redirect('system_health:risk_detail', pk=risk.pk)
    return render(request, 'system_health/risk_form.html', {'form': form, 'title': 'Nouveau risque'})


def _export_risks_csv(risks, request):
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="registre_risques.csv"'
    response.write('﻿')
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Réf', 'Titre', 'Catégorie', 'Probabilité', 'Impact',
                     'Score', 'Criticité', 'Statut', 'Responsable', 'Date cible'])
    for r in risks:
        writer.writerow([
            r.uid, r.title, r.get_category_display(),
            r.get_probability_display(), r.get_impact_display(),
            r.criticality_score, r.criticality_label, r.get_status_display(),
            r.owner.get_full_name() if r.owner else '',
            r.target_date or '',
        ])
    _audit(request, 'export', 'RiskRegister', '', 'Export CSV risques')
    return response


# ──────────────────────────────────────────────────────────────────────────────
# 16.8 — Configuration des seuils d'alerte
# ──────────────────────────────────────────────────────────────────────────────

@_require_perm('can_edit_thresholds')
def threshold_list(request):
    thresholds = AlertThreshold.objects.all().order_by('sensor_type')
    return render(request, 'system_health/threshold_list.html', {
        'thresholds': thresholds,
    })


@_require_perm('can_edit_thresholds')
def threshold_edit(request, pk=None):
    instance = get_object_or_404(AlertThreshold, pk=pk) if pk else None
    form = AlertThresholdForm(request.POST or None, instance=instance)
    if request.method == 'POST' and form.is_valid():
        t = form.save(commit=False)
        t.created_by = request.user
        t.save()
        _audit(request, 'edit_threshold', 'AlertThreshold', t.pk)
        messages.success(request, 'Seuil enregistré.')
        return redirect('system_health:threshold_list')
    return render(request, 'system_health/threshold_form.html', {
        'form': form,
        'title': 'Modifier le seuil' if pk else 'Nouveau seuil',
    })


# ──────────────────────────────────────────────────────────────────────────────
# 16.11 — Gestion des incidents
# ──────────────────────────────────────────────────────────────────────────────

@_require_perm('can_view_health')
def incident_list(request):
    qs = SystemIncident.objects.all()
    status = request.GET.get('status')
    if status: qs = qs.filter(status=status)

    paginator = Paginator(qs.order_by('-detected_at'), 20)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'system_health/incident_list.html', {
        'page':     page,
        'filters':  {'status': status},
        'statuses': SystemIncident.INCIDENT_STATUSES,
        'can_manage': has_health_perm(request.user, 'can_manage_incidents'),
    })


@_require_perm('can_view_health')
def incident_detail(request, pk):
    incident = get_object_or_404(SystemIncident, pk=pk)
    can_manage = has_health_perm(request.user, 'can_manage_incidents')
    _audit(request, 'view_incident', 'SystemIncident', pk)

    status_form   = IncidentStatusForm(request.POST if 'status_change' in (request.POST or {}) else None, instance=incident)
    timeline_form = IncidentTimelineForm(request.POST if 'timeline_add' in (request.POST or {}) else None)
    pir_form      = None
    pir = None
    try:
        pir = incident.post_report
    except PostIncidentReport.DoesNotExist:
        pass
    if not pir and can_manage:
        pir_form = PostIncidentReportForm(request.POST if 'pir_submit' in (request.POST or {}) else None)

    if request.method == 'POST' and can_manage:
        if 'status_change' in request.POST and status_form.is_valid():
            new_status = status_form.cleaned_data['status']
            status_form.save()
            if new_status == 'resolved':
                incident.resolved_at = timezone.now()
                incident.save(update_fields=['resolved_at'])
            IncidentTimeline.objects.create(
                incident=incident, event_type='update',
                author=request.user,
                description=f"Statut changé en : {incident.get_status_display()}"
            )
            _audit(request, 'status_change', 'SystemIncident', pk)
            messages.success(request, 'Statut mis à jour.')
            return redirect('system_health:incident_detail', pk=pk)

        if 'timeline_add' in request.POST and timeline_form.is_valid():
            entry = timeline_form.save(commit=False)
            entry.incident = incident
            entry.author   = request.user
            entry.save()
            return redirect('system_health:incident_detail', pk=pk)

        if 'pir_submit' in request.POST and pir_form and pir_form.is_valid():
            pir = pir_form.save(commit=False)
            pir.incident   = incident
            pir.created_by = request.user
            pir.save()
            messages.success(request, 'Rapport post-incident créé.')
            return redirect('system_health:incident_detail', pk=pk)

    return render(request, 'system_health/incident_detail.html', {
        'incident':      incident,
        'status_form':   status_form,
        'timeline_form': timeline_form,
        'pir_form':      pir_form,
        'pir':           pir,
        'can_manage':    can_manage,
    })


@_require_perm('can_manage_incidents')
def incident_create(request):
    form = SystemIncidentForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        incident = form.save(commit=False)
        incident.created_by = request.user
        incident.save()
        form.save_m2m()
        IncidentTimeline.objects.create(
            incident=incident, event_type='detected',
            author=request.user, description='Incident créé.'
        )
        _audit(request, 'status_change', 'SystemIncident', incident.pk, 'Création')
        messages.success(request, f'Incident "{incident.title}" créé.')
        return redirect('system_health:incident_detail', pk=incident.pk)
    return render(request, 'system_health/incident_form.html', {
        'form': form, 'title': 'Déclarer un incident',
    })


# ──────────────────────────────────────────────────────────────────────────────
# 16.12 — Administration des permissions
# ──────────────────────────────────────────────────────────────────────────────

@super_admin_required
def permissions_admin(request):
    users = User.objects.filter(is_active=True, is_superuser=False).order_by('username')
    user_perms = []
    for u in users:
        try:
            hp = u.health_permission
        except HealthPermission.DoesNotExist:
            hp = None
        user_perms.append((u, hp))
    return render(request, 'system_health/permissions_admin.html', {
        'user_perms': user_perms,
    })


@super_admin_required
def permission_edit(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    hp, _ = HealthPermission.objects.get_or_create(user=user)
    form = HealthPermissionForm(request.POST or None, instance=hp)
    if request.method == 'POST' and form.is_valid():
        perm = form.save(commit=False)
        perm.updated_by = request.user
        perm.save()
        _audit(request, 'status_change', 'HealthPermission', user_id,
               f"Permissions mises à jour pour {user.username}")
        messages.success(request, f'Permissions de {user.username} mises à jour.')
        return redirect('system_health:permissions_admin')
    return render(request, 'system_health/permission_form.html', {
        'form': form, 'target_user': user,
    })


# ──────────────────────────────────────────────────────────────────────────────
# 16.13 — Journal d'audit de la section santé
# ──────────────────────────────────────────────────────────────────────────────

@super_admin_required
def health_audit_log(request):
    qs = HealthAuditLog.objects.select_related('user').order_by('-created_at')
    user_id = request.GET.get('user')
    action  = request.GET.get('action')
    if user_id: qs = qs.filter(user_id=user_id)
    if action:  qs = qs.filter(action=action)

    paginator = Paginator(qs, 50)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'system_health/audit_log.html', {
        'page':    page,
        'filters': {'user': user_id, 'action': action},
        'actions': HealthAuditLog.ACTION_CHOICES,
        'users':   User.objects.filter(healthauditlog__isnull=False).distinct().order_by('username'),
    })


# ──────────────────────────────────────────────────────────────────────────────
# API AJAX — données de tableau de bord
# ──────────────────────────────────────────────────────────────────────────────

@require_GET
@_require_perm('can_view_technical')
def snapshot_history_api(request):
    """API JSON : historique des scores de santé pour les graphes de tendance."""
    hours = min(int(request.GET.get('hours', 24)), 168)
    data = get_snapshot_history(hours=hours)
    return JsonResponse({
        'hours': hours,
        'count': len(data),
        'snapshots': [
            {
                'ts':       s['collected_at'].isoformat(),
                'score':    s['global_score'],
                'status':   s['global_status'],
                'server':   s['server_score'],
                'app':      s['app_score'],
                'database': s['database_score'],
                'backups':  s['backups_score'],
                'security': s['security_score'],
                'celery':   s['celery_score'],
                'critical': s['critical_sensors'],
            }
            for s in data
        ],
    })


@require_GET
@_require_perm('can_view_health')
def dashboard_api(request):
    """Endpoint AJAX pour le rafraîchissement du tableau de bord (30s polling)."""
    health = compute_global_health()
    from .models import HEALTH_STATUSES
    STATUS_LABELS = dict(HEALTH_STATUSES)
    return JsonResponse({
        'status':       health['status'],
        'status_label': STATUS_LABELS.get(health['status'], health['status']),
        'score':        health['score'],
        'breakdown':    health['breakdown'],
        'critical':     health['critical'],
        'warnings':     health['warnings'],
        'open_errors':  SystemError.objects.filter(
                            status__in=['new', 'confirmed', 'in_progress']).count(),
        'open_incidents': SystemIncident.objects.filter(
                            status__in=['open', 'investigating', 'identified']).count(),
        'timestamp':    health['timestamp'].isoformat(),
    })
