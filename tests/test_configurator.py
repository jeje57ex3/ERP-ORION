"""
tests/test_configurator.py — Moteur configurateur générique (apps.configurator).
Couvre électricité (pose, diagnostic dangereux), réseau (quantité dérivée
d'une réponse), tarification (matériel/main-d'œuvre/déplacement/marge/
fourchette/gamme), CRM (dédup), et sécurité (isolation entreprise, API
publique, marge jamais exposée).
"""
import json
from decimal import Decimal

import pytest
from django.test import Client

from apps.btp.models import ElectricityPriceLibrary, GuidedQuoteRequest
from apps.configurator.models import (
    ServiceDomain, ServiceCategory, ConfiguratorQuestion, ConfiguratorQuestionOption,
    MaterialRequirement, LaborRule, TravelRule, MarginRule, DiagnosticScenario,
    ConfiguratorSubmission,
)
from apps.configurator.models import ConfiguratorSession, ConfiguratorSessionLot
from apps.configurator.services import engine
from apps.configurator.services.confidence import DONT_KNOW
from apps.configurator.services.formulas import evaluate_formula
from apps.configurator.services.pricing import compute_estimate
from apps.crm.models import Customer, Prospect


# ─── Fixtures ──────────────────────────────────────────────────────────────────
#
# NB : conftest.py::company / company_b appellent explicitement
# CompanySettings.objects.create(company=co) juste après Company.objects.create(),
# alors qu'un signal post_save (apps.core.signals.create_company_settings)
# en crée déjà un via get_or_create — IntegrityError garanti (contrainte
# unique sur company_id). Bug préexistant dans conftest.py, pas de notre
# fait ni de notre périmètre : on le contourne localement à ce fichier en
# redéfinissant ces deux fixtures sans l'appel redondant, plutôt que de
# corriger l'infrastructure de test partagée sans l'accord de l'utilisateur.

@pytest.fixture
def company(db):
    from apps.core.models import Company
    return Company.objects.create(
        name='Test Company SA', slug='test-company-sa', status='active', is_active=True,
    )


@pytest.fixture
def company_b(db):
    from apps.core.models import Company
    return Company.objects.create(
        name='Other Company SARL', slug='other-company-sarl', status='active', is_active=True,
    )


@pytest.fixture(autouse=True)
def _clear_rate_limit_cache():
    """Le rate-limiting de l'API publique s'appuie sur le cache Django —
    évite qu'un test épuise le quota d'un autre (même IP en environnement
    de test)."""
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def price_prise(company):
    return ElectricityPriceLibrary.objects.create(
        company=company, code='TST-PRISE', name='Prise test', category='prise_interrupteur', unit='u',
        price_min=50, price_avg=60, price_max=80, duration_hours=1, product_family='Prise test',
        metier='electricite', quality_level='standard',
    )


@pytest.fixture
def price_prise_premium(company, price_prise):
    return ElectricityPriceLibrary.objects.create(
        company=company, code='TST-PRISE-PREM', name='Prise test premium', category='prise_interrupteur', unit='u',
        price_min=90, price_avg=100, price_max=120, duration_hours=1, product_family='Prise test',
        metier='electricite', quality_level='premium',
    )


@pytest.fixture
def price_rj45(company):
    return ElectricityPriceLibrary.objects.create(
        company=company, code='TST-RJ45', name='Prise RJ45 test', category='reseau', unit='u',
        price_min=60, price_avg=80, price_max=100, duration_hours=1,
    )


@pytest.fixture
def domain_electricite(company):
    return ServiceDomain.objects.create(company=company, code='electricite', name='Électricité', order=1)


@pytest.fixture
def domain_reseau(company):
    return ServiceDomain.objects.create(company=company, code='reseau', name='Réseau', order=2)


@pytest.fixture
def labor_travel_margin(company):
    LaborRule.objects.create(company=company, domain=None, rate_type='normal', hourly_rate=Decimal('50'))
    LaborRule.objects.create(company=company, domain=None, rate_type='urgent', hourly_rate=Decimal('80'))
    TravelRule.objects.create(company=company, zone_code='z1', zone_label='Zone 1', flat_fee=Decimal('20'), is_default=True)
    MarginRule.objects.create(company=company, scope_type='global', margin_percent=Decimal('20'))


