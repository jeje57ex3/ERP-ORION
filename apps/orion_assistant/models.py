from django.db import models
from django.conf import settings
from apps.core.models import Company


class AssistantConversation(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='assistant_conversations')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assistant_conversations')
    title = models.CharField(max_length=255, blank=True)
    context_module = models.CharField(max_length=80, blank=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orion_assistant'
        verbose_name = 'Conversation assistant'
        verbose_name_plural = 'Conversations assistant'
        ordering = ['-updated_at']
        indexes = [models.Index(fields=['company', 'user', 'is_archived'])]

    def __str__(self):
        return self.title or f'Conversation #{self.pk}'


class AssistantMessage(models.Model):
    ROLE_CHOICES = [
        ('user', 'Utilisateur'),
        ('assistant', 'Orion'),
        ('system', 'Système'),
    ]
    conversation = models.ForeignKey(
        AssistantConversation, on_delete=models.CASCADE, related_name='messages'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    tokens_used = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'orion_assistant'
        verbose_name = 'Message assistant'
        verbose_name_plural = 'Messages assistant'
        ordering = ['created_at']

    def __str__(self):
        return f'[{self.role}] {self.content[:60]}'
