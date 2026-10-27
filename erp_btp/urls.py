"""
ERP BTP Starter — URL principale
"""
from django.contrib import admin

from apps.core.media_access import servir_media
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.views.generic import RedirectView
from django.conf.urls.i18n import set_language
from apps.private_saas.views import company_switcher
from apps.core.setup_views import setup_wizard


def home_redirect(request):
    website = getattr(request, 'website', None)
    if website is not None:
        slug = website.public_slug
        if website.site_type == 'btp':
            return redirect('public_websites:btp_home', site_slug=slug)
        if website.site_type == 'electricite':
            return redirect('public_websites:electricite_home', site_slug=slug)
        return redirect('public_websites:home', site_slug=slug)
    if request.user.is_authenticated:
        return redirect('core:dashboard')
    return redirect('accounts:login')


urlpatterns = [
    path('', home_redirect, name='home'),
    path('setup/', setup_wizard, name='setup'),
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
    path('configurateur/', include('apps.configurator.urls', namespace='configurator')),
    path('ecommerce/', include('apps.ecommerce.urls', namespace='ecommerce')),
    path('commerce/', include('apps.commerce.urls', namespace='commerce')),
    path('production/', include('apps.production.urls', namespace='production')),
    path('audio/', include('apps.audio.urls', namespace='audio')),
    path('websites/', include('apps.websites.urls', namespace='websites')),
    path('editeur-visuel/', include('apps.site_builder.urls', namespace='site_builder')),
    path('bi/', include('apps.bi.urls', namespace='bi')),
    path('sauvegardes/', include('apps.backups.urls', namespace='backups')),
    path('concurrents/', include('apps.competitor_intelligence.urls', namespace='competitor')),
    path('mon-dashboard/', include('apps.dashboard.urls', namespace='dashboard')),
    path('api/v1/', include('apps.api.urls', namespace='api')),
    path('api/v1/lunea/', include('apps.lunea.urls', namespace='lunea')),
    # API publique de l'editeur visuel. Les routes sont dans
    # apps/site_builder/public_urls.py et non dans
    # apps/ecommerce/public_urls.py, qui les cable aussi mais importe en
    # plus site_customization -- une autre application non enregistree.
    path('api/v1/public/', include('apps.site_builder.public_urls', namespace='public_builder')),
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
    # /assistant/ etait l'ancien module orion_assistant, remplace par orion_ai
    # (surensemble strict : memes conversations, plus les outils, la memoire et
    # l'audit). L'adresse est conservee en redirection : des liens et des
    # favoris la portent deja. Redirection TEMPORAIRE (302) et non permanente :
    # un 301 serait mis en cache par les navigateurs sans moyen de revenir.
    path(
        'assistant/',
        RedirectView.as_view(
            pattern_name='orion_ai:assistant_dashboard', permanent=False,
        ),
        name='assistant_redirection',
    ),
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
    # Interface telephone : pages concues pour le pouce, et prise de photo.
    path('', include('apps.mobile_web.urls', namespace='mobile_web')),

    # ── Amélioration continue PDCA ────────────────────────────────────────────
    path('', include('apps.continuous_improvement.urls', namespace='continuous_improvement')),

    # ── Dashboard Widgets API ─────────────────────────────────────────────────
    path('', include('apps.dashboard_widgets.urls', namespace='dashboard_widgets')),

    # ── Diagnostic Domaines & Cloudflare ──────────────────────────────────────
    path('diagnostic-domaines/', include('apps.domain_diagnostics.urls', namespace='domain_diagnostics')),

    # ── Santé du système ───────────────────────────────────────────────────────
    path('', include('apps.system_health.urls', namespace='system_health')),

    # Double authentification. A LA RACINE, et non sous un prefixe : ses
    # adresses sont absolues (« account/security/ », « auth/2fa/ ») et
    # correspondent exactement aux exemptions de
    # RequireTwoFactorMiddleware. Les monter ailleurs rendrait la page de
    # verification elle-meme soumise a la verification -- une boucle de
    # redirection dont on ne sort pas.
    path('', include('apps.user_security.urls', namespace='user_security')),

    # Sites web publics (doit être en dernier)
    path('sites/', include('apps.websites.public_urls', namespace='public_websites')),
]

# ── Fichiers media ───────────────────────────────────────────────────────────
#
# Servis par une vue qui applique une politique de refus par defaut, en
# production ET en developpement.
#
# Avant, `static(MEDIA_URL, ...)` etait derriere `if settings.DEBUG` : en
# production nginx relaie /media/ vers gunicorn, Django n'avait aucune route
# pour ce prefixe et WhiteNoise ne sert que STATIC_ROOT. AUCUN fichier
# televerse n'etait donc accessible sur l'appliance.
#
# La correction evidente -- servir MEDIA_ROOT en statique -- aurait publie
# employee_private/, c'est-a-dire les contrats et bulletins de paie que
# hr.private_document_download protege par un controle de role et un journal
# d'acces. Voir apps/core/media_access.py pour la politique.
#
# Monte aussi en developpement a dessein : filtrer seulement en production
# rendrait la politique invisible pendant qu'on la met au point.
urlpatterns += [
    re_path(r'^media/(?P<chemin>.+)$', servir_media, name='media'),
]

# Les fichiers statiques restent servis par WhiteNoise en production ; cette
# ligne ne sert qu'au developpement.
if settings.DEBUG:
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
