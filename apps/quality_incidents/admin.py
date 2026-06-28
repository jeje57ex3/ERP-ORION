from django.contrib import admin
from .models import QualityIncident, QualityIncidentComment


class CommentInline(admin.TabularInline):
    model = QualityIncidentComment
    extra = 0
    readonly_fields = ['user', 'content', 'created_at']
    can_delete = False


@admin.register(QualityIncident)
class QualityIncidentAdmin(admin.ModelAdmin):
    list_display = ['title', 'incident_type', 'severity', 'status', 'brand_key', 'customer', 'assigned_to', 'due_at', 'company']
    list_filter = ['incident_type', 'severity', 'status', 'company', 'brand_key']
    search_fields = ['title', 'description', 'customer__name']
    readonly_fields = ['created_at', 'updated_at', 'resolved_at']
    inlines = [CommentInline]
