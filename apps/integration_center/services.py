from django.utils import timezone
from .models import IntegrationConfig, IntegrationSyncLog


def create_integration(company, integration_type, name, config, *,
                       sync_interval_minutes=60, created_by=None):
    return IntegrationConfig.objects.create(
        company=company, integration_type=integration_type, name=name,
        config=config, sync_interval_minutes=sync_interval_minutes,
        created_by=created_by,
    )


def update_integration_config(integration, config):
    integration.config = config
    integration.updated_at = timezone.now()
    integration.save(update_fields=['config', 'updated_at'])
    return integration


def start_sync(company, integration):
    return IntegrationSyncLog.objects.create(
        company=company, integration=integration, status='running',
    )


def finish_sync(log, records_synced=0, records_failed=0, errors=None, success=True):
    log.status = 'success' if success and records_failed == 0 else ('partial' if records_synced > 0 else 'failed')
    log.records_synced = records_synced
    log.records_failed = records_failed
    log.errors = errors or []
    log.finished_at = timezone.now()
    log.save(update_fields=['status', 'records_synced', 'records_failed', 'errors', 'finished_at'])
    log.integration.last_sync_at = timezone.now()
    log.integration.save(update_fields=['last_sync_at'])
    return log


def get_active_integrations(company, integration_type=None):
    qs = IntegrationConfig.objects.filter(company=company, is_active=True)
    if integration_type:
        qs = qs.filter(integration_type=integration_type)
    return qs.order_by('name')


def get_sync_logs(company, integration=None, limit=50):
    qs = IntegrationSyncLog.objects.filter(company=company).select_related('integration')
    if integration:
        qs = qs.filter(integration=integration)
    return qs.order_by('-started_at')[:limit]


def get_integration_stats(company):
    configs = IntegrationConfig.objects.filter(company=company)
    logs = IntegrationSyncLog.objects.filter(company=company)
    return {
        'total': configs.count(),
        'active': configs.filter(is_active=True).count(),
        'total_syncs': logs.count(),
        'failed_syncs': logs.filter(status='failed').count(),
        'last_sync': logs.order_by('-started_at').first(),
    }
