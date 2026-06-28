"""
Commande de démonstration : crée 5 entreprises types + utilisateurs + données
Usage : python manage.py create_demo_data
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import random


class Command(BaseCommand):
    help = 'Crée les données de démonstration ERP'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Supprimer les données existantes avant de créer')

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Création des données de démonstration ERP ===\n'))

        if options['reset']:
            self.stdout.write('Suppression des données existantes...')
            from apps.core.models import Company
            Company.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()

        # ── 1. Entreprises de démonstration ───────────────────────────────
        companies_data = [
            {
                'name': 'BTP Construction Lefèvre',
                'sector': 'btp',
                'email': 'contact@lefevre-btp.fr',
                'phone': '04 76 12 34 56',
                'address': '12 rue du Chantier',
                'city': 'Grenoble',
                'zip_code': '38000',
                'siret': '12345678901234',
                'primary_color': '#F59E0B',
                'secondary_color': '#1F2937',
                'invoice_prefix': 'FAC-BTP',
                'quote_prefix': 'DEV-BTP',
            },
            {
                'name': 'E-Shop Tendance',
                'sector': 'ecommerce',
                'email': 'hello@eshoptendance.fr',
                'phone': '01 23 45 67 89',
                'address': '45 avenue du Commerce',
                'city': 'Paris',
                'zip_code': '75008',
                'siret': '98765432109876',
                'primary_color': '#7C3AED',
                'secondary_color': '#111827',
                'invoice_prefix': 'FACT',
                'quote_prefix': 'DEVIS',
            },
            {
                'name': 'Commerce & Distribution Martin',
                'sector': 'commerce',
                'email': 'info@martin-commerce.fr',
                'phone': '05 56 78 90 12',
                'address': '8 boulevard des Capucines',
                'city': 'Bordeaux',
                'zip_code': '33000',
                'siret': '11223344556677',
                'primary_color': '#2563EB',
                'secondary_color': '#0F172A',
                'invoice_prefix': 'F',
                'quote_prefix': 'D',
            },
            {
                'name': 'Industrie & Production Rhône',
                'sector': 'production',
                'email': 'contact@industrie-rhone.fr',
                'phone': '04 72 33 44 55',
                'address': '250 avenue de l\'Industrie',
                'city': 'Lyon',
                'zip_code': '69003',
                'siret': '55667788990011',
                'primary_color': '#16A34A',
                'secondary_color': '#064E3B',
                'invoice_prefix': 'INV',
                'quote_prefix': 'QT',
            },
            {
                'name': 'SoundEvent Productions',
                'sector': 'audio',
                'email': 'booking@soundevent.fr',
                'phone': '06 11 22 33 44',
                'address': '3 rue de la Musique',
                'city': 'Marseille',
                'zip_code': '13001',
                'siret': '33445566778899',
                'primary_color': '#DB2777',
                'secondary_color': '#0F172A',
                'invoice_prefix': 'SE-F',
                'quote_prefix': 'SE-D',
            },
        ]

        from apps.core.models import Company, CompanySettings
        companies = {}

        for data in companies_data:
            company, created = Company.objects.get_or_create(
                name=data['name'],
                defaults=data
            )
            companies[data['sector']] = company
            status = 'Créée' if created else 'Existante'
            self.stdout.write(f'  {status}: {company.name} ({company.get_sector_display()})')

        # ── 2. Utilisateurs ──────────────────────────────────────────────
        self.stdout.write('\nCréation des utilisateurs...')

        users_data = [
            {'username': 'admin_btp', 'first_name': 'Pierre', 'last_name': 'Lefèvre', 'email': 'pierre@lefevre-btp.fr', 'sector': 'btp', 'role': 'admin'},
            {'username': 'admin_ecom', 'first_name': 'Sophie', 'last_name': 'Martin', 'email': 'sophie@eshoptendance.fr', 'sector': 'ecommerce', 'role': 'admin'},
            {'username': 'admin_commerce', 'first_name': 'Jean', 'last_name': 'Dupont', 'email': 'jean@martin-commerce.fr', 'sector': 'commerce', 'role': 'admin'},
            {'username': 'admin_prod', 'first_name': 'Marie', 'last_name': 'Bernard', 'email': 'marie@industrie-rhone.fr', 'sector': 'production', 'role': 'admin'},
            {'username': 'admin_audio', 'first_name': 'Lucas', 'last_name': 'Moreau', 'email': 'lucas@soundevent.fr', 'sector': 'audio', 'role': 'admin'},
            {'username': 'commercial1', 'first_name': 'Camille', 'last_name': 'Rousseau', 'email': 'camille@lefevre-btp.fr', 'sector': 'btp', 'role': 'salesperson'},
            {'username': 'technicien1', 'first_name': 'Antoine', 'last_name': 'Petit', 'email': 'antoine@soundevent.fr', 'sector': 'audio', 'role': 'technician'},
        ]

        from apps.accounts.models import UserProfile

        for user_data in users_data:
            sector = user_data.pop('sector')
            role = user_data.pop('role')

            user, created = User.objects.get_or_create(
                username=user_data['username'],
                defaults={**user_data, 'is_active': True}
            )

            if created:
                user.set_password('Demo@2024!')
                user.save()
                self.stdout.write(f'  Créé: {user.username} (mdp: Demo@2024!)')
            else:
                self.stdout.write(f'  Existant: {user.username}')

            # Assigner à l'entreprise
            if sector in companies:
                profile = user.profile
                profile.role = role
                profile.companies.add(companies[sector])
                profile.save()

        # ── 3. Clients de démonstration ──────────────────────────────────
        self.stdout.write('\nCréation des clients...')

        from apps.crm.models import Customer

        clients_demo = [
            {'company': companies.get('btp'), 'name': 'Groupe Immobilier Horizon', 'customer_type': 'company', 'city': 'Grenoble', 'email': 'horizon@test.fr'},
            {'company': companies.get('btp'), 'name': 'Marie Fontaine', 'customer_type': 'individual', 'city': 'Annecy', 'email': 'marie.f@test.fr'},
            {'company': companies.get('ecommerce'), 'name': 'Boutique En Ligne SA', 'customer_type': 'company', 'city': 'Paris', 'email': 'boutique@test.fr'},
            {'company': companies.get('commerce'), 'name': 'Restauration Dupont SARL', 'customer_type': 'company', 'city': 'Bordeaux', 'email': 'restauration@test.fr'},
            {'company': companies.get('audio'), 'name': 'Association Festivals Sud', 'customer_type': 'company', 'city': 'Aix-en-Provence', 'email': 'festivals@test.fr'},
            {'company': companies.get('audio'), 'name': 'Mairie de Marseille', 'customer_type': 'company', 'city': 'Marseille', 'email': 'mairie@test.fr'},
            {'company': companies.get('production'), 'name': 'Automotive Parts SAS', 'customer_type': 'company', 'city': 'Saint-Étienne', 'email': 'automotive@test.fr'},
        ]

        admin_user = User.objects.filter(is_superuser=True).first() or User.objects.first()

        for client_data in clients_demo:
            if client_data['company']:
                Customer.objects.get_or_create(
                    company=client_data['company'],
                    name=client_data['name'],
                    defaults={**client_data, 'is_active': True, 'created_by': admin_user}
                )

        self.stdout.write(f'  {len(clients_demo)} clients créés/vérifiés')

        # ── 4. Sites web de démonstration ────────────────────────────────
        self.stdout.write('\nCréation des sites web...')

        from apps.websites.models import WebsiteTheme, Website, WebsitePage, WebsiteSection

        themes_data = [
            {'name': 'Modern Blue', 'primary_color': '#2563EB', 'secondary_color': '#0F172A', 'accent_color': '#38BDF8', 'font_primary': 'Inter', 'is_default': True},
            {'name': 'Construction Orange', 'primary_color': '#F59E0B', 'secondary_color': '#1F2937', 'accent_color': '#FB923C', 'font_primary': 'Poppins', 'footer_bg_color': '#1F2937'},
            {'name': 'E-commerce Purple', 'primary_color': '#7C3AED', 'secondary_color': '#111827', 'accent_color': '#A78BFA', 'font_primary': 'Inter'},
            {'name': 'Nature Green', 'primary_color': '#16A34A', 'secondary_color': '#064E3B', 'accent_color': '#86EFAC', 'font_primary': 'Nunito'},
            {'name': 'Audio Neon', 'primary_color': '#DB2777', 'secondary_color': '#0F172A', 'accent_color': '#22D3EE', 'font_primary': 'Poppins', 'footer_bg_color': '#0F172A'},
            {'name': 'Luxury Dark', 'primary_color': '#D4AF37', 'secondary_color': '#111827', 'accent_color': '#FACC15', 'font_primary': 'Poppins'},
        ]

        themes = {}
        for td in themes_data:
            theme, _ = WebsiteTheme.objects.get_or_create(name=td['name'], defaults=td)
            themes[td['name']] = theme

        sites_demo = [
            {'company': companies.get('btp'), 'name': 'BTP Lefèvre Construction', 'theme': themes.get('Construction Orange'), 'contact_email': 'contact@lefevre-btp.fr', 'contact_phone': '04 76 12 34 56'},
            {'company': companies.get('ecommerce'), 'name': 'E-Shop Tendance', 'theme': themes.get('E-commerce Purple'), 'contact_email': 'hello@eshoptendance.fr'},
            {'company': companies.get('commerce'), 'name': 'Martin Distribution', 'theme': themes.get('Modern Blue'), 'contact_email': 'info@martin-commerce.fr'},
            {'company': companies.get('production'), 'name': 'Industrie Rhône', 'theme': themes.get('Nature Green'), 'contact_email': 'contact@industrie-rhone.fr'},
            {'company': companies.get('audio'), 'name': 'SoundEvent Prod', 'theme': themes.get('Audio Neon'), 'contact_email': 'booking@soundevent.fr'},
        ]

        for site_data in sites_demo:
            if site_data['company']:
                site, created = Website.objects.get_or_create(
                    company=site_data['company'],
                    name=site_data['name'],
                    defaults={**site_data, 'is_active': True, 'language': 'fr'}
                )
                if created:
                    # Créer page d'accueil
                    homepage, _ = WebsitePage.objects.get_or_create(
                        website=site,
                        page_type='home',
                        defaults={
                            'title': 'Accueil',
                            'slug': 'accueil',
                            'status': 'published',
                            'is_homepage': True,
                            'order': 0,
                        }
                    )
                    # Section héro
                    WebsiteSection.objects.get_or_create(
                        page=homepage,
                        section_type='hero',
                        defaults={
                            'title': f'Bienvenue chez {site_data["company"].name}',
                            'subtitle': 'Votre partenaire de confiance pour tous vos projets.',
                            'button_text': 'Découvrir nos services',
                            'button_link': '#services',
                            'button_secondary_text': 'Demander un devis',
                            'button_secondary_link': f'/sites/{site_data["company"].slug}/devis/',
                            'order': 0,
                        }
                    )

        self.stdout.write(f'  {len(sites_demo)} sites web créés/vérifiés')

        # ── 5. Résumé ─────────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS(
            '\n'
            '========================================================\n'
            '  DONNEES DE DEMONSTRATION CREEES !\n'
            '========================================================\n'
            '  5 entreprises sectorielles\n'
            '  7 utilisateurs (mdp: Demo@2024!)\n'
            '  Clients, sites web, themes\n'
            '--------------------------------------------------------\n'
            '  Connexion : http://localhost:8000/accounts/login/\n'
            '  Admin :     http://localhost:8000/admin/\n'
            '  Comptes :   admin_btp / Demo@2024!\n'
            '              admin_ecom / Demo@2024!\n'
            '              admin_audio / Demo@2024!\n'
            '========================================================\n'
        ))
