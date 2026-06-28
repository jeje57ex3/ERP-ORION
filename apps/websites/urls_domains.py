"""
apps/websites/urls_domains.py — URLs du module de gestion des domaines Orion ERP
"""
from django.urls import path
from . import views_domains as v

urlpatterns = [
    # ─── Dashboard domaines ───────────────────────────────────────────────────
    path('',                      v.domain_dashboard,       name='domain_dashboard'),
    path('nouveau/',              v.domain_create,           name='domain_create'),
    path('wizard/',               v.domain_wizard,           name='domain_wizard'),

    # ─── Détail + actions sur un domaine ─────────────────────────────────────
    path('<int:pk>/',             v.domain_detail,           name='domain_detail'),
    path('<int:pk>/verifier/',    v.domain_verify,           name='domain_verify'),
    path('<int:pk>/ssl/',         v.domain_request_ssl,      name='domain_request_ssl'),
    path('<int:pk>/ssl/actif/',   v.domain_mark_ssl_active,  name='domain_mark_ssl_active'),
    path('<int:pk>/principal/',   v.domain_set_primary,      name='domain_set_primary'),
    path('<int:pk>/desactiver/',  v.domain_disable,          name='domain_disable'),
    path('<int:pk>/supprimer/',   v.domain_delete,           name='domain_delete'),
    path('<int:pk>/dns/',         v.domain_dns_instructions, name='domain_dns_instructions'),
    path('<int:pk>/redirections/', v.domain_redirects,       name='domain_redirects'),

    # ─── API JSON ─────────────────────────────────────────────────────────────
    path('api/',                  v.api_domain_list,         name='domain_api_list'),
    path('<int:pk>/api/status/',  v.api_domain_status,       name='domain_api_status'),
    path('<int:pk>/api/verify/',  v.api_domain_verify,       name='domain_api_verify'),
]
