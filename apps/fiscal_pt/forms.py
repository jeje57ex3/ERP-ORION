"""apps/fiscal_pt/forms.py — La saisie des paramètres de conformité."""

from decimal import Decimal

from django import forms
from django.utils import timezone

from apps.core.form_widgets import DateISO

from . import isencao, tipos
from .models import ParametresFiscauxPT, SerieFiscale


class ParametresForm(forms.ModelForm):
    class Meta:
        model = ParametresFiscauxPT
        fields = ('est_actif', 'nif', 'numero_de_certificat',
                  'region_par_defaut', 'regime_simplifiee', 'nom_editeur',
                  'nif_editeur', 'version_produit')
        widgets = {
            'nif': forms.TextInput(attrs={'class': 'form-control',
                                          'placeholder': '123456789'}),
            'numero_de_certificat': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': '0'}),
            'region_par_defaut': forms.Select(attrs={'class': 'form-select'}),
            'regime_simplifiee': forms.Select(attrs={'class': 'form-select'}),
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


class LigneDeNoteDeDebitForm(forms.Form):
    """Une ligne de note de débit, saisie à la main.

    POURQUOI ELLE N'EST PAS RECOPIÉE DE LA FACTURE

    Une note de débit facture ce qui MANQUAIT à la facture : une
    révision de prix, une quantité sous-évaluée, une prestation oubliée.
    Reprendre les lignes d'origine facturerait la même chose une seconde
    fois, et le document serait signé avant que quiconque s'en aperçoive.
    """

    description = forms.CharField(
        label='Désignation', max_length=200, required=False,
        widget=forms.TextInput(attrs={'class': 'form-control',
                                      'placeholder': 'Révision de prix'}))
    quantite = forms.DecimalField(
        label='Qté', max_digits=12, decimal_places=3, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control',
                                        'step': '0.001'}))
    prix_unitaire = forms.DecimalField(
        label='Prix unitaire', max_digits=12, decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control',
                                        'step': '0.01'}))
    taux = forms.DecimalField(
        label='TVA %', max_digits=5, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control',
                                        'step': '0.01'}))
    code_exoneration = forms.ChoiceField(
        label='Motif d’exonération', required=False,
        choices=[('', '—')] + list(isencao.choix()),
        widget=forms.Select(attrs={'class': 'form-select'}))

    def clean(self):
        donnees = super().clean()

        # UNE LIGNE VIDE EST UNE LIGNE VIDE, pas une ligne à zéro euro.
        #
        # Le formulaire propose trois lignes ; on en remplit souvent une.
        # Sans ce retour anticipé, les deux autres seraient validées, puis
        # facturées à zéro euro sans désignation — sur un document que la
        # signature rend définitif.
        if not any(donnees.get(nom) for nom in
                   ('description', 'quantite', 'prix_unitaire')):
            self.cleaned_data = {}
            return {}

        if not donnees.get('description'):
            raise forms.ValidationError(
                'Cette ligne porte un montant sans désignation. Le SAF-T '
                'exige « ProductDescription » sur chaque ligne.')

        quantite = donnees.get('quantite') or Decimal('1')
        prix = donnees.get('prix_unitaire')
        if prix is None:
            raise forms.ValidationError(
                'Cette ligne n’a pas de prix unitaire : il n’y a rien à '
                'réclamer.')

        taux = donnees.get('taux')
        if taux is None:
            raise forms.ValidationError(
                'Cette ligne n’a pas de taux de TVA. Pour une opération '
                'exonérée, saisissez 0 et choisissez le motif : une ligne '
                'sans TVA et sans motif fait rejeter le SAF-T.')

        donnees['quantite'] = quantite
        donnees['base'] = (quantite * prix).quantize(Decimal('0.01'))
        donnees['tva'] = (donnees['base'] * taux
                          / Decimal('100')).quantize(Decimal('0.01'))
        return donnees


LignesDeNoteDeDebitFormSet = forms.formset_factory(
    LigneDeNoteDeDebitForm, extra=3, can_delete=False)


class EncaissementForm(forms.Form):
    """L'encaissement qu'une facture-reçu atteste.

    Le mécanisme est demandé, bien que le schéma le rende optionnel : une
    quittance qui ne dit pas comment la somme a été reçue ne prouve pas
    grand-chose, et le champ est là pour être rempli.
    """

    mecanisme = forms.ChoiceField(
        label='Moyen de paiement', choices=tipos.MECANISMES_DE_PAIEMENT,
        initial='TB',
        widget=forms.Select(attrs={'class': 'form-select'}))
    montant = forms.DecimalField(
        label='Montant encaissé', max_digits=14, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control',
                                        'step': '0.01'}))
    date = forms.DateField(
        label='Date de l’encaissement',
        widget=DateISO(attrs={'class': 'form-control'}))

    def __init__(self, *args, total=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.fields['montant'].initial = total
            self.fields['date'].initial = timezone.now().date()


class RecuForm(forms.Form):
    """L'encaissement qu'un reçu séparé atteste.

    POURQUOI LE MONTANT EST PRÉ-REMPLI ET NON IMPOSÉ

    Le défaut est le RESTE À ENCAISSER, parce que c'est le cas courant :
    on quittance ce qu'on vient de recevoir, et c'est le solde. Mais un
    acompte est précisément le cas où ce n'est pas le solde — c'est même
    la raison d'être du reçu séparé. Le champ reste donc modifiable, et
    c'est l'émission qui refuse un montant supérieur au reste : un reçu
    qui dépasse la créance atteste un argent que personne ne devait.
    """

    mecanisme = forms.ChoiceField(
        label='Moyen de paiement', choices=tipos.MECANISMES_DE_PAIEMENT,
        initial='TB',
        widget=forms.Select(attrs={'class': 'form-select'}))
    montant = forms.DecimalField(
        label='Montant reçu', max_digits=14, decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={'class': 'form-control',
                                        'step': '0.01'}))
    date_encaissement = forms.DateField(
        label='Date de l’encaissement',
        widget=DateISO(attrs={'class': 'form-control'}))
    description = forms.CharField(
        label='Précision (facultatif)', max_length=200, required=False,
        widget=forms.TextInput(
            attrs={'class': 'form-control',
                   'placeholder': 'Ex. « Acompte de 30 % »'}))

    def __init__(self, *args, reste=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.fields['montant'].initial = reste
            self.fields['date_encaissement'].initial = timezone.now().date()
