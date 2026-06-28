from django import forms
from .models import BillOfMaterials, ManufacturingOrder, WorkCenter


class BOMForm(forms.ModelForm):
    class Meta:
        model = BillOfMaterials
        fields = ['product', 'name', 'version', 'quantity', 'unit', 'is_active', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            from apps.inventory.models import Product
            self.fields['product'].queryset = Product.objects.filter(company=company)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                continue
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'form-select form-select-sm')
            else:
                widget.attrs.setdefault('class', 'form-control form-control-sm')


class ManufacturingOrderForm(forms.ModelForm):
    class Meta:
        model = ManufacturingOrder
        fields = ['product', 'bom', 'quantity_planned', 'status',
                  'planned_start', 'planned_end', 'notes']
        widgets = {
            'planned_start': forms.DateInput(attrs={'type': 'date'}),
            'planned_end': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            from apps.inventory.models import Product
            self.fields['product'].queryset = Product.objects.filter(company=company)
            self.fields['bom'].queryset = BillOfMaterials.objects.filter(company=company, is_active=True)
            self.fields['bom'].required = False
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.Select):
                widget.attrs.setdefault('class', 'form-select form-select-sm')
            else:
                widget.attrs.setdefault('class', 'form-control form-control-sm')


class WorkCenterForm(forms.ModelForm):
    class Meta:
        model = WorkCenter
        fields = ['name', 'code', 'capacity', 'cost_per_hour', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                continue
            else:
                widget.attrs.setdefault('class', 'form-control form-control-sm')
