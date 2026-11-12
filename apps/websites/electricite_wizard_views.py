"""
apps/websites/electricite_wizard_views.py — Configurateurs publics du site
Électricité (chantier + dépannage), scopés par site (site_slug dans l'URL).

Contrairement au wizard BTP global (apps.btp.guided_quote_views, monté sur
/devis-guide/), celui-ci résout l'entreprise via le site public visité plutôt
que via request.current_company (qui dépend de la session d'un utilisateur
ERP connecté et ne fonctionne pas pour un visiteur anonyme multi-tenant).
Réutilise directement les modèles et briques de apps.btp / apps.crm.
"""
import secrets

from django.contrib import messages
from django.contrib.auth.models import User
from django.http import Http404, FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from apps.btp.guided_quote_pdf import generate_guided_quote_pdf
from apps.btp.models import (
    BTPQuote, BTPQuoteLine, ElectricityPriceLibrary, GuidedQuoteDocument,
    GuidedQuoteEstimate, GuidedQuoteEstimateItem, GuidedQuoteRequest,
    GuidedQuotePhoto,
)
from apps.core.numbering import next_number
from apps.crm.models import Customer, Opportunity, Prospect

from .btp_public_views import _notify_erp
from .models import Website
from .public_views import _base_context, _get_ip

ROOM_CHOICES = [
    ('salon', 'Salon'), ('cuisine', 'Cuisine'), ('chambre', 'Chambre'),
    ('salle_de_bain', 'Salle de bain'), ('garage', 'Garage'),
    ('terrasse', 'Terrasse'), ('jardin', 'Jardin'), ('local_technique', 'Local technique'),
]

EQUIPMENT_CHOICES = [
    ('prises', 'Prises', 'prise_interrupteur'),
    ('interrupteurs', 'Interrupteurs', 'prise_interrupteur'),
    ('rj45', 'RJ45', 'reseau'),
    ('baie_informatique', 'Baie informatique', 'reseau'),
    ('camera', 'Caméra', 'alarme'),
    ('alarme', 'Alarme', 'alarme'),
    ('domotique', 'Domotique', 'domotique'),
    ('volets_roulants', 'Volets roulants', 'domotique'),
    ('eclairage_led', 'Éclairage LED', 'eclairage'),
    ('spots', 'Spots', 'eclairage'),
    ('detecteurs', 'Détecteurs', 'alarme'),
    ('interphone', 'Interphone', 'reseau'),
    ('visiophone', 'Visiophone', 'reseau'),
    ('borne_ve', 'Borne de recharge VE', 'borne_recharge'),
    ('panneaux_photovoltaiques', 'Panneaux photovoltaïques', 'autre'),
    ('batterie', 'Batterie de stockage', 'autre'),
]
EQUIPMENT_CATEGORY_MAP = {key: category for key, _, category in EQUIPMENT_CHOICES}

QUALITY_MULTIPLIERS = {'standard': 1.0, 'premium': 1.25, 'luxe': 1.6}

BUILDING_TYPE_CHOICES = [
    ('house', 'Maison'), ('apartment', 'Appartement'), ('commercial', 'Commerce'),
    ('workshop', 'Industrie'), ('office', 'Bureau'), ('building', 'Entrepôt'),
    ('other', 'Local technique'),
]
PROJECT_TYPE_CHOICES = [
    ('installation_neuve', 'Construction'), ('renovation', 'Rénovation'),
    ('travaux', 'Extension'), ('depannage', 'Dépannage'), ('mise_normes', 'Maintenance'),
]


