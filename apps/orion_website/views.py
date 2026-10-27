from django.http import Http404
from django.shortcuts import render

from apps.orion_website.context import get_orion_public_context
from apps.orion_website.data import (
    ORION_APPS,
    ORION_FAQ,
    ORION_FAQ_CATEGORIES,
    ORION_MODULE_CATEGORIES,
    ORION_MODULES,
)


def page_context(**kwargs):
    ctx = get_orion_public_context()
    ctx.update(kwargs)
    return ctx


def home_view(request):
    return render(request, "orion_website/home.html", page_context(
        page_title="Orion ERP — Logiciel de gestion intelligent",
        featured_modules=ORION_MODULES[:6],
        apps=ORION_APPS,
    ))


def modules_view(request):
    modules_by_category = []

    for category in ORION_MODULE_CATEGORIES:
        category_modules = [
            module for module in ORION_MODULES
            if module.get("category") == category["code"]
        ]
        modules_by_category.append({
            "category": category,
            "modules": category_modules,
        })

    return render(request, "orion_website/modules.html", page_context(
        page_title="Tous les modules Orion ERP",
        modules=ORION_MODULES,
        categories=ORION_MODULE_CATEGORIES,
        modules_by_category=modules_by_category,
        total_modules=len(ORION_MODULES),
    ))


def module_detail_view(request, module_code):
    module = next(
        (item for item in ORION_MODULES if item["code"] == module_code),
        None,
    )

    if not module:
        raise Http404("Module introuvable.")

    category = next(
        (item for item in ORION_MODULE_CATEGORIES if item["code"] == module.get("category")),
        None,
    )

    related_modules = [
        item for item in ORION_MODULES
        if item.get("category") == module.get("category") and item["code"] != module_code
    ][:4]

    return render(request, "orion_website/module_detail.html", page_context(
        page_title=f"{module['title']} — Module Orion ERP",
        module=module,
        category=category,
        related_modules=related_modules,
    ))


def apps_view(request):
    return render(request, "orion_website/apps.html", page_context(
        page_title="Applications Orion ERP",
        apps=ORION_APPS,
    ))


def _lien_de_telechargement_android():
    """L'adresse de la dernière version Android publiée, ou None.

    `apps.mobile_app.models.MobileRelease` était importé ici, et rien de
    tout cela n'existe dans le projet : ni ce module, ni ce modèle, ni la
    route `/mobile/telecharger/<id>/` que la vue construisait. La seule
    application mobile présente est `apps.mobile_web`, qui ne porte qu'un
    modèle d'envoi de photos.

    L'application n'étant pas déclarée, cet import n'avait jamais été
    exécuté : la page de téléchargements levait `ModuleNotFoundError` dès
    la première visite — et avec elle la page qui sert à récupérer les
    applications.

    L'import est donc toléré plutôt que supprimé : le gabarit sait déjà
    afficher « Bientôt disponible » et griser la carte quand l'adresse
    manque, de sorte que la page reste utile pour Windows et Apple. Et le
    jour où ce module existera, le lien apparaîtra de lui-même, sans qu'il
    faille se souvenir de cette ligne.
    """
    try:
        from apps.mobile_app.models import MobileRelease
    except ImportError:
        return None

    version = (
        MobileRelease.objects
        .filter(platform="android", is_published=True, channel="stable")
        .order_by("-created_at")
        .first()
    )
    return f"/mobile/telecharger/{version.id}/" if version else None


def downloads_view(request):
    android_url = _lien_de_telechargement_android()
    return render(request, "orion_website/downloads.html", page_context(
        page_title="Téléchargements Orion ERP",
        apps=ORION_APPS,
        android_download_url=android_url,
    ))


def install_windows_view(request):
    return render(request, "orion_website/install_windows.html", page_context(
        page_title="Installer Orion ERP sur Windows",
    ))


def install_android_view(request):
    return render(request, "orion_website/install_android.html", page_context(
        page_title="Installer Orion ERP sur Android",
    ))


def install_apple_view(request):
    return render(request, "orion_website/install_apple.html", page_context(
        page_title="Installer Orion ERP sur iPhone / iPad",
    ))


def security_view(request):
    return render(request, "orion_website/security.html", page_context(
        page_title="Sécurité Orion ERP",
    ))


def faq_view(request):
    faq_by_category = []

    for category in ORION_FAQ_CATEGORIES:
        items = [
            item for item in ORION_FAQ
            if item.get("category") == category["code"]
        ]
        faq_by_category.append({
            "category": category,
            "items": items,
        })

    return render(request, "orion_website/faq.html", page_context(
        page_title="FAQ Orion ERP",
        faq_items=ORION_FAQ,
        faq_categories=ORION_FAQ_CATEGORIES,
        faq_by_category=faq_by_category,
    ))


def contact_view(request):
    return render(request, "orion_website/contact.html", page_context(
        page_title="Contact Orion ERP",
    ))
