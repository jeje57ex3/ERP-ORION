"""
apps/orion_ops/views.py — Tableau de bord OpsV2 (Super Admin uniquement).

Routes sous /orion-admin/ops/
"""
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.cache import never_cache
from django.utils import timezone
from django.core.paginator import Paginator

_superuser = user_passes_test(lambda u: u.is_active and u.is_superuser)


def _ops_login(f):
    return login_required(_superuser(f))


# ── Tableau de bord principal ─────────────────────────────────────────────────

@_ops_login
def dashboard(request):
    from apps.orion_ops.services.score_service import get_latest_extended_scores
    from apps.orion_ops.services.slo_service import refresh_all_slos
    from apps.orion_ops.models import (
        SLOTarget, DataQualityAnomaly, FailedTask,
        ServiceComponent, Deployment,
    )
    from apps.system_health.models import HealthSnapshot, SystemIncident

    # Scores étendus
    extended_scores = get_latest_extended_scores()

    # Derniers incidents ouverts
    open_incidents = SystemIncident.objects.filter(
        status__in=['detected', 'confirmed', 'assigned', 'investigating', 'fixing']
    ).order_by('-detected_at')[:5]

    # SLO résumé + liste
    all_slos = SLOTarget.objects.filter(enabled=True).order_by('status', 'name')
    slo_summary = {
        'ok':      all_slos.filter(status='ok').count(),
        'at_risk': all_slos.filter(status='at_risk').count(),
        'breached': all_slos.filter(status='breached').count(),
        'no_data': all_slos.filter(status='no_data').count(),
    }

    # Anomalies qualité ouvertes
    open_anomalies = DataQualityAnomaly.objects.filter(
        status__in=['open', 'acknowledged']
    ).order_by('-detected_at')[:5]

    # Tâches Celery échouées
    failed_tasks = FailedTask.objects.filter(status='failed').order_by('-failed_at')[:5]

    # Composants en problème
    components_down = ServiceComponent.objects.filter(
        status__in=['down', 'degraded'], is_active=True
    ).order_by('criticality')

    # Dernier déploiement
    last_deploy = Deployment.objects.order_by('-deployed_at').first()

    # Score global
    last_snapshot = HealthSnapshot.objects.order_by('-collected_at').first()

    return render(request, 'orion_ops/dashboard.html', {
        'extended_scores': extended_scores,
        'open_incidents': open_incidents,
        'slo_summary': slo_summary,
        'slos': all_slos,
        'open_anomalies': open_anomalies,
        'failed_tasks': failed_tasks,
        'components_down': components_down,
        'last_deploy': last_deploy,
        'last_snapshot': last_snapshot,
        'page_title': 'OpsV2 — Tableau de bord',
    })


# ── SLO ───────────────────────────────────────────────────────────────────────

@_ops_login
def slo_list(request):
    from apps.orion_ops.models import SLOTarget
    slos = SLOTarget.objects.prefetch_related('components').order_by('status', 'name')
    return render(request, 'orion_ops/slo_list.html', {
        'slos': slos,
        'page_title': 'Objectifs de service (SLO)',
    })


@_ops_login
def slo_detail(request, slug):
    from apps.orion_ops.models import SLOTarget, SLOBreach
    slo = get_object_or_404(SLOTarget, slug=slug)
    breaches = SLOBreach.objects.filter(slo=slo).order_by('-created_at')[:20]
    return render(request, 'orion_ops/slo_detail.html', {
        'slo': slo,
        'breaches': breaches,
        'page_title': f'SLO — {slo.name}',
    })


@_ops_login
@never_cache
def slo_api(request):
    """GET /orion-admin/ops/api/slo/ — JSON pour graphiques."""
    from apps.orion_ops.models import SLOTarget
    slos = SLOTarget.objects.filter(enabled=True).values(
        'slug', 'name', 'target_pct', 'current_value', 'error_budget_pct', 'status'
    )
    return JsonResponse({'slos': list(slos)})


# ── Cartographie des dépendances ───────────────────────────────────────────────

@_ops_login
def dependency_map(request):
    from apps.orion_ops.models import ServiceComponent, ComponentDependency
    components = ServiceComponent.objects.filter(is_active=True).order_by('criticality', 'name')
    deps = ComponentDependency.objects.select_related('source', 'target').all()
    return render(request, 'orion_ops/dependency_map.html', {
        'components': components,
        'deps': deps,
        'page_title': 'Cartographie des dépendances',
    })


