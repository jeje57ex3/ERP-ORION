from django import forms
from .models import AutomationRule, TRIGGER_TYPE_CHOICES


class AutomationRuleForm(forms.ModelForm):
    class Meta:
        model = AutomationRule
        fields = ['name', 'description', 'trigger_type', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].widget.attrs['placeholder'] = 'Ex : Relance factures impayées'
        self.fields['trigger_type'].widget.attrs['class'] = 'form-select'
