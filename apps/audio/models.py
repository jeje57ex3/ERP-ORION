"""
apps/audio/models.py — Matériel audio, Réservations, Événements, Techniciens
"""
from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Company
from apps.crm.models import Customer


class EquipmentCategory(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    name = models.CharField('Catégorie', max_length=100)
    description = models.TextField('Description', blank=True)

    class Meta:
        verbose_name = 'Catégorie matériel'

    def __str__(self):
        return self.name


class Equipment(models.Model):
    """Matériel audio/AV."""
    STATUS_CHOICES = [
        ('available', 'Disponible'),
        ('rented', 'En location'),
        ('maintenance', 'En maintenance'),
        ('damaged', 'Endommagé'),
        ('lost', 'Perdu'),
        ('retired', 'Retiré'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='equipment')
    category = models.ForeignKey(EquipmentCategory, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField('Nom', max_length=200)
    brand = models.CharField('Marque', max_length=100, blank=True)
    model = models.CharField('Modèle', max_length=100, blank=True)
    serial_number = models.CharField('N° série', max_length=100, blank=True)
    reference = models.CharField('Référence interne', max_length=50, blank=True)
    description = models.TextField('Description', blank=True)
    image = models.ImageField('Photo', upload_to='equipment/', blank=True, null=True)
    quantity = models.PositiveIntegerField('Quantité totale', default=1)
    available_quantity = models.PositiveIntegerField('Quantité disponible', default=1)
    rental_price_day = models.DecimalField('Prix location/jour HT', max_digits=10, decimal_places=2, default=0)
    replacement_value = models.DecimalField('Valeur remplacement', max_digits=10, decimal_places=2, null=True, blank=True)
    purchase_date = models.DateField('Date achat', null=True, blank=True)
    purchase_price = models.DecimalField('Prix achat', max_digits=10, decimal_places=2, null=True, blank=True)
    status = models.CharField('État', max_length=20, choices=STATUS_CHOICES, default='available')
    last_maintenance_date = models.DateField('Dernière maintenance', null=True, blank=True)
    next_maintenance_date = models.DateField('Prochaine maintenance', null=True, blank=True)
    notes = models.TextField('Notes', blank=True)
    is_active = models.BooleanField('Actif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Matériel'
        verbose_name_plural = 'Matériels'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.brand})' if self.brand else self.name


class EquipmentPack(models.Model):
    """Pack de matériels pour location."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='equipment_packs')
    name = models.CharField('Nom du pack', max_length=200)
    description = models.TextField('Description', blank=True)
    items = models.ManyToManyField(Equipment, through='PackItem', blank=True)
    rental_price_day = models.DecimalField('Prix pack/jour HT', max_digits=10, decimal_places=2, default=0)
    is_active = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Pack matériel'

    def __str__(self):
        return self.name


class PackItem(models.Model):
    pack = models.ForeignKey(EquipmentPack, on_delete=models.CASCADE)
    equipment = models.ForeignKey(Equipment, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField('Quantité', default=1)


class AudioEvent(models.Model):
    """Événement audio/AV."""
    EVENT_TYPES = [
        ('concert', 'Concert'),
        ('corporate', 'Événement corporate'),
        ('wedding', 'Mariage'),
        ('conference', 'Conférence'),
        ('festival', 'Festival'),
        ('exhibition', 'Exposition'),
        ('show', 'Spectacle'),
        ('other', 'Autre'),
    ]
    STATUS_CHOICES = [
        ('inquiry', 'Demande'),
        ('quoted', 'Devis envoyé'),
        ('confirmed', 'Confirmé'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminé'),
        ('invoiced', 'Facturé'),
        ('cancelled', 'Annulé'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='audio_events')
    name = models.CharField('Nom événement', max_length=200)
    event_type = models.CharField('Type', max_length=20, choices=EVENT_TYPES, default='other')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, null=True, blank=True, related_name='audio_events')
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='inquiry')
    event_date = models.DateField('Date événement')
    setup_date = models.DateField('Date montage', null=True, blank=True)
    teardown_date = models.DateField('Date démontage', null=True, blank=True)
    start_time = models.TimeField('Heure début', null=True, blank=True)
    end_time = models.TimeField('Heure fin', null=True, blank=True)
    venue = models.CharField('Lieu', max_length=300, blank=True)
    venue_address = models.TextField('Adresse lieu', blank=True)
    expected_attendance = models.PositiveIntegerField('Jauge prévue', null=True, blank=True)
    description = models.TextField('Description', blank=True)
    technical_notes = models.TextField('Notes techniques', blank=True)
    estimated_amount = models.DecimalField('Montant prévu HT', max_digits=12, decimal_places=2, default=0)
    deposit_amount = models.DecimalField('Acompte', max_digits=12, decimal_places=2, default=0)
    notes = models.TextField('Notes', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Événement Audio'
        verbose_name_plural = 'Événements Audio'
        ordering = ['-event_date']

    def __str__(self):
        return f'{self.name} — {self.event_date}'


class EquipmentReservation(models.Model):
    """Réservation de matériel."""
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('confirmed', 'Confirmée'),
        ('checked_out', 'Sorti'),
        ('returned', 'Rendu'),
        ('cancelled', 'Annulée'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='equipment_reservations')
    event = models.ForeignKey(AudioEvent, on_delete=models.CASCADE, null=True, blank=True, related_name='reservations')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, null=True, blank=True, related_name='equipment_reservations')
    equipment = models.ForeignKey(Equipment, on_delete=models.PROTECT, related_name='reservations')
    quantity = models.PositiveIntegerField('Quantité', default=1)
    start_date = models.DateField('Début location')
    end_date = models.DateField('Fin location')
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='pending')
    daily_rate = models.DecimalField('Tarif jour HT', max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField('Montant total HT', max_digits=12, decimal_places=2, default=0)
    deposit_amount = models.DecimalField('Caution', max_digits=10, decimal_places=2, default=0)
    deposit_returned = models.BooleanField('Caution rendue', default=False)
    condition_out = models.TextField('État départ', blank=True)
    condition_in = models.TextField('État retour', blank=True)
    checked_out_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='checked_out')
    checked_in_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='checked_in')
    notes = models.TextField('Notes', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Réservation matériel'
        verbose_name_plural = 'Réservations matériel'
        ordering = ['-start_date']

    def __str__(self):
        return f'{self.equipment.name} — {self.start_date} au {self.end_date}'

    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days + 1

    def calculate_total(self):
        self.total_amount = self.daily_rate * self.quantity * self.duration_days
        self.save(update_fields=['total_amount'])


class Technician(models.Model):
    """Technicien audio/AV."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='technicians')
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField('Nom', max_length=100)
    specialties = models.CharField('Spécialités', max_length=300, blank=True)
    phone = models.CharField('Téléphone', max_length=20, blank=True)
    email = models.EmailField('Email', blank=True)
    day_rate = models.DecimalField('Tarif journée HT', max_digits=10, decimal_places=2, default=0)
    is_employee = models.BooleanField('Salarié', default=True)
    is_active = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Technicien'

    def __str__(self):
        return self.name


class EventTechnicianAssignment(models.Model):
    """Affectation technicien à un événement."""
    event = models.ForeignKey(AudioEvent, on_delete=models.CASCADE, related_name='technician_assignments')
    technician = models.ForeignKey(Technician, on_delete=models.CASCADE, related_name='event_assignments')
    role = models.CharField('Rôle', max_length=100, blank=True)
    start_datetime = models.DateTimeField('Début', null=True, blank=True)
    end_datetime = models.DateTimeField('Fin', null=True, blank=True)
    day_rate = models.DecimalField('Tarif journée HT', max_digits=10, decimal_places=2, default=0)
    is_confirmed = models.BooleanField('Confirmé', default=False)

    class Meta:
        verbose_name = 'Affectation technicien'

    def __str__(self):
        return f'{self.technician.name} — {self.event.name}'
