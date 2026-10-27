"""
Context processors — données injectées dans tous les templates ERP
"""
from django.utils.translation import gettext_lazy as _

from .models import Company


def _get_erp_languages():
    """
    Langues actives pour le sélecteur de la topbar ERP interne
    (`templates/layouts/topbar.html`). Même format que
    `apps.websites.public_views._get_website_languages` (sites publics),
    mais sans notion de site : liste globale des langues actives.
    """
    try:
        from django.utils import translation
        from apps.translations.models import Language

        current = translation.get_language() or 'fr'
        return [
            {'code': lang.code, 'native_name': lang.native_name, 'flag_icon': lang.flag_icon,
             'is_current': lang.code == current}
            for lang in Language.objects.filter(is_active=True)
        ]
    except Exception:
        return []


def erp_context(request):
    """Contexte global ERP : entreprise courante, notifications, user."""
    ctx = {
        'current_company': None,
        'companies': [],
        'unread_notifications': [],
        'unread_count': 0,
        'erp_languages': _get_erp_languages(),
        'maintenance_annonce': None,
    }

    # L'annonce est lue AVANT le test d'authentification : une maintenance
    # concerne aussi les pages publiques, et un visiteur du portail client
    # a autant besoin d'etre averti qu'un salarie.
    #
    # courante() n'echoue jamais -- elle avale ses propres erreurs -- car
    # elle est appelee sur CHAQUE page : une table absente entre le
    # deploiement du code et la migration ne doit pas rendre l'ERP
    # inaccessible.
    try:
        from apps.core.models import MaintenanceAnnonce
        ctx['maintenance_annonce'] = MaintenanceAnnonce.courante()
    except Exception:
        pass

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
        'label': _('Mon dashboard'),
        'icon_img': 'private_saas_dashboard.png',
        'icon': 'ti-layout-grid',
        'url_name': 'dashboard:home',
        'color': '#C6A15B',
        'children': [
            # Dans « Mon dashboard » et non dans Super Admin : ce module
            # figure dans always_show, donc l'entree est visible de tous. La
            # page photo sert d'abord aux chefs de chantier, qui ne sont pas
            # super administrateurs -- place ailleurs, elle leur restait
            # invisible.
            {'label': _('Version téléphone'), 'url_name': 'mobile_web:accueil',
             'icon_img': 'private_saas_dashboard.png', 'icon': 'ti-device-mobile'},
            # A cote de la version telephone, pour la meme raison : ce module
            # est dans always_show, donc l'entree reste visible de tous. Un
            # employe qui veut l'application sur son poste n'a pas a passer
            # par un administrateur.
            {'label': _('Version PC'), 'url_name': 'dashboard:version_pc',
             'icon_img': 'private_saas_dashboard.png', 'icon': 'ti-device-desktop'},
        ],
    },
    {
        'id': 'erp_overview',
        'label': _('Vue générale'),
        'icon_img': 'ci_dashboard.png',
        'icon': 'ti-gauge',
        'url_name': 'core:dashboard',
        'color': '#2563EB',
    },
    {
        'id': 'crm',
        'label': _('CRM'),
        'icon_img': 'clients.png',
        'icon': 'ti-users',
        'url_name': 'crm:index',
        'color': '#0891B2',
        'children': [
            {'label': _('Clients'), 'url_name': 'crm:customer_list', 'icon_img': 'clients.png', 'icon': 'ti-user-check'},
            {'label': _('Prospects'), 'url_name': 'crm:prospect_list', 'icon_img': 'prospects.png', 'icon': 'ti-user-plus'},
            {'label': _('Opportunités'), 'url_name': 'crm:opportunity_list', 'icon_img': 'opportunites.png', 'icon': 'ti-trophy'},
            {'label': _('Contacts'), 'url_name': 'crm:contact_list', 'icon_img': 'contacts.png', 'icon': 'ti-address-book'},
        ],
    },
    {
        'id': 'sales',
        'label': _('Ventes'),
        'icon_img': 'devis_vente.png',
        'icon': 'ti-receipt',
        'url_name': 'sales:index',
        'color': '#2563EB',
        'children': [
            {'label': _('Devis'),      'url_name': 'sales:quote_list',   'icon_img': 'devis_vente.png', 'icon': 'ti-file-text'},
            {'label': _('Modèles de devis'), 'url_name': 'sales:quote_template_list', 'icon_img': 'devis_vente.png', 'icon': 'ti-file-symlink'},
            {'label': _('Commandes'),  'url_name': 'sales:order_list',   'icon_img': 'commandes_vente.png', 'icon': 'ti-shopping-bag'},
            {'label': _('Factures'),   'url_name': 'sales:invoice_list', 'icon_img': 'factures_vente.png', 'icon': 'ti-receipt-2'},
        ],
    },
    {
        'id': 'accounting',
        'label': _('Comptabilité'),
        'icon_img': 'comptabilite.png', 'icon': 'ti-calculator',
        'url_name': 'accounting:index',
        'color': '#0891B2',
    },
    {
        'id': 'purchases',
        'label': _('Achats'),
        'icon_img': 'fournisseurs.png',
        'icon': 'ti-shopping-cart',
        'url_name': 'purchases:index',
        'color': '#7C3AED',
        'children': [
            {'label': _('Fournisseurs'), 'url_name': 'purchases:supplier_list', 'icon_img': 'fournisseurs.png', 'icon': 'ti-building'},
            {'label': _('Commandes achat'), 'url_name': 'purchases:order_list', 'icon_img': 'cmd_achat.png', 'icon': 'ti-basket'},
            {'label': _('Factures achat'), 'url_name': 'purchases:supplier_invoice_list', 'icon_img': 'factures_achat.png', 'icon': 'ti-receipt'},
            {'label': _('Importer une facture PDF'), 'url_name': 'purchases:invoice_import', 'icon_img': 'factures_achat.png', 'icon': 'ti-file-import'},
        ],
    },
    {
        'id': 'inventory',
        'label': _('Stocks'),
        'icon_img': 'produits_stock.png',
        'icon': 'ti-box-multiple',
        'url_name': 'inventory:index',
        'color': '#16A34A',
        'children': [
            {'label': _('Produits'), 'url_name': 'inventory:product_list', 'icon_img': 'produits_stock.png', 'icon': 'ti-box'},
            {'label': _('Entrepôts'), 'url_name': 'inventory:warehouse_list', 'icon_img': 'entrepots.png', 'icon': 'ti-building'},
            {'label': _('Mouvements'), 'url_name': 'inventory:movement_list', 'icon_img': 'mouvements.png', 'icon': 'ti-arrows-left-right'},
        ],
    },
    {
        'id': 'btp',
        'label': _('BTP'),
        'icon_img': 'chantiers.png',
        'icon': 'ti-building',
        'url_name': 'btp:index',
        'color': '#F59E0B',
        'children': [
            {'label': _('Tableau de bord'),   'url_name': 'btp:site_manager_dashboard','icon': 'ti-gauge'},
            {'label': _('Chantiers'),      'url_name': 'btp:project_list',          'icon_img': 'chantiers.png', 'icon': 'ti-map-pin'},
            {'label': _('Devis BTP'),      'url_name': 'btp:quote_list',            'icon_img': 'devis_btp.png', 'icon': 'ti-file-description'},
            {'label': _('Demandes guidées'),  'url_name': 'btp:guided_quote_list',   'icon': 'ti-clipboard-list'},
            {'label': _('Bibliothèque de prix'), 'url_name': 'btp:price_library_list', 'icon_img': 'prix_historique.png', 'icon': 'ti-cash'},
            {'label': _('Catalogue BTP'), 'url_name': 'btp:material_list', 'icon_img': 'produits_stock.png', 'icon': 'ti-box'},
            {'label': _('Catalogues web'), 'url_name': 'btp:catalogue_source_list', 'icon_img': 'produits_stock.png', 'icon': 'ti-cloud-download'},
            {'label': _('Frais de déplacement'), 'url_name': 'btp:travel_settings', 'icon': 'ti-gas-station'},
            {'label': _('Pointages'),      'url_name': 'btp:timesheet_list',        'icon_img': 'pointages.png', 'icon': 'ti-clock'},
            {'label': _('Situations'),     'url_name': 'btp:situation_list',        'icon_img': 'situations.png', 'icon': 'ti-list-check'},
            {'label': _('Réserves'),       'url_name': 'btp:reservations_list',     'icon': 'ti-alert-triangle'},
            {'label': _('Messages clients'), 'url_name': 'btp:client_messages_list', 'icon_img': 'messages.png', 'icon': 'ti-messages'},
            {'label': _('Journal chantier'),'url_name': 'btp_smart_site_log:dashboard','icon_img': 'journal_chantier.png', 'icon': 'ti-notebook'},
        ],
    },
    {
        'id': 'ecommerce',
        'label': _('E-commerce'),
        'icon_img': 'commandes_web.png',
        'icon': 'ti-building-store',
        'url_name': 'ecommerce:index',
        'color': '#7C3AED',
        'children': [
            {'label': _('Commandes web'), 'url_name': 'ecommerce:order_list', 'icon_img': 'commandes_web.png', 'icon': 'ti-shopping-bag-check'},
            {'label': _('Catalogue'), 'url_name': 'ecommerce:product_list', 'icon_img': 'catalogue_ecom.png', 'icon': 'ti-layout-grid'},
            {'label': _('Expéditions'), 'url_name': 'ecommerce:shipment_list', 'icon_img': 'expeditions.png', 'icon': 'ti-truck'},
            {'label': _('Retours'), 'url_name': 'ecommerce:return_list', 'icon_img': 'retours.png', 'icon': 'ti-arrow-back-up'},
        ],
    },
    {
        'id': 'lunea_beauty_profile',
        'label': _('Profils beauté'),
        'icon_img': 'lunea_dashboard.png',
        'icon': 'ti-sparkles',
        'url_name': 'lunea_beauty_profile:dashboard',
        'color': '#C9A45C',
        'children': [
            {'label': _('Dashboard'),         'url_name': 'lunea_beauty_profile:dashboard',           'icon_img': 'lunea_dashboard.png', 'icon': 'ti-gauge'},
            {'label': _('Profils'),           'url_name': 'lunea_beauty_profile:profile_list',        'icon_img': 'profils.png', 'icon': 'ti-heart'},
            {'label': _('Recommandations'),   'url_name': 'lunea_beauty_profile:recommendations_list','icon_img': 'recommandations.png', 'icon': 'ti-sparkles'},
            {'label': _('Diagnostics'),       'url_name': 'lunea_beauty_profile:diagnostics',         'icon_img': 'diagnostics.png', 'icon': 'ti-clipboard-heart'},
            {'label': _('Routines'),          'url_name': 'lunea_beauty_profile:routines',            'icon_img': 'routines.png', 'icon': 'ti-refresh'},
        ],
    },
    {
        'id': 'siecle_creations',
        'label': _('SIÈCLE Créations'),
        'icon_img': 'siecle_dashboard.png',
        'icon': 'ti-diamond',
        'url_name': 'siecle_creations:dashboard',
        'color': '#1C1C1C',
        'children': [
            {'label': _('Dashboard'),      'url_name': 'siecle_creations:dashboard',   'icon_img': 'siecle_dashboard.png', 'icon': 'ti-gauge'},
            {'label': _('Catalogue'),      'url_name': 'siecle_creations:catalog',     'icon_img': 'catalogue_siecle.png', 'icon': 'ti-layout-grid'},
            {'label': _('Collections'),    'url_name': 'siecle_creations:collections', 'icon_img': 'collections.png', 'icon': 'ti-stack'},
            {'label': _('Commandes'),      'url_name': 'siecle_creations:campaigns',   'icon_img': 'commandes_siecle.png', 'icon': 'ti-shopping-bag-check'},
        ],
    },
    {
        'id': 'commerce',
        'label': _('Commerce'),
        'icon_img': 'caisse.png',
        'icon': 'ti-window',
        'url_name': 'commerce:index',
        'color': '#2563EB',
        'children': [
            {'label': _('Caisse'), 'url_name': 'commerce:pos_list', 'icon_img': 'caisse.png', 'icon': 'ti-cash'},
            {'label': _('Magasins'), 'url_name': 'commerce:store_list', 'icon_img': 'magasins.png', 'icon': 'ti-building-store'},
            {'label': _('Fidélité'), 'url_name': 'commerce:loyalty_list', 'icon_img': 'fidelite.png', 'icon': 'ti-star'},
        ],
    },
    {
        'id': 'production',
        'label': _('Production'),
        'icon_img': 'ordres_fabrication.png',
        'icon': 'ti-settings',
        'url_name': 'production:index',
        'color': '#16A34A',
        'children': [
            {'label': _('Ordres fabrication'), 'url_name': 'production:order_list', 'icon_img': 'ordres_fabrication.png', 'icon': 'ti-clipboard-list'},
            {'label': _('Nomenclatures'), 'url_name': 'production:bom_list', 'icon_img': 'nomenclatures.png', 'icon': 'ti-sitemap'},
            {'label': _('Planning'), 'url_name': 'production:planning', 'icon_img': 'planning.png', 'icon': 'ti-calendar'},
        ],
    },
    {
        'id': 'audio',
        'label': _('Audio / AV'),
        'icon_img': 'materiel.png',
        'icon': 'ti-device-speaker',
        'url_name': 'audio:index',
        'color': '#DB2777',
        'children': [
            {'label': _('Matériel'), 'url_name': 'audio:equipment_list', 'icon_img': 'materiel.png', 'icon': 'ti-headphones'},
            {'label': _('Réservations'), 'url_name': 'audio:reservation_list', 'icon_img': 'reservations.png', 'icon': 'ti-calendar-check'},
            {'label': _('Événements'), 'url_name': 'audio:event_list', 'icon_img': 'evenements.png', 'icon': 'ti-music'},
        ],
    },
    {
        'id': 'hr',
        'label': _('RH'),
        'icon_img': 'salaries.png',
        'icon': 'ti-users',
        'url_name': 'hr:index',
        'color': '#0D9488',
        'children': [
            {'label': _('Salariés'),       'url_name': 'hr:employee_list', 'icon_img': 'salaries.png', 'icon': 'ti-id-badge'},
            {'label': _('Planning'),       'url_name': 'hr:planning_equipe', 'icon_img': 'conges.png', 'icon': 'ti-calendar'},
            {'label': _('Mon planning'),   'url_name': 'hr:mon_planning',  'icon_img': 'conges.png', 'icon': 'ti-calendar-user'},
            {'label': _('Congés'),         'url_name': 'hr:leave_list',    'icon_img': 'conges.png', 'icon': 'ti-calendar-check'},
            {'label': _('Arrêts de travail'), 'url_name': 'hr:stoppage_list', 'icon_img': 'conges.png', 'icon': 'ti-first-aid-kit'},
            {'label': _('Rythmes de travail'), 'url_name': 'hr:schedule_list', 'icon_img': 'conges.png', 'icon': 'ti-calendar-week'},
            {'label': _('Habilitations'),  'url_name': 'hr:certification_expiring', 'icon_img': 'salaries.png', 'icon': 'ti-certificate'},
            {'label': _('Notes de frais'), 'url_name': 'hr:expense_list',  'icon_img': 'notes_frais.png', 'icon': 'ti-wallet'},
            {'label': _('Paie'),           'url_name': 'payroll:index',    'icon_img': 'paie.png', 'icon': 'ti-moneybag'},
        ],
    },
    {
        # Planning et temps dedies. Place apres les RH : il planifie des
        # salaries et des missions, et c'est la que l'utilisateur le
        # cherche. Code module 'work_planning', declare dans
        # ALL_MODULE_CODES -- sans lui, require_company_module refusait ses
        # vingt-huit vues.
        'id': 'work_planning',
        'label': _('Planning'),
        'icon': 'ti-calendar-time',
        'url_name': 'work_planning:dashboard',
        'color': '#0891B2',
        'children': [
            {'label': _('Tableau de bord'),  'url_name': 'work_planning:dashboard',              'icon': 'ti-gauge'},
            {'label': _('Semaine'),          'url_name': 'work_planning:weekly_planning',        'icon': 'ti-calendar-week'},
            {'label': _('Missions'),         'url_name': 'work_planning:mission_list',           'icon': 'ti-clipboard-list'},
            {'label': _('Équipe'),           'url_name': 'work_planning:employee_list',          'icon': 'ti-users'},
            {'label': _('Contraintes'),      'url_name': 'work_planning:all_employee_constraints', 'icon': 'ti-lock-cog'},
            {'label': _('Demandes client'),  'url_name': 'work_planning:customer_request_list',  'icon': 'ti-inbox'},
            {'label': _('Saisir des heures'), 'url_name': 'work_planning:time_block_create',     'icon': 'ti-clock-plus'},
        ],
    },
    {
        # Formations internes. Place apres les RH parce que c'est de la
        # formation des salaries, et non un module separe dans l'esprit de
        # qui l'utilise. Son code module est 'internal_training', declare
        # dans ALL_MODULE_CODES : sans lui, require_company_module refusait
        # ses dix-neuf vues.
        'id': 'internal_training',
        'label': _('Formations'),
        'icon': 'ti-school',
        'url_name': 'internal_training:dashboard',
        'color': '#7C3AED',
        'children': [
            {'label': _('Tableau de bord'), 'url_name': 'internal_training:dashboard',      'icon': 'ti-gauge'},
            {'label': _('Formations'),      'url_name': 'internal_training:course_list',    'icon': 'ti-books'},
            {'label': _('Nouvelle'),        'url_name': 'internal_training:course_create',  'icon': 'ti-circle-plus'},
        ],
    },
    {
        'id': 'documents',
        'label': _('Documents'),
        'icon_img': 'documents.png', 'icon': 'ti-folder',
        'url_name': 'documents:index',
        'color': '#6B7280',
    },
    {
        'id': 'support',
        'label': _('Support'),
        'icon_img': 'tickets.png',
        'icon': 'ti-headset',
        'url_name': 'support:index',
        'color': '#DC2626',
        'children': [
            {'label': _('Tickets'), 'url_name': 'support:ticket_list', 'icon_img': 'tickets.png', 'icon': 'ti-ticket'},
            {'label': _('Réclamations'), 'url_name': 'support:claim_list', 'icon_img': 'reclamations.png', 'icon': 'ti-alert-circle'},
        ],
    },
    {
        'id': 'websites',
        'label': _('Sites web'),
        'icon_img': 'mes_sites.png',
        'icon': 'ti-world',
        'url_name': 'websites:index',
        'color': '#0891B2',
        'children': [
            {'label': _('Mes sites'), 'url_name': 'websites:website_list', 'icon_img': 'mes_sites.png', 'icon': 'ti-browser'},
            {'label': _('Domaines'), 'url_name': 'websites:domain_dashboard', 'icon_img': 'domaines.png', 'icon': 'ti-world'},
            {'label': _('Pages'), 'url_name': 'websites:page_list', 'icon_img': 'pages.png', 'icon': 'ti-file'},
            # Editeur visuel. Sous « Sites web » parce que c'est la qu'on
            # cherche a modifier les pages de son site -- et parce que
            # filter_nav_modules ne filtre que les modules de premier
            # niveau, pas leurs enfants : une entreprise qui a « websites »
            # sans « site_builder » verra le lien et le decorateur
            # require_company_module lui dira que le module n'est pas
            # active, ce qui est plus parlant qu'une absence.
            {'label': _('Éditeur visuel'), 'url_name': 'site_builder:page_list', 'icon_img': 'pages.png', 'icon': 'ti-layout-board'},
            {'label': _('Blog'), 'url_name': 'websites:blog_list', 'icon_img': 'blog.png', 'icon': 'ti-pencil'},
            {'label': _('Messages'), 'url_name': 'websites:message_list', 'icon_img': 'messages.png', 'icon': 'ti-mail'},
            {'label': _('Boutique'), 'url_name': 'website_shop_settings:dashboard', 'icon_img': 'boutique.png', 'icon': 'ti-building-store'},
        ],
    },
    {
        'id': 'smart',
        'label': _('Automatisations & IA'),
        'icon_img': 'alertes.png',
        'icon': 'ti-robot',
        'url_name': 'smart_alerts:list',
        'color': '#6366F1',
        'children': [
            {'label': _('Alertes'),          'url_name': 'smart_alerts:list',          'icon_img': 'alertes.png', 'icon': 'ti-bell'},
            {'label': _('Automatisations'),  'url_name': 'smart_automations:list',     'icon_img': 'automatisations.png', 'icon': 'ti-bolt'},
            {'label': _('Workflows'),        'url_name': 'workflow_center:list',       'icon_img': 'workflows.png', 'icon': 'ti-sitemap'},
            {'label': _('Planification IA'), 'url_name': 'smart_planning:planning',    'icon_img': 'planification_ia.png', 'icon': 'ti-calendar-event'},
            {'label': _('Analytique'),       'url_name': 'predictive_analytics:dashboard', 'icon_img': 'analytique_ia.png', 'icon': 'ti-trending-up'},
            {'label': _('Documents IA'),     'url_name': 'smart_documents:list',       'icon_img': 'documents_ia.png', 'icon': 'ti-file-ai'},
        ],
    },
    {
        'id': 'qualite',
        'label': _('Qualité & Conformité'),
        'icon_img': 'incidents.png',
        'icon': 'ti-shield-check',
        'url_name': 'quality_incidents:list',
        'color': '#0891B2',
        'children': [
            {'label': _('Incidents'),       'url_name': 'quality_incidents:list',  'icon_img': 'incidents.png', 'icon': 'ti-alert-triangle'},
            {'label': _('Audit'),           'url_name': 'audit_compliance:list',   'icon_img': 'audit.png', 'icon': 'ti-clipboard-check'},
            {'label': _('Contrôle accès'),  'url_name': 'access_control:dashboard','icon_img': 'controle_acces.png', 'icon': 'ti-lock-access'},
            {'label': _('Intégrations'),    'url_name': 'integration_center:list', 'icon_img': 'integrations.png', 'icon': 'ti-plug'},
        ],
    },
    {
        'id': 'continuous_improvement',
        'label': _('Amélioration continue'),
        'icon_img': 'tableau_bord_ci.png',
        'icon': 'ti-refresh',
        'url_name': 'continuous_improvement:dashboard',
        'color': '#10B981',
        'children': [
            {'label': _('Tableau de bord'),  'url_name': 'continuous_improvement:dashboard',      'icon_img': 'tableau_bord_ci.png', 'icon': 'ti-gauge'},
            {'label': _('Cycles PDCA'),      'url_name': 'continuous_improvement:cycle_list',     'icon_img': 'cycles_pdca.png', 'icon': 'ti-list'},
            {'label': _('Nouveau cycle'),    'url_name': 'continuous_improvement:cycle_create',   'icon_img': 'nouveau_cycle.png', 'icon': 'ti-circle-plus'},
            {'label': _('Standards'),        'url_name': 'continuous_improvement:standards_list', 'icon_img': 'standards.png', 'icon': 'ti-shield-check'},
            {'label': _('Modèles'),          'url_name': 'continuous_improvement:templates_list', 'icon_img': 'modeles.png', 'icon': 'ti-template'},
        ],
    },
    {
        'id': 'bi',
        'label': _('Reporting'),
        'icon_img': 'reporting.png', 'icon': 'ti-chart-bar',
        'url_name': 'bi:index',
        'color': '#7C3AED',
    },
    {
        'id': 'competitor_intelligence',
        'label': _('Analyse concurrence'),
        'icon_img': 'ci_dashboard.png',
        'icon': 'ti-binoculars',
        'url_name': 'competitor:dashboard',
        'color': '#6366F1',
        'children': [
            {'label': _('Dashboard'),       'url_name': 'competitor:dashboard',         'icon_img': 'ci_dashboard.png', 'icon': 'ti-gauge'},
            {'label': _('Concurrents'),     'url_name': 'competitor:list',              'icon_img': 'concurrents.png', 'icon': 'ti-building'},
            {'label': _('Produits'),        'url_name': 'competitor:product_list',      'icon_img': 'produits_ci.png', 'icon': 'ti-grid-3x3'},
            {'label': _('Prix & historique'),'url_name': 'competitor:price_history',    'icon_img': 'prix_historique.png', 'icon': 'ti-trending-down'},
            {'label': _('Trafic estimé'),   'url_name': 'competitor:traffic',          'icon_img': 'trafic_estime.png', 'icon': 'ti-chart-bar'},
            {'label': _('Avantages'),       'url_name': 'competitor:advantages',        'icon_img': 'avantages.png', 'icon': 'ti-award'},
            {'label': _('Comparaison'),     'url_name': 'competitor:compare',           'icon_img': 'comparaison.png', 'icon': 'ti-columns'},
            {'label': _('Alertes'),         'url_name': 'competitor:alerts',            'icon_img': 'alertes_ci.png', 'icon': 'ti-bell'},
            {'label': _('Rapports'),        'url_name': 'competitor:reports',           'icon_img': 'rapports.png', 'icon': 'ti-report'},
        ],
    },
    {
        'id': 'backups',
        'label': _('Sauvegardes'),
        'icon_img': 'backup_dashboard.png',
        'icon': 'ti-cloud-download',
        'url_name': 'backups:dashboard',
        'color': '#0D9488',
        'children': [
            {'label': _('Dashboard'),     'url_name': 'backups:dashboard',  'icon_img': 'backup_dashboard.png', 'icon': 'ti-gauge'},
            {'label': _('Sauvegardes'),   'url_name': 'backups:list',       'icon_img': 'sauvegardes.png', 'icon': 'ti-archive'},
            {'label': _('Planification'), 'url_name': 'backups:schedules',  'icon_img': 'planification_backup.png', 'icon': 'ti-calendar-check'},
            {'label': _('Créer'),         'url_name': 'backups:create',     'icon_img': 'creer_backup.png', 'icon': 'ti-circle-plus'},
            {'label': _('Paramètres'),    'url_name': 'backups:settings',   'icon_img': 'params_backup.png', 'icon': 'ti-adjustments'},
        ],
    },
    {
        'id': 'private_saas',
        'label': _('Super Admin'),
        'icon_img': 'private_saas_dashboard.png',
        'icon': 'ti-shield-lock',
        'url_name': 'private_saas:dashboard',
        'color': '#DC2626',
        'super_admin_only': True,
        'children': [
            {'label': _('Dashboard'),       'url_name': 'private_saas:dashboard',         'icon_img': 'private_saas_dashboard.png', 'icon': 'ti-gauge'},
            {'label': _('Entreprises'),     'url_name': 'private_saas:company_list',      'icon_img': 'entreprises.png', 'icon': 'ti-building'},
            {'label': _('Santé'),           'url_name': 'private_saas:health',            'icon_img': 'sante.png', 'icon': 'ti-heartbeat'},
            # Les pages de apps.system_health n'etaient atteignables que par
            # URL directe : aucune entree de navigation n'y menait, et
            # l'entree « Sante » ci-dessus pointe vers une autre page
            # (private_saas:health). On ne pouvait donc pas trouver le
            # tableau de bord des disques depuis l'interface.
            {'label': _('Santé du système'),   'url_name': 'system_health:dashboard',      'icon': 'ti-heartbeat'},
            {'label': _('Disques & stockage'), 'url_name': 'system_health:disk_dashboard', 'icon': 'ti-hdd'},
            {'label': _('Observabilité'),      'url_name': 'system_observability:dashboard',  'icon_img': 'observabilite.png', 'icon': 'ti-activity'},
            # Meme raison que « Santé du système » ci-dessus : les pages de
            # apps.orion_ops n'etaient atteignables par aucune entree de
            # navigation. « Observabilité » juste au-dessus pointe vers une
            # AUTRE application (system_observability), ce qui rendait la
            # confusion facile et la page introuvable.
            {'label': _('Ops — Fiabilité'),    'url_name': 'orion_ops:dashboard',             'icon': 'ti-activity-heartbeat'},
            {'label': _('Ops — SLO'),          'url_name': 'orion_ops:slo_list',              'icon': 'ti-target'},
            {'label': _('Mises à jour'),       'url_name': 'system_updates:dashboard',        'icon_img': 'mises_a_jour.png', 'icon': 'ti-cloud-download'},
            {'label': _('Centre sauvegardes'), 'url_name': 'backup_center:dashboard',          'icon_img': 'centre_sauvegardes.png', 'icon': 'ti-server-2'},
            {'label': _('Haute dispo.'),       'url_name': 'high_availability:admin_settings', 'icon_img': 'haute_dispo.png', 'icon': 'ti-server'},
            {'label': _('Nœuds HA'),           'url_name': 'high_availability:admin_nodes',    'icon_img': 'noeuds_ha.png', 'icon': 'ti-sitemap'},
            {'label': _('Relier serveurs'),    'url_name': 'high_availability:admin_cluster',  'icon_img': 'noeuds_ha.png', 'icon': 'ti-binary-tree'},
            {'label': _('Réseau privé'),       'url_name': 'high_availability:admin_mesh',     'icon_img': 'noeuds_ha.png', 'icon': 'ti-shield-lock'},
            {'label': _('Basculement HA'),     'url_name': 'high_availability:admin_failover', 'icon_img': 'basculement_ha.png', 'icon': 'ti-arrows-left-right'},
            {'label': _('Paramètres'),         'url_name': 'private_saas:saas_settings',       'icon_img': 'params_saas.png', 'icon': 'ti-adjustments'},
            {'label': _('IA — Paramètres'),    'url_name': 'orion_ai:admin_ai_settings',      'icon_img': 'ia_params_audit.png', 'icon': 'ti-robot'},
            {'label': _('IA — Audit'),         'url_name': 'orion_ai:admin_ai_audit',         'icon_img': 'ia_params_audit.png', 'icon': 'ti-book'},
        ],
    },
    {
        'id': 'orion_ai',
        'label': _('Assistant IA'),
        'icon_img': 'chat_ia.png',
        'icon': 'ti-sparkles',
        'url_name': 'orion_ai:assistant_dashboard',
        'color': '#6366F1',
        'children': [
            {'label': _('Chat IA'),         'url_name': 'orion_ai:assistant_dashboard', 'icon_img': 'chat_ia.png', 'icon': 'ti-message-chatbot'},
            {'label': _('Conversations'),   'url_name': 'orion_ai:conversations',       'icon_img': 'conversations.png', 'icon': 'ti-messages'},
            {'label': _('Mémoire IA'),      'url_name': 'orion_ai:memory',              'icon_img': 'memoire_ia.png', 'icon': 'ti-cpu'},
            {'label': _('Paramètres IA'),   'url_name': 'orion_ai:user_settings',       'icon_img': 'params_ia.png', 'icon': 'ti-adjustments'},
        ],
    },
    {
        'id': 'settings',
        'label': _('Paramètres'),
        'icon_img': 'mon_profil.png',
        'icon': 'ti-settings',
        'color': '#6B7280',
        'children': [
            {'label': _('Mon profil'),       'url_name': 'accounts:profile',   'icon_img': 'mon_profil.png', 'icon': 'ti-user-circle'},
            {'label': _('Utilisateurs'),     'url_name': 'accounts:user_list', 'icon_img': 'utilisateurs_settings.png', 'icon': 'ti-users'},
            {'label': _('Entreprises'),      'url_name': 'core:company_list',  'icon_img': 'entreprises_settings.png', 'icon': 'ti-building'},
            {'label': _('Administration'),   'url_name': 'admin:index',        'icon_img': 'administration.png', 'icon': 'ti-shield-check'},
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
