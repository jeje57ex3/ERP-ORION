"""
python manage.py sync_missing_translations [--language=en] [--create]

Scanne les cles importantes, detecte les traductions manquantes,
affiche un rapport et cree les entrees si --create est passe.
"""
from django.core.management.base import BaseCommand

IMPORTANT_KEYS = [
    # Dashboard
    ('dashboard', 'dashboard.title',           'Tableau de bord'),
    ('dashboard', 'dashboard.welcome',         'Bienvenue'),
    # CRM
    ('crm',       'crm.clients',               'Clients'),
    ('crm',       'crm.prospects',             'Prospects'),
    ('crm',       'crm.contacts',              'Contacts'),
    ('crm',       'crm.opportunities',         'Opportunites'),
    # Ventes
    ('sales',     'sales.quotes',              'Devis'),
    ('sales',     'sales.orders',              'Commandes'),
    ('sales',     'sales.invoices',            'Factures'),
    ('sales',     'sales.quote.draft',         'Brouillon'),
    ('sales',     'sales.quote.sent',          'Envoye'),
    ('sales',     'sales.quote.accepted',      'Accepte'),
    ('sales',     'sales.quote.refused',       'Refuse'),
    ('sales',     'sales.quote.expired',       'Expire'),
    ('sales',     'sales.invoice.draft',       'Brouillon'),
    ('sales',     'sales.invoice.sent',        'Envoyee'),
    ('sales',     'sales.invoice.paid',        'Payee'),
    ('sales',     'sales.invoice.overdue',     'En retard'),
    ('sales',     'sales.invoice.cancelled',   'Annulee'),
    # BTP
    ('btp',       'btp.projects',              'Chantiers'),
    ('btp',       'btp.project.planned',       'Prevu'),
    ('btp',       'btp.project.in_progress',   'En cours'),
    ('btp',       'btp.project.suspended',     'Suspendu'),
    ('btp',       'btp.project.completed',     'Termine'),
    ('btp',       'btp.project.closed',        'Cloture'),
    # Portail client
    ('portal',    'client_portal.login_title', 'Espace client'),
    ('portal',    'client_portal.login',       'Se connecter'),
    ('portal',    'client_portal.logout',      'Deconnexion'),
    ('portal',    'client_portal.my_quotes',   'Mes devis'),
    ('portal',    'client_portal.my_invoices', 'Mes factures'),
    ('portal',    'client_portal.my_projects', 'Mes chantiers'),
    ('portal',    'client_portal.my_docs',     'Mes documents'),
    # Site web
    ('website',   'website.quote_button',      'Demander un devis'),
    ('website',   'website.contact',           'Contact'),
    ('website',   'website.services',          'Nos services'),
    # Documents
    ('documents', 'documents.title',           'Documents'),
    ('documents', 'documents.download',        'Telecharger'),
    ('documents', 'documents.share',           'Partager'),
]


class Command(BaseCommand):
    help = 'Detecte les traductions manquantes et affiche un rapport.'

    def add_arguments(self, parser):
        parser.add_argument('--language', type=str, default='',
                            help='Code langue a verifier (vide = toutes les langues actives)')
        parser.add_argument('--create', action='store_true',
                            help='Creer les entrees manquantes avec le texte source comme traduction provisoire')

    def handle(self, *args, **options):
        from apps.translations.models import Language, InterfaceTranslation

        if options['language']:
            languages = Language.objects.filter(code=options['language'], is_active=True)
        else:
            languages = Language.objects.filter(is_active=True)

        if not languages.exists():
            self.stdout.write(self.style.WARNING('Aucune langue active. Lancez d\'abord seed_languages.'))
            return

        total_missing = 0

        for lang in languages:
            if lang.is_default:
                continue  # pas besoin de traduire la langue source

            existing_keys = set(
                InterfaceTranslation.objects.filter(language=lang).values_list('key', flat=True)
            )
            missing = [(mod, key, src) for mod, key, src in IMPORTANT_KEYS if key not in existing_keys]

            self.stdout.write(f'\n[{lang.code}] {lang.native_name} — {len(missing)} cle(s) manquante(s) sur {len(IMPORTANT_KEYS)}')

            for mod, key, src in missing:
                self.stdout.write(f'  MANQUANT  [{mod}]  {key}  =  "{src}"')
                if options['create']:
                    InterfaceTranslation.objects.get_or_create(
                        company=None, key=key, language=lang,
                        defaults={
                            'source_text':     src,
                            'translated_text': src,  # provisoire
                            'module':          mod,
                            'is_verified':     False,
                        }
                    )

            total_missing += len(missing)

        action = 'creees' if options['create'] else 'detectees'
        self.stdout.write(self.style.SUCCESS(f'\nTotal : {total_missing} traductions manquantes {action}.'))
