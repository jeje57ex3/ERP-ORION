from django.core.management.base import BaseCommand

from apps.core.models import Company
from apps.domain_diagnostics.models import DomainDiagnosticTarget
from apps.domain_diagnostics.services import run_domain_diagnostic


class Command(BaseCommand):
    help = "Lance le diagnostic de domaine sur toutes les cibles actives (ou une seule si --domain est fourni)."

    def add_arguments(self, parser):
        parser.add_argument('--domain', type=str, help='Domaine spécifique à scanner.')
        parser.add_argument('--company', type=str, help='Slug ou ID de l\'entreprise.')

    def handle(self, *args, **options):
        qs = DomainDiagnosticTarget.objects.filter(is_active=True).select_related(
            'company', 'website', 'cloudflare_zone'
        )

        if options['domain']:
            qs = qs.filter(domain=options['domain'])

        if options['company']:
            ident = options['company']
            try:
                company = Company.objects.get(slug=ident)
            except (Company.DoesNotExist, ValueError):
                try:
                    company = Company.objects.get(pk=int(ident))
                except (Company.DoesNotExist, ValueError):
                    self.stderr.write(self.style.ERROR(f'Entreprise introuvable : {ident}'))
                    return
            qs = qs.filter(company=company)

        targets = list(qs)
        if not targets:
            self.stdout.write('Aucune cible active trouvée.')
            return

        for target in targets:
            self.stdout.write(f'→ Scan de {target.domain} …', ending=' ')
            try:
                run = run_domain_diagnostic(target)
                icon = {'ok': '✓', 'warning': '⚠', 'error': '✗'}.get(run.status, '?')
                self.stdout.write(self.style.SUCCESS(f'{icon} {run.status} — {run.summary}'))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f'ERREUR : {exc}'))
