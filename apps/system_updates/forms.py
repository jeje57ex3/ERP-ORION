from django import forms

from apps.system_updates.models import SystemUpdateSettings


class SystemUpdateSettingsForm(forms.ModelForm):
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
