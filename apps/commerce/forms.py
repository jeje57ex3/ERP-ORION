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
    class Meta:
        model = POSSession
        fields = ['store', 'opening_cash', 'closing_cash', 'status']

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
