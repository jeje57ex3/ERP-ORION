from django import forms

from apps.system_updates.models import SystemUpdateSettings
from apps.website_shop_settings.crypto import encrypt_secret


class SystemUpdateSettingsForm(forms.ModelForm):
    github_token = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=False),
        label='Jeton d\'accès GitHub',
        help_text="Requis si le dépôt est privé (scope 'repo' en lecture). "
                   "Laisser vide pour conserver le jeton existant.",
    )

    class Meta:
        model = SystemUpdateSettings
        fields = [
            'update_enabled',
            'manual_only',
            'git_remote',
            'git_branch',
            'require_backup_before_update',
            'require_health_check_before_update',
            'allow_rollback',
            'update_backend_enabled',
            'update_frontend_siecle_enabled',
            'update_frontend_lunea_enabled',
            'run_migrations',
            'collect_static',
            'restart_services',
            'maintenance_mode_during_update',
            'notify_admins',
            'notify_email',
        ]

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get('github_token'):
            instance.github_token_encrypted = encrypt_secret(self.cleaned_data['github_token'])
        if commit:
            instance.save()
        return instance


class ConfirmUpdateForm(forms.Form):
    confirm = forms.BooleanField(
        required=True,
        label='Je confirme vouloir lancer la mise à jour.',
    )
    backup_confirm = forms.BooleanField(
        required=True,
        label='Je confirme qu\'une sauvegarde sera lancée avant la mise à jour.',
    )


class ConfirmRollbackForm(forms.Form):
    confirm = forms.BooleanField(
        required=True,
        label='Je confirme vouloir lancer un rollback.',
    )


class ServerActionConfirmForm(forms.Form):
    confirm_text = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
    )

    def __init__(self, *args, expected_text='', **kwargs):
        self.expected_text = expected_text
        super().__init__(*args, **kwargs)
        self.fields['confirm_text'].label = f'Tapez {expected_text} pour confirmer'

    def clean_confirm_text(self):
        value = self.cleaned_data['confirm_text'].strip().upper()
        if value != self.expected_text:
            raise forms.ValidationError(f'Tapez exactement {self.expected_text} pour confirmer.')
        return value