@pytest.fixture
def service_pose_prise(company, domain_electricite, price_prise, labor_travel_margin):
    service = ServiceCategory.objects.create(
        domain=domain_electricite, company=company, code='pose-prise', name='Pose de prise',
        intervention_type='installation_neuve', requires_diagnostic=False, confidence_level='high',
        duration_min_hours=1, duration_avg_hours=1, duration_max_hours=2, estimate_width_pct=10,
    )
    q = ConfiguratorQuestion.objects.create(
        service=service, identifier='nb_prises', label='Combien de prises ?',
        question_type='number', order=1, is_required=True, impacts_material=True,
    )
    MaterialRequirement.objects.create(
        service=service, price_item=price_prise, quantity_source='from_answer',
        quantity_answer=q, quantity_multiplier=1,
    )
    return service


@pytest.fixture
def service_disjoncteur(company, domain_electricite, labor_travel_margin):
    service = ServiceCategory.objects.create(
        domain=domain_electricite, company=company, code='depannage-disjoncteur', name='Disjoncteur qui saute',
        intervention_type='depannage', requires_diagnostic=True, confidence_level='diagnostic_required',
        duration_min_hours=0.5, duration_avg_hours=1, duration_max_hours=2, estimate_width_pct=30,
        danger_alert=True,
    )
    ConfiguratorQuestion.objects.create(
        service=service, identifier='danger_signes', label='Fumée, étincelles ?',
        question_type='boolean', order=1, is_required=True, impacts_diagnostic=True,
    )
    DiagnosticScenario.objects.create(
        service=service,
        hypotheses=[{'label': 'Court-circuit', 'likelihood': 'medium'}],
        diagnostic_min_hours=0.5, diagnostic_avg_hours=1, diagnostic_max_hours=1.5,
        danger_keywords=['fumée', 'brûlé'],
    )
    return service


@pytest.fixture
def service_rj45(company, domain_reseau, price_rj45, labor_travel_margin):
    service = ServiceCategory.objects.create(
        domain=domain_reseau, company=company, code='rj45', name='Création RJ45',
        intervention_type='installation_neuve', requires_diagnostic=False, confidence_level='medium',
        duration_min_hours=1, duration_avg_hours=1, duration_max_hours=2, estimate_width_pct=15,
    )
    q = ConfiguratorQuestion.objects.create(
        service=service, identifier='nb_prises_rj45', label='Combien de prises RJ45 ?',
        question_type='number', order=1, is_required=True, impacts_material=True,
    )
    MaterialRequirement.objects.create(
        service=service, price_item=price_rj45, quantity_source='from_answer',
        quantity_answer=q, quantity_multiplier=1,
    )
    return service


def _contact(email='client@example.com'):
    return {'first_name': 'Jean', 'last_name': 'Test', 'email': email, 'phone': '0600000000'}


# ─── Électricité ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_pose_prise_high_confidence_creates_draft_quote(company, service_pose_prise):
    qr, public = engine.submit_configurator_request(company, {
        'service_code': 'pose-prise', 'urgency': 'normal', 'answers': {'nb_prises': 3},
        'contact': _contact(), 'building': {}, 'notes': '',
    })
    assert qr.company_id == company.id
    assert qr.btp_quote_id is not None, 'confiance haute -> devis brouillon auto-créé'
    submission = qr.configurator_submission
    assert submission.human_validation_required is False
    assert 'price' in public and 'min' in public['price']


@pytest.mark.django_db
def test_disjoncteur_with_danger_requires_human_validation(company, service_disjoncteur):
    qr, public = engine.submit_configurator_request(company, {
        'service_code': 'depannage-disjoncteur', 'urgency': 'urgent',
        'answers': {'danger_signes': True}, 'contact': _contact(), 'building': {}, 'notes': '',
    })
    assert qr.btp_quote_id is None, 'diagnostic + danger -> jamais de devis auto'
    submission = qr.configurator_submission
    assert submission.human_validation_required is True
    assert submission.danger_detected is True
    assert submission.confidence_level == 'diagnostic_required'
    # Le client voit l'alerte et une fourchette, jamais un diagnostic affirmé
    assert public['requires_diagnostic'] is True
    assert public.get('safety_message')
    assert 'hypotheses' not in public, 'les hypothèses restent internes (ConfiguratorSubmission), pas publiques'


