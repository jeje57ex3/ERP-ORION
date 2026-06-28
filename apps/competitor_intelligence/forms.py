"""
apps/competitor_intelligence/forms.py — Formulaires analyse concurrentielle
"""
from django import forms
from .models import (
    Competitor, CompetitorSite, CompetitorProduct,
    CompetitorAdvantage, CompetitorTrafficEstimate,
)


class CompetitorForm(forms.ModelForm):
    class Meta:
        model  = Competitor
        fields = ['name', 'website_url', 'industry', 'country', 'description', 'logo', 'is_active']
        widgets = {
            'name':        forms.TextInput(attrs={'class': 'form-control'}),
            'website_url': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'}),
            'industry':    forms.TextInput(attrs={'class': 'form-control'}),
            'country':     forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active':   forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CompetitorSiteForm(forms.ModelForm):
    class Meta:
        model  = CompetitorSite
        fields = ['site_url', 'site_type', 'tracking_enabled', 'scan_frequency', 'robots_policy', 'notes']
        widgets = {
            'site_url':        forms.URLInput(attrs={'class': 'form-control'}),
            'site_type':       forms.Select(attrs={'class': 'form-select'}),
            'scan_frequency':  forms.Select(attrs={'class': 'form-select'}),
            'robots_policy':   forms.Select(attrs={'class': 'form-select'}),
            'notes':           forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'tracking_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CompetitorProductForm(forms.ModelForm):
    class Meta:
        model  = CompetitorProduct
        fields = ['name', 'brand', 'category', 'product_url', 'price', 'currency',
                  'old_price', 'discount_percent', 'availability', 'description']
        widgets = {
            'name':             forms.TextInput(attrs={'class': 'form-control'}),
            'brand':            forms.TextInput(attrs={'class': 'form-control'}),
            'category':         forms.TextInput(attrs={'class': 'form-control'}),
            'product_url':      forms.URLInput(attrs={'class': 'form-control'}),
            'price':            forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'currency':         forms.TextInput(attrs={'class': 'form-control', 'value': 'EUR'}),
            'old_price':        forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'discount_percent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'availability':     forms.Select(attrs={'class': 'form-select'}),
            'description':      forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class CompetitorAdvantageForm(forms.ModelForm):
    class Meta:
        model  = CompetitorAdvantage
        fields = ['title', 'description', 'advantage_type', 'score', 'source_url']
        widgets = {
            'title':          forms.TextInput(attrs={'class': 'form-control'}),
            'description':    forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'advantage_type': forms.Select(attrs={'class': 'form-select'}),
            'score':          forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 10}),
            'source_url':     forms.URLInput(attrs={'class': 'form-control'}),
        }


class TrafficEstimateForm(forms.ModelForm):
    class Meta:
        model  = CompetitorTrafficEstimate
        fields = ['estimated_monthly_visitors', 'traffic_source', 'confidence_score', 'source_type']
        widgets = {
            'estimated_monthly_visitors': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'traffic_source':             forms.TextInput(attrs={'class': 'form-control'}),
            'confidence_score':           forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 10}),
            'source_type':                forms.Select(attrs={'class': 'form-select'}),
        }


class CSVImportForm(forms.Form):
    csv_file = forms.FileField(
        label='Fichier CSV',
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv'}),
    )
    competitor = forms.ChoiceField(
        label='Concurrent cible',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, competitors=None, **kwargs):
        super().__init__(*args, **kwargs)
        if competitors:
            self.fields['competitor'].choices = [(c.pk, c.name) for c in competitors]


class ComparisonForm(forms.Form):
    name       = forms.CharField(
        label='Nom de la comparaison',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    category   = forms.CharField(
        label='Catégorie / segment',
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )
    competitors = forms.MultipleChoiceField(
        label='Concurrents à comparer',
        widget=forms.CheckboxSelectMultiple(),
    )

    def __init__(self, *args, competitors=None, **kwargs):
        super().__init__(*args, **kwargs)
        if competitors:
            self.fields['competitors'].choices = [(c.pk, c.name) for c in competitors]
