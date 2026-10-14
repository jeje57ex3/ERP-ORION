from django.conf import settings
from django.db import models


class OrionAISettings(models.Model):
    PROVIDER_CHOICES = [
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic'),
        ('local', 'Local (Ollama)'),
        ('disabled', 'Désactivé'),
    ]

    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='ai_settings',
    )

    is_global = models.BooleanField(default=False)

    ai_enabled = models.BooleanField(default=True)

    # Le verrou local n'est pas un defaut mais une INTERDICTION. « Repondre
    # uniquement en local » est une propriete de confidentialite : les donnees
    # d'entreprise -- devis, clients, factures, sante systeme -- ne doivent
    # jamais quitter la machine. Un simple reglage par defaut se change par
    # inadvertance ; ici, choisir un fournisseur externe est refuse tant que
    # ce verrou est pose.
    local_only = models.BooleanField(
        default=True,
        verbose_name='Traitement local uniquement',
        help_text="Interdit tout fournisseur externe. Les données de "
                  "l'entreprise ne quittent jamais le serveur.",
    )

    default_provider = models.CharField(
        max_length=40,
        choices=PROVIDER_CHOICES,
        default='local',
    )

    default_model = models.CharField(
        max_length=120,
        default='qwen2.5:3b-instruct',
        help_text='Modele servi par Ollama sur ce serveur.',
    )

    temperature = models.DecimalField(max_digits=4, decimal_places=2, default=0.20)

    max_input_chars = models.PositiveIntegerField(default=20000)
    max_history_messages = models.PositiveIntegerField(default=20)

    # ─── Temps de réponse ────────────────────────────────────────────────────
    # Sur un petit modèle en CPU — le cas de l'appliance — le temps de réponse
    # se décompose en trois parts, et chacune a son réglage ici :
    #
    #   1. le CHARGEMENT du modèle en mémoire. Ollama le décharge après un
    #      délai d'inactivité ; la requête suivante attend alors plusieurs
    #      secondes qu'il remonte du disque. C'est ce qui rend l'assistant
    #      « parfois très lent » sans raison apparente.
    #   2. l'ÉVALUATION DU PROMPT, proportionnelle à sa longueur. C'est elle
    #      qui fait ralentir une conversation à mesure qu'elle avance.
    #   3. la GÉNÉRATION, proportionnelle à la longueur de la réponse.
    #
    # Les trois durées sont mesurées à chaque échange et conservées dans la
    # charge brute du message (voir LocalAIProvider) : le réglage se fait sur
    # des chiffres, pas sur une impression.
    keep_alive_minutes = models.PositiveIntegerField(
        default=30,
        verbose_name='Garder le modèle en mémoire (minutes)',
        help_text='Évite de le recharger depuis le disque à chaque question '
                  'après une période calme — c’est la cause la plus courante '
                  'des réponses très lentes. 0 = décharger aussitôt (libère '
                  'la mémoire, au prix de quelques secondes par question).',
    )

    max_output_tokens = models.PositiveIntegerField(
        default=600,
        verbose_name='Longueur maximale de la réponse (jetons)',
        help_text='Plafond de génération. Sans plafond, une réponse bavarde '
                  'se paie en secondes d’attente. 600 jetons ≈ 450 mots, '
                  'largement assez pour guider dans une interface.',
    )

    context_window_tokens = models.PositiveIntegerField(
        default=4096,
        verbose_name='Fenêtre de contexte (jetons)',
        help_text='Taille allouée au contexte. Plus grande, elle consomme '
                  'de la mémoire et ralentit chaque requête ; trop petite, '
                  'elle tronque les faits fournis au modèle.',
    )

    max_history_chars = models.PositiveIntegerField(
        default=4000,
        verbose_name='Historique transmis (caractères)',
        help_text='Budget de longueur pour les messages précédents, en plus '
                  'de leur nombre. C’est la longueur, non le nombre, qui '
                  'détermine le temps d’évaluation du prompt. 0 = aucun '
                  'plafond de longueur.',
    )

    allow_tools = models.BooleanField(default=True)
    allow_erp_read_tools = models.BooleanField(default=True)
    allow_erp_write_tools = models.BooleanField(default=False)

    allow_dangerous_actions = models.BooleanField(default=False)
    require_confirmation_for_write_actions = models.BooleanField(default=True)

    log_conversations = models.BooleanField(default=True)
    log_tool_calls = models.BooleanField(default=True)

    redact_sensitive_data = models.BooleanField(default=True)

    ai_name = models.CharField(max_length=120, default='Orion')

    system_prompt_extra = models.TextField(blank=True)

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orion_ai'
        verbose_name = 'Paramètres IA Orion'
        verbose_name_plural = 'Paramètres IA Orion'

    def __str__(self):
        if self.is_global:
            return 'Paramètres IA globaux Orion'
        return f'Paramètres IA — {self.company}'

    @classmethod
    def get_global(cls):
        obj, _ = cls.objects.get_or_create(
            is_global=True,
            company=None,
            defaults={'ai_enabled': True},
        )
        return obj

    @classmethod
    def get_for_company(cls, company):
        if company is None:
            return cls.get_global()
        obj, _ = cls.objects.get_or_create(
            company=company,
            is_global=False,
            defaults={'ai_enabled': True},
        )
        return obj


