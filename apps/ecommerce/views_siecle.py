"""
Vues ERP — SIÈCLE ARTICLES, SIÈCLE STATUS, PARRAINAGES, SYNC LOG
"""
import os
import json
import uuid
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q
from django.utils import timezone
from apps.websites.models import (
    StoreProduct, StoreProductImage, StoreProductVariant, StoreCategory,
    LoyaltyAccount, LoyaltyTransaction,
    AffiliateCode, AffiliateReferral,
    SyncLog, Website,
)

ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/jpg'}
MAX_IMAGE_SIZE_MB = 10


def _get_siecle_website(company):
    """Récupère le site SIÈCLE (slug='siecle') de l'entreprise."""
    return Website.objects.filter(
        company=company,
        slug='siecle',
        site_type='ecommerce',
        is_active=True,
    ).first()


def _get_siecle_categories(company):
    """Retourne les catégories actives du site SIÈCLE."""
    website = _get_siecle_website(company)
    if not website:
        return StoreCategory.objects.none()
    return StoreCategory.objects.filter(website=website, is_active=True).order_by('order', 'name')


# ─── ARTICLES ─────────────────────────────────────────────────────────────────

@login_required
def article_list(request):
    company = request.current_company
    website = _get_siecle_website(company)
    qs = StoreProduct.objects.filter(website__company=company) if website else StoreProduct.objects.none()

    status_filter   = request.GET.get('status', '')
    archive_filter  = request.GET.get('archive', '')
    category_filter = request.GET.get('category', '')
    search          = request.GET.get('q', '')

    if status_filter:
        qs = qs.filter(status=status_filter)
    if archive_filter:
        qs = qs.filter(archive_ref=archive_filter)
    if category_filter:
        qs = qs.filter(category__slug=category_filter)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(sku__icontains=search))

    return render(request, 'ecommerce/article_list.html', {
        'page_title': 'Articles SIÈCLE.',
        'articles': qs.select_related('category'),
        'status_choices': StoreProduct.STATUS_CHOICES,
        'categories': _get_siecle_categories(company),
        'status_filter': status_filter,
        'archive_filter': archive_filter,
        'category_filter': category_filter,
        'search': search,
        'total': qs.count(),
    })


@login_required
def article_create(request):
    company = request.current_company
    website = _get_siecle_website(company)
    if not website:
        messages.error(request, 'Aucun site SIÈCLE. configuré pour cette entreprise.')
        return redirect('ecommerce:article_list')

    if request.method == 'POST':
        data = request.POST
        try:
            category_id = data.get('category_id')
            category = None
            if category_id:
                category = StoreCategory.objects.filter(pk=category_id, website=website).first()

            def _parse_json_list(raw):
                try:
                    v = json.loads(raw) if raw else []
                    return v if isinstance(v, list) else []
                except Exception:
                    return []

            def _parse_json_dict(raw):
                try:
                    v = json.loads(raw) if raw else {}
                    return v if isinstance(v, dict) else {}
                except Exception:
                    return {}

            article = StoreProduct.objects.create(
                website=website,
                category=category,
                name=data.get('name', '').strip(),
                sku=data.get('sku', '').strip(),
                archive_ref=data.get('archive_ref', '').strip(),
                short_description=data.get('short_description', '').strip(),
                description=data.get('description', '').strip(),
                price=data.get('price') or 0,
                compare_at_price=data.get('compare_at_price') or None,
                stock_quantity=data.get('stock_quantity') or 0,
                status=data.get('status', 'draft'),
                available_sizes=json.loads(data.get('available_sizes_json', '[]')),
                display_order=data.get('display_order') or 0,
                early_access_type=data.get('early_access_type', 'public'),
                gold_access_start=data.get('gold_access_start') or None,
                public_access_start=data.get('public_access_start') or None,
                # Éditorial
                story_title=data.get('story_title', '').strip(),
                story_content=data.get('story_content', '').strip(),
                selection_reason=data.get('selection_reason', '').strip(),
                usage_note=data.get('usage_note', '').strip(),
                materials=data.get('materials', '').strip(),
                dimensions=data.get('dimensions', '').strip(),
                weight=data.get('weight', '').strip(),
                origin_country=data.get('origin_country', '').strip(),
                condition=data.get('condition', '').strip(),
                care_instructions=data.get('care_instructions', '').strip(),
                shipping_note=data.get('shipping_note', '').strip(),
                return_note=data.get('return_note', '').strip(),
                guarantee_note=data.get('guarantee_note', '').strip(),
                is_siecle_selection='is_siecle_selection' in data,
                is_limited_edition='is_limited_edition' in data,
                edition_quantity=data.get('edition_quantity') or None,
                is_new_arrival='is_new_arrival' in data,
                product_highlights=_parse_json_list(data.get('product_highlights_json', '')),
                technical_details=_parse_json_dict(data.get('technical_details_json', '')),
                faq_items=_parse_json_list(data.get('faq_items_json', '')),
            )
            _create_sync_log(company, article, 'success', 'Article créé dans l\'ERP.')
            messages.success(request, f'Article « {article.name} » créé.')
            return redirect('ecommerce:article_detail', pk=article.pk)
        except Exception as e:
            messages.error(request, f'Erreur lors de la création : {e}')

    return render(request, 'ecommerce/article_form.html', {
        'page_title': 'Créer un article',
        'status_choices': StoreProduct.STATUS_CHOICES,
        'early_access_choices': StoreProduct.EARLY_ACCESS_CHOICES,
        'categories': _get_siecle_categories(company),
        'article': None,
    })


