from apps.domain_diagnostics.models import (
    DomainDiagnosticTarget,
    DomainIssue,
    DomainRepairLog,
)


def get_company_targets(company):
    if not company:
        return DomainDiagnosticTarget.objects.none()
    return (
        DomainDiagnosticTarget.objects
        .filter(company=company, is_active=True)
        .select_related('website', 'cloudflare_zone')
        .order_by('domain')
    )


def get_open_issues(company):
    if not company:
        return DomainIssue.objects.none()
    return (
        DomainIssue.objects
        .filter(company=company, status='open')
        .select_related('target', 'run')
        .order_by('-detected_at')
    )


def get_recent_repairs(company):
    if not company:
        return DomainRepairLog.objects.none()
    return (
        DomainRepairLog.objects
        .filter(company=company)
        .select_related('target', 'issue')
        .order_by('-executed_at')[:20]
    )
