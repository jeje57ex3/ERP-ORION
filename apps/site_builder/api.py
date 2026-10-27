"""
apps/site_builder/api.py — AJAX API endpoints for the visual builder.
All views return JSON and require POST + login + site_builder module.
"""
import io
import json
import uuid

from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from apps.private_saas.decorators import require_company_module

from .models import BuilderPage, BuilderSection
from .registry import BUILDER_MODULES
from .renderer import render_section_html
from .services import (
    add_section_to_page,
    delete_section,
    publish_builder_page,
    reorder_sections_from_ids,
    update_section_settings,
)


def _parse_json_body(request):
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return {}


def _section_wrapper_html(request, section: BuilderSection, page: BuilderPage) -> str:
    rendered_html = render_section_html(section, page.brand_key)
    module_info = BUILDER_MODULES.get(section.module_type, {})
    return render_to_string('site_builder/_section_wrapper.html', {
        'section_id':    section.pk,
        'module_type':   section.module_type,
        'module_label':  module_info.get('label', section.module_type),
        'module_icon':   module_info.get('icon', 'bi-box'),
        'settings_json': json.dumps(section.settings),
        'rendered_html': rendered_html,
    }, request=request)


# ──────────────────────────────────────────────────────────────────────────────

@login_required
@require_company_module('site_builder')
@require_POST
def add_section_api(request, page_id):
    company = request.current_company
    page = get_object_or_404(BuilderPage, pk=page_id, company=company)

    data = _parse_json_body(request)
    module_type = data.get('module_type', '')

    if module_type not in BUILDER_MODULES:
        return JsonResponse({'success': False, 'error': 'Module inconnu.'}, status=400)

    section = add_section_to_page(page, module_type)
    module_info = BUILDER_MODULES[module_type]

    return JsonResponse({
        'success':      True,
        'section_id':   section.pk,
        'module_type':  section.module_type,
        'module_label': module_info['label'],
        'module_icon':  module_info['icon'],
        'wrapper_html': _section_wrapper_html(request, section, page),
    })


@login_required
@require_company_module('site_builder')
@require_POST
def update_section_api(request, section_id):
    company = request.current_company
    section = get_object_or_404(BuilderSection, pk=section_id, page__company=company)

    data = _parse_json_body(request)
    new_settings = data.get('settings', {})

    if not isinstance(new_settings, dict):
        return JsonResponse({'success': False, 'error': 'settings invalide.'}, status=400)

    section = update_section_settings(section, new_settings)
    rendered_html = render_section_html(section, section.page.brand_key)

    return JsonResponse({
        'success': True,
        'html':    rendered_html,
    })


@login_required
@require_company_module('site_builder')
@require_POST
def delete_section_api(request, section_id):
    company = request.current_company
    section = get_object_or_404(BuilderSection, pk=section_id, page__company=company)
    delete_section(section)
    return JsonResponse({'success': True})


@login_required
@require_company_module('site_builder')
@require_POST
def reorder_sections_api(request, page_id):
    company = request.current_company
    page = get_object_or_404(BuilderPage, pk=page_id, company=company)

    data = _parse_json_body(request)
    section_ids = data.get('section_ids', [])

    if not isinstance(section_ids, list):
        return JsonResponse({'success': False, 'error': 'section_ids invalide.'}, status=400)

    reorder_sections_from_ids(page, section_ids)
    return JsonResponse({'success': True})


# Extension deduite du format REELLEMENT lu dans le fichier, jamais du nom
# envoye par le client.
#
# L'ancienne version faisait `os.path.splitext(img.name)[1]` : le nom de
# fichier est fourni par le navigateur, et `content_type` aussi -- les deux
# se falsifient. Un fichier nomme « piege.svg » annonce « image/png »
# passait les deux controles et etait enregistre en .svg sous /media/. Un
# SVG est un document XML qui peut porter du <script> : servi depuis
# l'origine du site, il s'executait avec les droits du visiteur.
EXTENSION_PAR_FORMAT = {
    'JPEG': '.jpg',
    'PNG': '.png',
    'WEBP': '.webp',
    'GIF': '.gif',
    'AVIF': '.avif',
}


@login_required
@require_company_module('site_builder')
@require_POST
def upload_builder_image_api(request):
    """Upload une image pour le builder. Retourne l'URL absolue du fichier."""
    MAX_SIZE = 8 * 1024 * 1024  # 8 Mo

    img = request.FILES.get('image')
    if not img:
        return JsonResponse({'success': False, 'error': 'Aucune image envoyée.'}, status=400)
    # La taille d'abord : inutile de decoder huit mega-octets pour les
    # refuser ensuite.
    if img.size > MAX_SIZE:
        return JsonResponse({'success': False, 'error': 'Image trop lourde (max 8 Mo).'}, status=400)

    # Le format est lu dans les octets. `Image.verify()` controle la
    # structure du fichier sans le decoder entierement.
    from PIL import Image, UnidentifiedImageError

    octets = img.read()
    try:
        with Image.open(io.BytesIO(octets)) as sonde:
            format_reel = (sonde.format or '').upper()
            sonde.verify()
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError):
        return JsonResponse(
            {'success': False,
             'error': "Ce fichier n'est pas une image lisible."},
            status=400)

    ext = EXTENSION_PAR_FORMAT.get(format_reel)
    if not ext:
        return JsonResponse(
            {'success': False,
             'error': f'Format non supporté ({format_reel or "inconnu"}) — '
                      f'JPEG, PNG, WebP, GIF ou AVIF.'},
            status=400)

    filename = f'{uuid.uuid4().hex}{ext}'
    path = default_storage.save(f'builder/images/{filename}', ContentFile(octets))
    relative_url = default_storage.url(path)

    # Retourner une URL absolue pour que Next.js puisse charger l'image depuis n'importe où
    if relative_url.startswith('http'):
        absolute_url = relative_url
    else:
        absolute_url = request.build_absolute_uri(relative_url)

    return JsonResponse({'success': True, 'url': absolute_url})


@login_required
@require_company_module('site_builder')
@require_POST
def publish_page_api(request, page_id):
    company = request.current_company
    page = get_object_or_404(BuilderPage, pk=page_id, company=company)
    page = publish_builder_page(page, user=request.user)
    return JsonResponse({
        'success':      True,
        'published_at': page.published_at.isoformat(),
    })
