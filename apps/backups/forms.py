"""
apps/backups/forms.py — Formulaires sauvegardes
"""
from django import forms
from .models import BackupJob, BackupSchedule


class BackupCreateForm(forms.Form):
    scope = forms.ChoiceField(
        label='Périmètre',
        choices=BackupJob.SCOPE_CHOICES,
        initial='company_database',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    company = forms.ChoiceField(
        label='Entreprise',
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, companies=None, **kwargs):
        super().__init__(*args, **kwargs)
        if companies:
            choices = [('', '— Base centrale —')] + [(c.pk, c.name) for c in companies]
            self.fields['company'].choices = choices


class BackupScheduleForm(forms.ModelForm):
    class Meta:
        model = BackupSchedule
        fields = ['name', 'scope', 'frequency', 'time', 'day_of_week', 'retention_days', 'is_active']
        widgets = {
            'name':          forms.TextInput(attrs={'class': 'form-control'}),
            'scope':         forms.Select(attrs={'class': 'form-select'}),
            'frequency':     forms.Select(attrs={'class': 'form-select'}),
            'time':          forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'day_of_week':   forms.Select(attrs={'class': 'form-select'}),
            'retention_days': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'is_active':     forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class RestoreConfirmForm(forms.Form):
    confirm = forms.BooleanField(
        label='Je confirme vouloir restaurer cette sauvegarde. Une sauvegarde pré-restauration sera créée automatiquement.',
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
