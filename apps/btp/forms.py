from django import forms
from .models import BTPProject, BTPQuote, SituationOfWorks, BTPTimesheet


class BTPProjectForm(forms.ModelForm):
    class Meta:
        model = BTPProject
        fields = [
            'code', 'name', 'customer', 'status', 'description',
            'address', 'city', 'zip_code', 'project_manager', 'site_foreman',
            'start_date', 'end_date', 'actual_start_date', 'actual_end_date',
            'estimated_budget', 'retention_rate', 'market_type', 'market_number', 'notes',
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'zip_code': forms.TextInput(attrs={'class': 'form-control'}),
            'project_manager': forms.Select(attrs={'class': 'form-select'}),
            'site_foreman': forms.TextInput(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'actual_start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'actual_end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'estimated_budget': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'retention_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'market_type': forms.TextInput(attrs={'class': 'form-control'}),
            'market_number': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class BTPQuoteForm(forms.ModelForm):
    class Meta:
        model = BTPQuote
        fields = ['project', 'customer', 'status', 'issue_date', 'validity_date', 'subject', 'notes']
        widgets = {
            'project': forms.Select(attrs={'class': 'form-select'}),
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'issue_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'validity_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'subject': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }


class SituationForm(forms.ModelForm):
    class Meta:
        model = SituationOfWorks
        fields = ['project', 'number', 'status', 'period_start', 'period_end', 'cumulative_amount', 'previous_amount', 'notes']
        widgets = {
            'project': forms.Select(attrs={'class': 'form-select'}),
            'number': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'period_start': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'period_end': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'cumulative_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'previous_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class BTPTimesheetForm(forms.ModelForm):
    class Meta:
        model = BTPTimesheet
        fields = ['project', 'employee', 'work_date', 'hours', 'overtime_hours', 'task_description', 'notes']
        widgets = {
            'project': forms.Select(attrs={'class': 'form-select'}),
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'work_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'hours': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.25'}),
            'overtime_hours': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.25'}),
            'task_description': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
