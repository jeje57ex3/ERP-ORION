from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.utils.text import slugify
from .models import (
    Website, WebsitePage, BlogPost, ContactMessage, QuoteRequest,
    StoreCategory, StoreProduct, StoreCart, StoreCartItem, StoreOrder, StoreOrderItem,
)
from .forms import (
    WebsiteAdminForm, WebsiteShowcaseCreateForm, WebsiteStoreCreateForm,
    WebsitePageAdminForm, BlogPostAdminForm,
    StoreCategoryForm, StoreProductForm, StoreOrderStatusForm,
)


# ─── PAGES PAR DÉFAUT ─────────────────────────────────────────────────────────

SHOWCASE_DEFAULT_PAGES = [
    ('home', 'Accueil', True, True, 0),
    ('about', 'À propos', False, True, 1),
    ('services', 'Services', False, True, 2),
    ('projects', 'Réalisations', False, True, 3),
    ('blog_list', 'Blog', False, True, 4),
    ('contact', 'Contact', False, True, 5),
    ('quote_request', 'Demande de devis', False, True, 6),
    ('privacy', 'Politique de confidentialité', False, False, 7),
    ('legal', 'Mentions légales', False, False, 8),
]

ECOMMERCE_DEFAULT_PAGES = [
    ('home', 'Accueil boutique', True, True, 0),
    ('products', 'Catalogue', False, True, 1),
    ('contact', 'Contact', False, True, 2),
    ('faq', 'FAQ', False, True, 3),
    ('legal', 'Mentions légales', False, False, 4),
    ('privacy', 'Politique de confidentialité', False, False, 5),
    ('custom', 'Conditions générales de vente', False, False, 6),
    ('custom', 'Politique de retour', False, False, 7),
    ('custom', 'Politique de livraison', False, False, 8),
]


def _create_default_pages(website, page_defs):
    for page_type, title, is_home, show_menu, order in page_defs:
        WebsitePage.objects.get_or_create(
            website=website, slug=slugify(title),
            defaults={
                'page_type': page_type, 'title': title,
                'is_homepage': is_home, 'show_in_menu': show_menu,
                'order': order, 'status': 'draft',
            }
        )


# ─── INDEX ────────────────────────────────────────────────────────────────────

@login_required
def index(request):
    return redirect('websites:website_list')


# ─── SITES WEB ────────────────────────────────────────────────────────────────

@login_required
def website_list(request):
    company = request.current_company
    qs = Website.objects.filter(company=company)
    site_type = request.GET.get('type', '')
    status = request.GET.get('status', '')
    if site_type:
        qs = qs.filter(site_type=site_type)
    if status:
        qs = qs.filter(status=status)
    published_count = Website.objects.filter(company=company, status='published').count()
    ecommerce_count = Website.objects.filter(company=company, site_type='ecommerce').count()
    return render(request, 'websites/website_list.html', {
        'websites': qs,
        'site_type': site_type,
        'status': status,
        'site_type_choices': Website.SITE_TYPES,
        'status_choices': Website.STATUS_CHOICES,
        'published_count': published_count,
        'ecommerce_count': ecommerce_count,
        'total': qs.count(),
    })


@login_required
def website_detail(request, pk):
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    pages = WebsitePage.objects.filter(website=website).count()
    posts = BlogPost.objects.filter(website=website).count()
    new_messages = ContactMessage.objects.filter(website=website, status='new').count()
    store_products_count = StoreProduct.objects.filter(website=website).count()
    store_orders_count = StoreOrder.objects.filter(website=website).count()
    return render(request, 'websites/website_detail.html', {
        'website': website,
        'pages_count': pages,
        'posts_count': posts,
        'new_messages': new_messages,
        'store_products_count': store_products_count,
        'store_orders_count': store_orders_count,
    })


@login_required
def website_create(request):
    company = request.current_company
    form = WebsiteAdminForm()
    if request.method == 'POST':
        form = WebsiteAdminForm(request.POST)
        if form.is_valid():
            site = form.save(commit=False)
            site.company = company
            site.save()
            messages.success(request, f'Site « {site.name} » créé.')
            return redirect('websites:website_detail', pk=site.pk)
    return render(request, 'websites/website_form.html', {'form': form, 'action': 'create'})


