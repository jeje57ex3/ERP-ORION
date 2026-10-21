from django.contrib import admin
from .models import Employee, EmployeeSkill, EmployeeCertification


class EmployeeSkillInline(admin.TabularInline):
    model = EmployeeSkill
    extra = 0


class EmployeeCertificationInline(admin.TabularInline):
    model = EmployeeCertification
    extra = 0
    fields = ['category', 'name', 'reference', 'issued_date', 'expiry_date', 'issuing_body', 'is_active']


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
    inlines = [EmployeeSkillInline, EmployeeCertificationInline]
    fieldsets = (
        ('Identité', {'fields': ('first_name', 'last_name', 'email', 'phone', 'employee_number')}),
        ('Poste', {'fields': ('job_title', 'department', 'manager', 'company')}),
        ('Contrat', {'fields': ('contract_type', 'hire_date', 'end_date', 'gross_salary')}),
        ('Compte utilisateur', {'fields': ('user',)}),
        ('Statut', {'fields': ('is_active', 'created_at')}),
    )


@admin.register(EmployeeSkill)
class EmployeeSkillAdmin(admin.ModelAdmin):
    list_display = ['name', 'employee', 'level']
    list_filter = ['level']
    search_fields = ['name', 'employee__first_name', 'employee__last_name']


@admin.register(EmployeeCertification)
class EmployeeCertificationAdmin(admin.ModelAdmin):
    list_display = ['name', 'employee', 'category', 'expiry_date', 'is_active']
    list_filter = ['category', 'is_active']
    search_fields = ['name', 'reference', 'employee__first_name', 'employee__last_name']
