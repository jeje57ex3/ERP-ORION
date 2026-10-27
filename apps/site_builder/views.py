"""
apps/site_builder/views.py — ERP views for the Visual Site Builder.
"""
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.private_saas.decorators import require_company_module
from apps.websites.models import Website

from .forms import BuilderPageForm
from .models import BuilderPage
from .registry import BUILDER_MODULES
from .renderer import render_section_html
from .selectors import get_company_pages, get_page_or_404
from .services import create_default_builder_page_for_website
from .site_resolver import SiteResolverError, get_real_lunea_website, get_real_siecle_website


@login_required
@require_company_module('site_builder')
def page_list_view(request):
    company = request.current_company
    pages = get_company_pages(company)

    return render(request, 'site_builder/page_list.html', {
        'page_title': 'Éditeur visuel',
        'pages':      pages,
        'total':      pages.count(),
    })


@login_required
@require_company_module('site_builder')
def page_create_view(request):
    company = request.current_company
    websites = Website.objects.filter(company=company, is_active=True)

    if request.method == 'POST':
        form = BuilderPageForm(request.POST)
        website_id = request.POST.get('website')
        website = get_object_or_404(Website, pk=website_id, company=company)

        if form.is_valid():
            page = form.save(commit=False)
            page.company = company
            page.website = website
            page.brand_key = website.slug
            page.save()
            messages.success(request, f'Page « {page.title} » créée.')
            return redirect('site_builder:builder', page_id=page.pk)
    else:
        form = BuilderPageForm()
        website = websites.first()

    return render(request, 'site_builder/page_form.html', {
        'page_title': 'Nouvelle page',
        'form':       form,
        'websites':   websites,
        'editing':    False,
    })


@login_required
@require_company_module('site_builder')
def page_edit_view(request, page_id):
    company = request.current_company
    page = get_page_or_404(company, page_id)

    if request.method == 'POST':
        form = BuilderPageForm(request.POST, instance=page)
        if form.is_valid():
            form.save()
            messages.success(request, 'Page mise à jour.')
            return redirect('site_builder:builder', page_id=page.pk)
    else:
        form = BuilderPageForm(instance=page)

    return render(request, 'site_builder/page_form.html', {
        'page_title': f'Modifier — {page.title}',
        'form':       form,
        'page_obj':   page,
        'editing':    True,
    })


@login_required
@require_company_module('site_builder')
def builder_view(request, page_id):
    company = request.current_company
    page = get_page_or_404(company, page_id)
    sections = page.sections.order_by('position')

    sections_data = []
    for section in sections:
        module_info = BUILDER_MODULES.get(section.module_type, {})
        sections_data.append({
            'pk':           section.pk,
            'module_type':  section.module_type,
            'module_label': module_info.get('label', section.module_type),
            'module_icon':  module_info.get('icon', 'bi-box'),
            'settings_json': json.dumps(section.settings),
            'rendered_html': render_section_html(section, page.brand_key),
        })

    # Compute the live-preview URL for the iframe (real Next.js site)
    website = page.website
    site_url = None
    if website:
        slug = website.slug
        slug_path = f'/{slug}' if slug in ('siecle', 'lunea') else ''
        if website.domain:
            site_url = f'https://{website.domain}{slug_path}'
        elif website.local_port and website.local_port not in (0, 9000):
            site_url = f'http://localhost:{website.local_port}{slug_path}'
        elif slug == 'siecle':
            site_url = f'http://localhost:5173{slug_path}'
        elif slug == 'lunea':
            site_url = f'http://localhost:5174{slug_path}'

    return render(request, 'site_builder/builder.html', {
        'page':          page,
        'sections_data': sections_data,
        'modules':       BUILDER_MODULES,
        'site_url':      site_url,
    })


@login_required
@require_company_module('site_builder')
def preview_view(request, page_id):
    company = request.current_company
    page = get_page_or_404(company, page_id)
    sections = page.sections.order_by('position')

    sections_html = [
        render_section_html(s, page.brand_key)
        for s in sections
    ]

    return render(request, 'site_builder/preview.html', {
        'page':          page,
        'sections_html': sections_html,
    })


@login_required
@require_company_module('site_builder')
def page_delete_view(request, page_id):
    company = request.current_company
    page = get_page_or_404(company, page_id)
    if request.method == 'POST':
        title = page.title
        page.delete()
        messages.success(request, f'Page « {title} » supprimée.')
    return redirect('site_builder:page_list')


# ── Smart "ouvrir ou créer" par marque ───────────────────────────────────────

@login_required
@require_company_module('site_builder')
def open_siecle_builder(request):
    return _open_or_create_brand_homepage(request, get_real_siecle_website)


@login_required
@require_company_module('site_builder')
def open_lunea_builder(request):
    return _open_or_create_brand_homepage(request, get_real_lunea_website)


def _open_or_create_brand_homepage(request, website_getter):
    company = request.current_company

    try:
        website = website_getter(company)
    except SiteResolverError as exc:
        messages.error(request, str(exc))
        return redirect('site_builder:page_list')

    page = BuilderPage.objects.filter(
        company=company,
        website=website,
        is_homepage=True,
    ).first()

    if not page:
        page = create_default_builder_page_for_website(
            company=company,
            website=website,
            is_homepage=True,
        )
        messages.success(
            request,
            f"Page d'accueil {website.name} créée automatiquement avec des sections par défaut.",
        )

    return redirect('site_builder:builder', page_id=page.pk)
