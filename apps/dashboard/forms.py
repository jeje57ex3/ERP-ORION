from django import forms
from .models import DashboardShortcut, UserDashboardWidget, DashboardUserPreference, DashboardProfile

ICON_CHOICES = [
    ('bi-star', 'Étoile'), ('bi-house', 'Accueil'), ('bi-people', 'Personnes'),
    ('bi-building', 'Bâtiment'), ('bi-cart', 'Panier'), ('bi-receipt', 'Facture'),
    ('bi-file-text', 'Document'), ('bi-calendar', 'Calendrier'), ('bi-clock', 'Horloge'),
    ('bi-gear', 'Paramètres'), ('bi-graph-up', 'Graphique'), ('bi-envelope', 'Email'),
    ('bi-chat', 'Message'), ('bi-bell', 'Notification'), ('bi-folder', 'Dossier'),
    ('bi-box', 'Boîte'), ('bi-truck', 'Camion'), ('bi-tools', 'Outils'),
    ('bi-cash', 'Argent'), ('bi-calculator', 'Calculatrice'), ('bi-headset', 'Support'),
    ('bi-briefcase', 'Mallette'), ('bi-person-badge', 'Badge'), ('bi-cone-striped', 'Chantier'),
    ('bi-shop', 'Boutique'), ('bi-bar-chart', 'Statistiques'), ('bi-trophy', 'Trophée'),
    ('bi-lightning', 'Éclair'), ('bi-plus-circle', 'Ajouter'), ('bi-search', 'Rechercher'),
]

COLOR_CHOICES = [
    ('#C6A15B', 'Or Orion'), ('#3A2A1A', 'Brun Orion'), ('#10B981', 'Vert'),
    ('#2563EB', 'Bleu'), ('#7C3AED', 'Violet'), ('#DC2626', 'Rouge'),
    ('#F59E0B', 'Ambre'), ('#0891B2', 'Cyan'), ('#DB2777', 'Rose'),
    ('#6B7280', 'Gris'), ('#0D9488', 'Teal'), ('#16A34A', 'Vert foncé'),
]


class DashboardShortcutForm(forms.ModelForm):
    icon = forms.ChoiceField(choices=ICON_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))
    color = forms.ChoiceField(choices=COLOR_CHOICES, widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = DashboardShortcut
        fields = [
            'label', 'description', 'icon', 'color',
            'target_type', 'target_url', 'url_name',
            'module_code', 'action_code', 'is_favorite', 'is_active',
        ]
        widgets = {
            'label': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Nouveau devis'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Description courte'}),
            'target_type': forms.Select(attrs={'class': 'form-select'}),
            'target_url': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '/sales/quotes/create/'}),
            'url_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'sales:quote_create'}),
            'module_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : sales'}),
            'action_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : create_quote'}),
            'is_favorite': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'label': 'Libellé', 'description': 'Description', 'icon': 'Icône',
            'color': 'Couleur', 'target_type': 'Type de cible',
            'target_url': 'URL directe', 'url_name': 'Nom URL Django',
            'module_code': 'Code module', 'action_code': 'Code action',
            'is_favorite': 'Marquer comme favori', 'is_active': 'Actif',
        }


class UserDashboardWidgetConfigForm(forms.ModelForm):
    class Meta:
        model = UserDashboardWidget
        fields = ['title', 'width', 'height', 'is_visible']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Titre personnalisé'}),
            'width': forms.Select(
                choices=[(3, '1/4'), (4, '1/3'), (6, '1/2'), (8, '2/3'), (9, '3/4'), (12, 'Pleine largeur')],
                attrs={'class': 'form-select'}
            ),
            'height': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 12}),
            'is_visible': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'title': 'Titre personnalisé', 'width': 'Largeur',
            'height': 'Hauteur', 'is_visible': 'Visible',
        }


class DashboardPreferenceForm(forms.ModelForm):
    class Meta:
        model = DashboardUserPreference
        exclude = ['company', 'user', 'created_at', 'updated_at']
        widgets = {
            'default_period': forms.Select(attrs={'class': 'form-select'}),
            'refresh_interval': forms.Select(attrs={'class': 'form-select'}),
            'show_welcome_message': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_kpi_cards': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_notifications': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_sidebar_shortcuts': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'compact_mode': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'auto_refresh': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class DashboardLayoutForm(forms.ModelForm):
    class Meta:
        model = DashboardProfile
        fields = ['layout_type', 'theme', 'name']
        widgets = {
            'layout_type': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'theme': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }
