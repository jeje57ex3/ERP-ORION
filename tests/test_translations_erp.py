"""
Tests du systeme de traduction ERP — Orion
python manage.py test tests.test_translations_erp
"""
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model

SIMPLE_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
User = get_user_model()


@override_settings(STATICFILES_STORAGE=SIMPLE_STORAGE)
class LanguageModelTest(TestCase):
    """Tests du modele Language."""

    def test_seed_creates_seven_languages(self):
        from django.core.management import call_command
        from apps.translations.models import Language
        call_command('seed_languages', verbosity=0)
        self.assertEqual(Language.objects.count(), 7)

    def test_language_str(self):
        from apps.translations.models import Language
        lang = Language.objects.create(code='xx', name='Test', native_name='Test Lang', order=99)
        self.assertIn('xx', str(lang))

    def test_only_one_default(self):
        """Deux langues ne peuvent pas etre 'is_default=True' en meme temps."""
        from apps.translations.models import Language
        lang1 = Language.objects.create(code='a1', name='L1', native_name='L1', is_default=True, order=91)
        lang2 = Language.objects.create(code='a2', name='L2', native_name='L2', is_default=True, order=92)
        lang1.refresh_from_db()
        self.assertFalse(lang1.is_default)
        self.assertTrue(lang2.is_default)


@override_settings(STATICFILES_STORAGE=SIMPLE_STORAGE)
class CompanyLanguageSettingsTest(TestCase):
    """Tests des parametres langue entreprise."""

    def _make_company(self):
        from apps.core.models import Company
        return Company.objects.create(name='LangCo', slug='lang-co')

    def _make_lang(self, code):
        from apps.translations.models import Language
        lang, _ = Language.objects.get_or_create(code=code, defaults={'name': code, 'native_name': code, 'order': 1})
        return lang

    def test_create_company_language_settings(self):
        from apps.translations.models import CompanyLanguageSettings
        company = self._make_company()
        fr = self._make_lang('fr')
        en = self._make_lang('en')
        settings = CompanyLanguageSettings.objects.create(
            company=company,
            default_language=fr,
        )
        settings.enabled_languages.set([fr, en])
        self.assertEqual(settings.default_language.code, 'fr')
        self.assertEqual(settings.enabled_languages.count(), 2)

    def test_get_company_default_language(self):
        from apps.translations.models import CompanyLanguageSettings
        from apps.translations.services import get_company_default_language
        company = self._make_company()
        fr = self._make_lang('fr')
        CompanyLanguageSettings.objects.create(company=company, default_language=fr)
        self.assertEqual(get_company_default_language(company), 'fr')

    def test_get_company_default_language_fallback(self):
        """Sans parametres langue, retourne 'fr' par defaut."""
        from apps.translations.services import get_company_default_language
        company = self._make_company()
        self.assertEqual(get_company_default_language(company), 'fr')


@override_settings(STATICFILES_STORAGE=SIMPLE_STORAGE)
class UserLanguagePreferenceTest(TestCase):
    """Tests de la preference langue utilisateur."""

    def _make_user(self):
        return User.objects.create_user(username='languser', password='pass')

    def _make_lang(self, code):
        from apps.translations.models import Language
        lang, _ = Language.objects.get_or_create(code=code, defaults={'name': code, 'native_name': code, 'order': 1})
        return lang

    def test_set_and_get_user_language(self):
        from apps.translations.services import set_user_language, get_user_language
        user = self._make_user()
        self._make_lang('en')
        set_user_language(user, 'en')
        self.assertEqual(get_user_language(user), 'en')

    def test_invalid_language_code_not_saved(self):
        from apps.translations.services import set_user_language, get_user_language
        user = self._make_user()
        result = set_user_language(user, 'xx')
        self.assertFalse(result)


@override_settings(STATICFILES_STORAGE=SIMPLE_STORAGE)
class InterfaceTranslationTest(TestCase):
    """Tests des traductions d interface personnalisees."""

    def _make_lang(self, code='en'):
        from apps.translations.models import Language
        lang, _ = Language.objects.get_or_create(code=code, defaults={'name': code, 'native_name': code, 'order': 1})
        return lang

    def test_create_interface_translation(self):
        from apps.translations.models import InterfaceTranslation
        lang = self._make_lang()
        t = InterfaceTranslation.objects.create(
            key='dashboard.title',
            language=lang,
            source_text='Tableau de bord',
            translated_text='Dashboard',
            module='dashboard',
        )
        self.assertIn('dashboard.title', str(t))

    def test_unique_together_key_language_same_company(self):
        """Deux traductions du meme (key, language, company non-null) doivent etre uniques."""
        from apps.translations.models import InterfaceTranslation
        from apps.core.models import Company
        from django.db import IntegrityError
        lang = self._make_lang()
        company = Company.objects.create(name='TrCo', slug='tr-co')
        InterfaceTranslation.objects.create(
            key='crm.clients', language=lang, company=company,
            source_text='Clients', translated_text='Customers',
        )
        with self.assertRaises(IntegrityError):
            InterfaceTranslation.objects.create(
                key='crm.clients', language=lang, company=company,
                source_text='Clients', translated_text='Clients (dup)',
            )


@override_settings(STATICFILES_STORAGE=SIMPLE_STORAGE)
class SyncMissingTranslationsCommandTest(TestCase):
    """Tests de la commande sync_missing_translations."""

    def test_sync_detects_missing(self):
        from django.core.management import call_command
        from apps.translations.models import Language
        Language.objects.create(code='en', name='English', native_name='English', order=2)
        Language.objects.create(code='fr', name='French', native_name='Français', order=1, is_default=True)
        # Sans --create, ne doit pas creer d entrees
        call_command('sync_missing_translations', language='en', verbosity=0)
        from apps.translations.models import InterfaceTranslation
        self.assertEqual(InterfaceTranslation.objects.count(), 0)

    def test_sync_creates_entries_with_flag(self):
        from django.core.management import call_command
        from apps.translations.models import Language, InterfaceTranslation
        Language.objects.create(code='en', name='English', native_name='English', order=2)
        Language.objects.create(code='fr', name='French', native_name='Français', order=1, is_default=True)
        call_command('sync_missing_translations', language='en', create=True, verbosity=0)
        self.assertGreater(InterfaceTranslation.objects.filter(language__code='en').count(), 0)
