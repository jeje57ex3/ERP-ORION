from django.contrib import admin
from .models import (
    ServiceDomain, ServiceCategory, ConfiguratorQuestion, ConfiguratorQuestionOption,
    MaterialRequirement, LaborRule, TravelRule, PricingCoefficient, MarginRule,
    DiagnosticScenario, ConfiguratorSubmission, ConfiguratorSession, ConfiguratorSessionLot,
)


class ConfiguratorQuestionOptionInline(admin.TabularInline):
    model = ConfiguratorQuestionOption
    extra = 1


@admin.register(ConfiguratorQuestion)
class ConfiguratorQuestionAdmin(admin.ModelAdmin):
    list_display = ['identifier', 'service', 'question_type', 'order', 'is_required']
    list_filter = ['service__domain', 'service', 'question_type', 'is_required']
    search_fields = ['identifier', 'label']
    inlines = [ConfiguratorQuestionOptionInline]


class ConfiguratorQuestionInline(admin.TabularInline):
    model = ConfiguratorQuestion
    extra = 0
    fields = ['identifier', 'label', 'question_type', 'order', 'is_required']
    show_change_link = True


class MaterialRequirementInline(admin.TabularInline):
    model = MaterialRequirement
    extra = 0
    fields = ['price_item', 'quantity_source', 'fixed_quantity', 'quantity_answer', 'quantity_multiplier', 'order']


class DiagnosticScenarioInline(admin.StackedInline):
    model = DiagnosticScenario
    extra = 0
    can_delete = True


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'domain', 'intervention_type', 'requires_diagnostic', 'confidence_level', 'is_active', 'order']
    list_filter = ['domain', 'intervention_type', 'requires_diagnostic', 'confidence_level', 'is_active']
    search_fields = ['name', 'code']
    inlines = [ConfiguratorQuestionInline, MaterialRequirementInline, DiagnosticScenarioInline]


@admin.register(ServiceDomain)
class ServiceDomainAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'company', 'order', 'is_active']
    list_filter = ['company', 'is_active']
    search_fields = ['name', 'code']


@admin.register(LaborRule)
class LaborRuleAdmin(admin.ModelAdmin):
    list_display = ['label', 'rate_type', 'domain', 'hourly_rate', 'company', 'is_active']
    list_filter = ['company', 'rate_type', 'domain']


@admin.register(TravelRule)
class TravelRuleAdmin(admin.ModelAdmin):
    list_display = ['zone_label', 'zone_code', 'flat_fee', 'is_default', 'company', 'is_active']
    list_filter = ['company', 'is_active']


@admin.register(PricingCoefficient)
class PricingCoefficientAdmin(admin.ModelAdmin):
    list_display = ['label', 'coefficient_type', 'multiplier', 'domain', 'company', 'is_active']
    list_filter = ['company', 'coefficient_type', 'domain']


@admin.register(MarginRule)
class MarginRuleAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'scope_type', 'margin_percent', 'company', 'is_active']
    list_filter = ['company', 'scope_type']


@admin.register(ConfiguratorSubmission)
class ConfiguratorSubmissionAdmin(admin.ModelAdmin):
    list_display = [
        'request', 'domain', 'service', 'session', 'confidence_level', 'confidence_score', 'visit_necessity',
        'diagnostic_required', 'danger_detected', 'human_validation_required', 'human_validation_done',
        'recommended_price', 'created_at',
    ]
    list_filter = [
        'confidence_level', 'visit_necessity', 'diagnostic_required', 'danger_detected',
        'human_validation_required',
    ]
    readonly_fields = [f.name for f in ConfiguratorSubmission._meta.fields]
    search_fields = ['request__reference', 'request__client_email']


class ConfiguratorSessionLotInline(admin.TabularInline):
    model = ConfiguratorSessionLot
    extra = 0
    fields = ['label', 'domain', 'service', 'urgency', 'visit_necessity', 'confidence_score']
    readonly_fields = ['visit_necessity', 'confidence_score']


@admin.register(ConfiguratorSession)
class ConfiguratorSessionAdmin(admin.ModelAdmin):
    """Simulateur admin minimal (§45) : consulter l'état d'un parcours en
    cours (réponses, score, nécessité de visite, lots) sans passer par l'API."""
    list_display = [
        'session_key', 'company', 'domain', 'service', 'status',
        'visit_necessity', 'confidence_score', 'last_activity_at',
    ]
    list_filter = ['company', 'status', 'visit_necessity', 'domain']
    search_fields = ['session_key']
    readonly_fields = [f.name for f in ConfiguratorSession._meta.fields if f.name != 'is_active']
    inlines = [ConfiguratorSessionLotInline]
