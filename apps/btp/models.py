"""
apps/btp/models.py — Chantiers BTP, Devis, Situations, Pointage
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from apps.core.models import Company
from apps.crm.models import Customer


class BTPProject(models.Model):
    """Chantier BTP."""
    STATUS_CHOICES = [
        ('study', 'Étude'),
        ('quoted', 'Devis envoyé'),
        ('won', 'Gagné'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminé'),
        ('invoiced', 'Facturé'),
        ('guaranteed', 'En garantie'),
        ('lost', 'Perdu'),
        ('cancelled', 'Annulé'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='btp_projects')
    code = models.CharField('Code chantier', max_length=30, blank=True)
    name = models.CharField('Nom du chantier', max_length=200)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='btp_projects')
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='study')
    description = models.TextField('Description', blank=True)
    address = models.TextField('Adresse du chantier', blank=True)
    city = models.CharField('Ville', max_length=100, blank=True)
    zip_code = models.CharField('CP', max_length=10, blank=True)

    # Responsables
    project_manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_btp_projects')
    site_foreman = models.CharField('Chef de chantier', max_length=100, blank=True)

    # Dates
    start_date = models.DateField('Début prévu', null=True, blank=True)
    end_date = models.DateField('Fin prévue', null=True, blank=True)
    actual_start_date = models.DateField('Début réel', null=True, blank=True)
    actual_end_date = models.DateField('Fin réelle', null=True, blank=True)

    # Budget
    estimated_budget = models.DecimalField('Budget prévu HT', max_digits=14, decimal_places=2, default=0)
    actual_cost = models.DecimalField('Coût réel HT', max_digits=14, decimal_places=2, default=0)
    invoiced_amount = models.DecimalField('Montant facturé HT', max_digits=14, decimal_places=2, default=0)
    retention_rate = models.DecimalField('Retenue garantie %', max_digits=5, decimal_places=2, default=5)

    # Marché
    market_type = models.CharField('Type marché', max_length=100, blank=True)
    market_number = models.CharField('N° marché', max_length=50, blank=True)

    notes = models.TextField('Notes', blank=True)
    is_active = models.BooleanField('Actif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Chantier BTP'
        verbose_name_plural = 'Chantiers BTP'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.code} — {self.name}' if self.code else self.name

    @property
    def margin(self):
        if self.estimated_budget > 0:
            return ((self.estimated_budget - self.actual_cost) / self.estimated_budget) * 100
        return 0

    @property
    def completion_rate(self):
        if not self.start_date or not self.end_date:
            return 0
        from datetime import date
        today = date.today()
        total_days = (self.end_date - self.start_date).days
        elapsed_days = (today - self.start_date).days
        if total_days <= 0:
            return 100
        return min(100, max(0, int(elapsed_days / total_days * 100)))


class BTPPhase(models.Model):
    """Phase d'un chantier."""
    project = models.ForeignKey(BTPProject, on_delete=models.CASCADE, related_name='phases')
    name = models.CharField('Nom de la phase', max_length=200)
    order = models.PositiveIntegerField('Ordre', default=0)
    start_date = models.DateField('Début', null=True, blank=True)
    end_date = models.DateField('Fin', null=True, blank=True)
    budget = models.DecimalField('Budget HT', max_digits=14, decimal_places=2, default=0)
    is_completed = models.BooleanField('Terminée', default=False)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.project.name} — {self.name}'


