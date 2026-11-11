from django import forms
from .models import Store, POSSession, POSTicket, LoyaltyCard


class StoreForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = ['name', 'code', 'address', 'city', 'phone', 'email', 'is_active', 'opening_hours']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
            'opening_hours': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                continue
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'form-select form-select-sm')
            else:
                widget.attrs.setdefault('class', 'form-control form-control-sm')


class POSSessionForm(forms.ModelForm):
    """Le formulaire d'OUVERTURE d'une session de caisse.

    « status » et « closing_cash » en ont été retirés, et c'est ce qui
    corrige une panne muette : `status` porte une valeur par défaut au
    niveau du modèle mais pas `blank=True`, donc Django en faisait un champ
    OBLIGATOIRE — une valeur par défaut fournit l'initiale, elle ne rend
    rien facultatif. Le gabarit ne le rendait nulle part, il n'était donc
    jamais envoyé, et l'ouverture d'une caisse échouait à chaque fois en
    réaffichant la même page sans le moindre message.

    Les retirer plutôt que les ajouter au gabarit est le bon sens : une
    session qu'on ouvre est ouverte par définition, et son fond de caisse
    de clôture n'existe pas encore. Le modèle pose « open » tout seul, et
    la clôture passe par sa propre vue.
    """

    class Meta:
        model = POSSession
        fields = ['store', 'opening_cash']

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields['store'].queryset = Store.objects.filter(company=company, is_active=True)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'form-select form-select-sm')
            else:
                widget.attrs.setdefault('class', 'form-control form-control-sm')


class POSTicketForm(forms.ModelForm):
    class Meta:
        model = POSTicket
        fields = ['session', 'customer', 'total_ht', 'total_tva', 'total_ttc', 'discount', 'payment_method']

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            from apps.crm.models import Customer
            self.fields['customer'].queryset = Customer.objects.filter(company=company)
            self.fields['customer'].required = False
            self.fields['session'].queryset = POSSession.objects.filter(company=company, status='open')
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'form-select form-select-sm')
            else:
                widget.attrs.setdefault('class', 'form-control form-control-sm')