@pytest.mark.django_db
def test_danger_keyword_in_free_text_also_triggers_alert(company, service_disjoncteur):
    qr, public = engine.submit_configurator_request(company, {
        'service_code': 'depannage-disjoncteur', 'urgency': 'normal',
        'answers': {'danger_signes': False, 'depuis_quand': "ça sent le brûlé depuis ce matin"},
        'contact': _contact(), 'building': {}, 'notes': '',
    })
    assert qr.configurator_submission.danger_detected is True


# ─── Réseau (quantité dérivée d'une réponse) ───────────────────────────────────

@pytest.mark.django_db
def test_rj45_quantity_scales_with_answer(company, service_rj45):
    preview_2 = engine.estimate_preview(company, 'rj45', {'nb_prises_rj45': 2})
    preview_5 = engine.estimate_preview(company, 'rj45', {'nb_prises_rj45': 5})
    assert preview_5['price']['avg'] > preview_2['price']['avg']
    # 3 prises de plus x 80€ (price_avg) = 240€ de matériel en plus, à la marge (20%) près
    assert preview_5['price']['avg'] - preview_2['price']['avg'] == pytest.approx(240 * 1.2, rel=0.05)


# ─── Tarification ───────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_compute_estimate_material_labor_travel_margin_breakdown(company, service_pose_prise):
    estimate = compute_estimate(company, service_pose_prise, {'nb_prises': 2}, urgency='normal')
    # matériel : 2 x 60 (price_avg) = 120 ; main-d'œuvre : 1h x 50€/h = 50 ; déplacement : 20
    assert estimate['costs']['material_avg'] == pytest.approx(120, rel=0.01)
    assert estimate['costs']['labor_avg'] == pytest.approx(50, rel=0.01)
    assert estimate['costs']['travel'] == pytest.approx(20, rel=0.01)
    cost = 120 + 50 + 20
    assert estimate['costs']['cost_avg'] == pytest.approx(cost, rel=0.01)
    # marge 20% -> prix conseillé = coût x 1.2
    assert estimate['price']['avg'] == pytest.approx(cost * 1.2, rel=0.02)


@pytest.mark.django_db
def test_urgent_uses_urgent_labor_rate(company, service_pose_prise):
    normal = compute_estimate(company, service_pose_prise, {'nb_prises': 1}, urgency='normal')
    urgent = compute_estimate(company, service_pose_prise, {'nb_prises': 1}, urgency='urgent')
    assert urgent['costs']['labor_avg'] > normal['costs']['labor_avg']


@pytest.mark.django_db
def test_diagnostic_service_has_wider_price_range_than_precise_service(company, service_pose_prise, service_disjoncteur):
    precise = compute_estimate(company, service_pose_prise, {'nb_prises': 1}, urgency='normal')
    uncertain = compute_estimate(company, service_disjoncteur, {'danger_signes': False}, urgency='normal')
    precise_spread = (precise['price']['max'] - precise['price']['min']) / max(precise['price']['avg'], 1)
    uncertain_spread = (uncertain['price']['max'] - uncertain['price']['min']) / max(uncertain['price']['avg'], 1)
    assert uncertain_spread > precise_spread


@pytest.mark.django_db
def test_gamme_answer_switches_to_sibling_product(company, domain_electricite, price_prise, price_prise_premium, labor_travel_margin):
    service = ServiceCategory.objects.create(
        domain=domain_electricite, company=company, code='pose-gamme', name='Pose avec gamme',
        duration_min_hours=1, duration_avg_hours=1, duration_max_hours=1,
    )
    q = ConfiguratorQuestion.objects.create(service=service, identifier='nb', label='Nb', question_type='number', order=1)
    MaterialRequirement.objects.create(service=service, price_item=price_prise, quantity_source='from_answer', quantity_answer=q)

    standard = compute_estimate(company, service, {'nb': 1, 'gamme': 'standard'})
    premium = compute_estimate(company, service, {'nb': 1, 'gamme': 'premium'})
    assert standard['material_lines'][0]['price_item'].code == 'TST-PRISE'
    assert premium['material_lines'][0]['price_item'].code == 'TST-PRISE-PREM'
    assert premium['price']['avg'] > standard['price']['avg']