@login_required
def article_detail(request, pk):
    company = request.current_company
    article = get_object_or_404(StoreProduct, pk=pk, website__company=company)
    return render(request, 'ecommerce/article_detail.html', {
        'page_title': article.name,
        'article': article,
        'images': article.images.all(),
        'variants': article.variants.all(),
        'sync_logs': SyncLog.objects.filter(product=article).order_by('-created_at')[:10],
    })


@login_required
def article_edit(request, pk):
    company = request.current_company
    article = get_object_or_404(StoreProduct, pk=pk, website__company=company)

    if request.method == 'POST':
        data = request.POST
        try:
            def _parse_json_list(raw):
                try:
                    v = json.loads(raw) if raw else []
                    return v if isinstance(v, list) else []
                except Exception:
                    return []

            def _parse_json_dict(raw):
                try:
                    v = json.loads(raw) if raw else {}
                    return v if isinstance(v, dict) else {}
                except Exception:
                    return {}

            article.name = data.get('name', article.name).strip()
            article.sku = data.get('sku', article.sku).strip()
            article.archive_ref = data.get('archive_ref', article.archive_ref).strip()
            article.short_description = data.get('short_description', '').strip()
            article.description = data.get('description', '').strip()
            article.price = data.get('price') or article.price
            article.compare_at_price = data.get('compare_at_price') or None
            article.stock_quantity = data.get('stock_quantity') or 0
            article.status = data.get('status', article.status)
            article.display_order = data.get('display_order') or 0
            article.early_access_type = data.get('early_access_type', 'public')
            gold_start = data.get('gold_access_start')
            article.gold_access_start = gold_start if gold_start else None
            pub_start = data.get('public_access_start')
            article.public_access_start = pub_start if pub_start else None
            sizes_json = data.get('available_sizes_json', '')
            if sizes_json:
                article.available_sizes = json.loads(sizes_json)

            category_id = data.get('category_id')
            if category_id:
                article.category = StoreCategory.objects.filter(
                    pk=category_id, website=article.website,
                ).first()
            elif 'category_id' in data:
                article.category = None

            # Éditorial
            article.story_title = data.get('story_title', '').strip()
            article.story_content = data.get('story_content', '').strip()
            article.selection_reason = data.get('selection_reason', '').strip()
            article.usage_note = data.get('usage_note', '').strip()
            article.materials = data.get('materials', '').strip()
            article.dimensions = data.get('dimensions', '').strip()
            article.weight = data.get('weight', '').strip()
            article.origin_country = data.get('origin_country', '').strip()
            article.condition = data.get('condition', '').strip()
            article.care_instructions = data.get('care_instructions', '').strip()
            article.shipping_note = data.get('shipping_note', '').strip()
            article.return_note = data.get('return_note', '').strip()
            article.guarantee_note = data.get('guarantee_note', '').strip()
            article.is_siecle_selection = 'is_siecle_selection' in data
            article.is_limited_edition = 'is_limited_edition' in data
            article.edition_quantity = data.get('edition_quantity') or None
            article.is_new_arrival = 'is_new_arrival' in data
            ph = data.get('product_highlights_json', '')
            if ph:
                article.product_highlights = _parse_json_list(ph)
            td = data.get('technical_details_json', '')
            if td:
                article.technical_details = _parse_json_dict(td)
            fi = data.get('faq_items_json', '')
            if fi:
                article.faq_items = _parse_json_list(fi)

            article.save()
            _create_sync_log(company, article, 'success', 'Article mis à jour.')
            messages.success(request, 'Article mis à jour.')
            return redirect('ecommerce:article_detail', pk=article.pk)
        except Exception as e:
            messages.error(request, f'Erreur : {e}')

    return render(request, 'ecommerce/article_form.html', {
        'page_title': f'Modifier — {article.name}',
        'article': article,
        'status_choices': StoreProduct.STATUS_CHOICES,
        'early_access_choices': StoreProduct.EARLY_ACCESS_CHOICES,
        'categories': _get_siecle_categories(company),
        'sizes_json': json.dumps(article.available_sizes),
        'product_highlights_json': json.dumps(article.product_highlights or [], ensure_ascii=False),
        'technical_details_json': json.dumps(article.technical_details or {}, ensure_ascii=False),
        'faq_items_json': json.dumps(article.faq_items or [], ensure_ascii=False),
    })


