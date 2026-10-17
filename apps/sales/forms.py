"""apps/sales/forms.py — Formulaires Ventes"""
from decimal import Decimal

from django import forms
from .models import (
    Invoice,
    InvoiceLine,
    Quote,
    QuoteDetailLine,
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


class QuoteDetailLineForm(forms.ModelForm):
    """Un matériel ou une fourniture détaillé sur le devis.

    **La nature n'a pas de valeur par défaut dans ce formulaire, et c'est
    délibéré.** Avec un défaut, une ligne de fourniture laissée par
    inattention sur « Matériel » irait dans le mauvais bloc du devis sans
    que rien ne le signale. Un choix vide oblige à trancher, et ce qui est
    affiché est ce qui sera enregistré — l'article du catalogue ne vient
    jamais contredire en silence le menu que l'on voit.
    """

    class Meta:
        model = QuoteDetailLine
        fields = ['nature', 'material', 'designation', 'quantity', 'unit',
                  'unit_price']
        widgets = {
            'nature': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'material': forms.Select(attrs={'class': 'form-select form-select-sm'}),
            'designation': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.001'}),
            'unit': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control form-control-sm', 'step': '0.0001'}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company

        from apps.btp.models import Material
        # Borne a l'entreprise dans __init__, donc a la VALIDATION et pas
        # seulement a l'affichage : restreindre le seul affichage laisse
        # accepter un identifiant forge.
        self.fields['material'].queryset = (
            Material.objects.filter(company=company, is_active=True)
            if company is not None else Material.objects.none()
        )
        self.fields['material'].required = False
        self.fields['material'].label = 'Article du catalogue'

        # Pas de choix par defaut : voir la docstring.
        self.fields['nature'].choices = (
            [('', '— choisir —')] + list(QuoteDetailLine.NATURES))

        # Une ligne NEUVE ne doit porter aucune valeur initiale.
        #
        # Un defaut de modele (quantity=1, unit='u') devient valeur
        # initiale du formulaire. Le formset compare alors la ligne vide
        # envoyee a cette initiale, la croit MODIFIEE, la valide, et
        # reclame une designation pour une ligne que personne n'a
        # remplie -- l'enregistrement du devis entier echouait sur une
        # ligne laissee vide expres. Constate par un test.
        # Mesure : avec les defauts du modele, changed_data valait
        # ['unit_price'] (initiale 0) pour une ligne entierement vide.
        # On neutralise TOUS les champs plutot qu'une liste : un futur
        # champ dote d'un defaut rouvrirait sinon le meme piege.
        if not self.instance.pk:
            for nom in self.fields:
                self.initial[nom] = ''

        # Deduits de l'article choisi : les exiger obligerait a retaper ce
        # que le catalogue sait deja. Les laisser obligatoires rendrait la
        # deduction inatteignable -- un champ vide echoue avant clean().
        for nom in ('designation', 'unit', 'unit_price', 'quantity'):
            self.fields[nom].required = False

    def clean(self):
        donnees = super().clean()

        # Une ligne entierement vide est une ligne non remplie du formset :
        # elle ne doit ni etre enregistree ni produire d'erreur.
        if not self.has_changed():
            return donnees

        article = donnees.get('material')
        if article:
            if not (donnees.get('designation') or '').strip():
                donnees['designation'] = article.name
            if not (donnees.get('unit') or '').strip():
                donnees['unit'] = article.unit
            if not donnees.get('unit_price'):
                # Prix de VENTE : ce bloc est imprime sur le devis remis au
                # client. Le prix d'achat y exposerait la marge.
                donnees['unit_price'] = article.sale_price

        if not (donnees.get('designation') or '').strip():
            self.add_error(
                'designation',
                'Indiquez une désignation, ou choisissez un article du '
                'catalogue.')
        if not donnees.get('nature'):
            self.add_error('nature', 'Matériel ou fourniture ?')

        if donnees.get('quantity') is None:
            donnees['quantity'] = Decimal('1')
        if donnees.get('unit_price') is None:
            donnees['unit_price'] = Decimal('0')
        if not (donnees.get('unit') or '').strip():
            donnees['unit'] = 'u'

        return donnees


QuoteDetailLineFormSet = forms.inlineformset_factory(
    Quote,
    QuoteDetailLine,
    form=QuoteDetailLineForm,
    extra=3,
    can_delete=True,
)


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
