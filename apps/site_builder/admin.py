from django.contrib import admin
from .models import BuilderPage, BuilderSection, BuilderAsset, BuilderPublishLog


class BuilderSectionInline(admin.TabularInline):
    model = BuilderSection
    extra = 0
    fields = ['module_type', 'position', 'is_visible']
    ordering = ['position']


@admin.register(BuilderPage)
class BuilderPageAdmin(admin.ModelAdmin):
    list_display = ['title', 'website', 'status', 'is_homepage', 'updated_at']
    list_filter = ['status', 'is_homepage', 'website']
    search_fields = ['title', 'slug']
    inlines = [BuilderSectionInline]


@admin.register(BuilderSection)
class BuilderSectionAdmin(admin.ModelAdmin):
    list_display = ['module_type', 'page', 'position', 'is_visible']
    list_filter = ['module_type']


@admin.register(BuilderAsset)
class BuilderAssetAdmin(admin.ModelAdmin):
    list_display = ['alt_text', 'file_type', 'company', 'created_at']


@admin.register(BuilderPublishLog)
class BuilderPublishLogAdmin(admin.ModelAdmin):
    list_display = ['page', 'published_by', 'published_at']
    readonly_fields = ['page', 'published_by', 'published_at', 'sections_snapshot']
