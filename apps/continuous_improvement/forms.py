from django import forms

from .models import PDCACycle, PDCAPlan, PDCADo, PDCACheck, PDCAAct, PDCAAction, PDCAKPI


class PDCACycleCreateForm(forms.ModelForm):
    class Meta:
        model = PDCACycle
        fields = [
            'title', 'problem_statement', 'objective',
            'category', 'priority', 'owner',
            'start_date', 'target_date',
            'root_cause', 'success_criteria', 'expected_result',
            'related_module', 'brand_key',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Titre du cycle PDCA'}),
            'problem_statement': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Décrivez le problème ou l\'amélioration souhaitée…'}),
            'objective': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'owner': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'target_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'root_cause': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'success_criteria': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'expected_result': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'related_module': forms.TextInput(attrs={'class': 'form-control'}),
            'brand_key': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: siecle, lunea'}),
        }


class PDCACycleEditForm(PDCACycleCreateForm):
    class Meta(PDCACycleCreateForm.Meta):
        fields = PDCACycleCreateForm.Meta.fields + ['status', 'actual_result', 'failure_reason']
        widgets = {
            **PDCACycleCreateForm.Meta.widgets,
            'status': forms.Select(attrs={'class': 'form-select'}),
            'actual_result': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'failure_reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class PDCAPlanForm(forms.ModelForm):
    class Meta:
        model = PDCAPlan
        fields = [
            'current_situation', 'analysis', 'root_causes', 'risks', 'assumptions',
            'planned_actions_summary',
            'baseline_metric_name', 'baseline_metric_value',
            'target_metric_name', 'target_metric_value',
        ]
        widgets = {f: forms.Textarea(attrs={'class': 'form-control', 'rows': 3}) for f in [
            'current_situation', 'analysis', 'root_causes', 'risks', 'assumptions', 'planned_actions_summary',
        ]}
        widgets.update({
            'baseline_metric_name': forms.TextInput(attrs={'class': 'form-control'}),
            'baseline_metric_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'target_metric_name': forms.TextInput(attrs={'class': 'form-control'}),
            'target_metric_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        })


class PDCADoForm(forms.ModelForm):
    class Meta:
        model = PDCADo
        fields = ['execution_summary', 'difficulties', 'deviations_from_plan']
        widgets = {f: forms.Textarea(attrs={'class': 'form-control', 'rows': 3}) for f in fields}


class PDCACheckForm(forms.ModelForm):
    class Meta:
        model = PDCACheck
        fields = [
            'result_status', 'measured_result', 'data_sources',
            'measured_metric_name', 'measured_metric_value',
            'gap_analysis', 'lessons_learned',
        ]
        widgets = {
            'result_status': forms.Select(attrs={'class': 'form-select'}),
            'measured_result': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'data_sources': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'measured_metric_name': forms.TextInput(attrs={'class': 'form-control'}),
            'measured_metric_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'gap_analysis': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'lessons_learned': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class PDCAActForm(forms.ModelForm):
    class Meta:
        model = PDCAAct
        fields = ['decision', 'decision_reason', 'standardization_notes', 'next_steps', 'create_new_cycle']
        widgets = {
            'decision': forms.Select(attrs={'class': 'form-select'}),
            'decision_reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'standardization_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'next_steps': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'create_new_cycle': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class PDCAActionForm(forms.ModelForm):
    class Meta:
        model = PDCAAction
        fields = ['title', 'description', 'assigned_to', 'due_date', 'order', 'status']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


class PDCAKPIForm(forms.ModelForm):
    class Meta:
        model = PDCAKPI
        fields = ['name', 'description', 'unit', 'before_value', 'target_value', 'after_value']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'unit': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'ex: %, EUR, pcs'}),
            'before_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'target_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'after_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