@_ops_login
@never_cache
def dependency_api(request):
    """GET /orion-admin/ops/api/dependencies/ — JSON pour visualisation graphe."""
    from apps.orion_ops.models import ServiceComponent, ComponentDependency
    nodes = [
        {
            'id': c.slug, 'label': c.name, 'type': c.component_type,
            'status': c.status, 'criticality': c.criticality,
        }
        for c in ServiceComponent.objects.filter(is_active=True)
    ]
    edges = [
        {
            'source': d.source.slug, 'target': d.target.slug,
            'type': d.dep_type, 'impact': d.impact_desc,
        }
        for d in ComponentDependency.objects.select_related('source', 'target')
    ]
    return JsonResponse({'nodes': nodes, 'edges': edges})


# ── Qualité des données ────────────────────────────────────────────────────────

@_ops_login
def data_quality(request):
    from apps.orion_ops.models import DataQualityAnomaly
    anomalies = DataQualityAnomaly.objects.order_by('-detected_at')
    paginator = Paginator(anomalies, 25)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'orion_ops/data_quality.html', {
        'anomalies': page,
        'open_count': anomalies.filter(status__in=['open', 'acknowledged', 'fixing']).count(),
        'page_title': 'Qualité des données',
    })


# ── Déploiements ──────────────────────────────────────────────────────────────

@_ops_login
def deployment_list(request):
    from apps.orion_ops.models import Deployment
    deployments = Deployment.objects.order_by('-deployed_at')
    paginator = Paginator(deployments, 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'orion_ops/deployment_list.html', {
        'deployments': page,
        'page_title': 'Registre des déploiements',
    })


@_ops_login
def deployment_create(request):
    from apps.orion_ops.models import Deployment
    from apps.system_health.models import HealthSnapshot

    if request.method == 'POST':
        last_snapshot = HealthSnapshot.objects.order_by('-collected_at').first()
        metrics_before = {}
        if last_snapshot:
            metrics_before = {
                'global': last_snapshot.global_score,
                'app': last_snapshot.app_score,
                'db': last_snapshot.database_score,
            }
        deploy = Deployment.objects.create(
            version=request.POST.get('version', ''),
            environment=request.POST.get('environment', 'production'),
            git_commit=request.POST.get('git_commit', ''),
            git_branch=request.POST.get('git_branch', ''),
            features=request.POST.get('features', ''),
            fixes=request.POST.get('fixes', ''),
            risks=request.POST.get('risks', ''),
            rollback_procedure=request.POST.get('rollback_procedure', ''),
            deployed_by=request.user,
            metrics_before=metrics_before,
        )
        from django.shortcuts import redirect
        from django.urls import reverse
        return redirect('orion_ops:deployment_list')

    return render(request, 'orion_ops/deployment_form.html', {
        'page_title': 'Nouveau déploiement',
    })


# ── Tests de restauration ──────────────────────────────────────────────────────

@_ops_login
def restore_test_list(request):
    from apps.orion_ops.models import RestoreTest
    tests = RestoreTest.objects.select_related('backup_job', 'triggered_by').order_by('-tested_at')
    paginator = Paginator(tests, 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'orion_ops/restore_test_list.html', {
        'tests': page,
        'page_title': 'Tests de restauration',
    })


# ── Capacité ──────────────────────────────────────────────────────────────────

@_ops_login
def capacity_dashboard(request):
    from apps.orion_ops.services.capacity_service import get_latest_capacity_trends
    trends = get_latest_capacity_trends()
    return render(request, 'orion_ops/capacity.html', {
        'trends': trends,
        'page_title': 'Prévisions de capacité',
    })


# ── Scores étendus API ────────────────────────────────────────────────────────

@_ops_login
@never_cache
def extended_scores_api(request):
    """GET /orion-admin/ops/api/scores/ — JSON scores étendus."""
    from apps.orion_ops.services.score_service import get_latest_extended_scores
    scores = get_latest_extended_scores()
    # Sérialiser les datetimes
    for domain, s in scores.items():
        if 'computed_at' in s and s['computed_at']:
            scores[domain] = dict(s, computed_at=s['computed_at'].isoformat())
    return JsonResponse({'scores': scores})


# ── Tâches Celery échouées ────────────────────────────────────────────────────

