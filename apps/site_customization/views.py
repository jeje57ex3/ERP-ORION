"""
apps/site_customization/views.py — Interface ERP de personnalisation des sites
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.private_saas.decorators import require_company_module
from .forms import SiteContentBlockForm, SitePageCustomizationForm, SitePageSectionForm, SiteThemeSettingsForm
from .models import SiteContentBlock, SitePageCustomization, SitePageSection, SiteThemeSettings
from .selectors import get_company_pages, get_company_websites, get_or_create_theme
from .services import build_theme_css, publish_page, publish_theme


@login_required
@require_company_module('site_customization')
def dashboard(request):
    company = request.current_company
    websites = get_company_websites(company)
    pages = get_company_pages(company)[:10]
    return render(request, 'site_customization/dashboard.html', {
        'page_title': 'Personnalisation des sites',
        'websites':   websites,
        'pages':      pages,
    })


# ─── THÈME ────────────────────────────────────────────────────────────────────

@login_required
@require_company_module('site_customization')
def theme_edit(request, website_id):
    company = request.current_company
    website = get_object_or_404(get_company_websites(company), pk=website_id)
    theme = get_or_create_theme(company, website)

    if request.method == 'POST':
        form = SiteThemeSettingsForm(request.POST, request.FILES, instance=theme)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.company = company
            obj.website = website
            obj.updated_by = request.user
            obj.save()
            messages.success(request, 'Thème enregistré.')
            return redirect('site_customization:theme_edit', website_id=website.pk)
    else:
        form = SiteThemeSettingsForm(instance=theme)

    return render(request, 'site_customization/theme_form.html', {
        'page_title': f'Thème — {website.name}',
        'form':    form,
        'website': website,
        'theme':   theme,
    })


@login_required
@require_company_module('site_customization')
def theme_publish(request, website_id):
    company = request.current_company
    website = get_object_or_404(get_company_websites(company), pk=website_id)
    theme = get_or_create_theme(company, website)
    publish_theme(theme, request.user)
    messages.success(request, 'Thème publié sur le site.')
    return redirect('site_customization:theme_edit', website_id=website.pk)


# ─── PAGES ────────────────────────────────────────────────────────────────────

@login_required
@require_company_module('site_customization')
def page_list(request):
    company = request.current_company
    pages = get_company_pages(company)
    return render(request, 'site_customization/page_list.html', {
        'page_title': 'Pages personnalisées',
        'pages': pages,
    })


@login_required
@require_company_module('site_customization')
def page_create(request):
    company = request.current_company
    if request.method == 'POST':
        form = SitePageCustomizationForm(request.POST, request.FILES)
        form.fields['website'].queryset = get_company_websites(company)
        if form.is_valid():
            page = form.save(commit=False)
            page.company = company
            page.created_by = request.user
            page.updated_by = request.user
            page.save()
            messages.success(request, f'Page « {page.title} » créée.')
            return redirect('site_customization:page_detail', pk=page.pk)
    else:
        form = SitePageCustomizationForm()
    form.fields['website'].queryset = get_company_websites(company)
    return render(request, 'site_customization/page_form.html', {
        'page_title': 'Nouvelle page',
        'form': form,
    })


@login_required
@require_company_module('site_customization')
def page_detail(request, pk):
    company = request.current_company
    page = get_object_or_404(
        SitePageCustomization.objects.select_related('website').prefetch_related('sections__blocks'),
        pk=pk, company=company,
    )
    return render(request, 'site_customization/page_detail.html', {
        'page_title': page.title,
        'page':     page,
        'sections': page.sections.all(),
    })


@login_required
@require_company_module('site_customization')
def page_edit(request, pk):
    company = request.current_company
    page = get_object_or_404(SitePageCustomization, pk=pk, company=company)
    if request.method == 'POST':
        form = SitePageCustomizationForm(request.POST, request.FILES, instance=page)
        form.fields['website'].queryset = get_company_websites(company)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            obj.save()
            messages.success(request, 'Page mise à jour.')
            return redirect('site_customization:page_detail', pk=page.pk)
    else:
        form = SitePageCustomizationForm(instance=page)
    form.fields['website'].queryset = get_company_websites(company)
    return render(request, 'site_customization/page_form.html', {
        'page_title': f'Modifier — {page.title}',
        'form': form,
        'page': page,
    })


@login_required
@require_company_module('site_customization')
def page_publish(request, pk):
    company = request.current_company
    page = get_object_or_404(SitePageCustomization, pk=pk, company=company)
    publish_page(page, request.user)
    messages.success(request, f'Page « {page.title} » publiée.')
    return redirect('site_customization:page_detail', pk=page.pk)


@login_required
@require_company_module('site_customization')
def page_preview(request, pk):
    company = request.current_company
    page = get_object_or_404(
        SitePageCustomization.objects.select_related('website').prefetch_related('sections__blocks'),
        pk=pk, company=company,
    )
    theme = SiteThemeSettings.objects.filter(website=page.website).first()
    theme_css = build_theme_css(theme)
    return render(request, 'site_customization/preview.html', {
        'page':      page,
        'theme':     theme,
        'theme_css': theme_css,
        'sections':  page.sections.filter(is_visible=True),
    })


# ─── SECTIONS ─────────────────────────────────────────────────────────────────

@login_required
@require_company_module('site_customization')
def section_create(request, page_id):
    company = request.current_company
    page = get_object_or_404(SitePageCustomization, pk=page_id, company=company)
    if request.method == 'POST':
        form = SitePageSectionForm(request.POST, request.FILES)
        if form.is_valid():
            section = form.save(commit=False)
            section.page = page
            section.save()
            messages.success(request, 'Section ajoutée.')
            return redirect('site_customization:page_detail', pk=page.pk)
    else:
        form = SitePageSectionForm()
    return render(request, 'site_customization/section_form.html', {
        'page_title': 'Nouvelle section',
        'form': form,
        'page': page,
    })


@login_required
@require_company_module('site_customization')
def section_edit(request, section_id):
    company = request.current_company
    section = get_object_or_404(SitePageSection.objects.select_related('page'), pk=section_id, page__company=company)
    if request.method == 'POST':
        form = SitePageSectionForm(request.POST, request.FILES, instance=section)
        if form.is_valid():
            form.save()
            messages.success(request, 'Section mise à jour.')
            return redirect('site_customization:page_detail', pk=section.page.pk)
    else:
        form = SitePageSectionForm(instance=section)
    return render(request, 'site_customization/section_form.html', {
        'page_title': f'Modifier section — {section.title}',
        'form':    form,
        'section': section,
        'page':    section.page,
    })


@login_required
@require_company_module('site_customization')
def section_delete(request, section_id):
    company = request.current_company
    section = get_object_or_404(SitePageSection.objects.select_related('page'), pk=section_id, page__company=company)
    page_pk = section.page.pk
    if request.method == 'POST':
        section.delete()
        messages.success(request, 'Section supprimée.')
    return redirect('site_customization:page_detail', pk=page_pk)


# ─── BLOCS ────────────────────────────────────────────────────────────────────

@login_required
@require_company_module('site_customization')
def block_create(request, section_id):
    company = request.current_company
    section = get_object_or_404(SitePageSection.objects.select_related('page'), pk=section_id, page__company=company)
    if request.method == 'POST':
        form = SiteContentBlockForm(request.POST, request.FILES)
        if form.is_valid():
            block = form.save(commit=False)
            block.section = section
            block.save()
            messages.success(request, 'Bloc ajouté.')
            return redirect('site_customization:page_detail', pk=section.page.pk)
    else:
        form = SiteContentBlockForm()
    return render(request, 'site_customization/block_form.html', {
        'page_title': 'Nouveau bloc',
        'form':    form,
        'section': section,
        'page':    section.page,
    })


@login_required
@require_company_module('site_customization')
def block_edit(request, block_id):
    company = request.current_company
    block = get_object_or_404(SiteContentBlock.objects.select_related('section__page'), pk=block_id, section__page__company=company)
    if request.method == 'POST':
        form = SiteContentBlockForm(request.POST, request.FILES, instance=block)
        if form.is_valid():
            form.save()
            messages.success(request, 'Bloc mis à jour.')
            return redirect('site_customization:page_detail', pk=block.section.page.pk)
    else:
        form = SiteContentBlockForm(instance=block)
    return render(request, 'site_customization/block_form.html', {
        'page_title': f'Modifier bloc — {block.title or block.pk}',
        'form':    form,
        'block':   block,
        'section': block.section,
        'page':    block.section.page,
    })


@login_required
@require_company_module('site_customization')
def block_delete(request, block_id):
    company = request.current_company
    block = get_object_or_404(SiteContentBlock.objects.select_related('section__page'), pk=block_id, section__page__company=company)
    page_pk = block.section.page.pk
    if request.method == 'POST':
        block.delete()
        messages.success(request, 'Bloc supprimé.')
    return redirect('site_customization:page_detail', pk=page_pk)
