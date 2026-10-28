"""
python manage.py check_siecle_orders

Affiche un résumé des commandes SIÈCLE par statut et paiement.
Utile pour détecter des commandes bloquées (ex: paiement paid mais statut pending).
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Sum

from apps.websites.models import StoreOrder, Website


class Command(BaseCommand):
    help = 'Vérifie les commandes SIÈCLE et affiche un résumé par statut/paiement'

    def add_arguments(self, parser):
        parser.add_argument(
            '--fix-stuck',
            action='store_true',
            help='Passe en "confirmed" les commandes payées qui sont encore en "pending"',
        )

    def handle(self, *args, **options):
        siecle_sites = Website.objects.filter(
            slug='siecle', site_type='ecommerce', is_active=True,
        )

        if not siecle_sites.exists():
            self.stderr.write(self.style.WARNING('Aucun site SIÈCLE actif trouvé.'))
            return

        qs = StoreOrder.objects.filter(website__in=siecle_sites)
        total = qs.count()
        self.stdout.write(self.style.SUCCESS(f'\n=== Commandes SIÈCLE — {total} au total ===\n'))

        # Résumé par statut
        self.stdout.write('Par statut :')
        for row in qs.values('status').annotate(n=Count('id'), revenue=Sum('grand_total')).order_by('-n'):
            label = dict(StoreOrder.STATUS_CHOICES).get(row['status'], row['status'])
            revenue = row['revenue'] or 0
            self.stdout.write(f"  {label:<22} {row['n']:>4} commandes  {revenue:>10.2f} €")

        self.stdout.write('\nPar paiement :')
        for row in qs.values('payment_status').annotate(n=Count('id')).order_by('-n'):
            label = dict(StoreOrder.PAYMENT_STATUS_CHOICES).get(row['payment_status'], row['payment_status'])
            self.stdout.write(f"  {label:<22} {row['n']:>4} commandes")

        # Commandes potentiellement bloquées
        stuck = qs.filter(payment_status='paid', status='pending')
        if stuck.exists():
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                f'⚠  {stuck.count()} commande(s) payée(s) encore en statut "pending" :'
            ))
            for o in stuck[:10]:
                self.stdout.write(f'   #{o.order_number} — {o.customer_name} — {o.grand_total} €')

            if options['fix_stuck']:
                updated = stuck.update(status='confirmed')
                self.stdout.write(self.style.SUCCESS(f'  → {updated} commandes passées en "confirmed".'))
            else:
                self.stdout.write('   Relancez avec --fix-stuck pour les corriger automatiquement.')

        self.stdout.write('')
