"""
apps/configurator/models.py — Moteur de configurateur métier générique
(NÉOSTRUCTURA pour l'instant, conçu pour être réutilisable par d'autres
entreprises sans code supplémentaire — voir docstring du module engine).

Principe : aucune règle de prix, de durée ou de question n'est codée en
Python. Tout est donné (ServiceDomain, ServiceCategory, ConfiguratorQuestion,
MaterialRequirement, LaborRule, TravelRule, PricingCoefficient, MarginRule,
DiagnosticScenario) et gérable depuis l'admin Django. Le catalogue prix reste
`apps.btp.models.ElectricityPriceLibrary` — ces modèles s'y RÉFÈRENT, ne le
dupliquent pas.

Isolation multi-tenant : les entités de premier niveau (interrogées
directement par entreprise depuis l'API/l'admin) utilisent
`apps.core.managers.CompanyBaseModel`. Les entités enfants (question, option,
exigence matériel) n'ont pas leur propre `company` — elles héritent du
scope de leur parent (comme `GuidedQuoteEstimateItem` n'a pas de company
propre) pour éviter tout risque de désynchronisation.
"""
from django.conf import settings
from django.db import models

from apps.core.managers import CompanyBaseModel
from apps.btp.models import ElectricityPriceLibrary, GuidedQuoteRequest


CONFIDENCE_CHOICES = [
    ('high', 'Élevée — estimation précise'),
    ('medium', 'Moyenne — fourchette à confirmer'),
    ('low', 'Faible — fourchette large'),
    ('diagnostic_required', 'Diagnostic obligatoire'),
]


# ─── DOMAINES & PRESTATIONS ────────────────────────────────────────────────────

class ServiceDomain(CompanyBaseModel):
    """Grand domaine métier proposé dans le configurateur (Électricité,
    Informatique & Réseaux, BTP / Rénovation...)."""
    code = models.SlugField('Code', max_length=40)
    name = models.CharField('Nom', max_length=120)
    description = models.CharField('Description courte', max_length=250, blank=True)
    icon = models.CharField('Icône (emoji ou classe)', max_length=20, blank=True, default='🔧')
    order = models.PositiveIntegerField('Ordre', default=0)

    class Meta(CompanyBaseModel.Meta):
        verbose_name = 'Domaine de service'
        verbose_name_plural = 'Domaines de service'
        ordering = ['order', 'name']
        unique_together = [('company', 'code')]

    def __str__(self):
        return self.name


class ServiceCategory(CompanyBaseModel):
    """Un besoin concret dans un domaine (« Dépannage électrique », « Wi-Fi
    faible dans certaines pièces »...). C'est la maille à laquelle se
    rattachent questions, matériel et règles de diagnostic."""
    INTERVENTION_TYPE_CHOICES = GuidedQuoteRequest.REQUEST_TYPE_CHOICES

    domain = models.ForeignKey(ServiceDomain, on_delete=models.CASCADE, related_name='categories')
    code = models.SlugField('Code', max_length=50)
    name = models.CharField('Nom', max_length=150)
    short_description = models.CharField('Description courte', max_length=250, blank=True)
    intervention_type = models.CharField(
        'Type d\'intervention', max_length=30, choices=INTERVENTION_TYPE_CHOICES, default='depannage',
    )

    requires_diagnostic = models.BooleanField('Diagnostic obligatoire', default=False)
    confidence_level = models.CharField(
        'Niveau de confiance par défaut', max_length=20, choices=CONFIDENCE_CHOICES, default='medium',
    )
    duration_min_hours = models.DecimalField('Durée min (h)', max_digits=6, decimal_places=2, default=1)
    duration_avg_hours = models.DecimalField('Durée moyenne (h)', max_digits=6, decimal_places=2, default=1)
    duration_max_hours = models.DecimalField('Durée max (h)', max_digits=6, decimal_places=2, default=2)
    estimate_width_pct = models.PositiveIntegerField(
        'Largeur de fourchette (%)', default=15,
        help_text='Écart appliqué autour du prix conseillé pour construire min/max, en plus des prix min/max du matériel.',
    )
    danger_alert = models.BooleanField(
        'Alerte danger possible', default=False,
        help_text='Affiche un avertissement de sécurité immédiat côté client si un scénario de diagnostic dangereux est détecté.',
    )
    requires_photo_hint = models.BooleanField('Suggérer une photo', default=False)
    order = models.PositiveIntegerField('Ordre', default=0)

    class Meta(CompanyBaseModel.Meta):
        verbose_name = 'Prestation configurable'
        verbose_name_plural = 'Prestations configurables'
        ordering = ['domain__order', 'order', 'name']
        unique_together = [('domain', 'code')]

    def __str__(self):
        return f'{self.domain.name} — {self.name}'


