from apps.dashboard_widgets.registry import register_dashboard_widget


@register_dashboard_widget(
    code="orion_ai_status",
    title="Assistant Orion IA",
    description="État de l'assistant IA, conversations actives et actions proposées.",
    module="orion_ai",
    icon="bi-stars",
    order=10,
)
def orion_ai_status_widget(*, user, company=None, brand_key="", **kwargs):
    try:
        from apps.orion_ai.models import OrionAIConversation, OrionAIProposedAction, OrionAISettings
        settings_obj = OrionAISettings.get_for_company(company) if company else OrionAISettings.get_global()
        conversations_count = OrionAIConversation.objects.filter(
            company=company, user=user, status="active"
        ).count()
        pending_actions_count = OrionAIProposedAction.objects.filter(
            conversation__company=company, status="pending"
        ).count()
        return {
            "status": "enabled" if settings_obj.ai_enabled else "disabled",
            "label": "IA active" if settings_obj.ai_enabled else "IA désactivée",
            "conversations_count": conversations_count,
            "pending_actions_count": pending_actions_count,
            "url": "/erp/assistant/",
        }
    except Exception as exc:
        return {
            "status": "error",
            "label": "IA non configurée",
            "error": str(exc),
            "url": "/erp/assistant/",
        }


@register_dashboard_widget(
    code="system_health_summary",
    title="Santé système",
    description="Dernier diagnostic santé Orion et problèmes ouverts.",
    module="system_observability",
    icon="bi-heart-pulse",
    order=20,
    permission="private_saas.view_dashboard",
)
def system_health_summary_widget(*, user, company=None, brand_key="", **kwargs):
    try:
        from apps.system_observability.models import ObservabilityCheck
        latest = ObservabilityCheck.objects.order_by('-created_at').first()
        open_issues = ObservabilityCheck.objects.filter(status="error").count()
        return {
            "status": latest.status if latest else "not_scanned",
            "label": latest.check_type if latest else "Aucun diagnostic lancé",
            "open_issues": open_issues,
            "url": "/systeme/",
        }
    except Exception as exc:
        return {
            "status": "error",
            "label": "Santé système indisponible",
            "error": str(exc),
            "url": "/systeme/",
        }


@register_dashboard_widget(
    code="system_updates_status",
    title="Mises à jour Orion",
    description="Version, disponibilité des mises à jour et dernier statut.",
    module="system_updates",
    icon="bi-cloud-download",
    order=30,
    permission="private_saas.view_dashboard",
)
def system_updates_status_widget(*, user, company=None, brand_key="", **kwargs):
    try:
        from apps.system_updates.models import SystemUpdateCheck, SystemUpdateRun
        latest_check = SystemUpdateCheck.objects.order_by('-checked_at').first()
        latest_run = SystemUpdateRun.objects.order_by('-started_at').first()
        return {
            "status": latest_check.status if latest_check else "not_checked",
            "label": latest_check.get_status_display() if latest_check else "Non vérifié",
            "commits_behind": getattr(latest_check, 'commits_behind', 0),
            "latest_run_status": latest_run.status if latest_run else "",
            "url": "/orion-admin/system-updates/",
        }
    except Exception as exc:
        return {
            "status": "error",
            "label": "Mises à jour indisponibles",
            "error": str(exc),
            "url": "/orion-admin/system-updates/",
        }


@register_dashboard_widget(
    code="high_availability_status",
    title="Haute disponibilité",
    description="État du serveur principal et des nœuds secondaires.",
    module="high_availability",
    icon="bi-server",
    order=40,
    permission="private_saas.view_dashboard",
)
def high_availability_status_widget(*, user, company=None, brand_key="", **kwargs):
    try:
        from apps.high_availability.models import OrionHANode
        nodes = OrionHANode.objects.all()
        healthy_nodes = nodes.filter(status="healthy").count()
        primary = nodes.filter(role="primary").first()
        return {
            "status": "healthy" if primary and primary.status == "healthy" else "warning",
            "label": "Cluster opérationnel" if healthy_nodes >= 2 else "Cluster à vérifier",
            "nodes_count": nodes.count(),
            "healthy_nodes": healthy_nodes,
            "primary_node": primary.name if primary else "",
            "url": "/orion-admin/ha/settings/",
        }
    except Exception as exc:
        return {
            "status": "error",
            "label": "HA non configurée",
            "error": str(exc),
            "url": "/orion-admin/ha/settings/",
        }


