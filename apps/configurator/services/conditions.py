"""
apps/configurator/services/conditions.py — Évaluation des conditions
d'affichage (ConfiguratorQuestion.display_condition,
MaterialRequirement.applies_when). Même format JSON pour les deux.

Formats supportés (vide = toujours vrai) :
    {"question": "<identifier>", "equals": <valeur>}
    {"question": "<identifier>", "in": [<valeurs>]}
    {"question": "<identifier>", "truthy": true}
"""


def condition_met(condition, answers):
    if not condition:
        return True
    identifier = condition.get('question')
    if not identifier:
        return True
    value = answers.get(identifier)

    if 'equals' in condition:
        return str(value) == str(condition['equals'])
    if 'in' in condition:
        allowed = condition['in']
        if isinstance(value, list):
            return any(str(v) in [str(a) for a in allowed] for v in value)
        return str(value) in [str(a) for a in allowed]
    if 'truthy' in condition:
        return bool(value) == bool(condition['truthy'])
    return True