class OrionAIConversation(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('archived', 'Archivée'),
        ('deleted', 'Supprimée'),
    ]

    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='ai_conversations',
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_conversations',
    )

    title = models.CharField(max_length=220, default='Nouvelle conversation')

    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='active')

    context_module = models.CharField(
        max_length=80,
        blank=True,
        help_text='Exemple : orders, products, shop_settings, system_health',
    )

    brand_key = models.CharField(max_length=40, blank=True)

    metadata = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'orion_ai'
        ordering = ['-updated_at']

    def __str__(self):
        return self.title


class OrionAIMessage(models.Model):
    ROLE_CHOICES = [
        ('system', 'Système'),
        ('user', 'Utilisateur'),
        ('assistant', 'Assistant'),
        ('tool', 'Outil'),
    ]

    conversation = models.ForeignKey(
        OrionAIConversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )

    role = models.CharField(max_length=40, choices=ROLE_CHOICES)
    content = models.TextField(blank=True)

    provider = models.CharField(max_length=40, blank=True)
    model = models.CharField(max_length=120, blank=True)

    tool_name = models.CharField(max_length=120, blank=True)
    tool_call_id = models.CharField(max_length=180, blank=True)

    token_input = models.PositiveIntegerField(default=0)
    token_output = models.PositiveIntegerField(default=0)

    raw_payload = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'orion_ai'
        ordering = ['created_at']

    def __str__(self):
        return f'{self.role} — {self.conversation_id}'


class OrionAIToolCall(models.Model):
    STATUS_CHOICES = [
        ('planned', 'Planifié'),
        ('running', 'En cours'),
        ('success', 'Succès'),
        ('failed', 'Échec'),
        ('blocked', 'Bloqué'),
    ]

    conversation = models.ForeignKey(
        OrionAIConversation,
        on_delete=models.CASCADE,
        related_name='tool_calls',
    )

    message = models.ForeignKey(
        OrionAIMessage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tool_calls',
    )

    tool_name = models.CharField(max_length=120)
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='planned')

    arguments = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)

    error_message = models.TextField(blank=True)

    is_write_action = models.BooleanField(default=False)
    is_dangerous_action = models.BooleanField(default=False)

    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = 'orion_ai'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.tool_name} — {self.status}'


class OrionAIProposedAction(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('confirmed', 'Confirmée'),
        ('executed', 'Exécutée'),
        ('cancelled', 'Annulée'),
        ('failed', 'Échec'),
    ]

    conversation = models.ForeignKey(
        OrionAIConversation,
        on_delete=models.CASCADE,
        related_name='proposed_actions',
    )

    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)

    action_code = models.CharField(max_length=120)
    arguments = models.JSONField(default=dict, blank=True)

    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='pending')

    is_write_action = models.BooleanField(default=True)
    is_dangerous_action = models.BooleanField(default=False)

    requires_confirmation = models.BooleanField(default=True)

    created_by_ai = models.BooleanField(default=True)

    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='confirmed_ai_actions',
    )

    confirmed_at = models.DateTimeField(null=True, blank=True)
    executed_at = models.DateTimeField(null=True, blank=True)

    result = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'orion_ai'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.title} — {self.status}'


class OrionAIMemory(models.Model):
    SCOPE_CHOICES = [
        ('global', 'Global'),
        ('company', 'Entreprise'),
        ('user', 'Utilisateur'),
        ('brand', 'Marque'),
    ]

    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    brand_key = models.CharField(max_length=40, blank=True)

    scope = models.CharField(max_length=40, choices=SCOPE_CHOICES)

    key = models.CharField(max_length=120)
    value = models.TextField()

    is_active = models.BooleanField(default=True)
    is_sensitive = models.BooleanField(default=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_ai_memories',
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'orion_ai'
        unique_together = [
            ('company', 'user', 'brand_key', 'scope', 'key'),
        ]
        ordering = ['scope', 'key']

    def __str__(self):
        return f'{self.scope}:{self.key}'


class OrionAIAuditLog(models.Model):
    EVENT_CHOICES = [
        ('chat_message', 'Message IA'),
        ('tool_call', 'Appel outil'),
        ('action_proposed', 'Action proposée'),
        ('action_confirmed', 'Action confirmée'),
        ('action_executed', 'Action exécutée'),
        ('action_blocked', 'Action bloquée'),
        ('safety_block', 'Blocage sécurité'),
        ('settings_changed', 'Paramètres modifiés'),
    ]

    company = models.ForeignKey(
        'core.Company',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    event_type = models.CharField(max_length=80, choices=EVENT_CHOICES)

    title = models.CharField(max_length=220)
    description = models.TextField(blank=True)

    payload = models.JSONField(default=dict, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'orion_ai'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.event_type} — {self.title}'
