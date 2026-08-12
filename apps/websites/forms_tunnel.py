"""
apps/websites/forms_tunnel.py — Formulaires pour la gestion des tunnels Cloudflare
"""
from django import forms
from .models_domains import CloudflareTunnel, TunnelIngressRule, CloudflareAccount


class CloudflareTunnelForm(forms.ModelForm):
    class Meta:
        model = CloudflareTunnel
        fields = ['name', 'tunnel_id', 'cloudflare_account', 'credentials_file', 'config_file', 'is_active', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Tunnel principal Orion'}),
            'tunnel_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'f4aa00aa-1df4-41f9-b676-946933560b2f'}),
            'cloudflare_account': forms.Select(attrs={'class': 'form-select'}),
            'credentials_file': forms.TextInput(attrs={'class': 'form-control', 'placeholder': r'C:\Users\jessy\.cloudflared\<id>.json'}),
            'config_file': forms.TextInput(attrs={'class': 'form-control', 'placeholder': r'C:\Users\jessy\.cloudflared\config.yml'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields['cloudflare_account'].queryset = CloudflareAccount.objects.filter(company=company)
        self.fields['cloudflare_account'].required = False
        self.fields['tunnel_id'].required = False
        self.fields['credentials_file'].required = False
        self.fields['config_file'].required = False
        self.fields['notes'].required = False


class TunnelIngressRuleForm(forms.ModelForm):
    local_port = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=65535,
        label='Port local',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '9000',
            'style': 'max-width:140px',
        }),
        help_text='Raccourci pour un service localhost — renseigner le port suffit.',
    )

    class Meta:
        model = TunnelIngressRule
        fields = ['hostname', 'local_port', 'service', 'order', 'is_active', 'website']
        widgets = {
            'hostname': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'login.elysiums.fr'}),
            'service': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'http://localhost:9000'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'website': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import Website
        if company:
            self.fields['website'].queryset = Website.objects.filter(company=company)
        self.fields['website'].required = False
        self.fields['service'].required = False
        # Pré-remplir local_port si le service existant est un localhost
        if self.instance and self.instance.pk and self.instance.local_port:
            self.fields['local_port'].initial = self.instance.local_port

    def clean_hostname(self):
        value = self.cleaned_data.get('hostname', '').strip().lower()
        for prefix in ('https://', 'http://'):
            if value.startswith(prefix):
                value = value[len(prefix):]
        return value.rstrip('/')

    def clean(self):
        cleaned_data = super().clean()
        local_port = cleaned_data.get('local_port')
        service = (cleaned_data.get('service') or '').strip()
        if local_port:
            cleaned_data['service'] = f'http://localhost:{local_port}'
        elif not service:
            raise forms.ValidationError(
                'Indiquez soit un port local (localhost), soit une URL de service complète.'
            )
        return cleaned_data
