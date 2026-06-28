"""
Context processors — données injectées dans tous les templates ERP
"""
from .models import Company


def erp_context(request):
    """Contexte global ERP : entreprise courante, notifications, user."""
    ctx = {
        'current_company': None,
        'companies': [],
        'unread_notifications': [],
        'unread_count': 0,
    }

    if not request.user.is_authenticated:
        return ctx

    ctx['current_company'] = getattr(request, 'current_company', None)

    try:
        if request.user.is_superuser:
            ctx['companies'] = Company.objects.filter(is_active=True).order_by('name')
        else:
            ctx['companies'] = request.user.profile.companies.filter(is_active=True).order_by('name')
    except Exception:
        pass

    try:
        from apps.notifications.models import Notification
        company = ctx['current_company']
        qs = Notification.objects.filter(user=request.user, is_read=False)
        if company:
            qs = qs.filter(company=company)
        notifications = qs.order_by('-created_at')[:10]
        ctx['unread_notifications'] = list(notifications)
        ctx['unread_count'] = len(ctx['unread_notifications'])
    except Exception:
        pass

    return ctx


# Navigation ERP par module
NAV_MODULES = [
    {
        'id': 'dashboard',
        'label': 'Mon dashboard',
        'icon': 'bi-grid-3x3-gap',
        'url_name': 'dashboard:home',
        'color': '#C6A15B',
    },
    {
        'id': 'erp_overview',
        'label': 'Vue générale',
        'icon': 'bi-speedometer2',
        'url_name': 'core:dashboard',
        'color': '#2563EB',
    },
    {
        'id': 'crm',
        'label': 'CRM',
        'icon': 'bi-people',
        'url_name': 'crm:index',
        'color': '#0891B2',
        'children': [
            {'label': 'Clients', 'url_name': 'crm:customer_list', 'icon': 'bi-person-check'},
            {'label': 'Prospects', 'url_name': 'crm:prospect_list', 'icon': 'bi-person-plus'},
            {'label': 'Opportunités', 'url_name': 'crm:opportunity_list', 'icon': 'bi-trophy'},
            {'label': 'Contacts', 'url_name': 'crm:contact_list', 'icon': 'bi-person-lines-fill'},
        ],
    },
    {
        'id': 'sales',
        'label': 'Ventes',
        'icon': 'bi-receipt',
        'url_name': 'sales:index',
        'color': '#2563EB',
        'children': [
            {'label': 'Devis',      'url_name': 'sales:quote_list',   'icon': 'bi-file-earmark-text'},
            {'label': 'Commandes',  'url_name': 'sales:order_list',   'icon': 'bi-bag'},
            {'label': 'Factures',   'url_name': 'sales:invoice_list', 'icon': 'bi-receipt-cutoff'},
        ],
    },
    {
        'id': 'accounting',
        'label': 'Comptabilité',
        'icon': 'bi-calculator',
        'url_name': 'accounting:index',
        'color': '#0891B2',
    },
    {
        'id': 'purchases',
        'label': 'Achats',
        'icon': 'bi-cart',
        'url_name': 'purchases:index',
        'color': '#7C3AED',
        'children': [
            {'label': 'Fournisseurs', 'url_name': 'purchases:supplier_list', 'icon': 'bi-building'},
            {'label': 'Commandes achat', 'url_name': 'purchases:order_list', 'icon': 'bi-basket'},
            {'label': 'Factures achat', 'url_name': 'purchases:supplier_invoice_list', 'icon': 'bi-receipt'},
        ],
    },
    {
        'id': 'inventory',
        'label': 'Stocks',
        'icon': 'bi-boxes',
        'url_name': 'inventory:index',
        'color': '#16A34A',
        'children': [
            {'label': 'Produits', 'url_name': 'inventory:product_list', 'icon': 'bi-box'},
            {'label': 'Entrepôts', 'url_name': 'inventory:warehouse_list', 'icon': 'bi-building'},
            {'label': 'Mouvements', 'url_name': 'inventory:movement_list', 'icon': 'bi-arrow-left-right'},
        ],
    },
    {
        'id': 'btp',
        'label': 'BTP',
        'icon': 'bi-building',
        'url_name': 'btp:index',
        'color': '#F59E0B',
        'children': [
            {'label': 'Chantiers',      'url_name': 'btp:project_list',          'icon': 'bi-geo-alt'},
            {'label': 'Devis BTP',      'url_name': 'btp:quote_list',            'icon': 'bi-file-earmark-ruled'},
            {'label': 'Pointages',      'url_name': 'btp:timesheet_list',        'icon': 'bi-clock'},
            {'label': 'Situations',     'url_name': 'btp:situation_list',        'icon': 'bi-list-check'},
            {'label': 'Journal chantier','url_name': 'btp_smart_site_log:dashboard','icon': 'bi-journal-check'},
        ],
    },
    {
        'id': 'ecommerce',
        'label': 'E-commerce',
        'icon': 'bi-shop',
        'url_name': 'ecommerce:index',
        'color': '#7C3AED',
        'children': [
            {'label': 'Commandes web', 'url_name': 'ecommerce:order_list', 'icon': 'bi-bag-check'},
            {'label': 'Catalogue', 'url_name': 'ecommerce:product_list', 'icon': 'bi-grid'},
            {'label': 'Expéditions', 'url_name': 'ecommerce:shipment_list', 'icon': 'bi-truck'},
            {'label': 'Retours', 'url_name': 'ecommerce:return_list', 'icon': 'bi-arrow-return-left'},
        ],
    },
    {
        'id': 'lunea_beauty_profile',
        'label': 'Profils beauté',
        'icon': 'bi-stars',
        'url_name': 'lunea_beauty_profile:dashboard',
        'color': '#C9A45C',
        'children': [
            {'label': 'Dashboard',         'url_name': 'lunea_beauty_profile:dashboard',           'icon': 'bi-speedometer2'},
            {'label': 'Profils',           'url_name': 'lunea_beauty_profile:profile_list',        'icon': 'bi-person-heart'},
            {'label': 'Recommandations',   'url_name': 'lunea_beauty_profile:recommendations_list','icon': 'bi-stars'},
            {'label': 'Diagnostics',       'url_name': 'lunea_beauty_profile:diagnostics',         'icon': 'bi-clipboard2-pulse'},
            {'label': 'Routines',          'url_name': 'lunea_beauty_profile:routines',            'icon': 'bi-arrow-repeat'},
        ],
    },
    {
        'id': 'siecle_creations',
        'label': 'SIÈCLE Créations',
        'icon': 'bi-gem',
        'url_name': 'siecle_creations:dashboard',
        'color': '#1C1C1C',
        'children': [
            {'label': 'Dashboard',      'url_name': 'siecle_creations:dashboard',   'icon': 'bi-speedometer2'},
            {'label': 'Catalogue',      'url_name': 'siecle_creations:catalog',     'icon': 'bi-grid'},
            {'label': 'Collections',    'url_name': 'siecle_creations:collections', 'icon': 'bi-collection'},
            {'label': 'Commandes',      'url_name': 'siecle_creations:campaigns',   'icon': 'bi-bag-check'},
        ],
    },
    {
        'id': 'commerce',
        'label': 'Commerce',
        'icon': 'bi-shop-window',
        'url_name': 'commerce:index',
        'color': '#2563EB',
        'children': [
            {'label': 'Caisse', 'url_name': 'commerce:pos_list', 'icon': 'bi-cash'},
            {'label': 'Magasins', 'url_name': 'commerce:store_list', 'icon': 'bi-shop'},
            {'label': 'Fidélité', 'url_name': 'commerce:loyalty_list', 'icon': 'bi-star'},
        ],
    },
    {
        'id': 'production',
        'label': 'Production',
        'icon': 'bi-gear',
        'url_name': 'production:index',
        'color': '#16A34A',
        'children': [
            {'label': 'Ordres fabrication', 'url_name': 'production:order_list', 'icon': 'bi-list-task'},
            {'label': 'Nomenclatures', 'url_name': 'production:bom_list', 'icon': 'bi-diagram-3'},
            {'label': 'Planning', 'url_name': 'production:planning', 'icon': 'bi-calendar3'},
        ],
    },
    {
        'id': 'audio',
        'label': 'Audio / AV',
        'icon': 'bi-speaker',
        'url_name': 'audio:index',
        'color': '#DB2777',
        'children': [
            {'label': 'Matériel', 'url_name': 'audio:equipment_list', 'icon': 'bi-headphones'},
            {'label': 'Réservations', 'url_name': 'audio:reservation_list', 'icon': 'bi-calendar-check'},
            {'label': 'Événements', 'url_name': 'audio:event_list', 'icon': 'bi-music-note-list'},
        ],
    },
    {
        'id': 'hr',
        'label': 'RH',
        'icon': 'bi-people-fill',
        'url_name': 'hr:index',
        'color': '#0D9488',
        'children': [
            {'label': 'Salariés',       'url_name': 'hr:employee_list', 'icon': 'bi-person-badge'},
            {'label': 'Congés',         'url_name': 'hr:leave_list',    'icon': 'bi-calendar-check'},
            {'label': 'Notes de frais', 'url_name': 'hr:expense_list',  'icon': 'bi-wallet'},
            {'label': 'Paie',           'url_name': 'payroll:index',    'icon': 'bi-cash-stack'},
        ],
    },
    {
        'id': 'documents',
        'label': 'Documents',
        'icon': 'bi-folder',
        'url_name': 'documents:index',
        'color': '#6B7280',
    },
    {
        'id': 'support',
        'label': 'Support',
        'icon': 'bi-headset',
        'url_name': 'support:index',
        'color': '#DC2626',
        'children': [
            {'label': 'Tickets', 'url_name': 'support:ticket_list', 'icon': 'bi-ticket'},
            {'label': 'Réclamations', 'url_name': 'support:claim_list', 'icon': 'bi-exclamation-circle'},
        ],
    },
    {
        'id': 'websites',
        'label': 'Sites web',
        'icon': 'bi-globe2',
        'url_name': 'websites:index',
        'color': '#0891B2',
        'children': [
            {'label': 'Mes sites', 'url_name': 'websites:website_list', 'icon': 'bi-layout-text-window'},
            {'label': 'Domaines', 'url_name': 'websites:domain_dashboard', 'icon': 'bi-globe2'},
            {'label': 'Pages', 'url_name': 'websites:page_list', 'icon': 'bi-file-earmark'},
            {'label': 'Blog', 'url_name': 'websites:blog_list', 'icon': 'bi-pencil-square'},
            {'label': 'Messages', 'url_name': 'websites:message_list', 'icon': 'bi-envelope'},
            {'label': 'Boutique', 'url_name': 'website_shop_settings:dashboard', 'icon': 'bi-shop'},
        ],
    },
    {
        'id': 'smart',
        'label': 'Automatisations & IA',
        'icon': 'bi-robot',
        'url_name': 'smart_alerts:list',
        'color': '#6366F1',
        'children': [
            {'label': 'Alertes',          'url_name': 'smart_alerts:list',          'icon': 'bi-bell-fill'},
            {'label': 'Automatisations',  'url_name': 'smart_automations:list',     'icon': 'bi-lightning-charge'},
            {'label': 'Workflows',        'url_name': 'workflow_center:list',       'icon': 'bi-diagram-3'},
            {'label': 'Planification IA', 'url_name': 'smart_planning:planning',    'icon': 'bi-calendar4-event'},
            {'label': 'Analytique',       'url_name': 'predictive_analytics:dashboard', 'icon': 'bi-graph-up-arrow'},
            {'label': 'Documents IA',     'url_name': 'smart_documents:list',       'icon': 'bi-file-earmark-sparkles'},
            {'label': 'Assistant Orion',  'url_name': 'orion_assistant:list',       'icon': 'bi-stars'},
        ],
    },
    {
        'id': 'qualite',
        'label': 'Qualité & Conformité',
        'icon': 'bi-shield-check',
        'url_name': 'quality_incidents:list',
        'color': '#0891B2',
        'children': [
            {'label': 'Incidents',       'url_name': 'quality_incidents:list',  'icon': 'bi-exclamation-triangle'},
            {'label': 'Audit',           'url_name': 'audit_compliance:list',   'icon': 'bi-clipboard2-check'},
            {'label': 'Contrôle accès',  'url_name': 'access_control:dashboard','icon': 'bi-person-lock'},
            {'label': 'Intégrations',    'url_name': 'integration_center:list', 'icon': 'bi-plug'},
        ],
    },
    {
        'id': 'continuous_improvement',
        'label': 'Amélioration continue',
        'icon': 'bi-arrow-repeat',
        'url_name': 'continuous_improvement:dashboard',
        'color': '#10B981',
        'children': [
            {'label': 'Tableau de bord',  'url_name': 'continuous_improvement:dashboard',      'icon': 'bi-speedometer2'},
            {'label': 'Cycles PDCA',      'url_name': 'continuous_improvement:cycle_list',     'icon': 'bi-list-ul'},
            {'label': 'Nouveau cycle',    'url_name': 'continuous_improvement:cycle_create',   'icon': 'bi-plus-circle'},
            {'label': 'Standards',        'url_name': 'continuous_improvement:standards_list', 'icon': 'bi-shield-check'},
            {'label': 'Modèles',          'url_name': 'continuous_improvement:templates_list', 'icon': 'bi-layout-text-window-reverse'},
        ],
    },
    {
        'id': 'bi',
        'label': 'Reporting',
        'icon': 'bi-bar-chart-line',
        'url_name': 'bi:index',
        'color': '#7C3AED',
    },
    {
        'id': 'competitor_intelligence',
        'label': 'Analyse concurrence',
        'icon': 'bi-binoculars',
        'url_name': 'competitor:dashboard',
        'color': '#6366F1',
        'children': [
            {'label': 'Dashboard',       'url_name': 'competitor:dashboard',         'icon': 'bi-speedometer2'},
            {'label': 'Concurrents',     'url_name': 'competitor:list',              'icon': 'bi-building-check'},
            {'label': 'Produits',        'url_name': 'competitor:product_list',      'icon': 'bi-grid-3x3'},
            {'label': 'Prix & historique','url_name': 'competitor:price_history',    'icon': 'bi-graph-down-arrow'},
            {'label': 'Trafic estimé',   'url_name': 'competitor:traffic',          'icon': 'bi-bar-chart-line'},
            {'label': 'Avantages',       'url_name': 'competitor:advantages',        'icon': 'bi-award'},
            {'label': 'Comparaison',     'url_name': 'competitor:compare',           'icon': 'bi-layout-split'},
            {'label': 'Alertes',         'url_name': 'competitor:alerts',            'icon': 'bi-bell'},
            {'label': 'Rapports',        'url_name': 'competitor:reports',           'icon': 'bi-file-earmark-bar-graph'},
        ],
    },
    {
        'id': 'backups',
        'label': 'Sauvegardes',
        'icon': 'bi-cloud-arrow-down',
        'url_name': 'backups:dashboard',
        'color': '#0D9488',
        'children': [
            {'label': 'Dashboard',     'url_name': 'backups:dashboard',  'icon': 'bi-speedometer2'},
            {'label': 'Sauvegardes',   'url_name': 'backups:list',       'icon': 'bi-archive'},
            {'label': 'Planification', 'url_name': 'backups:schedules',  'icon': 'bi-calendar-check'},
            {'label': 'Créer',         'url_name': 'backups:create',     'icon': 'bi-plus-circle'},
            {'label': 'Paramètres',    'url_name': 'backups:settings',   'icon': 'bi-sliders'},
        ],
    },
    {
        'id': 'private_saas',
        'label': 'Super Admin',
        'icon': 'bi-shield-lock',
        'url_name': 'private_saas:dashboard',
        'color': '#DC2626',
        'super_admin_only': True,
        'children': [
            {'label': 'Dashboard',       'url_name': 'private_saas:dashboard',         'icon': 'bi-speedometer2'},
            {'label': 'Entreprises',     'url_name': 'private_saas:company_list',      'icon': 'bi-building'},
            {'label': 'Santé',           'url_name': 'private_saas:health',            'icon': 'bi-heart-pulse'},
            {'label': 'Observabilité',      'url_name': 'system_observability:dashboard',  'icon': 'bi-activity'},
            {'label': 'Mises à jour',       'url_name': 'system_updates:dashboard',        'icon': 'bi-cloud-download'},
            {'label': 'Centre sauvegardes', 'url_name': 'backup_center:dashboard',          'icon': 'bi-hdd-rack'},
            {'label': 'Haute dispo.',       'url_name': 'high_availability:admin_settings', 'icon': 'bi-server'},
            {'label': 'Nœuds HA',           'url_name': 'high_availability:admin_nodes',    'icon': 'bi-diagram-3'},
            {'label': 'Basculement HA',     'url_name': 'high_availability:admin_failover', 'icon': 'bi-arrow-left-right'},
            {'label': 'Paramètres',         'url_name': 'private_saas:saas_settings',       'icon': 'bi-sliders'},
            {'label': 'IA — Paramètres',    'url_name': 'orion_ai:admin_ai_settings',      'icon': 'bi-robot'},
            {'label': 'IA — Audit',         'url_name': 'orion_ai:admin_ai_audit',         'icon': 'bi-journal-text'},
        ],
    },
    {
        'id': 'orion_ai',
        'label': 'Assistant IA',
        'icon': 'bi-stars',
        'url_name': 'orion_ai:assistant_dashboard',
        'color': '#6366F1',
        'children': [
            {'label': 'Chat IA',         'url_name': 'orion_ai:assistant_dashboard', 'icon': 'bi-chat-heart'},
            {'label': 'Conversations',   'url_name': 'orion_ai:conversations',       'icon': 'bi-chat-left-text'},
            {'label': 'Mémoire IA',      'url_name': 'orion_ai:memory',              'icon': 'bi-memory'},
            {'label': 'Paramètres IA',   'url_name': 'orion_ai:user_settings',       'icon': 'bi-sliders'},
        ],
    },
    {
        'id': 'settings',
        'label': 'Paramètres',
        'icon': 'bi-gear-fill',
        'color': '#6B7280',
        'children': [
            {'label': 'Mon profil',       'url_name': 'accounts:profile',   'icon': 'bi-person-circle'},
            {'label': 'Utilisateurs',     'url_name': 'accounts:user_list', 'icon': 'bi-people'},
            {'label': 'Entreprises',      'url_name': 'core:company_list',  'icon': 'bi-building'},
            {'label': 'Administration',   'url_name': 'admin:index',        'icon': 'bi-shield-check'},
        ],
    },
]


