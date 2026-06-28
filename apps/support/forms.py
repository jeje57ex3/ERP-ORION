from django import forms
from .models import Ticket, TicketMessage


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = [
            'ticket_type', 'subject', 'description', 'priority',
            'status', 'customer', 'assigned_to', 'resolution_notes',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5}),
            'resolution_notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            from apps.crm.models import Customer
            self.fields['customer'].queryset = Customer.objects.filter(company=company, is_active=True)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'form-select form-select-sm')
            else:
                widget.attrs.setdefault('class', 'form-control form-control-sm')


class TicketMessageForm(forms.ModelForm):
    class Meta:
        model = TicketMessage
        fields = ['message', 'is_internal', 'attachment']
        widgets = {
            'message': forms.Textarea(attrs={'rows': 4, 'class': 'form-control form-control-sm', 'placeholder': 'Votre message...'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control form-control-sm'}),
        }
