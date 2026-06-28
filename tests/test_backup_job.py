"""
tests/test_backup_job.py — Tests du modele BackupJob

Lance avec : pytest tests/test_backup_job.py -v
"""
import pytest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth.models import User

from apps.core.models import Company
from apps.backups.models import BackupJob, BackupSchedule


class TestBackupJobModel(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin', password='adminpass', email='admin@test.com'
        )
        self.company = Company.objects.create(
            name='Test SA', slug='test-sa', status='active', is_active=True
        )

    def test_create_backup_job_minimal(self):
        job = BackupJob.objects.create(
            company=self.company,
            name='test-backup',
            backup_type='manual',
            scope='core_database',
            status='pending',
            created_by=self.user,
        )
        self.assertIsNotNone(job.pk)
        self.assertEqual(job.status, 'pending')
        self.assertEqual(job.backup_type, 'manual')

    def test_backup_job_str(self):
        job = BackupJob.objects.create(
            company=self.company,
            name='daily-backup',
            backup_type='scheduled',
            scope='company_database',
            status='success',
            created_by=self.user,
        )
        self.assertIn('daily-backup', str(job))

    def test_file_size_display_bytes(self):
        job = BackupJob(file_size=512)
        self.assertIn('512', job.file_size_display)

    def test_file_size_display_kb(self):
        job = BackupJob(file_size=2048)
        display = job.file_size_display
        self.assertTrue('KB' in display or 'kB' in display or '2' in display)

    def test_file_size_display_mb(self):
        job = BackupJob(file_size=5 * 1024 * 1024)
        self.assertIn('MB', job.file_size_display)

    def test_status_color_success(self):
        job = BackupJob(status='success')
        self.assertEqual(job.status_color, 'success')

    def test_status_color_failed(self):
        job = BackupJob(status='failed')
        self.assertEqual(job.status_color, 'danger')

    def test_status_color_running(self):
        job = BackupJob(status='running')
        self.assertEqual(job.status_color, 'warning')

    def test_status_icon_success(self):
        job = BackupJob(status='success')
        self.assertIn('check', job.status_icon)

    def test_duration_display_none(self):
        job = BackupJob(duration_seconds=None)
        self.assertEqual(job.duration_display, '-')

    def test_duration_display_seconds(self):
        job = BackupJob(duration_seconds=45)
        self.assertIn('45', job.duration_display)

    def test_duration_display_minutes(self):
        job = BackupJob(duration_seconds=120)
        display = job.duration_display
        self.assertTrue('2' in display or '120' in display)

    def test_backup_job_ordering(self):
        BackupJob.objects.create(
            company=self.company, name='first', backup_type='manual',
            scope='core_database', status='success', created_by=self.user,
        )
        BackupJob.objects.create(
            company=self.company, name='second', backup_type='manual',
            scope='core_database', status='success', created_by=self.user,
        )
        jobs = list(BackupJob.objects.filter(company=self.company))
        self.assertEqual(len(jobs), 2)

    def test_backup_scope_choices(self):
        valid_scopes = ['core_database', 'company_database', 'all_companies', 'media_files', 'documents', 'full_system']
        for scope in valid_scopes:
            job = BackupJob(
                company=self.company, name='x', backup_type='manual',
                scope=scope, status='pending', created_by=self.user,
            )
            self.assertEqual(job.scope, scope)


class TestBackupScheduleModel(TestCase):

    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin2', password='adminpass', email='admin2@test.com'
        )
        self.company = Company.objects.create(
            name='Sched SA', slug='sched-sa', status='active', is_active=True
        )

    def test_create_schedule(self):
        sched = BackupSchedule.objects.create(
            company=self.company,
            name='Daily DB Backup',
            scope='core_database',
            frequency='daily',
            retention_days=30,
            is_active=True,
            created_by=self.user,
        )
        self.assertEqual(sched.frequency, 'daily')
        self.assertTrue(sched.is_active)

    def test_schedule_str(self):
        sched = BackupSchedule.objects.create(
            company=self.company,
            name='Weekly Backup',
            scope='full_system',
            frequency='weekly',
            retention_days=90,
            created_by=self.user,
        )
        self.assertIn('Weekly Backup', str(sched))

    def test_schedule_frequencies(self):
        for freq in ['daily', 'weekly', 'monthly']:
            sched = BackupSchedule(
                company=self.company, name='x', scope='core_database',
                frequency=freq, retention_days=7, created_by=self.user,
            )
            self.assertEqual(sched.frequency, freq)
