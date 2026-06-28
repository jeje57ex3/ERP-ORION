"""
apps/websites/models_domains.py — Modèles complémentaires pour la gestion des domaines Orion ERP
"""
from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Company


class DomainDNSRecord(models.Model):
    """Enregistrement DNS attendu et détecté pour un domaine."""

    RECORD_TYPES = [
        ('A',     'A — Adresse IPv4'),
        ('AAAA',  'AAAA — Adresse IPv6'),
        ('CNAME', 'CNAME — Alias'),
        ('TXT',   'TXT — Texte'),
        ('MX',    'MX — Mail'),
        ('CAA',   'CAA — Autorité certificat'),
    ]
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('valid',   'Valide'),
        ('invalid', 'Invalide'),
        ('missing', 'Manquant'),
    ]

    domain = models.ForeignKey(
        'websites.WebsiteDomain',
        on_delete=models.CASCADE,
        related_name='dns_records',
        verbose_name='Domaine',
    )
    record_type = models.CharField('Type', max_length=10, choices=RECORD_TYPES)
    name = models.CharField('Nom', max_length=253, help_text='Ex: @, www, _orion-verification')
    expected_value = models.CharField('Valeur attendue', max_length=500)
    detected_value = models.CharField('Valeur détectée', max_length=500, blank=True)
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='pending')
    last_checked_at = models.DateTimeField('Dernier check', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'websites'
        verbose_name = 'Enregistrement DNS'
        verbose_name_plural = 'Enregistrements DNS'
        ordering = ['record_type', 'name']

    def __str__(self):
        return f'{self.record_type} {self.name} — {self.domain.domain}'

    @property
    def is_valid(self):
        return self.status == 'valid'


class DomainRedirect(models.Model):
    """Redirection HTTP/HTTPS pour un domaine ou chemin."""

    REDIRECT_TYPES = [
        ('301', 'Redirection permanente (301)'),
        ('302', 'Redirection temporaire (302)'),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='domain_redirects',
        verbose_name='Entreprise',
    )
    domain = models.ForeignKey(
        'websites.WebsiteDomain',
        on_delete=models.CASCADE,
        related_name='redirects',
        verbose_name='Domaine source',
    )
    source_path = models.CharField(
        'Chemin source',
        max_length=500,
        default='/',
        help_text='Ex: / pour tout le domaine, /ancienne-page pour une page spécifique',
    )
    target_url = models.CharField(
        'URL cible',
        max_length=500,
        help_text='Ex: https://nouveaudomaine.fr ou /nouvelle-page',
    )
    redirect_type = models.CharField('Type', max_length=3, choices=REDIRECT_TYPES, default='301')
    description = models.CharField('Description', max_length=200, blank=True)
    is_active = models.BooleanField('Active', default=True)
    hit_count = models.PositiveIntegerField('Utilisations', default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'websites'
        verbose_name = 'Redirection domaine'
        verbose_name_plural = 'Redirections domaine'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.domain.domain}{self.source_path} → {self.target_url} ({self.redirect_type})'


class DomainConnectionLog(models.Model):
    """Historique complet des actions sur les domaines."""

    ACTION_CHOICES = [
        ('created',          'Domaine créé'),
        ('dns_checked',      'DNS vérifié (tentative)'),
        ('dns_verified',     'DNS validé'),
        ('dns_failed',       'DNS invalide'),
        ('ssl_requested',    'SSL demandé'),
        ('ssl_active',       'SSL actif'),
        ('ssl_expired',      'SSL expiré'),
        ('set_primary',      'Défini comme principal'),
        ('disabled',         'Désactivé'),
        ('enabled',          'Réactivé'),
        ('deleted',          'Supprimé'),
        ('redirect_created', 'Redirection créée'),
        ('redirect_deleted', 'Redirection supprimée'),
        ('target_changed',   'Cible modifiée'),
        ('error',            'Erreur'),
    ]
    STATUS_CHOICES = [
        ('success', 'Succès'),
        ('error',   'Erreur'),
        ('info',    'Info'),
        ('warning', 'Avertissement'),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='domain_logs',
        verbose_name='Entreprise',
        null=True,
        blank=True,
    )
    domain = models.ForeignKey(
        'websites.WebsiteDomain',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logs',
        verbose_name='Domaine',
    )
    domain_name = models.CharField(
        'Nom domaine',
        max_length=253,
        blank=True,
        help_text='Copie pour historique après suppression du domaine',
    )
    action = models.CharField('Action', max_length=30, choices=ACTION_CHOICES)
    message = models.TextField('Message', blank=True)
    details = models.JSONField('Détails', default=dict, blank=True)
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='info')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='domain_logs',
        verbose_name='Auteur',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'websites'
        verbose_name = 'Journal domaine'
        verbose_name_plural = 'Journal domaines'
        ordering = ['-created_at']

    def __str__(self):
        name = self.domain_name or (self.domain.domain if self.domain else '?')
        return f'{name} — {self.get_action_display()} ({self.created_at:%d/%m/%Y %H:%M})'

    def save(self, *args, **kwargs):
        if self.domain and not self.domain_name:
            self.domain_name = self.domain.domain
        if self.domain and not self.company_id:
            try:
                self.company = self.domain.website.company
            except Exception:
                pass
        super().save(*args, **kwargs)


class CloudflareAccount(models.Model):
    """
    Intégration Cloudflare optionnelle.
    Permet la gestion DNS automatique via l'API Cloudflare.
    Non activé par défaut.
    """

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='cloudflare_accounts',
        verbose_name='Entreprise',
    )
    api_token = models.CharField(
        'Token API Cloudflare',
        max_length=200,
        help_text='Token API avec permissions DNS Edit sur les zones concernées',
    )
    account_id = models.CharField('ID compte Cloudflare', max_length=100, blank=True)
    email = models.EmailField('Email Cloudflare', blank=True)
    label = models.CharField('Libellé', max_length=100, blank=True, default='Principal')
    is_active = models.BooleanField('Actif', default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'websites'
        verbose_name = 'Compte Cloudflare'
        verbose_name_plural = 'Comptes Cloudflare'

    def __str__(self):
        return f'Cloudflare — {self.company.name} ({self.label})'

    def get_zones(self) -> list:
        """Liste les zones Cloudflare (nécessite l'API token)."""
        try:
            import requests
            headers = {'Authorization': f'Bearer {self.api_token}', 'Content-Type': 'application/json'}
            r = requests.get('https://api.cloudflare.com/client/v4/zones', headers=headers, timeout=10)
            data = r.json()
            if data.get('success'):
                return data.get('result', [])
        except Exception:
            pass
        return []
