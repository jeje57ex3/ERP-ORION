from django import forms
from .models import Equipment, AudioEvent, EquipmentReservation, Technician


class EquipmentForm(forms.ModelForm):
    class Meta:
        model = Equipment
        fields = [
            'name', 'brand', 'model', 'reference', 'serial_number',
            'category', 'quantity', 'available_quantity',
            'rental_price_day', 'replacement_value',
            'purchase_date', 'purchase_price', 'status',
            'last_maintenance_date', 'next_maintenance_date',
            'description', 'notes', 'is_active',
        ]
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'last_maintenance_date': forms.DateInput(attrs={'type': 'date'}),
            'next_maintenance_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            from .models import EquipmentCategory
            self.fields['category'].queryset = EquipmentCategory.objects.filter(company=company)
            self.fields['category'].required = False
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                continue
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'form-select form-select-sm')
            else:
                widget.attrs.setdefault('class', 'form-control form-control-sm')


class AudioEventForm(forms.ModelForm):
    class Meta:
        model = AudioEvent
        fields = [
            'name', 'event_type', 'customer', 'status', 'event_date',
            'setup_date', 'teardown_date', 'start_time', 'end_time',
            'venue', 'venue_address', 'expected_attendance',
            'estimated_amount', 'deposit_amount',
            'description', 'technical_notes', 'notes',
        ]
        widgets = {
            'event_date': forms.DateInput(attrs={'type': 'date'}),
            'setup_date': forms.DateInput(attrs={'type': 'date'}),
            'teardown_date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
            'venue_address': forms.Textarea(attrs={'rows': 2}),
            'description': forms.Textarea(attrs={'rows': 3}),
            'technical_notes': forms.Textarea(attrs={'rows': 3}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            from apps.crm.models import Customer
            self.fields['customer'].queryset = Customer.objects.filter(company=company)
            self.fields['customer'].required = False
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'form-select form-select-sm')
            else:
                widget.attrs.setdefault('class', 'form-control form-control-sm')


class ReservationForm(forms.ModelForm):
    class Meta:
        model = EquipmentReservation
        fields = [
            'event', 'customer', 'equipment', 'quantity',
            'start_date', 'end_date', 'status',
            'daily_rate', 'total_amount', 'deposit_amount', 'notes',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            from apps.crm.models import Customer
            self.fields['customer'].queryset = Customer.objects.filter(company=company)
            self.fields['customer'].required = False
            self.fields['event'].queryset = AudioEvent.objects.filter(company=company)
            self.fields['event'].required = False
            self.fields['equipment'].queryset = Equipment.objects.filter(company=company, is_active=True)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'form-select form-select-sm')
            else:
                widget.attrs.setdefault('class', 'form-control form-control-sm')


class TechnicianForm(forms.ModelForm):
    class Meta:
        model = Technician
        fields = ['name', 'specialties', 'phone', 'email', 'day_rate', 'is_employee', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                continue
            else:
                widget.attrs.setdefault('class', 'form-control form-control-sm')
