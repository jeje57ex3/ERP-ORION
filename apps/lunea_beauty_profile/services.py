from django.utils import timezone
from .models import BeautyProfile, BeautyRecommendation


def create_or_update_profile(company, customer, *, skin_type='unknown', hair_type='unknown',
                              allergies=None, intolerances=None, preferred_brands=None,
                              skin_concerns=None, hair_concerns=None,
                              avoided_ingredients=None, notes='', created_by=None):
    profile, created = BeautyProfile.objects.update_or_create(
        company=company, customer=customer,
        defaults={
            'brand_key': 'lunea',
            'skin_type': skin_type,
            'hair_type': hair_type,
            'allergies': allergies or [],
            'intolerances': intolerances or [],
            'preferred_brands': preferred_brands or [],
            'skin_concerns': skin_concerns or [],
            'hair_concerns': hair_concerns or [],
            'avoided_ingredients': avoided_ingredients or [],
            'notes': notes,
        },
    )
    if created and created_by:
        profile.created_by = created_by
        profile.save(update_fields=['created_by'])
    return profile


def add_recommendation(company, profile, product_name, reason, *,
                       recommendation_type='product', brand='', score=0.8, metadata=None):
    return BeautyRecommendation.objects.create(
        company=company, profile=profile,
        recommendation_type=recommendation_type,
        product_name=product_name, brand=brand,
        reason=reason, score=score,
        metadata=metadata or {},
    )


def mark_recommendation_applied(recommendation):
    recommendation.is_applied = True
    recommendation.applied_at = timezone.now()
    recommendation.save(update_fields=['is_applied', 'applied_at'])
    return recommendation


def get_recommendations(company, profile, *, limit=10, only_pending=False):
    qs = BeautyRecommendation.objects.filter(company=company, profile=profile)
    if only_pending:
        qs = qs.filter(is_applied=False)
    return qs.order_by('-score', '-created_at')[:limit]


def get_profile_for_customer(company, customer):
    try:
        return BeautyProfile.objects.get(company=company, customer=customer)
    except BeautyProfile.DoesNotExist:
        return None


def get_beauty_stats(company):
    profiles = BeautyProfile.objects.filter(company=company, brand_key='lunea')
    recs = BeautyRecommendation.objects.filter(company=company)
    from django.db.models import Count
    skin_breakdown = dict(
        profiles.values_list('skin_type').annotate(n=Count('id')).values_list('skin_type', 'n')
    )
    return {
        'total_profiles': profiles.count(),
        'total_recommendations': recs.count(),
        'applied_recommendations': recs.filter(is_applied=True).count(),
        'pending_recommendations': recs.filter(is_applied=False).count(),
        'skin_breakdown': skin_breakdown,
    }
