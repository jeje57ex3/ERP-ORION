from django.db import models
from django.conf import settings
from apps.core.models import Company

SKIN_TYPE_CHOICES = [
    ('normal', 'Normale'), ('dry', 'Sèche'), ('oily', 'Grasse'),
    ('combination', 'Mixte'), ('sensitive', 'Sensible'), ('unknown', 'Non renseigné'),
]

HAIR_TYPE_CHOICES = [
    ('straight', 'Lisse'), ('wavy', 'Ondulé'), ('curly', 'Bouclé'),
    ('coily', 'Crépu'), ('fine', 'Fin'), ('thick', 'Épais'), ('unknown', 'Non renseigné'),
]

RECOMMENDATION_TYPE_CHOICES = [
    ('product', 'Produit'), ('routine', 'Routine'), ('treatment', 'Soin'),
    ('appointment', 'Rendez-vous'), ('tip', 'Conseil'),
]


class BeautyProfile(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='lunea_beauty_profiles')
    brand_key = models.CharField(max_length=40, default='lunea')
    customer = models.OneToOneField(
        'crm.Customer', on_delete=models.CASCADE, related_name='lunea_beauty_profile',
    )
    skin_type = models.CharField(max_length=30, choices=SKIN_TYPE_CHOICES, default='unknown')
    hair_type = models.CharField(max_length=30, choices=HAIR_TYPE_CHOICES, default='unknown')
    allergies = models.JSONField(default=list, blank=True)
    intolerances = models.JSONField(default=list, blank=True)
    preferred_brands = models.JSONField(default=list, blank=True)
    preferred_ingredients = models.JSONField(default=list, blank=True)
    avoided_ingredients = models.JSONField(default=list, blank=True)
    skin_concerns = models.JSONField(default=list, blank=True)
    hair_concerns = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    last_appointment_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='created_lunea_profiles',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'lunea_beauty_profile'
        verbose_name = 'Profil beauté Lunea'
        verbose_name_plural = 'Profils beauté Lunea'
        ordering = ['-updated_at']
        indexes = [models.Index(fields=['company', 'brand_key'])]

    def __str__(self):
        return f'Profil Lunea — {self.customer}'


class BeautyRecommendation(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='lunea_recommendations')
    profile = models.ForeignKey(BeautyProfile, on_delete=models.CASCADE, related_name='recommendations')
    recommendation_type = models.CharField(max_length=40, choices=RECOMMENDATION_TYPE_CHOICES, default='product')
    product_name = models.CharField(max_length=180)
    brand = models.CharField(max_length=100, blank=True)
    reason = models.TextField()
    score = models.FloatField(default=0.8)
    is_applied = models.BooleanField(default=False)
    applied_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'lunea_beauty_profile'
        verbose_name = 'Recommandation beauté'
        verbose_name_plural = 'Recommandations beauté'
        ordering = ['-score', '-created_at']

    def __str__(self):
        return f'{self.product_name} → {self.profile.customer}'
