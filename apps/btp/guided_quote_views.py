"""
Vues publiques : wizard de demande de devis guidée électricité.
URL namespace: guided_quote
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from apps.core.models import Company
from .models import (
    GuidedQuoteRequest, GuidedQuoteEstimate, GuidedQuoteEstimateItem,
    GuidedQuotePhoto, GuidedQuoteDocument, ElectricityPriceLibrary,
    ClientNotification,
)


def _get_company(request):
    return getattr(request, 'current_company', None)


def _notify_manager(request, quote_request):
    """Notifie le responsable par notification interne."""
    ClientNotification.objects.create(
        client_email='admin@erp.local',
        notif_type='project',
        title=f'Nouvelle demande guidée — {quote_request.reference}',
        message=f'Demande de {quote_request.client_full_name} ({quote_request.get_request_type_display()}) reçue depuis le site.',
        link=f'/btp/demandes-guidees/{quote_request.pk}/',
    )


def _calculate_estimate(company, quote_request):
    """Calcule automatiquement un pré-devis selon les réponses."""
    answers = quote_request.answers or {}
    items = []
    total_min = 0
    total_avg = 0
    total_max = 0

    if quote_request.request_type == 'depannage':
        # Forfait déplacement
        travel = ElectricityPriceLibrary.objects.filter(company=company, category='deplacement', is_active=True).first()
        if travel:
            items.append({'item': travel, 'qty': 1, 'desc': 'Déplacement'})
            total_min += float(travel.price_min)
            total_avg += float(travel.price_avg)
            total_max += float(travel.price_max)

        # Diagnostic
        diag = ElectricityPriceLibrary.objects.filter(company=company, category='diagnostic', is_active=True).first()
        if diag:
            items.append({'item': diag, 'qty': 1, 'desc': 'Diagnostic panne'})
            total_min += float(diag.price_min)
            total_avg += float(diag.price_avg)
            total_max += float(diag.price_max)

        # Urgence
        if quote_request.urgency == 'urgent':
            forfait = ElectricityPriceLibrary.objects.filter(company=company, category='forfait', name__icontains='urgent', is_active=True).first()
            if forfait:
                items.append({'item': forfait, 'qty': 1, 'desc': 'Majoration urgence'})
                total_min += float(forfait.price_min)
                total_avg += float(forfait.price_avg)
                total_max += float(forfait.price_max)

        # Main d'oeuvre 1h estimée
        mo = ElectricityPriceLibrary.objects.filter(company=company, category='main_oeuvre', is_active=True).first()
        if mo:
            items.append({'item': mo, 'qty': 1, 'desc': 'Main-d\'œuvre estimée (1h)'})
            total_min += float(mo.price_min)
            total_avg += float(mo.price_avg)
            total_max += float(mo.price_max)

    elif quote_request.request_type in ('travaux', 'renovation', 'installation_neuve', 'mise_normes'):
        surface_key = answers.get('surface', '')
        rooms = answers.get('nb_rooms', {})

        # Prises
        nb_prises = int(answers.get('nb_prises', 0) or 0)
        prise_item = ElectricityPriceLibrary.objects.filter(company=company, category='prise_interrupteur', is_active=True).first()
        if prise_item and nb_prises:
            items.append({'item': prise_item, 'qty': nb_prises, 'desc': f'Prises ({nb_prises})'})
            total_min += float(prise_item.price_min) * nb_prises
            total_avg += float(prise_item.price_avg) * nb_prises
            total_max += float(prise_item.price_max) * nb_prises

        # Points lumineux
        nb_lights = int(answers.get('nb_lights', 0) or 0)
        light_item = ElectricityPriceLibrary.objects.filter(company=company, category='eclairage', is_active=True).first()
        if light_item and nb_lights:
            items.append({'item': light_item, 'qty': nb_lights, 'desc': f'Points lumineux ({nb_lights})'})
            total_min += float(light_item.price_min) * nb_lights
            total_avg += float(light_item.price_avg) * nb_lights
            total_max += float(light_item.price_max) * nb_lights

        # Tableau électrique
        if answers.get('replace_panel') == 'yes':
            panel_item = ElectricityPriceLibrary.objects.filter(company=company, category='tableau', is_active=True).first()
            if panel_item:
                items.append({'item': panel_item, 'qty': 1, 'desc': 'Remplacement tableau électrique'})
                total_min += float(panel_item.price_min)
                total_avg += float(panel_item.price_avg)
                total_max += float(panel_item.price_max)

        # Borne de recharge
        if answers.get('borne_recharge'):
            borne_item = ElectricityPriceLibrary.objects.filter(company=company, category='borne_recharge', is_active=True).first()
            if borne_item:
                items.append({'item': borne_item, 'qty': 1, 'desc': 'Borne de recharge VE'})
                total_min += float(borne_item.price_min)
                total_avg += float(borne_item.price_avg)
                total_max += float(borne_item.price_max)

        # Si rien trouvé, estimation forfaitaire surface
        if not items:
            ren_item = ElectricityPriceLibrary.objects.filter(company=company, category='renovation', is_active=True).first()
            if ren_item:
                qty = 50 if 'moins' in surface_key else 80 if '30' in surface_key else 100
                items.append({'item': ren_item, 'qty': qty, 'desc': f'Rénovation électrique (estimation {qty} m²)'})
                total_min += float(ren_item.price_min) * qty
                total_avg += float(ren_item.price_avg) * qty
                total_max += float(ren_item.price_max) * qty

    vat = 0.20
    total_ttc = total_avg * (1 + vat)
    estimate = GuidedQuoteEstimate.objects.create(
        request=quote_request,
        amount_min_ht=round(total_min, 2),
        amount_avg_ht=round(total_avg, 2),
        amount_max_ht=round(total_max, 2),
        labor_amount=round(total_avg * 0.6, 2),
        materials_amount=round(total_avg * 0.4, 2),
        travel_amount=round(50 if quote_request.request_type == 'depannage' else 0, 2),
        urgency_surcharge=round(total_avg * 0.25 if quote_request.urgency == 'urgent' else 0, 2),
        total_ttc=round(total_ttc, 2),
        duration_min_days=0.5 if quote_request.request_type == 'depannage' else 1,
        duration_max_days=1 if quote_request.request_type == 'depannage' else 5,
    )
    for order, it in enumerate(items):
        GuidedQuoteEstimateItem.objects.create(
            estimate=estimate,
            price_item=it['item'],
            description=it['desc'],
            quantity=it['qty'],
            unit=it['item'].unit,
            unit_price_avg=it['item'].price_avg,
            order=order,
        )
    return estimate


# ─── STEP 1 : CHOIX TYPE ──────────────────────────────────────────────────────

def wizard_start(request):
    company = _get_company(request)
    if request.method == 'POST':
        request_type = request.POST.get('request_type')
        if request_type:
            request.session['guided_request_type'] = request_type
            request.session['guided_answers'] = {}
            return redirect('guided_quote:wizard_step2')
    return render(request, 'electricity/wizard/step1_type.html', {'company': company})


# ─── STEP 2 : QUESTIONNAIRE DÉPANNAGE ─────────────────────────────────────────

def wizard_step2(request):
    company = _get_company(request)
    request_type = request.session.get('guided_request_type', 'depannage')
    if request.method == 'POST':
        answers = request.session.get('guided_answers', {})
        answers.update({
            'urgency': request.POST.get('urgency', 'normal'),
            'problem_type': request.POST.get('problem_type', ''),
            'safety_issue': request.POST.get('safety_issue', 'no'),
            'property_type': request.POST.get('property_type', ''),
            'panel_accessible': request.POST.get('panel_accessible', ''),
            # Travaux
            'work_type': request.POST.get('work_type', ''),
            'surface': request.POST.get('surface', ''),
            'old_installation': request.POST.get('old_installation', ''),
            'replace_panel': request.POST.get('replace_panel', ''),
            'nb_bedrooms': request.POST.get('nb_bedrooms', ''),
            'nb_living': request.POST.get('nb_living', ''),
            'nb_kitchen': request.POST.get('nb_kitchen', ''),
            'nb_bathroom': request.POST.get('nb_bathroom', ''),
            'nb_floors': request.POST.get('nb_floors', ''),
            'nb_prises': request.POST.get('nb_prises', ''),
            'nb_interrupteurs': request.POST.get('nb_interrupteurs', ''),
            'nb_lights': request.POST.get('nb_lights', ''),
            'nb_circuits': request.POST.get('nb_circuits', ''),
            'nb_radiateurs': request.POST.get('nb_radiateurs', ''),
            'borne_recharge': request.POST.get('borne_recharge', ''),
            'domotique': request.POST.get('domotique', ''),
            'alarme': request.POST.get('alarme', ''),
            'start_delay': request.POST.get('start_delay', ''),
            'occupied': request.POST.get('occupied', ''),
        })
        request.session['guided_answers'] = answers
        request.session['guided_urgency'] = answers.get('urgency', 'normal')
        return redirect('guided_quote:wizard_step3')
    surface_choices = [
        ('less30', 'Moins de 30 m²'), ('30-60', '30 à 60 m²'), ('60-100', '60 à 100 m²'),
        ('100-150', '100 à 150 m²'), ('more150', 'Plus de 150 m²'), ('unknown', 'Je ne sais pas'),
    ]
    problem_type_choices = [
        ('no_power_all', 'Plus de courant dans tout le logement'),
        ('no_power_room', 'Plus de courant dans une pièce'),
        ('breaker', 'Disjoncteur qui saute'),
        ('dead_outlet', 'Prise qui ne fonctionne plus'),
        ('dead_switch', 'Interrupteur défectueux'),
        ('dead_light', 'Éclairage en panne'),
        ('burn_smell', 'Odeur de brûlé'),
        ('sparks', 'Étincelles'),
        ('panel_issue', 'Tableau électrique problématique'),
        ('other', 'Autre problème'),
    ]
    property_type_choices = [
        ('apartment', 'Appartement'), ('house', 'Maison'), ('commercial', 'Local commercial'),
        ('office', 'Bureau'), ('workshop', 'Atelier'), ('building', 'Immeuble'), ('other', 'Autre'),
    ]
    # Fallback pour types inconnus → travaux
    tpl = request_type if request_type in ('depannage', 'travaux') else 'travaux'
    return render(request, f'electricity/wizard/step2_{tpl}.html', {
        'company': company, 'request_type': request_type,
        'problem_type_choices': problem_type_choices,
        'property_type_choices': property_type_choices,
        'surface_choices': surface_choices,
    })


# ─── STEP 3 : ADRESSE + CONTACT ───────────────────────────────────────────────

def wizard_step3(request):
    company = _get_company(request)
    if request.method == 'POST':
        request.session['guided_contact'] = {
            'first_name': request.POST.get('first_name', ''),
            'last_name': request.POST.get('last_name', ''),
            'email': request.POST.get('email', ''),
            'phone': request.POST.get('phone', ''),
            'address': request.POST.get('address', ''),
            'zip_code': request.POST.get('zip_code', ''),
            'city': request.POST.get('city', ''),
            'floor': request.POST.get('floor', ''),
            'digicode': request.POST.get('digicode', ''),
            'parking': request.POST.get('parking', '') == 'on',
            'preferred_slots': request.POST.get('preferred_slots', ''),
            'client_notes': request.POST.get('client_notes', ''),
            'create_portal': request.POST.get('create_portal') == 'on',
        }
        return redirect('guided_quote:wizard_step4')
    request_type = request.session.get('guided_request_type', 'depannage')
    return render(request, 'electricity/wizard/step3_contact.html', {
        'company': company, 'request_type': request_type,
    })


# ─── STEP 4 : RÉCAPITULATIF + ENVOI ──────────────────────────────────────────

def wizard_step4(request):
    company = _get_company(request)
    request_type = request.session.get('guided_request_type', 'depannage')
    answers = request.session.get('guided_answers', {})
    contact = request.session.get('guided_contact', {})

    if request.method == 'POST':
        # Créer la demande
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
            floor=contact.get('floor', ''),
            digicode=contact.get('digicode', ''),
            parking=contact.get('parking', False),
            property_type=answers.get('property_type', ''),
            surface=answers.get('surface', ''),
            answers=answers,
            client_notes=contact.get('client_notes', ''),
            preferred_slots=contact.get('preferred_slots', ''),
            create_portal_account=contact.get('create_portal', False),
        )

        # Créer espace client si demandé
        if contact.get('create_portal') and contact.get('email'):
            _create_portal_account(company, contact)

        # Calculer l'estimation
        estimate = _calculate_estimate(company, quote_request)

        # Notifier le responsable
        _notify_manager(request, quote_request)

        # Nettoyer la session
        for k in ['guided_request_type', 'guided_answers', 'guided_contact', 'guided_urgency']:
            request.session.pop(k, None)

        request.session['last_guided_request_pk'] = quote_request.pk
        return redirect('guided_quote:wizard_success')

    return render(request, 'electricity/wizard/step4_recap.html', {
        'company': company,
        'request_type': request_type,
        'answers': answers,
        'contact': contact,
    })


def _create_portal_account(company, contact):
    """Crée un compte portail client depuis les données de contact."""
    from apps.portals.models import ClientPortalAccount
    email = contact.get('email', '')
    if not email or User.objects.filter(email=email).exists():
        return
    import secrets
    pwd = secrets.token_urlsafe(12)
    username = email.split('@')[0]
    base = username
    i = 1
    while User.objects.filter(username=username).exists():
        username = f'{base}{i}'; i += 1
    user = User.objects.create_user(
        username=username, email=email, password=pwd,
        first_name=contact.get('first_name', ''),
        last_name=contact.get('last_name', ''),
    )
    ClientPortalAccount.objects.create(
        company=company, user=user, email=email,
        first_name=contact.get('first_name', ''),
        last_name=contact.get('last_name', ''),
        phone=contact.get('phone', ''),
        created_from_guided_quote=True,
    )


def wizard_success(request):
    company = _get_company(request)
    quote_pk = request.session.get('last_guided_request_pk')
    quote_request = None
    estimate = None
    if quote_pk:
        try:
            quote_request = GuidedQuoteRequest.objects.get(pk=quote_pk, company=company)
            estimate = getattr(quote_request, 'estimate', None)
        except GuidedQuoteRequest.DoesNotExist:
            pass
    return render(request, 'electricity/wizard/success.html', {
        'company': company,
        'quote_request': quote_request,
        'estimate': estimate,
    })


# ─── PAGE UPLOAD PHOTOS ────────────────────────────────────────────────────────

def wizard_upload_photos(request, pk):
    company = _get_company(request)
    quote_request = get_object_or_404(GuidedQuoteRequest, pk=pk, company=company)
    if request.method == 'POST':
        for f in request.FILES.getlist('photos'):
            GuidedQuotePhoto.objects.create(
                request=quote_request, photo=f,
                caption=request.POST.get('caption', ''),
            )
        for f in request.FILES.getlist('documents'):
            GuidedQuoteDocument.objects.create(
                request=quote_request, file=f,
                name=f.name,
            )
        messages.success(request, 'Fichiers ajoutés avec succès.')
        return redirect('guided_quote:wizard_success')
    return render(request, 'electricity/wizard/upload_photos.html', {
        'company': company, 'quote_request': quote_request,
    })
