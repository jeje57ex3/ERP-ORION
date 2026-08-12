from django import forms

from apps.domain_diagnostics.models import CloudflareZoneConfig, DomainDiagnosticTarget


class CloudflareZoneConfigForm(forms.ModelForm):
    class Meta:
        model = CloudflareZoneConfig
        fields = ['zone_name', 'zone_id', 'api_token_hint', 'is_active']
        widgets = {
            'zone_name':      forms.TextInput(attrs={'class': 'orion-input', 'placeholder': 'elysiums.fr'}),
            'zone_id':        forms.TextInput(attrs={'class': 'orion-input', 'placeholder': 'ID rempli automatiquement'}),
            'api_token_hint': forms.TextInput(attrs={'class': 'orion-input', 'placeholder': 'Token se terminant par …abcd (indice seulement)'}),
            'is_active':      forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class DomainDiagnosticTargetForm(forms.ModelForm):
    class Meta:
        model = DomainDiagnosticTarget
        fields = [
            'website', 'cloudflare_zone', 'domain', 'brand_key', 'target_type',
            'expected_origin_ip', 'expected_record_type', 'expected_record_content',
            'expected_proxy', 'expected_ssl_mode', 'expected_https_status',
            'is_active', 'auto_repair_enabled',
        ]
        widgets = {
            'website':                  forms.Select(attrs={'class': 'orion-select'}),
            'cloudflare_zone':          forms.Select(attrs={'class': 'orion-select'}),
            'domain':                   forms.TextInput(attrs={'class': 'orion-input', 'placeholder': 'siecle.elysiums.fr'}),
            'brand_key':                forms.TextInput(attrs={'class': 'orion-input', 'placeholder': 'siecle'}),
            'target_type':              forms.Select(attrs={'class': 'orion-select'}),
            'expected_origin_ip':       forms.TextInput(attrs={'class': 'orion-input', 'placeholder': '1.2.3.4'}),
            'expected_record_type':     forms.TextInput(attrs={'class': 'orion-input', 'placeholder': 'A'}),
            'expected_record_content':  forms.TextInput(attrs={'class': 'orion-input', 'placeholder': '1.2.3.4 ou target.cname.com'}),
            'expected_proxy':           forms.Select(attrs={'class': 'orion-select'}),
            'expected_ssl_mode':        forms.TextInput(attrs={'class': 'orion-input', 'placeholder': 'strict'}),
            'expected_https_status':    forms.NumberInput(attrs={'class': 'orion-input'}),
            'is_active':                forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'auto_repair_enabled':      forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
