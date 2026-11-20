from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.website_shop_settings.forms import (
    CheckoutSettingsForm,
    CookieSettingsForm,
    EmailSettingsForm,
    LegalSettingsForm,
    PaymentSettingsForm,
    ReturnSettingsForm,
    SEOSettingsForm,
    ShippingSettingsForm,
    ShopSecuritySettingsForm,
    SiteMaintenanceSettingsForm,
    StockSettingsForm,
    TaxSettingsForm,
    WebsiteShopSettingsForm,
)
from apps.website_shop_settings.models import WebsiteShopSettings
from apps.website_shop_settings.permissions import shop_settings_access_required
from apps.website_shop_settings.services import ensure_all_related_settings


def _get_company(request):
    return getattr(request, 'current_company', None)


def _nav_items(pk):
    from django.urls import reverse
    sections = [
        ('general', 'Général', 'bi-sliders', 'website_shop_settings:general'),
        ('payments', 'Paiements', 'bi-credit-card', 'website_shop_settings:payments'),
        ('checkout', 'Checkout', 'bi-cart-check', 'website_shop_settings:checkout'),
        ('shipping', 'Livraison', 'bi-truck', 'website_shop_settings:shipping'),
        ('returns', 'Retours', 'bi-arrow-return-left', 'website_shop_settings:returns'),
        ('taxes', 'Taxes', 'bi-percent', 'website_shop_settings:taxes'),
        ('emails', 'Emails', 'bi-envelope', 'website_shop_settings:emails'),
        ('legal', 'Pages légales', 'bi-file-earmark-text', 'website_shop_settings:legal'),
        ('seo', 'SEO', 'bi-search', 'website_shop_settings:seo'),
        ('cookies', 'Cookies', 'bi-shield-check', 'website_shop_settings:cookies'),
        ('stock', 'Stock', 'bi-box-seam', 'website_shop_settings:stock'),
        ('maintenance', 'Maintenance', 'bi-tools', 'website_shop_settings:maintenance'),
        ('security', 'Sécurité', 'bi-lock', 'website_shop_settings:security'),
    ]
    return [
        {'key': key, 'label': label, 'icon': icon, 'url': reverse(url_name, kwargs={'pk': pk})}
        for key, label, icon, url_name in sections
    ]


@login_required
@shop_settings_access_required
def shop_settings_dashboard(request):
    company = _get_company(request)
    settings_list = WebsiteShopSettings.objects.filter(company=company).order_by('brand_key')
    return render(request, 'website_shop_settings/dashboard.html', {
        'settings_list': settings_list,
    })


def _reglages_de_l_entreprise(request, pk):
    """Les réglages de boutique, BORNÉS à l'entreprise courante.

    LA FAILLE QUE CECI FERME. `_settings_view` et `general_settings_view`
    allaient chercher l'objet par sa seule clé primaire. Le décorateur
    `shop_settings_access_required`, lui, vérifie que l'utilisateur est
    administrateur ou propriétaire de **son entreprise courante** — pas
    que l'objet demandé lui appartienne.

    Un administrateur de l'entreprise A pouvait donc, en changeant le
    numéro dans l'URL, ouvrir ET ENREGISTRER les réglages de l'entreprise
    B. Ces réglages portent `stripe_secret_key_encrypted`,
    `stripe_webhook_secret_encrypted` et les URL de retour : remplacer la
    clé et l'URL de succès d'un concurrent, c'est détourner ses paiements.

    La lecture des secrets, elle, était déjà protégée — le champ du
    formulaire est en écriture seule et le modèle ne rend que la version
    chiffrée. C'est l'ÉCRITURE qui était ouverte, et elle suffisait.

    LE SUPER-ADMINISTRATEUR N'EST PAS BORNÉ, et c'est le même choix que
    celui du décorateur juste au-dessus : l'exploitant de l'installation
    intervient légitimement sur toutes les entreprises. Reproduire sa
    règle plutôt qu'en inventer une seconde évite qu'elles divergent.
    """
    from django.core.exceptions import PermissionDenied

    if request.user.is_superuser:
        return get_object_or_404(WebsiteShopSettings, pk=pk)

    company = _get_company(request)
    if company is None:
        raise PermissionDenied
    return get_object_or_404(WebsiteShopSettings, pk=pk, company=company)


