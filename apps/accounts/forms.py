from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.core.exceptions import ValidationError
from .models import UserProfile


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label='Nom d\'utilisateur',
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': 'Votre identifiant',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control form-control-lg',
            'placeholder': '••••••••',
        })
    )
    remember_me = forms.BooleanField(required=False, label='Se souvenir de moi')


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            'phone', 'mobile', 'job_title', 'department',
            'avatar', 'signature', 'bio', 'language', 'items_per_page',
            'email_notifications',
        ]
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3}),
            'signature': forms.ClearableFileInput(attrs={
                'accept': 'image/png,image/jpeg,image/webp',
            }),
        }


class UserCreateForm(forms.ModelForm):
    password1 = forms.CharField(label='Mot de passe', widget=forms.PasswordInput())
    password2 = forms.CharField(label='Confirmer', widget=forms.PasswordInput())
    role = forms.ChoiceField(label='Rôle', choices=UserProfile.role.field.choices if hasattr(UserProfile, 'role') else [])

    employee = forms.ModelChoiceField(
        queryset=None,
        required=False,
        label='Salarié lié',
        help_text='Obligatoire pour les rôles non administrateurs, '
                  'sauf si la case ci-dessous est cochée.',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    without_employee_record = forms.BooleanField(
        required=False,
        label='Ce compte ne correspond à aucun salarié',
        help_text='Prestataire, expert-comptable externe, client, compte de '
                  'service. À cocher pour créer le compte sans fiche salarié.',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

    def __init__(self, *args, company=None, employee_prefill=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company

        # Une seule source pour la liste et pour son diagnostic : deux
        # filtres écrits séparément finissent par ne plus dire la même
        # chose, et l'écran expliquerait alors une liste qui n'est pas
        # celle qu'il affiche.
        from apps.accounts.services.user_employee_link_service import (
            diagnostic_rattachement,
            salaries_rattachables,
        )
        self.fields['employee'].queryset = salaries_rattachables(company)
        self.diagnostic_salaries = diagnostic_rattachement(company)

        if employee_prefill:
            self.fields['employee'].initial = employee_prefill

    def clean(self):
        """Un compte non administrateur est rattaché, ou déclaré non salarié.

        Les deux ensemble sont contradictoires et le dire vaut mieux que
        choisir en silence : cochée, la case ferait ignorer un salarié
        sélectionné exprès, et l'administrateur croirait la liaison faite.
        """
        cleaned = super().clean()
        role = cleaned.get('role', 'user')
        employee = cleaned.get('employee')
        sans_salarie = cleaned.get('without_employee_record')
        exempt_roles = ('superadmin', 'admin')

        if employee and sans_salarie:
            self.add_error(
                'without_employee_record',
                'Un salarié est sélectionné : décochez cette case, ou retirez '
                'le salarié.'
            )
        elif role not in exempt_roles and not employee and not sans_salarie:
            # Ni rattachement ni déclaration : c'est l'oubli que l'on veut
            # continuer d'attraper.
            self.add_error(
                'employee',
                'Un utilisateur non administrateur doit être lié à un salarié, '
                'ou déclaré sans fiche salarié en cochant la case ci-dessous.'
            )
        return cleaned

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1')
        p2 = self.cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('Les mots de passe ne correspondent pas.')
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user
