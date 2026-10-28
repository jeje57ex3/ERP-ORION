from django.test import TestCase
from django.urls import reverse


class OrionWebsitePagesTests(TestCase):
    def test_home_page(self):
        response = self.client.get(reverse("orion_website:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Orion ERP")

    def test_modules_page(self):
        response = self.client.get(reverse("orion_website:modules"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Modules")

    def test_downloads_page(self):
        response = self.client.get(reverse("orion_website:downloads"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Windows")
        self.assertContains(response, "Android")

    def test_login_link_present(self):
        response = self.client.get(reverse("orion_website:home"))
        self.assertContains(response, "Connexion")

    def test_faq_page(self):
        response = self.client.get(reverse("orion_website:faq"))
        self.assertEqual(response.status_code, 200)

    def test_contact_page(self):
        response = self.client.get(reverse("orion_website:contact"))
        self.assertEqual(response.status_code, 200)

    def test_install_windows_page(self):
        response = self.client.get(reverse("orion_website:install_windows"))
        self.assertEqual(response.status_code, 200)

    def test_install_android_page(self):
        response = self.client.get(reverse("orion_website:install_android"))
        self.assertEqual(response.status_code, 200)

    def test_module_detail_page(self):
        response = self.client.get(reverse("orion_website:module_detail", args=["dashboard"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")

    def test_module_detail_404(self):
        response = self.client.get(reverse("orion_website:module_detail", args=["unknown-module"]))
        self.assertEqual(response.status_code, 404)

    def test_faq_has_search(self):
        response = self.client.get(reverse("orion_website:faq"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rechercher dans la FAQ")

    def test_modules_categories_present(self):
        response = self.client.get(reverse("orion_website:modules"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Base ERP")
        self.assertContains(response, "E-commerce &amp; ventes")

    def test_modules_page_lists_all_modules(self):
        response = self.client.get(reverse("orion_website:modules"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tous les modules Orion ERP")
        self.assertContains(response, "E-commerce")
        self.assertContains(response, "Formations internes")
        self.assertContains(response, "Application Windows")
        self.assertContains(response, "Application Android")

    def test_module_detail_dashboard(self):
        response = self.client.get(reverse("orion_website:module_detail", args=["dashboard"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")
        self.assertContains(response, "Pourquoi utiliser ce module")

    def test_module_detail_ecommerce(self):
        response = self.client.get(reverse("orion_website:module_detail", args=["ecommerce"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Gestion boutique")

    def test_module_detail_unknown_404(self):
        response = self.client.get(reverse("orion_website:module_detail", args=["module-inconnu"]))
        self.assertEqual(response.status_code, 404)
