"""
apps/configurator/services/diagnostic.py — Questions visibles + évaluation
du pré-diagnostic. Ne prétend jamais connaître la panne : construit des
hypothèses avec un niveau de confiance, jamais un diagnostic affirmé.
"""
from .conditions import condition_met


def get_visible_questions(service, answers):
    """Questions dont la condition d'affichage est satisfaite par les
    réponses déjà données — c'est ce qui rend le parcours adaptatif."""
    questions = service.questions.all().prefetch_related('options')
    return [q for q in questions if condition_met(q.display_condition, answers)]


def _detect_danger(service, answers):
    scenario = getattr(service, 'diagnostic_scenario', None)
    if not scenario:
        return False

    # Questions booléennes taguées impacts_diagnostic répondues "oui"
    for q in service.questions.filter(impacts_diagnostic=True, question_type='boolean'):
        if answers.get(q.identifier) in (True, 'true', 'True', 'on', '1', 1):
            return True

    # Mots-clés de danger dans les réponses texte libres
    keywords = [k.lower() for k in (scenario.danger_keywords or [])]
    if keywords:
        for value in answers.values():
            if isinstance(value, str) and any(k in value.lower() for k in keywords):
                return True
    return False


def evaluate_diagnostic(service, answers):
    """Retourne un dict {requires_diagnostic, confidence_level, hypotheses,
    danger_detected, diagnostic_duration} — jamais un prix, jamais une
    affirmation de panne confirmée."""
    if not service.requires_diagnostic:
        return {
            'requires_diagnostic': False,
            'confidence_level': service.confidence_level,
            'hypotheses': [],
            'danger_detected': False,
            'diagnostic_duration': None,
        }

    danger_detected = _detect_danger(service, answers)
    scenario = getattr(service, 'diagnostic_scenario', None)
    hypotheses = scenario.hypotheses if scenario else []
    duration = None
    if scenario:
        duration = {
            'min': float(scenario.diagnostic_min_hours),
            'avg': float(scenario.diagnostic_avg_hours),
            'max': float(scenario.diagnostic_max_hours),
        }

    return {
        'requires_diagnostic': True,
        # Un danger détecté ne peut jamais faire remonter la confiance —
        # au contraire, il force le niveau le plus prudent.
        'confidence_level': 'diagnostic_required' if danger_detected else service.confidence_level,
        'hypotheses': hypotheses,
        'danger_detected': danger_detected,
        'diagnostic_duration': duration,
        'safety_message': scenario.safety_message if (danger_detected and scenario) else '',
    }