@_ops_login
def failed_tasks_list(request):
    from apps.orion_ops.models import FailedTask
    tasks = FailedTask.objects.order_by('-failed_at')
    paginator = Paginator(tasks, 25)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'orion_ops/failed_tasks.html', {
        'tasks': page,
        'page_title': 'Tâches Celery échouées',
    })


@_ops_login
@require_POST
def failed_task_close(request, pk):
    from apps.orion_ops.models import FailedTask
    task = get_object_or_404(FailedTask, pk=pk)
    task.status = 'closed'
    task.close_reason = request.POST.get('reason', 'Fermée manuellement')
    task.save(update_fields=['status', 'close_reason'])
    return JsonResponse({'ok': True})


# ── Règles d'alerte ───────────────────────────────────────────────────────────

@_ops_login
def alert_rules_list(request):
    from apps.orion_ops.models import AlertRule
    rules = AlertRule.objects.order_by('severity', 'name')
    return render(request, 'orion_ops/alert_rules.html', {
        'rules': rules,
        'page_title': 'Règles d\'alerte',
        'counts': {
            'total':     rules.count(),
            'enabled':   rules.filter(enabled=True).count(),
            'triggered': rules.filter(last_status='triggered').count(),
        },
    })


@_ops_login
@require_POST
def alert_rule_toggle(request, pk):
    from apps.orion_ops.models import AlertRule
    rule = get_object_or_404(AlertRule, pk=pk)
    rule.enabled = not rule.enabled
    rule.save(update_fields=['enabled', 'updated_at'])
    return JsonResponse({'ok': True, 'enabled': rule.enabled})


# ── Plan de Continuité d'Activité (BCP) ──────────────────────────────────────

@_ops_login
def bcp_list(request):
    from apps.orion_ops.models import BCPScenario
    scenarios = BCPScenario.objects.filter(is_active=True).order_by('priority', 'scenario_type')
    return render(request, 'orion_ops/bcp_list.html', {
        'scenarios': scenarios,
        'page_title': 'Plan de continuité d\'activité',
        'needs_retest_count': sum(1 for s in scenarios if s.needs_retest),
        'not_tested_count':   scenarios.filter(last_result='not_tested').count(),
    })


@_ops_login
def bcp_create(request):
    from apps.orion_ops.models import BCPScenario, ServiceComponent
    if request.method == 'POST':
        scenario = BCPScenario.objects.create(
            name=request.POST.get('name', ''),
            scenario_type=request.POST.get('scenario_type', 'service_down'),
            description=request.POST.get('description', ''),
            priority=request.POST.get('priority', 'high'),
            rto_hours=float(request.POST.get('rto_hours', 4)),
            rpo_hours=float(request.POST.get('rpo_hours', 1)),
            owner=request.user,
        )
        from django.shortcuts import redirect
        return redirect('orion_ops:bcp_list')
    components = ServiceComponent.objects.filter(is_active=True).order_by('criticality', 'name')
    return render(request, 'orion_ops/bcp_form.html', {
        'page_title': 'Nouveau scénario BCP',
        'components': components,
        'scenario_types': BCPScenario.SCENARIO_TYPES,
        'priorities': BCPScenario.PRIORITIES,
    })


# ── Tests de défaillance ──────────────────────────────────────────────────────

@_ops_login
def failure_tests_list(request):
    from apps.orion_ops.models import FailureTest
    tests = FailureTest.objects.select_related('target_component', 'executed_by').order_by('-created_at')
    paginator = Paginator(tests, 20)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'orion_ops/failure_tests.html', {
        'tests': page,
        'page_title': 'Tests de défaillance',
        'pending_count':  tests.filter(result='pending').count(),
        'failed_count':   tests.filter(result='failed', remediation_done=False).count(),
    })


@_ops_login
def failure_test_create(request):
    from apps.orion_ops.models import FailureTest, ServiceComponent
    if request.method == 'POST':
        component_id = request.POST.get('target_component')
        FailureTest.objects.create(
            name=request.POST.get('name', ''),
            test_type=request.POST.get('test_type', 'custom'),
            description=request.POST.get('description', ''),
            target_component_id=component_id if component_id else None,
            result='pending',
            executed_by=request.user,
        )
        from django.shortcuts import redirect
        return redirect('orion_ops:failure_tests_list')
    components = ServiceComponent.objects.filter(is_active=True).order_by('criticality', 'name')
    return render(request, 'orion_ops/failure_test_form.html', {
        'page_title': 'Nouveau test de défaillance',
        'components': components,
        'test_types': FailureTest.TEST_TYPES,
    })