# ─── Score de confiance / nécessité de visite (V2 §32-33) ──────────────────────

@pytest.mark.django_db
def test_visit_necessity_non_necessaire_for_simple_fully_answered_service(company, service_pose_prise):
    estimate = compute_estimate(company, service_pose_prise, {'nb_prises': 3}, urgency='normal')
    assert estimate['visit_necessity'] == 'non_necessaire'
    assert estimate['confidence_score'] >= 60


@pytest.mark.django_db
def test_visit_necessity_obligatoire_when_danger_detected(company, service_disjoncteur):
    estimate = compute_estimate(company, service_disjoncteur, {'danger_signes': True}, urgency='urgent')
    assert estimate['visit_necessity'] == 'obligatoire'
    assert estimate['confidence_score'] <= 35


@pytest.mark.django_db
def test_dont_know_answer_does_not_block_but_lowers_confidence(company, service_pose_prise):
    answered = compute_estimate(company, service_pose_prise, {'nb_prises': 2})
    unknown = compute_estimate(company, service_pose_prise, {'nb_prises': DONT_KNOW})
    assert unknown['confidence_score'] < answered['confidence_score']


@pytest.mark.django_db
def test_dont_know_answer_recorded_as_missing_info_on_submission(company, service_pose_prise):
    qr, _ = engine.submit_configurator_request(company, {
        'service_code': 'pose-prise', 'answers': {'nb_prises': DONT_KNOW},
        'contact': _contact('dontknow@example.com'), 'building': {},
    })
    assert 'nb_prises' in qr.configurator_submission.missing_info


@pytest.mark.django_db
def test_confidence_score_never_exposed_publicly(company, service_pose_prise):
    public = engine.estimate_preview(company, 'pose-prise', {'nb_prises': 2})
    serialized = json.dumps(public).lower()
    assert 'confidence_score' not in serialized


# ─── Session persistante (V2 §4/§50) ───────────────────────────────────────────

@pytest.mark.django_db
def test_session_update_persists_answers_and_recomputes_visit_necessity(company, service_pose_prise):
    session = ConfiguratorSession.objects.create(company=company)
    updated = engine.update_session(
        session, domain_code='electricite', service_code='pose-prise', urgency='normal',
        answers={'nb_prises': 3},
    )
    assert updated.answers == {'nb_prises': 3}
    assert updated.service_id == service_pose_prise.id
    assert updated.visit_necessity == 'non_necessaire'

    reloaded = ConfiguratorSession.objects.get(pk=session.pk)
    assert reloaded.answers == {'nb_prises': 3}


@pytest.mark.django_db
def test_session_merges_answers_across_multiple_updates(company, service_pose_prise):
    session = ConfiguratorSession.objects.create(company=company)
    engine.update_session(session, 'electricite', 'pose-prise', 'normal', {'nb_prises': 1})
    session.refresh_from_db()
    engine.update_session(session, None, None, None, {'gamme': 'premium'})
    session.refresh_from_db()
    assert session.answers == {'nb_prises': 1, 'gamme': 'premium'}


@pytest.mark.django_db
def test_session_never_crosses_company_boundary(company, company_b):
    session = ConfiguratorSession.objects.create(company=company)
    assert ConfiguratorSession.objects.for_company(company_b).filter(pk=session.pk).count() == 0


# ─── Journal de calcul (V2 §42/§46) ────────────────────────────────────────────

@pytest.mark.django_db
def test_calculation_log_traces_applied_rules(company, service_pose_prise):
    estimate = compute_estimate(company, service_pose_prise, {'nb_prises': 2})
    types = {entry['type'] for entry in estimate['calculation_log']}
    assert {'material', 'labor', 'travel', 'margin'} <= types