@register_dashboard_widget(
    code="pdca_summary",
    title="Amélioration continue",
    description="Cycles PDCA actifs, en retard et terminés.",
    module="continuous_improvement",
    icon="bi-arrow-repeat",
    order=50,
)
def pdca_summary_widget(*, user, company=None, brand_key="", **kwargs):
    try:
        from apps.continuous_improvement.models import PDCACycle
        qs = PDCACycle.objects.filter(company=company) if company else PDCACycle.objects.all()
        active = qs.exclude(stage="closed").count()
        completed = qs.filter(status="completed").count()
        critical = qs.filter(priority="critical").exclude(stage="closed").count()
        return {
            "status": "active" if active else "empty",
            "label": f"{active} cycle(s) actif(s)",
            "active_cycles": active,
            "completed_cycles": completed,
            "critical_cycles": critical,
            "url": "/erp/pdca/",
        }
    except Exception as exc:
        return {
            "status": "error",
            "label": "PDCA indisponible",
            "error": str(exc),
            "url": "/erp/pdca/",
        }


@register_dashboard_widget(
    code="shop_settings_summary",
    title="Paramètres boutique",
    description="État Stripe, checkout, livraison et pages légales.",
    module="website_shop_settings",
    icon="bi-shop",
    order=60,
)
def shop_settings_summary_widget(*, user, company=None, brand_key="", **kwargs):
    try:
        from apps.website_shop_settings.models import WebsiteShopSettings
        qs = WebsiteShopSettings.objects.filter(company=company)
        if brand_key:
            qs = qs.filter(brand_key=brand_key)
        shops_count = qs.count()
        shops = []
        for shop in qs[:5]:
            shops.append({
                "brand_key": shop.brand_key,
                "site_name": shop.site_name,
                "shop_enabled": shop.is_shop_enabled,
            })
        return {
            "status": "active" if shops_count else "empty",
            "label": f"{shops_count} boutique(s) configurée(s)",
            "shops": shops,
            "url": "/erp/websites/shop-settings/",
        }
    except Exception as exc:
        return {
            "status": "error",
            "label": "Paramètres boutique indisponibles",
            "error": str(exc),
            "url": "/erp/websites/shop-settings/",
        }


@register_dashboard_widget(
    code="siecle_creation_summary",
    title="SIÈCLE Créations",
    description="Créations, éditions limitées, commandes en attente.",
    module="siecle_creations",
    icon="bi-gem",
    order=70,
    brand_key="siecle",
)
def siecle_creation_summary_widget(*, user, company=None, brand_key="", **kwargs):
    try:
        from apps.siecle_creations.models import Creation, CreationOrder
        creations_qs = Creation.objects.filter(company=company)
        total = creations_qs.count()
        published = creations_qs.filter(status="published").count()
        sold_out = creations_qs.filter(status="sold_out").count()
        pending_orders = CreationOrder.objects.filter(company=company, status="pending").count()
        return {
            "status": "active" if total else "empty",
            "label": f"{published} création(s) publiée(s)",
            "total_creations": total,
            "published": published,
            "sold_out": sold_out,
            "pending_orders": pending_orders,
            "url": "/creations/",
        }
    except Exception as exc:
        return {
            "status": "error",
            "label": "Module SIÈCLE indisponible",
            "error": str(exc),
            "url": "/creations/",
        }


@register_dashboard_widget(
    code="lunea_beauty_profiles_summary",
    title="Profils beauté LUNEA",
    description="Profils peau, recommandations appliquées et en attente.",
    module="lunea_beauty_profile",
    icon="bi-person-heart",
    order=80,
    brand_key="lunea",
)
def lunea_beauty_profiles_summary_widget(*, user, company=None, brand_key="", **kwargs):
    try:
        from apps.lunea_beauty_profile.models import BeautyProfile, BeautyRecommendation
        profiles_count = BeautyProfile.objects.filter(company=company).count()
        total_recs = BeautyRecommendation.objects.filter(company=company).count()
        pending_recs = BeautyRecommendation.objects.filter(company=company, is_applied=False).count()
        return {
            "status": "active" if profiles_count else "empty",
            "label": f"{profiles_count} profil(s) beauté",
            "profiles_count": profiles_count,
            "total_recommendations": total_recs,
            "pending_recommendations": pending_recs,
            "url": "/beaute/",
        }
    except Exception as exc:
        return {
            "status": "error",
            "label": "Module Profils beauté indisponible",
            "error": str(exc),
            "url": "/beaute/",
        }
