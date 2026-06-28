from django.http import HttpResponse
from django.views.decorators.cache import cache_page


@cache_page(60 * 60 * 24)
def robots_txt(request):
    lines = [
        'User-agent: *',
        'Allow: /',
        '',
        'Disallow: /admin/',
        'Disallow: /orion-admin/',
        'Disallow: /api/',
        '',
        'Sitemap: https://siecle.example.com/sitemap.xml',
        'Sitemap: https://lunea.example.com/sitemap.xml',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain')


@cache_page(60 * 60 * 6)
def sitemap_xml(request):
    brand = request.GET.get('brand', 'siecle')
    base = 'https://lunea.example.com' if brand == 'lunea' else 'https://siecle.example.com'
    prefix = '/lunea' if brand == 'lunea' else ''

    pages = [
        ('/', '1.0', 'daily'),
        ('/boutique/', '0.9', 'daily'),
        ('/livraison-retours/', '0.7', 'monthly'),
        ('/mentions-legales/', '0.3', 'yearly'),
        ('/cgv/', '0.3', 'yearly'),
        ('/confidentialite/', '0.3', 'yearly'),
        ('/cookies/', '0.3', 'yearly'),
    ]

    urls = []
    for path, priority, changefreq in pages:
        urls.append(f'''  <url>
    <loc>{base}{prefix}{path}</loc>
    <priority>{priority}</priority>
    <changefreq>{changefreq}</changefreq>
  </url>''')

    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>'''
    return HttpResponse(xml, content_type='application/xml')
