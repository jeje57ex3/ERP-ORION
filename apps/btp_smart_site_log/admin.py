from django.contrib import admin
from .models import SiteLog, SiteLogIncident


class IncidentInline(admin.TabularInline):
    model = SiteLogIncident
    extra = 0
    readonly_fields = ['incident_type', 'severity', 'is_resolved', 'created_at']
    can_delete = False


@admin.register(SiteLog)
class SiteLogAdmin(admin.ModelAdmin):
    list_display = ['project_id', 'title', 'log_type', 'workers_count',
                    'weather', 'logged_by', 'logged_at', 'company']
    list_filter = ['log_type', 'weather', 'company']
    search_fields = ['project_id', 'project_name', 'title']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [IncidentInline]


@admin.register(SiteLogIncident)
class SiteLogIncidentAdmin(admin.ModelAdmin):
    list_display = ['incident_type', 'severity', 'is_resolved', 'site_log', 'company', 'created_at']
    list_filter = ['incident_type', 'severity', 'is_resolved', 'company']
    readonly_fields = ['created_at', 'resolved_at']