def navigation_context(request):
    """Injecte la navigation filtrée par modules entreprise dans tous les templates ERP."""
    if not request.user.is_authenticated:
        return {'nav_modules': [], 'is_super_admin': False}

    current_path = request.path
    company = getattr(request, 'current_company', None)
    is_super_admin = request.user.is_superuser

    # Filtrage des modules selon l'entreprise active
    try:
        from apps.private_saas.permissions import filter_nav_modules
        visible_modules = filter_nav_modules(NAV_MODULES, company, user=request.user)
    except Exception:
        visible_modules = NAV_MODULES

    # Détermine le module actif
    active_module = None
    for module in visible_modules:
        if f'/{module["id"]}/' in current_path or current_path.startswith('/orion-admin'):
            active_module = module['id']
            break
    if current_path.startswith('/orion-admin'):
        active_module = 'private_saas'

    return {
        'nav_modules':    visible_modules,
        'active_module':  active_module,
        'is_super_admin': is_super_admin,
    }


def brand_context(request):
    """Injecte les constantes de marque Orion ERP dans tous les templates."""
    from .brand import (
        BRAND_NAME, BRAND_SHORT_NAME, BRAND_SHORT, BRAND_TAGLINE, BRAND_VERSION,
        BRAND_COLORS, BRAND_PRIMARY_COLOR, BRAND_SECONDARY_COLOR, BRAND_ACCENT_COLOR,
        BRAND_LOGO_PATH, BRAND_LOGO_LIGHT_PATH, BRAND_ICON_PATH, BRAND_ICON_LIGHT_PATH,
        BRAND_FAVICON_PATH, LOGO_PATH, LOGO_WHITE_PATH,
    )
    return {
        # Textes
        'brand_name':           BRAND_NAME,
        'brand_short_name':     BRAND_SHORT_NAME,
        'brand_short':          BRAND_SHORT,
        'brand_tagline':        BRAND_TAGLINE,
        'brand_version':        BRAND_VERSION,
        # Logos
        'BRAND_LOGO_PATH':      BRAND_LOGO_PATH,
        'BRAND_LOGO_LIGHT_PATH': BRAND_LOGO_LIGHT_PATH,
        'BRAND_ICON_PATH':      BRAND_ICON_PATH,
        'BRAND_ICON_LIGHT_PATH': BRAND_ICON_LIGHT_PATH,
        'BRAND_FAVICON_PATH':   BRAND_FAVICON_PATH,
        # Rétrocompatibilité
        'brand_logo_path':      BRAND_LOGO_PATH,
        'brand_logo_white_path': BRAND_LOGO_LIGHT_PATH,
        # Couleurs
        'brand_colors':         BRAND_COLORS,
        'BRAND_PRIMARY_COLOR':  BRAND_PRIMARY_COLOR,
        'BRAND_SECONDARY_COLOR': BRAND_SECONDARY_COLOR,
        'BRAND_ACCENT_COLOR':   BRAND_ACCENT_COLOR,
    }