def _get_electricite_site(site_slug):
    """Le site électricité désigné par cette adresse.

    QUATRE TENTATIVES, ET C'EST UNE CORRECTION.

    Cette fonction ne cherchait que par le slug de l'ENTREPRISE, alors que
    les pages génériques du même préfixe (`_get_site` dans public_views)
    acceptent d'abord le slug du SITE puis celui de l'entreprise. Un site
    dont le slug diffère de celui de son entreprise était donc joignable
    sur « /sites/<slug>/ » et rendait 404 sur « /sites/<slug>/electricite/ »
    — pour la même machine, la même entreprise, à un segment près.

    On essaie donc les deux désignations, en préférant à chaque fois un
    site réellement de type « electricite » : servir ce dessin à une
    boutique afficherait une page d'électricien sur un site de vente.
    """
    recherches = (
        {'slug': site_slug, 'site_type': 'electricite'},
        {'company__slug': site_slug, 'site_type': 'electricite'},
        {'slug': site_slug},
        {'company__slug': site_slug},
    )
    for criteres in recherches:
        site = Website.objects.filter(is_active=True, **criteres).first()
        if site is not None:
            return site
    raise Http404


def _wizard_context(site):
    ctx = _base_context(site)
    ctx.update({
        'room_choices': ROOM_CHOICES,
        'equipment_choices': EQUIPMENT_CHOICES,
        'building_type_choices': BUILDING_TYPE_CHOICES,
        'project_type_choices': PROJECT_TYPE_CHOICES,
        'quality_choices': GuidedQuoteRequest.QUALITY_LEVEL_CHOICES,
    })
    return ctx


# ─── STEP 1 : type de bâtiment + type de projet ────────────────────────────────

def wizard_start(request, site_slug):
    site = _get_electricite_site(site_slug)
    if request.method == 'POST':
        request.session['elec_building_type'] = request.POST.get('building_type', '')
        request.session['elec_request_type'] = request.POST.get('request_type', 'depannage')
        request.session['elec_answers'] = {}
        return redirect('public_websites:electricite_wizard_step2', site_slug=site_slug)
    return render(request, 'websites/public/electricite/wizard/step1_type.html', _wizard_context(site))


# ─── STEP 2 : dépannage (court) OU configurateur de chantier (9 sous-étapes) ───

def wizard_step2(request, site_slug):
    site = _get_electricite_site(site_slug)
    request_type = request.session.get('elec_request_type', 'depannage')

    if request.method == 'POST':
        answers = request.session.get('elec_answers', {})
        if request_type == 'depannage':
            answers.update({
                'urgency': request.POST.get('urgency', 'normal'),
                'problem_type': request.POST.get('problem_type', ''),
                'safety_issue': request.POST.get('safety_issue', 'no'),
                'has_photo': bool(request.POST.get('has_photo')),
                'availability': request.POST.get('availability', ''),
            })
        else:
            answers.update({
                'surface': request.POST.get('surface', ''),
                'rooms': {key: request.POST.get(f'room_{key}', '0') for key, _ in ROOM_CHOICES},
                'equipments': request.POST.getlist('equipments'),
                'comments': request.POST.get('comments', ''),
            })
            request.session['elec_quality_level'] = request.POST.get('quality_level', 'standard')
        request.session['elec_answers'] = answers
        request.session['elec_urgency'] = answers.get('urgency', 'normal')
        return redirect('public_websites:electricite_wizard_step3', site_slug=site_slug)

    ctx = _wizard_context(site)
    ctx['request_type'] = request_type
    ctx['building_type'] = request.session.get('elec_building_type', '')
    problem_type_choices = [
        ('no_power_all', 'Plus de courant dans tout le logement'),
        ('no_power_room', 'Plus de courant dans une pièce'),
        ('breaker', 'Disjoncteur qui saute'),
        ('dead_outlet', 'Prise qui ne fonctionne plus'),
        ('panel_issue', 'Tableau électrique problématique'),
        ('other', 'Autre problème'),
    ]
    ctx['problem_type_choices'] = problem_type_choices
    tpl = 'step2_depannage.html' if request_type == 'depannage' else 'step2_chantier.html'
    return render(request, f'websites/public/electricite/wizard/{tpl}', ctx)


# ─── STEP 3 : contact ───────────────────────────────────────────────────────────

