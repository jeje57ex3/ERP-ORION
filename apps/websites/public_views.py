"""
apps/websites/public_views.py — Pages publiques des sites web
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from django.utils.translation import gettext as _
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
            menu_items = list(main_menu.items.filter(is_active=True, parent=None).prefetch_related('children', 'translations'))
            for item in menu_items:
                _translated(item, ['label', 'url'])
                for child in item.children.all():
                    _translated(child, ['label', 'url'])
    except Exception:
        pass

    footer_links = []
    try:
        footer_menu = site.menus.filter(position='footer', is_active=True).first()
        if footer_menu:
            footer_links = list(footer_menu.items.filter(is_active=True).prefetch_related('translations'))
            for item in footer_links:
                _translated(item, ['label', 'url'])
    except Exception:
        pass

    return {
        'site': site,
        'theme': site.theme,
        'menu_items': menu_items,
        'footer_links': footer_links,
        'company': site.company,
        'website_languages': _get_website_languages(site),
    }


DEFAULT_SITE_LANGUAGES = ['fr', 'en', 'es', 'it', 'pt']


def translate_static_items(items, key_prefix, fields=('name', 'desc')):
    """
    Traduit une liste de dicts de contenu statique (listes Python en dur,
    ex: ELECTRICITE_SERVICES, WORK_CATEGORIES) via InterfaceTranslation,
    clé `<key_prefix>.<slug-ou-index>.<field>`. Retombe sur le texte français
    d'origine si aucune traduction n'existe pour la langue active. Ne modifie
    pas les dicts d'origine (retourne des copies).
    """
    from django.utils import translation as dj_translation
    from apps.translations.templatetags.translation_tags import get_translation

    lang = dj_translation.get_language() or 'fr'
    if lang == 'fr':
        return items
    translated = []
    for item in items:
        item_key = item.get('slug') or item.get('name', '')
        new_item = dict(item)
        for field in fields:
            if field in item:
                key = f'{key_prefix}.{item_key}.{field}'
                new_item[field] = get_translation(key, fallback=item[field]) if lang != 'fr' else item[field]
        translated.append(new_item)
    return translated


def translate_faq_items(items, key_prefix):
    """Comme `translate_static_items` mais pour une liste de tuples (question, réponse)."""
    from django.utils import translation as dj_translation
    from apps.translations.templatetags.translation_tags import get_translation

    lang = dj_translation.get_language() or 'fr'
    if lang == 'fr':
        return items
    result = []
    for index, (question, answer) in enumerate(items):
        q = get_translation(f'{key_prefix}.{index}.question', fallback=question)
        a = get_translation(f'{key_prefix}.{index}.answer', fallback=answer)
        result.append((q, a))
    return result


def _get_website_languages(site):
    """
    Liste des langues actives du site pour le sélecteur public
    (`templates/websites/public/components/language_switcher.html`).
    Crée les réglages de langue du site à la volée (5 langues par défaut)
    s'ils n'existent pas encore — évite toute étape d'admin manuelle.
    """
    try:
        from django.utils import translation
        from apps.translations.models import Language, WebsiteLanguageSettings

        settings_obj, created = WebsiteLanguageSettings.objects.get_or_create(website=site)
        if created or not settings_obj.enabled_languages.exists():
            default_langs = Language.objects.filter(code__in=DEFAULT_SITE_LANGUAGES, is_active=True)
            settings_obj.enabled_languages.set(default_langs)
            if not settings_obj.default_language:
                settings_obj.default_language = default_langs.filter(code='fr').first()
                settings_obj.save(update_fields=['default_language'])

        if not settings_obj.show_language_switcher:
            return []

        current = translation.get_language() or 'fr'
        return [
            {'code': lang.code, 'native_name': lang.native_name, 'flag_icon': lang.flag_icon,
             'is_current': lang.code == current}
            for lang in settings_obj.get_enabled_language_list()
        ]
    except Exception:
        return []


def _translated(obj, fields):
    """
    Retourne `obj` avec les champs indiqués remplacés par leur traduction dans
    la langue active (table `<Model>Translation`, relation inverse `translations`),
    fallback français (valeurs d'origine inchangées) si aucune ligne traduite
    n'existe. Modification en mémoire uniquement, rien n'est sauvegardé.
    Volontairement générique : fonctionne pour WebsitePage, WebsiteSection et
    BlogPost, qui exposent tous une relation `translations` au même format.
    Le champ `slug` n'est jamais traduit ici : les URLs restent basées sur le
    slug français (pas d'URLs préfixées par langue dans ce périmètre).
    """
    from django.utils import translation as dj_translation

    lang = dj_translation.get_language() or 'fr'
    if lang == 'fr':
        return obj
    tr = obj.translations.filter(language=lang).first()
    if tr:
        for field in fields:
            value = getattr(tr, field, '')
            if value:
                setattr(obj, field, value)
    return obj


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
    web_page = _translated(web_page, ('title', 'content', 'meta_title', 'meta_description', 'meta_keywords'))
    sections = [
        _translated(section, ('title', 'subtitle', 'content', 'button_text', 'button_url'))
        for section in web_page.sections.filter(is_visible=True).order_by('order')
    ]

    ctx = _base_context(site)
    ctx['page'] = web_page
    ctx['sections'] = sections

    return render(request, 'websites/public/page.html', ctx)


def blog_list(request, site_slug):
    """Liste des articles de blog."""
    site = _get_site(site_slug)
    posts = site.blog_posts.filter(status='published').order_by('-published_at')
    categories = site.blog_categories.all()

    category_slug = request.GET.get('category')
    if category_slug:
        posts = posts.filter(category__slug=category_slug)

    posts = [_translated(post, ('title', 'excerpt')) for post in posts]

    ctx = _base_context(site)
    ctx.update({
        'posts': posts,
        'categories': categories,
        'current_category': category_slug,
        'page_title': _('Blog'),
    })
    return render(request, 'websites/public/blog_list.html', ctx)


def blog_detail(request, site_slug, post_slug):
    """Article de blog."""
    site = _get_site(site_slug)
    post = get_object_or_404(BlogPost, website=site, slug=post_slug, status='published')
    post = _translated(post, ('title', 'excerpt', 'content', 'meta_title', 'meta_description'))

    related = site.blog_posts.filter(
        status='published', category=post.category
    ).exclude(pk=post.pk).order_by('-published_at')[:3]
    related = [_translated(r, ('title', 'excerpt')) for r in related]

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

    ctx.update({'form': form, 'page_title': _('Nous contacter')})
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

    ctx.update({'form': form, 'page_title': _('Demande de devis')})
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


def sitemap_public(request, site_slug):
    """sitemap.xml public du site (réutilise apps.websites.seo_services)."""
    from django.http import HttpResponse
    from .seo_services import generate_sitemap_xml
    site = _get_site(site_slug)
    return HttpResponse(generate_sitemap_xml(site), content_type='application/xml')


def robots_public(request, site_slug):
    """robots.txt public du site (réutilise apps.websites.seo_services)."""
    from django.http import HttpResponse
    from .seo_services import generate_robots_txt
    site = _get_site(site_slug)
    return HttpResponse(generate_robots_txt(site), content_type='text/plain')


def set_site_language(request):
    """
    Change la langue active pour les sites publics (visiteurs anonymes inclus).
    Lit `?lang=xx`, valide contre les langues actives en base, écrit la clé de
    session lue par `apps.translations.middleware.OrionLanguageMiddleware`
    (distincte de la clé standard Django, volontairement — voir le plan i18n),
    puis redirige vers la page d'origine sans le paramètre `lang`.
    """
    from apps.translations.models import Language

    code = request.GET.get('lang', '')
    if Language.objects.filter(code=code, is_active=True).exists():
        request.session['_language'] = code

    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER')
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect('/')


def newsletter_subscribe(request):
    """Inscription newsletter — générique, réutilisée par tous les sites publics."""
    if request.method == 'POST':
        from .models import NewsletterSubscriber
        email = request.POST.get('email', '').strip()
        if email:
            NewsletterSubscriber.objects.get_or_create(email=email)
            messages.success(request, 'Merci ! Votre inscription à la newsletter est confirmée.')
    referer = request.META.get('HTTP_REFERER')
    return redirect(referer or '/')
