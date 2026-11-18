"""apps/fiscal_pt/forms.py — La saisie des paramètres de conformité."""

from django import forms
from django.utils import timezone

from apps.core.form_widgets import DateISO

from .models import ParametresFiscauxPT, SerieFiscale


class ParametresForm(forms.ModelForm):
    class Meta:
        model = ParametresFiscauxPT
        fields = ('est_actif', 'nif', 'numero_de_certificat',
                  'region_par_defaut', 'nom_editeur', 'nif_editeur',
                  'version_produit')
        widgets = {
            'nif': forms.TextInput(attrs={'class': 'form-control',
                                          'placeholder': '123456789'}),
            'numero_de_certificat': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': '0'}),
            'region_par_defaut': forms.Select(attrs={'class': 'form-select'}),
            'nom_editeur': forms.TextInput(attrs={'class': 'form-control'}),
            'nif_editeur': forms.TextInput(attrs={'class': 'form-control'}),
            'version_produit': forms.TextInput(attrs={'class': 'form-control'}),
            'est_actif': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}),
        }


class SerieForm(forms.ModelForm):
    """La série, et son code de validation.

    `prochain_numero` n'est PAS modifiable ici. Le laisser à la main
    ouvrirait deux portes qu'on ne peut pas refermer : reculer le compteur
    produit des numéros en doublon, l'avancer laisse un trou permanent
    dans la série. Les deux sont des manquements que le contrôle relève.
    """

    class Meta:
        model = SerieFiscale
        fields = ('type_document', 'nom', 'region', 'code_de_validation',
                  'cle', 'est_active')
        widgets = {
            'type_document': forms.Select(attrs={'class': 'form-select'}),
            'nom': forms.TextInput(attrs={'class': 'form-control',
                                          'placeholder': 'A'}),
            'region': forms.Select(attrs={'class': 'form-select'}),
            'code_de_validation': forms.TextInput(
                attrs={'class': 'form-control',
                       'placeholder': 'CSDF7T5H — rendu par l’AT'}),
            'cle': forms.Select(attrs={'class': 'form-select'}),
            'est_active': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}),
        }

    def __init__(self, company, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.company = company

        # La liste des clés est restreinte à l'entreprise courante.
        #
        # Sans ce filtrage, le menu déroulant d'un ModelChoiceField propose
        # TOUTES les clés de l'installation : une entreprise pourrait
        # signer ses factures avec la clé d'une autre, et la fuite ne se
        # verrait nulle part à l'écran.
        from .models import CleDeSignature
        self.fields['cle'].queryset = CleDeSignature.objects.filter(
            company=company).order_by('-version')
        self.fields['cle'].empty_label = 'Clé active de l’entreprise'


class PeriodeForm(forms.Form):
    """La période d'un export SAF-T."""

    debut = forms.DateField(label='Du', widget=DateISO(
        attrs={'class': 'form-control'}))
    fin = forms.DateField(label='Au', widget=DateISO(
        attrs={'class': 'form-control'}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            aujourdhui = timezone.now().date()
            self.fields['debut'].initial = aujourdhui.replace(month=1, day=1)
            self.fields['fin'].initial = aujourdhui

    def clean(self):
        donnees = super().clean()
        debut, fin = donnees.get('debut'), donnees.get('fin')
        if debut and fin and debut > fin:
            raise forms.ValidationError(
                'La date de début est postérieure à la date de fin.')
        return donnees
