from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta

from .models import PerformanceEvent


@staff_member_required
def dashboard(request):
    since = timezone.now() - timedelta(hours=24)

    # La liste est materialisee UNE fois, et les quatre indicateurs sont
    # calcules dessus.
    #
    # Avant, `events` etait tranche a 200 puis `events.filter(level='slow')`
    # etait appele dessus : Django leve « Cannot filter a query once a
    # slice has been taken », et la page n'a donc jamais pu s'afficher.
    # L'application n'etant pas declaree, personne ne l'avait jamais vue.
    #
    # Compter les lentes sur les 200 memes enregistrements, et non sur les
    # 24 heures entieres, est voulu : les trois autres chiffres portent
    # sur cet echantillon. Melanger « moyenne sur 200 requetes » et
    # « 3000 requetes lentes » donnerait deux nombres qui ne se rapportent
    # a rien de commun.
    events = list(
        PerformanceEvent.objects
        .filter(timestamp__gte=since)
        .order_by('-timestamp')[:200]
    )

    slow_count   = sum(1 for e in events if e.level == 'slow')
    avg_ms       = int(sum(e.response_ms for e in events) / len(events)) if events else 0
    max_ms       = max((e.response_ms for e in events), default=0)
    top_slow     = sorted(events, key=lambda e: e.response_ms, reverse=True)[:10]

    return render(request, 'performance_monitor/dashboard.html', {
        'page_title':  'Performance',
        'events':      events,
        'slow_count':  slow_count,
        'avg_ms':      avg_ms,
        'max_ms':      max_ms,
        'top_slow':    top_slow,
        'since':       since,
    })
