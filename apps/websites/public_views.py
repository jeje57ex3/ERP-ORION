"""
apps/websites/public_views.py — Pages publiques des sites web
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from .models import Website, WebsitePage, BlogPost, ContactMessage, QuoteRequest
from .forms import ContactForm, QuoteRequestForm


def _get_site(site_slug):
    """Récupère le site web et le contexte de base."""
    from django.http import Http404
    # Cherche d'abord par slug du site, puis par slug de l'entreprise (compat anciens sites)
    site = Website.objects.filter(slug=site_slug, is_active=True).first()
    if site is None:
        site = Website.objects.filter(company__slug=site_slug, is_active=True).first()
    if site is None:
        raise Http404
    return site


def _base_context(site):
    """Contexte commun à toutes les pages publiques."""
    menu_items = []
    try:
        main_menu = site.menus.filter(position='header', is_active=True).first()
        if main_menu:
            menu_items = main_menu.items.filter(is_active=True, parent=None).prefetch_related('children')
    except Exception:
        pass

    footer_links = []
    try:
        footer_menu = site.menus.filter(position='footer', is_active=True).first()
        if footer_menu:
            footer_links = footer_menu.items.filter(is_active=True)
    except Exception:
        pass

    return {
        'site': site,
        'theme': site.theme,
        'menu_items': menu_items,
        'footer_links': footer_links,
        'company': site.company,
    }


def home(request, site_slug):
    """Page d'accueil du site."""
    site = _get_site(site_slug)
    ctx = _base_context(site)

    # Page d'accueil
    homepage = site.pages.filter(is_homepage=True, status='published').first()
    if not homepage:
        homepage = site.pages.filter(page_type='home', status='published').first()

    ctx['page'] = homepage

    if homepage:
        ctx['sections'] = homepage.sections.filter(is_visible=True).order_by('order')
    else:
        ctx['sections'] = []

    # Contenu complémentaire
    ctx['featured_services'] = site.services.filter(is_active=True).order_by('order')[:6]
    ctx['featured_projects'] = site.web_projects.filter(is_active=True, is_featured=True).order_by('order')[:6]
    ctx['testimonials'] = site.testimonials.filter(is_active=True).order_by('order')[:6]
    ctx['recent_posts'] = site.blog_posts.filter(status='published').order_by('-published_at')[:3]
    ctx['faqs'] = site.faqs.filter(is_active=True).order_by('order')

    return render(request, 'websites/public/home.html', ctx)


def page(request, site_slug, page_slug):
    """Page dynamique du site."""
    site = _get_site(site_slug)
    web_page = get_object_or_404(WebsitePage, website=site, slug=page_slug, status='published')

    ctx = _base_context(site)
    ctx['page'] = web_page
    ctx['sections'] = web_page.sections.filter(is_visible=True).order_by('order')

    return render(request, 'websites/public/page.html', ctx)


def blog_list(request, site_slug):
    """Liste des articles de blog."""
    site = _get_site(site_slug)
    posts = site.blog_posts.filter(status='published').order_by('-published_at')
    categories = site.blog_categories.all()

    category_slug = request.GET.get('category')
    if category_slug:
        posts = posts.filter(category__slug=category_slug)

    ctx = _base_context(site)
    ctx.update({
        'posts': posts,
        'categories': categories,
        'current_category': category_slug,
        'page_title': 'Blog',
    })
    return render(request, 'websites/public/blog_list.html', ctx)


def blog_detail(request, site_slug, post_slug):
    """Article de blog."""
    site = _get_site(site_slug)
    post = get_object_or_404(BlogPost, website=site, slug=post_slug, status='published')

    related = site.blog_posts.filter(
        status='published', category=post.category
    ).exclude(pk=post.pk).order_by('-published_at')[:3]

    ctx = _base_context(site)
    ctx.update({
        'post': post,
        'related_posts': related,
        'page_title': post.title,
    })
    return render(request, 'websites/public/blog_detail.html', ctx)


def contact(request, site_slug):
    """Formulaire de contact."""
    site = _get_site(site_slug)
    ctx = _base_context(site)

    form = ContactForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        # Anti-spam honeypot
        if not form.cleaned_data.get('website_url_field'):
            msg = form.save(commit=False)
            msg.website = site
            msg.ip_address = _get_ip(request)
            msg.honeypot = form.cleaned_data.get('website_url_field', '')
            msg.save()
            messages.success(request, 'Votre message a été envoyé avec succès. Nous vous répondrons rapidement.')
            return redirect(request.path)
        else:
            pass  # Spam détecté, on ignore silencieusement

    ctx.update({'form': form, 'page_title': 'Nous contacter'})
    return render(request, 'websites/public/contact.html', ctx)


def quote_request(request, site_slug):
    """Formulaire de demande de devis."""
    site = _get_site(site_slug)
    ctx = _base_context(site)

    form = QuoteRequestForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        if not form.cleaned_data.get('website_url_field'):
            qr = form.save(commit=False)
            qr.website = site
            qr.ip_address = _get_ip(request)
            qr.save()

            # Créer automatiquement un prospect CRM
            _create_crm_lead(site, qr)

            messages.success(request, 'Votre demande de devis a été envoyée. Notre équipe vous contactera très prochainement.')
            return redirect(request.path)

    ctx.update({'form': form, 'page_title': 'Demande de devis'})
    return render(request, 'websites/public/quote_request.html', ctx)


def _create_crm_lead(site, quote_request):
    """Crée automatiquement un prospect CRM depuis une demande de devis."""
    try:
        from apps.crm.models import Prospect, Opportunity
        prospect = Prospect.objects.create(
            company=site.company,
            name=quote_request.company_name or quote_request.name,
            contact_name=quote_request.name,
            email=quote_request.email,
            phone=quote_request.phone,
            source='website',
            notes=f'Demande de devis web : {quote_request.description}',
            status='new',
        )
        quote_request.crm_prospect_id = prospect.pk

        opportunity = Opportunity.objects.create(
            company=site.company,
            name=f'Devis web — {quote_request.project_type or quote_request.name}',
            prospect=prospect,
            stage='prospecting',
            probability=10,
            notes=quote_request.description,
        )
        quote_request.crm_opportunity_id = opportunity.pk
        quote_request.save(update_fields=['crm_prospect_id', 'crm_opportunity_id'])
    except Exception:
        pass


def _get_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')
