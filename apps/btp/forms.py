from decimal import Decimal

from django import forms

from .models import (
    BTPPhase,
    BTPProject,
    BTPQuote,
    BTPQuoteLine,
    BTPTimesheet,
    Material,
    ProjectSupply,
    SituationOfWorks,
    WorkLibrary,
)


class BTPProjectForm(forms.ModelForm):
    class Meta:
        model = BTPProject
        fields = [
            'code', 'name', 'customer', 'status', 'description',
            'address', 'city', 'zip_code', 'project_manager', 'site_foreman',
            'start_date', 'end_date', 'actual_start_date', 'actual_end_date',
            'estimated_budget', 'retention_rate', 'market_type', 'market_number', 'notes',
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'zip_code': forms.TextInput(attrs={'class': 'form-control'}),
            'project_manager': forms.Select(attrs={'class': 'form-select'}),
            'site_foreman': forms.TextInput(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'actual_start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'actual_end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'estimated_budget': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'retention_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'market_type': forms.TextInput(attrs={'class': 'form-control'}),
            'market_number': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class BTPQuoteForm(forms.ModelForm):
    class Meta:
        model = BTPQuote
        fields = ['project', 'customer', 'status', 'issue_date', 'validity_date', 'subject', 'notes']
        widgets = {
            'project': forms.Select(attrs={'class': 'form-select'}),
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'validity_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class SituationForm(forms.ModelForm):
    class Meta:
        model = SituationOfWorks
        fields = ['project', 'number', 'status', 'period_start', 'period_end', 'cumulative_amount', 'previous_amount', 'notes']
        widgets = {
            'project': forms.Select(attrs={'class': 'form-select'}),
            'number': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'period_start': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'period_end': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'cumulative_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'previous_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class BTPTimesheetForm(forms.ModelForm):
    class Meta:
        model = BTPTimesheet
        fields = ['project', 'employee', 'work_date', 'hours', 'overtime_hours', 'task_description', 'notes']
        widgets = {
            'project': forms.Select(attrs={'class': 'form-select'}),
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'work_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'hours': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.25'}),
            'overtime_hours': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.25'}),
            'task_description': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


# ─── Matériaux et fournitures ────────────────────────────────────────────────
#
# Trois formulaires, une règle commune : **toute liste déroulante est bornée
# à l'entreprise dans __init__**, donc à la VALIDATION et pas seulement à
# l'affichage. Restreindre le seul affichage laisse accepter un identifiant
# forgé, et un chantier d'une autre société se retrouverait rattaché.


def _rendre_deductibles(form, noms):
    """Lève l'obligation sur les champs que clean() remplit lui-même.

    Sans cela la déduction est INATTEIGNABLE : un champ obligatoire laissé
    vide échoue à la validation du champ, et clean() n'est jamais atteint —
    le formulaire refuse de valider en réclamant précisément ce que le
    catalogue savait déjà. Erreur commise ici, attrapée par les tests.
    """
    for nom in noms:
        if nom in form.fields:
            form.fields[nom].required = False


def _completer_les_defauts(donnees):
    """Remet les valeurs par défaut du modèle là où rien n'a été déduit.

    Un champ non obligatoire laissé vide vaut None dans cleaned_data, or la
    colonne n'accepte pas NULL : sans ce passage, enregistrer lèverait une
    IntegrityError au lieu d'afficher une erreur de saisie.
    """
    if donnees.get('unit') in (None, ''):
        donnees['unit'] = 'u'
    if donnees.get('unit_price') is None:
        donnees['unit_price'] = Decimal('0')
    if donnees.get('vat_rate') is None:
        donnees['vat_rate'] = Decimal('20')
    if 'quantity' in donnees and donnees.get('quantity') is None:
        donnees['quantity'] = Decimal('0')
    return donnees


def _recopier_depuis_article(article, donnees):
    """Complète les champs laissés vides avec ceux de l'article du catalogue.

    Recopie et ne référence pas : le prix d'un achat passé ne doit pas
    bouger parce que le catalogue a changé six mois plus tard. Ce qui est
    déjà saisi n'est jamais écrasé — l'utilisateur a pu corriger le prix
    exprès, c'est même le cas courant (remise de négoce, promotion).
    """
    if donnees.get('description') in (None, ''):
        donnees['description'] = article.name
    if donnees.get('reference') in (None, ''):
        donnees['reference'] = article.reference
    if donnees.get('unit') in (None, ''):
        donnees['unit'] = article.unit
    return donnees


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = ['kind', 'reference', 'name', 'category', 'unit',
                  'purchase_price', 'sale_price', 'vat_rate',
                  'supplier', 'supplier_reference', 'description',
                  'is_active']
        widgets = {
            'kind': forms.Select(attrs={'class': 'form-select'}),
            'reference': forms.TextInput(attrs={'class': 'form-control',
                                                'placeholder': 'CIM-35'}),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ciment CEM II 35 kg'}),
            'category': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Gros œuvre, Électricité, Plomberie…'}),
            'unit': forms.TextInput(attrs={'class': 'form-control',
                                           'placeholder': 'u, sac, ml, m²'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-control',
                                                       'step': '0.0001'}),
            'sale_price': forms.NumberInput(attrs={'class': 'form-control',
                                                   'step': '0.0001'}),
            'vat_rate': forms.NumberInput(attrs={'class': 'form-control',
                                                 'step': '0.01'}),
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'supplier_reference': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control',
                                                 'rows': 2}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        from apps.purchases.models import Supplier
        self.fields['supplier'].queryset = Supplier.objects.filter(
            company=company, is_active=True).order_by('name')
        self.fields['supplier'].required = False

    def clean_reference(self):
        """Refuse une référence déjà prise dans cette entreprise.

        C'est fait ici et pas en contrainte de base : la référence peut
        rester vide, et une contrainte unique conditionnelle est ignorée par
        MySQL/MariaDB, qui ne connaissent pas les index partiels. Une
        référence en double rendrait le choix ambigu au moment de piocher
        dans le catalogue.
        """
        reference = (self.cleaned_data.get('reference') or '').strip()
        if not reference:
            return reference
        doublons = Material.objects.filter(company=self.company,
                                           reference__iexact=reference)
        if self.instance.pk:
            doublons = doublons.exclude(pk=self.instance.pk)
        if doublons.exists():
            raise forms.ValidationError(
                'Cette référence est déjà utilisée par « %s ».'
                % doublons.first().name)
        return reference


class ProjectSupplyForm(forms.ModelForm):
    """Un achat réel rattaché à un chantier."""

    class Meta:
        model = ProjectSupply
        fields = ['material', 'description', 'reference', 'quantity', 'unit',
                  'unit_price', 'vat_rate', 'supplier', 'purchase_date',
                  'invoice_reference', 'notes']
        widgets = {
            'material': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control',
                                                 'step': '0.001'}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control',
                                                   'step': '0.0001'}),
            'vat_rate': forms.NumberInput(attrs={'class': 'form-control',
                                                 'step': '0.01'}),
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'purchase_date': forms.DateInput(attrs={'class': 'form-control',
                                                    'type': 'date'}),
            'invoice_reference': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'N° de facture ou de bon de livraison'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        from apps.purchases.models import Supplier
        self.fields['material'].queryset = Material.objects.filter(
            company=company, is_active=True)
        self.fields['material'].required = False
        self.fields['material'].label = 'Article du catalogue'
        self.fields['material'].help_text = (
            'Laissez vide pour un achat ponctuel hors catalogue.')
        self.fields['supplier'].queryset = Supplier.objects.filter(
            company=company, is_active=True).order_by('name')
        self.fields['supplier'].required = False
        # La désignation, l'unité, le prix et la TVA se déduisent de
        # l'article choisi : les exiger obligerait à retaper ce que le
        # catalogue sait déjà — et rendrait la déduction inatteignable.
        #
        # `quantity` reste obligatoire, et c'est délibéré : c'est le seul
        # nombre qu'aucun catalogue ne peut deviner. En supposer 1 fausserait
        # un coût de chantier en silence.
        _rendre_deductibles(self, ('description', 'unit', 'unit_price',
                                   'vat_rate'))

    def clean(self):
        donnees = super().clean()
        article = donnees.get('material')

        if article:
            _recopier_depuis_article(article, donnees)
            # Prix d'ACHAT ici : c'est ce que le chantier coûte, pas ce
            # qu'on le facture.
            if not donnees.get('unit_price'):
                donnees['unit_price'] = article.purchase_price
            if not donnees.get('supplier'):
                donnees['supplier'] = article.supplier
        elif not (donnees.get('description') or '').strip():
            self.add_error(
                'description',
                'Indiquez une désignation, ou choisissez un article du '
                'catalogue.')

        return _completer_les_defauts(donnees)


class BTPQuoteLineForm(forms.ModelForm):
    """Une ligne de devis BTP : ouvrage, article du catalogue ou saisie libre."""

    class Meta:
        model = BTPQuoteLine
        fields = ['is_section', 'material', 'work_item', 'phase',
                  'description', 'unit', 'quantity', 'unit_price', 'vat_rate']
        widgets = {
            'is_section': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'material': forms.Select(attrs={'class': 'form-select'}),
            'work_item': forms.Select(attrs={'class': 'form-select'}),
            'phase': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control',
                                                 'step': '0.001'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control',
                                                   'step': '0.0001'}),
            'vat_rate': forms.NumberInput(attrs={'class': 'form-control',
                                                 'step': '0.01'}),
        }

    def __init__(self, *args, quote=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.quote = quote
        company = quote.company if quote else None

        self.fields['material'].queryset = Material.objects.filter(
            company=company, is_active=True)
        self.fields['work_item'].queryset = WorkLibrary.objects.filter(
            company=company, is_active=True)
        # Les phases du chantier de CE devis, pas de tous les chantiers.
        if quote and quote.project_id:
            self.fields['phase'].queryset = BTPPhase.objects.filter(
                project=quote.project)
        else:
            self.fields['phase'].queryset = BTPPhase.objects.none()

        # Tout ce qui se déduit d'un article, d'un ouvrage, ou n'a pas de
        # sens sur une ligne de section.
        _rendre_deductibles(self, ('material', 'work_item', 'phase',
                                   'description', 'unit', 'unit_price',
                                   'vat_rate', 'quantity'))
        self.fields['material'].label = 'Matériau / fourniture'
        self.fields['work_item'].label = 'Ouvrage'

    def clean(self):
        donnees = super().clean()
        article = donnees.get('material')
        ouvrage = donnees.get('work_item')

        if article and ouvrage:
            # Les deux rempliraient la même ligne avec deux prix différents.
            # Choisir en silence tromperait sur le montant du devis.
            self.add_error(
                'work_item',
                'Choisissez un ouvrage OU un article du catalogue, pas les '
                'deux.')
            return donnees

        if donnees.get('is_section'):
            # Une section n'est qu'un intitulé : ni quantité, ni prix.
            if not (donnees.get('description') or '').strip():
                self.add_error('description',
                               'Donnez un intitulé à la section.')
            donnees['quantity'] = Decimal('0')
            donnees['unit_price'] = Decimal('0')
            return _completer_les_defauts(donnees)

        if article:
            _recopier_depuis_article(article, donnees)
            # Prix de VENTE ici : un devis se chiffre à ce qu'on facture.
            # Reprendre le prix d'achat exposerait le coût au client et
            # supprimerait la marge.
            if not donnees.get('unit_price'):
                donnees['unit_price'] = article.sale_price
            if not donnees.get('vat_rate'):
                donnees['vat_rate'] = article.vat_rate
        elif ouvrage:
            if donnees.get('description') in (None, ''):
                donnees['description'] = ouvrage.name
            if donnees.get('unit') in (None, ''):
                donnees['unit'] = ouvrage.unit
            if not donnees.get('unit_price'):
                donnees['unit_price'] = ouvrage.unit_price
        elif not (donnees.get('description') or '').strip():
            self.add_error(
                'description',
                'Indiquez une désignation, ou choisissez un ouvrage ou un '
                'article du catalogue.')

        return _completer_les_defauts(donnees)
