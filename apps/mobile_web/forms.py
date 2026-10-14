"""Formulaire de prise de photo depuis un telephone."""

from django import forms


class PhotoMobileForm(forms.Form):
    """Une ou plusieurs photos, destinees a un chantier ou au fonds general.

    Aucun nouveau modele de stockage : les photos rejoignent les pieces
    jointes que l'ERP connait deja -- `btp.ProjectDocument` pour un chantier,
    `documents.Document` sinon. Inventer un stock parallele aurait produit des
    photos invisibles depuis les pages ou on les cherche.
    """

    chantier = forms.ChoiceField(
        label='Chantier',
        required=False,
        help_text='Laissez vide pour ranger la photo dans les documents '
                  "generaux de l'entreprise.",
    )

    libelle = forms.CharField(
        label='Libelle',
        max_length=180,
        required=False,
        help_text='Facultatif. A defaut, la date et l heure servent de nom.',
    )

    description = forms.CharField(
        label='Note',
        required=False,
        widget=forms.Textarea(attrs={'rows': 2}),
    )

    visible_client = forms.BooleanField(
        label='Visible par le client',
        required=False,
        help_text='Decoche par defaut : une photo de chantier ne doit pas '
                  'devenir visible sans decision.',
    )

    def __init__(self, *args, chantiers=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['chantier'].choices = [('', 'Documents generaux')] + [
            (str(p.pk), f'{p.code} - {p.name}' if p.code else p.name)
            for p in chantiers
        ]
