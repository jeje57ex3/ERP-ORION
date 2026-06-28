from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from .models import BeautyProfile, BeautyRecommendation
from . import services


@login_required
def dashboard(request):
    company = request.current_company
    stats = services.get_beauty_stats(company)
    recent = BeautyProfile.objects.filter(company=company).order_by('-updated_at')[:5]
    return render(request, 'lunea_beauty_profile/dashboard.html', {
        'stats': stats,
        'recent': recent,
    })


@login_required
def profile_list(request):
    company = request.current_company
    profiles = BeautyProfile.objects.filter(company=company).select_related('customer').order_by('-updated_at')
    return render(request, 'lunea_beauty_profile/profile_list.html', {
        'profiles': profiles,
    })


@login_required
def profile_detail(request, pk):
    company = request.current_company
    profile = get_object_or_404(BeautyProfile, pk=pk, company=company)
    recommendations = services.get_recommendations(company, profile, limit=20, only_pending=False)
    return render(request, 'lunea_beauty_profile/profile_detail.html', {
        'profile': profile,
        'recommendations': recommendations,
    })


@login_required
def mark_applied(request, pk):
    company = request.current_company
    rec = get_object_or_404(BeautyRecommendation, pk=pk, company=company)
    if request.method == 'POST':
        services.mark_recommendation_applied(rec)
        messages.success(request, 'Recommandation marquée comme appliquée.')
    from django.shortcuts import redirect
    return redirect('lunea_beauty_profile:profile_detail', pk=rec.profile_id)


@login_required
def recommendations_list(request):
    """Toutes les recommandations — alias /erp/lunea/beauty-profiles/recommendations/"""
    company = request.current_company
    only_pending = request.GET.get('pending') == '1'
    qs = BeautyRecommendation.objects.filter(company=company).select_related(
        'profile', 'profile__customer'
    ).order_by('-score', '-created_at')
    if only_pending:
        qs = qs.filter(is_applied=False)
    return render(request, 'lunea_beauty_profile/recommendations.html', {
        'recommendations': qs[:100],
        'only_pending': only_pending,
    })


@login_required
def diagnostics_view(request):
    """Vue diagnostics beauté — /erp/lunea/beauty-profiles/diagnostics/"""
    company = request.current_company
    profiles = BeautyProfile.objects.filter(company=company).select_related('customer').order_by('-updated_at')
    skin_breakdown = {}
    for p in profiles:
        skin_breakdown[p.get_skin_type_display()] = skin_breakdown.get(p.get_skin_type_display(), 0) + 1
    return render(request, 'lunea_beauty_profile/diagnostics.html', {
        'profiles': profiles,
        'skin_breakdown': skin_breakdown,
        'total_profiles': profiles.count(),
    })


@login_required
def routines_view(request):
    """Vue routines beauté — /erp/lunea/beauty-profiles/routines/"""
    company = request.current_company
    profiles = BeautyProfile.objects.filter(company=company).select_related(
        'customer'
    ).exclude(skin_concerns=[]).order_by('-updated_at')[:50]
    return render(request, 'lunea_beauty_profile/routines.html', {
        'profiles': profiles,
    })