@login_required
@require_POST
def article_publish(request, pk):
    company = request.current_company
    article = get_object_or_404(StoreProduct, pk=pk, website__company=company)
    new_status = request.POST.get('status', 'published')
    article.status = new_status
    article.save()
    _create_sync_log(company, article, 'success', f'Statut changé → {new_status}')
    messages.success(request, f'Article « {article.name} » : statut mis à jour.')
    return redirect('ecommerce:article_detail', pk=pk)


# ─── MÉDIAS (IMAGES) ──────────────────────────────────────────────────────────

@login_required
@require_POST
def article_image_upload(request, pk):
    company = request.current_company
    article = get_object_or_404(StoreProduct, pk=pk, website__company=company)

    img = request.FILES.get('image')
    if not img:
        messages.error(request, 'Aucun fichier fourni.')
        return redirect('ecommerce:article_detail', pk=pk)

    # Validation côté serveur — type MIME réel
    content_type = img.content_type
    if content_type not in ALLOWED_IMAGE_TYPES:
        messages.error(request, f'Type de fichier non autorisé : {content_type}. Formats acceptés : JPG, PNG, WEBP.')
        return redirect('ecommerce:article_detail', pk=pk)

    if img.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        messages.error(request, f'Fichier trop lourd (max {MAX_IMAGE_SIZE_MB} Mo).')
        return redirect('ecommerce:article_detail', pk=pk)

    alt_text = request.POST.get('alt_text', '').strip()
    variant_label = request.POST.get('variant_label', '').strip()
    is_primary = request.POST.get('is_primary') == '1'
    current_max = article.images.count()

    StoreProductImage.objects.create(
        product=article,
        image=img,
        alt_text=alt_text,
        variant_label=variant_label,
        is_primary=is_primary,
        order=current_max,
    )
    messages.success(request, 'Image ajoutée.')
    return redirect('ecommerce:article_detail', pk=pk)


@login_required
@require_POST
def article_image_delete(request, pk, image_pk):
    company = request.current_company
    article = get_object_or_404(StoreProduct, pk=pk, website__company=company)
    img = get_object_or_404(StoreProductImage, pk=image_pk, product=article)
    # Supprimer le fichier physique
    if img.image and os.path.exists(img.image.path):
        try:
            os.remove(img.image.path)
        except OSError:
            pass
    img.delete()
    messages.success(request, 'Image supprimée.')
    return redirect('ecommerce:article_detail', pk=pk)


@login_required
@require_POST
def article_image_set_primary(request, pk, image_pk):
    company = request.current_company
    article = get_object_or_404(StoreProduct, pk=pk, website__company=company)
    img = get_object_or_404(StoreProductImage, pk=image_pk, product=article)
    # La méthode save() de StoreProductImage gère l'unicité
    img.is_primary = True
    img.save()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def article_image_reorder(request, pk):
    """Réorganisation par drag-and-drop — reçoit JSON: [{id: N, order: N}, ...]"""
    company = request.current_company
    article = get_object_or_404(StoreProduct, pk=pk, website__company=company)
    try:
        data = json.loads(request.body)
        for item in data:
            StoreProductImage.objects.filter(pk=item['id'], product=article).update(order=item['order'])
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# ─── VARIANTES ────────────────────────────────────────────────────────────────

@login_required
def article_variants(request, pk):
    """Page de gestion complète des variantes (taille, couleur, SKU, prix, stock)."""
    from apps.ecommerce.forms import StoreProductVariantFormSet
    company = request.current_company
    article = get_object_or_404(StoreProduct, pk=pk, website__company=company)

    if request.method == 'POST':
        formset = StoreProductVariantFormSet(request.POST, request.FILES, instance=article)
        if formset.is_valid():
            formset.save()
            messages.success(request, 'Variantes enregistrées.')
            return redirect('ecommerce:article_variants', pk=pk)
        else:
            messages.error(request, 'Corrigez les erreurs ci-dessous.')
    else:
        formset = StoreProductVariantFormSet(instance=article)

    return render(request, 'ecommerce/article_variants.html', {
        'page_title': f'Variantes — {article.name}',
        'article': article,
        'formset': formset,
    })


@login_required
@require_POST
def article_variant_add(request, pk):
    """Ajout rapide d'une variante (redirige vers la page de gestion complète)."""
    return redirect('ecommerce:article_variants', pk=pk)


