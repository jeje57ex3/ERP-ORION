"""
tests/test_private_saas_permissions.py — Tests permissions SaaS privé
"""
from django.test import TestCase
from unittest.mock import patch, MagicMock


class TestCompanyHasModule(TestCase):

    def test_superuser_always_has_access(self):
        """Un superuser a accès à tous les modules."""
        from apps.private_saas.permissions import user_can_access_module
        user = MagicMock(is_authenticated=True, is_superuser=True)
        self.assertTrue(user_can_access_module(user, None, 'crm'))
        self.assertTrue(user_can_access_module(user, None, 'btp'))

    def test_no_company_refuse_tout_module(self):
        """Sans entreprise, aucun module n'est accessible.

        Ce test attendait l'inverse — « pas d'entreprise, pas de filtre,
        retourne True » — et ce fichier contenait donc deux intentions
        contradictoires : celle-ci ouvrait tout, tandis que
        test_non_superuser_no_super_admin exigeait que le menu Super Admin
        reste masque.

        Trois raisons de trancher pour le refus :

          - « module_access.company_has_module », qui alimente les
            decorateurs d'acces, repond deja False dans ce cas. Deux reponses
            opposees a la meme question, c'etait le vrai defaut ;
          - sans entreprise, aucune donnee metier ne peut etre cloisonnee :
            ouvrir n'a pas de sens dans un ERP multi-entreprises ;
          - ouvrir faisait proposer au menu tous les modules, y compris ceux
            que l'exploitant n'a pas souscrits.
        """
        from apps.private_saas.permissions import company_has_module
        self.assertFalse(company_has_module(None, 'crm'))

    def test_unauthenticated_denied(self):
        """Un utilisateur non authentifié est refusé."""
        from apps.private_saas.permissions import user_can_access_module
        user = MagicMock(is_authenticated=False, is_superuser=False)
        self.assertFalse(user_can_access_module(user, MagicMock(), 'crm'))

    def test_enabled_module_allowed(self):
        """Un module activé est accessible."""
        from apps.core.models import Company
        from apps.private_saas.models import CompanyModule
        from apps.private_saas.permissions import company_has_module

        # De vraies lignes, et non un gestionnaire simulé : la propriété à
        # éprouver est que seul un module « is_enabled » passe, et une
        # simulation la rendrait vraie par construction.
        company = Company.objects.create(name='Modules SA', slug='modules-sa')
        CompanyModule.objects.create(
            company=company, module_code='crm', module_name='CRM',
            is_enabled=True,
        )
        self.assertTrue(company_has_module(company, 'crm'))

    def test_disabled_module_blocked(self):
        """Un module désactivé n'est pas accessible."""
        from apps.core.models import Company
        from apps.private_saas.models import CompanyModule
        from apps.private_saas.permissions import company_has_module

        company = Company.objects.create(name='Modules SA', slug='modules-sa')
        CompanyModule.objects.create(
            company=company, module_code='btp', module_name='BTP',
            is_enabled=False,
        )
        self.assertFalse(company_has_module(company, 'btp'))

    def test_module_jamais_declare_est_refuse(self):
        """Un module absent de la table n'est pas accessible non plus.

        Distinct du cas « désactivé » : l'absence de ligne et une ligne à
        faux doivent donner le même refus, sans quoi activer un module
        reviendrait à oublier de le déclarer.
        """
        from apps.core.models import Company
        from apps.private_saas.permissions import company_has_module

        company = Company.objects.create(name='Vide SA', slug='vide-sa')
        self.assertFalse(company_has_module(company, 'ecommerce'))


class TestFilterNavModules(TestCase):

    def test_superuser_sees_all_modules(self):
        """Un superuser voit tous les modules incluant Super Admin."""
        from apps.private_saas.permissions import filter_nav_modules
        nav = [
            {'id': 'crm', 'label': 'CRM'},
            {'id': 'private_saas', 'label': 'Super Admin', 'super_admin_only': True},
            {'id': 'dashboard', 'label': 'Dashboard'},
        ]
        user = MagicMock(is_superuser=True)
        result = filter_nav_modules(nav, None, user)
        ids = [m['id'] for m in result]
        self.assertIn('private_saas', ids)

    def test_non_superuser_no_super_admin(self):
        """Un utilisateur normal ne voit pas le Super Admin."""
        from apps.private_saas.permissions import filter_nav_modules
        nav = [
            {'id': 'private_saas', 'label': 'Super Admin', 'super_admin_only': True},
            {'id': 'dashboard', 'label': 'Dashboard'},
        ]
        user = MagicMock(is_superuser=False)
        result = filter_nav_modules(nav, None, user)
        ids = [m['id'] for m in result]
        self.assertNotIn('private_saas', ids)
        self.assertIn('dashboard', ids)
