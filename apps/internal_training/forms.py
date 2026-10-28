from django import forms
from .models import TrainingCourse, TrainingChapter, TrainingPage, TrainingPageBlock


class TrainingCourseForm(forms.ModelForm):
    class Meta:
        model = TrainingCourse
        fields = ('title', 'description', 'cover_image', 'status', 'order')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'orion-input', 'placeholder': 'Ex : Accueil nouveaux salariés, Sécurité incendie…', 'autofocus': True}),
            'description': forms.Textarea(attrs={'class': 'orion-input', 'rows': 5, 'placeholder': 'Décrivez l\'objectif et le contenu de cette formation…'}),
            'status': forms.Select(attrs={'class': 'orion-select'}),
            'order': forms.NumberInput(attrs={'class': 'orion-input', 'min': 0}),
        }
        labels = {
            'title': 'Titre de la formation',
            'description': 'Description',
            'cover_image': 'Image de couverture',
            'status': 'Statut',
            'order': 'Ordre d\'affichage',
        }


class TrainingChapterForm(forms.ModelForm):
    class Meta:
        model = TrainingChapter
        fields = ('title', 'order')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'orion-input', 'placeholder': 'Titre du chapitre'}),
            'order': forms.NumberInput(attrs={'class': 'orion-input'}),
        }
        labels = {
            'title': 'Titre',
            'order': 'Ordre',
        }


class TrainingPageForm(forms.ModelForm):
    class Meta:
        model = TrainingPage
        fields = ('title', 'order', 'status')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'orion-input', 'placeholder': 'Titre de la page'}),
            'order': forms.NumberInput(attrs={'class': 'orion-input'}),
            'status': forms.Select(attrs={'class': 'orion-select'}),
        }
        labels = {
            'title': 'Titre',
            'order': 'Ordre',
            'status': 'Statut',
        }


class TrainingPageBlockForm(forms.ModelForm):
    class Meta:
        model = TrainingPageBlock
        fields = ('block_type', 'content', 'file', 'order')
        widgets = {
            'block_type': forms.Select(attrs={'class': 'orion-select'}),
            'content': forms.Textarea(attrs={'class': 'orion-input', 'rows': 4}),
            'order': forms.NumberInput(attrs={'class': 'orion-input'}),
        }
        labels = {
            'block_type': 'Type de bloc',
            'content': 'Contenu',
            'file': 'Fichier (image ou audio)',
            'order': 'Ordre',
        }