@login_required
@require_POST
def article_variant_delete(request, pk, variant_pk):
    company = request.current_company
    article = get_object_or_404(StoreProduct, pk=pk, website__company=company)
    variant = get_object_or_404(StoreProductVariant, pk=variant_pk, product=article)
    variant.delete()
    messages.success(request, 'Variante supprimée.')
    return redirect('ecommerce:article_variants', pk=pk)


# ─── SYNC LOG ─────────────────────────────────────────────────────────────────

@login_required
def sync_log_list(request):
    company = request.current_company
    logs = SyncLog.objects.filter(company=company)
    status_filter = request.GET.get('status', '')
    if status_filter:
        logs = logs.filter(status=status_filter)
    return render(request, 'ecommerce/sync_log_list.html', {
        'page_title': 'Journal de synchronisation',
        'logs': logs[:100],
        'status_filter': status_filter,
    })


@login_required
@require_POST
def sync_retry(request, log_pk):
    company = request.current_company
    log = get_object_or_404(SyncLog, pk=log_pk, company=company)
    if log.product:
        log.product.save()
        new_log = SyncLog.objects.create(
            company=company, product=log.product,
            product_name=log.product.name,
            direction='erp_to_site', status='success',
            message='Réessai manuel depuis le journal de sync.',
        )
        log.status = 'success'
        log.message += ' [Réessayé]'
        log.save()
        messages.success(request, 'Synchronisation relancée.')
    return redirect('ecommerce:sync_log_list')


# ─── SIÈCLE STATUS ────────────────────────────────────────────────────────────

@login_required
def loyalty_status_list(request):
    company = request.current_company
    accounts = LoyaltyAccount.objects.filter(company=company)
    tier_filter = request.GET.get('tier', '')
    search = request.GET.get('q', '')
    if tier_filter:
        accounts = accounts.filter(tier=tier_filter)
    if search:
        accounts = accounts.filter(
            Q(customer_email__icontains=search) |
            Q(customer__first_name__icontains=search) |
            Q(customer__last_name__icontains=search)
        )
    return render(request, 'ecommerce/loyalty_status_list.html', {
        'page_title': 'SIÈCLE STATUS',
        'accounts': accounts.order_by('-lifetime_points'),
        'tier_filter': tier_filter,
        'search': search,
        'tier_choices': LoyaltyAccount.TIER_CHOICES,
        'total': accounts.count(),
        'gold_count': LoyaltyAccount.objects.filter(company=company, tier='gold').count(),
        'silver_count': LoyaltyAccount.objects.filter(company=company, tier='silver').count(),
        'member_count': LoyaltyAccount.objects.filter(company=company, tier='classic').count(),
    })


@login_required
def loyalty_status_detail(request, pk):
    company = request.current_company
    account = get_object_or_404(LoyaltyAccount, pk=pk, company=company)
    transactions = account.transactions.all().order_by('-created_at')[:50]
    return render(request, 'ecommerce/loyalty_status_detail.html', {
        'page_title': f'SIÈCLE STATUS — {account.customer_email}',
        'account': account,
        'transactions': transactions,
    })


@login_required
@require_POST
def loyalty_status_adjust(request, pk):
    company = request.current_company
    account = get_object_or_404(LoyaltyAccount, pk=pk, company=company)
    try:
        points = int(request.POST.get('points', 0))
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, 'Un motif est obligatoire pour tout ajustement.')
            return redirect('ecommerce:loyalty_status_detail', pk=pk)
        account.adjust_points(points, reason, admin_user=request.user)
        sign = '+' if points >= 0 else ''
        messages.success(request, f'Ajustement {sign}{points} pts enregistré.')
    except Exception as e:
        messages.error(request, f'Erreur : {e}')
    return redirect('ecommerce:loyalty_status_detail', pk=pk)


# ─── PARRAINAGES ──────────────────────────────────────────────────────────────

@login_required
def referral_list(request):
    company = request.current_company
    referrals = AffiliateReferral.objects.filter(company=company).select_related('affiliate_code')
    status_filter = request.GET.get('status', '')
    search = request.GET.get('q', '')
    if status_filter:
        referrals = referrals.filter(status=status_filter)
    if search:
        referrals = referrals.filter(
            Q(referrer_email__icontains=search) | Q(referred_email__icontains=search)
        )
    return render(request, 'ecommerce/referral_list.html', {
        'page_title': 'Parrainages',
        'referrals': referrals.order_by('-created_at'),
        'status_filter': status_filter,
        'search': search,
        'status_choices': AffiliateReferral.STATUS_CHOICES,
        'total': referrals.count(),
    })


# ─── Helper ───────────────────────────────────────────────────────────────────

def _create_sync_log(company, product, status, message):
    try:
        SyncLog.objects.create(
            company=company,
            product=product,
            product_name=product.name if product else '',
            direction='erp_to_site',
            status=status,
            message=message,
        )
    except Exception:
        pass
