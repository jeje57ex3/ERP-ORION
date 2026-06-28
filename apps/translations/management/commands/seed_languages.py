"""
python manage.py seed_languages

Cree ou met a jour les 7 langues par defaut dans la base de donnees.
"""
from django.core.management.base import BaseCommand


LANGUAGES_DATA = [
    {'code': 'fr', 'name': 'French',     'native_name': 'Français',   'flag_icon': '🇫🇷', 'order': 1, 'is_default': True},
    {'code': 'en', 'name': 'English',    'native_name': 'English',    'flag_icon': '🇬🇧', 'order': 2},
    {'code': 'es', 'name': 'Spanish',    'native_name': 'Español',    'flag_icon': '🇪🇸', 'order': 3},
    {'code': 'de', 'name': 'German',     'native_name': 'Deutsch',    'flag_icon': '🇩🇪', 'order': 4},
    {'code': 'it', 'name': 'Italian',    'native_name': 'Italiano',   'flag_icon': '🇮🇹', 'order': 5},
    {'code': 'nl', 'name': 'Dutch',      'native_name': 'Nederlands', 'flag_icon': '🇳🇱', 'order': 6},
    {'code': 'pt', 'name': 'Portuguese', 'native_name': 'Português',  'flag_icon': '🇵🇹', 'order': 7},
]


class Command(BaseCommand):
    help = 'Cree ou met a jour les langues par defaut dans la base de donnees.'

    def handle(self, *args, **options):
        from apps.translations.models import Language

        created_count = 0
        updated_count = 0

        for data in LANGUAGES_DATA:
            lang, created = Language.objects.update_or_create(
                code=data['code'],
                defaults={
                    'name':        data['name'],
                    'native_name': data['native_name'],
                    'flag_icon':   data['flag_icon'],
                    'order':       data['order'],
                    'is_default':  data.get('is_default', False),
                    'is_active':   True,
                    'is_rtl':      False,
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f'  Creee  : {lang}')
            else:
                updated_count += 1
                self.stdout.write(f'  Mise a jour : {lang}')

        self.stdout.write(self.style.SUCCESS(
            f'\n{created_count} langue(s) creee(s), {updated_count} mise(s) a jour.'
        ))