class WorkLibrary(models.Model):
    """Bibliothèque d'ouvrages BTP."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='work_library')
    code = models.CharField('Code ouvrage', max_length=30, blank=True)
    name = models.CharField('Désignation', max_length=300)
    category = models.CharField('Catégorie', max_length=100, blank=True)
    unit = models.CharField('Unité', max_length=20, default='m²')
    unit_price = models.DecimalField('Prix unitaire HT', max_digits=12, decimal_places=4, default=0)
    description = models.TextField('Détail', blank=True)
    is_active = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Ouvrage BTP'
        verbose_name_plural = 'Bibliothèque ouvrages'
        ordering = ['code', 'name']

    def __str__(self):
        return f'{self.code} — {self.name}' if self.code else self.name


class BTPQuote(models.Model):
    """Devis BTP."""
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('sent', 'Envoyé'),
        ('accepted', 'Accepté'),
        ('refused', 'Refusé'),
        ('expired', 'Expiré'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='btp_quotes')
    project = models.ForeignKey(BTPProject, on_delete=models.CASCADE, null=True, blank=True, related_name='quotes')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='btp_quotes')
    number = models.CharField('Numéro', max_length=30, blank=True)
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='draft')
    issue_date = models.DateField('Date', default=timezone.now)
    validity_date = models.DateField('Validité', null=True, blank=True)
    subject = models.CharField('Objet', max_length=300, blank=True)
    notes = models.TextField('Notes', blank=True)
    total_ht = models.DecimalField('Total HT', max_digits=14, decimal_places=2, default=0)
    total_tva = models.DecimalField('Total TVA', max_digits=14, decimal_places=2, default=0)
    total_ttc = models.DecimalField('Total TTC', max_digits=14, decimal_places=2, default=0)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Devis BTP'
        verbose_name_plural = 'Devis BTP'
        ordering = ['-issue_date']

    def __str__(self):
        return f'{self.number or "DEV-BTP"} — {self.customer.name}'


class BTPQuoteLine(models.Model):
    """Ligne de devis BTP."""
    quote = models.ForeignKey(BTPQuote, on_delete=models.CASCADE, related_name='lines')
    phase = models.ForeignKey(BTPPhase, on_delete=models.SET_NULL, null=True, blank=True)
    work_item = models.ForeignKey(WorkLibrary, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField('Désignation')
    unit = models.CharField('Unité', max_length=20, default='m²')
    quantity = models.DecimalField('Quantité', max_digits=12, decimal_places=3, default=0)
    unit_price = models.DecimalField('PU HT', max_digits=12, decimal_places=4, default=0)
    total_ht = models.DecimalField('Total HT', max_digits=14, decimal_places=2, default=0)
    vat_rate = models.DecimalField('TVA %', max_digits=5, decimal_places=2, default=20)
    order = models.PositiveIntegerField('Ordre', default=0)
    is_section = models.BooleanField('Sous-total section', default=False)

    class Meta:
        ordering = ['order']

    def save(self, *args, **kwargs):
        if not self.is_section:
            self.total_ht = self.quantity * self.unit_price
        super().save(*args, **kwargs)


class SituationOfWorks(models.Model):
    """Situation de travaux (facturation avancement)."""
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('submitted', 'Soumise'),
        ('approved', 'Approuvée'),
        ('invoiced', 'Facturée'),
        ('rejected', 'Rejetée'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='situations')
    project = models.ForeignKey(BTPProject, on_delete=models.CASCADE, related_name='situations')
    number = models.PositiveIntegerField('N° situation', default=1)
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='draft')
    period_start = models.DateField('Début période')
    period_end = models.DateField('Fin période')
    cumulative_amount = models.DecimalField('Montant cumulé HT', max_digits=14, decimal_places=2, default=0)
    previous_amount = models.DecimalField('Montant précédent HT', max_digits=14, decimal_places=2, default=0)
    period_amount = models.DecimalField('Montant période HT', max_digits=14, decimal_places=2, default=0)
    retention_amount = models.DecimalField('Retenue garantie HT', max_digits=14, decimal_places=2, default=0)
    notes = models.TextField('Notes', blank=True)
    validated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='validated_situations')
    validated_at = models.DateTimeField('Validée le', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Situation de travaux'
        verbose_name_plural = 'Situations de travaux'
        unique_together = ['project', 'number']
        ordering = ['-period_end']

    def __str__(self):
        return f'Situation n°{self.number} — {self.project.name}'


class BTPTimesheet(models.Model):
    """Pointage chantier."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='btp_timesheets')
    project = models.ForeignKey(BTPProject, on_delete=models.CASCADE, related_name='timesheets')
    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='btp_timesheets')
    work_date = models.DateField('Date')
    hours = models.DecimalField('Heures', max_digits=5, decimal_places=2, default=8)
    overtime_hours = models.DecimalField('Heures sup', max_digits=5, decimal_places=2, default=0)
    task_description = models.CharField('Tâche', max_length=200, blank=True)
    notes = models.TextField('Notes', blank=True)
    is_validated = models.BooleanField('Validé', default=False)
    validated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='validated_timesheets')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pointage'
        verbose_name_plural = 'Pointages'
        ordering = ['-work_date']

    def __str__(self):
        return f'{self.employee.get_full_name()} — {self.project.name} — {self.work_date}'


