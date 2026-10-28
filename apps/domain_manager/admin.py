from django.contrib import admin

from apps.domain_manager.models import CustomDomain


@admin.register(CustomDomain)
class CustomDomainAdmin(admin.ModelAdmin):
    list_display = [
        'domain', 'company', 'brand_key', 'target_type',
        'status', 'dns_is_valid', 'ssl_is_valid', 'is_primary',
    ]
    list_filter = [
        'status', 'target_type', 'brand_key',
        'dns_is_valid', 'ssl_is_valid', 'is_primary',
    ]
    search_fields = ['domain', 'company__name', 'brand_key']
    readonly_fields = [
        'verification_token', 'expected_txt_name', 'expected_txt_value',
        'expected_cname', 'expected_a_record', 'last_dns_check_at',
        'last_ssl_check_at', 'created_at', 'updated_at',
    ]
