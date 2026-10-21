"""
apps/hr/forms_planning.py — Formulaires du planning

**Une règle, appliquée partout ici : toute liste déroulante est bornée à
l'entreprise dans `__init__`**, donc à la VALIDATION et pas seulement à
l'affichage.

La nuance n'est pas théorique. Le code existant de ce module bornait
`employee` dans la seule branche GET de la vue :

    form = LeaveRequestForm()
    form.fields['employee'].queryset = Employee.objects.filter(company=...)

Au POST, le formulaire était reconstruit sans ce filtre. Un identifiant de
salarié recopié depuis une autre entreprise passait donc la validation, et
le congé était enregistré sous l'entreprise courante en désignant le salarié
d'une autre. Borner dans `__init__` rend cette fuite impossible, parce qu'il
n'existe plus de chemin où le filtre soit absent.
"""

from django import forms

from .models import JOURS_SEMAINE, Employee, WorkSchedule, WorkStoppage

CLASSE_NOMBRE = {'class': 'form-control', 'step': '0.25', 'min': '0',
                 'max': '24'}


class WorkScheduleForm(forms.ModelForm):
    """Rythme hebdomadaire d'un salarié."""

    class Meta:
        model = WorkSchedule
        fields = ['employee'] + [f'hours_{cle}' for cle, _ in JOURS_SEMAINE] \
            + ['notes']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control',
                                           'rows': 2}),
            **{f'hours_{cle}': forms.NumberInput(attrs=dict(CLASSE_NOMBRE))
               for cle, _ in JOURS_SEMAINE},
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        if self.instance.pk:
            # Le salarié d'un rythme existant ne se change pas : ce serait
            # déplacer un historique d'un salarié à l'autre. Le champ est
            # désactivé — Django ignore alors la valeur soumise et reprend
            # l'initiale, donc même un POST forgé ne le déplace pas. La
            # liste se réduit au salarié concerné, juste pour l'affichage.
            self.fields['employee'].disabled = True
            self.fields['employee'].queryset = Employee.objects.filter(
                pk=self.instance.employee_id)
        elif company is not None:
            # Un rythme par salarié (OneToOne) : proposer un salarié qui en
            # a déjà un mènerait à une erreur d'unicité incompréhensible au
            # moment d'enregistrer, là où il faut l'écarter de la liste.
            self.fields['employee'].queryset = Employee.objects.filter(
                company=company, is_active=True, work_schedule__isnull=True
            ).order_by('last_name', 'first_name')

    def clean(self):
        donnees = super().clean()
        heures = [donnees.get(f'hours_{cle}') or 0 for cle, _ in JOURS_SEMAINE]
        if all(valeur == 0 for valeur in heures):
            raise forms.ValidationError(
                'Un rythme entièrement à zéro signifie que le salarié ne '
                'travaille jamais. Si le contrat est suspendu, désactivez '
                'la fiche salarié plutôt que de vider le rythme — sinon le '
                'planning le montre présent et disponible toute l\'année.')
        return donnees


class WorkStoppageForm(forms.ModelForm):
    """Arrêt de travail. Déclaré, pas demandé — il n'y a rien à approuver."""

    class Meta:
        model = WorkStoppage
        fields = ['employee', 'kind', 'start_date', 'end_date',
                  'certificate_date', 'certificate_reference',
                  'prolongation_de', 'notes']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'kind': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control',
                                                 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control',
                                               'type': 'date'}),
            'certificate_date': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'}),
            'certificate_reference': forms.TextInput(
                attrs={'class': 'form-control'}),
            'prolongation_de': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control',
                                           'rows': 3}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        if company is not None:
            self.fields['employee'].queryset = Employee.objects.filter(
                company=company, is_active=True).order_by('last_name',
                                                          'first_name')
            # Borné à l'entreprise ET à l'arrêt courant exclu : un arrêt qui
            # se prolongerait lui-même formerait un cycle, et le parcours
            # des prolongations ne finirait jamais.
            prolongeables = WorkStoppage.objects.filter(company=company)
            if self.instance.pk:
                prolongeables = prolongeables.exclude(pk=self.instance.pk)
            self.fields['prolongation_de'].queryset = prolongeables.order_by(
                '-start_date')

        self.fields['end_date'].required = False
        self.fields['prolongation_de'].required = False
        self.fields['prolongation_de'].empty_label = '— Arrêt initial —'

    def clean(self):
        donnees = super().clean()
        # Les contrôles de cohérence vivent dans WorkStoppage.clean() pour
        # valoir aussi hors formulaire (import, commande, shell). Le
        # ModelForm les déclenche déjà via _post_clean ; on ne les redit pas
        # ici, deux copies divergeraient.
        return donnees
