"""
URLs publiques des sites web (visibles par les visiteurs)
"""
from django.urls import path
from . import public_views
from . import btp_public_views as btp

app_name = 'public_websites'

urlpatterns = [
    # ── Pages génériques ────────────────────────────────────────────
    path('<slug:site_slug>/', public_views.home, name='home'),
    path('<slug:site_slug>/page/<slug:page_slug>/', public_views.page, name='page'),
    path('<slug:site_slug>/blog/', public_views.blog_list, name='blog_list'),
    path('<slug:site_slug>/blog/<slug:post_slug>/', public_views.blog_detail, name='blog_detail'),
    path('<slug:site_slug>/contact/', public_views.contact, name='contact'),
    path('<slug:site_slug>/devis/', public_views.quote_request, name='quote_request'),

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
]