# ─── QUESTIONS CONDITIONNELLES ────────────────────────────────────────────────

class ConfiguratorQuestion(models.Model):
    """Une question du parcours. `display_condition` détermine si elle est
    affichée compte tenu des réponses déjà données — c'est ce qui rend le
    configurateur adaptatif (pas de formulaire à 50 champs d'un coup).

    Format de `display_condition` (vide = toujours affichée) :
        {"question": "<identifier>", "equals": <valeur>}
        {"question": "<identifier>", "in": [<valeurs>]}
        {"question": "<identifier>", "truthy": true}
    """
    QUESTION_TYPE_CHOICES = [
        ('single_choice', 'Choix unique'), ('multi_choice', 'Choix multiple'),
        ('number', 'Nombre'), ('text', 'Texte'),
        ('address', 'Adresse'), ('zip_code', 'Code postal'),
        ('photo', 'Photo'), ('file', 'Fichier'),
        ('boolean', 'Oui / Non'), ('slider', 'Curseur'),
        ('surface', 'Surface (m²)'), ('distance', 'Distance'),
    ]

    service = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, related_name='questions')
    identifier = models.SlugField('Identifiant', max_length=60)
    label = models.CharField('Question', max_length=250)
    help_text = models.CharField('Texte d\'aide', max_length=250, blank=True)
    question_type = models.CharField('Type', max_length=20, choices=QUESTION_TYPE_CHOICES)
    order = models.PositiveIntegerField('Ordre', default=0)
    is_required = models.BooleanField('Obligatoire', default=True)
    display_condition = models.JSONField('Condition d\'affichage', default=dict, blank=True)

    impacts_diagnostic = models.BooleanField('Impacte le diagnostic', default=False)
    impacts_material = models.BooleanField('Impacte le matériel', default=False)
    impacts_duration = models.BooleanField('Impacte la durée', default=False)
    impacts_price = models.BooleanField('Impacte le prix', default=False)

    class Meta:
        ordering = ['service', 'order']
        unique_together = [('service', 'identifier')]
        verbose_name = 'Question du configurateur'
        verbose_name_plural = 'Questions du configurateur'

    def __str__(self):
        return f'{self.service.code} · {self.identifier}'


class ConfiguratorQuestionOption(models.Model):
    """Option pour une question à choix (unique ou multiple)."""
    question = models.ForeignKey(ConfiguratorQuestion, on_delete=models.CASCADE, related_name='options')
    value = models.SlugField('Valeur', max_length=60)
    label = models.CharField('Libellé', max_length=200)
    order = models.PositiveIntegerField('Ordre', default=0)

    class Meta:
        ordering = ['question', 'order']
        unique_together = [('question', 'value')]
        verbose_name = 'Option de question'
        verbose_name_plural = 'Options de question'

    def __str__(self):
        return f'{self.question.identifier} = {self.value}'


# ─── MATÉRIEL & RÈGLES DE CHIFFRAGE ────────────────────────────────────────────

class MaterialRequirement(models.Model):
    """Relie une prestation à un poste de `ElectricityPriceLibrary`, avec une
    quantité fixe ou dérivée d'une réponse numérique (ex: « nombre de
    prises »). Ne duplique jamais le prix — seule la quantité est calculée ici."""
    QUANTITY_SOURCE_CHOICES = [('fixed', 'Quantité fixe'), ('from_answer', 'Depuis une réponse')]

    service = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, related_name='material_requirements')
    price_item = models.ForeignKey(ElectricityPriceLibrary, on_delete=models.CASCADE, related_name='+')
    quantity_source = models.CharField('Source de la quantité', max_length=15, choices=QUANTITY_SOURCE_CHOICES, default='fixed')
    fixed_quantity = models.DecimalField('Quantité fixe', max_digits=8, decimal_places=2, default=1)
    quantity_answer = models.ForeignKey(
        ConfiguratorQuestion, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
        verbose_name='Question source de quantité',
        help_text='Question de type "Nombre" ou "Surface" dont la réponse donne la quantité.',
    )
    quantity_multiplier = models.DecimalField('Multiplicateur', max_digits=6, decimal_places=2, default=1)
    applies_when = models.JSONField(
        'Condition d\'inclusion', default=dict, blank=True,
        help_text='Même format que display_condition — vide = toujours inclus si quantité > 0.',
    )
    order = models.PositiveIntegerField('Ordre', default=0)

    class Meta:
        ordering = ['service', 'order']
        verbose_name = 'Matériel requis'
        verbose_name_plural = 'Matériel requis'

    def __str__(self):
        return f'{self.service.code} · {self.price_item.name}'


