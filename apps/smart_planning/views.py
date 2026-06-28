from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import PlanningEvent
from .services import get_events_for_period, get_conflicts, get_planning_stats


@login_required
def planning_view(request):
    company = request.current_company
    if not company:
        return redirect('core:dashboard')
    today = timezone.now().date()
    from datetime import timedelta
    end = today + timedelta(days=30)
    events = get_events_for_period(company, today, end)
    conflicts = get_conflicts(company)[:10]
    stats = get_planning_stats(company)
    return render(request, 'smart_planning/planning.html', {
        'page_title': 'Planning intelligent',
        'events': events, 'conflicts': conflicts, 'stats': stats,
        'today': today,
    })


@login_required
def event_detail(request, pk):
    company = request.current_company
    event = get_object_or_404(PlanningEvent, pk=pk, company=company)
    return render(request, 'smart_planning/event_detail.html', {
        'page_title': event.title, 'event': event,
    })