@login_required
def website_create_showcase(request):
    company = request.current_company
    form = WebsiteShowcaseCreateForm()
    if request.method == 'POST':
        form = WebsiteShowcaseCreateForm(request.POST, request.FILES)
        if form.is_valid():
            site = form.save(commit=False)
            site.company = company
            site.site_type = 'showcase'
            site.status = 'draft'
            site.save()
            _create_default_pages(site, SHOWCASE_DEFAULT_PAGES)
            messages.success(request, f'Site vitrine « {site.name} » créé avec {len(SHOWCASE_DEFAULT_PAGES)} pages.')
            return redirect('websites:website_detail', pk=site.pk)
    return render(request, 'websites/website_create_showcase.html', {'form': form})


@login_required
def website_create_store(request):
    company = request.current_company
    form = WebsiteStoreCreateForm()
    if request.method == 'POST':
        form = WebsiteStoreCreateForm(request.POST, request.FILES)
        if form.is_valid():
            site = form.save(commit=False)
            site.company = company
            site.site_type = 'ecommerce'
            site.status = 'draft'
            site.save()
            _create_default_pages(site, ECOMMERCE_DEFAULT_PAGES)
            messages.success(request, f'Boutique en ligne « {site.name} » créée avec {len(ECOMMERCE_DEFAULT_PAGES)} pages.')
            return redirect('websites:store_dashboard', pk=site.pk)
    return render(request, 'websites/website_create_store.html', {'form': form})


@login_required
def website_edit(request, pk):
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    form = WebsiteAdminForm(instance=website)
    if request.method == 'POST':
        form = WebsiteAdminForm(request.POST, request.FILES, instance=website)
        if form.is_valid():
            form.save()
            messages.success(request, 'Site mis à jour.')
            return redirect('websites:website_detail', pk=pk)
    return render(request, 'websites/website_form.html', {'form': form, 'website': website, 'action': 'edit'})


@login_required
def website_publish(request, pk):
    company = request.current_company
    site = get_object_or_404(Website, pk=pk, company=company)
    if request.method == 'POST':
        site.status = 'published'
        site.is_active = True
        site.save()
        messages.success(request, f'Site « {site.name} » publié.')
    return redirect('websites:website_detail', pk=pk)


@login_required
def website_unpublish(request, pk):
    company = request.current_company
    site = get_object_or_404(Website, pk=pk, company=company)
    if request.method == 'POST':
        site.status = 'unpublished'
        site.is_active = False
        site.save()
        messages.success(request, f'Site « {site.name} » dépublié.')
    return redirect('websites:website_detail', pk=pk)


@login_required
def website_archive(request, pk):
    company = request.current_company
    site = get_object_or_404(Website, pk=pk, company=company)
    if request.method == 'POST':
        site.status = 'archived'
        site.is_active = False
        site.save()
        messages.success(request, f'Site « {site.name} » archivé.')
    return redirect('websites:website_list')


@login_required
def website_duplicate(request, pk):
    company = request.current_company
    site = get_object_or_404(Website, pk=pk, company=company)
    if request.method == 'POST':
        pages = list(site.pages.all())
        site.pk = None
        site.name = f'{site.name} (copie)'
        site.status = 'draft'
        site.domain = ''
        site.subdomain = ''
        site.save()
        for page in pages:
            page.pk = None
            page.website = site
            page.status = 'draft'
            page.save()
        messages.success(request, f'Site dupliqué : « {site.name} ».')
        return redirect('websites:website_detail', pk=site.pk)
    return render(request, 'websites/website_confirm_duplicate.html', {'website': site})


# ─── PAGES ────────────────────────────────────────────────────────────────────

@login_required
def page_list(request):
    company = request.current_company
    site_id = request.GET.get('site', '')
    qs = WebsitePage.objects.filter(website__company=company).select_related('website')
    if site_id:
        qs = qs.filter(website_id=site_id)
    sites = Website.objects.filter(company=company)
    return render(request, 'websites/page_list.html', {'pages': qs, 'sites': sites, 'site_id': site_id})


@login_required
def page_create(request):
    company = request.current_company
    form = WebsitePageAdminForm(company=company)
    if request.method == 'POST':
        form = WebsitePageAdminForm(request.POST, company=company)
        if form.is_valid():
            page = form.save()
            messages.success(request, f'Page « {page.title} » créée.')
            return redirect('websites:page_list')
    return render(request, 'websites/page_form.html', {'form': form, 'action': 'create'})