def wizard_step3(request, site_slug):
    site = _get_electricite_site(site_slug)
    if request.method == 'POST':
        request.session['elec_contact'] = {
            'first_name': request.POST.get('first_name', ''),
            'last_name': request.POST.get('last_name', ''),
            'email': request.POST.get('email', ''),
            'phone': request.POST.get('phone', ''),
            'address': request.POST.get('address', ''),
            'zip_code': request.POST.get('zip_code', ''),
            'city': request.POST.get('city', ''),
            'client_notes': request.POST.get('client_notes', ''),
            'create_portal': request.POST.get('create_portal') == 'on',
        }
        return redirect('public_websites:electricite_wizard_step4', site_slug=site_slug)
    ctx = _wizard_context(site)
    ctx['request_type'] = request.session.get('elec_request_type', 'depannage')
    return render(request, 'websites/public/electricite/wizard/step3_contact.html', ctx)


# ─── STEP 4 : récapitulatif + envoi (calcul + sync CRM + devis + PDF) ─────────

def wizard_step4(request, site_slug):
    site = _get_electricite_site(site_slug)
    company = site.company
    request_type = request.session.get('elec_request_type', 'depannage')
    answers = request.session.get('elec_answers', {})
    contact = request.session.get('elec_contact', {})
    building_type = request.session.get('elec_building_type', '')
    quality_level = request.session.get('elec_quality_level', 'standard')

    if request.method == 'POST':
        quote_request = GuidedQuoteRequest.objects.create(
            company=company,
            request_type=request_type,
            urgency=answers.get('urgency', 'normal'),
            client_first_name=contact.get('first_name', ''),
            client_last_name=contact.get('last_name', ''),
            client_email=contact.get('email', ''),
            client_phone=contact.get('phone', ''),
            address=contact.get('address', ''),
            zip_code=contact.get('zip_code', ''),
            city=contact.get('city', ''),
            property_type=building_type,
            surface=answers.get('surface', ''),
            quality_level=quality_level,
            answers=answers,
            client_notes=contact.get('client_notes', ''),
            create_portal_account=contact.get('create_portal', False),
        )

        if contact.get('create_portal') and contact.get('email'):
            _create_portal_account(company, contact)

        estimate = _calculate_electricite_estimate(company, quote_request)
        _create_crm_lead_from_guided_quote(company, quote_request)
        _auto_create_btp_quote(company, quote_request, estimate)

        _notify_erp(
            site,
            title=f'Nouvelle demande {quote_request.get_request_type_display()} — {quote_request.reference}',
            message=f'{quote_request.client_full_name} ({quote_request.client_phone or quote_request.client_email})',
            notif_type_label='Demande électricité',
            source='electricite_wizard',
            priority='urgent' if quote_request.is_urgent else 'normal',
        )

        for k in ['elec_building_type', 'elec_request_type', 'elec_answers', 'elec_contact', 'elec_urgency', 'elec_quality_level']:
            request.session.pop(k, None)
        request.session['elec_last_request_pk'] = quote_request.pk
        return redirect('public_websites:electricite_wizard_success', site_slug=site_slug)

    ctx = _wizard_context(site)
    ctx.update({
        'request_type': request_type, 'answers': answers, 'contact': contact,
        'building_type': building_type, 'quality_level': quality_level,
    })
    return render(request, 'websites/public/electricite/wizard/step4_recap.html', ctx)


def _create_portal_account(company, contact):
    from apps.portals.models import ClientPortalAccount
    email = contact.get('email', '')
    if not email or User.objects.filter(email=email).exists():
        return
    pwd = secrets.token_urlsafe(12)
    username = email.split('@')[0]
    base, i = username, 1
    while User.objects.filter(username=username).exists():
        username = f'{base}{i}'
        i += 1
    user = User.objects.create_user(
        username=username, email=email, password=pwd,
        first_name=contact.get('first_name', ''), last_name=contact.get('last_name', ''),
    )
    ClientPortalAccount.objects.create(
        company=company, user=user, email=email,
        first_name=contact.get('first_name', ''), last_name=contact.get('last_name', ''),
        phone=contact.get('phone', ''), created_from_guided_quote=True,
    )


