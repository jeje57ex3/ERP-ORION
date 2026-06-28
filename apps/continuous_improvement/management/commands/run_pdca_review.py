"""Daily PDCA review: flag late cycles and send summary to stdout (or logs)."""
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.continuous_improvement.models import PDCACycle, PDCAAction
from apps.continuous_improvement.services import log_event


class Command(BaseCommand):
    help = 'Revue quotidienne PDCA : détecte les retards et génère un rapport'

    def handle(self, *args, **options):
        today = timezone.now().date()
        late_cycles = PDCACycle.objects.filter(
            status='active',
            target_date__lt=today,
        ).select_related('owner', 'company')

        overdue_actions = PDCAAction.objects.filter(
            due_date__lt=today,
            status__in=('todo', 'in_progress'),
        ).select_related('cycle', 'assigned_to')

        self.stdout.write(f'\n=== Revue PDCA — {today} ===\n')

        if late_cycles.exists():
            self.stdout.write(self.style.WARNING(f'\nCycles en retard : {late_cycles.count()}'))
            for cycle in late_cycles:
                delay = (today - cycle.target_date).days
                self.stdout.write(
                    f'  [{cycle.get_priority_display().upper()}] {cycle.title}'
                    f' — retard de {delay}j — etape {cycle.get_stage_display()}'
                    f' — responsable : {cycle.owner or "—"}'
                )
                log_event(
                    cycle, 'auto_late_flag',
                    f'Retard détecté automatiquement ({delay}j)',
                    payload={'delay_days': delay, 'check_date': str(today)},
                )
        else:
            self.stdout.write(self.style.SUCCESS('Aucun cycle en retard.'))

        if overdue_actions.exists():
            self.stdout.write(self.style.WARNING(f'\nActions en retard : {overdue_actions.count()}'))
            for action in overdue_actions:
                delay = (today - action.due_date).days
                self.stdout.write(
                    f'  {action.title} (cycle: {action.cycle.title})'
                    f' — retard {delay}j — assigné à {action.assigned_to or "—"}'
                )
        else:
            self.stdout.write(self.style.SUCCESS('\nAucune action en retard.'))

        total_active = PDCACycle.objects.filter(status='active').count()
        plan_count = PDCACycle.objects.filter(status='active', stage='plan').count()
        do_count = PDCACycle.objects.filter(status='active', stage='do').count()
        check_count = PDCACycle.objects.filter(status='active', stage='check').count()
        act_count = PDCACycle.objects.filter(status='active', stage='act').count()

        self.stdout.write(
            f'\nCycles actifs : {total_active}'
            f' (PLAN={plan_count} FAIRE={do_count} VERIFIER={check_count} AGIR={act_count})'
        )

        self.stdout.write(self.style.SUCCESS('\nRevue PDCA terminee.'))