class LaborRule(CompanyBaseModel):
    RATE_TYPE_CHOICES = [
        ('normal', 'Normal'), ('urgent', 'Urgence'),
        ('night', 'Nuit'), ('weekend', 'Week-end'),
    ]
    domain = models.ForeignKey(
        ServiceDomain, on_delete=models.CASCADE, null=True, blank=True, related_name='labor_rules',
        help_text='Vide = s\'applique à tous les domaines.',
    )
    rate_type = models.CharField('Type de tarif', max_length=10, choices=RATE_TYPE_CHOICES, default='normal')
    label = models.CharField('Libellé', max_length=120, blank=True)
    hourly_rate = models.DecimalField('Taux horaire HT', max_digits=8, decimal_places=2)

    class Meta(CompanyBaseModel.Meta):
        verbose_name = 'Tarif main-d\'œuvre'
        verbose_name_plural = 'Tarifs main-d\'œuvre'
        ordering = ['company', 'domain_id', 'rate_type']
        unique_together = [('company', 'domain', 'rate_type')]

    def __str__(self):
        scope = self.domain.name if self.domain_id else 'Tous domaines'
        return f'{scope} — {self.get_rate_type_display()} ({self.hourly_rate} €/h)'


class TravelRule(CompanyBaseModel):
    zone_code = models.CharField('Code zone', max_length=20)
    zone_label = models.CharField('Libellé zone', max_length=120)
    flat_fee = models.DecimalField('Forfait déplacement HT', max_digits=8, decimal_places=2, default=0)
    per_km_fee = models.DecimalField('€/km au-delà (optionnel)', max_digits=6, decimal_places=2, null=True, blank=True)
    urgency_surcharge_pct = models.DecimalField('Majoration urgence %', max_digits=5, decimal_places=2, default=0)
    is_default = models.BooleanField('Zone par défaut', default=False)
    order = models.PositiveIntegerField('Ordre', default=0)

    class Meta(CompanyBaseModel.Meta):
        verbose_name = 'Zone de déplacement'
        verbose_name_plural = 'Zones de déplacement'
        ordering = ['company', 'order']
        unique_together = [('company', 'zone_code')]

    def __str__(self):
        return f'{self.zone_label} ({self.flat_fee} €)'


class PricingCoefficient(CompanyBaseModel):
    COEFFICIENT_TYPE_CHOICES = [
        ('urgency', 'Urgence'), ('difficulty', 'Difficulté'),
        ('night', 'Nuit'), ('weekend', 'Week-end'),
    ]
    coefficient_type = models.CharField('Type', max_length=15, choices=COEFFICIENT_TYPE_CHOICES)
    code = models.SlugField('Code', max_length=40)
    label = models.CharField('Libellé', max_length=120)
    multiplier = models.DecimalField('Coefficient multiplicateur', max_digits=5, decimal_places=3, default=1)
    domain = models.ForeignKey(
        ServiceDomain, on_delete=models.CASCADE, null=True, blank=True, related_name='coefficients',
        help_text='Vide = s\'applique à tous les domaines.',
    )

    class Meta(CompanyBaseModel.Meta):
        verbose_name = 'Coefficient tarifaire'
        verbose_name_plural = 'Coefficients tarifaires'
        ordering = ['company', 'coefficient_type', 'code']
        unique_together = [('company', 'coefficient_type', 'code', 'domain')]

    def __str__(self):
        return f'{self.get_coefficient_type_display()} · {self.label} (×{self.multiplier})'


class MarginRule(CompanyBaseModel):
    """Marge STRICTEMENT interne — jamais sérialisée vers le frontend public.
    Résolution : catégorie > domaine > globale (la plus spécifique gagne)."""
    SCOPE_CHOICES = [('global', 'Globale'), ('domain', 'Par domaine'), ('category', 'Par prestation')]

    scope_type = models.CharField('Portée', max_length=10, choices=SCOPE_CHOICES, default='global')
    domain = models.ForeignKey(ServiceDomain, on_delete=models.CASCADE, null=True, blank=True, related_name='margin_rules')
    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, null=True, blank=True, related_name='margin_rules')
    margin_percent = models.DecimalField('Marge %', max_digits=6, decimal_places=2)

    class Meta(CompanyBaseModel.Meta):
        verbose_name = 'Règle de marge'
        verbose_name_plural = 'Règles de marge'
        ordering = ['company', 'scope_type']

    def __str__(self):
        if self.scope_type == 'category' and self.category_id:
            return f'{self.category.name} — {self.margin_percent}%'
        if self.scope_type == 'domain' and self.domain_id:
            return f'{self.domain.name} — {self.margin_percent}%'
        return f'Marge globale — {self.margin_percent}%'


