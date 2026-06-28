from django.contrib import admin
from .models import Employee


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = [
        'full_name', 'email', 'job_title', 'department',
        'company', 'user', 'contract_type', 'is_active',
    ]
    list_filter = ['company', 'department', 'is_active', 'contract_type']
    search_fields = [
        'first_name', 'last_name', 'email',
        'employee_number', 'user__email', 'user__username',
    ]
    autocomplete_fields = ['user']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Identité', {'fields': ('first_name', 'last_name', 'email', 'phone', 'employee_number')}),
        ('Poste', {'fields': ('job_title', 'department', 'manager', 'company')}),
        ('Contrat', {'fields': ('contract_type', 'hire_date', 'end_date', 'gross_salary')}),
        ('Compte utilisateur', {'fields': ('user',)}),
        ('Statut', {'fields': ('is_active', 'created_at')}),
    )