@pytest.mark.django_db
def test_calculation_log_stored_internally_but_never_exposed_publicly(company, service_pose_prise):
    qr, public = engine.submit_configurator_request(company, {
        'service_code': 'pose-prise', 'answers': {'nb_prises': 2},
        'contact': _contact('log@example.com'), 'building': {},
    })
    assert qr.configurator_submission.calculation_log, 'le journal doit être conservé côté interne'
    assert 'calculation_log' not in json.dumps(public).lower()


# ─── Architecture multi-lot (V2 §12-13 : « mode projet ») ──────────────────────

@pytest.mark.django_db
def test_add_lot_computes_estimate_and_session_totals_aggregate(company, service_pose_prise, service_rj45):
    session = ConfiguratorSession.objects.create(company=company)
    engine.add_lot(session, 'electricite', 'pose-prise', 'normal', {'nb_prises': 2}, label='Prises salon')
    engine.add_lot(session, 'reseau', 'rj45', 'normal', {'nb_prises_rj45': 3}, label='Réseau bureau')

    assert session.lots.count() == 2
    payload = engine.session_payload(session)
    assert len(payload['lots']) == 2
    assert payload['totals'] is not None
    single_min = sum(lot['estimate']['price']['min'] for lot in payload['lots'])
    assert payload['totals']['price_min'] == pytest.approx(single_min, rel=0.01)


@pytest.mark.django_db
def test_update_lot_merges_answers_and_remove_lot_deletes_it(company, service_pose_prise):
    session = ConfiguratorSession.objects.create(company=company)
    lot = engine.add_lot(session, 'electricite', 'pose-prise', 'normal', {'nb_prises': 1})
    engine.update_lot(lot, None, None, None, {'gamme': 'standard'})
    lot.refresh_from_db()
    assert lot.answers == {'nb_prises': 1, 'gamme': 'standard'}

    engine.remove_lot(session, lot.id)
    assert ConfiguratorSessionLot.objects.filter(pk=lot.id).count() == 0


@pytest.mark.django_db
def test_submit_configurator_project_creates_one_quote_request_per_lot(company, service_pose_prise, service_rj45):
    session = ConfiguratorSession.objects.create(company=company)
    engine.add_lot(session, 'electricite', 'pose-prise', 'normal', {'nb_prises': 2})
    engine.add_lot(session, 'reseau', 'rj45', 'normal', {'nb_prises_rj45': 1})

    quote_requests, project = engine.submit_configurator_project(company, {
        'session_key': str(session.session_key), 'contact': _contact('projet@example.com'), 'building': {},
    })
    assert len(quote_requests) == 2
    for qr in quote_requests:
        assert qr.configurator_submission.session_id == session.pk
    session.refresh_from_db()
    assert session.status == 'submitted'
    assert len(project['lots']) == 2
    assert 'totals' in project
    serialized = json.dumps(project).lower()
    for forbidden in ('margin', 'marge', 'cost_price', 'calculation_log'):
        assert forbidden not in serialized


@pytest.mark.django_db
def test_submit_configurator_project_without_lots_raises_value_error(company):
    session = ConfiguratorSession.objects.create(company=company)
    with pytest.raises(ValueError):
        engine.submit_configurator_project(company, {
            'session_key': str(session.session_key), 'contact': _contact(), 'building': {},
        })


# ─── Moteur de formules (V2 §19-20) ────────────────────────────────────────────

def test_evaluate_formula_combines_two_answers():
    assert evaluate_formula('nb_points * longueur', {'nb_points': 8, 'longueur': 5}) == 40


def test_evaluate_formula_supports_addition_and_constants():
    assert evaluate_formula('2 + nb_prises * 0.25', {'nb_prises': 4}) == 3


def test_evaluate_formula_missing_variable_defaults_to_zero():
    assert evaluate_formula('nb_points * longueur', {'nb_points': 8}) == 0


def test_evaluate_formula_rejects_unsafe_expressions_without_crashing():
    # Pas de eval() arbitraire : ni les attributs/appels, ni le code fantaisiste
    # ne doivent planter — ils retombent silencieusement sur 0.
    assert evaluate_formula('__import__("os").system("echo hi")', {}) == 0
    assert evaluate_formula('nb.__class__', {'nb': 3}) == 0
    assert evaluate_formula('', {}) == 0
    assert evaluate_formula(None, {}) == 0


