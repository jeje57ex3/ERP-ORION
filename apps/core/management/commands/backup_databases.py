"""
python manage.py backup_databases

Options :
  --all         Sauvegarde toutes les bases (core + entreprises)
  --core        Sauvegarde uniquement la base centrale
  --company-id  Sauvegarde la base d'une entreprise spécifique
  --cleanup     Supprime les sauvegardes de plus de 30 jours après backup
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Sauvegarde les bases de données Orion ERP'

    def add_arguments(self, parser):
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--all', action='store_true', help='Sauvegarde toutes les bases')
        group.add_argument('--core', action='store_true', help='Sauvegarde la base centrale uniquement')
        group.add_argument('--company-id', type=int, help='ID de l\'entreprise à sauvegarder')
        parser.add_argument('--cleanup', action='store_true', help='Supprime les vieilles sauvegardes après')
        parser.add_argument('--cleanup-days', type=int, default=30, help='Jours de rétention (défaut: 30)')

    def handle(self, *args, **options):
        from apps.core.backups import (
            backup_core_database, backup_company_database,
            backup_all_company_databases, delete_old_backups
        )

        self.stdout.write('\n=== Orion ERP — Sauvegarde bases de données ===\n')

        if options['core'] or options['all']:
            self.stdout.write('Sauvegarde base centrale...')
            ok, msg = backup_core_database()
            if ok:
                self.stdout.write(self.style.SUCCESS(f'  OK: {msg}'))
            else:
                self.stdout.write(self.style.ERROR(f'  Erreur: {msg}'))

        if options['company_id']:
            try:
                from apps.core.models import Company
                company = Company.objects.get(pk=options['company_id'])
            except Company.DoesNotExist:
                raise CommandError(f"Entreprise #{options['company_id']} introuvable.")
            self.stdout.write(f'Sauvegarde entreprise : {company.name}...')
            ok, msg = backup_company_database(company)
            if ok:
                self.stdout.write(self.style.SUCCESS(f'  OK: {msg}'))
            else:
                self.stdout.write(self.style.ERROR(f'  Erreur: {msg}'))

        elif options['all']:
            self.stdout.write('Sauvegarde toutes les bases entreprises...')
            results = backup_all_company_databases()
            ok_count = sum(1 for r in results if r['ok'])
            err_count = len(results) - ok_count
            for r in results:
                if r['ok']:
                    self.stdout.write(self.style.SUCCESS(f"  OK: {r['company']} → {r['message']}"))
                else:
                    self.stdout.write(self.style.ERROR(f"  Erreur: {r['company']} — {r['message']}"))
            self.stdout.write(f'\n  Total: {ok_count} réussi(es), {err_count} erreur(s)')

        if options['cleanup']:
            days = options['cleanup_days']
            self.stdout.write(f'\nNettoyage des sauvegardes > {days} jours...')
            deleted = delete_old_backups(days=days)
            self.stdout.write(self.style.SUCCESS(f'  {deleted} fichier(s) supprimé(s)'))

        self.stdout.write('\n=== Terminé ===\n')
