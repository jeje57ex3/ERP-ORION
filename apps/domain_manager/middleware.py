class CustomDomainResolverMiddleware:
    """
    Résout le domaine de la requête vers une entreprise et une marque Orion.
    Utilisé par les boutiques publiques avec domaines personnalisés.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.custom_domain = None
        request.domain_company = None
        request.domain_brand_key = ''

        host = request.get_host().split(':')[0].lower()

        try:
            from apps.domain_manager.models import CustomDomain
            custom_domain = (
                CustomDomain.objects
                .select_related('company')
                .filter(domain=host, status='active')
                .first()
            )
            if custom_domain:
                request.custom_domain = custom_domain
                request.domain_company = custom_domain.company
                request.domain_brand_key = custom_domain.brand_key
        except Exception:
            pass

        return self.get_response(request)
