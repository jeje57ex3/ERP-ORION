from django.shortcuts import get_object_or_404

from .models import BuilderPage, BuilderSection


def get_company_pages(company):
    return BuilderPage.objects.filter(company=company).select_related('website').order_by('-updated_at')


def get_page_or_404(company, page_id):
    return get_object_or_404(BuilderPage, pk=page_id, company=company)


def get_published_pages_for_website(website):
    return BuilderPage.objects.filter(
        website=website,
        status=BuilderPage.STATUS_PUBLISHED,
    ).order_by('is_homepage', 'title')


def get_published_page(website, slug=None, homepage=False):
    qs = BuilderPage.objects.filter(website=website, status=BuilderPage.STATUS_PUBLISHED)
    if homepage:
        return qs.filter(is_homepage=True).first()
    if slug:
        return qs.filter(slug=slug).first()
    return None
