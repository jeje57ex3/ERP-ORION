from django import forms
from .models import Company


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = [
            'name', 'sector', 'email', 'phone', 'address', 'city',
            'zip_code', 'country', 'siret', 'vat_number', 'legal_form',
            'capital', 'logo', 'primary_color', 'secondary_color', 'accent_color',
            'currency', 'default_vat_rate', 'invoice_prefix', 'quote_prefix',
            'bank_name', 'iban', 'bic', 'website_url', 'is_active',
        ]
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'primary_color': forms.TextInput(attrs={'type': 'color'}),
            'secondary_color': forms.TextInput(attrs={'type': 'color'}),
            'accent_color': forms.TextInput(attrs={'type': 'color'}),
        }
