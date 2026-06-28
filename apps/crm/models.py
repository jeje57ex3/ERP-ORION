"""
apps/crm/models.py — CRM : Clients, Prospects, Opportunités, Contacts
"""
from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Company


class Customer(models.Model):
    """Client de l'entreprise."""
    TYPE_CHOICES = [('individual', 'Particulier'), ('company', 'Société')]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='customers')
    customer_type = models.CharField('Type', max_length=20, choices=TYPE_CHOICES, default='company')
    code = models.CharField('Code client', max_length=20, blank=True)
    name = models.CharField('Nom / Raison sociale', max_length=200)
    contact_name = models.CharField('Nom contact', max_length=100, blank=True)
    email = models.EmailField('Email', blank=True)
    phone = models.CharField('Téléphone', max_length=20, blank=True)
    mobile = models.CharField('Mobile', max_length=20, blank=True)
    address = models.TextField('Adresse', blank=True)
    city = models.CharField('Ville', max_length=100, blank=True)
    zip_code = models.CharField('CP', max_length=10, blank=True)
    country = models.CharField('Pays', max_length=100, default='France')
    siret = models.CharField('SIRET', max_length=14, blank=True)
    vat_number = models.CharField('N° TVA', max_length=20, blank=True)
    website = models.URLField('Site web', blank=True)
    payment_terms = models.PositiveIntegerField('Délai paiement (j)', default=30)
    credit_limit = models.DecimalField('Limite crédit', max_digits=12, decimal_places=2, null=True, blank=True)
    discount_rate = models.DecimalField('Remise %', max_digits=5, decimal_places=2, default=0)
    notes = models.TextField('Notes', blank=True)
    salesperson = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='customers')
    is_active = models.BooleanField('Actif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_customers')

    class Meta:
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'
        ordering = ['name']

    def __str__(self):
        return self.name


class Prospect(models.Model):
    """Prospect commercial."""
    STATUS_CHOICES = [
        ('new', 'Nouveau'),
        ('contacted', 'Contacté'),
        ('qualified', 'Qualifié'),
        ('proposal', 'Proposition'),
        ('negotiation', 'Négociation'),
        ('won', 'Gagné'),
        ('lost', 'Perdu'),
        ('inactive', 'Inactif'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='prospects')
    name = models.CharField('Nom / Société', max_length=200)
    contact_name = models.CharField('Contact', max_length=100, blank=True)
    email = models.EmailField('Email', blank=True)
    phone = models.CharField('Téléphone', max_length=20, blank=True)
    city = models.CharField('Ville', max_length=100, blank=True)
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='new')
    source = models.CharField('Source', max_length=100, blank=True)
    estimated_value = models.DecimalField('Valeur estimée', max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField('Notes', blank=True)
    salesperson = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    next_action_date = models.DateField('Prochaine action', null=True, blank=True)
    converted_to_customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True)
    is_active = models.BooleanField('Actif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Prospect'
        verbose_name_plural = 'Prospects'
        ordering = ['-created_at']

    def __str__(self):
        return self.name


class Contact(models.Model):
    """Contact associé à un client ou prospect."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True, related_name='contacts')
    prospect = models.ForeignKey(Prospect, on_delete=models.CASCADE, null=True, blank=True, related_name='contacts')
    first_name = models.CharField('Prénom', max_length=100)
    last_name = models.CharField('Nom', max_length=100)
    job_title = models.CharField('Poste', max_length=100, blank=True)
    email = models.EmailField('Email', blank=True)
    phone = models.CharField('Téléphone', max_length=20, blank=True)
    mobile = models.CharField('Mobile', max_length=20, blank=True)
    is_primary = models.BooleanField('Contact principal', default=False)
    notes = models.TextField('Notes', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Contact'
        verbose_name_plural = 'Contacts'

    def __str__(self):
        return f'{self.first_name} {self.last_name}'


class Opportunity(models.Model):
    """Opportunité commerciale."""
    STAGE_CHOICES = [
        ('prospecting', 'Prospection'),
        ('qualification', 'Qualification'),
        ('proposal', 'Proposition'),
        ('negotiation', 'Négociation'),
        ('closed_won', 'Gagné'),
        ('closed_lost', 'Perdu'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='opportunities')
    name = models.CharField('Nom opportunité', max_length=200)
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='opportunities')
    prospect = models.ForeignKey(Prospect, on_delete=models.SET_NULL, null=True, blank=True, related_name='opportunities')
    stage = models.CharField('Étape', max_length=20, choices=STAGE_CHOICES, default='prospecting')
    probability = models.PositiveIntegerField('Probabilité %', default=10)
    expected_revenue = models.DecimalField('CA prévu', max_digits=12, decimal_places=2, null=True, blank=True)
    close_date = models.DateField('Date clôture prévue', null=True, blank=True)
    salesperson = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField('Notes', blank=True)
    lost_reason = models.TextField('Raison perte', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Opportunité'
        verbose_name_plural = 'Opportunités'
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    @property
    def weighted_revenue(self):
        if self.expected_revenue:
            return self.expected_revenue * self.probability / 100
        return 0


class CRMActivity(models.Model):
    """Historique d'activité CRM."""
    TYPE_CHOICES = [
        ('call', 'Appel téléphonique'),
        ('email', 'Email'),
        ('meeting', 'Réunion'),
        ('visit', 'Visite'),
        ('note', 'Note'),
        ('task', 'Tâche'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    activity_type = models.CharField('Type', max_length=20, choices=TYPE_CHOICES)
    subject = models.CharField('Sujet', max_length=200)
    description = models.TextField('Description', blank=True)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, null=True, blank=True, related_name='activities')
    prospect = models.ForeignKey(Prospect, on_delete=models.CASCADE, null=True, blank=True, related_name='activities')
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, null=True, blank=True, related_name='activities')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    date = models.DateTimeField('Date')
    duration_minutes = models.PositiveIntegerField('Durée (min)', default=0)
    is_done = models.BooleanField('Fait', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Activité CRM'
        verbose_name_plural = 'Activités CRM'
        ordering = ['-date']

    def __str__(self):
        return f'{self.get_activity_type_display()} — {self.subject}'