def _settings_view(request, pk, related_attr, form_class, template, active_key):
    shop_settings = _reglages_de_l_entreprise(request, pk)
    ensure_all_related_settings(shop_settings)
    instance = getattr(shop_settings, related_attr)

    if request.method == 'POST':
        form = form_class(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, 'Paramètres enregistrés.')
            return redirect(request.path)
    else:
        form = form_class(instance=instance)

    return render(request, template, {
        'form': form,
        'shop_settings': shop_settings,
        'active_section': active_key,
        'nav_items': _nav_items(pk),
        'page_title': form.instance._meta.verbose_name.capitalize() if hasattr(form.instance, '_meta') else 'Paramètres',
    })


@login_required
@shop_settings_access_required
def general_settings_view(request, pk):
    shop_settings = _reglages_de_l_entreprise(request, pk)
    ensure_all_related_settings(shop_settings)
    if request.method == 'POST':
        form = WebsiteShopSettingsForm(request.POST, request.FILES, instance=shop_settings)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user
            obj.save()
            messages.success(request, 'Paramètres généraux enregistrés.')
            return redirect(request.path)
    else:
        form = WebsiteShopSettingsForm(instance=shop_settings)
    return render(request, 'website_shop_settings/site_settings.html', {
        'form': form,
        'shop_settings': shop_settings,
        'active_section': 'general',
        'nav_items': _nav_items(pk),
        'page_title': 'Paramètres généraux',
    })


@login_required
@shop_settings_access_required
def payment_settings_view(request, pk):
    return _settings_view(request, pk, 'payment_settings', PaymentSettingsForm,
                          'website_shop_settings/payment_settings.html', 'payments')


@login_required
@shop_settings_access_required
def checkout_settings_view(request, pk):
    return _settings_view(request, pk, 'checkout_settings', CheckoutSettingsForm,
                          'website_shop_settings/checkout_settings.html', 'checkout')


@login_required
@shop_settings_access_required
def shipping_settings_view(request, pk):
    return _settings_view(request, pk, 'shipping_settings', ShippingSettingsForm,
                          'website_shop_settings/shipping_settings.html', 'shipping')


@login_required
@shop_settings_access_required
def return_settings_view(request, pk):
    return _settings_view(request, pk, 'return_settings', ReturnSettingsForm,
                          'website_shop_settings/return_settings.html', 'returns')


@login_required
@shop_settings_access_required
def tax_settings_view(request, pk):
    return _settings_view(request, pk, 'tax_settings', TaxSettingsForm,
                          'website_shop_settings/tax_settings.html', 'taxes')


@login_required
@shop_settings_access_required
def email_settings_view(request, pk):
    return _settings_view(request, pk, 'email_settings', EmailSettingsForm,
                          'website_shop_settings/email_settings.html', 'emails')


@login_required
@shop_settings_access_required
def legal_settings_view(request, pk):
    return _settings_view(request, pk, 'legal_settings', LegalSettingsForm,
                          'website_shop_settings/legal_settings.html', 'legal')


@login_required
@shop_settings_access_required
def seo_settings_view(request, pk):
    return _settings_view(request, pk, 'seo_settings', SEOSettingsForm,
                          'website_shop_settings/seo_settings.html', 'seo')


@login_required
@shop_settings_access_required
def cookie_settings_view(request, pk):
    return _settings_view(request, pk, 'cookie_settings', CookieSettingsForm,
                          'website_shop_settings/cookie_settings.html', 'cookies')


@login_required
@shop_settings_access_required
def stock_settings_view(request, pk):
    return _settings_view(request, pk, 'stock_settings', StockSettingsForm,
                          'website_shop_settings/stock_settings.html', 'stock')


@login_required
@shop_settings_access_required
def maintenance_settings_view(request, pk):
    return _settings_view(request, pk, 'maintenance_settings', SiteMaintenanceSettingsForm,
                          'website_shop_settings/maintenance_settings.html', 'maintenance')


@login_required
@shop_settings_access_required
def security_settings_view(request, pk):
    return _settings_view(request, pk, 'security_settings', ShopSecuritySettingsForm,
                          'website_shop_settings/security_settings.html', 'security')
