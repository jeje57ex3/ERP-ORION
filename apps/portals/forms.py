from django import forms


class ClientPortalSignupForm(forms.Form):
    """Formulaire d'inscription au portail client."""

    first_name = forms.CharField(
        label='Prénom', max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'Votre prénom', 'autocomplete': 'given-name'}),
    )
    last_name = forms.CharField(
        label='Nom', max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'Votre nom', 'autocomplete': 'family-name'}),
    )
    email = forms.EmailField(
        label='Adresse email',
        widget=forms.EmailInput(attrs={'placeholder': 'votre@email.com', 'autocomplete': 'email'}),
    )
    phone = forms.CharField(
        label='Téléphone', max_length=20, required=False,
        widget=forms.TextInput(attrs={'placeholder': '06 00 00 00 00', 'autocomplete': 'tel'}),
    )
    company_name = forms.CharField(
        label='Nom de votre entreprise', max_length=200, required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Optionnel'}),
    )
    password = forms.CharField(
        label='Mot de passe', min_length=8,
        widget=forms.PasswordInput(attrs={'placeholder': 'Minimum 8 caractères', 'autocomplete': 'new-password'}),
        help_text='Minimum 8 caractères.',
    )
    password_confirm = forms.CharField(
        label='Confirmer le mot de passe',
        widget=forms.PasswordInput(attrs={'placeholder': 'Répétez votre mot de passe', 'autocomplete': 'new-password'}),
    )
    message = forms.CharField(
        label='Message (optionnel)', required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Un message pour l\'entreprise ?'}),
    )
    accept_terms = forms.BooleanField(
        label='J\'accepte les conditions d\'utilisation',
        error_messages={'required': 'Vous devez accepter les conditions d\'utilisation.'},
    )
    # Champ honeypot anti-spam (caché, ne doit pas être rempli)
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    def clean_website(self):
        value = self.cleaned_data.get('website', '')
        if value:
            raise forms.ValidationError('Soumission bloquée.')
        return value

    def clean_email(self):
        return self.cleaned_data['email'].lower().strip()

    def clean_password(self):
        pwd = self.cleaned_data.get('password', '')
        if len(pwd) < 8:
            raise forms.ValidationError('Le mot de passe doit contenir au moins 8 caractères.')
        return pwd

    def clean(self):
        cleaned = super().clean()
        pwd = cleaned.get('password')
        pwd_confirm = cleaned.get('password_confirm')
        if pwd and pwd_confirm and pwd != pwd_confirm:
            self.add_error('password_confirm', 'Les mots de passe ne correspondent pas.')
        return cleaned


class RejectSignupForm(forms.Form):
    """Formulaire de refus d'une demande d'inscription (admin ERP)."""
    reason = forms.CharField(
        label='Raison du refus (optionnel)', required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Expliquer la raison du refus...'}),
    )
