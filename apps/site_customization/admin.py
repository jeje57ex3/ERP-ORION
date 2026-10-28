from django.contrib import admin
from .models import SiteThemeSettings, SitePageCustomization, SitePageSection, SiteContentBlock

admin.site.register(SiteThemeSettings)
admin.site.register(SitePageCustomization)
admin.site.register(SitePageSection)
admin.site.register(SiteContentBlock)
