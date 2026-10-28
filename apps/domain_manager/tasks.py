try:
    from celery import shared_task

    @shared_task
    def verify_pending_domains():
        from apps.domain_manager.models import CustomDomain
        from apps.domain_manager.services import verify_custom_domain

        domains = CustomDomain.objects.filter(
            status__in=['pending', 'dns_pending', 'dns_valid', 'ssl_pending']
        )
        for domain in domains:
            verify_custom_domain(domain)
        return domains.count()

except ImportError:
    pass