@pytest.mark.django_db
def test_material_requirement_formula_quantity_source(company, domain_reseau, price_rj45, labor_travel_margin):
    service = ServiceCategory.objects.create(
        domain=domain_reseau, company=company, code='rj45-formule', name='RJ45 avec formule',
        duration_min_hours=1, duration_avg_hours=1, duration_max_hours=1,
    )
    q_points = ConfiguratorQuestion.objects.create(service=service, identifier='nb_points', label='Points', question_type='number', order=1)
    ConfiguratorQuestion.objects.create(service=service, identifier='longueur', label='Longueur moyenne', question_type='number', order=2)
    MaterialRequirement.objects.create(
        service=service, price_item=price_rj45, quantity_source='formula',
        quantity_formula='nb_points * longueur',
    )
    estimate = compute_estimate(company, service, {'nb_points': 4, 'longueur': 3})
    assert estimate['material_lines'][0]['qty'] == 12


@pytest.mark.django_db
def test_service_duration_formula_overrides_static_duration_but_keeps_ratio(company, domain_electricite, labor_travel_margin):
    service = ServiceCategory.objects.create(
        domain=domain_electricite, company=company, code='formule-duree', name='Service formule durée',
        duration_min_hours=1, duration_avg_hours=2, duration_max_hours=3,
        duration_formula='2 + nb_prises * 0.5',
    )
    ConfiguratorQuestion.objects.create(service=service, identifier='nb_prises', label='Nb', question_type='number', order=1)

    small = compute_estimate(company, service, {'nb_prises': 0})
    large = compute_estimate(company, service, {'nb_prises': 8})
    assert small['duration']['avg'] == pytest.approx(2.0)
    assert large['duration']['avg'] == pytest.approx(6.0)
    # Le ratio min/max (1/2 et 3/2 dans la config statique) doit être conservé.
    assert large['duration']['min'] == pytest.approx(6.0 * 0.5, rel=0.02)
    assert large['duration']['max'] == pytest.approx(6.0 * 1.5, rel=0.02)


# ─── CRM ────────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_crm_deduplicates_customer_and_prospect_by_email(company, service_pose_prise):
    email = 'dedup@example.com'
    qr1, _ = engine.submit_configurator_request(company, {
        'service_code': 'pose-prise', 'answers': {'nb_prises': 1}, 'contact': _contact(email), 'building': {},
    })
    qr2, _ = engine.submit_configurator_request(company, {
        'service_code': 'pose-prise', 'answers': {'nb_prises': 1}, 'contact': _contact(email), 'building': {},
    })
    assert qr1.crm_customer_id == qr2.crm_customer_id
    assert Customer.objects.filter(company=company, email__iexact=email).count() == 1
    assert Prospect.objects.filter(company=company, email__iexact=email).count() == 1


# ─── Sécurité / isolation ────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_service_lookup_never_crosses_company_boundary(company, company_b, service_pose_prise):
    # service_pose_prise appartient à `company` ; company_b ne doit jamais le voir.
    assert engine.get_service(company, 'pose-prise') is not None
    assert engine.get_service(company_b, 'pose-prise') is None


@pytest.mark.django_db
def test_domain_manager_for_company_excludes_other_companies(company, company_b, domain_electricite):
    ServiceDomain.objects.create(company=company_b, code='electricite', name='Électricité (autre entreprise)')
    domains_for_a = list(ServiceDomain.objects.for_company(company))
    assert all(d.company_id == company.id for d in domains_for_a)
    assert domain_electricite in domains_for_a


@pytest.mark.django_db
def test_public_estimate_never_exposes_margin_or_cost(company, service_pose_prise):
    public = engine.estimate_preview(company, 'pose-prise', {'nb_prises': 2})
    serialized = json.dumps(public).lower()
    for forbidden in ('margin', 'marge', 'cost_price', 'coût de revient', 'cost_avg'):
        assert forbidden not in serialized


@pytest.mark.django_db
def test_full_submission_response_never_exposes_margin_or_hypotheses(company, service_disjoncteur):
    _, public = engine.submit_configurator_request(company, {
        'service_code': 'depannage-disjoncteur', 'answers': {'danger_signes': False},
        'contact': _contact('nodup@example.com'), 'building': {},
    })
    serialized = json.dumps(public).lower()
    for forbidden in ('margin', 'marge', 'cost_price', 'hypothes'):
        assert forbidden not in serialized


