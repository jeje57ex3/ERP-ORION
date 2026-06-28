"""
python manage.py export_translations --language=en [--format=csv|json] [--module=crm] [--output=file.csv]
"""
import csv
import json
import sys
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Exporte les traductions InterfaceTranslation vers CSV ou JSON.'

    def add_arguments(self, parser):
        parser.add_argument('--language', type=str, required=True, help='Code langue (fr, en, es...)')
        parser.add_argument('--format', type=str, default='csv', choices=['csv', 'json'], help='Format de sortie')
        parser.add_argument('--module', type=str, default='', help='Filtrer par module')
        parser.add_argument('--output', type=str, default='', help='Fichier de sortie (defaut: stdout)')

    def handle(self, *args, **options):
        from apps.translations.models import InterfaceTranslation

        qs = InterfaceTranslation.objects.filter(language__code=options['language']).select_related('language', 'company')
        if options['module']:
            qs = qs.filter(module=options['module'])

        rows = [
            {
                'key':             t.key,
                'source_text':     t.source_text,
                'translated_text': t.translated_text,
                'language':        t.language.code,
                'module':          t.module,
                'context':         t.context,
                'is_verified':     t.is_verified,
            }
            for t in qs
        ]

        output = options['output']
        fout = open(output, 'w', newline='', encoding='utf-8') if output else sys.stdout

        try:
            if options['format'] == 'csv':
                writer = csv.DictWriter(fout, fieldnames=['key', 'source_text', 'translated_text', 'language', 'module', 'context', 'is_verified'])
                writer.writeheader()
                writer.writerows(rows)
            else:
                json.dump(rows, fout, ensure_ascii=False, indent=2)
        finally:
            if output:
                fout.close()

        self.stdout.write(self.style.SUCCESS(f'{len(rows)} traductions exportees [{options["language"]}].'))
