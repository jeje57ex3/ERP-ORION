"""
Assistant de premier accès (/setup/) — formulaire web remplaçant l'ancien
wizard console de l'appliance Proxmox. Affiché automatiquement par
SetupRequiredMiddleware tant qu'aucune Company n'existe en base.
"""
from django import forms
from django.contrib.auth import login
from django.shortcuts import render, redirect

from .models import Company
from .setup_service import complete_initial_setup


TIMEZONE_CHOICES = [
    ('Europe/Paris', 'Europe/Paris'),
    ('Europe/Brussels', 'Europe/Brussels'),
    ('Europe/Zurich', 'Europe/Zurich'),
    ('Europe/London', 'Europe/London'),
    ('Europe/Madrid', 'Europe/Madrid'),
    ('Europe/Rome', 'Europe/Rome'),
    ('America/Montreal', 'America/Montreal'),
    ('Africa/Casablanca', 'Africa/Casablanca'),
    ('Indian/Reunion', 'Indian/Reunion'),
    ('UTC', 'UTC'),
]


class SetupForm(forms.Form):
    company_name = forms.CharField(
        label="Nom de l'entreprise", max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ma Société'}),
    )
    admin_email = forms.EmailField(
        label='Email administrateur',
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'admin@exemple.fr'}),
    )
    admin_password = forms.CharField(
        label='Mot de passe', min_length=8,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '••••••••'}),
    )
    admin_password_confirm = forms.CharField(
        label='Confirmer le mot de passe',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '••••••••'}),
    )
    timezone = forms.ChoiceField(
        label='Fuseau horaire', choices=TIMEZONE_CHOICES, initial='Europe/Paris',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def clean(self):
        cleaned = super().clean()
        pwd, confirm = cleaned.get('admin_password'), cleaned.get('admin_password_confirm')
        if pwd and confirm and pwd != confirm:
            self.add_error('admin_password_confirm', 'Les deux mots de passe ne correspondent pas.')
        return cleaned


def setup_wizard(request):
    if Company.objects.exists():
        return redirect('/')

    form = SetupForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        user = complete_initial_setup(
            company_name=form.cleaned_data['company_name'],
            admin_email=form.cleaned_data['admin_email'],
            admin_password=form.cleaned_data['admin_password'],
            timezone=form.cleaned_data['timezone'],
        )
        login(request, user)
        return redirect('core:dashboard')

    return render(request, 'core/setup_wizard.html', {'form': form})