@pytest.mark.django_db
def test_invalid_service_code_raises_value_error(company):
    with pytest.raises(ValueError):
        engine.submit_configurator_request(company, {
            'service_code': 'ne-existe-pas', 'answers': {}, 'contact': _contact(), 'building': {},
        })


@pytest.mark.django_db
def test_missing_contact_fields_raise_value_error(company, service_pose_prise):
    with pytest.raises(ValueError):
        engine.submit_configurator_request(company, {
            'service_code': 'pose-prise', 'answers': {'nb_prises': 1},
            'contact': {'first_name': 'Jean'}, 'building': {},
        })


# ─── API publique (HTTP) ─────────────────────────────────────────────────────────

@pytest.fixture
def neostructura_company(db):
    """L'API publique du configurateur est câblée sur le slug 'neostructura'
    (choix explicite de l'utilisateur — pas de généralisation multi-site)."""
    from apps.core.models import Company
    # Un signal post_save (apps.core.signals) crée déjà CompanySettings
    # automatiquement à la création — pas besoin de le faire ici.
    return Company.objects.create(name='NÉOSTRUCTURA test', slug='neostructura', status='active', is_active=True)


@pytest.mark.django_db
def test_public_api_domains_endpoint(neostructura_company):
    ServiceDomain.objects.create(company=neostructura_company, code='electricite', name='Électricité', order=1)
    resp = Client().get('/api/v1/neostructura/configurateur/domaines/')
    assert resp.status_code == 200
    assert resp.json()['domains'][0]['code'] == 'electricite'


@pytest.mark.django_db
def test_public_api_rate_limits_estimate_endpoint(neostructura_company):
    domain = ServiceDomain.objects.create(company=neostructura_company, code='electricite', name='Électricité')
    ServiceCategory.objects.create(
        domain=domain, company=neostructura_company, code='svc', name='Service',
        duration_min_hours=1, duration_avg_hours=1, duration_max_hours=1,
    )
    client = Client()
    responses = [
        client.post('/api/v1/neostructura/configurateur/estimer/',
                     data=json.dumps({'service_code': 'svc', 'answers': {}}), content_type='application/json')
        for _ in range(65)
    ]
    assert any(r.status_code == 429 for r in responses), 'la limite de 60/h doit finir par se déclencher'


@pytest.mark.django_db
def test_public_api_rejects_oversized_answers_payload(neostructura_company):
    domain = ServiceDomain.objects.create(company=neostructura_company, code='electricite', name='Électricité')
    ServiceCategory.objects.create(
        domain=domain, company=neostructura_company, code='svc2', name='Service 2',
        duration_min_hours=1, duration_avg_hours=1, duration_max_hours=1,
    )
    huge_answers = {f'key_{i}': 'x' * 5000 for i in range(200)}
    resp = Client().post(
        '/api/v1/neostructura/configurateur/estimer/',
        data=json.dumps({'service_code': 'svc2', 'answers': huge_answers}), content_type='application/json',
    )
    # Ne doit jamais planter (500) — troncature silencieuse côté _sanitize_answers.
    assert resp.status_code == 200


@pytest.mark.django_db
def test_public_api_session_start_update_resume_roundtrip(neostructura_company):
    domain = ServiceDomain.objects.create(company=neostructura_company, code='electricite', name='Électricité')
    ServiceCategory.objects.create(
        domain=domain, company=neostructura_company, code='svc4', name='Service 4',
        duration_min_hours=1, duration_avg_hours=1, duration_max_hours=1,
    )
    client = Client()

    started = client.post('/api/v1/neostructura/configurateur/session/', data='{}', content_type='application/json')
    assert started.status_code == 200
    session_key = started.json()['session_key']

    updated = client.post(
        f'/api/v1/neostructura/configurateur/session/{session_key}/',
        data=json.dumps({'domain_code': 'electricite', 'service_code': 'svc4', 'answers': {'foo': 'bar'}}),
        content_type='application/json',
    )
    assert updated.status_code == 200
    assert updated.json()['answers'] == {'foo': 'bar'}
    assert updated.json()['service_code'] == 'svc4'

    resumed = client.get(f'/api/v1/neostructura/configurateur/session/{session_key}/')
    assert resumed.status_code == 200
    assert resumed.json()['answers'] == {'foo': 'bar'}
    assert resumed.json()['estimate'] is not None


