"""
apps/configurator/services/confidence.py — Score de confiance interne (0-100)
et nécessité de visite tri-état (§32-§33 du cahier des charges V2).

Complète `confidence_level` (grossier, garde son rôle historique dans
pricing.py pour la largeur de fourchette) par un score continu et ses
facteurs. Le score n'est JAMAIS exposé au client (§56 : "scoring interne"
est strictement interne) — seule `visit_necessity` (qualitatif) l'est.

`DONT_KNOW` est la valeur sentinelle envoyée par le frontend quand le
client répond "Je ne sais pas" (§10) : elle compte comme "répondu" pour ne
pas bloquer le parcours, mais réduit le score de confiance et alimente la
liste `missing_info` du dossier technicien.
"""
DONT_KNOW = '__dont_know__'

BASE_SCORE_BY_LEVEL = {'high': 90, 'medium': 70, 'low': 45, 'diagnostic_required': 25}


def compute_confidence_score(service, answers, photos_count=0, danger_detected=False):
    score = BASE_SCORE_BY_LEVEL.get(service.confidence_level, 60)

    required = [q for q in service.questions.all() if q.is_required]
    if required:
        answered = sum(1 for q in required if answers.get(q.identifier) not in (None, '', DONT_KNOW))
        dont_know = sum(1 for q in required if answers.get(q.identifier) == DONT_KNOW)
        completeness = answered / len(required)
        score += round((completeness - 1) * 20)
        score -= dont_know * 8

    if photos_count > 0:
        score += 8
    if answers.get('surface') or answers.get('distance'):
        score += 4

    if danger_detected:
        score = min(score, 35)
    if service.requires_diagnostic:
        score = min(score, 65)

    return max(0, min(100, round(score)))


def compute_visit_necessity(service, confidence_score, danger_detected):
    if danger_detected:
        return 'obligatoire'
    if service.requires_diagnostic:
        return 'obligatoire' if confidence_score < 50 else 'recommandee'
    if confidence_score < 60:
        return 'recommandee'
    return 'non_necessaire'


def missing_info_from_answers(service, answers):
    """Identifiants des questions obligatoires répondues "je ne sais pas" —
    alimente le dossier technicien (§34/§38 « Questions non résolues »)."""
    return [
        q.identifier for q in service.questions.filter(is_required=True)
        if answers.get(q.identifier) == DONT_KNOW
    ]
