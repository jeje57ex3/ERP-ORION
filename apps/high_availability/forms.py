from django import forms
from apps.high_availability.models import OrionHASettings, OrionHANode


class OrionHASettingsForm(forms.ModelForm):
    class Meta:
        model = OrionHASettings
        fields = [
            'failover_enabled',
            'automatic_failover_enabled',
            'require_manual_confirmation',
            'failover_after_seconds',
            'max_allowed_replication_lag_seconds',
            'minimum_healthy_secondaries',
            'preferred_secondary_node',
            'allow_failover_to_secondary_2',
            'media_sync_enabled',
            'database_replication_check_enabled',
            'cloudflare_failover_enabled',
            'cloudflare_zone_id',
            'cloudflare_dns_record_id',
            'cloudflare_record_name',
            'notify_admins',
            'notify_email',
            'split_brain_protection_enabled',
            'maintenance_mode_enabled',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['preferred_secondary_node'].queryset = OrionHANode.objects.filter(
            role='secondary',
            is_enabled=True,
        ).order_by('priority')

    def clean(self):
        cleaned_data = super().clean()
        automatic = cleaned_data.get('automatic_failover_enabled')
        manual_confirmation = cleaned_data.get('require_manual_confirmation')
        failover_after = cleaned_data.get('failover_after_seconds')
        max_lag = cleaned_data.get('max_allowed_replication_lag_seconds')

        if automatic and manual_confirmation:
            raise forms.ValidationError(
                'Le failover automatique ne peut pas être activé si la confirmation manuelle est obligatoire.'
            )
        if failover_after and failover_after < 60:
            raise forms.ValidationError(
                'Le délai de failover doit être au minimum de 60 secondes.'
            )
        if max_lag is not None and max_lag > 300:
            raise forms.ValidationError(
                'Le retard de réplication maximum ne doit pas dépasser 300 secondes.'
            )
        return cleaned_data


class OrionHANodeForm(forms.ModelForm):
    class Meta:
        model = OrionHANode
        fields = [
            'node_id',
            'name',
            'role',
            'status',
            'base_url',
            'public_ip',
            'private_ip',
            'region',
            'priority',
            'is_enabled',
            'is_current_active',
            'is_failover_target',
            'allow_auto_failover',
            'notes',
        ]

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        priority = cleaned_data.get('priority')
        is_current_active = cleaned_data.get('is_current_active')

        if role == 'primary' and priority != 1:
            raise forms.ValidationError('Le serveur principal doit avoir la priorité 1.')
        if role == 'secondary' and priority == 1:
            raise forms.ValidationError('Un serveur secondaire ne peut pas avoir la priorité 1.')

        if is_current_active:
            qs = OrionHANode.objects.filter(is_current_active=True)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError('Un autre serveur est déjà marqué comme actif.')

        return cleaned_data
