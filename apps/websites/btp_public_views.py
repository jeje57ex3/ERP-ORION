"""
apps/websites/btp_public_views.py — Vues publiques du site BTP
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.contrib import messages as django_messages
from django.utils import timezone

from .models import (
    Website, BlogPost, BTPPortfolioProject, BTPWebsiteReview,
    BTPClientAccessRequest, BTPEmergencyRequest,
)
from .public_views import _get_site, _base_context, _get_ip, _create_crm_lead


WORK_CATEGORIES = [
    {'icon': 'bi-lightning-charge',    'name': 'Électricité',         'desc': 'Installation, mise aux normes, dépannage électrique.'},
    {'icon': 'bi-droplet-fill',        'name': 'Plomberie',           'desc': 'Canalisations, sanitaires, fuite d\'eau, chauffe-eau.'},
    {'icon': 'bi-thermometer-half',    'name': 'Chauffage',           'desc': 'Chaudière, pompe à chaleur, radiateurs, plancher chauffant.'},
    {'icon': 'bi-brush',               'name': 'Peinture',            'desc': 'Enduits, peintures intérieur / extérieur.'},
    {'icon': 'bi-bricks',              'name': 'Maçonnerie',          'desc': 'Gros œuvre, dalle, fondations, mur.'},
    {'icon': 'bi-door-open',           'name': 'Menuiserie',          'desc': 'Fenêtres, portes, parquet, agencement bois.'},
    {'icon': 'bi-house-check',         'name': 'Isolation',           'desc': 'Combles, murs, façade — amélioration énergétique.'},
    {'icon': 'bi-building',            'name': 'Toiture',             'desc': 'Couverture, zinguerie, entretien toiture.'},
    {'icon': 'bi-grid-3x3-gap',        'name': 'Revêtement sol',      'desc': 'Carrelage, parquet, stratifié, moquette.'},
    {'icon': 'bi-droplet-half',        'name': 'Salle de bain',       'desc': 'Rénovation complète, douche, baignoire, WC.'},
    {'icon': 'bi-egg-fried',           'name': 'Cuisine',             'desc': 'Pose de cuisine équipée, plan de travail, électroménager.'},
    {'icon': 'bi-house-gear',          'name': 'Rénovation complète', 'desc': 'Coordination de tous les corps de métier.'},
    {'icon': 'bi-arrows-expand',       'name': 'Extension',           'desc': 'Agrandissement, véranda, surélévation.'},
]

EMERGENCY_TYPES = [
    'Panne électrique',
    'Fuite d\'eau',
    'Chauffage en panne',
    'Porte / serrure bloquée',
    'Dégât des eaux',
    'Dégât bâtiment',
]


def _get_btp_site(site_slug):
    site = Website.objects.filter(
        company__slug=site_slug, is_active=True, site_type='btp'
    ).first()
    if site is None:
        # Fallback : any active site for this company
        site = Website.objects.filter(company__slug=site_slug, is_active=True).first()
    if site is None:
        raise Http404
    return site


def _btp_context(site):
    ctx = _base_context(site)
    ctx.update({
        'btp_portfolio': site.btp_portfolio_projects.filter(is_published=True).order_by('order')[:6],
        'btp_reviews':   site.btp_reviews.filter(is_published=True).order_by('order')[:6],
    })
    return ctx


def btp_home(request, site_slug):
    site = _get_btp_site(site_slug)
    ctx  = _btp_context(site)
    ctx.update({
        'featured_services': site.services.filter(is_active=True).order_by('order')[:6],
        'page_title': site.meta_title or f'{site.company.name} — Entreprise BTP',
    })
    return render(request, 'websites/public/btp/home.html', ctx)


def btp_services(request, site_slug):
    site = _get_btp_site(site_slug)
    ctx  = _btp_context(site)
    ctx.update({
        'featured_services': site.services.filter(is_active=True).order_by('order'),
        'default_services':  WORK_CATEGORIES[:6],
        'page_title': 'Nos services',
    })
    return render(request, 'websites/public/btp/services.html', ctx)


def btp_works(request, site_slug):
    site = _get_btp_site(site_slug)
    ctx  = _btp_context(site)
    ctx.update({'work_categories': WORK_CATEGORIES, 'page_title': 'Types de travaux'})
    return render(request, 'websites/public/btp/works.html', ctx)


def btp_portfolio(request, site_slug):
    site = _get_btp_site(site_slug)
    ctx  = _btp_context(site)

    work_type_filter = request.GET.get('type', '')
    qs = site.btp_portfolio_projects.filter(is_published=True).order_by('order', '-created_at')
    if work_type_filter and work_type_filter != 'all':
        qs = qs.filter(work_type=work_type_filter)

    ctx.update({
        'portfolio_projects': qs,
        'work_types':        BTPPortfolioProject.WORK_TYPES,
        'work_type_filter':  work_type_filter,
        'page_title': 'Nos réalisations',
    })
    return render(request, 'websites/public/btp/portfolio.html', ctx)


def btp_reviews(request, site_slug):
    site    = _get_btp_site(site_slug)
    ctx     = _btp_context(site)
    reviews = site.btp_reviews.filter(is_published=True).order_by('order', '-created_at')

    avg_rating = None
    if reviews.exists():
        total = sum(r.rating for r in reviews)
        avg_rating = total / reviews.count()

    ctx.update({'reviews': reviews, 'avg_rating': avg_rating, 'page_title': 'Avis clients'})
    return render(request, 'websites/public/btp/reviews.html', ctx)


def btp_emergency(request, site_slug):
    site = _get_btp_site(site_slug)
    ctx  = _btp_context(site)
    ctx.update({'emergency_types': EMERGENCY_TYPES, 'page_title': 'Dépannage urgent'})

    if request.method == 'POST':
        honeypot = request.POST.get('website_url_field', '')
        if honeypot:
            return render(request, 'websites/public/btp/emergency.html', ctx)

        em = BTPEmergencyRequest(
            website       = site,
            first_name    = request.POST.get('first_name', '').strip()[:100],
            last_name     = request.POST.get('last_name', '').strip()[:100],
            phone         = request.POST.get('phone', '').strip()[:20],
            email         = request.POST.get('email', '').strip()[:254],
            emergency_type= request.POST.get('emergency_type', 'autre'),
            address       = request.POST.get('address', '').strip()[:300],
            description   = request.POST.get('description', '').strip(),
            wants_callback= bool(request.POST.get('wants_callback')),
            ip_address    = _get_ip(request),
        )
        if request.FILES.get('photo'):
            em.photo = request.FILES['photo']
        em.save()

        # Créer un GuidedQuoteRequest urgence + notifications ERP
        _handle_emergency_erp(site, em)

        ctx['success'] = True
        return render(request, 'websites/public/btp/emergency.html', ctx)

    return render(request, 'websites/public/btp/emergency.html', ctx)


def btp_contact(request, site_slug):
    site = _get_btp_site(site_slug)
    ctx  = _btp_context(site)
    ctx['page_title'] = 'Contact'

    if request.method == 'POST':
        honeypot = request.POST.get('website_url_field', '')
        if not honeypot:
            from .models import ContactMessage
            msg = ContactMessage(
                website    = site,
                name       = request.POST.get('name', '').strip()[:200],
                email      = request.POST.get('email', '').strip()[:254],
                phone      = request.POST.get('phone', '').strip()[:20],
                subject    = request.POST.get('subject', '').strip()[:200],
                message    = request.POST.get('message', '').strip(),
                ip_address = _get_ip(request),
            )
            msg.save()
            _notify_erp(site, f'Nouveau message de {msg.name}', msg.message[:200],
                        'Nouveau message contact', 'website_contact')
            ctx['success'] = True

    return render(request, 'websites/public/btp/contact.html', ctx)


def btp_client_access(request, site_slug):
    site = _get_btp_site(site_slug)
    ctx  = _btp_context(site)
    ctx['page_title'] = 'Espace client'

    if request.method == 'POST':
        honeypot = request.POST.get('website_url_field', '')
        if not honeypot and request.POST.get('form_type') == 'access_request':
            access = BTPClientAccessRequest(
                website      = site,
                first_name   = request.POST.get('first_name', '').strip()[:100],
                last_name    = request.POST.get('last_name', '').strip()[:100],
                email        = request.POST.get('email', '').strip()[:254],
                phone        = request.POST.get('phone', '').strip()[:20],
                company_name = request.POST.get('company_name', '').strip()[:200],
                message      = request.POST.get('message', '').strip(),
                reference    = request.POST.get('reference', '').strip()[:100],
                ip_address   = _get_ip(request),
            )
            access.save()
            _notify_erp(
                site,
                f"Demande d'accès portail — {access.first_name} {access.last_name}",
                f"Email : {access.email}  |  Réf : {access.reference or 'non renseignée'}",
                "Demande accès espace client",
                'client_access_request',
            )
            ctx['access_success'] = True

    return render(request, 'websites/public/btp/client_access.html', ctx)


def btp_blog(request, site_slug):
    site       = _get_btp_site(site_slug)
    ctx        = _btp_context(site)
    posts      = site.blog_posts.filter(status='published').order_by('-published_at')
    categories = site.blog_categories.all()

    current_category = request.GET.get('category', '')
    if current_category:
        posts = posts.filter(category__slug=current_category)

    ctx.update({'posts': posts, 'categories': categories,
                'current_category': current_category, 'page_title': 'Blog'})
    return render(request, 'websites/public/btp/blog_list.html', ctx)


def btp_blog_detail(request, site_slug, post_slug):
    site = _get_btp_site(site_slug)
    post = get_object_or_404(BlogPost, website=site, slug=post_slug, status='published')
    related = site.blog_posts.filter(
        status='published', category=post.category
    ).exclude(pk=post.pk).order_by('-published_at')[:3]

    ctx = _btp_context(site)
    ctx.update({'post': post, 'related_posts': related, 'page_title': post.title})
    return render(request, 'websites/public/btp/blog_detail.html', ctx)


# ─── ERP integration helpers ──────────────────────────────────────────────────

def _handle_emergency_erp(site, emergency):
    """Crée une GuidedQuoteRequest urgente et une notification ERP."""
    try:
        from apps.btp.models import GuidedQuoteRequest
        gqr = GuidedQuoteRequest.objects.create(
            company        = site.company,
            request_type   = 'depannage',
            urgency        = 'urgent',
            status         = 'new',
            client_first_name = emergency.first_name,
            client_last_name  = emergency.last_name,
            client_email      = emergency.email,
            client_phone      = emergency.phone,
            address        = emergency.address,
            client_notes   = f"URGENCE {emergency.get_emergency_type_display()}\n{emergency.description}",
        )
        emergency.guided_quote = gqr
        emergency.save(update_fields=['guided_quote'])
    except Exception:
        pass

    _notify_erp(
        site,
        f"URGENCE — {emergency.get_emergency_type_display()} — {emergency.first_name} {emergency.last_name}",
        f"Tél : {emergency.phone}  |  Adresse : {emergency.address}",
        'Nouvelle demande dépannage urgente',
        'btp_emergency',
        priority='urgent',
    )


def _notify_erp(site, title, message, notif_type_label, source, priority='normal'):
    """Crée une notification interne Orion ERP."""
    try:
        from apps.notifications.models import Notification
        from django.contrib.auth.models import User
        admins = User.objects.filter(is_staff=True, is_active=True)[:3]
        for user in admins:
            Notification.objects.create(
                company      = site.company,
                user         = user,
                notification_type = source,
                priority     = priority,
                title        = title[:200],
                message      = message[:500],
                source_module= 'websites',
                icon         = 'bi-globe2',
                icon_color   = '#C6A15B',
            )
    except Exception:
        pass
