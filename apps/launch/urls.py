from django.urls import path
from .views import waitlist_subscribe, contact_submit
from .seo_views import robots_txt, sitemap_xml

app_name = 'launch'

urlpatterns = [
    path('api/v1/waitlist/subscribe/', waitlist_subscribe, name='waitlist_subscribe'),
    path('api/v1/contact/', contact_submit, name='contact_submit'),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap_xml, name='sitemap_xml'),
]
