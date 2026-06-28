from django.db import models
from apps.core.models import Company


SCORE_TYPE_CHOICES = [
    ('loyalty', 'Fidélité'),
    ('risk', 'Risque départ'),
    ('payment', 'Comportement paiement'),
    ('potential', 'Potentiel'),
    ('engagement', 'Engagement'),
    ('overall', 'Score global'),
]

EVENT_TYPE_CHOICES = [
    ('order', 'Commande'),
    ('quote', 'Devis'),
    ('invoice', 'Facture'),
    ('payment', 'Paiement'),
    ('support', 'Ticket support'),
    ('message', 'Message'),
    ('portal_login', 'Connexion portail'),
    ('document', 'Document'),
    ('note', 'Note interne'),
    ('alert', 'Alerte'),
    ('email', 'Email'),
    ('call', 'Appel'),
    ('visit', 'Visite'),
    ('loyalty', 'Points fidélité'),
    ('custom', 'Événement personnalisé'),
]


class CustomerScore(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='customer_scores')
    customer = models.ForeignKey('crm.Customer', on_delete=models.CASCADE, related_name='scores')
    brand_key = models.CharField(max_length=40, blank=True)
    score_type = models.CharField(max_length=80, choices=SCORE_TYPE_CHOICES)
    score = models.DecimalField(max_digits=8, decimal_places=2)
    label = models.CharField(max_length=80, blank=True)
    explanation = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'customer_360'
        verbose_name = 'Score client'
        verbose_name_plural = 'Scores clients'
        unique_together = [('company', 'customer', 'score_type', 'brand_key')]
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.customer} — {self.get_score_type_display()} : {self.score}'


class CustomerTimelineEvent(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='customer_timeline_events')
    customer = models.ForeignKey('crm.Customer', on_delete=models.CASCADE, related_name='timeline_events')
    brand_key = models.CharField(max_length=40, blank=True)
    event_type = models.CharField(max_length=80, choices=EVENT_TYPE_CHOICES)
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    related_object_type = models.CharField(max_length=80, blank=True)
    related_object_id = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'customer_360'
        verbose_name = 'Événement timeline client'
        verbose_name_plural = 'Événements timeline clients'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['company', 'customer', 'created_at']),
        ]

    def __str__(self):
        return f'{self.customer} — {self.title}'
