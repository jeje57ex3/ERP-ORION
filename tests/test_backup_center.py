"""
tests/test_backup_center.py
Tests du module Centre de Sauvegardes.
"""
import pytest
from django.utils import timezone
from apps.core.models import Company
from apps.backup_center.models import BackupJob, BackupRun
from apps.backup_center.services import (
    create_job, start_backup_run, finish_backup_run,
    get_backup_runs, get_recent_failures, get_backup_stats,
)


@pytest.fixture
def company(db):
    return Company.objects.create(name='Backup SA', slug='backup-sa', status='active', is_active=True)


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(username='bk_user', password='pass')


@pytest.fixture
def job(db, company, user):
    return create_job(company, 'BDD Quotidienne', 'full_db',
                      schedule='daily', storage_target='local', created_by=user)


class TestCreateJob:
    def test_creates_job(self, db, company, user):
        j = create_job(company, 'Media', 'media_files')
        assert j.pk is not None
        assert j.job_type == 'media_files'
        assert j.is_active is True

    def test_defaults(self, db, company):
        j = create_job(company, 'Config', 'config')
        assert j.schedule == 'manual'
        assert j.storage_target == 'local'
        assert j.retention_days == 30

    def test_custom_retention(self, db, company):
        j = create_job(company, 'Long', 'full_db', retention_days=90)
        assert j.retention_days == 90


class TestStartBackupRun:
    def test_creates_run(self, db, company, job, user):
        run = start_backup_run(company, job, triggered_by=user)
        assert run.pk is not None
        assert run.status == 'running'

    def test_updates_job_last_run(self, db, company, job):
        start_backup_run(company, job)
        job.refresh_from_db()
        assert job.last_run_at is not None
        assert job.last_status == 'running'


class TestFinishBackupRun:
    def test_success(self, db, company, job, user):
        run = start_backup_run(company, job)
        finish_backup_run(run, success=True, file_path='/backups/db.sql.gz',
                          file_size_bytes=1024 * 1024 * 50)
        run.refresh_from_db()
        assert run.status == 'success'
        assert run.finished_at is not None
        assert run.file_size_bytes == 1024 * 1024 * 50

    def test_failure(self, db, company, job):
        run = start_backup_run(company, job)
        finish_backup_run(run, success=False, error_message='Connection timeout')
        run.refresh_from_db()
        assert run.status == 'failed'
        assert run.error_message == 'Connection timeout'

    def test_updates_job_status(self, db, company, job):
        run = start_backup_run(company, job)
        finish_backup_run(run, success=True)
        job.refresh_from_db()
        assert job.last_status == 'success'

    def test_duration_property(self, db, company, job):
        run = start_backup_run(company, job)
        finish_backup_run(run, success=True)
        run.refresh_from_db()
        assert run.duration_seconds is not None
        assert run.duration_seconds >= 0

    def test_file_size_mb_property(self, db, company, job):
        run = start_backup_run(company, job)
        finish_backup_run(run, file_size_bytes=10 * 1024 * 1024)
        assert run.file_size_mb == 10.0


class TestGetBackupRuns:
    def test_returns_runs(self, db, company, job):
        run = start_backup_run(company, job)
        result = list(get_backup_runs(company))
        assert run in result

    def test_filter_by_job(self, db, company, job):
        job2 = create_job(company, 'Media', 'media_files')
        run1 = start_backup_run(company, job)
        run2 = start_backup_run(company, job2)
        result = list(get_backup_runs(company, job=job))
        assert run1 in result
        assert run2 not in result

    def test_limit_respected(self, db, company, job):
        for _ in range(10):
            start_backup_run(company, job)
        result = list(get_backup_runs(company, limit=5))
        assert len(result) <= 5


class TestGetRecentFailures:
    def test_returns_failed(self, db, company, job):
        run = start_backup_run(company, job)
        finish_backup_run(run, success=False)
        result = list(get_recent_failures(company))
        assert run in result

    def test_excludes_success(self, db, company, job):
        run = start_backup_run(company, job)
        finish_backup_run(run, success=True)
        result = list(get_recent_failures(company))
        assert run not in result


class TestGetBackupStats:
    def test_stats_keys(self, db, company, job):
        run = start_backup_run(company, job)
        finish_backup_run(run, success=True)
        stats = get_backup_stats(company)
        assert 'total_jobs' in stats
        assert 'active_jobs' in stats
        assert 'success_24h' in stats
        assert 'failed_24h' in stats
        assert stats['active_jobs'] >= 1
        assert stats['success_24h'] >= 1
