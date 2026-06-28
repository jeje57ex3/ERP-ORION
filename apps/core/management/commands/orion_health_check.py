"""
python manage.py orion_health_check

Vérifie l'état global d'Orion ERP :
  - Connexion base centrale
  - Connexions bases entreprises
  - Migrations manquantes
  - Répertoires (media, logs, backups)
  - Superadmins existants
  - Entreprises sans base
"""
import os
import sys
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Vérification de santé du système Orion ERP'

    OK = '  [OK] '
    WARN = '  [WARN] '
    ERR = '  [ERR] '

    def handle(self, *args, **options):
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('  Orion ERP — Vérification de santé système')
        self.stdout.write('=' * 60 + '\n')

        errors = []
        warnings = []

        errors, warnings = self._check_core_db(errors, warnings)
        errors, warnings = self._check_company_databases(errors, warnings)
        errors, warnings = self._check_migrations(errors, warnings)
        errors, warnings = self._check_directories(errors, warnings)
        errors, warnings = self._check_superadmins(errors, warnings)
        errors, warnings = self._check_companies_without_db(errors, warnings)
        errors, warnings = self._check_settings(errors, warnings)

        self.stdout.write('\n' + '─' * 60)
        if not errors and not warnings:
            self.stdout.write(self.style.SUCCESS('\n  Système sain. Aucune anomalie détectée.\n'))
        else:
            if warnings:
                self.stdout.write(self.style.WARNING(f'\n  {len(warnings)} avertissement(s) :'))
                for w in warnings:
                    self.stdout.write(self.style.WARNING(f'    - {w}'))
            if errors:
                self.stdout.write(self.style.ERROR(f'\n  {len(errors)} erreur(s) critique(s) :'))
                for e in errors:
                    self.stdout.write(self.style.ERROR(f'    - {e}'))
        self.stdout.write('')

    def _check_core_db(self, errors, warnings):
        self.stdout.write('Base centrale :')
        try:
            from django.db import connections
            conn = connections['default']
            conn.ensure_connection()
            self.stdout.write(self.style.SUCCESS(self.OK + f"Connexion OK ({settings.DATABASES['default']['NAME']})"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(self.ERR + f"Connexion échouée: {e}"))
            errors.append(f"Base centrale inaccessible: {e}")
        return errors, warnings

    def _check_company_databases(self, errors, warnings):
        self.stdout.write('\nBases entreprises :')
        try:
            from apps.core.models import Company
            from django.db import connections
            companies = Company.objects.filter(database_created=True, is_active=True)
            ok_count = 0
            for company in companies:
                alias = f'company_{company.pk}'
                if alias in connections:
                    try:
                        connections[alias].ensure_connection()
                        ok_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(self.ERR + f"{company.name}: {e}"))
                        errors.append(f"Base {company.name} inaccessible")
                else:
                    warnings.append(f"Alias '{alias}' non chargé dans DATABASES pour {company.name}")
            if ok_count:
                self.stdout.write(self.style.SUCCESS(self.OK + f"{ok_count} base(s) entreprise OK"))
            elif not companies:
                self.stdout.write(self.OK + "Aucune base entreprise dédiée configurée")
        except Exception as e:
            warnings.append(f"Vérification bases entreprises échouée: {e}")
        return errors, warnings

    def _check_migrations(self, errors, warnings):
        self.stdout.write('\nMigrations :')
        try:
            from django.db.migrations.executor import MigrationExecutor
            from django.db import connections
            executor = MigrationExecutor(connections['default'])
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            if plan:
                pending = [str(m) for m, _ in plan]
                self.stdout.write(self.style.WARNING(self.WARN + f"{len(pending)} migration(s) en attente"))
                warnings.append(f"Migrations en attente: {', '.join(pending[:5])}")
            else:
                self.stdout.write(self.style.SUCCESS(self.OK + "Toutes les migrations appliquées"))
        except Exception as e:
            warnings.append(f"Vérification migrations échouée: {e}")
        return errors, warnings

    def _check_directories(self, errors, warnings):
        self.stdout.write('\nRépertoires :')
        dirs_to_check = {
            'media': settings.MEDIA_ROOT,
            'logs': getattr(settings, 'LOG_DIR', settings.BASE_DIR / 'logs'),
            'backups': getattr(settings, 'BACKUP_DIR', settings.BASE_DIR / 'backups'),
        }
        for name, path in dirs_to_check.items():
            p = Path(path)
            if p.exists():
                self.stdout.write(self.style.SUCCESS(self.OK + f"{name}/ ({p})"))
            else:
                try:
                    p.mkdir(parents=True, exist_ok=True)
                    self.stdout.write(self.style.WARNING(self.WARN + f"{name}/ créé ({p})"))
                    warnings.append(f"Répertoire {name}/ créé automatiquement")
                except Exception as e:
                    self.stdout.write(self.style.ERROR(self.ERR + f"{name}/: {e}"))
                    errors.append(f"Impossible de créer {name}/: {e}")
        return errors, warnings

    def _check_superadmins(self, errors, warnings):
        self.stdout.write('\nSuperadmins :')
        try:
            from django.contrib.auth.models import User
            count = User.objects.filter(is_superuser=True, is_active=True).count()
            if count == 0:
                self.stdout.write(self.style.ERROR(self.ERR + "Aucun superadmin actif !"))
                errors.append("Aucun superadmin actif dans la base")
            else:
                self.stdout.write(self.style.SUCCESS(self.OK + f"{count} superadmin(s) actif(s)"))
        except Exception as e:
            warnings.append(f"Vérification superadmins échouée: {e}")
        return errors, warnings

    def _check_companies_without_db(self, errors, warnings):
        self.stdout.write('\nEntreprises sans base :')
        try:
            from apps.core.models import Company
            orphans = Company.objects.filter(is_active=True, database_created=False)
            count = orphans.count()
            if count:
                names = ', '.join(orphans.values_list('name', flat=True)[:5])
                self.stdout.write(self.style.WARNING(self.WARN + f"{count} entreprise(s) sans base: {names}"))
                warnings.append(f"{count} entreprise(s) actives sans base dédiée")
            else:
                self.stdout.write(self.style.SUCCESS(self.OK + "Toutes les entreprises actives ont une base"))
        except Exception as e:
            warnings.append(f"Vérification entreprises échouée: {e}")
        return errors, warnings

    def _check_settings(self, errors, warnings):
        self.stdout.write('\nConfiguration :')
        if settings.DEBUG:
            self.stdout.write(self.style.WARNING(self.WARN + "DEBUG=True (ne jamais utiliser en production)"))
            warnings.append("DEBUG=True")
        else:
            self.stdout.write(self.style.SUCCESS(self.OK + "DEBUG=False"))

        secret = settings.SECRET_KEY
        if 'insecure' in secret or 'change-me' in secret or len(secret) < 40:
            self.stdout.write(self.style.ERROR(self.ERR + "SECRET_KEY faible ou par défaut !"))
            errors.append("SECRET_KEY non sécurisée")
        else:
            self.stdout.write(self.style.SUCCESS(self.OK + "SECRET_KEY configurée"))

        return errors, warnings
