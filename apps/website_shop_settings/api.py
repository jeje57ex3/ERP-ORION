from django.core.exceptions import ObjectDoesNotExist
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.website_shop_settings.models import ShippingMethod
from apps.website_shop_settings.selectors import (
    get_checkout_public_settings,
    get_public_shop_settings,
    get_shop_settings,
)
from apps.website_shop_settings.serializers import ShippingMethodSerializer


def _get_company(request):
    return getattr(request, 'current_company', None)


@api_view(['GET'])
@permission_classes([AllowAny])
def public_shop_settings_api(request, brand_key):
    company = _get_company(request)
    if not company:
        return Response({'error': 'Entreprise non trouvée.'}, status=404)
    try:
        data = get_public_shop_settings(company, brand_key)
    except ObjectDoesNotExist:
        return Response({'error': 'Paramètres introuvables.'}, status=404)
    return Response(data)


@api_view(['GET'])
@permission_classes([AllowAny])
def checkout_settings_api(request, brand_key):
    company = _get_company(request)
    if not company:
        return Response({'error': 'Entreprise non trouvée.'}, status=404)
    try:
        data = get_checkout_public_settings(company, brand_key)
    except ObjectDoesNotExist:
        return Response({'error': 'Paramètres introuvables.'}, status=404)
    return Response(data)


@api_view(['GET'])
@permission_classes([AllowAny])
def shipping_methods_api(request, brand_key):
    company = _get_company(request)
    if not company:
        return Response({'error': 'Entreprise non trouvée.'}, status=404)
    try:
        shop_settings = get_shop_settings(company, brand_key)
    except ObjectDoesNotExist:
        return Response({'error': 'Paramètres introuvables.'}, status=404)
    methods = ShippingMethod.objects.filter(
        shop_settings=shop_settings,
        is_active=True,
    ).order_by('sort_order', 'name')
    return Response(ShippingMethodSerializer(methods, many=True).data)


@api_view(['GET'])
@permission_classes([AllowAny])
def legal_pages_api(request, brand_key):
    company = _get_company(request)
    if not company:
        return Response({'error': 'Entreprise non trouvée.'}, status=404)
    try:
        shop_settings = get_shop_settings(company, brand_key)
        legal = shop_settings.legal_settings
    except ObjectDoesNotExist:
        return Response({'error': 'Paramètres légaux introuvables.'}, status=404)
    return Response({
        'cgv': legal.cgv_content,
        'privacy': legal.privacy_policy_content,
        'cookies': legal.cookie_policy_content,
        'legal_notice': legal.legal_notice_content,
        'shipping_returns': legal.shipping_returns_content,
        'company_name': legal.company_name,
        'company_address': legal.company_address,
        'company_siret': legal.company_siret,
        'company_vat_number': legal.company_vat_number,
        'publication_director': legal.publication_director,
        'hosting_provider': legal.hosting_provider,
    })
