"""
apps/websites/forms_domains.py — Formulaires de gestion des domaines Orion ERP
"""
import re
from django import forms
from django.core.exceptions import ValidationError

from .models import WebsiteDomain, Website
from .models_domains import DomainRedirect, CloudflareAccount


# ─── Validation ───────────────────────────────────────────────────────────────

_DOMAIN_RE = re.compile(r'^(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$')
_FORBIDDEN = {'localhost', '127.0.0.1', '0.0.0.0', '::1'}


def clean_domain_input(value: str) -> str:
    """Normalise et valide un nom de domaine saisi par l'utilisateur."""
    value = value.strip().lower()
    for prefix in ('https://', 'http://', 'www.'):
        if value.startswith(prefix):
            value = value[len(prefix):]
    value = value.rstrip('/')
    if not value:
        raise ValidationError('Le domaine est vide.')
    if value in _FORBIDDEN or value.startswith('192.168.') or value.startswith('10.'):
        raise ValidationError("Ce domaine n'est pas autorisé.")
    if len(value) > 253:
        raise ValidationError('Le domaine est trop long (253 caractères max).')
    if not _DOMAIN_RE.match(value):
        raise ValidationError(
            'Format invalide. Exemples valides : monsite.fr, boutique.monsite.fr'
        )
    return value


# ─── Formulaire principal d'ajout de domaine ─────────────────────────────────

class DomainCreateForm(forms.Form):
    """Formulaire d'ajout d'un domaine à un site web."""

    TARGET_CHOICES = [
        ('website',       'Site web / vitrine'),
        ('shop',          'Boutique en ligne'),
        ('client_portal', 'Portail client'),
        ('erp',           'Orion ERP'),
        ('landing_page',  'Landing page'),
        ('blog',          'Blog'),
    ]
    TYPE_CHOICES = [
        ('root',      'Domaine racine (monsite.fr)'),
        ('subdomain', 'Sous-domaine (boutique.monsite.fr)'),
    ]

    domain = forms.CharField(
        label='Nom de domaine',
        max_length=253,
        widget=forms.TextInput(attrs={
            'class':       'form-control',
            'placeholder': 'Ex: monentreprise.fr ou boutique.monsite.fr',
            'autocomplete': 'off',
        }),
        help_text='Sans http:// ni https://. Exemple : www.monsite.fr',
    )
    domain_type = forms.ChoiceField(
        label='Type de domaine',
        choices=TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='subdomain',
    )
    target_type = forms.ChoiceField(
        label='Cible',
        choices=TARGET_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        initial='website',
        help_text='Vers quel service ce domaine doit-il pointer ?',
    )
    website = forms.ModelChoiceField(
        label='Site web relié',
        queryset=Website.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Optionnel si la cible est ERP ou portail client.',
    )
    force_https = forms.BooleanField(
        label='Forcer HTTPS (redirection automatique HTTP → HTTPS)',
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    redirect_www = forms.BooleanField(
        label='Rediriger www → domaine racine',
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def __init__(self, company, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        self.fields['website'].queryset = Website.objects.filter(
            company=company, is_active=True
        ).order_by('name')

    def clean_domain(self):
        return clean_domain_input(self.cleaned_data['domain'])

    def clean(self):
        cleaned = super().clean()
        domain = cleaned.get('domain')
        if domain and WebsiteDomain.objects.filter(domain=domain).exists():
            raise ValidationError(
                f'Le domaine « {domain} » est déjà utilisé dans Orion ERP.'
            )
        return cleaned


# ─── Formulaire wizard (étape par étape) ─────────────────────────────────────

class DomainWizardStep1Form(forms.Form):
    """Étape 1 : Choix du type de connexion."""
    TARGET_CHOICES = [
        ('website',       'Site web / vitrine'),
        ('shop',          'Boutique en ligne'),
        ('client_portal', 'Portail client'),
        ('erp',           'Orion ERP'),
        ('landing_page',  'Landing page'),
        ('blog',          'Blog'),
    ]
    target_type = forms.ChoiceField(
        choices=TARGET_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'domain-wizard-radio'}),
        label='Type de connexion',
    )


class DomainWizardStep2Form(forms.Form):
    """Étape 2 : Saisie du domaine."""
    domain = forms.CharField(
        label='Nom de domaine',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'monentreprise.fr',
            'autofocus': True,
        }),
    )
    domain_type = forms.ChoiceField(
        choices=[('root', 'Domaine racine'), ('subdomain', 'Sous-domaine')],
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def clean_domain(self):
        return clean_domain_input(self.cleaned_data['domain'])


class DomainWizardStep3Form(forms.Form):
    """Étape 3 : Choix de la cible (site, boutique...)."""
    website = forms.ModelChoiceField(
        queryset=Website.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label='— Sélectionnez un site —',
    )

    def __init__(self, company, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['website'].queryset = Website.objects.filter(
            company=company, is_active=True
        ).order_by('name')


# ─── Formulaire redirection ───────────────────────────────────────────────────

class DomainRedirectForm(forms.ModelForm):
    class Meta:
        model = DomainRedirect
        fields = ['source_path', 'target_url', 'redirect_type', 'description', 'is_active']
        widgets = {
            'source_path':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': '/ancienne-page'}),
            'target_url':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'https://monsite.fr/nouvelle-page'}),
            'redirect_type':  forms.Select(attrs={'class': 'form-select'}),
            'description':    forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Description optionnelle'}),
            'is_active':      forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'source_path': 'Chemin source',
            'target_url':  'URL cible',
            'redirect_type': 'Type de redirection',
        }

    def clean_target_url(self):
        url = self.cleaned_data['target_url'].strip()
        if not url:
            raise ValidationError('L\'URL cible est requise.')
        return url


# ─── Formulaire SSL ───────────────────────────────────────────────────────────

class DomainSSLForm(forms.Form):
    """Formulaire de demande / activation SSL manuelle."""
    PROVIDER_CHOICES = [
        ('certbot_nginx',  'Certbot + Nginx'),
        ('certbot_apache', 'Certbot + Apache'),
        ('caddy',          'Caddy (automatique)'),
        ('traefik',        'Traefik (automatique)'),
        ('manual',         'Certificat manuel (autre fournisseur)'),
    ]
    ssl_provider = forms.ChoiceField(
        label='Environnement serveur',
        choices=PROVIDER_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    confirm_dns_verified = forms.BooleanField(
        label='Je confirme que le DNS est bien configuré et propagé.',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )


# ─── Formulaire Cloudflare ────────────────────────────────────────────────────

class CloudflareAccountForm(forms.ModelForm):
    class Meta:
        model = CloudflareAccount
        fields = ['api_token', 'account_id', 'email', 'label', 'is_active']
        widgets = {
            'api_token':  forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
            'account_id': forms.TextInput(attrs={'class': 'form-control'}),
            'email':      forms.EmailInput(attrs={'class': 'form-control'}),
            'label':      forms.TextInput(attrs={'class': 'form-control'}),
            'is_active':  forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'api_token': 'Token API Cloudflare',
        }
        help_texts = {
            'api_token': 'Token avec permissions « DNS Edit » sur les zones concernées.',
        }
