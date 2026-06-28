"""
python manage.py create_private_company --name="SIÈCLE" --type=fashion --admin-email="admin@siecle.fr"
"""
from django.core.management.base import BaseCommand, CommandError
from apps.private_saas.services import create_private_company, create_company_admin


COMPANY_TYPES = ['btp', 'fashion', 'beauty', 'watch', 'ecommerce', 'commerce', 'audio', 'production', 'generic']


class Command(BaseCommand):
    help = 'Crée une entreprise privée dans Orion ERP SaaS'

    def add_arguments(self, parser):
        parser.add_argument('--name',        required=True,  help='Nom de l\'entreprise')
        parser.add_argument('--type',        default='generic', choices=COMPANY_TYPES, help='Type d\'activité')
        parser.add_argument('--admin-email', required=True,  help='Email de l\'administrateur')
        parser.add_argument('--admin-password', default=None, help='Mot de passe (auto si absent)')
        parser.add_argument('--currency',    default='EUR', help='Devise (EUR, USD, GBP…)')

    def handle(self, *args, **options):
        name        = options['name']
        ctype       = options['type']
        admin_email = options['admin_email']
        admin_pwd   = options['admin_password']
        currency    = options['currency']

        self.stdout.write(f'\n╔══════════════════════════════════════════╗')
        self.stdout.write(f'║   Orion ERP — Création entreprise privée ║')
        self.stdout.write(f'╚══════════════════════════════════════════╝\n')

        # 1. Créer l'entreprise
        self.stdout.write(f'[1/3] Création de l\'entreprise « {name} » (type: {ctype})…')
        try:
            company = create_private_company(name=name, company_type=ctype)
            if currency != 'EUR':
                company.currency = currency
                company.save(update_fields=['currency'])
            self.stdout.write(self.style.SUCCESS(f'     ✓ Entreprise créée — ID: {company.pk}, slug: {company.slug}'))
        except Exception as e:
            raise CommandError(f'Erreur création entreprise: {e}')

        # 2. Créer l'admin
        self.stdout.write(f'[2/3] Création de l\'administrateur ({admin_email})…')
        try:
            user, pwd, created = create_company_admin(company, admin_email, password=admin_pwd)
            if created:
                self.stdout.write(self.style.SUCCESS(f'     ✓ Utilisateur créé — Email: {user.email}'))
                self.stdout.write(self.style.WARNING(f'     ! Mot de passe généré : {pwd}'))
                self.stdout.write(self.style.WARNING(f'     ! Notez-le — il ne sera plus affiché.'))
            else:
                self.stdout.write(self.style.SUCCESS(f'     ✓ Utilisateur existant rattaché: {user.email}'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'     ! Erreur admin (non bloquant): {e}'))

        # 3. Résumé modules
        self.stdout.write(f'[3/3] Modules activés…')
        from apps.private_saas.models import CompanyModule
        enabled = CompanyModule.objects.filter(company=company, is_enabled=True).values_list('module_code', flat=True)
        self.stdout.write(self.style.SUCCESS(f'     ✓ {len(enabled)} modules activés : {", ".join(enabled)}'))

        self.stdout.write(f'\n══════════════════════════════════════════════')
        self.stdout.write(self.style.SUCCESS(f'✓ Entreprise « {name} » prête !'))
        self.stdout.write(f'  Accès Super Admin : /orion-admin/entreprises/{company.pk}/')
        self.stdout.write(f'  Dashboard ERP     : /dashboard/')
        self.stdout.write(f'══════════════════════════════════════════════\n')
