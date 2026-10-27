from django import forms
from django.utils.text import slugify

from .models import BuilderPage


class BuilderPageForm(forms.ModelForm):
    class Meta:
        model = BuilderPage
        fields = ['title', 'slug', 'is_homepage', 'meta_title', 'meta_description']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex : Page d\'accueil'}),
            'slug': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex-accueil'}),
            'meta_title': forms.TextInput(attrs={'class': 'form-control'}),
            'meta_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_homepage': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_slug(self):
        slug = self.cleaned_data.get('slug', '').strip()
        if not slug and self.cleaned_data.get('title'):
            slug = slugify(self.cleaned_data['title'])
        return slug
