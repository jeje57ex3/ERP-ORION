from django import forms
from django.contrib.auth.models import User
from .models import (
    EmployeeProfile, WorkMission, WorkTask, DedicatedTimeBlock,
    CustomerRequest, EmployeeAvailabilityConstraint,
)


class EmployeeProfileForm(forms.ModelForm):
    class Meta:
        model = EmployeeProfile
        fields = [
            'user', 'role', 'color_code',
            'default_hours_per_day', 'weekly_capacity_hours',
            'skills',
            'accepts_overtime', 'max_overtime_hours_per_week',
            'normal_work_start', 'normal_work_end',
            'lunch_break_start', 'lunch_break_end',
            'planning_notes',
            'is_active', 'notes',
        ]
        widgets = {
            'user': forms.Select(attrs={'class': 'form-select'}),
            'role': forms.Select(attrs={'class': 'form-select'}),
            'color_code': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'default_hours_per_day': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '24', 'step': '0.5'}),
            'weekly_capacity_hours': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '80', 'step': '0.5'}),
            'max_overtime_hours_per_week': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '40', 'step': '0.5'}),
            'normal_work_start': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'normal_work_end': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'lunch_break_start': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'lunch_break_end': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'planning_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    skills_input = forms.CharField(
        required=False,
        label='Compétences',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'support, ecommerce, logistique, technique, creation...',
        }),
        help_text='Séparées par des virgules. Ex : support, ecommerce, logistique',
    )

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['skills_input'].initial = ', '.join(self.instance.skills or [])
        self.fields.pop('skills')
        self.fields['max_overtime_hours_per_week'].required = False
        self.fields['lunch_break_start'].required = False
        self.fields['lunch_break_end'].required = False
        self.fields['planning_notes'].required = False
        if company is not None:
            self.fields['user'].queryset = User.objects.filter(is_active=True, profile__companies=company)

    def save(self, commit=True):
        instance = super().save(commit=False)
        raw = self.cleaned_data.get('skills_input', '')
        instance.skills = [s.strip().lower() for s in raw.split(',') if s.strip()]
        if commit:
            instance.save()
        return instance


class EmployeeAvailabilityConstraintForm(forms.ModelForm):
    class Meta:
        model = EmployeeAvailabilityConstraint
        fields = [
            'employee', 'title', 'description',
            'constraint_type', 'priority', 'recurrence',
            'weekday', 'starts_at', 'ends_at',
            'start_time', 'end_time',
            'is_active', 'can_be_overridden_by_manager',
        ]
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'constraint_type': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'recurrence': forms.Select(attrs={'class': 'form-select'}),
            'weekday': forms.Select(attrs={'class': 'form-select'}),
            'starts_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'ends_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields['employee'].queryset = EmployeeProfile.objects.filter(
                company=company, is_active=True,
            ).select_related('user')
        self.fields['employee'].empty_label = '— Sélectionner un salarié —'
        self.fields['weekday'].required = False
        self.fields['starts_at'].required = False
        self.fields['ends_at'].required = False
        self.fields['start_time'].required = False
        self.fields['end_time'].required = False
        self.fields['description'].required = False


class WorkMissionForm(forms.ModelForm):
    class Meta:
        model = WorkMission
        fields = ['name', 'code', 'description', 'status', 'priority', 'start_date', 'end_date', 'estimated_hours', 'color_code']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: PROJ-01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'estimated_hours': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.5'}),
            'color_code': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_date')
        end = cleaned_data.get('end_date')
        if start and end and end < start:
            self.add_error('end_date', 'La date de fin doit être après la date de début.')
        return cleaned_data


class WorkTaskForm(forms.ModelForm):
    class Meta:
        model = WorkTask
        fields = ['name', 'description', 'status', 'priority', 'estimated_hours', 'estimated_minutes', 'customer_request', 'assigned_to', 'due_date', 'is_locked']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'estimated_hours': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.5'}),
            'estimated_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '15', 'placeholder': '60'}),
            'customer_request': forms.Select(attrs={'class': 'form-select'}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer_request'].required = False
        self.fields['customer_request'].empty_label = '— Aucune demande —'
        if company:
            self.fields['customer_request'].queryset = CustomerRequest.objects.filter(
                company=company
            ).exclude(status='cancelled')
            self.fields['assigned_to'].queryset = User.objects.filter(
                is_active=True, profile__companies=company
            )


class CustomerRequestForm(forms.ModelForm):
    class Meta:
        model = CustomerRequest
        fields = [
            'customer', 'website', 'brand_key',
            'title', 'description',
            'source', 'status', 'urgency',
            'requested_deadline', 'estimated_minutes',
            'required_skill',
            'assigned_employee', 'mission',
            'auto_planning_enabled', 'is_locked',
        ]
        widgets = {
            'customer': forms.Select(attrs={'class': 'form-select'}),
            'website': forms.Select(attrs={'class': 'form-select'}),
            'brand_key': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'siecle, lunea...'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'source': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'urgency': forms.Select(attrs={'class': 'form-select'}),
            'requested_deadline': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'estimated_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': '5', 'step': '5'}),
            'required_skill': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'support, ecommerce, logistique...'}),
            'assigned_employee': forms.Select(attrs={'class': 'form-select'}),
            'mission': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['customer'].required = False
        self.fields['customer'].empty_label = '— Aucun client —'
        self.fields['website'].required = False
        self.fields['website'].empty_label = '— Aucun site —'
        self.fields['assigned_employee'].required = False
        self.fields['assigned_employee'].empty_label = '— Non assigné —'
        self.fields['mission'].required = False
        self.fields['mission'].empty_label = '— Sans mission —'

        if company:
            from apps.crm.models import Customer
            self.fields['customer'].queryset = Customer.objects.filter(company=company, is_active=True)
            from apps.websites.models import Website
            self.fields['website'].queryset = Website.objects.filter(company=company)
            self.fields['assigned_employee'].queryset = EmployeeProfile.objects.filter(
                company=company, is_active=True
            ).select_related('user')
            self.fields['mission'].queryset = WorkMission.objects.filter(
                company=company, status='active'
            )


class DedicatedTimeBlockForm(forms.ModelForm):
    class Meta:
        model = DedicatedTimeBlock
        fields = ['employee', 'mission', 'task', 'date', 'hours', 'note', 'is_locked']
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select'}),
            'mission': forms.Select(attrs={'class': 'form-select'}),
            'task': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'hours': forms.NumberInput(attrs={'class': 'form-control', 'min': '0.5', 'max': '24', 'step': '0.5'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        if company:
            self.fields['employee'].queryset = EmployeeProfile.objects.filter(
                company=company, is_active=True
            ).select_related('user')
            self.fields['mission'].queryset = WorkMission.objects.filter(
                company=company, status='active'
            )
            self.fields['task'].queryset = WorkTask.objects.filter(
                mission__company=company
            ).select_related('mission')
        self.fields['mission'].required = False
        self.fields['task'].required = False

    def clean_hours(self):
        hours = self.cleaned_data.get('hours')
        if hours is not None and hours <= 0:
            raise forms.ValidationError('Le nombre d\'heures doit être positif.')
        if hours is not None and hours > 24:
            raise forms.ValidationError('Impossible de saisir plus de 24h par jour.')
        return hours
