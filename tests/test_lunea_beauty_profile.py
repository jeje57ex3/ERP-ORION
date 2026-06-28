import pytest
from apps.lunea_beauty_profile.models import BeautyProfile, BeautyRecommendation
from apps.lunea_beauty_profile import services

pytestmark = pytest.mark.django_db


@pytest.fixture
def company(db):
    from apps.core.models import Company
    return Company.objects.create(name='Lunea Test', slug='lunea-test', is_active=True)


@pytest.fixture
def customer(company):
    from apps.crm.models import Customer
    return Customer.objects.create(company=company, name='Marie Martin', email='marie@example.com')


@pytest.fixture
def profile(company, customer):
    return services.create_or_update_profile(
        company, customer,
        skin_type='normal', hair_type='dry',
        allergies=['parabènes'], intolerances='sulfates',
        preferred_brands='Kérastase, L\'Oréal',
        skin_concerns=['acne'], hair_concerns=['fragilité'],
        avoided_ingredients='alcool', notes='Peau sensible',
    )


# ── Model tests ───────────────────────────────────────────────────────────────

def test_beauty_profile_str(profile, customer):
    assert customer.name in str(profile) or 'BeautyProfile' in str(profile)


def test_beauty_profile_brand_key(profile):
    assert profile.brand_key == 'lunea'


def test_beauty_profile_skin_type(profile):
    assert profile.skin_type == 'normal'


def test_beauty_profile_hair_type(profile):
    assert profile.hair_type == 'dry'


def test_beauty_profile_allergies(profile):
    assert 'parabènes' in profile.allergies


# ── Service tests ─────────────────────────────────────────────────────────────

def test_create_profile(company, customer):
    p = services.create_or_update_profile(
        company, customer,
        skin_type='oily', hair_type='normal',
        allergies=[], intolerances='',
        preferred_brands='', skin_concerns=[], hair_concerns=[],
        avoided_ingredients='', notes='',
    )
    assert p.pk is not None
    assert p.skin_type == 'oily'


def test_update_profile_idempotent(company, customer, profile):
    updated = services.create_or_update_profile(
        company, customer,
        skin_type='dry', hair_type='oily',
        allergies=[], intolerances='', preferred_brands='',
        skin_concerns=[], hair_concerns=[], avoided_ingredients='', notes='',
    )
    assert updated.pk == profile.pk
    assert updated.skin_type == 'dry'


def test_add_recommendation(company, profile):
    rec = services.add_recommendation(
        company, profile, 'Crème Hydratante Pro', 'Peau sèche',
        recommendation_type='skincare', brand='Kérastase', score=0.9,
    )
    assert rec.pk is not None
    assert rec.score == 0.9
    assert rec.is_applied is False


def test_mark_recommendation_applied(company, profile):
    rec = services.add_recommendation(
        company, profile, 'Sérum Éclat', 'Anti-tâches',
        recommendation_type='skincare', brand='L\'Oréal', score=0.8,
    )
    services.mark_recommendation_applied(rec)
    rec.refresh_from_db()
    assert rec.is_applied is True
    assert rec.applied_at is not None


def test_get_recommendations_all(company, profile):
    services.add_recommendation(company, profile, 'P1', 'r', recommendation_type='skincare', brand='B', score=0.7)
    services.add_recommendation(company, profile, 'P2', 'r', recommendation_type='haircare', brand='B', score=0.6)
    recs = services.get_recommendations(company, profile, limit=10, only_pending=False)
    assert recs.count() == 2


def test_get_recommendations_only_pending(company, profile):
    rec = services.add_recommendation(company, profile, 'P1', 'r', recommendation_type='skincare', brand='B', score=0.7)
    services.add_recommendation(company, profile, 'P2', 'r', recommendation_type='skincare', brand='B', score=0.5)
    services.mark_recommendation_applied(rec)
    pending = services.get_recommendations(company, profile, limit=10, only_pending=True)
    assert pending.count() == 1


def test_get_recommendations_limit(company, profile):
    for i in range(5):
        services.add_recommendation(company, profile, f'P{i}', 'r', recommendation_type='skincare', brand='B', score=0.5)
    limited = services.get_recommendations(company, profile, limit=3, only_pending=False)
    assert limited.count() == 3


def test_get_beauty_stats_empty(company):
    stats = services.get_beauty_stats(company)
    assert stats['total_profiles'] == 0
    assert stats['total_recommendations'] == 0


def test_get_beauty_stats_with_data(company, profile):
    services.add_recommendation(company, profile, 'P1', 'r', recommendation_type='skincare', brand='B', score=0.8)
    rec = services.add_recommendation(company, profile, 'P2', 'r', recommendation_type='skincare', brand='B', score=0.7)
    services.mark_recommendation_applied(rec)
    stats = services.get_beauty_stats(company)
    assert stats['total_profiles'] == 1
    assert stats['total_recommendations'] == 2
    assert stats['applied_recommendations'] == 1
    assert stats['pending_recommendations'] == 1


def test_beauty_profile_isolation(company, customer):
    from apps.core.models import Company
    other_company = Company.objects.create(name='Other', slug='other', is_active=True)
    p1 = services.create_or_update_profile(
        company, customer, skin_type='normal', hair_type='normal',
        allergies=[], intolerances='', preferred_brands='',
        skin_concerns=[], hair_concerns=[], avoided_ingredients='', notes='',
    )
    stats_company = services.get_beauty_stats(company)
    stats_other = services.get_beauty_stats(other_company)
    assert stats_company['total_profiles'] == 1
    assert stats_other['total_profiles'] == 0


def test_recommendation_score_range(company, profile):
    rec = services.add_recommendation(
        company, profile, 'Produit Test', 'Raison test',
        recommendation_type='makeup', brand='TestBrand', score=1.0,
    )
    assert 0.0 <= rec.score <= 1.0
