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
            'avatar', 'bio', 'language', 'items_per_page',
            'email_notifications',
        ]
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3}),
        }


class UserCreateForm(forms.ModelForm):
    password1 = forms.CharField(label='Mot de passe', widget=forms.PasswordInput())
    password2 = forms.CharField(label='Confirmer', widget=forms.PasswordInput())
    role = forms.ChoiceField(label='Rôle', choices=UserProfile.role.field.choices if hasattr(UserProfile, 'role') else [])

    employee = forms.ModelChoiceField(
        queryset=None,
        required=False,
        label='Salarié lié',
        help_text='Obligatoire pour les rôles non administrateurs.',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

    def __init__(self, *args, company=None, employee_prefill=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        from apps.hr.models import Employee
        if company:
            self.fields['employee'].queryset = Employee.objects.filter(
                company=company, is_active=True, user__isnull=True,
            ).order_by('last_name', 'first_name')
        else:
            self.fields['employee'].queryset = Employee.objects.filter(
                is_active=True, user__isnull=True,
            ).order_by('last_name', 'first_name')
        if employee_prefill:
            self.fields['employee'].initial = employee_prefill

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get('role', 'user')
        employee = cleaned.get('employee')
        exempt_roles = ('superadmin', 'admin')
        is_staff = False  # formulaire de création
        is_superuser = False
        if role not in exempt_roles and not is_staff and not is_superuser:
            if not employee:
                raise ValidationError(
                    'Un utilisateur non administrateur doit être lié à un salarié.'
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
