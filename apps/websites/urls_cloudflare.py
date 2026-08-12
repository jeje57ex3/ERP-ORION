"""
apps/websites/urls_cloudflare.py — URLs du module de connexion Cloudflare Orion ERP
"""
from django.urls import path
from . import views_cloudflare as v

urlpatterns = [
    # ─── Dashboard & connexion ─────────────────────────────────────────────────
    path('',                        v.cloudflare_dashboard, name='cloudflare_dashboard'),
    path('connecter/',              v.cloudflare_connect,   name='cloudflare_connect'),

    # ─── Actions sur un compte ────────────────────────────────────────────────
    path('<int:pk>/modifier/',      v.cloudflare_edit,      name='cloudflare_edit'),
    path('<int:pk>/tester/',        v.cloudflare_test,      name='cloudflare_test'),
    path('<int:pk>/toggle/',        v.cloudflare_toggle,    name='cloudflare_toggle'),
    path('<int:pk>/supprimer/',     v.cloudflare_delete,    name='cloudflare_delete'),

    # ─── Synchronisation ──────────────────────────────────────────────────────
    path('sync-tunnels/',           v.cloudflare_sync_tunnels, name='cloudflare_sync_tunnels'),
    path('import-one/',             v.cloudflare_import_one,   name='cloudflare_import_one'),

    # ─── API JSON ─────────────────────────────────────────────────────────────
    path('api/tester-token/',       v.api_test_token,          name='cloudflare_api_test_token'),
    path('<int:pk>/api/zones/',     v.api_cloudflare_zones,    name='cloudflare_api_zones'),
]
