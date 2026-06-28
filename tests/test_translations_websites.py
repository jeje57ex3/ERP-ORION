"""
Tests du systeme de traduction sites web — Orion
python manage.py test tests.test_translations_websites
"""
from django.test import TestCase, override_settings

SIMPLE_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"


@override_settings(STATICFILES_STORAGE=SIMPLE_STORAGE)
class WebsiteTranslationModelsTest(TestCase):
    """Tests des modeles de traduction sites web."""

    def _make_company_and_site(self):
        from apps.core.models import Company
        from apps.websites.models import Website
        company = Company.objects.create(name='TransCo', slug='trans-co')
        site = Website.objects.create(
            company=company, name='Trans Site', slug='trans-co',
            site_type='btp', is_active=True,
        )
        return company, site

    def test_website_page_translation_str(self):
        from apps.websites.models import WebsitePage, WebsitePageTranslation
        _, site = self._make_company_and_site()
        page = WebsitePage.objects.create(
            website=site, title='Accueil', slug='accueil',
            page_type='home', status='published',
        )
        t = WebsitePageTranslation.objects.create(
            page=page, language='en', title='Home', slug='home',
        )
        self.assertIn('en', str(t))
        self.assertIn('Home', t.title)

    def test_blog_post_translation(self):
        from apps.websites.models import BlogCategory, BlogPost, BlogPostTranslation
        from django.contrib.auth import get_user_model
        _, site = self._make_company_and_site()
        author = get_user_model().objects.create_user(username='author2', password='pass')
        cat = BlogCategory.objects.create(website=site, name='Actualites', slug='actualites')
        post = BlogPost.objects.create(
            website=site, category=cat, author=author,
            title='Mon article', slug='mon-article', status='published',
        )
        t = BlogPostTranslation.objects.create(
            post=post, language='en', title='My article',
            slug='my-article', content='Content',
        )
        self.assertEqual(t.language, 'en')
        self.assertIn('en', str(t))

    def test_menu_item_translation(self):
        from apps.websites.models import WebsiteMenu, WebsiteMenuItem, WebsiteMenuItemTranslation
        _, site = self._make_company_and_site()
        menu = WebsiteMenu.objects.create(website=site, name='Nav', position='header')
        item = WebsiteMenuItem.objects.create(menu=menu, label='Accueil', url='/', order=1)
        t = WebsiteMenuItemTranslation.objects.create(
            menu_item=item, language='en', label='Home', url='/',
        )
        self.assertEqual(t.label, 'Home')

    def test_unique_together_page_language(self):
        from apps.websites.models import WebsitePage, WebsitePageTranslation
        from django.db import IntegrityError
        _, site = self._make_company_and_site()
        page = WebsitePage.objects.create(
            website=site, title='Services', slug='services',
            page_type='services', status='published',
        )
        WebsitePageTranslation.objects.create(
            page=page, language='en', title='Services EN', slug='services-en',
        )
        with self.assertRaises(IntegrityError):
            WebsitePageTranslation.objects.create(
                page=page, language='en', title='Duplicate', slug='dup',
            )


@override_settings(STATICFILES_STORAGE=SIMPLE_STORAGE)
class WebsiteLanguageSettingsTest(TestCase):
    """Tests des parametres langue site web."""

    def _make_company_and_site(self):
        from apps.core.models import Company
        from apps.websites.models import Website
        company = Company.objects.create(name='LangSiteCo', slug='lang-site-co')
        site = Website.objects.create(
            company=company, name='Lang Site', slug='lang-site-co',
            site_type='btp', is_active=True,
        )
        return company, site

    def _make_lang(self, code):
        from apps.translations.models import Language
        lang, _ = Language.objects.get_or_create(code=code, defaults={'name': code, 'native_name': code, 'order': 1})
        return lang

    def test_create_website_language_settings(self):
        from apps.translations.models import WebsiteLanguageSettings
        _, site = self._make_company_and_site()
        fr = self._make_lang('fr')
        en = self._make_lang('en')
        ls = WebsiteLanguageSettings.objects.create(
            website=site, default_language=fr,
            show_language_switcher=True, use_language_prefix_urls=False,
        )
        ls.enabled_languages.set([fr, en])
        self.assertEqual(ls.default_language.code, 'fr')
        self.assertEqual(ls.enabled_languages.count(), 2)
        self.assertIn('Lang Site', str(ls))

    def test_language_resolver_get_website_language(self):
        """get_website_language_from_request retourne la langue du parametre GET."""
        from apps.translations.models import WebsiteLanguageSettings
        from apps.websites.services.language_resolver import get_website_language_from_request
        _, site = self._make_company_and_site()
        fr = self._make_lang('fr')
        en = self._make_lang('en')
        ls = WebsiteLanguageSettings.objects.create(website=site, default_language=fr)
        ls.enabled_languages.set([fr, en])

        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/', {'lang': 'en'})
        request.session = {}
        lang = get_website_language_from_request(request, site)
        self.assertEqual(lang, 'en')

    def test_language_resolver_fallback_to_default(self):
        """Sans parametre GET, retourne la langue par defaut du site."""
        from apps.translations.models import WebsiteLanguageSettings
        from apps.websites.services.language_resolver import get_website_language_from_request
        _, site = self._make_company_and_site()
        fr = self._make_lang('fr')
        ls = WebsiteLanguageSettings.objects.create(website=site, default_language=fr)
        ls.enabled_languages.set([fr])

        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/')
        request.session = {}
        lang = get_website_language_from_request(request, site)
        self.assertEqual(lang, 'fr')

    def test_get_translated_page_overlay(self):
        """get_translated_page retourne l overlay avec le titre traduit."""
        from apps.websites.models import WebsitePage, WebsitePageTranslation
        from apps.websites.services.language_resolver import get_translated_page
        _, site = self._make_company_and_site()
        page = WebsitePage.objects.create(
            website=site, title='Contact', slug='contact',
            page_type='contact', status='published',
        )
        WebsitePageTranslation.objects.create(
            page=page, language='en', title='Contact Us', slug='contact-us',
        )
        overlay = get_translated_page(page, 'en')
        self.assertEqual(overlay.title, 'Contact Us')
        self.assertEqual(overlay.slug, 'contact-us')

    def test_get_translated_page_fallback(self):
        """Sans traduction, get_translated_page retourne l original."""
        from apps.websites.models import WebsitePage
        from apps.websites.services.language_resolver import get_translated_page
        _, site = self._make_company_and_site()
        page = WebsitePage.objects.create(
            website=site, title='Blog', slug='blog',
            page_type='blog', status='published',
        )
        result = get_translated_page(page, 'de')
        self.assertEqual(result.title, 'Blog')

    def test_get_language_url_with_param(self):
        """get_language_url genere une URL avec parametre ?lang= si pas de prefixe."""
        from apps.websites.services.language_resolver import get_language_url
        _, site = self._make_company_and_site()
        url = get_language_url(site, 'en', '/services/')
        self.assertIn('lang=en', url)

    def test_hreflang_links(self):
        """get_hreflang_links retourne les liens pour chaque langue active."""
        from apps.translations.models import WebsiteLanguageSettings
        from apps.websites.services.language_resolver import get_hreflang_links
        _, site = self._make_company_and_site()
        fr = self._make_lang('fr')
        en = self._make_lang('en')
        ls = WebsiteLanguageSettings.objects.create(website=site)
        ls.enabled_languages.set([fr, en])
        links = get_hreflang_links(None, site, '/contact/')
        codes = [l['lang'] for l in links]
        self.assertIn('fr', codes)
        self.assertIn('en', codes)
