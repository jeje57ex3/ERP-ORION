from django import forms
from .models import SiteContentBlock, SitePageCustomization, SitePageSection, SiteThemeSettings


class SiteThemeSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteThemeSettings
        fields = [
            'logo', 'logo_dark', 'favicon',
            'primary_color', 'secondary_color', 'background_color',
            'surface_color', 'text_color', 'muted_text_color',
            'font_family', 'border_radius', 'button_radius',
            'custom_css', 'head_scripts', 'body_scripts',
        ]
        widgets = {
            'primary_color':    forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'}),
            'secondary_color':  forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'}),
            'background_color': forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'}),
            'surface_color':    forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'}),
            'text_color':       forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'}),
            'muted_text_color': forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'}),
            'custom_css':    forms.Textarea(attrs={'rows': 8,  'class': 'orion-input font-monospace', 'placeholder': '/* CSS personnalisé */'}),
            'head_scripts':  forms.Textarea(attrs={'rows': 5,  'class': 'orion-input font-monospace', 'placeholder': '<!-- Scripts <head> -->'}),
            'body_scripts':  forms.Textarea(attrs={'rows': 5,  'class': 'orion-input font-monospace', 'placeholder': '<!-- Scripts <body> -->'}),
            'font_family':   forms.TextInput(attrs={'class': 'orion-input'}),
            'border_radius': forms.NumberInput(attrs={'class': 'orion-input', 'min': 0, 'max': 100}),
            'button_radius': forms.NumberInput(attrs={'class': 'orion-input', 'min': 0, 'max': 999}),
        }


class SitePageCustomizationForm(forms.ModelForm):
    class Meta:
        model = SitePageCustomization
        fields = [
            'website', 'page_type', 'title', 'slug',
            'seo_title', 'seo_description',
            'hero_title', 'hero_subtitle', 'hero_image',
            'cta_label', 'cta_url',
            'status', 'is_homepage',
        ]
        widgets = {
            'website':         forms.Select(attrs={'class': 'orion-select'}),
            'page_type':       forms.Select(attrs={'class': 'orion-select'}),
            'status':          forms.Select(attrs={'class': 'orion-select'}),
            'title':           forms.TextInput(attrs={'class': 'orion-input'}),
            'slug':            forms.TextInput(attrs={'class': 'orion-input'}),
            'seo_title':       forms.TextInput(attrs={'class': 'orion-input'}),
            'seo_description': forms.Textarea(attrs={'rows': 3, 'class': 'orion-input'}),
            'hero_title':      forms.TextInput(attrs={'class': 'orion-input'}),
            'hero_subtitle':   forms.Textarea(attrs={'rows': 4, 'class': 'orion-input'}),
            'cta_label':       forms.TextInput(attrs={'class': 'orion-input'}),
            'cta_url':         forms.TextInput(attrs={'class': 'orion-input'}),
        }


class SitePageSectionForm(forms.ModelForm):
    class Meta:
        model = SitePageSection
        fields = [
            'title', 'subtitle', 'section_type', 'image',
            'content', 'custom_html',
            'cta_label', 'cta_url',
            'position', 'is_visible',
            'background_color', 'text_color',
        ]
        widgets = {
            'section_type':      forms.Select(attrs={'class': 'orion-select'}),
            'title':             forms.TextInput(attrs={'class': 'orion-input'}),
            'subtitle':          forms.Textarea(attrs={'rows': 3, 'class': 'orion-input'}),
            'content':           forms.Textarea(attrs={'rows': 6, 'class': 'orion-input'}),
            'custom_html':       forms.Textarea(attrs={'rows': 8, 'class': 'orion-input font-monospace'}),
            'cta_label':         forms.TextInput(attrs={'class': 'orion-input'}),
            'cta_url':           forms.TextInput(attrs={'class': 'orion-input'}),
            'position':          forms.NumberInput(attrs={'class': 'orion-input', 'min': 0}),
            'background_color':  forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'}),
            'text_color':        forms.TextInput(attrs={'type': 'color', 'class': 'form-control form-control-color'}),
        }


class SiteContentBlockForm(forms.ModelForm):
    class Meta:
        model = SiteContentBlock
        fields = [
            'block_type', 'title', 'content', 'image',
            'link_label', 'link_url',
            'position', 'is_visible',
        ]
        widgets = {
            'block_type': forms.Select(attrs={'class': 'orion-select'}),
            'title':      forms.TextInput(attrs={'class': 'orion-input'}),
            'content':    forms.Textarea(attrs={'rows': 5, 'class': 'orion-input'}),
            'link_label': forms.TextInput(attrs={'class': 'orion-input'}),
            'link_url':   forms.TextInput(attrs={'class': 'orion-input'}),
            'position':   forms.NumberInput(attrs={'class': 'orion-input', 'min': 0}),
        }
