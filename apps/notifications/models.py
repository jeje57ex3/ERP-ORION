"""
apps/notifications/models.py — Notifications internes ERP
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


NOTIFICATION_TYPES = [
    ('validation_pending', 'Validation en attente'),
    ('message_received', 'Message reçu'),
    ('quote_accepted', 'Devis accepté'),
    ('invoice_overdue', 'Facture en retard'),
    ('document_signed', 'Document signé'),
    ('project_updated', 'Chantier mis à jour'),
    ('stock_low', 'Stock faible'),
    ('web_order', 'Commande web reçue'),
    ('leave_request', 'Congé demandé'),
    ('expense_validated', 'Note de frais validée'),
    ('system', 'Système'),
    ('info', 'Information'),
    ('warning', 'Avertissement'),
    ('error', 'Erreur'),
]

PRIORITY_CHOICES = [
    ('low', 'Basse'),
    ('normal', 'Normale'),
    ('high', 'Haute'),
    ('urgent', 'Urgente'),
]


class Notification(models.Model):
    """Notification interne utilisateur ERP."""

    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name='Entreprise',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='erp_notifications',
        verbose_name='Utilisateur',
    )
    notification_type = models.CharField(
        'Type',
        max_length=50,
        choices=NOTIFICATION_TYPES,
        default='info',
    )
    priority = models.CharField(
        'Priorité',
        max_length=10,
        choices=PRIORITY_CHOICES,
        default='normal',
    )
    title = models.CharField('Titre', max_length=200)
    message = models.TextField('Message', blank=True)
    icon = models.CharField('Icône', max_length=50, default='bi-bell')
    icon_color = models.CharField('Couleur icône', max_length=20, default='primary')

    # Lien optionnel vers l'objet concerné
    link_url = models.CharField('URL lien', max_length=500, blank=True)
    link_label = models.CharField('Libellé lien', max_length=100, blank=True)

    # Module source
    source_module = models.CharField('Module source', max_length=50, blank=True)
    source_model = models.CharField('Modèle source', max_length=100, blank=True)
    source_id = models.PositiveIntegerField('ID source', null=True, blank=True)

    # Statut lecture
    is_read = models.BooleanField('Lu', default=False)
    read_at = models.DateTimeField('Lu le', null=True, blank=True)

    # Email
    email_sent = models.BooleanField('Email envoyé', default=False)
    email_sent_at = models.DateTimeField('Email envoyé le', null=True, blank=True)

    created_at = models.DateTimeField('Créée le', auto_now_add=True)

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', '-created_at'], name='notif_user_read_idx'),
            models.Index(fields=['company', '-created_at'], name='notif_company_idx'),
        ]

    def __str__(self):
        return f'[{self.get_notification_type_display()}] {self.title}'

    def mark_read(self):
        """Marque la notification comme lue."""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    @property
    def priority_badge_class(self):
        return {
            'low': 'secondary',
            'normal': 'info',
            'high': 'warning',
            'urgent': 'danger',
        }.get(self.priority, 'info')

    @property
    def type_icon(self):
        return {
            'validation_pending': 'bi-hourglass-split',
            'message_received': 'bi-chat-dots',
            'quote_accepted': 'bi-file-earmark-check',
            'invoice_overdue': 'bi-exclamation-triangle',
            'document_signed': 'bi-pen',
            'project_updated': 'bi-hammer',
            'stock_low': 'bi-box-seam',
            'web_order': 'bi-cart',
            'leave_request': 'bi-calendar-x',
            'expense_validated': 'bi-receipt',
            'system': 'bi-gear',
            'info': 'bi-info-circle',
            'warning': 'bi-exclamation-circle',
            'error': 'bi-x-circle',
        }.get(self.notification_type, self.icon)
