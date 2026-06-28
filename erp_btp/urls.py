"""
ERP BTP Starter — URL principale
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.conf.urls.i18n import set_language
from apps.private_saas.views import company_switcher


def home_redirect(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    return redirect('accounts:login')


urlpatterns = [
    path('', home_redirect, name='home'),
    path('admin/', admin.site.urls),
    path('orion-admin/', include('apps.private_saas.urls', namespace='private_saas')),
    path('switch-company/', company_switcher, name='switch_company'),
    path('i18n/', include('django.conf.urls.i18n')),

    # ERP Apps
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    path('dashboard/', include('apps.core.urls', namespace='core')),
    path('acces/', include('apps.access_control.urls', namespace='access_control')),
    path('crm/', include('apps.crm.urls', namespace='crm')),
    path('sales/', include('apps.sales.urls', namespace='sales')),
    path('accounting/', include('apps.accounting.urls', namespace='accounting')),
    path('purchases/', include('apps.purchases.urls', namespace='purchases')),
    path('inventory/', include('apps.inventory.urls', namespace='inventory')),
    path('documents/', include('apps.documents.urls', namespace='documents')),
    path('hr/', include('apps.hr.urls', namespace='hr')),
    path('paie/', include('apps.payroll.urls', namespace='payroll')),
    path('support/', include('apps.support.urls', namespace='support')),
    path('btp/', include('apps.btp.urls', namespace='btp')),
    path('ecommerce/', include('apps.ecommerce.urls', namespace='ecommerce')),
    path('commerce/', include('apps.commerce.urls', namespace='commerce')),
    path('production/', include('apps.production.urls', namespace='production')),
    path('audio/', include('apps.audio.urls', namespace='audio')),
    path('websites/', include('apps.websites.urls', namespace='websites')),
    path('bi/', include('apps.bi.urls', namespace='bi')),
    path('sauvegardes/', include('apps.backups.urls', namespace='backups')),
    path('concurrents/', include('apps.competitor_intelligence.urls', namespace='competitor')),
    path('mon-dashboard/', include('apps.dashboard.urls', namespace='dashboard')),
    path('api/v1/', include('apps.api.urls', namespace='api')),
    path('api/v1/lunea/', include('apps.lunea.urls', namespace='lunea')),
    path('api/v1/auth/customer/', include('apps.ecommerce.auth_urls', namespace='ecommerce_auth')),
    path('api/v1/siecle/', include('apps.ecommerce.brand_urls', namespace='ecommerce_siecle')),
    path('api/v1/lunea/store/', include('apps.ecommerce.brand_urls', namespace='ecommerce_lunea')),
    path('notifications/', include('apps.notifications.urls', namespace='notifications')),

    # Boutique en ligne publique
    path('boutique/', include('apps.ecommerce.store_urls', namespace='store')),

    # Devis guidé public (vitrine électricité)
    path('devis-guide/', include('apps.btp.guided_quote_urls', namespace='guided_quote')),

    # Portail client — gestion admin ERP
    path('portails/', include('apps.portals.urls', namespace='portals')),

    # Espace client chantier
    path('client/', include('apps.portals.client_urls', namespace='client_portal')),

    # ── Phase 1 — Modules innovants ───────────────────────────────────────────
    path('alertes/', include('apps.smart_alerts.urls', namespace='smart_alerts')),
    path('automatisations/', include('apps.smart_automations.urls', namespace='smart_automations')),
    path('audit/', include('apps.audit_compliance.urls', namespace='audit_compliance')),
    path('clients/360/', include('apps.customer_360.urls', namespace='customer_360')),

    # ── Phase 2 — Opérations & Documents ─────────────────────────────────────
    path('workflows/', include('apps.workflow_center.urls', namespace='workflow_center')),
    path('docs/', include('apps.smart_documents.urls', namespace='smart_documents')),
    path('planning/', include('apps.smart_planning.urls', namespace='smart_planning')),
    path('qualite/', include('apps.quality_incidents.urls', namespace='quality_incidents')),

    # ── Phase 3 — Intelligence & API ─────────────────────────────────────────
    path('assistant/', include('apps.orion_assistant.urls', namespace='orion_assistant')),
    path('analytique/', include('apps.predictive_analytics.urls', namespace='predictive_analytics')),
    path('webhooks/', include('apps.api_webhooks.urls', namespace='api_webhooks')),
    path('integrations/', include('apps.integration_center.urls', namespace='integration_center')),

    # ── Phase 4 — Système & Infrastructure ───────────────────────────────────
    path('backups/', include('apps.backup_center.urls', namespace='backup_center')),
    path('systeme/', include('apps.system_observability.urls', namespace='system_observability')),

    # ── Phase 5 — Modules Métier Spécialisés ─────────────────────────────────
    path('creations/', include('apps.siecle_creations.urls', namespace='siecle_creations')),
    path('beaute/', include('apps.lunea_beauty_profile.urls', namespace='lunea_beauty_profile')),
    path('chantier/', include('apps.btp_smart_site_log.urls', namespace='btp_smart_site_log')),

    # ── Launch — Waitlist & Contact (no prefix — routes match /api/v1/...) ───
    path('', include('apps.launch.urls', namespace='launch')),

    # ── Infrastructure — Haute disponibilité ─────────────────────────────────
    path('', include('apps.high_availability.urls', namespace='high_availability')),

    # ── Système — Mises à jour ────────────────────────────────────────────────
    path('', include('apps.system_updates.urls', namespace='system_updates')),

    # ── Sites web — Paramètres boutique ──────────────────────────────────────
    path('', include('apps.website_shop_settings.urls', namespace='website_shop_settings')),

    # ── Intelligence Artificielle ─────────────────────────────────────────────
    path('', include('apps.orion_ai.urls', namespace='orion_ai')),

    # ── Amélioration continue PDCA ────────────────────────────────────────────
    path('', include('apps.continuous_improvement.urls', namespace='continuous_improvement')),

    # ── Dashboard Widgets API ─────────────────────────────────────────────────
    path('', include('apps.dashboard_widgets.urls', namespace='dashboard_widgets')),

    # Sites web publics (doit être en dernier)
    path('sites/', include('apps.websites.public_urls', namespace='public_websites')),
]

# Fichiers media en développement
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# ─── Handlers d'erreurs ──────────────────────────────────────────────────────
handler400 = 'django.views.defaults.bad_request'
handler403 = 'django.views.defaults.permission_denied'
handler404 = 'django.views.defaults.page_not_found'
handler500 = 'django.views.defaults.server_error'

# Configuration Admin
admin.site.site_header = 'Orion ERP — Administration'
admin.site.site_title = 'Orion ERP Admin'
admin.site.index_title = 'Tableau de bord administrateur'
