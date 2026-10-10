"""
apps/configurator/erp_views.py — Outils internes ERP pour le configurateur
NÉOSTRUCTURA : simulateur admin (§45) et tableau de bord analytique (§52).

Contrairement à apps/configurator/public_api.py (visiteur anonyme, jamais
de marge/coût/journal de calcul), ces vues sont réservées au personnel
connecté (@login_required, scope `request.current_company` comme le reste
de l'ERP) et exposent volontairement tout le détail interne.
"""
import json

from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from .models import ConfiguratorSubmission, ConfiguratorSession
from .services import engine
from .services.pricing import compute_estimate


def _company(request):
    return request.current_company


# ─── SIMULATEUR (§45) ───────────────────────────────────────────────────────────

@login_required
def simulator_view(request):
    company = _company(request)
    domains = engine.get_domains(company) if company else []
    return render(request, 'configurator/simulator.html', {'domains': domains})


@login_required
def simulator_services(request):
    company = _company(request)
    _, services = engine.get_services(company, request.GET.get('domain_code', ''))
    return JsonResponse({'services': [{'code': s.code, 'name': s.name} for s in services]})


@login_required
def simulator_questions(request):
    company = _company(request)
    service = engine.get_service(company, request.GET.get('service_code', ''))
    if not service:
        return JsonResponse({'error': 'Prestation introuvable.'}, status=404)
    try:
        answers = json.loads(request.GET.get('answers') or '{}')
    except json.JSONDecodeError:
        answers = {}
    return JsonResponse({'questions': engine.get_questions_payload(service, answers)})


def _serialize_full_estimate(estimate):
    """Version JSON-sérialisable de l'estimation interne complète (marge,
    coûts, journal de calcul) — réservée à cette vue authentifiée."""
    out = dict(estimate)
    out['costs'] = dict(estimate['costs'])
    out['costs']['margin_percent'] = float(out['costs']['margin_percent'])
    out['material_lines'] = [
        {
            'code': line['price_item'].code, 'name': line['price_item'].name,
            'unit': line['price_item'].unit, 'qty': line['qty'],
            'price_avg': float(line['price_item'].price_avg),
            'total_avg': round(float(line['price_item'].price_avg) * line['qty'], 2),
        }
        for line in estimate['material_lines']
    ]
    return out


@login_required
@require_POST
def simulator_estimate(request):
    company = _company(request)
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Requête invalide.'}, status=400)
    service = engine.get_service(company, data.get('service_code', ''))
    if not service:
        return JsonResponse({'error': 'Prestation introuvable.'}, status=404)
    answers = data.get('answers') or {}
    if not isinstance(answers, dict):
        answers = {}
    urgency = data.get('urgency') if data.get('urgency') in ('urgent', 'normal', 'flexible') else 'normal'
    estimate = compute_estimate(company, service, answers, urgency)
    return JsonResponse(_serialize_full_estimate(estimate))


# ─── ANALYTIQUE (§52) ───────────────────────────────────────────────────────────

@login_required
def analytics_view(request):
    """Dérivé uniquement des données déjà stockées (aucun nouveau tracking
    ajouté dans cette tranche) : volume par domaine/prestation, score de
    confiance moyen, taux de validation humaine, écart estimation vs devis
    final quand un devis a été créé depuis la demande."""
    company = _company(request)
    submissions = ConfiguratorSubmission.objects.filter(request__company=company)

    by_domain = list(
        submissions.exclude(domain__isnull=True)
        .values('domain__name').annotate(total=Count('id')).order_by('-total')
    )
    by_service = list(
        submissions.exclude(service__isnull=True)
        .values('service__name')
        .annotate(total=Count('id'), avg_confidence=Avg('confidence_score'))
        .order_by('-total')[:15]
    )
    totals = {
        'total_submissions': submissions.count(),
        'human_validation_required': submissions.filter(human_validation_required=True).count(),
        'danger_detected': submissions.filter(danger_detected=True).count(),
        'avg_confidence_score': submissions.aggregate(avg=Avg('confidence_score'))['avg'],
        'sessions_in_progress': ConfiguratorSession.objects.filter(company=company, status='in_progress').count(),
        'sessions_submitted': ConfiguratorSession.objects.filter(company=company, status='submitted').count(),
    }

    estimate_vs_quote = []
    linked = submissions.filter(request__btp_quote__isnull=False).select_related('request__btp_quote')
    for sub in linked[:200]:
        quote = sub.request.btp_quote
        if quote and quote.total_ht and sub.recommended_price:
            diff_pct = round((float(quote.total_ht) - float(sub.recommended_price)) / float(sub.recommended_price) * 100, 1)
            estimate_vs_quote.append({
                'reference': sub.request.reference,
                'estimated': float(sub.recommended_price),
                'quoted': float(quote.total_ht),
                'diff_pct': diff_pct,
            })

    diffs = [e['diff_pct'] for e in estimate_vs_quote]
    avg_diff_pct = round(sum(diffs) / len(diffs), 1) if diffs else None

    return render(request, 'configurator/analytics.html', {
        'totals': totals, 'by_domain': by_domain, 'by_service': by_service,
        'estimate_vs_quote': estimate_vs_quote[:30], 'avg_diff_pct': avg_diff_pct,
    })
