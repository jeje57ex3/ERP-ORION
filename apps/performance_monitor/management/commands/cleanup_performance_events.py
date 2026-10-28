from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta


class Command(BaseCommand):
    help = 'Supprime les PerformanceEvent de plus de N jours (défaut 30)'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30)

    def handle(self, *args, **options):
        from apps.performance_monitor.models import PerformanceEvent
        cutoff = timezone.now() - timedelta(days=options['days'])
        deleted, _ = PerformanceEvent.objects.filter(timestamp__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(f'{deleted} événements supprimés (antérieurs à {cutoff.date()})'))