@login_required
def page_edit(request, pk):
    company = request.current_company
    page = get_object_or_404(WebsitePage, pk=pk, website__company=company)
    form = WebsitePageAdminForm(instance=page, company=company)
    if request.method == 'POST':
        form = WebsitePageAdminForm(request.POST, instance=page, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Page mise à jour.')
            return redirect('websites:page_list')
    return render(request, 'websites/page_form.html', {'form': form, 'page': page, 'action': 'edit'})


# ─── BLOG ─────────────────────────────────────────────────────────────────────

@login_required
def blog_list(request):
    company = request.current_company
    site_id = request.GET.get('site', '')
    qs = BlogPost.objects.filter(website__company=company).select_related('website', 'author')
    if site_id:
        qs = qs.filter(website_id=site_id)
    search = request.GET.get('q', '')
    if search:
        qs = qs.filter(Q(title__icontains=search))
    sites = Website.objects.filter(company=company)
    return render(request, 'websites/blog_list.html', {'posts': qs, 'sites': sites, 'site_id': site_id, 'search': search})


@login_required
def blog_create(request):
    company = request.current_company
    form = BlogPostAdminForm(company=company)
    if request.method == 'POST':
        form = BlogPostAdminForm(request.POST, company=company)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            messages.success(request, f'Article « {post.title} » créé.')
            return redirect('websites:blog_list')
    return render(request, 'websites/blog_form.html', {'form': form, 'action': 'create'})


@login_required
def blog_edit(request, pk):
    company = request.current_company
    post = get_object_or_404(BlogPost, pk=pk, website__company=company)
    form = BlogPostAdminForm(instance=post, company=company)
    if request.method == 'POST':
        form = BlogPostAdminForm(request.POST, instance=post, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Article mis à jour.')
            return redirect('websites:blog_list')
    return render(request, 'websites/blog_form.html', {'form': form, 'post': post, 'action': 'edit'})


# ─── MESSAGES & DEVIS ─────────────────────────────────────────────────────────

@login_required
def message_list(request):
    company = request.current_company
    qs = ContactMessage.objects.filter(website__company=company)
    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)
    new_count = ContactMessage.objects.filter(website__company=company, status='new').count()
    return render(request, 'websites/message_list.html', {
        'messages_list': qs, 'status': status,
        'status_choices': ContactMessage.STATUS_CHOICES, 'new_count': new_count,
    })


@login_required
def quote_request_list(request):
    company = request.current_company
    qs = QuoteRequest.objects.filter(website__company=company)
    status = request.GET.get('status', '')
    if status:
        qs = qs.filter(status=status)
    new_count = QuoteRequest.objects.filter(website__company=company, status='new').count()
    return render(request, 'websites/quote_request_list.html', {
        'quote_requests': qs, 'status': status,
        'status_choices': QuoteRequest.STATUS_CHOICES, 'new_count': new_count,
    })


# ─── DASHBOARD BOUTIQUE ───────────────────────────────────────────────────────

@login_required
def store_dashboard(request, pk):
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    today = timezone.now().date()
    orders_today = StoreOrder.objects.filter(website=website, created_at__date=today).count()
    revenue = StoreOrder.objects.filter(website=website, payment_status='paid').aggregate(v=Sum('grand_total'))['v'] or 0
    pending_orders = StoreOrder.objects.filter(website=website, status='pending').count()
    published_products = StoreProduct.objects.filter(website=website, status='published').count()
    draft_products = StoreProduct.objects.filter(website=website, status='draft').count()
    out_of_stock = StoreProduct.objects.filter(website=website, stock_quantity=0, status='published').count()
    recent_orders = StoreOrder.objects.filter(website=website).order_by('-created_at')[:8]
    abandoned_carts = StoreCart.objects.filter(website=website, is_active=True).count()
    return render(request, 'websites/store_dashboard.html', {
        'website': website,
        'orders_today': orders_today,
        'revenue': revenue,
        'pending_orders': pending_orders,
        'published_products': published_products,
        'draft_products': draft_products,
        'out_of_stock': out_of_stock,
        'recent_orders': recent_orders,
        'abandoned_carts': abandoned_carts,
    })


# ─── CATÉGORIES BOUTIQUE ──────────────────────────────────────────────────────

@login_required
def store_category_list(request, pk):
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    categories = StoreCategory.objects.filter(website=website).select_related('parent')
    return render(request, 'websites/store_category_list.html', {
        'website': website, 'categories': categories,
    })


@login_required
def store_category_create(request, pk):
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    form = StoreCategoryForm(website=website)
    if request.method == 'POST':
        form = StoreCategoryForm(request.POST, request.FILES, website=website)
        if form.is_valid():
            cat = form.save(commit=False)
            cat.website = website
            cat.save()
            messages.success(request, f'Catégorie « {cat.name} » créée.')
            return redirect('websites:store_category_list', pk=pk)
    return render(request, 'websites/store_category_form.html', {'form': form, 'website': website, 'action': 'create'})


@login_required
def store_category_edit(request, pk, cat_pk):
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    category = get_object_or_404(StoreCategory, pk=cat_pk, website=website)
    form = StoreCategoryForm(instance=category, website=website)
    if request.method == 'POST':
        form = StoreCategoryForm(request.POST, request.FILES, instance=category, website=website)
        if form.is_valid():
            form.save()
            messages.success(request, 'Catégorie mise à jour.')
            return redirect('websites:store_category_list', pk=pk)
    return render(request, 'websites/store_category_form.html', {
        'form': form, 'website': website, 'category': category, 'action': 'edit',
    })


# ─── PRODUITS BOUTIQUE ────────────────────────────────────────────────────────

@login_required
def store_product_list(request, pk):
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    qs = StoreProduct.objects.filter(website=website).select_related('category')
    status = request.GET.get('status', '')
    search = request.GET.get('q', '')
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(Q(name__icontains=search) | Q(sku__icontains=search))
    published = StoreProduct.objects.filter(website=website, status='published').count()
    out_of_stock = StoreProduct.objects.filter(website=website, stock_quantity=0).count()
    return render(request, 'websites/store_product_list.html', {
        'website': website, 'products': qs, 'status': status, 'search': search,
        'status_choices': StoreProduct.STATUS_CHOICES,
        'published': published, 'out_of_stock': out_of_stock,
        'total': qs.count(),
    })


@login_required
def store_product_create(request, pk):
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    form = StoreProductForm(website=website, company=company)
    if request.method == 'POST':
        form = StoreProductForm(request.POST, request.FILES, website=website, company=company)
        if form.is_valid():
            product = form.save(commit=False)
            product.website = website
            product.save()
            messages.success(request, f'Produit « {product.name} » créé.')
            return redirect('websites:store_product_list', pk=pk)
    return render(request, 'websites/store_product_form.html', {
        'form': form, 'website': website, 'action': 'create',
    })


@login_required
def store_product_edit(request, pk, prod_pk):
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    product = get_object_or_404(StoreProduct, pk=prod_pk, website=website)
    form = StoreProductForm(instance=product, website=website, company=company)
    if request.method == 'POST':
        form = StoreProductForm(request.POST, request.FILES, instance=product, website=website, company=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Produit mis à jour.')
            return redirect('websites:store_product_list', pk=pk)
    return render(request, 'websites/store_product_form.html', {
        'form': form, 'website': website, 'product': product, 'action': 'edit',
    })


@login_required
def store_product_delete(request, pk, prod_pk):
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    product = get_object_or_404(StoreProduct, pk=prod_pk, website=website)
    if request.method == 'POST':
        name = product.name
        product.delete()
        messages.success(request, f'Produit « {name} » supprimé.')
        return redirect('websites:store_product_list', pk=pk)
    return render(request, 'websites/store_product_confirm_delete.html', {'website': website, 'product': product})


@login_required
def store_product_import_erp(request, pk):
    """Importe tous les produits ERP actifs comme produits boutique."""
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    if request.method == 'POST':
        from apps.inventory.models import Product
        erp_products = Product.objects.filter(company=company, is_active=True)
        created = 0
        for erp_prod in erp_products:
            slug = slugify(erp_prod.name)
            if StoreProduct.objects.filter(website=website, slug=slug).exists():
                continue
            StoreProduct.objects.create(
                website=website,
                erp_product=erp_prod,
                name=erp_prod.name,
                slug=slug,
                sku=getattr(erp_prod, 'reference', '') or '',
                price=getattr(erp_prod, 'sale_price', None) or getattr(erp_prod, 'purchase_price', 0) or 0,
                stock_quantity=getattr(erp_prod, 'quantity', 0) or 0,
                stock_from_erp=True,
                status='draft',
            )
            created += 1
        messages.success(request, f'{created} produit(s) ERP importé(s) en brouillon.')
    return redirect('websites:store_product_list', pk=pk)


@login_required
def store_product_toggle_status(request, pk, prod_pk):
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    product = get_object_or_404(StoreProduct, pk=prod_pk, website=website)
    if request.method == 'POST':
        product.status = 'draft' if product.status == 'published' else 'published'
        product.save()
        messages.success(request, f'Produit « {product.name} » : {product.get_status_display()}.')
    return redirect('websites:store_product_list', pk=pk)


# ─── COMMANDES BOUTIQUE ───────────────────────────────────────────────────────

@login_required
def store_order_list(request, pk):
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    qs = StoreOrder.objects.filter(website=website)
    status = request.GET.get('status', '')
    search = request.GET.get('q', '')
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(
            Q(order_number__icontains=search) |
            Q(customer_name__icontains=search) |
            Q(customer_email__icontains=search)
        )
    revenue = StoreOrder.objects.filter(website=website, payment_status='paid').aggregate(v=Sum('grand_total'))['v'] or 0
    pending = StoreOrder.objects.filter(website=website, status='pending').count()
    return render(request, 'websites/store_order_list.html', {
        'website': website, 'orders': qs, 'status': status, 'search': search,
        'status_choices': StoreOrder.STATUS_CHOICES,
        'revenue': revenue, 'pending': pending,
        'total': qs.count(),
    })


@login_required
def store_order_detail(request, pk, order_pk):
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    order = get_object_or_404(StoreOrder, pk=order_pk, website=website)
    form = StoreOrderStatusForm(instance=order)
    if request.method == 'POST':
        form = StoreOrderStatusForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(request, 'Commande mise à jour.')
            return redirect('websites:store_order_detail', pk=pk, order_pk=order_pk)
    return render(request, 'websites/store_order_detail.html', {
        'website': website, 'order': order, 'form': form,
    })


# ─── DOMAINES ─────────────────────────────────────────────────────────────────

@login_required
def domain_settings(request, pk):
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    from .models import WebsiteDomain
    from .domain_services import generate_verification_token, normalize_domain, validate_domain_format, get_expected_dns_records

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'add_domain':
            raw_domain = request.POST.get('domain', '').strip()
            domain_type = request.POST.get('domain_type', 'subdomain')
            domain = normalize_domain(raw_domain)
            valid, error = validate_domain_format(domain)
            if not valid:
                messages.error(request, f'Domaine invalide : {error}')
            elif WebsiteDomain.objects.filter(website=website, domain=domain).exists():
                messages.warning(request, 'Ce domaine est déjà configuré pour ce site.')
            else:
                token = generate_verification_token(domain)
                wd = WebsiteDomain.objects.create(
                    website=website,
                    company=website.company,
                    domain=domain,
                    domain_type=domain_type,
                    verification_token=token,
                    expected_txt_record=f'orion-verification={token}',
                    status='pending',
                )
                messages.success(request, f'Domaine « {domain} » ajouté. Configurez vos DNS.')
            return redirect('websites:domain_settings', pk=pk)

        if action == 'verify_dns':
            domain_id = request.POST.get('domain_id')
            wd = get_object_or_404(WebsiteDomain, pk=domain_id, website=website)
            from .domain_services import verify_domain_ownership
            verified = verify_domain_ownership(wd)
            if verified:
                messages.success(request, f'DNS vérifié pour {wd.domain}.')
            else:
                messages.warning(request, f'DNS non vérifié pour {wd.domain}. {wd.last_error}')
            return redirect('websites:domain_settings', pk=pk)

        if action == 'set_primary':
            domain_id = request.POST.get('domain_id')
            wd = get_object_or_404(WebsiteDomain, pk=domain_id, website=website)
            from .domain_services import set_primary_domain
            set_primary_domain(wd)
            messages.success(request, f'« {wd.domain} » défini comme domaine principal.')
            return redirect('websites:domain_settings', pk=pk)

        if action == 'delete_domain':
            domain_id = request.POST.get('domain_id')
            wd = get_object_or_404(WebsiteDomain, pk=domain_id, website=website)
            name = wd.domain
            wd.delete()
            messages.success(request, f'Domaine « {name} » supprimé.')
            return redirect('websites:domain_settings', pk=pk)

        if action == 'toggle_maintenance':
            website.maintenance_mode = not website.maintenance_mode
            website.save(update_fields=['maintenance_mode'])
            state = 'activé' if website.maintenance_mode else 'désactivé'
            messages.info(request, f'Mode maintenance {state}.')
            return redirect('websites:domain_settings', pk=pk)

    domains = website.domains.all().order_by('-is_primary', 'domain')
    domains_with_dns = []
    from .domain_services import get_expected_dns_records
    for d in domains:
        domains_with_dns.append({'domain': d, 'dns_records': get_expected_dns_records(d)})

    return render(request, 'websites/domain_settings.html', {
        'website': website,
        'domains_with_dns': domains_with_dns,
        'domain_type_choices': WebsiteDomain.DOMAIN_TYPES,
        'page_title': f'Domaines — {website.name}',
        'active_module': 'websites',
    })


# ─── MÉDIATHÈQUE ──────────────────────────────────────────────────────────────

@login_required
def media_library(request, pk):
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    from .models import WebsiteMedia

    if request.method == 'POST':
        action = request.POST.get('action', 'upload')
        if action == 'upload' and request.FILES.get('file'):
            f = request.FILES['file']
            ext = f.name.rsplit('.', 1)[-1].lower() if '.' in f.name else ''
            if ext in ('jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'):
                mtype = 'image'
            elif ext == 'pdf':
                mtype = 'pdf'
            elif ext in ('mp4', 'webm', 'mov'):
                mtype = 'video'
            elif ext in ('ico', 'png') and 'favicon' in f.name.lower():
                mtype = 'favicon'
            else:
                mtype = 'other'
            WebsiteMedia.objects.create(
                company=company,
                website=website,
                file=f,
                title=request.POST.get('title', '') or f.name,
                alt_text=request.POST.get('alt_text', ''),
                media_type=mtype,
                file_size=f.size,
                uploaded_by=request.user,
            )
            messages.success(request, f'Fichier « {f.name} » ajouté à la médiathèque.')
        elif action == 'delete':
            media_id = request.POST.get('media_id')
            media = get_object_or_404(WebsiteMedia, pk=media_id, website=website)
            media.file.delete(save=False)
            media.delete()
            messages.success(request, 'Média supprimé.')
        return redirect('websites:media_library', pk=pk)

    media_type = request.GET.get('type', '')
    qs = WebsiteMedia.objects.filter(website=website)
    if media_type:
        qs = qs.filter(media_type=media_type)
    return render(request, 'websites/media_library.html', {
        'website': website,
        'media_files': qs,
        'media_type': media_type,
        'media_type_choices': WebsiteMedia.MEDIA_TYPES,
        'page_title': f'Médiathèque — {website.name}',
        'active_module': 'websites',
    })


# ─── PAGE BUILDER ─────────────────────────────────────────────────────────────

@login_required
def page_builder(request, pk, page_pk):
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    page = get_object_or_404(WebsitePage, pk=page_pk, website=website)
    from .models import WebsiteSection
    import json

    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'add_section':
            section_type = request.POST.get('section_type', 'text')
            last_order = page.sections.aggregate(m=Count('id'))['m'] or 0
            WebsiteSection.objects.create(
                page=page,
                section_type=section_type,
                title=request.POST.get('title', ''),
                content=request.POST.get('content', ''),
                order=last_order,
                is_visible=True,
            )
            messages.success(request, 'Section ajoutée.')

        elif action == 'update_section':
            sec_id = request.POST.get('section_id')
            sec = get_object_or_404(WebsiteSection, pk=sec_id, page=page)
            sec.title = request.POST.get('title', sec.title)
            sec.subtitle = request.POST.get('subtitle', sec.subtitle)
            sec.content = request.POST.get('content', sec.content)
            sec.button_text = request.POST.get('button_text', sec.button_text)
            sec.button_link = request.POST.get('button_link', sec.button_link)
            sec.bg_color = request.POST.get('bg_color', sec.bg_color)
            sec.save()
            messages.success(request, 'Section mise à jour.')

        elif action == 'delete_section':
            sec_id = request.POST.get('section_id')
            sec = get_object_or_404(WebsiteSection, pk=sec_id, page=page)
            sec.delete()
            messages.success(request, 'Section supprimée.')

        elif action == 'move_up':
            sec_id = request.POST.get('section_id')
            sec = get_object_or_404(WebsiteSection, pk=sec_id, page=page)
            if sec.order > 0:
                prev = page.sections.filter(order__lt=sec.order).order_by('-order').first()
                if prev:
                    prev.order, sec.order = sec.order, prev.order
                    prev.save()
                    sec.save()

        elif action == 'move_down':
            sec_id = request.POST.get('section_id')
            sec = get_object_or_404(WebsiteSection, pk=sec_id, page=page)
            next_sec = page.sections.filter(order__gt=sec.order).order_by('order').first()
            if next_sec:
                next_sec.order, sec.order = sec.order, next_sec.order
                next_sec.save()
                sec.save()

        elif action == 'toggle_visibility':
            sec_id = request.POST.get('section_id')
            sec = get_object_or_404(WebsiteSection, pk=sec_id, page=page)
            sec.is_visible = not sec.is_visible
            sec.save()

        elif action == 'publish_page':
            from .publishing_services import publish_page
            publish_page(page)
            messages.success(request, f'Page « {page.title} » publiée.')

        return redirect('websites:page_builder', pk=pk, page_pk=page_pk)

    sections = page.sections.order_by('order')
    return render(request, 'websites/page_builder.html', {
        'website': website,
        'page': page,
        'sections': sections,
        'section_types': WebsiteSection.SECTION_TYPES,
        'page_title': f'Page builder — {page.title}',
        'active_module': 'websites',
    })


# ─── CHECKLIST PUBLICATION ────────────────────────────────────────────────────

@login_required
def publish_checklist(request, pk):
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    from .publishing_services import check_website_ready_to_publish, publish_website, unpublish_website

    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'publish':
            result = publish_website(website)
            if result['success']:
                messages.success(request, f'Site « {website.name} » publié avec succès.')
            else:
                for err in result['errors']:
                    messages.error(request, f'Bloquant : {err}')
        elif action == 'unpublish':
            unpublish_website(website)
            messages.info(request, f'Site « {website.name} » dépublié.')
        return redirect('websites:publish_checklist', pk=pk)

    check = check_website_ready_to_publish(website)
    return render(request, 'websites/publish_checklist.html', {
        'website': website,
        'check': check,
        'page_title': f'Checklist publication — {website.name}',
        'active_module': 'websites',
    })


# ─── SEO ──────────────────────────────────────────────────────────────────────

@login_required
def seo_dashboard(request, pk):
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    from .seo_services import calculate_seo_score, check_missing_meta, generate_meta_preview

    pages = website.pages.filter(status='published').order_by('order', 'title')
    pages_seo = []
    for p in pages:
        score = calculate_seo_score(p)
        preview = generate_meta_preview(p)
        missing = check_missing_meta(p)
        pages_seo.append({'page': p, 'score': score, 'preview': preview, 'missing': missing})

    return render(request, 'websites/seo_dashboard.html', {
        'website': website,
        'pages_seo': pages_seo,
        'page_title': f'SEO — {website.name}',
        'active_module': 'websites',
    })


@login_required
def seo_page_edit(request, pk, page_pk):
    """Edition rapide SEO d'une page."""
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    page = get_object_or_404(WebsitePage, pk=page_pk, website=website)
    from .seo_services import calculate_seo_score, generate_meta_preview

    if request.method == 'POST':
        page.meta_title = request.POST.get('meta_title', page.meta_title)
        page.meta_description = request.POST.get('meta_description', page.meta_description)
        page.is_indexable = request.POST.get('is_indexable') == 'on'
        page.canonical_url = request.POST.get('canonical_url', page.canonical_url)
        page.save(update_fields=['meta_title', 'meta_description', 'is_indexable', 'canonical_url'])
        messages.success(request, 'SEO mis à jour.')
        return redirect('websites:seo_dashboard', pk=pk)

    score = calculate_seo_score(page)
    preview = generate_meta_preview(page)
    return render(request, 'websites/seo_page_edit.html', {
        'website': website, 'page': page, 'score': score, 'preview': preview,
        'page_title': f'SEO — {page.title}',
        'active_module': 'websites',
    })


@login_required
def sitemap_view(request, pk):
    """Génère et affiche le sitemap XML."""
    from django.http import HttpResponse
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    from .seo_services import generate_sitemap_xml
    xml = generate_sitemap_xml(website)
    return HttpResponse(xml, content_type='application/xml')


@login_required
def robots_view(request, pk):
    """Génère et affiche le robots.txt."""
    from django.http import HttpResponse
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    from .seo_services import generate_robots_txt
    txt = generate_robots_txt(website)
    return HttpResponse(txt, content_type='text/plain')


# ─── ANALYTICS ────────────────────────────────────────────────────────────────

@login_required
def website_analytics(request, pk):
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    from .models import WebsiteAnalyticsEvent
    from django.db.models import Count as DjCount

    period = request.GET.get('period', '30')
    try:
        days = int(period)
    except ValueError:
        days = 30

    from datetime import timedelta
    since = timezone.now() - timedelta(days=days)

    events = WebsiteAnalyticsEvent.objects.filter(website=website, created_at__gte=since)
    page_views = events.filter(event_type='page_view').count()
    form_submissions = events.filter(event_type='form_submission').count()
    product_views = events.filter(event_type='product_view').count()

    top_pages = (
        events.filter(event_type='page_view')
        .values('path')
        .annotate(count=DjCount('id'))
        .order_by('-count')[:10]
    )

    contact_messages = ContactMessage.objects.filter(website=website, created_at__gte=since).count()
    quote_requests = QuoteRequest.objects.filter(website=website, created_at__gte=since).count()
    store_orders = StoreOrder.objects.filter(website=website, created_at__gte=since).count()

    return render(request, 'websites/website_analytics.html', {
        'website': website,
        'page_views': page_views,
        'form_submissions': form_submissions,
        'product_views': product_views,
        'contact_messages': contact_messages,
        'quote_requests': quote_requests,
        'store_orders': store_orders,
        'top_pages': top_pages,
        'period': period,
        'page_title': f'Analytics — {website.name}',
        'active_module': 'websites',
    })


# ─── THÈMES ───────────────────────────────────────────────────────────────────

@login_required
def theme_list(request, pk):
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    from .models import WebsiteTheme
    themes = WebsiteTheme.objects.filter(
        Q(company=company) | Q(company__isnull=True)
    ).order_by('company', 'name')
    return render(request, 'websites/theme_list.html', {
        'website': website,
        'themes': themes,
        'page_title': f'Thèmes — {website.name}',
        'active_module': 'websites',
    })


@login_required
def theme_apply(request, pk, theme_pk):
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    from .models import WebsiteTheme
    theme = get_object_or_404(WebsiteTheme, pk=theme_pk)
    if request.method == 'POST':
        website.theme = theme
        website.save(update_fields=['theme'])
        messages.success(request, f'Thème « {theme.name} » appliqué.')
    return redirect('websites:theme_list', pk=pk)


@login_required
def theme_settings(request, pk):
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    from .models import WebsiteTheme

    theme = website.theme
    if not theme:
        default = WebsiteTheme.objects.filter(company__isnull=True, is_default=True).first()
        if default:
            website.theme = default
            website.save(update_fields=['theme'])
            theme = default

    if request.method == 'POST' and theme:
        theme.primary_color = request.POST.get('primary_color', theme.primary_color)
        theme.secondary_color = request.POST.get('secondary_color', theme.secondary_color)
        theme.accent_color = request.POST.get('accent_color', theme.accent_color)
        theme.background_color = request.POST.get('background_color', theme.background_color)
        theme.text_color = request.POST.get('text_color', theme.text_color)
        theme.button_color = request.POST.get('button_color', theme.button_color)
        theme.header_bg_color = request.POST.get('header_bg_color', theme.header_bg_color)
        theme.footer_bg_color = request.POST.get('footer_bg_color', theme.footer_bg_color)
        theme.font_primary = request.POST.get('font_primary', theme.font_primary)
        theme.button_style = request.POST.get('button_style', theme.button_style)
        theme.border_radius = request.POST.get('border_radius', theme.border_radius)
        theme.custom_css = request.POST.get('custom_css', theme.custom_css)
        theme.save()
        messages.success(request, 'Thème mis à jour.')
        return redirect('websites:theme_settings', pk=pk)

    return render(request, 'websites/theme_settings.html', {
        'website': website,
        'theme': theme,
        'font_choices': WebsiteTheme.FONT_CHOICES,
        'button_style_choices': WebsiteTheme.BUTTON_STYLE_CHOICES,
        'page_title': f'Paramètres thème — {website.name}',
        'active_module': 'websites',
    })


# ─── PRÉVISUALISATION ─────────────────────────────────────────────────────────

@login_required
def website_preview(request, pk):
    company = request.current_company
    website = get_object_or_404(Website, pk=pk, company=company)
    return render(request, 'websites/website_preview.html', {
        'website': website,
        'page_title': f'Prévisualisation — {website.name}',
        'active_module': 'websites',
    })
