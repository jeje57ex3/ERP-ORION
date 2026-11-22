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
        # La signature n'est PAS ici : elle se trace dans un cadre et
        # s'enregistre par sa propre adresse (accounts:signature_save), qui
        # verifie notamment qu'un cadre vide n'est pas accepte. La laisser
        # aussi dans ce formulaire ferait deux chemins d'ecriture pour le
        # meme champ, dont un sans ce controle.
        fields = [
            'phone', 'mobile', 'job_title', 'department',
            'avatar', 'bio', 'language', 'items_per_page',
            'email_notifications',
        ]
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3}),
        }


class ChangementDeMotDePasseForm(PasswordChangeForm):
    """`PasswordChangeForm`, plus le refus de reposer le même mot de passe.

    **LE TROU QUE CECI FERME.** Un compte neuf arrive ici avec l'obligation
    de remplacer son code provisoire. `PasswordChangeForm` ne compare pas
    le nouveau mot de passe à l'ancien : ressaisir le code reçu par
    courriel aurait donc satisfait le formulaire, levé l'obligation, et
    laissé en place un mot de passe engendré par la machine — que
    l'administrateur a vu passer dans les journaux du serveur de courriel,
    et qui dort dans une boîte de réception. L'écran aurait affiché « mot
    de passe modifié » sans que rien ne change.

    Le contrôle vaut aussi pour un changement volontaire : reposer le même
    mot de passe n'est jamais ce qu'on voulait faire, et le dire coûte
    moins qu'un faux sentiment de changement.

    Comparé par `check_password` sur l'empreinte, et non en comparant les
    deux chaînes saisies : l'ancien mot de passe n'est pas forcément celui
    que le champ « ancien » contient — sur un compte dont l'empreinte a
    changé entre l'affichage et l'envoi, c'est l'empreinte qui fait foi.
    """

    def clean_new_password1(self):
        nouveau = self.cleaned_data.get('new_password1')
        if nouveau and self.user.check_password(nouveau):
            raise ValidationError(
                'Ce mot de passe est déjà celui du compte. Choisissez-en un '
                'autre : le code reçu par courriel ne doit pas rester votre '
                'mot de passe.')
        return nouveau


class UserCreateForm(forms.ModelForm):
    """Tout sauf le mot de passe : un code provisoire part par courriel.

    **CE QUI A ÉTÉ RETIRÉ, ET POURQUOI.** Ce formulaire demandait
    `password1`/`password2` à l'administrateur, qui devait ensuite
    transmettre le mot de passe au nouvel arrivant. Trois défauts
    superposés : l'administrateur connaissait le mot de passe de quelqu'un
    d'autre, celui-ci transitait par un canal que personne ne maîtrise
    (message, papier, de vive voix), et rien n'obligeait jamais à le
    changer — un compte ouvert en janvier gardait en octobre le mot de
    passe tapé par son patron.

    Désormais, `apps/accounts/services/code_provisoire.py` engendre un
    code aléatoire, l'envoie à l'adresse saisie ci-dessous, et le profil
    porte l'obligation de le remplacer à la première connexion.

    **L'ADRESSE DEVIENT OBLIGATOIRE**, et c'est la conséquence directe :
    elle est le seul chemin par lequel le code atteint son destinataire.
    `User.email` est `blank=True` dans Django, donc sans cette ligne un
    compte pouvait se créer sans adresse — et un compte sans adresse est
    maintenant un compte auquel personne ne peut se connecter. Mieux vaut
    le refuser à la saisie que le découvrir au premier appel.
    """

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

        # L'adresse est le seul chemin du code provisoire : sans elle, le
        # compte créé serait inutilisable par son titulaire.
        self.fields['email'].required = True
        self.fields['email'].label = 'Adresse de courriel'
        self.fields['email'].help_text = (
            'Le code provisoire de première connexion y sera envoyé. '
            'Vérifiez-la : une adresse fautive crée un compte auquel '
            'personne ne peut se connecter.')

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

    def clean_email(self):
        """Refuse une adresse déjà portée par un autre compte.

        `User.email` n'est pas unique dans Django, et ce n'était sans
        conséquence que tant que l'adresse ne servait à rien. Elle reçoit
        maintenant les codes de connexion : deux comptes sur la même
        adresse, et son titulaire reçoit des codes sans savoir auquel des
        deux ils servent — puis se plaint que « le code ne marche pas ».
        """
        adresse = (self.cleaned_data.get('email') or '').strip()
        if adresse and User.objects.filter(email__iexact=adresse).exists():
            raise forms.ValidationError(
                'Un compte utilise déjà cette adresse. Le code de première '
                'connexion y serait envoyé sans qu’on sache lequel des deux '
                'comptes il ouvre.')
        return adresse

    def save(self, commit=True):
        """Enregistre le compte SANS mot de passe utilisable.

        `set_unusable_password()` et non un mot de passe vide : un mot de
        passe vide est un mot de passe, et Django le comparerait à la
        saisie. Un mot de passe inutilisable ne peut satisfaire aucune
        connexion, quelle que soit la saisie.

        C'est aussi l'état sûr entre les deux écritures : si la pose du
        code provisoire échouait juste après, le compte resterait
        inaccessible au lieu d'être ouvert à tous.
        """
        user = super().save(commit=False)
        user.set_unusable_password()
        if commit:
            user.save()
        return user
