"""
apps/support/models.py — Tickets, SAV, Réclamations
"""
from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Company
from apps.crm.models import Customer


class Ticket(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Basse'),
        ('medium', 'Normale'),
        ('high', 'Haute'),
        ('critical', 'Critique'),
    ]
    STATUS_CHOICES = [
        ('open', 'Ouvert'),
        ('in_progress', 'En cours'),
        ('waiting', 'En attente client'),
        ('resolved', 'Résolu'),
        ('closed', 'Fermé'),
        ('cancelled', 'Annulé'),
    ]
    TYPE_CHOICES = [
        ('support', 'Support technique'),
        ('claim', 'Réclamation'),
        ('sav', 'SAV'),
        ('incident', 'Incident'),
        ('info', 'Demande d\'information'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='tickets')
    number = models.CharField('Numéro', max_length=20, blank=True)
    ticket_type = models.CharField('Type', max_length=20, choices=TYPE_CHOICES, default='support')
    subject = models.CharField('Sujet', max_length=300)
    description = models.TextField('Description')
    priority = models.CharField('Priorité', max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='open')
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='tickets')
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tickets')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_tickets')
    resolved_at = models.DateTimeField('Résolu le', null=True, blank=True)
    resolution_notes = models.TextField('Notes résolution', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Ticket'
        verbose_name_plural = 'Tickets'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.number or "TKT"} — {self.subject}'


class TicketMessage(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    message = models.TextField('Message')
    is_internal = models.BooleanField('Note interne', default=False)
    attachment = models.FileField('Pièce jointe', upload_to='tickets/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Message ticket {self.ticket.number}'