# ─── ÉLECTRICITÉ : BIBLIOTHÈQUE DE PRIX ───────────────────────────────────────

class ElectricityPriceLibrary(models.Model):
    CATEGORY_CHOICES = [
        ('deplacement', 'Déplacement'), ('diagnostic', 'Diagnostic'),
        ('depannage', 'Dépannage'), ('installation', 'Installation'),
        ('tableau', 'Tableau électrique'), ('prise_interrupteur', 'Prise / Interrupteur'),
        ('eclairage', 'Éclairage'), ('borne_recharge', 'Borne de recharge'),
        ('domotique', 'Domotique'), ('vmc', 'VMC'), ('reseau', 'Réseau informatique'),
        ('chauffage', 'Chauffage électrique'), ('alarme', 'Alarme / Sécurité'),
        ('main_oeuvre', 'Main-d\'œuvre'), ('renovation', 'Rénovation'),
        ('mise_normes', 'Mise aux normes'), ('forfait', 'Forfait'), ('autre', 'Autre'),
    ]
    UNIT_CHOICES = [
        ('u', 'Unité'), ('h', 'Heure'), ('m2', 'm²'), ('ml', 'Mètre linéaire'),
        ('forfait', 'Forfait'), ('point', 'Point'), ('circuit', 'Circuit'),
    ]
    COMPLEXITY_CHOICES = [('simple', 'Simple'), ('medium', 'Intermédiaire'), ('complex', 'Complexe')]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='electricity_price_library')
    code = models.CharField('Code', max_length=30, blank=True)
    name = models.CharField('Désignation', max_length=200)
    category = models.CharField('Catégorie', max_length=30, choices=CATEGORY_CHOICES, default='autre')
    description = models.TextField('Description', blank=True)
    unit = models.CharField('Unité', max_length=20, choices=UNIT_CHOICES, default='u')
    price_min = models.DecimalField('Prix minimum HT', max_digits=10, decimal_places=2, default=0)
    price_avg = models.DecimalField('Prix moyen HT', max_digits=10, decimal_places=2, default=0)
    price_max = models.DecimalField('Prix maximum HT', max_digits=10, decimal_places=2, default=0)
    duration_hours = models.DecimalField('Durée estimée (h)', max_digits=5, decimal_places=2, default=0)
    complexity = models.CharField('Complexité', max_length=10, choices=COMPLEXITY_CHOICES, default='medium')
    is_active = models.BooleanField('Actif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Poste tarif électricité'
        verbose_name_plural = 'Bibliothèque prix électricité'
        ordering = ['category', 'name']

    def __str__(self):
        return f'{self.name} ({self.get_unit_display()})'


# ─── DEMANDE GUIDÉE ───────────────────────────────────────────────────────────

class GuidedQuoteRequest(models.Model):
    REQUEST_TYPE_CHOICES = [
        ('depannage', 'Dépannage'), ('travaux', 'Travaux'),
        ('renovation', 'Rénovation'), ('mise_normes', 'Mise aux normes'),
        ('installation_neuve', 'Installation neuve'), ('autre', 'Autre'),
    ]
    STATUS_CHOICES = [
        ('new', 'Nouvelle'), ('to_analyze', 'À analyser'),
        ('complement_asked', 'Complément demandé'), ('estimate_sent', 'Pré-devis envoyé'),
        ('quote_created', 'Devis créé'), ('accepted', 'Acceptée'),
        ('refused', 'Refusée'), ('converted', 'Transformée en chantier'),
        ('archived', 'Archivée'),
    ]
    URGENCY_CHOICES = [('urgent', 'Urgent'), ('normal', 'Normal'), ('flexible', 'Flexible')]
    PROPERTY_TYPE_CHOICES = [
        ('apartment', 'Appartement'), ('house', 'Maison'), ('commercial', 'Local commercial'),
        ('office', 'Bureau'), ('workshop', 'Atelier'), ('building', 'Immeuble'), ('other', 'Autre'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='guided_quote_requests')
    reference = models.CharField('Référence', max_length=30, blank=True)
    request_type = models.CharField('Type de demande', max_length=30, choices=REQUEST_TYPE_CHOICES)
    status = models.CharField('Statut', max_length=30, choices=STATUS_CHOICES, default='new')
    urgency = models.CharField('Urgence', max_length=10, choices=URGENCY_CHOICES, default='normal')

    # Client info
    client_first_name = models.CharField('Prénom', max_length=100)
    client_last_name = models.CharField('Nom', max_length=100)
    client_email = models.EmailField('Email')
    client_phone = models.CharField('Téléphone', max_length=20, blank=True)
    create_portal_account = models.BooleanField('Créer espace client', default=False)

    # Adresse intervention
    address = models.CharField('Adresse', max_length=200, blank=True)
    zip_code = models.CharField('Code postal', max_length=10, blank=True)
    city = models.CharField('Ville', max_length=100, blank=True)
    floor = models.CharField('Étage', max_length=20, blank=True)
    digicode = models.CharField('Digicode', max_length=20, blank=True)
    parking = models.BooleanField('Parking disponible', default=False)

    # Bien
    property_type = models.CharField('Type de bien', max_length=20, choices=PROPERTY_TYPE_CHOICES, blank=True)
    surface = models.CharField('Surface', max_length=30, blank=True)

    # Réponses formulaire (JSON flexible)
    answers = models.JSONField('Réponses', default=dict, blank=True)

    # Notes
    client_notes = models.TextField('Message client', blank=True)
    internal_notes = models.TextField('Notes internes', blank=True)

    # Liens ERP
    btp_project = models.ForeignKey(BTPProject, on_delete=models.SET_NULL, null=True, blank=True, related_name='guided_requests')
    btp_quote = models.ForeignKey(BTPQuote, on_delete=models.SET_NULL, null=True, blank=True, related_name='guided_requests')
    crm_customer_id = models.PositiveIntegerField('ID client CRM', null=True, blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_guided_requests')

    # Créneaux souhaités
    preferred_slots = models.TextField('Créneaux souhaités', blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Demande guidée'
        verbose_name_plural = 'Demandes guidées'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.reference:
            count = GuidedQuoteRequest.objects.filter(company=self.company).count()
            self.reference = f'DG-{count + 1:05d}'
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.reference} — {self.client_last_name} ({self.get_request_type_display()})'

    @property
    def client_full_name(self):
        return f'{self.client_first_name} {self.client_last_name}'.strip()

    @property
    def is_urgent(self):
        return self.urgency == 'urgent'


class GuidedQuotePhoto(models.Model):
    request = models.ForeignKey(GuidedQuoteRequest, on_delete=models.CASCADE, related_name='photos')
    photo = models.ImageField('Photo', upload_to='guided_quotes/photos/')
    caption = models.CharField('Légende', max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Photo demande'


class GuidedQuoteDocument(models.Model):
    request = models.ForeignKey(GuidedQuoteRequest, on_delete=models.CASCADE, related_name='documents')
    file = models.FileField('Fichier', upload_to='guided_quotes/docs/')
    name = models.CharField('Nom', max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Document demande'


# ─── PRÉ-DEVIS ESTIMATIF ──────────────────────────────────────────────────────

class GuidedQuoteEstimate(models.Model):
    request = models.OneToOneField(GuidedQuoteRequest, on_delete=models.CASCADE, related_name='estimate')
    # Montants
    amount_min_ht = models.DecimalField('Minimum HT', max_digits=12, decimal_places=2, default=0)
    amount_avg_ht = models.DecimalField('Estimé HT', max_digits=12, decimal_places=2, default=0)
    amount_max_ht = models.DecimalField('Maximum HT', max_digits=12, decimal_places=2, default=0)
    labor_amount = models.DecimalField('Main-d\'œuvre HT', max_digits=12, decimal_places=2, default=0)
    materials_amount = models.DecimalField('Fournitures HT', max_digits=12, decimal_places=2, default=0)
    travel_amount = models.DecimalField('Déplacement HT', max_digits=12, decimal_places=2, default=0)
    urgency_surcharge = models.DecimalField('Majoration urgence HT', max_digits=10, decimal_places=2, default=0)
    vat_rate = models.DecimalField('TVA %', max_digits=5, decimal_places=2, default=20)
    total_ttc = models.DecimalField('Total TTC estimé', max_digits=12, decimal_places=2, default=0)
    duration_min_days = models.DecimalField('Durée min (jours)', max_digits=5, decimal_places=1, default=0)
    duration_max_days = models.DecimalField('Durée max (jours)', max_digits=5, decimal_places=1, default=0)
    complexity_level = models.CharField('Complexité', max_length=10, choices=[('simple', 'Simple'), ('medium', 'Intermédiaire'), ('complex', 'Complexe')], default='medium')
    disclaimer = models.TextField('Avertissement', default='Ce pré-devis est une estimation indicative basée sur les informations fournies. Le montant final pourra être ajusté après analyse technique, visite sur site ou validation par un responsable.')
    sent_to_client = models.BooleanField('Envoyé au client', default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pré-devis estimatif'

    def __str__(self):
        return f'Estimation {self.request.reference}'


class GuidedQuoteEstimateItem(models.Model):
    estimate = models.ForeignKey(GuidedQuoteEstimate, on_delete=models.CASCADE, related_name='items')
    price_item = models.ForeignKey(ElectricityPriceLibrary, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField('Désignation', max_length=300)
    quantity = models.DecimalField('Quantité', max_digits=8, decimal_places=2, default=1)
    unit = models.CharField('Unité', max_length=20, default='u')
    unit_price_avg = models.DecimalField('PU moyen HT', max_digits=10, decimal_places=2, default=0)
    total_avg = models.DecimalField('Total moyen HT', max_digits=12, decimal_places=2, default=0)
    order = models.PositiveIntegerField('Ordre', default=0)

    class Meta:
        ordering = ['order']

    def save(self, *args, **kwargs):
        self.total_avg = self.quantity * self.unit_price_avg
        super().save(*args, **kwargs)


# ─── AFFECTATION SALARIÉ SUR CHANTIER ─────────────────────────────────────────

class SiteAssignment(models.Model):
    ROLE_CHOICES = [
        ('project_manager', 'Responsable chantier'), ('electrician', 'Électricien'),
        ('team_leader', 'Chef d\'équipe'), ('apprentice', 'Apprenti'),
        ('technician', 'Technicien'), ('works_manager', 'Conducteur de travaux'),
        ('business_manager', 'Chargé d\'affaires'), ('subcontractor', 'Sous-traitant'),
    ]

    project = models.ForeignKey(BTPProject, on_delete=models.CASCADE, related_name='site_assignments')
    employee = models.ForeignKey('hr.Employee', on_delete=models.CASCADE, related_name='site_assignments')
    role = models.CharField('Rôle', max_length=30, choices=ROLE_CHOICES, default='electrician')
    start_date = models.DateField('Début affectation', null=True, blank=True)
    end_date = models.DateField('Fin affectation', null=True, blank=True)
    planned_days = models.TextField('Jours d\'intervention prévus', blank=True)

    # Visibilité côté client
    visible_to_client = models.BooleanField('Visible par le client', default=True)
    client_can_contact = models.BooleanField('Client peut contacter', default=False)
    show_phone_to_client = models.BooleanField('Afficher téléphone au client', default=False)
    show_email_to_client = models.BooleanField('Afficher email au client', default=False)

    notes = models.TextField('Notes', blank=True)
    is_active = models.BooleanField('Actif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Affectation chantier'
        verbose_name_plural = 'Affectations chantier'
        unique_together = ['project', 'employee']

    def __str__(self):
        return f'{self.employee} — {self.project.name} ({self.get_role_display()})'


# ─── HEURES SAISIES SUR CHANTIER ──────────────────────────────────────────────

class TimeEntry(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Saisi'), ('validated', 'Validé en interne'),
        ('client_visible', 'Visible client'), ('disputed', 'Contesté'), ('invoiced', 'Facturé'),
    ]

    project = models.ForeignKey(BTPProject, on_delete=models.CASCADE, related_name='time_entries')
    employee = models.ForeignKey('hr.Employee', on_delete=models.CASCADE, related_name='time_entries')
    work_date = models.DateField('Date')
    hours = models.DecimalField('Heures', max_digits=5, decimal_places=2)
    task_description = models.CharField('Tâche réalisée', max_length=300, blank=True)
    internal_comment = models.TextField('Commentaire interne', blank=True)
    client_comment = models.TextField('Commentaire visible client', blank=True)
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='draft')
    visible_to_client = models.BooleanField('Visible client', default=False)
    validated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Saisie d\'heures'
        verbose_name_plural = 'Saisies d\'heures'
        ordering = ['-work_date']

    def __str__(self):
        return f'{self.employee} — {self.project.name} — {self.work_date} ({self.hours}h)'


# ─── MESSAGERIE CLIENT ────────────────────────────────────────────────────────

class ClientConversation(models.Model):
    STATUS_CHOICES = [
        ('open', 'Ouverte'), ('waiting_client', 'En attente client'),
        ('waiting_manager', 'En attente responsable'), ('resolved', 'Traitée'), ('closed', 'Fermée'),
    ]

    project = models.ForeignKey(BTPProject, on_delete=models.CASCADE, related_name='conversations')
    subject = models.CharField('Sujet', max_length=200, default='Message chantier')
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='open')
    created_by_client = models.BooleanField('Créé par le client', default=True)
    unread_by_client = models.PositiveIntegerField('Non lus (client)', default=0)
    unread_by_manager = models.PositiveIntegerField('Non lus (responsable)', default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Conversation client'
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.subject} — {self.project.name}'


class ClientMessage(models.Model):
    conversation = models.ForeignKey(ClientConversation, on_delete=models.CASCADE, related_name='messages')
    sender_name = models.CharField('Expéditeur', max_length=100)
    is_from_client = models.BooleanField('Message du client', default=True)
    is_internal = models.BooleanField('Note interne (non visible client)', default=False)
    content = models.TextField('Message')
    is_read_by_client = models.BooleanField('Lu par le client', default=False)
    is_read_by_manager = models.BooleanField('Lu par le responsable', default=False)
    created_task = models.BooleanField('Transformé en tâche', default=False)
    created_reservation = models.BooleanField('Transformé en réserve', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Message client'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender_name} — {self.created_at:%d/%m/%Y %H:%M}'


class MessageAttachment(models.Model):
    message = models.ForeignKey(ClientMessage, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField('Fichier', upload_to='client_messages/')
    name = models.CharField('Nom', max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)


# ─── DOCUMENTS CHANTIER ───────────────────────────────────────────────────────

class DocumentCategory(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='doc_categories')
    name = models.CharField('Nom', max_length=100)
    icon = models.CharField('Icône Bootstrap', max_length=50, default='file-earmark')
    order = models.PositiveIntegerField('Ordre', default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class ProjectDocument(models.Model):
    DOC_TYPE_CHOICES = [
        ('quote', 'Devis'), ('invoice', 'Facture'), ('plan', 'Plan'),
        ('photo', 'Photo'), ('diagnostic', 'Diagnostic électrique'),
        ('attestation', 'Attestation'), ('pv_reception', 'PV de réception'),
        ('notice', 'Notice technique'), ('warranty', 'Garantie'),
        ('doe', 'DOE'), ('diuo', 'DIUO'), ('contract', 'Contrat'),
        ('amendment', 'Avenant'), ('work_order', 'Bon d\'intervention'),
        ('daily_report', 'Rapport journalier'), ('certificate', 'Certificat'),
        ('client_doc', 'Document client'), ('other', 'Autre'),
    ]

    project = models.ForeignKey(BTPProject, on_delete=models.CASCADE, related_name='project_documents')
    category = models.ForeignKey(DocumentCategory, on_delete=models.SET_NULL, null=True, blank=True)
    doc_type = models.CharField('Type', max_length=30, choices=DOC_TYPE_CHOICES, default='other')
    name = models.CharField('Nom', max_length=200)
    file = models.FileField('Fichier', upload_to='project_documents/')
    description = models.TextField('Description', blank=True)
    version = models.CharField('Version', max_length=20, default='1.0')

    # Visibilité et droits
    visible_to_client = models.BooleanField('Visible client', default=False)
    client_can_download = models.BooleanField('Client peut télécharger', default=True)
    client_can_comment = models.BooleanField('Client peut commenter', default=False)
    is_mandatory = models.BooleanField('Document obligatoire', default=False)
    requires_signature = models.BooleanField('Signature requise', default=False)
    is_signed = models.BooleanField('Signé', default=False)

    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Document chantier'
        verbose_name_plural = 'Documents chantier'
        ordering = ['-added_at']

    def __str__(self):
        return f'{self.name} — {self.project.name}'


# ─── PLANNING CHANTIER ────────────────────────────────────────────────────────

class ProjectPlanStep(models.Model):
    STATUS_CHOICES = [
        ('pending', 'À venir'), ('in_progress', 'En cours'),
        ('waiting_client', 'En attente client'), ('waiting_material', 'En attente matériel'),
        ('done', 'Terminée'), ('delayed', 'Retardée'),
    ]
    STEP_TYPE_CHOICES = [
        ('technical_visit', 'Visite technique'), ('quote_validation', 'Validation devis'),
        ('material_prep', 'Préparation matériel'), ('work_start', 'Début travaux'),
        ('cable_pass', 'Passage câbles'), ('fitting', 'Pose appareillage'),
        ('panel', 'Tableau électrique'), ('tests', 'Tests'),
        ('commissioning', 'Mise en service'), ('cleaning', 'Nettoyage'),
        ('reception', 'Réception chantier'), ('reserve_lifting', 'Levée de réserves'), ('other', 'Autre'),
    ]

    project = models.ForeignKey(BTPProject, on_delete=models.CASCADE, related_name='plan_steps')
    name = models.CharField('Étape', max_length=200)
    step_type = models.CharField('Type', max_length=30, choices=STEP_TYPE_CHOICES, default='other')
    order = models.PositiveIntegerField('Ordre', default=0)
    planned_date = models.DateField('Date prévue', null=True, blank=True)
    actual_date = models.DateField('Date réelle', null=True, blank=True)
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='pending')
    progress_percent = models.PositiveIntegerField('Avancement %', default=0)
    responsible = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    client_comment = models.TextField('Commentaire visible client', blank=True)
    visible_to_client = models.BooleanField('Visible client', default=True)
    client_can_validate = models.BooleanField('Client peut valider', default=False)
    validated_by_client = models.BooleanField('Validé par le client', default=False)
    validated_by_client_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Étape planning'
        verbose_name_plural = 'Planning chantier'
        ordering = ['order']

    def __str__(self):
        return f'{self.project.name} — {self.name}'


# ─── AVENANTS CLIENT ──────────────────────────────────────────────────────────

class ClientChangeRequest(models.Model):
    STATUS_CHOICES = [
        ('requested', 'Demandée'), ('analyzing', 'En analyse'),
        ('quoting', 'Chiffrage en cours'), ('amendment_proposed', 'Avenant proposé'),
        ('accepted', 'Acceptée'), ('refused', 'Refusée'), ('integrated', 'Intégrée'),
    ]

    project = models.ForeignKey(BTPProject, on_delete=models.CASCADE, related_name='change_requests')
    reference = models.CharField('Référence', max_length=30, blank=True)
    title = models.CharField('Titre', max_length=200)
    description = models.TextField('Description')
    status = models.CharField('Statut', max_length=25, choices=STATUS_CHOICES, default='requested')
    requested_by_client = models.BooleanField('Demandé par le client', default=True)
    estimated_amount = models.DecimalField('Montant estimé HT', max_digits=12, decimal_places=2, null=True, blank=True)
    btp_quote = models.ForeignKey(BTPQuote, on_delete=models.SET_NULL, null=True, blank=True, related_name='change_request_amendments')
    internal_notes = models.TextField('Notes internes', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Demande de modification'
        verbose_name_plural = 'Demandes de modification'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.reference or "MOD"} — {self.title}'


class ChangeRequestItem(models.Model):
    change_request = models.ForeignKey(ClientChangeRequest, on_delete=models.CASCADE, related_name='items')
    description = models.CharField('Description', max_length=300)
    quantity = models.DecimalField('Quantité', max_digits=8, decimal_places=2, default=1)
    unit = models.CharField('Unité', max_length=20, blank=True)
    unit_price = models.DecimalField('PU HT', max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return self.description


# ─── RÉSERVES CLIENT ──────────────────────────────────────────────────────────

class ProjectReservation(models.Model):
    IMPORTANCE_CHOICES = [('low', 'Faible'), ('medium', 'Moyenne'), ('high', 'Importante'), ('blocking', 'Bloquante')]
    STATUS_CHOICES = [
        ('new', 'Nouvelle'), ('analyzing', 'En analyse'), ('accepted', 'Acceptée'),
        ('refused', 'Refusée'), ('planned', 'Planifiée'), ('corrected', 'Corrigée'),
        ('lifted', 'Levée'), ('closed', 'Clôturée'),
    ]

    project = models.ForeignKey(BTPProject, on_delete=models.CASCADE, related_name='reservations')
    reference = models.CharField('Référence', max_length=30, blank=True)
    title = models.CharField('Titre', max_length=200)
    description = models.TextField('Description')
    room = models.CharField('Pièce concernée', max_length=100, blank=True)
    importance = models.CharField('Importance', max_length=10, choices=IMPORTANCE_CHOICES, default='medium')
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='new')
    reported_by_client = models.BooleanField('Signalée par le client', default=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    planned_correction_date = models.DateField('Date correction prévue', null=True, blank=True)
    corrected_at = models.DateTimeField('Corrigée le', null=True, blank=True)
    validated_by_client = models.BooleanField('Validée par le client', default=False)
    internal_notes = models.TextField('Notes internes', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Réserve'
        verbose_name_plural = 'Réserves'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.reference or "RES"} — {self.title}'


class ReservationPhoto(models.Model):
    reservation = models.ForeignKey(ProjectReservation, on_delete=models.CASCADE, related_name='photos')
    photo = models.ImageField('Photo', upload_to='reservations/')
    caption = models.CharField('Légende', max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)


# ─── NOTIFICATIONS CLIENT ─────────────────────────────────────────────────────

class ClientNotification(models.Model):
    NOTIF_TYPE_CHOICES = [
        ('message', 'Nouveau message'), ('document', 'Nouveau document'),
        ('planning', 'Planning mis à jour'), ('project', 'Chantier mis à jour'),
        ('quote', 'Devis disponible'), ('invoice', 'Facture disponible'),
        ('amendment', 'Avenant à valider'), ('reservation', 'Réserve traitée'),
        ('intervention', 'Intervention planifiée'), ('hours', 'Heures mises à jour'),
    ]

    project = models.ForeignKey(BTPProject, on_delete=models.CASCADE, related_name='client_notifications', null=True, blank=True)
    client_email = models.EmailField('Email client')
    notif_type = models.CharField('Type', max_length=20, choices=NOTIF_TYPE_CHOICES)
    title = models.CharField('Titre', max_length=200)
    message = models.TextField('Message')
    link = models.CharField('Lien', max_length=300, blank=True)
    is_read = models.BooleanField('Lu', default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Notification client'
        verbose_name_plural = 'Notifications client'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_notif_type_display()} — {self.client_email}'
