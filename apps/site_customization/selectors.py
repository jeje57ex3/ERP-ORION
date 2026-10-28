from .models import SitePageCustomization, SiteThemeSettings


def get_company_websites(company):
    if not company:
        from django.db.models import QuerySet
        from apps.websites.models import Website
        return Website.objects.none()
    from apps.websites.models import Website
    return Website.objects.filter(company=company).order_by('name')


def get_theme_for_website(website):
    if not website:
        return None
    return SiteThemeSettings.objects.filter(website=website).first()


def get_or_create_theme(company, website):
    theme, _ = SiteThemeSettings.objects.get_or_create(
        company=company,
        website=website,
    )
    return theme


def get_company_pages(company):
    if not company:
        return SitePageCustomization.objects.none()
    return (
        SitePageCustomization.objects
        .filter(company=company)
        .select_related('website')
        .order_by('website__name', 'title')
    )


def get_published_theme(website):
    return SiteThemeSettings.objects.filter(website=website, is_published=True).first()


def get_public_page(website, slug=None, homepage=False):
    qs = SitePageCustomization.objects.filter(
        website=website, status='published'
    ).prefetch_related('sections__blocks')
    if homepage:
        return qs.filter(is_homepage=True).first()
    if slug:
        return qs.filter(slug=slug).first()
    return None
