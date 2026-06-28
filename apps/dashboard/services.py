"""
dashboard/services.py — Logique métier du dashboard personnalisable
"""
from .models import DashboardProfile, DashboardWidget, UserDashboardWidget, DashboardShortcut, DashboardUserPreference
from .permissions import widget_is_accessible


DEFAULT_WIDGETS_BY_CODE = [
    'favorite_shortcuts',
    'my_requests',
    'my_notifications',
    'my_validations',
]

DEFAULT_SHORTCUTS = [
    {'label': 'Nouveau devis', 'icon': 'bi-file-text', 'color': '#2563EB', 'url_name': 'sales:quote_create', 'target_type': 'create_action', 'module_code': 'sales'},
    {'label': 'Nouveau client', 'icon': 'bi-person-plus', 'color': '#0891B2', 'url_name': 'crm:customer_create', 'target_type': 'create_action', 'module_code': 'crm'},
    {'label': 'Mes messages', 'icon': 'bi-chat', 'color': '#C6A15B', 'url_name': 'support:ticket_list', 'target_type': 'object_list', 'module_code': 'support'},
    {'label': 'Mes documents', 'icon': 'bi-folder', 'color': '#6B7280', 'url_name': 'documents:index', 'target_type': 'module', 'module_code': 'documents'},
]


def get_or_create_default_dashboard(user, company):
    if company is None:
        return None
    profile, created = DashboardProfile.objects.get_or_create(
        user=user,
        company=company,
        is_default=True,
        defaults={'name': 'Mon tableau de bord'},
    )
    if created:
        _add_default_widgets(profile, user, company)
    return profile


def _add_default_widgets(profile, user, company):
    widgets = DashboardWidget.objects.filter(
        code__in=DEFAULT_WIDGETS_BY_CODE, is_active=True
    )
    positions = {
        'favorite_shortcuts': (0, 0, 12),
        'my_requests': (0, 1, 6),
        'my_notifications': (6, 1, 6),
        'my_validations': (0, 2, 12),
    }
    for w in widgets:
        if not widget_is_accessible(user, company, w):
            continue
        pos = positions.get(w.code, (0, 99, 6))
        UserDashboardWidget.objects.get_or_create(
            dashboard_profile=profile,
            widget=w,
            defaults={
                'position_x': pos[0],
                'position_y': pos[1],
                'width': pos[2],
                'is_visible': True,
            }
        )


def get_available_widgets(user, company):
    qs = DashboardWidget.objects.filter(is_active=True)
    return [w for w in qs if widget_is_accessible(user, company, w)]


def get_user_widgets(user, company, profile=None):
    if profile is None:
        profile = get_or_create_default_dashboard(user, company)
    return profile.user_widgets.select_related('widget').order_by('position_y', 'position_x')


def get_user_shortcuts(user, company):
    return DashboardShortcut.objects.filter(
        user=user, company=company, is_active=True
    ).order_by('order', 'label')


def get_user_preference(user, company):
    pref, _ = DashboardUserPreference.objects.get_or_create(
        user=user,
        company=company,
        defaults={},
    )
    return pref


