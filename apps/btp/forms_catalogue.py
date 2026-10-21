"""Formulaire d'une source de catalogue web.

La correspondance des colonnes est stockée en JSON sur le modèle, mais
saisie **champ par champ** : demander à l'exploitant d'écrire
`{"nom": "Designation"}` à la main, c'est lui demander de produire du JSON
valide pour configurer un import — et une virgule oubliée donnerait une
erreur technique au lieu d'une erreur de saisie.
"""

from django import forms

from .models import CatalogueSource


class CatalogueSourceForm(forms.ModelForm):
    class Meta:
        model = CatalogueSource
        fields = ['name', 'url', 'format', 'delimiteur', 'encodage',
                  'nature_par_defaut', 'supplier', 'intervalle_minutes',
                  'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Point P — tarifs 2026'}),
            'url': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://exemple.fr/tarifs.csv'}),
            'format': forms.Select(attrs={'class': 'form-select'}),
            'delimiteur': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': ';'}),
            'encodage': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'auto'}),
            'nature_par_defaut': forms.Select(attrs={'class': 'form-select'}),
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'intervalle_minutes': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 15}),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company

        from apps.purchases.models import Supplier
        self.fields['supplier'].queryset = (
            Supplier.objects.filter(company=company, is_active=True)
            .order_by('name') if company is not None
            else Supplier.objects.none()
        )
        self.fields['supplier'].required = False

        # Un champ de saisie par champ importable, prerempli depuis le JSON.
        existantes = (self.instance.colonnes or {}) if self.instance else {}
        for champ, libelle in CatalogueSource.CHAMPS_IMPORTABLES.items():
            self.fields[f'colonne_{champ}'] = forms.CharField(
                label=libelle,
                required=False,
                initial=existantes.get(champ, ''),
                widget=forms.TextInput(attrs={
                    'class': 'form-control form-control-sm',
                    'placeholder': 'nom de la colonne dans le fichier',
                }),
            )

    @property
    def champs_de_colonnes(self):
        """Les champs de correspondance, pour que le gabarit les parcoure."""
        for champ in CatalogueSource.CHAMPS_IMPORTABLES:
            yield self[f'colonne_{champ}']

    def clean(self):
        donnees = super().clean()

        colonnes = {}
        for champ in CatalogueSource.CHAMPS_IMPORTABLES:
            valeur = (donnees.get(f'colonne_{champ}') or '').strip()
            if valeur:
                colonnes[champ] = valeur

        if 'nom' not in colonnes:
            # Sans designation, un article importe n'est pas lisible : la
            # refuser ici vaut mieux que de produire un catalogue de lignes
            # vides qu'il faudra retrouver et effacer.
            self.add_error(
                'colonne_nom',
                'Indispensable : sans la colonne de la désignation, les '
                'articles importés n’auraient pas de nom.')

        donnees['_colonnes'] = colonnes
        return donnees

    def save(self, commit=True):
        source = super().save(commit=False)
        source.colonnes = self.cleaned_data.get('_colonnes', {})
        if commit:
            source.save()
        return source


class DetectionForm(forms.Form):
    """Un PDF à déposer, ou une adresse de page à analyser. Pas les deux.

    Pas les deux, et le refuser plutôt que choisir : trancher en silence
    ferait analyser l'un en ignorant l'autre, et l'exploitant croirait
    avoir obtenu le résultat du second.
    """

    url = forms.URLField(
        label='Adresse d’une page produit',
        required=False, max_length=500,
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://fabricant.example/produit/reference',
        }),
        help_text='La page d’UN produit donne un meilleur résultat qu’une '
                  'page de catégorie.',
    )

    fichier = forms.FileField(
        label='Ou un tarif en PDF',
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control', 'accept': 'application/pdf',
        }),
        help_text='Le PDF doit contenir du texte. Un document scanné ne '
                  'porte qu’une image de la page : rien n’en sortira.',
    )

    def clean(self):
        donnees = super().clean()
        url = (donnees.get('url') or '').strip()
        fichier = donnees.get('fichier')

        if url and fichier:
            self.add_error(
                'fichier',
                'Une adresse OU un PDF, pas les deux : indiquez ce que vous '
                'voulez analyser.')
        elif not url and not fichier:
            self.add_error(
                'url', 'Indiquez une adresse de page, ou déposez un PDF.')

        if fichier:
            nom = (getattr(fichier, 'name', '') or '').lower()
            if not nom.endswith('.pdf'):
                self.add_error('fichier', 'Le fichier doit être un PDF.')
            else:
                # L'extension ne prouve rien : un .docx renomme passerait.
                debut = fichier.read(5)
                fichier.seek(0)
                if not debut.startswith(b'%PDF'):
                    self.add_error(
                        'fichier',
                        'Ce fichier porte l’extension .pdf mais n’en est '
                        'pas un.')

        return donnees
