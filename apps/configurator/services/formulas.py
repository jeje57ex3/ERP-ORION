"""
apps/configurator/services/formulas.py — Moteur de formules générique
(§19-20 du cahier des charges V2).

Permet d'exprimer une quantité de matériel ou une durée comme une
combinaison arithmétique des réponses plutôt qu'une simple quantité fixe
ou un facteur unique appliqué à une seule réponse — ex. :
    cable = nb_prises * longueur_moyenne
    temps = 2 + nb_prises * 0.25

Évaluation restreinte via `ast` : uniquement +, -, *, /, parenthèses,
nombres et identifiants (résolus depuis `answers`, 0 si absent ou non
numérique) — jamais un `eval()` sur du code arbitraire. Une formule mal
écrite ne doit jamais faire planter un chiffrage : elle retombe sur 0
plutôt que de lever une exception vers l'appelant.
"""
import ast
import operator

_ALLOWED_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
}
_ALLOWED_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


class FormulaError(ValueError):
    pass


def _to_number(value):
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _eval_node(node, variables):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, variables)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return float(node.value)
        raise FormulaError('Constante non numérique interdite dans une formule.')
    if isinstance(node, ast.Name):
        return _to_number(variables.get(node.id))
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        left = _eval_node(node.left, variables)
        right = _eval_node(node.right, variables)
        if isinstance(node.op, ast.Div) and right == 0:
            return 0.0
        return _ALLOWED_BINOPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return _ALLOWED_UNARYOPS[type(node.op)](_eval_node(node.operand, variables))
    raise FormulaError('Expression non autorisée dans une formule.')


def evaluate_formula(expression, answers):
    """Évalue une formule arithmétique simple référençant des identifiants
    de question. Ne lève jamais d'exception : une formule vide, invalide ou
    dont une variable est absente/non numérique renvoie 0.0 plutôt que de
    bloquer un chiffrage sur une erreur de configuration admin."""
    if not expression or not str(expression).strip():
        return 0.0
    try:
        tree = ast.parse(expression, mode='eval')
        return _eval_node(tree, answers or {})
    except (FormulaError, SyntaxError, TypeError, ZeroDivisionError, RecursionError):
        return 0.0