def _calculate_electricite_estimate(company, quote_request):
    """Calcul étendu : pièces, équipements (multi), niveau de gamme, dépannage."""
    answers = quote_request.answers or {}
    multiplier = QUALITY_MULTIPLIERS.get(quote_request.quality_level, 1.0)
    items = []
    total_min = total_avg = total_max = 0.0

    def add(category, desc, qty=1, name_filter=None):
        nonlocal total_min, total_avg, total_max
        qs = ElectricityPriceLibrary.objects.filter(company=company, category=category, is_active=True)
        if name_filter:
            qs = qs.filter(name__icontains=name_filter)
        price_item = qs.first()
        if not price_item or not qty:
            return
        items.append({'item': price_item, 'qty': qty, 'desc': desc})
        total_min += float(price_item.price_min) * qty
        total_avg += float(price_item.price_avg) * qty
        total_max += float(price_item.price_max) * qty

    if quote_request.request_type == 'depannage':
        add('deplacement', 'Déplacement')
        add('diagnostic', 'Diagnostic panne')
        if quote_request.urgency == 'urgent':
            add('forfait', 'Majoration urgence', name_filter='urgent')
        add('main_oeuvre', "Main-d'œuvre estimée (1h)")
    else:
        for eq_key in answers.get('equipments', []):
            category = EQUIPMENT_CATEGORY_MAP.get(eq_key, 'autre')
            label = dict((k, l) for k, l, _ in EQUIPMENT_CHOICES).get(eq_key, eq_key)
            add(category, label)

        rooms = answers.get('rooms', {}) or {}
        nb_rooms = sum(int(v or 0) for v in rooms.values())
        if nb_rooms:
            add('installation', f'Installation électrique par pièce ({nb_rooms} pièce(s))', qty=nb_rooms)

        if not items:
            surface_key = answers.get('surface', '')
            qty = 50 if 'less' in surface_key or '30' in surface_key else 80 if '60' in surface_key else 100
            add('renovation', f'Rénovation électrique (estimation {qty} m²)', qty=qty)

    total_min *= multiplier
    total_avg *= multiplier
    total_max *= multiplier

    vat = 0.20
    estimate = GuidedQuoteEstimate.objects.create(
        request=quote_request,
        amount_min_ht=round(total_min, 2), amount_avg_ht=round(total_avg, 2), amount_max_ht=round(total_max, 2),
        labor_amount=round(total_avg * 0.6, 2), materials_amount=round(total_avg * 0.4, 2),
        travel_amount=round(50 if quote_request.request_type == 'depannage' else 0, 2),
        urgency_surcharge=round(total_avg * 0.25 if quote_request.urgency == 'urgent' else 0, 2),
        total_ttc=round(total_avg * (1 + vat), 2),
        duration_min_days=0.5 if quote_request.request_type == 'depannage' else 1,
        duration_max_days=1 if quote_request.request_type == 'depannage' else 5,
    )
    for order, it in enumerate(items):
        GuidedQuoteEstimateItem.objects.create(
            estimate=estimate, price_item=it['item'], description=it['desc'],
            quantity=it['qty'], unit=it['item'].unit,
            unit_price_avg=round(float(it['item'].price_avg) * multiplier, 2), order=order,
        )
    return estimate


def _create_crm_lead_from_guided_quote(company, quote_request):
    """Crée Customer (requis par BTPQuote) + Prospect/Opportunity (suivi commercial)."""
    try:
        customer = Customer.objects.create(
            company=company, customer_type='individual',
            name=quote_request.client_full_name or quote_request.client_email,
            contact_name=quote_request.client_full_name,
            email=quote_request.client_email, phone=quote_request.client_phone,
            address=quote_request.address, city=quote_request.city, zip_code=quote_request.zip_code,
            notes=f'Créé automatiquement depuis le configurateur — {quote_request.reference}',
        )
        quote_request.crm_customer_id = customer.pk

        prospect = Prospect.objects.create(
            company=company, name=quote_request.client_full_name,
            contact_name=quote_request.client_full_name,
            email=quote_request.client_email, phone=quote_request.client_phone,
            city=quote_request.city, status='qualified', source='website_electricite',
            notes=f'Demande {quote_request.get_request_type_display()} — {quote_request.client_notes}',
        )
        quote_request.crm_prospect = prospect

        Opportunity.objects.create(
            company=company, name=f'{quote_request.get_request_type_display()} — {quote_request.reference}',
            prospect=prospect, stage='prospecting', probability=20,
            notes=quote_request.client_notes,
        )
        quote_request.save(update_fields=['crm_customer_id', 'crm_prospect'])
    except Exception:
        pass


