"""
URLs publiques des sites web (visibles par les visiteurs)
"""
from django.urls import path
from . import public_views
from . import btp_public_views as btp
from . import electricite_public_views as elec
from . import electricite_wizard_views as elec_wizard

app_name = 'public_websites'

urlpatterns = [
    # ── Newsletter / langue (génériques, tous sites) ───────────────────
    path('newsletter/', public_views.newsletter_subscribe, name='newsletter_subscribe'),
    path('set-language/', public_views.set_site_language, name='set_site_language'),

    # ── Pages génériques ────────────────────────────────────────────
    path('<slug:site_slug>/', public_views.home, name='home'),
    path('<slug:site_slug>/page/<slug:page_slug>/', public_views.page, name='page'),
    path('<slug:site_slug>/blog/', public_views.blog_list, name='blog_list'),
    path('<slug:site_slug>/blog/<slug:post_slug>/', public_views.blog_detail, name='blog_detail'),
    path('<slug:site_slug>/contact/', public_views.contact, name='contact'),
    path('<slug:site_slug>/devis/', public_views.quote_request, name='quote_request'),
    path('<slug:site_slug>/sitemap.xml', public_views.sitemap_public, name='sitemap_public'),
    path('<slug:site_slug>/robots.txt', public_views.robots_public, name='robots_public'),

    # ── Site BTP ─────────────────────────────────────────────────────
    path('<slug:site_slug>/btp/', btp.btp_home, name='btp_home'),
    path('<slug:site_slug>/btp/services/', btp.btp_services, name='btp_services'),
    path('<slug:site_slug>/btp/travaux/', btp.btp_works, name='btp_works'),
    path('<slug:site_slug>/btp/urgence/', btp.btp_emergency, name='btp_emergency'),
    path('<slug:site_slug>/btp/realisations/', btp.btp_portfolio, name='btp_portfolio'),
    path('<slug:site_slug>/btp/avis/', btp.btp_reviews, name='btp_reviews'),
    path('<slug:site_slug>/btp/contact/', btp.btp_contact, name='btp_contact'),
    path('<slug:site_slug>/btp/espace-client/', btp.btp_client_access, name='btp_client_access'),
    path('<slug:site_slug>/btp/blog/', btp.btp_blog, name='btp_blog'),
    path('<slug:site_slug>/btp/blog/<slug:post_slug>/', btp.btp_blog_detail, name='btp_blog_detail'),

    # ── Site Électricité ─────────────────────────────────────────────
    path('<slug:site_slug>/electricite/', elec.electricite_home, name='electricite_home'),
    path('<slug:site_slug>/electricite/a-propos/', elec.electricite_about, name='electricite_about'),
    path('<slug:site_slug>/electricite/services/', elec.electricite_services, name='electricite_services'),
    path('<slug:site_slug>/electricite/services/<slug:service_slug>/', elec.electricite_service_detail, name='electricite_service_detail'),
    path('<slug:site_slug>/electricite/realisations/', elec.electricite_portfolio, name='electricite_portfolio'),
    path('<slug:site_slug>/electricite/avis/', elec.electricite_reviews, name='electricite_reviews'),
    path('<slug:site_slug>/electricite/faq/', elec.electricite_faq, name='electricite_faq'),
    path('<slug:site_slug>/electricite/calculateur/', elec.electricite_calculateur, name='electricite_calculateur'),
    path('<slug:site_slug>/electricite/contact/', elec.electricite_contact, name='electricite_contact'),
    path('<slug:site_slug>/electricite/espace-client/', elec.electricite_client_access, name='electricite_client_access'),
    path('<slug:site_slug>/electricite/mentions-legales/', elec.electricite_mentions_legales, name='electricite_mentions_legales'),
    path('<slug:site_slug>/electricite/confidentialite/', elec.electricite_confidentialite, name='electricite_confidentialite'),

    # ── Configurateurs Électricité (chantier + dépannage) ─────────────
    path('<slug:site_slug>/electricite/devis/', elec_wizard.wizard_start, name='electricite_wizard_start'),
    path('<slug:site_slug>/electricite/devis/etape-2/', elec_wizard.wizard_step2, name='electricite_wizard_step2'),
    path('<slug:site_slug>/electricite/devis/etape-3/', elec_wizard.wizard_step3, name='electricite_wizard_step3'),
    path('<slug:site_slug>/electricite/devis/etape-4/', elec_wizard.wizard_step4, name='electricite_wizard_step4'),
    path('<slug:site_slug>/electricite/devis/confirmation/', elec_wizard.wizard_success, name='electricite_wizard_success'),
    path('<slug:site_slug>/electricite/devis/<int:pk>/photos/', elec_wizard.wizard_upload_photos, name='electricite_wizard_photos'),
    path('<slug:site_slug>/electricite/devis/<int:pk>/pdf/', elec_wizard.wizard_pdf, name='electricite_wizard_pdf'),
]
