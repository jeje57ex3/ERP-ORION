from django import forms
from .models import Document, DocumentCategory


class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = [
            'title', 'document_type', 'category', 'description',
            'file', 'version', 'tags', 'is_confidential',
        ]
        # « chantier » n'est pas un champ du modele : Document n'a aucun
        # lien vers un chantier, et lui en ajouter un ferait doublon avec
        # ProjectDocument, qui existe deja et porte bien davantage
        # (visibilite client, versions, document obligatoire). On route
        # donc vers ce modele-la plutot que d'en creer un second.
        #
        # Le champ est ajoute dans __init__, apres la liste ci-dessus.
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'tags': forms.TextInput(attrs={'placeholder': 'tag1, tag2, tag3...'}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields['category'].queryset = DocumentCategory.objects.filter(company=company)

        # Le chantier est FACULTATIF : la plupart des documents d'une
        # entreprise n'en relevent pas. Choisi, le document part dans les
        # documents du chantier et non dans cette liste.
        #
        # Le champ est declare HORS du « if company » : a l'interieur, un
        # formulaire construit sans entreprise ne l'aurait pas du tout, et
        # le gabarit qui le rend afficherait un vide sans que rien ne
        # l'explique. Sans entreprise, la liste est seulement vide.
        from apps.btp.models import BTPProject
        self.fields['chantier'] = forms.ModelChoiceField(
            queryset=(BTPProject.objects.filter(company=company)
                      .order_by('-created_at') if company
                      else BTPProject.objects.none()),
            required=False,
            label='Chantier',
            empty_label='— Document de l’entreprise —',
            help_text='Choisissez un chantier pour classer ce document dans '
                      'ses documents plutôt qu’ici.',
        )
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'form-select form-select-sm')
            elif isinstance(widget, forms.FileInput):
                widget.attrs.setdefault('class', 'form-control form-control-sm')
            elif isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault('class', 'form-check-input')
            else:
                widget.attrs.setdefault('class', 'form-control form-control-sm')
