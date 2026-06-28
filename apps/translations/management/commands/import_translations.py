"""
python manage.py import_translations --language=en --file=translations_en.csv [--format=csv|json] [--company-id=1]

CSV attendu : key, source_text, translated_text, language, module, context
"""
import csv
import json
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Importe des traductions depuis un fichier CSV ou JSON.'

    def add_arguments(self, parser):
        parser.add_argument('--language', type=str, required=True)
        parser.add_argument('--file',     type=str, required=True)
        parser.add_argument('--format',   type=str, default='csv', choices=['csv', 'json'])
        parser.add_argument('--company-id', type=int, default=None)
        parser.add_argument('--overwrite', action='store_true', help='Ecraser les traductions existantes')

    def handle(self, *args, **options):
        from apps.translations.models import InterfaceTranslation, Language
        from apps.core.models import Company

        lang = Language.objects.filter(code=options['language']).first()
        if not lang:
            raise CommandError(f"Langue introuvable : {options['language']}. Lancez d'abord seed_languages.")

        company = None
        if options['company_id']:
            company = Company.objects.filter(pk=options['company_id']).first()
            if not company:
                raise CommandError(f"Entreprise introuvable : id={options['company_id']}")

        try:
            with open(options['file'], encoding='utf-8') as f:
                if options['format'] == 'csv':
                    rows = list(csv.DictReader(f))
                else:
                    rows = json.load(f)
        except FileNotFoundError:
            raise CommandError(f"Fichier introuvable : {options['file']}")

        created = updated = skipped = 0
        for row in rows:
            key = row.get('key', '').strip()
            if not key:
                continue
            translated = row.get('translated_text', '').strip()
            source     = row.get('source_text', key)

            obj, created_flag = InterfaceTranslation.objects.get_or_create(
                company=company, key=key, language=lang,
                defaults={
                    'source_text':     source,
                    'translated_text': translated,
                    'module':          row.get('module', ''),
                    'context':         row.get('context', ''),
                }
            )
            if created_flag:
                created += 1
            elif options['overwrite']:
                obj.translated_text = translated
                obj.source_text     = source
                obj.save(update_fields=['translated_text', 'source_text', 'updated_at'])
                updated += 1
            else:
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f'{created} creees, {updated} mises a jour, {skipped} ignorees.'
        ))