# ─── DIAGNOSTIC ────────────────────────────────────────────────────────────────

class DiagnosticScenario(models.Model):
    """Pour les prestations à diagnostic obligatoire : hypothèses, niveau de
    confiance, mots-clés de danger. Le client ne doit jamais recevoir un
    diagnostic présenté comme confirmé — voir services/diagnostic.py."""
    service = models.OneToOneField(ServiceCategory, on_delete=models.CASCADE, related_name='diagnostic_scenario')
    hypotheses = models.JSONField(
        'Hypothèses possibles', default=list, blank=True,
        help_text='Liste de {"label": "...", "likelihood": "high|medium|low"}.',
    )
    diagnostic_min_hours = models.DecimalField('Diagnostic min (h)', max_digits=5, decimal_places=2, default=0.5)
    diagnostic_avg_hours = models.DecimalField('Diagnostic moyen (h)', max_digits=5, decimal_places=2, default=1)
    diagnostic_max_hours = models.DecimalField('Diagnostic max (h)', max_digits=5, decimal_places=2, default=1.5)
    danger_keywords = models.JSONField(
        'Mots-clés déclenchant une alerte danger', default=list, blank=True,
        help_text='Ex: ["fumée", "étincelles", "odeur de brûlé"] — recherchés dans les réponses texte libres.',
    )
    safety_message = models.TextField(
        'Message de sécurité', blank=True,
        default='Ceci concerne potentiellement un risque électrique. Coupez le disjoncteur concerné si possible '
                'et contactez-nous immédiatement — n\'intervenez pas vous-même.',
    )

    class Meta:
        verbose_name = 'Scénario de diagnostic'
        verbose_name_plural = 'Scénarios de diagnostic'

    def __str__(self):
        return f'Diagnostic — {self.service.name}'


# ─── RÉSUMÉ INTERNE (jamais exposé au frontend) ────────────────────────────────

class ConfiguratorSubmission(models.Model):
    """Extension de GuidedQuoteRequest portant tout ce que l'ERP doit savoir
    et que le client ne voit jamais : coûts, marge, confiance, hypothèses,
    besoin de validation humaine. GuidedQuoteRequest reste le pivot connu du
    CRM/BTP/portail — on ne le modifie pas, on l'étend proprement (cf. §7 du
    cahier des charges : ne pas modifier brutalement un modèle historique)."""
    request = models.OneToOneField(GuidedQuoteRequest, on_delete=models.CASCADE, related_name='configurator_submission')
    domain = models.ForeignKey(ServiceDomain, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    service = models.ForeignKey(ServiceCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    confidence_level = models.CharField('Niveau de confiance', max_length=20, choices=CONFIDENCE_CHOICES, default='medium')
    diagnostic_required = models.BooleanField('Diagnostic obligatoire', default=False)
    hypotheses = models.JSONField('Hypothèses retenues', default=list, blank=True)
    danger_detected = models.BooleanField('Danger détecté', default=False)

    human_validation_required = models.BooleanField('Validation humaine requise', default=False)
    human_validation_done = models.BooleanField('Validation humaine effectuée', default=False)
    human_validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+',
    )
    human_validated_at = models.DateTimeField(null=True, blank=True)

    cost_material = models.DecimalField('Coût matériel HT', max_digits=12, decimal_places=2, default=0)
    cost_labor = models.DecimalField('Coût main-d\'œuvre HT', max_digits=12, decimal_places=2, default=0)
    cost_travel = models.DecimalField('Coût déplacement HT', max_digits=12, decimal_places=2, default=0)
    cost_price = models.DecimalField('Coût de revient HT', max_digits=12, decimal_places=2, default=0)
    margin_percent_applied = models.DecimalField('Marge appliquée %', max_digits=6, decimal_places=2, default=0)
    margin_amount = models.DecimalField('Marge HT', max_digits=12, decimal_places=2, default=0)
    recommended_price = models.DecimalField('Prix conseillé HT', max_digits=12, decimal_places=2, default=0)

    raw_answers_snapshot = models.JSONField('Copie des réponses au calcul', default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Résumé interne configurateur'
        verbose_name_plural = 'Résumés internes configurateur'

    def __str__(self):
        return f'Résumé interne — {self.request.reference}'
