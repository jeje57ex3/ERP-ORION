"""
apps/system_health/forms.py — Formulaires de la section Santé du système.
"""
from django import forms
from .models import (
    SystemError, ErrorComment, SystemIncident, IncidentTimeline,
    PostIncidentReport, RiskRegister, AlertThreshold, HealthPermission,
)


class SystemErrorForm(forms.ModelForm):
    class Meta:
        model = SystemError
        fields = [
            'severity', 'module', 'environment', 'error_type', 'app_version',
            'user_message', 'technical_message', 'api_route', 'http_method',
            'response_code', 'correlation_id',
        ]
        widgets = {
            'user_message':      forms.Textarea(attrs={'rows': 3}),
            'technical_message': forms.Textarea(attrs={'rows': 5}),
        }


class SystemErrorTriageForm(forms.ModelForm):
    """Formulaire de tri / mise à jour d'une erreur."""
    class Meta:
        model = SystemError
        fields = ['status', 'assigned_to', 'probable_cause', 'solution_applied', 'ignore_reason', 'incident']
        widgets = {
            'probable_cause':   forms.Textarea(attrs={'rows': 3}),
            'solution_applied': forms.Textarea(attrs={'rows': 3}),
            'ignore_reason':    forms.Textarea(attrs={'rows': 2}),
        }


class ErrorCommentForm(forms.ModelForm):
    class Meta:
        model = ErrorComment
        fields = ['content']
        widgets = {'content': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Ajouter un commentaire…'})}


class SystemIncidentForm(forms.ModelForm):
    class Meta:
        model = SystemIncident
        fields = [
            'title', 'severity', 'description', 'affected_services',
            'started_at', 'detected_at', 'root_cause', 'immediate_actions',
            'fix_applied', 'consequences', 'prevention_plan', 'assigned_to',
        ]
        widgets = {
            'description':       forms.Textarea(attrs={'rows': 4}),
            'root_cause':        forms.Textarea(attrs={'rows': 3}),
            'immediate_actions': forms.Textarea(attrs={'rows': 3}),
            'fix_applied':       forms.Textarea(attrs={'rows': 3}),
            'consequences':      forms.Textarea(attrs={'rows': 3}),
            'prevention_plan':   forms.Textarea(attrs={'rows': 3}),
            'affected_services': forms.Textarea(attrs={'rows': 2,
                                  'placeholder': '["ERP", "Site SIÈCLE"]'}),
            'started_at':        forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'detected_at':       forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }


class IncidentStatusForm(forms.ModelForm):
    class Meta:
        model = SystemIncident
        fields = ['status']


class IncidentTimelineForm(forms.ModelForm):
    class Meta:
        model = IncidentTimeline
        fields = ['event_type', 'description']
        widgets = {'description': forms.Textarea(attrs={'rows': 3})}


class PostIncidentReportForm(forms.ModelForm):
    class Meta:
        model = PostIncidentReport
        fields = ['what_happened', 'why_it_happened', 'why_not_detected_earlier',
                  'how_fixed', 'how_to_prevent']
        widgets = {f: forms.Textarea(attrs={'rows': 4}) for f in
                   ['what_happened', 'why_it_happened', 'why_not_detected_earlier',
                    'how_fixed', 'how_to_prevent']}


class RiskRegisterForm(forms.ModelForm):
    class Meta:
        model = RiskRegister
        fields = [
            'title', 'description', 'category', 'origin', 'affected_module', 'affected_data',
            'probability', 'probability_justification', 'impact', 'impact_justification',
            'detected_at', 'owner', 'existing_measures', 'corrective_actions', 'target_date',
            'status', 'residual_risk', 'last_review', 'linked_incident',
        ]
        widgets = {
            'description':               forms.Textarea(attrs={'rows': 4}),
            'affected_data':             forms.Textarea(attrs={'rows': 2}),
            'probability_justification': forms.Textarea(attrs={'rows': 2}),
            'impact_justification':      forms.Textarea(attrs={'rows': 2}),
            'existing_measures':         forms.Textarea(attrs={'rows': 3}),
            'corrective_actions':        forms.Textarea(attrs={'rows': 3}),
            'detected_at':               forms.DateInput(attrs={'type': 'date'}),
            'target_date':               forms.DateInput(attrs={'type': 'date'}),
            'last_review':               forms.DateInput(attrs={'type': 'date'}),
        }


class AlertThresholdForm(forms.ModelForm):
    class Meta:
        model = AlertThreshold
        fields = [
            'sensor_type', 'warning_threshold', 'critical_threshold', 'comparison',
            'enabled', 'silence_until', 'notification_emails', 'escalation_after_min',
        ]
        widgets = {
            'silence_until':       forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'notification_emails': forms.Textarea(attrs={'rows': 2,
                                    'placeholder': '["admin@example.com"]'}),
        }


class HealthPermissionForm(forms.ModelForm):
    class Meta:
        model = HealthPermission
        fields = [
            'can_view_health', 'can_view_errors', 'can_view_technical', 'can_view_security',
            'can_view_risks', 'can_manage_incidents', 'can_edit_thresholds', 'can_close_alerts',
            'can_export_reports', 'can_view_sensitive', 'can_administrate',
        ]
