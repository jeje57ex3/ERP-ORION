"""
apps/dashboard/models.py — Dashboard personnalisable Orion ERP
"""
from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Company


class DashboardProfile(models.Model):
    LAYOUT_TYPES = [
        ('grid', 'Grille'),
        ('compact', 'Compact'),
        ('large_cards', 'Grandes cartes'),
        ('two_columns', 'Deux colonnes'),
        ('three_columns', 'Trois colonnes'),
        ('role_based', 'Par rôle'),
    ]
    THEMES = [
        ('orion_luxury', 'Orion Luxe'),
        ('light', 'Clair'),
        ('dark', 'Sombre'),
        ('btp', 'BTP'),
        ('commerce', 'Commerce'),
        ('ecommerce', 'E-commerce'),
        ('minimal', 'Minimaliste'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='dashboard_profiles')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dashboard_profiles')
    name = models.CharField('Nom', max_length=100, default='Mon tableau de bord')
    description = models.TextField('Description', blank=True)
    is_default = models.BooleanField('Par défaut', default=True)
    layout_type = models.CharField('Disposition', max_length=20, choices=LAYOUT_TYPES, default='grid')
    theme = models.CharField('Thème', max_length=20, choices=THEMES, default='orion_luxury')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Profil dashboard'
        verbose_name_plural = 'Profils dashboard'

    def __str__(self):
        return f'{self.user.username} — {self.name}'


class DashboardWidget(models.Model):
    WIDGET_TYPES = [
        ('shortcut', 'Raccourcis'),
        ('list', 'Liste'),
        ('kpi', 'KPI'),
        ('chart', 'Graphique'),
        ('calendar', 'Calendrier'),
        ('task', 'Tâches'),
        ('notification', 'Notifications'),
        ('message', 'Messages'),
        ('document', 'Documents'),
        ('workflow', 'Workflow'),
        ('project', 'Projet'),
        ('finance', 'Finance'),
        ('support', 'Support'),
        ('alert', 'Alerte'),
        ('agenda', 'Agenda'),
        ('progress', 'Progression'),
        ('photo', 'Photos'),
        ('pipeline', 'Pipeline'),
        ('summary', 'Résumé'),
        ('note', 'Notes'),
        ('action', 'Actions rapides'),
        ('goal', 'Objectifs'),
        ('hr', 'RH'),
    ]

    name = models.CharField('Nom', max_length=100)
    code = models.CharField('Code', max_length=60, unique=True)
    description = models.TextField('Description', blank=True)
    module_code = models.CharField('Module', max_length=30, blank=True)
    widget_type = models.CharField('Type', max_length=20, choices=WIDGET_TYPES, default='list')
    icon = models.CharField('Icône Bootstrap', max_length=60, default='bi-grid')
    color = models.CharField('Couleur', max_length=7, default='#C6A15B')
    template_name = models.CharField('Template', max_length=200)
    default_width = models.PositiveSmallIntegerField('Largeur par défaut (col)', default=6)
    default_height = models.PositiveSmallIntegerField('Hauteur par défaut', default=4)
    is_active = models.BooleanField('Actif', default=True)
    requires_permission = models.BooleanField('Requiert permission', default=False)
    permission_code = models.CharField('Code permission', max_length=60, blank=True)
    order = models.PositiveIntegerField('Ordre catalogue', default=0)

    class Meta:
        verbose_name = 'Widget catalogue'
        verbose_name_plural = 'Widgets catalogue'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class UserDashboardWidget(models.Model):
    dashboard_profile = models.ForeignKey(DashboardProfile, on_delete=models.CASCADE, related_name='user_widgets')
    widget = models.ForeignKey(DashboardWidget, on_delete=models.CASCADE)
    title = models.CharField('Titre personnalisé', max_length=100, blank=True)
    position_x = models.PositiveSmallIntegerField('Position X', default=0)
    position_y = models.PositiveSmallIntegerField('Position Y', default=0)
    width = models.PositiveSmallIntegerField('Largeur (col)', default=6)
    height = models.PositiveSmallIntegerField('Hauteur', default=4)
    is_visible = models.BooleanField('Visible', default=True)
    settings = models.JSONField('Paramètres', default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Widget utilisateur'
        verbose_name_plural = 'Widgets utilisateur'
        ordering = ['position_y', 'position_x']

    def __str__(self):
        return f'{self.dashboard_profile.user.username} — {self.widget.name}'

    def get_display_title(self):
        return self.title or self.widget.name


class DashboardShortcut(models.Model):
    TARGET_TYPES = [
        ('url', 'URL directe'),
        ('module', 'Module ERP'),
        ('create_action', 'Action de création'),
        ('object_list', 'Liste d\'objets'),
        ('object_detail', 'Détail objet'),
        ('external_link', 'Lien externe'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='dashboard_shortcuts')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dashboard_shortcuts')
    label = models.CharField('Libellé', max_length=80)
    description = models.CharField('Description', max_length=200, blank=True)
    icon = models.CharField('Icône Bootstrap', max_length=60, default='bi-star')
    color = models.CharField('Couleur', max_length=7, default='#C6A15B')
    target_type = models.CharField('Type cible', max_length=20, choices=TARGET_TYPES, default='url')
    target_url = models.CharField('URL cible', max_length=500, blank=True)
    url_name = models.CharField('Nom URL Django', max_length=100, blank=True)
    module_code = models.CharField('Module', max_length=30, blank=True)
    action_code = models.CharField('Action', max_length=60, blank=True)
    order = models.PositiveIntegerField('Ordre', default=0)
    is_favorite = models.BooleanField('Favori', default=False)
    is_active = models.BooleanField('Actif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Raccourci'
        verbose_name_plural = 'Raccourcis'
        ordering = ['order', 'label']

    def __str__(self):
        return f'{self.user.username} — {self.label}'

    def get_resolved_url(self):
        if self.target_url:
            return self.target_url
        if self.url_name:
            try:
                from django.urls import reverse
                return reverse(self.url_name)
            except Exception:
                pass
        return '#'


class DashboardUserPreference(models.Model):
    PERIOD_CHOICES = [
        ('today', 'Aujourd\'hui'),
        ('week', 'Cette semaine'),
        ('month', 'Ce mois'),
        ('quarter', 'Ce trimestre'),
        ('year', 'Cette année'),
    ]
    REFRESH_CHOICES = [
        (0, 'Désactivée'),
        (60, '1 minute'),
        (300, '5 minutes'),
        (600, '10 minutes'),
        (1800, '30 minutes'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='dashboard_user_prefs')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dashboard_preferences')
    show_welcome_message = models.BooleanField('Message de bienvenue', default=True)
    show_kpi_cards = models.BooleanField('Afficher les KPI', default=True)
    show_notifications = models.BooleanField('Afficher les notifications', default=True)
    show_sidebar_shortcuts = models.BooleanField('Raccourcis dans la sidebar', default=True)
    default_period = models.CharField('Période par défaut', max_length=10, choices=PERIOD_CHOICES, default='week')
    compact_mode = models.BooleanField('Mode compact', default=False)
    auto_refresh = models.BooleanField('Actualisation automatique', default=False)
    refresh_interval = models.PositiveIntegerField('Intervalle (secondes)', choices=REFRESH_CHOICES, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Préférences dashboard'
        verbose_name_plural = 'Préférences dashboard'
        unique_together = [('company', 'user')]

    def __str__(self):
        return f'Préférences — {self.user.username}'


class DashboardRequestBox(models.Model):
    REQUEST_TYPES = [
        ('quote', 'Devis à traiter'),
        ('customer_request', 'Demande client'),
        ('leave', 'Demande de congé'),
        ('expense', 'Note de frais'),
        ('purchase_validation', 'Validation achat'),
        ('invoice_validation', 'Validation facture'),
        ('btp_request', 'Demande chantier'),
        ('sav', 'Demande SAV'),
        ('document_request', 'Demande document'),
        ('amendment', 'Demande d\'avenant'),
        ('reservation', 'Réserve client'),
        ('support_ticket', 'Ticket support'),
    ]
    STATUS_CHOICES = [
        ('new', 'Nouvelle'),
        ('waiting', 'En attente'),
        ('in_progress', 'En cours'),
        ('to_validate', 'À valider'),
        ('validated', 'Validée'),
        ('refused', 'Refusée'),
        ('done', 'Terminée'),
        ('archived', 'Archivée'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Basse'),
        ('normal', 'Normale'),
        ('high', 'Haute'),
        ('urgent', 'Urgente'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='dashboard_request_boxes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dashboard_request_boxes')
    request_type = models.CharField('Type', max_length=30, choices=REQUEST_TYPES)
    title = models.CharField('Titre', max_length=200)
    description = models.TextField('Description', blank=True)
    status = models.CharField('Statut', max_length=20, choices=STATUS_CHOICES, default='new')
    priority = models.CharField('Priorité', max_length=10, choices=PRIORITY_CHOICES, default='normal')
    related_module = models.CharField('Module lié', max_length=30, blank=True)
    related_object_id = models.PositiveIntegerField('ID objet', null=True, blank=True)
    target_url = models.CharField('URL', max_length=500, blank=True)
    due_date = models.DateField('Échéance', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Demande dashboard'
        verbose_name_plural = 'Demandes dashboard'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_request_type_display()} — {self.title}'

    def priority_badge_class(self):  # noqa (kept for template use)
        return {
            'low': 'bg-secondary',
            'normal': 'bg-info',
            'high': 'bg-warning',
            'urgent': 'bg-danger',
        }.get(self.priority, 'bg-secondary')

    def status_badge_class(self):
        return {
            'new': 'bg-primary',
            'waiting': 'bg-warning text-dark',
            'in_progress': 'bg-info',
            'to_validate': 'bg-warning text-dark',
            'validated': 'bg-success',
            'refused': 'bg-danger',
            'done': 'bg-success',
            'archived': 'bg-secondary',
        }.get(self.status, 'bg-secondary')


class DashboardPersonalNote(models.Model):
    COLOR_CHOICES = [
        ('#FEF3C7', 'Jaune'),
        ('#DCFCE7', 'Vert'),
        ('#DBEAFE', 'Bleu'),
        ('#FCE7F3', 'Rose'),
        ('#F3F4F6', 'Gris'),
        ('#FEE2E2', 'Rouge'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='dashboard_notes')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dashboard_notes')
    title = models.CharField('Titre', max_length=100, blank=True)
    content = models.TextField('Contenu')
    color = models.CharField('Couleur', max_length=7, choices=COLOR_CHOICES, default='#FEF3C7')
    is_pinned = models.BooleanField('Épinglée', default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Note personnelle'
        verbose_name_plural = 'Notes personnelles'
        ordering = ['-is_pinned', '-updated_at']

    def __str__(self):
        return f'{self.user.username} — {self.title or "Note"}'


class DashboardGoal(models.Model):
    PERIOD_CHOICES = [
        ('day', 'Jour'),
        ('week', 'Semaine'),
        ('month', 'Mois'),
        ('quarter', 'Trimestre'),
        ('year', 'Année'),
    ]
    STATUS_CHOICES = [
        ('active', 'En cours'),
        ('achieved', 'Atteint'),
        ('failed', 'Non atteint'),
        ('paused', 'Suspendu'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='dashboard_goals')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='dashboard_goals')
    title = models.CharField('Objectif', max_length=200)
    target_value = models.DecimalField('Valeur cible', max_digits=12, decimal_places=2)
    current_value = models.DecimalField('Valeur actuelle', max_digits=12, decimal_places=2, default=0)
    unit = models.CharField('Unité', max_length=30, default='')
    period = models.CharField('Période', max_length=10, choices=PERIOD_CHOICES, default='month')
    status = models.CharField('Statut', max_length=10, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Objectif personnel'
        verbose_name_plural = 'Objectifs personnels'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.user.username} — {self.title}'

    def progress_pct(self):
        if not self.target_value:
            return 0
        return min(100, int(self.current_value / self.target_value * 100))
