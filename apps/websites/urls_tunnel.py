"""
apps/websites/urls_tunnel.py — URLs du module tunnels Cloudflare Orion ERP
"""
from django.urls import path
from . import views_tunnel as v

urlpatterns = [
    # ─── Liste / création / import ───────────────────────────────────────────
    path('',                                                v.tunnel_list,            name='tunnel_list'),
    path('nouveau/',                                        v.tunnel_create,          name='tunnel_create'),
    path('importer/',                                       v.tunnel_import,          name='tunnel_import'),

    # ─── Détail / édition / suppression ─────────────────────────────────────
    path('<int:pk>/',                                       v.tunnel_detail,          name='tunnel_detail'),
    path('<int:pk>/modifier/',                              v.tunnel_edit,            name='tunnel_edit'),
    path('<int:pk>/supprimer/',                             v.tunnel_delete,          name='tunnel_delete'),

    # ─── Config.yml ───────────────────────────────────────────────────────────
    path('<int:pk>/config/ecrire/',                         v.tunnel_write_config,    name='tunnel_write_config'),
    path('<int:pk>/config/telecharger/',                    v.tunnel_download_config, name='tunnel_download_config'),

    # ─── Règles d'ingress ─────────────────────────────────────────────────────
    path('<int:tunnel_pk>/regles/nouvelle/',                v.ingress_create,         name='ingress_create'),
    path('<int:tunnel_pk>/regles/<int:rule_pk>/modifier/',  v.ingress_edit,           name='ingress_edit'),
    path('<int:tunnel_pk>/regles/<int:rule_pk>/supprimer/', v.ingress_delete,         name='ingress_delete'),
    path('<int:tunnel_pk>/regles/<int:rule_pk>/port/',      v.ingress_update_port,    name='ingress_update_port'),
    path('<int:tunnel_pk>/regles/<int:rule_pk>/dns/',       v.ingress_sync_dns,       name='ingress_sync_dns'),

    # ─── API JSON ─────────────────────────────────────────────────────────────
    path('api/status/',                                     v.api_tunnel_status,       name='tunnel_api_status'),
    path('api/cf-tunnels/',                                 v.api_fetch_cf_tunnels,    name='tunnel_api_cf_tunnels'),
    path('api/preview-config/',                             v.api_preview_config_yml,  name='tunnel_api_preview_config'),
]
