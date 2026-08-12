"""
manage.py collect_health_sensors
Collecte immédiate de tous les capteurs (sans Celery).
Utile en dev ou pour forcer une collecte.
"""
from django.core.management.base import BaseCommand
from apps.system_health import services


class Command(BaseCommand):
    help = 'Collecte immédiate des capteurs système (sans Celery)'

    def handle(self, *args, **options):
        collectors = [
            ('Serveur (CPU/RAM/Disque)',  services.collect_server_sensors),
            ('Application (temps réponse)', services.collect_app_sensors),
            ('Base de données',           services.collect_db_sensors),
            ('Sauvegardes',               services.collect_backup_sensors),
            ('Sécurité',                  services.collect_security_sensors),
            ('Celery / Redis',            services.collect_celery_sensors),
        ]
        for label, fn in collectors:
            ok = fn()
            icon = self.style.SUCCESS('OK') if ok else self.style.WARNING('ECHEC')
            self.stdout.write(f'  {label:<30s} {icon}')

        self.stdout.write('')
        health = services.compute_global_health()
        self.stdout.write(self.style.SUCCESS(
            f'Score global : {health["score"]}/100 ({health["status"]})'
        ))
        for cat, score in health['breakdown'].items():
            color = self.style.SUCCESS if score >= 80 else (
                self.style.WARNING if score >= 50 else self.style.ERROR
            )
            self.stdout.write(f'  {cat:<12s} {color(str(score))}/100')

        if health['critical']:
            self.stdout.write(self.style.ERROR(f'\nCritiques : {health["critical"]}'))
        if health['warnings']:
            self.stdout.write(self.style.WARNING(f'Attentions : {health["warnings"]}'))