def _auto_create_btp_quote(company, quote_request, estimate):
    """Auto-génère un devis BTP brouillon à partir de l'estimation, avec ses lignes."""
    if not quote_request.crm_customer_id:
        return None
    try:
        quote = BTPQuote.objects.create(
            company=company, customer_id=quote_request.crm_customer_id,
            number=next_number(company, 'quote') or '',
            subject=f'Devis suite demande {quote_request.reference}',
            status='draft',
            validity_date=timezone.now().date(),
            notes=f'Généré automatiquement depuis le configurateur en ligne ({quote_request.reference}).',
        )
        if estimate:
            for order, item in enumerate(estimate.items.all().order_by('order')):
                BTPQuoteLine.objects.create(
                    quote=quote, description=item.description, unit=item.unit,
                    quantity=item.quantity, unit_price=item.unit_price_avg,
                    total_ht=item.total_avg, order=order,
                )
            quote.total_ht = estimate.amount_avg_ht
            quote.total_tva = round(float(estimate.amount_avg_ht) * 0.20, 2)
            quote.total_ttc = estimate.total_ttc
            quote.save(update_fields=['total_ht', 'total_tva', 'total_ttc'])
        quote_request.btp_quote = quote
        quote_request.status = 'quote_created'
        quote_request.save(update_fields=['btp_quote', 'status'])
        return quote
    except Exception:
        return None


def wizard_success(request, site_slug):
    site = _get_electricite_site(site_slug)
    quote_pk = request.session.get('elec_last_request_pk')
    quote_request = None
    estimate = None
    if quote_pk:
        try:
            quote_request = GuidedQuoteRequest.objects.get(pk=quote_pk, company=site.company)
            estimate = getattr(quote_request, 'estimate', None)
        except GuidedQuoteRequest.DoesNotExist:
            pass
    ctx = _wizard_context(site)
    ctx.update({'quote_request': quote_request, 'estimate': estimate})
    return render(request, 'websites/public/electricite/wizard/success.html', ctx)


def wizard_upload_photos(request, site_slug, pk):
    site = _get_electricite_site(site_slug)
    quote_request = get_object_or_404(GuidedQuoteRequest, pk=pk, company=site.company)
    if request.method == 'POST':
        for f in request.FILES.getlist('photos'):
            GuidedQuotePhoto.objects.create(request=quote_request, photo=f, caption=request.POST.get('caption', ''))
        for f in request.FILES.getlist('documents'):
            GuidedQuoteDocument.objects.create(request=quote_request, file=f, name=f.name)
        messages.success(request, 'Fichiers ajoutés avec succès.')
        return redirect('public_websites:electricite_wizard_success', site_slug=site_slug)
    ctx = _wizard_context(site)
    ctx['quote_request'] = quote_request
    return render(request, 'websites/public/electricite/wizard/upload_photos.html', ctx)


def wizard_pdf(request, site_slug, pk):
    site = _get_electricite_site(site_slug)
    quote_request = get_object_or_404(GuidedQuoteRequest, pk=pk, company=site.company)
    public_url = request.build_absolute_uri(
        reverse('public_websites:electricite_wizard_success', args=[site_slug])
    )
    buf = generate_guided_quote_pdf(quote_request, public_url=public_url)
    return FileResponse(buf, as_attachment=True, filename=f'pre-devis-{quote_request.reference}.pdf',
                         content_type='application/pdf')
