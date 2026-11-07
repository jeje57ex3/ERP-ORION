"""apps/btp/forms_etapes.py — modèles de chantier et saisie des points.

Deux familles de formulaires :

  * trois ModelForm pour écrire un modèle (le modèle, ses étapes, ses points)
  * un formulaire DYNAMIQUE pour remplir les points d'une étape de chantier

Le second est le cœur du fichier : les champs ne sont pas connus à
l'écriture du code, ils dépendent du type de chaque point. On les construit
dans __init__, et la validation est donc celle du type choisi — un nombre
est validé comme un nombre, une date comme une date. C'est tout l'intérêt
des réponses typées : l'erreur de saisie est refusée au moment de la
saisie, et pas découverte six mois plus tard dans une recherche.
"""

from django import forms

from .models import (
    ProjectPlanStep,
    ProjectTemplate,
    ProjectTemplateItem,
    ProjectTemplateStep,
)


# ─── Écrire un modèle ────────────────────────────────────────────────────────

class ProjectTemplateForm(forms.ModelForm):
    class Meta:
        model = ProjectTemplate
        fields = ['name', 'description', 'is_default', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Électricité — logement neuf'}),
            'description': forms.Textarea(attrs={'class': 'form-control',
                                                 'rows': 2}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company

    def clean_name(self):
        """Refuse un nom déjà pris dans cette entreprise.

        `unique_together ['company', 'name']` existe sur le modèle, mais
        `company` n'est pas un champ du formulaire : Django ne peut donc pas
        valider la contrainte lui-même et l'enregistrement échouerait en
        IntegrityError — une page d'erreur 500 au lieu d'un message.
        """
        nom = (self.cleaned_data.get('name') or '').strip()
        doublons = ProjectTemplate.objects.filter(
            company=self.company, name__iexact=nom)
        if self.instance.pk:
            doublons = doublons.exclude(pk=self.instance.pk)
        if doublons.exists():
            raise forms.ValidationError(
                'Un modèle de ce nom existe déjà dans cette entreprise.')
        return nom


class ProjectTemplateStepForm(forms.ModelForm):
    class Meta:
        model = ProjectTemplateStep
        fields = ['name', 'step_type', 'order', 'offset_days',
                  'visible_to_client', 'client_can_validate']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Analyse sur place'}),
            'step_type': forms.Select(attrs={'class': 'form-select'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'offset_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'visible_to_client': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'client_can_validate': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ProjectTemplateItemForm(forms.ModelForm):
    """Un point à remplir. Les options d'une liste sont saisies en lignes.

    Le modèle stocke un JSONField, mais on ne demande pas à l'utilisateur
    d'écrire du JSON : il tape une option par ligne, et `clean_options`
    fait la conversion. Un JSONField rendu brut afficherait
    `["Oui", "Non"]` dans un champ de texte, et une virgule oubliée
    produirait une erreur de syntaxe illisible.
    """

    options_saisies = forms.CharField(
        label='Choix possibles', required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 4,
            'placeholder': 'Un choix par ligne :\nFacile\nDifficile\n'
                           'Impossible sans nacelle'}),
        help_text='Un choix par ligne. Utilisé seulement pour une réponse '
                  'de type « Choix dans une liste ».')

    class Meta:
        model = ProjectTemplateItem
        fields = ['label', 'help_text', 'answer_type', 'unit', 'is_required',
                  'order']
        widgets = {
            'label': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Une nacelle est-elle nécessaire ?'}),
            'help_text': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Précision affichée sous la question'}),
            'answer_type': forms.Select(attrs={'class': 'form-select'}),
            'unit': forms.TextInput(attrs={'class': 'form-control',
                                           'placeholder': 'm, m², A…'}),
            'is_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.options:
            self.fields['options_saisies'].initial = '\n'.join(
                str(option) for option in self.instance.options)

    def clean(self):
        donnees = super().clean()
        options = [ligne.strip()
                   for ligne in (donnees.get('options_saisies') or '').splitlines()
                   if ligne.strip()]

        if donnees.get('answer_type') == 'choice' and len(options) < 2:
            self.add_error(
                'options_saisies',
                'Donnez au moins deux choix, sinon la question n’a qu’une '
                'réponse possible.')

        self.instance.options = options
        return donnees


# ─── Remplir les points d'une étape de chantier ──────────────────────────────

class EtapeDuChantierForm(forms.ModelForm):
    """L'étape elle-même : date, statut, avancement."""

    class Meta:
        model = ProjectPlanStep
        fields = ['name', 'step_type', 'order', 'planned_date', 'actual_date',
                  'status', 'progress_percent', 'responsible',
                  'client_comment', 'visible_to_client', 'client_can_validate']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'step_type': forms.Select(attrs={'class': 'form-select'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'planned_date': forms.DateInput(attrs={'class': 'form-control',
                                                   'type': 'date'}),
            'actual_date': forms.DateInput(attrs={'class': 'form-control',
                                                  'type': 'date'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'progress_percent': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 0, 'max': 100}),
            'responsible': forms.Select(attrs={'class': 'form-select'}),
            'client_comment': forms.Textarea(attrs={'class': 'form-control',
                                                    'rows': 2}),
            'visible_to_client': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'client_can_validate': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Le responsable est borné à l'entreprise dans __init__, donc à la
        # VALIDATION. Le borner seulement à l'affichage laisse accepter un
        # identifiant recopié d'une autre société — le piège déjà rencontré
        # sur le pointage.
        from django.contrib.auth.models import User
        if company is not None:
            self.fields['responsible'].queryset = User.objects.filter(
                employee_profile__company=company,
                employee_profile__is_active=True,
            ).order_by('last_name', 'first_name', 'username')
        else:
            self.fields['responsible'].queryset = User.objects.none()
        self.fields['responsible'].required = False


OUI_NON_CHOIX = [('', '— Pas encore renseigné —'),
                 ('true', 'Oui'), ('false', 'Non')]


class PointsDeLEtapeForm(forms.Form):
    """Formulaire construit à la volée depuis les points de l'étape.

    Un champ par point, du type du point, plus un champ de commentaire.
    Les noms sont `point_<pk>` et `commentaire_<pk>` : l'identifiant du
    point et non son rang, parce qu'un rang change quand on réordonne et
    qu'une réponse se retrouverait alors sur la mauvaise question.

    AUCUN champ n'est `required`, y compris ceux marqués obligatoires dans
    le modèle. C'est la décision « avertir sans bloquer » : on enregistre ce
    qui est saisi, et l'on affiche ce qui manque. Rendre les champs
    obligatoires ici empêcherait d'enregistrer une visite à moitié faite —
    donc ferait tout retaper, donc ferait inventer.
    """

    def __init__(self, *args, points=None, company=None, project=None,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.points = list(points or [])
        self.company = company
        self.project = project

        # Les deux listes de fiches sont construites UNE fois, et pas une
        # par point : un modèle peut citer le fournisseur dans trois étapes,
        # et trois requêtes identiques n'apportent rien.
        #
        # `company=None` donne `none()` et non « tout ». Sans entreprise
        # connue, le choix sûr est de ne rien proposer : ouvrir la liste
        # entière exposerait les devis et les fournisseurs de toutes les
        # sociétés.
        self._devis = self._devis_de_l_entreprise()
        self._fournisseurs = self._fournisseurs_de_l_entreprise()
        # Compté UNE fois : `.exists()` dans la boucle repartirait en base
        # à chaque point qui désigne un devis, et un modèle en cite deux.
        self._il_y_a_des_devis = self._devis.exists()

        for point in self.points:
            cle = f'point_{point.pk}'
            commun = {
                'label': point.label,
                'required': False,
                'help_text': point.help_text,
            }

            if point.answer_type == 'yes_no':
                self.fields[cle] = forms.ChoiceField(
                    choices=OUI_NON_CHOIX,
                    widget=forms.Select(attrs={'class': 'form-select'}),
                    **commun)
                if point.answer_boolean is True:
                    self.initial[cle] = 'true'
                elif point.answer_boolean is False:
                    self.initial[cle] = 'false'

            elif point.answer_type == 'number':
                etiquette = point.label
                if point.unit:
                    etiquette = f'{point.label} ({point.unit})'
                self.fields[cle] = forms.DecimalField(
                    max_digits=12, decimal_places=3,
                    widget=forms.NumberInput(attrs={'class': 'form-control',
                                                    'step': 'any'}),
                    **{**commun, 'label': etiquette})
                self.initial[cle] = point.answer_number

            elif point.answer_type == 'date':
                self.fields[cle] = forms.DateField(
                    widget=forms.DateInput(attrs={'class': 'form-control',
                                                  'type': 'date'}),
                    **commun)
                self.initial[cle] = point.answer_date

            elif point.answer_type == 'choice':
                choix = [('', '— Pas encore renseigné —')]
                choix += [(str(option), str(option))
                          for option in (point.options or [])]
                self.fields[cle] = forms.ChoiceField(
                    choices=choix,
                    widget=forms.Select(attrs={'class': 'form-select'}),
                    **commun)
                self.initial[cle] = point.answer_choice

            elif point.answer_type == 'quote':
                champ = forms.ModelChoiceField(
                    queryset=self._devis,
                    empty_label='— Aucun devis désigné —',
                    widget=forms.Select(attrs={'class': 'form-select'}),
                    **commun)
                champ.label_from_instance = self._etiquette_du_devis
                if not self._il_y_a_des_devis:
                    champ.help_text = (
                        (point.help_text + ' ') if point.help_text else ''
                    ) + 'Aucun devis dans cette entreprise pour le moment.'
                self.fields[cle] = champ
                self.initial[cle] = point.answer_quote_id

            elif point.answer_type == 'supplier':
                self.fields[cle] = forms.ModelChoiceField(
                    queryset=self._fournisseurs,
                    empty_label='— Aucun fournisseur désigné —',
                    widget=forms.Select(attrs={'class': 'form-select'}),
                    **commun)
                self.initial[cle] = point.answer_supplier_id

            elif point.answer_type == 'photo':
                self.fields[cle] = forms.ImageField(
                    widget=forms.ClearableFileInput(attrs={
                        'class': 'form-control', 'accept': 'image/*'}),
                    **commun)
                # Pas d'`initial` sur un champ fichier : Django ne peut pas
                # pré-remplir un <input type="file">, et la photo déjà
                # enregistrée est affichée par le gabarit à côté du champ.

            else:
                self.fields[cle] = forms.CharField(
                    widget=forms.Textarea(attrs={'class': 'form-control',
                                                 'rows': 2}),
                    **commun)
                self.initial[cle] = point.answer_text

            self.fields[f'commentaire_{point.pk}'] = forms.CharField(
                label='Commentaire', required=False, max_length=300,
                widget=forms.TextInput(attrs={
                    'class': 'form-control form-control-sm',
                    'placeholder': 'Remarque…'}),
                initial=point.comment)

    def _devis_de_l_entreprise(self):
        """Les devis proposables, ceux du chantier d'abord.

        Bornés à l'ENTREPRISE et non au seul chantier, et c'est délibéré :
        un devis est souvent établi avant d'être rattaché au chantier, et
        un avenant peut vivre sur un autre chantier du même client. Le
        borner au chantier rendrait la liste vide précisément quand on en
        a besoin.

        Ce qui doit être interdit, c'est le devis d'une AUTRE société, et
        ça l'est. Pour que le reste se voie, chaque option porte son
        chantier : choisir celui du voisin de palier devient visible.
        """
        from .models import BTPQuote

        if self.company is None:
            return BTPQuote.objects.none()

        devis = (BTPQuote.objects
                 .filter(company=self.company)
                 .select_related('project', 'customer'))
        if self.project is not None:
            # Les devis de CE chantier remontent en tête de liste : c'est
            # ce qu'on cherche neuf fois sur dix.
            from django.db.models import Case, IntegerField, Value, When
            devis = devis.annotate(
                _priorite=Case(
                    When(project=self.project, then=Value(0)),
                    default=Value(1), output_field=IntegerField()),
            ).order_by('_priorite', '-issue_date')
        return devis

    def _fournisseurs_de_l_entreprise(self):
        if self.company is None:
            from apps.purchases.models import Supplier
            return Supplier.objects.none()
        from apps.purchases.models import Supplier
        return Supplier.objects.filter(
            company=self.company, is_active=True).order_by('name')

    @staticmethod
    def _etiquette_du_devis(devis):
        """« DEV-0012 — Mme Martin — 4 300,00 € HT — Rénovation Martin ».

        `__str__` ne donne que le numéro et le client. Sans le chantier ni
        le montant, deux devis du même client sont indiscernables dans la
        liste — et l'on en choisit un au hasard.
        """
        morceaux = [devis.number or 'Devis sans numéro', devis.customer.name,
                    f'{devis.total_ht:.2f} € HT']
        if devis.project_id:
            morceaux.append(devis.project.name)
        return ' — '.join(morceaux)

    def champs_par_point(self):
        """Les paires (point, champ principal, champ commentaire).

        Le gabarit en a besoin pour afficher la question, sa réponse et son
        commentaire ensemble. Itérer sur `form` donnerait les champs à plat,
        commentaires mêlés aux réponses, sans savoir lequel va avec lequel.
        """
        for point in self.points:
            yield (point,
                   self[f'point_{point.pk}'],
                   self[f'commentaire_{point.pk}'])


class ChoisirUnModeleForm(forms.Form):
    """Appliquer un modèle à un chantier qui n'a pas encore d'étapes."""

    template = forms.ModelChoiceField(
        queryset=ProjectTemplate.objects.none(),
        label='Modèle de chantier',
        widget=forms.Select(attrs={'class': 'form-select'}))
    remplacer = forms.BooleanField(
        label='Remplacer les étapes existantes', required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Supprime les étapes en place ET les réponses déjà '
                  'saisies. À cocher seulement pour repartir de zéro.')

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['template'].queryset = ProjectTemplate.objects.filter(
            company=company, is_active=True)
