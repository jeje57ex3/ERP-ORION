from django import forms


class TwoFactorCodeForm(forms.Form):
    code = forms.CharField(
        label="Code de vérification",
        max_length=20,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "autocomplete": "one-time-code",
            "inputmode": "numeric",
            "placeholder": "123456",
            "autofocus": True,
        }),
    )
    remember_device = forms.BooleanField(
        label="Faire confiance à cet appareil pendant 30 jours",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )


class DisableTwoFactorForm(forms.Form):
    password = forms.CharField(
        label="Mot de passe actuel",
        widget=forms.PasswordInput(attrs={"class": "form-control", "autocomplete": "current-password"}),
    )


class RecoveryCodeForm(forms.Form):
    recovery_code = forms.CharField(
        label="Code de récupération",
        max_length=30,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "ABCDE-12345"}),
    )
