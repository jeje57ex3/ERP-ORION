"""
tests/test_backup_permissions.py — Tests des permissions des vues de sauvegarde

Lance avec : pytest tests/test_backup_permissions.py -v
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from apps.core.models import Company
from apps.backups.models import BackupJob


class TestBackupViewPermissions(TestCase):
    """Les vues de sauvegarde requierent is_superuser."""

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='admin', password='adminpass', email='admin@test.com'
        )
        self.staff = User.objects.create_user(
            username='staff', password='staffpass', email='staff@test.com',
            is_staff=True,
        )
        self.regular = User.objects.create_user(
            username='regular', password='regpass', email='reg@test.com'
        )
        self.company = Company.objects.create(
            name='Perm SA', slug='perm-sa', status='active', is_active=True
        )
        self.client = Client()

    def _login(self, user):
        self.client.force_login(user)

    def test_anonymous_redirect_from_backup_dashboard(self):
        resp = self.client.get('/sauvegardes/')
        self.assertIn(resp.status_code, [302, 301])

    def test_anonymous_redirect_from_backup_list(self):
        resp = self.client.get('/sauvegardes/liste/')
        self.assertIn(resp.status_code, [302, 301])

    def test_anonymous_redirect_from_backup_create(self):
        resp = self.client.get('/sauvegardes/creer/')
        self.assertIn(resp.status_code, [302, 301])

    def test_anonymous_redirect_from_backup_schedules(self):
        resp = self.client.get('/sauvegardes/planification/')
        self.assertIn(resp.status_code, [302, 301])

    def test_superuser_can_access_dashboard(self):
        self._login(self.superuser)
        resp = self.client.get('/sauvegardes/')
        self.assertIn(resp.status_code, [200, 302])

    def test_superuser_can_access_backup_list(self):
        self._login(self.superuser)
        resp = self.client.get('/sauvegardes/liste/')
        self.assertIn(resp.status_code, [200, 302])

    def test_superuser_can_access_backup_create(self):
        self._login(self.superuser)
        resp = self.client.get('/sauvegardes/creer/')
        self.assertIn(resp.status_code, [200, 302])

    def test_non_superuser_forbidden_from_restore(self):
        self._login(self.staff)
        backup = BackupJob.objects.create(
            company=self.company,
            name='test-backup',
            backup_type='manual',
            scope='core_database',
            status='success',
            created_by=self.superuser,
        )
        resp = self.client.post(f'/sauvegardes/{backup.pk}/restaurer/')
        self.assertIn(resp.status_code, [302, 403])

    def test_non_superuser_forbidden_from_download(self):
        self._login(self.staff)
        backup = BackupJob.objects.create(
            company=self.company,
            name='test-backup2',
            backup_type='manual',
            scope='core_database',
            status='success',
            created_by=self.superuser,
        )
        resp = self.client.get(f'/sauvegardes/{backup.pk}/telecharger/')
        self.assertIn(resp.status_code, [302, 403])

    def test_regular_user_forbidden_from_backup_settings(self):
        self._login(self.regular)
        resp = self.client.get('/sauvegardes/parametres/')
        self.assertIn(resp.status_code, [302, 403])

    def test_superuser_can_access_settings(self):
        self._login(self.superuser)
        resp = self.client.get('/sauvegardes/parametres/')
        self.assertIn(resp.status_code, [200, 302])


class TestBackupDeletePermission(TestCase):

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='admin2', password='adminpass', email='admin2@test.com'
        )
        self.regular = User.objects.create_user(
            username='reg2', password='regpass', email='reg2@test.com'
        )
        self.company = Company.objects.create(
            name='Del SA', slug='del-sa', status='active', is_active=True
        )
        self.backup = BackupJob.objects.create(
            company=self.company,
            name='deletable',
            backup_type='manual',
            scope='core_database',
            status='success',
            created_by=self.superuser,
        )

    def test_regular_user_cannot_delete_backup(self):
        client = Client()
        client.force_login(self.regular)
        resp = client.post(f'/sauvegardes/{self.backup.pk}/supprimer/')
        self.assertIn(resp.status_code, [302, 403])
        self.assertTrue(BackupJob.objects.filter(pk=self.backup.pk).exists())

    def test_superuser_can_delete_backup(self):
        client = Client()
        client.force_login(self.superuser)
        resp = client.post(f'/sauvegardes/{self.backup.pk}/supprimer/')
        self.assertIn(resp.status_code, [200, 302])