@pytest.mark.django_db
def test_public_api_session_lots_add_update_remove_roundtrip(neostructura_company):
    domain = ServiceDomain.objects.create(company=neostructura_company, code='electricite', name='Électricité')
    ServiceCategory.objects.create(
        domain=domain, company=neostructura_company, code='svc5', name='Service 5',
        duration_min_hours=1, duration_avg_hours=1, duration_max_hours=1,
    )
    client = Client()
    session_key = client.post('/api/v1/neostructura/configurateur/session/', data='{}', content_type='application/json').json()['session_key']

    added = client.post(
        f'/api/v1/neostructura/configurateur/session/{session_key}/lots/',
        data=json.dumps({'domain_code': 'electricite', 'service_code': 'svc5', 'answers': {'a': 1}, 'label': 'Besoin 1'}),
        content_type='application/json',
    )
    assert added.status_code == 201
    lot_id = added.json()['lots'][0]['id']
    assert added.json()['lots'][0]['label'] == 'Besoin 1'

    updated = client.post(
        f'/api/v1/neostructura/configurateur/session/{session_key}/lots/{lot_id}/',
        data=json.dumps({'answers': {'b': 2}}), content_type='application/json',
    )
    assert updated.status_code == 200
    assert updated.json()['lots'][0]['answers'] == {'a': 1, 'b': 2}

    removed = client.delete(f'/api/v1/neostructura/configurateur/session/{session_key}/lots/{lot_id}/')
    assert removed.status_code == 200
    assert removed.json()['lots'] == []


@pytest.mark.django_db
def test_public_api_submit_project_endpoint(neostructura_company):
    domain = ServiceDomain.objects.create(company=neostructura_company, code='electricite', name='Électricité')
    ServiceCategory.objects.create(
        domain=domain, company=neostructura_company, code='svc6', name='Service 6',
        duration_min_hours=1, duration_avg_hours=1, duration_max_hours=1,
    )
    client = Client()
    session_key = client.post('/api/v1/neostructura/configurateur/session/', data='{}', content_type='application/json').json()['session_key']
    client.post(
        f'/api/v1/neostructura/configurateur/session/{session_key}/lots/',
        data=json.dumps({'domain_code': 'electricite', 'service_code': 'svc6', 'answers': {}}),
        content_type='application/json',
    )
    resp = client.post(
        '/api/v1/neostructura/configurateur/soumettre-projet/',
        data=json.dumps({
            'session_key': session_key,
            'contact': {'first_name': 'Jean', 'last_name': 'Test', 'email': 'proj@example.com'},
            'building': {},
        }),
        content_type='application/json',
    )
    assert resp.status_code == 200
    assert len(resp.json()['references']) == 1


@pytest.mark.django_db
def test_public_api_session_detail_unknown_key_returns_404(neostructura_company):
    resp = Client().get('/api/v1/neostructura/configurateur/session/00000000-0000-0000-0000-000000000000/')
    assert resp.status_code == 404


@pytest.mark.django_db
def test_photo_upload_rejects_non_image_file(neostructura_company):
    from io import BytesIO
    domain = ServiceDomain.objects.create(company=neostructura_company, code='electricite', name='Électricité')
    service = ServiceCategory.objects.create(
        domain=domain, company=neostructura_company, code='svc3', name='Service 3',
        duration_min_hours=1, duration_avg_hours=1, duration_max_hours=1,
    )
    qr = GuidedQuoteRequest.objects.create(
        company=neostructura_company, request_type='depannage',
        client_first_name='A', client_last_name='B', client_email='a@b.com',
    )
    fake_exe = BytesIO(b'not-an-image')
    fake_exe.name = 'malware.exe'
    resp = Client().post(f'/api/v1/neostructura/configurateur/{qr.reference}/photos/', {'photos': fake_exe})
    assert resp.status_code == 400
