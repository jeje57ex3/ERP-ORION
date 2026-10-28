from django import forms

from apps.domain_manager.models import CustomDomain


class CustomDomainForm(forms.ModelForm):
    class Meta:
        model = CustomDomain
        fields = ['domain', 'brand_key', 'target_type', 'redirect_to_primary']
        widgets = {
            'domain': forms.TextInput(attrs={'placeholder': 'ex: mondomaine.fr ou www.mondomaine.fr'}),
            'brand_key': forms.TextInput(attrs={'placeholder': 'ex: siecle, lunea (laisser vide pour global)'}),
        }
        labels = {
            'domain': 'Nom de domaine',
            'brand_key': 'Marque associée',
            'target_type': 'Cible',
            'redirect_to_primary': 'Rediriger vers le domaine principal',
        }

    def clean_domain(self):
        domain = self.cleaned_data['domain']
        domain = domain.replace('https://', '').replace('http://', '')
        domain = domain.split('/')[0].strip().lower().strip('.')
        if '.' not in domain:
            raise forms.ValidationError('Domaine invalide. Exemple : mondomaine.fr')
        return domain
