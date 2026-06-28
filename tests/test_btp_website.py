"""
Tests du site vitrine BTP — Orion ERP
python manage.py test tests.test_btp_website
"""
from django.test import TestCase, Client, override_settings
from django.urls import reverse, NoReverseMatch

SIMPLE_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"


@override_settings(STATICFILES_STORAGE=SIMPLE_STORAGE)
class BTPPublicViewsTest(TestCase):
    """Tests des vues publiques du site BTP."""

    fixtures = []

    def setUp(self):
        self.client = Client()

    def _make_company_and_site(self):
        from apps.core.models import Company
        from apps.websites.models import Website, WebsiteTheme

        company = Company.objects.create(
            name="Test BTP SARL",
            slug="test-btp-sarl",
        )
        theme = WebsiteTheme.objects.create(
            name="BTP Test Theme",
            primary_color="#3A2A1A",
        )
        site = Website.objects.create(
            company=company,
            name="Site BTP Test",
            slug="test-btp-sarl",
            site_type="btp",
            status="published",
            is_published=True,
            is_active=True,
            theme=theme,
            contact_phone="01 23 45 67 89",
        )
        return company, site

    def test_btp_home_returns_200(self):
        company, site = self._make_company_and_site()
        url = reverse("public_websites:btp_home", args=[company.slug])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_btp_home_contains_devis_link(self):
        company, site = self._make_company_and_site()
        url = reverse("public_websites:btp_home", args=[company.slug])
        response = self.client.get(url)
        self.assertContains(response, "devis-guide")

    def test_btp_services_returns_200(self):
        company, site = self._make_company_and_site()
        url = reverse("public_websites:btp_services", args=[company.slug])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_btp_works_returns_200(self):
        company, site = self._make_company_and_site()
        url = reverse("public_websites:btp_works", args=[company.slug])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_btp_emergency_returns_200(self):
        company, site = self._make_company_and_site()
        url = reverse("public_websites:btp_emergency", args=[company.slug])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_btp_portfolio_returns_200(self):
        company, site = self._make_company_and_site()
        url = reverse("public_websites:btp_portfolio", args=[company.slug])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_btp_reviews_returns_200(self):
        company, site = self._make_company_and_site()
        url = reverse("public_websites:btp_reviews", args=[company.slug])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_btp_contact_returns_200(self):
        company, site = self._make_company_and_site()
        url = reverse("public_websites:btp_contact", args=[company.slug])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_btp_client_access_returns_200(self):
        company, site = self._make_company_and_site()
        url = reverse("public_websites:btp_client_access", args=[company.slug])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_btp_blog_returns_200(self):
        company, site = self._make_company_and_site()
        url = reverse("public_websites:btp_blog", args=[company.slug])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_btp_home_contains_client_portal_link(self):
        """Le bouton espace client doit pointer vers le login portail."""
        company, site = self._make_company_and_site()
        url = reverse("public_websites:btp_home", args=[company.slug])
        response = self.client.get(url)
        self.assertContains(response, "/client/")

    def test_btp_client_access_contains_login_link(self):
        """La page espace client doit avoir un lien vers /client/."""
        company, site = self._make_company_and_site()
        url = reverse("public_websites:btp_client_access", args=[company.slug])
        response = self.client.get(url)
        self.assertContains(response, "/client/")

    def test_emergency_form_creates_request(self):
        """La soumission du formulaire urgence cree un BTPEmergencyRequest."""
        from apps.websites.models import BTPEmergencyRequest
        company, site = self._make_company_and_site()
        url = reverse("public_websites:btp_emergency", args=[company.slug])
        data = {
            "first_name":     "Jean",
            "last_name":      "Dupont",
            "phone":          "06 12 34 56 78",
            "email":          "jean@example.com",
            "emergency_type": "electricite",
            "address":        "10 rue de la Paix, Paris",
            "description":    "Panne complete de courant",
            "wants_callback": "on",
            "website_url_field": "",   # honeypot vide
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(BTPEmergencyRequest.objects.filter(website=site).count(), 1)
        req = BTPEmergencyRequest.objects.get(website=site)
        self.assertEqual(req.first_name, "Jean")
        self.assertEqual(req.emergency_type, "electricite")

    def test_spam_honeypot_blocks_emergency(self):
        """Le honeypot bloque les soumissions spam."""
        from apps.websites.models import BTPEmergencyRequest
        company, site = self._make_company_and_site()
        url = reverse("public_websites:btp_emergency", args=[company.slug])
        data = {
            "first_name":       "Spammer",
            "last_name":        "Bot",
            "phone":            "00 00 00 00 00",
            "emergency_type":   "autre",
            "address":          "Spam",
            "description":      "Spam",
            "website_url_field":"http://spam.com",   # honeypot rempli
        }
        self.client.post(url, data)
        self.assertEqual(BTPEmergencyRequest.objects.filter(website=site).count(), 0)

    def test_access_request_form_creates_record(self):
        """La demande d'acces cree un BTPClientAccessRequest."""
        from apps.websites.models import BTPClientAccessRequest
        company, site = self._make_company_and_site()
        url = reverse("public_websites:btp_client_access", args=[company.slug])
        data = {
            "form_type":        "access_request",
            "first_name":       "Marie",
            "last_name":        "Martin",
            "email":            "marie@example.com",
            "phone":            "06 98 76 54 32",
            "reference":        "DEV-2024-001",
            "message":          "Je souhaite acceder a mon espace.",
            "website_url_field":"",
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(BTPClientAccessRequest.objects.filter(website=site).count(), 1)

    def test_portfolio_filter(self):
        """Le filtre par type de travaux fonctionne."""
        from apps.websites.models import BTPPortfolioProject
        company, site = self._make_company_and_site()
        BTPPortfolioProject.objects.create(website=site, title="Elec 1", work_type="electricite", is_published=True)
        BTPPortfolioProject.objects.create(website=site, title="Plomb 1", work_type="plomberie", is_published=True)

        url = reverse("public_websites:btp_portfolio", args=[company.slug])
        response = self.client.get(url + "?type=electricite")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Elec 1")

    def test_reviews_avg_rating(self):
        """La note moyenne est calculee correctement."""
        from apps.websites.models import BTPWebsiteReview
        company, site = self._make_company_and_site()
        BTPWebsiteReview.objects.create(website=site, customer_name="A", rating=4, comment="Bien", is_published=True)
        BTPWebsiteReview.objects.create(website=site, customer_name="B", rating=5, comment="Excellent", is_published=True)

        url = reverse("public_websites:btp_reviews", args=[company.slug])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("avg_rating", response.context)
        self.assertAlmostEqual(response.context["avg_rating"], 4.5)

    def test_unknown_company_returns_404(self):
        """Un slug inexistant retourne 404."""
        url = reverse("public_websites:btp_home", args=["societe-inexistante"])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


@override_settings(STATICFILES_STORAGE=SIMPLE_STORAGE)
class BTPModelsTest(TestCase):
    """Tests des modeles BTP."""

    def _make_site(self):
        from apps.core.models import Company
        from apps.websites.models import Website
        company = Company.objects.create(name="BTP Co", slug="btp-co")
        return Website.objects.create(
            company=company, name="BTP Site", slug="btp-co",
            site_type="btp", is_active=True,
        )

    def test_portfolio_project_str(self):
        from apps.websites.models import BTPPortfolioProject
        site = self._make_site()
        p = BTPPortfolioProject.objects.create(
            website=site, title="Renovation cuisine", work_type="cuisine"
        )
        self.assertIn("Renovation cuisine", str(p))

    def test_portfolio_project_auto_slug(self):
        from apps.websites.models import BTPPortfolioProject
        site = self._make_site()
        p = BTPPortfolioProject.objects.create(
            website=site, title="Installation electrique", work_type="electricite"
        )
        self.assertTrue(p.slug)
        self.assertIn("installation", p.slug)

    def test_review_str(self):
        from apps.websites.models import BTPWebsiteReview
        site = self._make_site()
        r = BTPWebsiteReview.objects.create(
            website=site, customer_name="Dupont", rating=5, comment="Super"
        )
        self.assertIn("5/5", str(r))

    def test_emergency_request_str(self):
        from apps.websites.models import BTPEmergencyRequest
        site = self._make_site()
        e = BTPEmergencyRequest.objects.create(
            website=site, first_name="Jean", last_name="Valjean",
            phone="0612345678", emergency_type="electricite",
            address="1 rue Hugo", description="Panne",
        )
        self.assertIn("URGENT", str(e))
