"""
Commande pour créer les thèmes de sites web par défaut.
"""
from django.core.management.base import BaseCommand
from apps.websites.models import WebsiteTheme


THEMES = [
    {
        'name': 'Orion Luxury',
        'primary_color': '#3A2A1A',
        'secondary_color': '#C6A15B',
        'accent_color': '#D4A853',
        'background_color': '#F8F3EA',
        'text_color': '#1A1208',
        'button_color': '#C6A15B',
        'header_bg_color': '#3A2A1A',
        'footer_bg_color': '#1A1208',
        'footer_text_color': '#C6A15B',
        'font_primary': 'Montserrat',
        'font_secondary': 'Raleway',
        'button_style': 'pill',
        'border_radius': '0.5rem',
        'mode': 'light',
        'is_default': True,
    },
    {
        'name': 'BTP Pro',
        'primary_color': '#EA580C',
        'secondary_color': '#1C1917',
        'accent_color': '#F97316',
        'background_color': '#FAFAF9',
        'text_color': '#1C1917',
        'button_color': '#EA580C',
        'header_bg_color': '#1C1917',
        'footer_bg_color': '#1C1917',
        'footer_text_color': '#E7E5E4',
        'font_primary': 'Roboto',
        'font_secondary': 'Open Sans',
        'button_style': 'square',
        'border_radius': '0.25rem',
        'mode': 'light',
        'is_default': False,
    },
    {
        'name': 'Électricité Moderne',
        'primary_color': '#EAB308',
        'secondary_color': '#1E3A5F',
        'accent_color': '#FBBF24',
        'background_color': '#FFFFFF',
        'text_color': '#0F172A',
        'button_color': '#EAB308',
        'header_bg_color': '#1E3A5F',
        'footer_bg_color': '#0F172A',
        'footer_text_color': '#E2E8F0',
        'font_primary': 'Inter',
        'font_secondary': 'Poppins',
        'button_style': 'rounded',
        'border_radius': '0.375rem',
        'mode': 'light',
        'is_default': False,
    },
    {
        'name': 'E-commerce Clean',
        'primary_color': '#7C3AED',
        'secondary_color': '#F1F5F9',
        'accent_color': '#A855F7',
        'background_color': '#FFFFFF',
        'text_color': '#111827',
        'button_color': '#7C3AED',
        'header_bg_color': '#FFFFFF',
        'footer_bg_color': '#1E293B',
        'footer_text_color': '#CBD5E1',
        'font_primary': 'Inter',
        'font_secondary': 'Nunito',
        'button_style': 'rounded',
        'border_radius': '0.5rem',
        'mode': 'light',
        'is_default': False,
    },
    {
        'name': 'Audio Dark',
        'primary_color': '#EC4899',
        'secondary_color': '#0EA5E9',
        'accent_color': '#06B6D4',
        'background_color': '#0A0A0A',
        'text_color': '#F9FAFB',
        'button_color': '#EC4899',
        'header_bg_color': '#111111',
        'footer_bg_color': '#111111',
        'footer_text_color': '#9CA3AF',
        'font_primary': 'Montserrat',
        'font_secondary': 'Inter',
        'button_style': 'pill',
        'border_radius': '9999px',
        'mode': 'dark',
        'is_default': False,
    },
    {
        'name': 'Industrie Pro',
        'primary_color': '#2563EB',
        'secondary_color': '#475569',
        'accent_color': '#3B82F6',
        'background_color': '#F8FAFC',
        'text_color': '#0F172A',
        'button_color': '#2563EB',
        'header_bg_color': '#0F172A',
        'footer_bg_color': '#0F172A',
        'footer_text_color': '#94A3B8',
        'font_primary': 'Inter',
        'font_secondary': 'Roboto',
        'button_style': 'square',
        'border_radius': '0.25rem',
        'mode': 'light',
        'is_default': False,
    },
    {
        'name': 'Commerce Premium',
        'primary_color': '#DC2626',
        'secondary_color': '#F59E0B',
        'accent_color': '#EF4444',
        'background_color': '#FFFFFF',
        'text_color': '#111827',
        'button_color': '#DC2626',
        'header_bg_color': '#FFFFFF',
        'footer_bg_color': '#111827',
        'footer_text_color': '#D1D5DB',
        'font_primary': 'Lato',
        'font_secondary': 'Poppins',
        'button_style': 'rounded',
        'border_radius': '0.375rem',
        'mode': 'light',
        'is_default': False,
    },
    {
        'name': 'Minimal Light',
        'primary_color': '#111827',
        'secondary_color': '#6B7280',
        'accent_color': '#374151',
        'background_color': '#FFFFFF',
        'text_color': '#111827',
        'button_color': '#111827',
        'header_bg_color': '#FFFFFF',
        'footer_bg_color': '#111827',
        'footer_text_color': '#9CA3AF',
        'font_primary': 'Inter',
        'font_secondary': 'Inter',
        'button_style': 'square',
        'border_radius': '0.25rem',
        'mode': 'light',
        'is_default': False,
    },
]


class Command(BaseCommand):
    help = 'Crée les thèmes de sites web par défaut (sans entreprise associée).'

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for theme_data in THEMES:
            obj, was_created = WebsiteTheme.objects.update_or_create(
                name=theme_data['name'],
                company=None,
                defaults=theme_data,
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'  [OK] Theme cree : {obj.name}'))
            else:
                updated += 1
                self.stdout.write(f'  [MAJ] Theme mis a jour : {obj.name}')
        self.stdout.write(self.style.SUCCESS(
            f'\n{created} thème(s) créé(s), {updated} mis à jour.'
        ))
