"""
python manage.py check_private_saas
Vérifie la santé du système SaaS privé Orion ERP.
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Vérifie la santé du SaaS privé Orion ERP'

    def handle(self, *args, **options):
        ok_count = 0
        fail_count = 0

        def check(label, fn):
            nonlocal ok_count, fail_count
            try:
                detail = fn()
                self.stdout.write(self.style.SUCCESS(f'  OK {label}') + (f' - {detail}' if detail else ''))
                ok_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  FAIL {label} - {e}'))
                fail_count += 1

        self.stdout.write('\n===============================================')
        self.stdout.write('  Orion ERP -- Diagnostic SaaS Prive')
        self.stdout.write('===============================================\n')

        # 1. Base centrale
        self.stdout.write('[ Base de données centrale ]')
        def _check_db():
            connection.ensure_connection()
            return 'OK'
        check('Connexion base centrale', _check_db)

        # 2. Entreprises
        self.stdout.write('\n[ Entreprises ]')
        from apps.core.models import Company
        companies = Company.objects.all()

        def _check_companies():
            n = companies.count()
            active = companies.filter(is_active=True).count()
            return f'{n} total, {active} actives'
        check('Nombre d\'entreprises', _check_companies)

        for company in companies:
            def _check_co(c=company):
                return f'statut={c.status}, secteur={c.sector}'
            check(f'  Entreprise: {company.name}', _check_co)

        # 3. Modules
        self.stdout.write('\n[ Modules ]')
        from apps.private_saas.models import CompanyModule

        def _check_modules():
            total   = CompanyModule.objects.count()
            enabled = CompanyModule.objects.filter(is_enabled=True).count()
            return f'{enabled} activés / {total} configurés'
        check('Modules configurés', _check_modules)

        for company in companies:
            def _check_co_modules(c=company):
                enabled = CompanyModule.objects.filter(company=c, is_enabled=True).count()
                return f'{enabled} modules actifs'
            check(f'  Modules {company.name}', _check_co_modules)

        # 4. Settings SaaS
        self.stdout.write('\n[ Paramètres SaaS ]')
        from apps.private_saas.models import PrivateSaaSSettings

        def _check_saas():
            s = PrivateSaaSSettings.get()
            parts = []
            if s.private_mode_enabled:
                parts.append('mode privé ON')
            if not s.public_signup_enabled:
                parts.append('inscription OFF')
            if s.maintenance_mode:
                parts.append('MAINTENANCE')
            return ', '.join(parts) or 'OK'
        check('Paramètres SaaS privé', _check_saas)

        # 5. Sites web
        self.stdout.write('\n[ Sites web ]')
        try:
            from apps.websites.models import Website
            def _check_sites():
                n = Website.objects.count()
                active = Website.objects.filter(is_active=True).count()
                return f'{n} total, {active} actifs'
            check('Sites web', _check_sites)
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ~ Sites web non disponibles: {e}'))

        # 6. Domaines
        self.stdout.write('\n[ Domaines ]')
        try:
            from apps.websites.models import WebsiteDomain
            def _check_domains():
                n = WebsiteDomain.objects.count()
                active = WebsiteDomain.objects.filter(status='active').count()
                return f'{n} total, {active} actifs'
            check('Domaines', _check_domains)
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ~ Domaines non disponibles: {e}'))

        # 7. Sauvegardes
        self.stdout.write('\n[ Sauvegardes ]')
        from apps.private_saas.models import CompanyBackup

        def _check_backups():
            last = CompanyBackup.objects.filter(status='success').order_by('-created_at').first()
            if last:
                return f'Dernière: {last.created_at:%d/%m/%Y %H:%M} ({last.company.name})'
            return 'Aucune sauvegarde'
        check('Sauvegardes', _check_backups)

        # Résumé
        self.stdout.write(f'\n===============================================')
        total = ok_count + fail_count
        if fail_count == 0:
            self.stdout.write(self.style.SUCCESS(f'  OK {ok_count}/{total} verifications reussies - Systeme sain'))
        else:
            self.stdout.write(self.style.WARNING(f'  ! {ok_count} OK / {fail_count} erreurs - Action requise'))
        self.stdout.write('===============================================\n')
