"""apps/core/form_widgets.py — Les widgets de saisie communs.

POURQUOI « DateISO » EXISTE

Un « <input type="date"> » n'accepte sa valeur initiale qu'au format ISO,
« AAAA-MM-JJ ». C'est la norme HTML, et le navigateur n'est pas tolérant :
toute autre écriture est rejetée, et le champ s'affiche VIDE.

Or Django rend les dates au format de la langue active. En français, cela
donne « 14/11/2026 » :

    <input type="date" name="purchase_date" value="14/11/2026" required>

Le navigateur refuse cette valeur, le champ paraît vide, et comme il est
souvent obligatoire, l'enregistrement échoue. L'utilisateur voit alors un
formulaire qui « ne marche pas » et le ramène à la même page — sans
comprendre qu'il manque une date qui semblait pourtant déjà remplie.

Le défaut touchait les CINQUANTE-CINQ champs date de l'ERP, dans douze
fichiers : aucun ne précisait son format. Il ne se voit pas sur un champ
vide (création sans valeur initiale), ce qui explique qu'il ait survécu —
il n'apparaît qu'en modification, ou quand le modèle fournit un défaut,
comme « purchase_date = timezone.now ».

CE QUE CE WIDGET GARANTIT

Le rendu est toujours ISO, et « type=date » est posé d'office : on ne peut
plus l'oublier. La LECTURE de la valeur soumise, elle, reste assurée par
DATE_INPUT_FORMATS, qui accepte l'ISO dans toutes les langues livrées par
Django.
"""

from django import forms


class DateISO(forms.DateInput):
    """Un champ date dont la valeur initiale est écrite au format ISO."""

    def __init__(self, attrs=None, format=None):
        # « type » est force ici plutot que laisse a chaque appelant : c'est
        # precisement l'attribut dont l'oubli rendait le widget inoffensif
        # en apparence. Un appelant peut toujours le surcharger s'il sait
        # ce qu'il fait.
        attributs = {'type': 'date'}
        attributs.update(attrs or {})
        super().__init__(attrs=attributs, format=format or '%Y-%m-%d')


class DateTimeISO(forms.DateTimeInput):
    """Même chose pour « <input type="datetime-local"> ».

    Le format attendu y est « AAAA-MM-JJTHH:MM », sans fuseau ni secondes.
    """

    def __init__(self, attrs=None, format=None):
        attributs = {'type': 'datetime-local'}
        attributs.update(attrs or {})
        super().__init__(attrs=attributs, format=format or '%Y-%m-%dT%H:%M')
