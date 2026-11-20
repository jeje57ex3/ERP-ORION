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


class MoyenDePaiementForm(forms.Form):
    """Un moyen de paiement parmi plusieurs sur le même document.

    POURQUOI LE MONTANT EST FACULTATIF ICI, ET OBLIGATOIRE À PARTIR DE DEUX

    Un seul moyen sans montant vaut LE TOTAL du document — et c'est la
    seule valeur légale, que l'émission remplit depuis les lignes figées
    qu'elle vient de calculer. Le faire saisir à l'écran ferait entrer ici
    le cumul tenu par la facture de l'ERP, qui dérive d'un centime après
    une suppression de ligne ; au Portugal ce centime est signé.

    À partir de deux moyens, chacun doit porter le sien : « le total »
    réparti sur plusieurs n'a pas de valeur par défaut, et le schéma rend
    `PaymentAmount` obligatoire. C'est `tipos.valider_les_paiements` qui
    le refuse, au même endroit que la règle d'égalité des sommes — on ne
    la recopie pas ici, pour qu'il n'y ait jamais deux versions de la
    règle à maintenir.
    """

    # AUCUNE VALEUR PAR DÉFAUT, ET C'EST DÉLIBÉRÉ.
    #
    # `initial` s'applique à CHAQUE rangée d'un formset. Pré-remplir au
    # virement aurait donné trois moyens de paiement sur un reçu dont une
    # seule rangée est remplie — dont deux sans montant, ce que la règle
    # refuse. L'écran aurait été inutilisable dans son cas le plus
    # courant.
    #
    # Et le choix vide n'est pas qu'une commodité technique : une
    # quittance qui ne dit pas comment la somme est arrivée ne prouve pas
    # grand-chose. Mieux vaut un choix à faire qu'un défaut qui se glisse
    # dans un document signé.
    mecanisme = forms.ChoiceField(
        label='Moyen', required=False,
        choices=(('', '— Choisir le moyen —'),)
                + tuple(tipos.MECANISMES_DE_PAIEMENT),
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'}))
    montant = forms.DecimalField(
        label='Montant', max_digits=14, decimal_places=2, required=False,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={'class': 'form-control '
                                                 'form-control-sm',
                                        'step': '0.01',
                                        'placeholder': 'Le total'}))

    def clean(self):
        donnees = super().clean()

        # UNE LIGNE AVEC UN MONTANT ET SANS MOYEN EST UN OUBLI, PAS UN VIDE.
        #
        # Le formset ignore les lignes entièrement vides — c'est ainsi
        # qu'on offre trois rangées sans en imposer trois. Mais une rangée
        # où quelqu'un a tapé 40 € en oubliant de choisir le moyen ne doit
        # pas disparaître en silence : la somme encaissée serait alors
        # inférieure au total, et le refus parlerait d'un écart de 40 €
        # sans dire d'où il vient.
        if donnees.get('montant') is not None and not donnees.get('mecanisme'):
            raise forms.ValidationError(
                'Ce montant n’a pas de moyen de paiement. Choisissez-en un, '
                'ou videz le montant.')
        return donnees


class BaseMoyensDePaiement(forms.BaseFormSet):
    """Au moins un moyen, et le contrôle est posé ici.

    POURQUOI SUR LE JEU ET NON SUR UNE RANGÉE

    « Au moins un » n'a de sens que pour l'ensemble : une rangée ne sait
    rien des deux autres. Rendre le champ obligatoire rangée par rangée
    en imposerait trois ; le laisser facultatif partout sans contrôle
    d'ensemble laisserait émettre un document qui n'atteste aucun moyen.

    `validate_min` de Django ne suffit pas : il compte les formulaires
    soumis, pas ceux qui portent un moyen — trois rangées vides le
    satisfont.
    """

    def clean(self):
        super().clean()
        if any(self.errors):
            # Une rangée déjà fautive dira ce qui lui manque. Ajouter
            # « choisissez un moyen » par-dessus enverrait corriger
            # ailleurs que là où le message précis est affiché.
            return

        remplis = [formulaire for formulaire in self.forms
                   if formulaire.cleaned_data.get('mecanisme')]
        if not remplis:
            raise forms.ValidationError(
                'Choisissez au moins un moyen de paiement. Une quittance '
                'qui ne dit pas comment la somme est arrivée ne prouve pas '
                'grand-chose, et le SAF-T attend le code du moyen.')


#: Trois rangées offertes, aucune imposée — et la première suffit.
MoyensDePaiementFormSet = forms.formset_factory(
    MoyenDePaiementForm, formset=BaseMoyensDePaiement, extra=3,
    can_delete=False)


def moyens_saisis(formset, date_par_defaut):
    """Les moyens réellement remplis, prêts pour l'émission.

    Rend `None` quand rien n'est saisi : l'appelant garde alors son
    comportement d'avant — un virement par défaut — au lieu de recevoir
    une liste vide, qui ferait refuser le document pour absence de
    paiement sur un écran où personne n'a rien demandé.
    """
    moyens = []
    for formulaire in formset:
        if not formulaire.cleaned_data:
            continue
        mecanisme = formulaire.cleaned_data.get('mecanisme')
        if not mecanisme:
            continue
        moyen = {'mecanisme': mecanisme, 'date': date_par_defaut}
        montant = formulaire.cleaned_data.get('montant')
        if montant is not None:
            moyen['montant'] = montant
        moyens.append(moyen)

    if not moyens:
        return None

    # UN SEUL MOYEN : ON RETIRE LE MONTANT SAISI S'IL ÉGALE LE TOTAL ?
    # Non — on ne retire rien. Si l'utilisateur a saisi un montant, il
    # est validé contre le total par la règle, qui dira l'écart. Le
    # défaut « le total » ne joue que sur un champ laissé vide, et c'est
    # exactement ce que fait l'absence de la clé « montant ».
    return moyens


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

    # LE MOYEN DE PAIEMENT N'EST PLUS UN CHAMP UNIQUE ICI.
    #
    # Il est porté par `MoyensDePaiementFormSet`, parce qu'un encaissement
    # peut arriver par plusieurs moyens à la fois — moitié en espèces,
    # moitié par carte — ce que le modèle, la règle et le SAF-T
    # acceptaient déjà, et que cet écran seul interdisait.
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
