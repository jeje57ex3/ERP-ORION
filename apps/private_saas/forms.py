"""
apps/private_saas/forms.py — Formulaires SaaS privé
"""
from django import forms


COMPANY_TYPE_CHOICES = [
    ('generic',    'Générique'),
    ('btp',        'BTP / Construction'),
    ('fashion',    'Mode / Textile'),
    ('beauty',     'Beauté / Cosmétique'),
    ('watch',      'Horlogerie / Luxe'),
    ('ecommerce',  'E-commerce'),
    ('commerce',   'Commerce / Point de vente'),
    ('audio',      'Audio / Audiovisuel'),
    ('production', 'Production / Fabrication'),
]


class CompanyCreateForm(forms.Form):
    name = forms.CharField(
        label='Nom de l\'entreprise',
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : SIÈCLE, BTP Dupont…'}),
    )
    legal_name = forms.CharField(
        label='Raison sociale',
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optionnel'}),
    )
    company_type = forms.ChoiceField(
        label='Type d\'activité',
        choices=COMPANY_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    admin_email = forms.EmailField(
        label='Email administrateur',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'admin@monentreprise.fr'}),
    )
    admin_password = forms.CharField(
        label='Mot de passe (laisser vide = auto-généré)',
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
    )
    currency = forms.ChoiceField(
        label='Devise',
        choices=[('EUR', 'Euro (€)'), ('USD', 'Dollar ($)'), ('GBP', 'Livre (£)'), ('CHF', 'Franc suisse (CHF)')],
        initial='EUR',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    timezone = forms.ChoiceField(
        label='Fuseau horaire',
        choices=[
            ('Europe/Paris', 'Europe/Paris'),
            ('Europe/London', 'Europe/London'),
            ('America/New_York', 'America/New_York'),
            ('America/Chicago', 'America/Chicago'),
        ],
        initial='Europe/Paris',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )


class CompanyModuleForm(forms.Form):
    """Formulaire de gestion des modules d'une entreprise."""

    def __init__(self, company, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .models import CompanyModule, MODULE_LABELS, ALL_MODULE_CODES
        for code in ALL_MODULE_CODES:
            try:
                mod = CompanyModule.objects.get(company=company, module_code=code)
                initial = mod.is_enabled
            except CompanyModule.DoesNotExist:
                initial = False
            self.fields[f'module_{code}'] = forms.BooleanField(
                label=MODULE_LABELS.get(code, code),
                required=False,
                initial=initial,
                widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            )


class PrivateSaaSSettingsForm(forms.Form):
    private_mode_enabled = forms.BooleanField(
        label='Mode privé activé', required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    public_signup_enabled = forms.BooleanField(
        label='Inscription publique autorisée', required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    allow_domain_management = forms.BooleanField(
        label='Gestion des domaines autorisée', required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    allow_module_management = forms.BooleanField(
        label='Gestion des modules autorisée', required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    maintenance_mode = forms.BooleanField(
        label='Mode maintenance global', required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
