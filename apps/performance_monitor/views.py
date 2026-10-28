from apps.private_saas.decorators import super_admin_required
from django.shortcuts import render
from django.utils import timezone
from datetime import timedelta

from .models import PerformanceEvent


@super_admin_required
def dashboard(request):
    """Mesures de performance de l'installation.

    Garde alignee sur celle de ses VOISINES dans le menu Super Admin.

    Elle employait `staff_member_required`, et c'etait un piege a deux
    detentes. D'abord il exige `is_staff` quand toutes les autres pages de
    ce menu exigent `is_superuser` : un super-administrateur sans le drapeau
    « equipe » voyait cette page seule lui resister. Ensuite, en cas de
    refus, il redirige vers `admin:login` -- la page de connexion de l'admin
    Django -- au lieu de ramener au tableau de bord avec un message. D'ou
    l'impression d'une page cassee plutot que d'un acces refuse.

    Ces mesures portent sur l'infrastructure entiere et non sur une
    entreprise : le perimetre super-administrateur est le bon.
    """
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
