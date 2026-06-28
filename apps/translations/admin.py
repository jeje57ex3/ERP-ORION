"""
apps/translations/admin.py
"""
from django.contrib import admin
from .models import (
    Language, CompanyLanguageSettings, UserLanguagePreference,
    WebsiteLanguageSettings, InterfaceTranslation,
)


@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display  = ['flag_icon', 'code', 'name', 'native_name', 'is_active', 'is_default', 'is_rtl', 'order']
    list_editable = ['is_active', 'is_default', 'order']
    list_filter   = ['is_active', 'is_default', 'is_rtl']
    search_fields = ['code', 'name', 'native_name']
    ordering      = ['order', 'name']


@admin.register(CompanyLanguageSettings)
class CompanyLanguageSettingsAdmin(admin.ModelAdmin):
    list_display  = ['company', 'default_language', 'allow_users_to_change_language', 'auto_detect_browser_language']
    list_filter   = ['default_language', 'allow_users_to_change_language']
    search_fields = ['company__name']
    filter_horizontal = ['enabled_languages']
    autocomplete_fields = ['company']


@admin.register(UserLanguagePreference)
class UserLanguagePreferenceAdmin(admin.ModelAdmin):
    list_display  = ['user', 'company', 'language', 'updated_at']
    list_filter   = ['language', 'company']
    search_fields = ['user__username', 'user__email']
    raw_id_fields = ['user']


@admin.register(WebsiteLanguageSettings)
class WebsiteLanguageSettingsAdmin(admin.ModelAdmin):
    list_display  = ['website', 'default_language', 'show_language_switcher', 'use_language_prefix_urls', 'auto_redirect_by_browser']
    list_filter   = ['default_language', 'show_language_switcher', 'use_language_prefix_urls']
    search_fields = ['website__name']
    filter_horizontal = ['enabled_languages']


@admin.register(InterfaceTranslation)
class InterfaceTranslationAdmin(admin.ModelAdmin):
    list_display  = ['key', 'language', 'module', 'company', 'is_verified', 'updated_at']
    list_filter   = ['language', 'module', 'is_verified', 'company']
    search_fields = ['key', 'source_text', 'translated_text']
    list_editable = ['is_verified']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        (None, {'fields': ('company', 'key', 'module', 'language', 'context')}),
        ('Contenu', {'fields': ('source_text', 'translated_text', 'is_verified')}),
        ('Dates', {'fields': ('created_at', 'updated_at'), 'classes': ['collapse']}),
    )
