"""Recherche globale dans les données de l'entreprise active.

Filtrage par entreprise, explicitement. L'isolation ne peut pas être laissée
au routeur de base : celui-ci n'aiguille vers une base dédiée que les
entreprises dont `database_created` est vrai. Les autres partagent la base
`default`, et une requête sans filtre y verrait les clients, devis et
chantiers des entreprises voisines. Le filtre explicite est correct dans les
deux topologies, et c'est le même que celui employé partout ailleurs dans
l'ERP, la clé étrangère `company`.

Les échecs sont journalisés et non avalés. La version précédente enveloppait
chaque recherche dans un `except Exception: return []`, ce qui a masqué un
défaut pendant tout ce temps : `_search_btp` importait `apps.btp.models.Project`,
un modèle qui n'existe pas — il s'appelle `BTPProject`. Les chantiers étaient
donc introuvables, sans que rien ne le signale.
"""

import logging

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render

logger = logging.getLogger(__name__)

RESULT_LIMIT = 5


def _entreprise_active(request):
    return getattr(request, 'current_company', None)


def _collecter(nom_source, fonction, q, company, user):
    """Exécute une recherche en journalisant son échec plutôt qu'en l'ignorant.

    Un module absent est normal — tous les modules ne sont pas installés
    partout — mais une erreur de requête ou de nom de modèle doit laisser une
    trace, sinon la recherche devient silencieusement incomplète.
    """
    try:
        return fonction(q, company, user)
    except ImportError:
        return []
    except Exception as exc:
        logger.warning('Recherche globale — source « %s » en échec : %s', nom_source, exc)
        return []


def _search_crm(q, company, user=None):
    from apps.crm.models import Customer

    return [
        {
            'type': 'client', 'label': 'Client',
            'icon': 'bi-person', 'color': 'primary',
            'url': f'/crm/clients/{c.pk}/',
            'title': c.name,
            'subtitle': c.email or '',
        }
        for c in Customer.objects.filter(
            Q(company=company),
            Q(name__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q),
        )[:RESULT_LIMIT]
    ]


def _search_sales(q, company, user=None):
    from apps.sales.models import Invoice, Quote

    results = []
    for inv in Invoice.objects.filter(
        Q(company=company),
        Q(number__icontains=q) | Q(subject__icontains=q),
    )[:RESULT_LIMIT]:
        results.append({
            'type': 'facture', 'label': 'Facture',
            'icon': 'bi-receipt', 'color': 'success',
            'url': f'/sales/factures/{inv.pk}/',
            'title': inv.number,
            'subtitle': inv.subject or '',
        })
    for quote in Quote.objects.filter(
        Q(company=company),
        Q(number__icontains=q) | Q(subject__icontains=q),
    )[:RESULT_LIMIT]:
        results.append({
            'type': 'devis', 'label': 'Devis',
            'icon': 'bi-file-earmark-text', 'color': 'warning',
            'url': f'/sales/devis/{quote.pk}/',
            'title': quote.number,
            'subtitle': quote.subject or '',
        })
    return results


def _search_btp(q, company, user=None):
    # BTPProject, et non Project : ce dernier n'existe pas, et l'import ratait
    # en silence derriere un except trop large.
    from apps.btp.models import BTPProject

    return [
        {
            'type': 'chantier', 'label': 'Chantier',
            'icon': 'bi-building-gear', 'color': 'info',
            'url': f'/btp/chantiers/{p.pk}/',
            'title': p.name,
            'subtitle': p.code or '',
        }
        for p in BTPProject.objects.filter(
            Q(company=company),
            Q(name__icontains=q) | Q(code__icontains=q),
        )[:RESULT_LIMIT]
    ]


def _search_inventory(q, company, user=None):
    from apps.inventory.models import Product

    return [
        {
            'type': 'produit', 'label': 'Produit',
            'icon': 'bi-box-seam', 'color': 'secondary',
            'url': f'/inventory/produits/{p.pk}/',
            'title': p.name,
            'subtitle': p.reference or '',
        }
        for p in Product.objects.filter(
            Q(company=company),
            Q(name__icontains=q) | Q(reference__icontains=q),
        )[:RESULT_LIMIT]
    ]


def _search_pages(q, company, user=None):
    """Pages de l'interface, et non seulement les donnees metier.

    La recherche ne couvrait que clients, devis, factures, chantiers et
    produits. Chercher « disques », « sauvegarde » ou « parametres IA » ne
    renvoyait donc rien -- alors que ce sont des demandes au moins aussi
    frequentes que la recherche d'un client.

    L'index reutilise celui construit pour Orion : les libelles viennent du
    menu affiche, les adresses du resolveur d'URL, et le tout est filtre par
    les permissions de l'utilisateur. Une page qu'il ne peut pas ouvrir ne lui
    est donc pas proposee.
    """
    from apps.orion_ai.knowledge import chercher_pages

    return [
        {
            'type': 'page', 'label': 'Page',
            'icon': 'bi-window-stack', 'color': 'dark',
            'url': page['url'],
            'title': page['libelle'],
            'subtitle': page['module'],
        }
        for page in chercher_pages(q, user=user, company=company)
    ]


SOURCES = (
    ('pages', _search_pages),
    ('crm', _search_crm),
    ('ventes', _search_sales),
    ('btp', _search_btp),
    ('stock', _search_inventory),
)


def chercher(q, company, user=None):
    """Résultats de toutes les sources.

    Une entreprise active est exigée pour les données métier, mais PAS pour
    les pages : un utilisateur sans entreprise résolue doit tout de même
    pouvoir retrouver une page de l'interface, sinon la recherche lui est
    entièrement inutile.
    """
    if len(q) < 2:
        return []

    resultats = []
    for nom, fonction in SOURCES:
        if nom != 'pages' and company is None:
            continue
        resultats += _collecter(nom, fonction, q, company, user)
    return resultats


@login_required
def global_search(request):
    """Recherche globale, en JSON pour la palette et en HTML pour la page.

    La palette de commandes appelle cette vue avec `format=json`. La version
    précédente rendait TOUJOURS le gabarit HTML : la palette recevait donc du
    HTML, `response.json()` échouait, et l'utilisateur voyait un champ qui ne
    répondait jamais. Le gabarit, de son côté, interrogeait « /search/ » en
    dur alors que cette vue est montée sous « /dashboard/search/ » — deux
    défauts superposés, chacun suffisant à tout casser.
    """
    q = request.GET.get('q', '').strip()
    company = _entreprise_active(request)
    results = chercher(q, company, user=request.user)

    veut_json = (
        request.GET.get('format') == 'json'
        or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    )

    if veut_json:
        return JsonResponse({
            'query': q,
            'count': len(results),
            'results': results,
        })

    return render(request, 'core/search_results.html', {
        'query': q,
        'results': results,
        'result_count': len(results),
        'page_title': f'Recherche : {q}' if q else 'Recherche globale',
        'active_module': 'dashboard',
    })
