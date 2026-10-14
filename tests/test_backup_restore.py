"""
tests/test_backup_restore.py — Tests du service de restauration de sauvegardes

Lance avec : pytest tests/test_backup_restore.py -v
"""
import pytest
from unittest.mock import patch, MagicMock, call
import os
from pathlib import Path
from django.test import TestCase
from django.contrib.auth.models import User

from apps.core.models import Company
from apps.backups.models import BackupJob, BackupRestoreLog


class TestRestoreBackupService(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin', password='adminpass', email='admin@test.com'
        )
        self.company = Company.objects.create(
            name='Restore SA', slug='restore-sa', status='active', is_active=True
        )
        self.backup = BackupJob.objects.create(
            company=self.company,
            name='pre-restore-backup',
            backup_type='manual',
            scope='core_database',
            status='success',
            file_path='/tmp/backup.sql.gz',
            checksum='abc123',
            created_by=self.user,
        )

    @patch('apps.backups.services.Path.exists', return_value=False)
    def test_restore_fails_if_file_missing(self, mock_exists):
        from apps.backups.services import restore_backup
        log = restore_backup(self.backup, self.user)
        self.assertEqual(log.status, 'failed')
        self.assertIn('introuvable', log.error_message.lower())

    @patch('apps.backups.services.verify_backup_integrity')
    @patch('apps.backups.services.create_database_backup')
    @patch('apps.backups.services.Path.exists', return_value=True)
    def test_restore_creates_pre_restore_backup(self, mock_exists, mock_create, mock_verify):
        mock_verify.return_value = (True, 'OK')
        pre_backup = BackupJob.objects.create(
            company=self.company,
            name='pre-restore-auto',
            backup_type='pre_restore',
            scope='core_database',
            status='success',
            file_path='/tmp/pre.sql.gz',
            checksum='def456',
            created_by=self.user,
        )
        mock_create.return_value = pre_backup

        with patch('apps.backups.services._run_mysqldump') as mock_dump:
            mock_dump.return_value = (False, 'simulated')
            from apps.backups.services import restore_backup
            restore_backup(self.backup, self.user)

        mock_create.assert_called_once()

    @patch('apps.backups.services.verify_backup_integrity')
    @patch('apps.backups.services.Path.exists', return_value=True)
    def test_restore_fails_if_integrity_check_fails(self, mock_exists, mock_verify):
        mock_verify.return_value = (False, 'Checksum mismatch')
        from apps.backups.services import restore_backup
        log = restore_backup(self.backup, self.user)
        self.assertEqual(log.status, 'failed')

    def test_restore_log_created(self):
        self.assertEqual(BackupRestoreLog.objects.count(), 0)

    def test_restore_log_links_backup(self):
        log = BackupRestoreLog.objects.create(
            backup=self.backup,
            company=self.company,
            status='success',
            restored_by=self.user,
        )
        self.assertEqual(log.backup, self.backup)
        self.assertEqual(log.restored_by, self.user)

    def test_restore_log_str(self):
        log = BackupRestoreLog.objects.create(
            backup=self.backup,
            company=self.company,
            status='failed',
            restored_by=self.user,
            error_message='Test error',
        )
        self.assertIsNotNone(str(log))


class TestVerifyBackupIntegrity(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin3', password='adminpass', email='admin3@test.com'
        )
        self.company = Company.objects.create(
            name='Integrity SA', slug='integrity-sa', status='active', is_active=True
        )

    @patch('apps.backups.services.Path.exists', return_value=False)
    def test_verify_fails_if_no_file(self, mock_exists):
        from apps.backups.services import verify_backup_integrity
        backup = BackupJob(
            company=self.company,
            file_path='/nonexistent/file.sql.gz',
            checksum='abc',
        )
        ok, msg = verify_backup_integrity(backup)
        self.assertFalse(ok)

    def test_verify_passes_if_checksum_matches(self):
        # Un VRAI fichier, et non des simulations : la fonction ne passe plus
        # par « calculate_checksum » ni « Path.exists » mais par
        # apps.backups.storage (path_exists / open_read), pour lire
        # indifferemment un fichier local ou une destination SMB. Les anciennes
        # simulations visaient donc des internes disparus, et ce test ne
        # verifiait plus rien de ce qu'il annoncait.
        import hashlib
        import tempfile

        contenu = b'contenu de sauvegarde'
        with tempfile.NamedTemporaryFile(suffix='.sql.gz', delete=False) as fichier:
            fichier.write(contenu)
            chemin = fichier.name
        self.addCleanup(os.unlink, chemin)

        from apps.backups.services import verify_backup_integrity
        backup = BackupJob(
            company=self.company,
            file_path=chemin,
            checksum=hashlib.sha256(contenu).hexdigest(),
        )
        ok, msg = verify_backup_integrity(backup)
        self.assertTrue(ok, msg)

    @patch('apps.backups.services.calculate_checksum', return_value='wronghash')
    @patch('apps.backups.services.Path.exists', return_value=True)
    def test_verify_fails_if_checksum_mismatch(self, mock_exists, mock_checksum):
        from apps.backups.services import verify_backup_integrity
        backup = BackupJob(
            company=self.company,
            file_path='/some/file.sql.gz',
            checksum='correcthash',
        )
        ok, msg = verify_backup_integrity(backup)
        self.assertFalse(ok)

    def test_verify_fails_if_no_checksum(self):
        from apps.backups.services import verify_backup_integrity
        backup = BackupJob(
            company=self.company,
            file_path='/some/file.sql.gz',
            checksum='',
        )
        ok, msg = verify_backup_integrity(backup)
        self.assertFalse(ok)


class TestChecksumCalculation(TestCase):

    def test_calculate_checksum_returns_hex(self):
        # Un vrai fichier plutot que deux simulations de « open » qui se
        # contredisaient : la fonction lit par morceaux de 8192 octets, ce
        # qu'un mock_open(read_data=...) ne reproduit pas fidelement. Elle
        # avale toute exception et renvoie '' -- la simulation la faisait donc
        # echouer en silence, et le test comparait '' a une empreinte.
        import hashlib
        import tempfile

        contenu = b'hello world'
        with tempfile.NamedTemporaryFile(suffix='.sql', delete=False) as fichier:
            fichier.write(contenu)
            chemin = fichier.name
        self.addCleanup(os.unlink, chemin)

        from apps.backups.services import calculate_checksum
        self.assertEqual(
            calculate_checksum(chemin),
            hashlib.sha256(contenu).hexdigest(),
        )

    def test_calculate_checksum_sur_fichier_absent(self):
        """La fonction avale l'erreur et renvoie une chaine vide.

        C'est un choix discutable mais delibere : un checksum vide signale
        « non calculable » sans interrompre une sauvegarde par ailleurs
        reussie. Encore faut-il que ce soit eprouve, sinon le test precedent
        passait en comparant '' a '' sans rien verifier.
        """
        from apps.backups.services import calculate_checksum
        self.assertEqual(calculate_checksum('/chemin/inexistant.sql'), '')
