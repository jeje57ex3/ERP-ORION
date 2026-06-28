"""
python manage.py seed_dashboard_demo
Crée des dashboards de démonstration par rôle.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from apps.core.models import Company
from apps.dashboard.models import DashboardProfile, DashboardWidget, UserDashboardWidget, DashboardShortcut


ROLE_WIDGETS = {
    'direction': [
        ('accounting_cash_balance', 0, 0, 4),
        ('sales_unpaid_invoices', 4, 0, 4),
        ('accounting_overdue_customer_invoices', 8, 0, 4),
        ('btp_active_projects', 0, 1, 8),
        ('my_validations', 8, 1, 4),
        ('my_notifications', 0, 2, 6),
        ('crm_open_opportunities', 6, 2, 6),
    ],
    'comptable': [
        ('accounting_cash_balance', 0, 0, 4),
        ('accounting_vat_summary', 4, 0, 4),
        ('accounting_draft_entries', 8, 0, 4),
        ('accounting_overdue_customer_invoices', 0, 1, 6),
        ('accounting_supplier_invoices_due', 6, 1, 6),
        ('hr_expenses_to_validate', 0, 2, 6),
        ('my_notifications', 6, 2, 6),
    ],
    'responsable_chantier': [
        ('btp_my_projects', 0, 0, 8),
        ('btp_hours_to_validate', 8, 0, 4),
        ('btp_open_reservations', 0, 1, 6),
        ('btp_pending_change_requests', 6, 1, 6),
        ('my_messages', 0, 2, 6),
        ('recent_documents', 6, 2, 6),
    ],
    'salarie_terrain': [
        ('btp_my_projects', 0, 0, 8),
        ('my_notifications', 8, 0, 4),
        ('hr_my_private_documents', 0, 1, 6),
        ('calendar_events', 6, 1, 6),
        ('favorite_shortcuts', 0, 2, 12),
    ],
    'commercial': [
        ('crm_followups', 0, 0, 6),
        ('crm_open_opportunities', 6, 0, 6),
        ('sales_quotes_to_send', 0, 1, 6),
        ('sales_quotes_waiting_response', 6, 1, 6),
        ('sales_unpaid_invoices', 0, 2, 6),
        ('my_notifications', 6, 2, 6),
    ],
    'ecommerce': [
        ('ecommerce_orders_to_prepare', 0, 0, 6),
        ('inventory_low_stock_products', 6, 0, 6),
        ('ecommerce_returns_pending', 0, 1, 6),
        ('commerce_daily_sales', 6, 1, 4),
        ('my_notifications', 10, 1, 2),
        ('my_messages', 0, 2, 12),
    ],
}

ROLE_NAMES = {
    'direction': 'Dashboard Direction',
    'comptable': 'Dashboard Comptable',
    'responsable_chantier': 'Dashboard Responsable Chantier',
    'salarie_terrain': 'Dashboard Salarié Terrain',
    'commercial': 'Dashboard Commercial',
    'ecommerce': 'Dashboard E-commerce',
}


class Command(BaseCommand):
    help = 'Crée des dashboards de démonstration par rôle pour le premier superutilisateur.'

    def handle(self, *args, **options):
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            self.stdout.write(self.style.WARNING('Aucun superutilisateur trouvé.'))
            return
        company = Company.objects.filter(is_active=True).first()
        if not company:
            self.stdout.write(self.style.WARNING('Aucune entreprise active trouvée.'))
            return

        # S'assurer que les widgets existent
        from django.core.management import call_command
        call_command('seed_dashboard_widgets', verbosity=0)

        for role_key, widget_list in ROLE_WIDGETS.items():
            profile, _ = DashboardProfile.objects.get_or_create(
                user=user, company=company, name=ROLE_NAMES[role_key],
                defaults={'is_default': False}
            )
            profile.user_widgets.all().delete()
            for code, px, py, width in widget_list:
                widget = DashboardWidget.objects.filter(code=code).first()
                if widget:
                    UserDashboardWidget.objects.create(
                        dashboard_profile=profile,
                        widget=widget,
                        position_x=px,
                        position_y=py,
                        width=width,
                        is_visible=True,
                    )
            self.stdout.write(f'  ✓ {ROLE_NAMES[role_key]}')

        self.stdout.write(self.style.SUCCESS(f'{len(ROLE_WIDGETS)} dashboard(s) de démo créé(s) pour {user.username}.'))
