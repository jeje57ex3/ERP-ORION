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
    compute_global_health, get_disk_summary, get_latest_sensor_readings,
    get_snapshot_history,
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
    return render(request, 'system_health/disk_dashboard.html', {
        'disks': get_disk_summary(),
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
