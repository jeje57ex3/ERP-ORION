"""
python manage.py sync_siecle_products --company-id=1

Synchronise les stocks des produits ERP vers les produits SIECLE boutique.
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Synchronise les stocks ERP vers les produits SIECLE.'

    def add_arguments(self, parser):
        parser.add_argument('--company-id', type=int, required=True)
        parser.add_argument('--dry-run', action='store_true', help='Afficher sans modifier')

    def handle(self, *args, **options):
        from apps.core.models import Company
        from apps.websites.models import Website, StoreProduct

        try:
            company = Company.objects.get(pk=options['company_id'])
        except Company.DoesNotExist:
            raise CommandError(f"Entreprise introuvable : id={options['company_id']}")

        site = Website.objects.filter(company=company, site_type='ecommerce', slug='siecle').first()
        if not site:
            raise CommandError("Site SIECLE introuvable.")

        products = StoreProduct.objects.filter(website=site, stock_from_erp=True).select_related('erp_product')
        synced = 0

        for product in products:
            if not product.erp_product:
                continue
            erp_stock = getattr(product.erp_product, 'stock_quantity', None)
            if erp_stock is None:
                continue
            self.stdout.write(f'  {product.name} : {product.stock_quantity} → {erp_stock}')
            if not options['dry_run']:
                product.stock_quantity = erp_stock
                product.status = 'published' if erp_stock > 0 else 'out_of_stock'
                product.save(update_fields=['stock_quantity', 'status', 'updated_at'])
                synced += 1

        suffix = ' (dry-run)' if options['dry_run'] else ''
        self.stdout.write(self.style.SUCCESS(f'{synced} produit(s) synchronise(s){suffix}.'))
