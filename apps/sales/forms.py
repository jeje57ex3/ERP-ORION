"""apps/sales/forms.py — Formulaires Ventes"""
from django import forms
from .models import (
    Invoice,
    InvoiceLine,
    Quote,
    QuoteLine,
    QuoteTemplate,
    QuoteTemplateField,
    SalesOrder,
)


class QuoteForm(forms.ModelForm):
    class Meta:
        model = Quote
        fields = ['customer', 'subject', 'issue_date', 'validity_date', 'delivery_date',
                  'payment_terms', 'discount_rate',
                  'cout_materiels', 'cout_fournitures', 'cout_main_oeuvre',
                  'taches_principales',
                  'notes', 'internal_notes', 'salesperson', 'status']
        widgets = {
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'validity_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'delivery_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'payment_terms': forms.NumberInput(attrs={'class': 'form-control'}),
            'discount_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'cout_materiels': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'cout_fournitures': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'cout_main_oeuvre': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'taches_principales': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 5,
                'placeholder': 'Une tache par ligne :\nDepose de l-ancien revetement\nRagreage du support\nPose du carrelage',
            }),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'internal_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'salesperson': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


class SalesOrderForm(forms.ModelForm):
    class Meta:
        model = SalesOrder
        fields = ['customer', 'order_date', 'delivery_date', 'delivery_address', 'notes', 'salesperson']
        widgets = {
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'order_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'delivery_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'delivery_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'salesperson': forms.Select(attrs={'class': 'form-select'}),
        }


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['customer', 'subject', 'issue_date', 'due_date',
                  'payment_terms', 'notes', 'salesperson', 'status']
        widgets = {
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'payment_terms': forms.NumberInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'salesperson': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


# ─── Modèles de devis ────────────────────────────────────────────────────────

class QuoteTemplateForm(forms.ModelForm):
    class Meta:
        model = QuoteTemplate
        fields = ['name', 'description', 'pdf', 'is_active', 'is_default']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Devis standard, Rénovation, Entretien…',
            }),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'pdf': forms.ClearableFileInput(attrs={
                'class': 'form-control', 'accept': 'application/pdf',
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_pdf(self):
        fichier = self.cleaned_data.get('pdf')
        if not fichier:
            return fichier

        # Un fichier qui n'est pas un PDF ne serait refusé qu'à la première
        # génération de devis, avec une erreur technique. Le refuser ici dit
        # ce qui ne va pas, au moment où l'on peut encore le corriger.
        nom = (getattr(fichier, 'name', '') or '').lower()
        if not nom.endswith('.pdf'):
            raise forms.ValidationError(
                'Le modèle doit être un fichier PDF.')

        try:
            debut = fichier.read(5)
            fichier.seek(0)
        except Exception:
            raise forms.ValidationError('Fichier illisible.')
        if not debut.startswith(b'%PDF'):
            # L'extension ne prouve rien : un .docx renommé en .pdf passerait.
            raise forms.ValidationError(
                "Ce fichier porte l'extension .pdf mais n'en est pas un.")
        return fichier


class QuoteTemplateFieldForm(forms.ModelForm):
    class Meta:
        model = QuoteTemplateField
        fields = ['cle', 'page', 'x', 'y', 'taille', 'gras', 'alignement',
                  'couleur', 'multiligne', 'prefixe', 'suffixe']
        widgets = {
            'cle': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'page': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': 1}),
            'x': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.5'}),
            'y': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.5'}),
            'taille': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'min': 4, 'max': 72}),
            'gras': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'alignement': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'couleur': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'multiligne': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'prefixe': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'suffixe': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
        }


QuoteTemplateFieldFormSet = forms.inlineformset_factory(
    QuoteTemplate,
    QuoteTemplateField,
    form=QuoteTemplateFieldForm,
    extra=3,
    can_delete=True,
)


class QuoteFromTemplateForm(forms.Form):
    """Créer un devis en reprenant un modèle.

    Le modèle ne porte pas de lignes : il porte la MISE EN PAGE et
    l'emplacement des valeurs. Les lignes du devis restent à saisir — ou
    viennent d'ailleurs (configurateur, devis guidé BTP).
    """

    template = forms.ModelChoiceField(
        queryset=QuoteTemplate.objects.none(),
        label='Modèle de devis',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    customer = forms.ModelChoiceField(
        queryset=None,
        label='Client',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    subject = forms.CharField(
        label='Objet', required=False, max_length=300,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
    )

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.crm.models import Customer

        # Les deux listes sont bornées à l'entreprise, et c'est fait ici --
        # donc aussi bien à l'affichage qu'à la validation. Les restreindre
        # seulement à l'affichage laisse accepter une valeur forgée.
        self.fields['template'].queryset = QuoteTemplate.objects.filter(
            company=company, is_active=True)
        self.fields['customer'].queryset = Customer.objects.filter(
            company=company, is_active=True)