def get_dashboard_context(user, company):
    from . import widgets as wdata
    profile = get_or_create_default_dashboard(user, company)
    user_widgets = get_user_widgets(user, company, profile)
    shortcuts = get_user_shortcuts(user, company)
    pref = get_user_preference(user, company)

    active_codes = {uw.widget.code for uw in user_widgets if uw.is_visible}

    LOADERS = {
        'favorite_shortcuts': wdata.get_favorite_shortcuts_data,
        'my_requests': wdata.get_my_requests_data,
        'my_tasks': wdata.get_my_tasks_data,
        'my_validations': wdata.get_my_validations_data,
        'my_notifications': wdata.get_my_notifications_data,
        'my_messages': wdata.get_my_messages_data,
        'recent_documents': wdata.get_recent_documents_data,
        'calendar_events': wdata.get_calendar_events_data,
        'btp_active_projects': wdata.get_btp_active_projects_data,
        'btp_my_projects': wdata.get_btp_my_projects_data,
        'btp_hours_to_validate': wdata.get_btp_hours_to_validate_data,
        'btp_open_reservations': wdata.get_btp_open_reservations_data,
        'btp_pending_change_requests': wdata.get_btp_pending_change_requests_data,
        'btp_guided_quote_requests': wdata.get_btp_guided_quote_requests_data,
        'crm_followups': wdata.get_crm_followups_data,
        'crm_open_opportunities': wdata.get_crm_opportunities_data,
        'sales_quotes_to_send': wdata.get_sales_quotes_to_send_data,
        'sales_quotes_waiting_response': wdata.get_sales_quotes_waiting_data,
        'sales_unpaid_invoices': wdata.get_sales_unpaid_invoices_data,
        'accounting_cash_balance': wdata.get_accounting_cash_balance_data,
        'accounting_overdue_customer_invoices': wdata.get_accounting_overdue_invoices_data,
        'accounting_supplier_invoices_due': wdata.get_accounting_supplier_due_data,
        'accounting_vat_summary': wdata.get_accounting_vat_data,
        'accounting_draft_entries': wdata.get_accounting_draft_entries_data,
        'hr_leave_requests_to_validate': wdata.get_hr_leave_requests_data,
        'hr_expenses_to_validate': wdata.get_hr_expenses_data,
        'hr_expiring_documents': wdata.get_hr_expiring_documents_data,
        'hr_my_private_documents': wdata.get_hr_my_private_documents_data,
        'ecommerce_orders_to_prepare': wdata.get_ecommerce_orders_data,
        'inventory_low_stock_products': wdata.get_inventory_low_stock_data,
        'ecommerce_returns_pending': wdata.get_ecommerce_returns_data,
        'commerce_daily_sales': wdata.get_commerce_daily_sales_data,
        'commerce_click_collect_pending': wdata.get_commerce_click_collect_data,
        # ── Phase 2 — Productivité personnelle ──────────────────────────────
        'quick_actions': wdata.get_quick_actions_data,
        'user_favorites': wdata.get_user_favorites_data,
        'today_todo': wdata.get_today_todo_data,
        'weekly_agenda': wdata.get_weekly_agenda_data,
        'personal_notes': wdata.get_personal_notes_data,
        # ── Alertes et priorités ─────────────────────────────────────────────
        'important_alerts': wdata.get_important_alerts_data,
        'upcoming_deadlines': wdata.get_upcoming_deadlines_data,
        'late_items': wdata.get_late_items_data,
        # ── BTP avancés ──────────────────────────────────────────────────────
        'btp_project_profitability': wdata.get_btp_project_profitability_data,
        'btp_risky_projects': wdata.get_btp_risky_projects_data,
        'btp_projects_progress': wdata.get_btp_projects_progress_data,
        'btp_client_requests': wdata.get_btp_client_requests_data,
        'btp_recent_site_photos': wdata.get_btp_recent_site_photos_data,
        'btp_equipment_status': wdata.get_btp_equipment_status_data,
        # ── CRM / Ventes avancés ─────────────────────────────────────────────
        'crm_sales_pipeline': wdata.get_crm_sales_pipeline_data,
        'crm_priority_followups': wdata.get_crm_priority_followups_data,
        'sales_quotes_expiring_soon': wdata.get_sales_quotes_expiring_soon_data,
        'crm_top_customers': wdata.get_crm_top_customers_data,
        # ── Comptabilité / Trésorerie avancés ────────────────────────────────
        'accounting_bank_balances': wdata.get_accounting_bank_balances_data,
        'accounting_cashflow_forecast': wdata.get_accounting_cashflow_forecast_data,
        'accounting_invoice_reminders': wdata.get_accounting_invoice_reminders_data,
        'accounting_expenses_to_reimburse': wdata.get_accounting_expenses_to_reimburse_data,
        'accounting_vat_to_declare': wdata.get_accounting_vat_to_declare_data,
        # ── Documents avancés ────────────────────────────────────────────────
        'documents_to_sign': wdata.get_documents_to_sign_data,
        'documents_expiring_soon': wdata.get_documents_expiring_soon_data,
        'documents_recently_shared': wdata.get_documents_recently_shared_data,
        # ── RH avancés ───────────────────────────────────────────────────────
        'hr_today_absences': wdata.get_hr_today_absences_data,
        'hr_important_dates': wdata.get_hr_important_dates_data,
        'hr_my_hours': wdata.get_hr_my_hours_data,
        # ── Support et portail ───────────────────────────────────────────────
        'support_urgent_tickets': wdata.get_support_urgent_tickets_data,
        'client_unread_messages': wdata.get_client_unread_messages_data,
        'client_portal_activity': wdata.get_client_portal_activity_data,
        # ── Sites web ────────────────────────────────────────────────────────
        'website_leads': wdata.get_website_leads_data,
        'website_pages_to_publish': wdata.get_website_pages_to_publish_data,
        'website_basic_stats': wdata.get_website_basic_stats_data,
        # ── E-commerce et commerce ───────────────────────────────────────────
        'ecommerce_urgent_orders': wdata.get_ecommerce_urgent_orders_data,
        'ecommerce_abandoned_carts': wdata.get_ecommerce_abandoned_carts_data,
        'inventory_products_to_reorder': wdata.get_inventory_products_to_reorder_data,
        'commerce_omnichannel_sales': wdata.get_commerce_omnichannel_sales_data,
        # ── Intelligence Orion ───────────────────────────────────────────────
        'orion_suggestions': wdata.get_orion_suggestions_data,
        'daily_summary': wdata.get_daily_summary_data,
        'personal_goals': wdata.get_personal_goals_data,
        # ── LUNEA ────────────────────────────────────────────────────────────
        'lunea_new_orders': wdata.get_lunea_new_orders_data,
        'lunea_orders_to_prepare': wdata.get_lunea_orders_to_prepare_data,
        'lunea_low_shade_stock': wdata.get_lunea_low_shade_stock_data,
        'lunea_best_sellers': wdata.get_lunea_best_sellers_data,
        'lunea_pending_reviews': wdata.get_lunea_pending_reviews_data,
        'lunea_revenue_today': wdata.get_lunea_revenue_today_data,
        'lunea_shade_alerts': wdata.get_lunea_shade_alerts_data,
        'lunea_gift_cards_active': wdata.get_lunea_gift_cards_active_data,
        'lunea_loyalty_points_issued': wdata.get_lunea_loyalty_points_issued_data,
        'lunea_newsletter_subscribers': wdata.get_lunea_newsletter_subscribers_data,
        'lunea_subscription_renewals': wdata.get_lunea_subscription_renewals_data,
        'lunea_abandoned_carts': wdata.get_lunea_abandoned_carts_data,
        'lunea_conversion_rate': wdata.get_lunea_conversion_rate_data,
        'lunea_beauty_quiz_completions': wdata.get_lunea_beauty_quiz_completions_data,
        'lunea_samples_sent': wdata.get_lunea_samples_sent_data,
        # ── Backups ──────────────────────────────────────────────────────────
        'backups_last_status': wdata.get_backups_last_status_data,
        'backups_pending': wdata.get_backups_pending_data,
        'backups_failed': wdata.get_backups_failed_data,
        'backups_size_used': wdata.get_backups_size_used_data,
        'backups_scheduled': wdata.get_backups_scheduled_data,
        'backups_recent_restores': wdata.get_backups_recent_restores_data,
        # ── Competitor Intelligence ───────────────────────────────────────────
        'competitor_price_alerts': wdata.get_competitor_price_alerts_data,
        'competitor_new_products': wdata.get_competitor_new_products_data,
        'competitor_social_mentions': wdata.get_competitor_social_mentions_data,
        'competitor_ranking_changes': wdata.get_competitor_ranking_changes_data,
        'competitor_promo_alerts': wdata.get_competitor_promo_alerts_data,
        'competitor_reviews_summary': wdata.get_competitor_reviews_summary_data,
        'competitor_traffic_trends': wdata.get_competitor_traffic_trends_data,
        'competitor_ad_intelligence': wdata.get_competitor_ad_intelligence_data,
        'competitor_news': wdata.get_competitor_news_data,
        # ── Cloudflare ───────────────────────────────────────────────────────
        'cloudflare_zones_status': wdata.get_cloudflare_zones_status_data,
        'cloudflare_firewall_events': wdata.get_cloudflare_firewall_events_data,
        'cloudflare_traffic_stats': wdata.get_cloudflare_traffic_stats_data,
        'cloudflare_ssl_status': wdata.get_cloudflare_ssl_status_data,
        'cloudflare_page_rules': wdata.get_cloudflare_page_rules_data,
        'cloudflare_analytics': wdata.get_cloudflare_analytics_data,
        # ── Domains ──────────────────────────────────────────────────────────
        'domains_expiring': wdata.get_domains_expiring_data,
        'domains_dns_health': wdata.get_domains_dns_health_data,
        'domains_whois_summary': wdata.get_domains_whois_summary_data,
        'domains_ssl_expiry': wdata.get_domains_ssl_expiry_data,
        'domains_redirect_status': wdata.get_domains_redirect_status_data,
        # ── Private SaaS ─────────────────────────────────────────────────────
        'private_saas_services_status': wdata.get_private_saas_services_status_data,
        'private_saas_users_count': wdata.get_private_saas_users_count_data,
        'private_saas_storage_usage': wdata.get_private_saas_storage_usage_data,
        'private_saas_pending_updates': wdata.get_private_saas_pending_updates_data,
        'private_saas_incidents': wdata.get_private_saas_incidents_data,
        'private_saas_backups': wdata.get_private_saas_backups_data,
        # ── Loyalty ──────────────────────────────────────────────────────────
        'loyalty_points_issued': wdata.get_loyalty_points_issued_data,
        'loyalty_members_active': wdata.get_loyalty_members_active_data,
        'loyalty_redemptions': wdata.get_loyalty_redemptions_data,
        'loyalty_tier_distribution': wdata.get_loyalty_tier_distribution_data,
        'loyalty_expiring_points': wdata.get_loyalty_expiring_points_data,
        # ── Gift Cards ────────────────────────────────────────────────────────
        'gift_cards_issued': wdata.get_gift_cards_issued_data,
        'gift_cards_active': wdata.get_gift_cards_active_data,
        'gift_cards_redeemed': wdata.get_gift_cards_redeemed_data,
        'gift_cards_expiring': wdata.get_gift_cards_expiring_data,
    }

    widget_data = {}
    for code in active_codes:
        loader = LOADERS.get(code)
        if loader:
            try:
                widget_data[code] = loader(user, company)
            except Exception:
                widget_data[code] = {}

    return {
        'dashboard_profile': profile,
        'user_widgets': user_widgets,
        'user_shortcuts': shortcuts,
        'dashboard_pref': pref,
        'widget_data': widget_data,
        'available_widgets': get_available_widgets(user, company),
    }


def reset_user_dashboard(user, company):
    profile = get_or_create_default_dashboard(user, company)
    profile.user_widgets.all().delete()
    _add_default_widgets(profile, user, company)
    return profile


def create_default_shortcuts(user, company):
    for i, sc_data in enumerate(DEFAULT_SHORTCUTS):
        DashboardShortcut.objects.get_or_create(
            user=user,
            company=company,
            label=sc_data['label'],
            defaults={
                'icon': sc_data['icon'],
                'color': sc_data['color'],
                'url_name': sc_data['url_name'],
                'target_type': sc_data['target_type'],
                'module_code': sc_data.get('module_code', ''),
                'order': i,
                'is_favorite': True,
                'is_active': True,
            }
        )


def user_can_add_widget(user, company, widget):
    return widget_is_accessible(user, company, widget)
