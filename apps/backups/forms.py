"""
apps/backups/forms.py — Formulaires sauvegardes
"""
from django import forms
from .models import BackupJob, BackupSchedule, BackupDestination


class BackupDestinationForm(forms.ModelForm):
    smb_password = forms.CharField(
        label='Mot de passe', required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
        help_text='Laisser vide pour conserver le mot de passe déjà enregistré.',
    )

    class Meta:
        model = BackupDestination
        fields = [
            'name', 'destination_type', 'local_path',
            'smb_server', 'smb_share', 'smb_path', 'smb_username', 'smb_domain',
            'is_active', 'is_default',
        ]
        widgets = {
            'name':             forms.TextInput(attrs={'class': 'form-control'}),
            'destination_type': forms.Select(attrs={'class': 'form-select'}),
            'local_path':       forms.TextInput(attrs={'class': 'form-control', 'placeholder': r'E:\Sauvegardes'}),
            'smb_server':       forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'nas.local ou 192.168.1.10'}),
            'smb_share':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'sauvegardes'}),
            'smb_path':         forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'orion (optionnel)'}),
            'smb_username':     forms.TextInput(attrs={'class': 'form-control'}),
            'smb_domain':       forms.TextInput(attrs={'class': 'form-control'}),
            'is_active':        forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_default':       forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned = super().clean()
        dtype = cleaned.get('destination_type')
        if dtype == 'local' and not cleaned.get('local_path'):
            self.add_error('local_path', 'Chemin requis pour une destination locale.')
        if dtype == 'smb' and not (cleaned.get('smb_server') and cleaned.get('smb_share')):
            self.add_error('smb_server', 'Serveur et partage requis pour une destination SMB.')
        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        password = self.cleaned_data.get('smb_password')
        if password:
            instance.smb_password = password
        if commit:
            instance.save()
        return instance


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


class BackupImportForm(forms.Form):
    file = forms.FileField(
        label='Fichier d\'export (.zip)',
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.zip'}),
    )
    confirm_text = forms.CharField(
        label='Tapez IMPORTER pour confirmer',
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
    )

    def clean_confirm_text(self):
        value = self.cleaned_data['confirm_text']
        if value.strip().upper() != 'IMPORTER':
            raise forms.ValidationError('Tapez exactement IMPORTER pour confirmer.')
        return value

    def clean_file(self):
        f = self.cleaned_data['file']
        if not f.name.lower().endswith('.zip'):
            raise forms.ValidationError('Le fichier doit être une archive .zip (export Orion ERP).')
        return f
