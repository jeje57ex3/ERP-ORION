"""
apps/websites/electricite_public_views.py — Vues publiques du site Électricité.
Pattern calqué sur apps/websites/btp_public_views.py (mêmes helpers réutilisés :
_base_context, _get_ip, _notify_erp).
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.translation import gettext as _

from .models import Website, BTPPortfolioProject, BTPWebsiteReview, BTPClientAccessRequest, BTPEmergencyRequest
from .public_views import _base_context, _get_ip, translate_static_items, translate_faq_items
from .btp_public_views import _notify_erp
from .electricite_wizard_views import _get_electricite_site
from django.templatetags.static import static


ELECTRICITE_SERVICES = [
    {'slug': 'electricite-generale', 'icon': 'bi-lightning-charge-fill', 'name': 'Électricité générale',
     'desc': 'Installation, rénovation, mise aux normes NF C 15-100.'},
    {'slug': 'domotique', 'icon': 'bi-house-gear-fill', 'name': 'Domotique',
     'desc': 'Pilotage centralisé éclairage, volets, chauffage, scénarios.'},
    {'slug': 'reseau-informatique', 'icon': 'bi-diagram-3-fill', 'name': 'Réseau informatique',
     'desc': 'Câblage RJ45, brassage, infrastructure réseau professionnelle.'},
    {'slug': 'baies-de-brassage', 'icon': 'bi-hdd-rack-fill', 'name': 'Baies de brassage',
     'desc': 'Installation et organisation de baies informatiques.'},
    {'slug': 'wifi-professionnel', 'icon': 'bi-wifi', 'name': 'Wi-Fi professionnel',
     'desc': 'Couverture Wi-Fi optimisée pour locaux professionnels.'},
    {'slug': 'videosurveillance', 'icon': 'bi-camera-video-fill', 'name': 'Vidéosurveillance',
     'desc': 'Caméras IP, enregistrement, supervision à distance.'},
    {'slug': 'alarmes', 'icon': 'bi-bell-fill', 'name': 'Alarmes',
     'desc': 'Détection intrusion, alerte, télésurveillance.'},
    {'slug': 'controle-acces', 'icon': 'bi-fingerprint', 'name': "Contrôle d'accès",
     'desc': 'Badges, digicodes, interphonie, visiophonie.'},
    {'slug': 'bornes-de-recharge', 'icon': 'bi-ev-station-fill', 'name': 'Bornes de recharge',
     'desc': 'Installation de bornes de recharge véhicules électriques.'},
    {'slug': 'eclairage', 'icon': 'bi-lightbulb-fill', 'name': 'Éclairage',
     'desc': 'LED, spots, éclairage extérieur et scénarisation lumineuse.'},
    {'slug': 'depannage', 'icon': 'bi-tools', 'name': 'Dépannage',
     'desc': 'Intervention rapide sur panne électrique.'},
    {'slug': 'maintenance', 'icon': 'bi-wrench-adjustable', 'name': 'Maintenance',
     'desc': 'Suivi préventif et curatif de vos installations.'},
    {'slug': 'contrats-entretien', 'icon': 'bi-file-earmark-check-fill', 'name': "Contrats d'entretien",
     'desc': 'Visites périodiques planifiées, priorité d\'intervention.'},
]

FAQ_ITEMS = [
    ('Combien coûte une mise aux normes électriques ?',
     "Le coût dépend de la surface, de l'état de l'installation existante et du niveau de gamme choisi. "
     "Utilisez notre configurateur pour obtenir un pré-devis instantané."),
    ('Intervenez-vous en urgence ?',
     "Oui, notre service de dépannage traite les urgences électriques (coupure totale, odeur de brûlé, "
     "étincelles) en priorité — utilisez le configurateur de dépannage."),
    ('Proposez-vous des contrats d\'entretien ?',
     "Oui, des contrats avec visites périodiques planifiées et priorité d'intervention sont disponibles — "
     "contactez-nous pour un devis personnalisé."),
    ('Puis-je suivre ma demande en ligne ?',
     "Oui, à la fin du configurateur vous recevez une référence et pouvez créer un espace client pour "
     "suivre l'avancement, vos documents et échanger avec nos équipes."),
    ('Les devis sont-ils gratuits ?',
     "Le pré-devis généré par le configurateur est gratuit et sans engagement. Un devis ferme est établi "
     "après diagnostic ou visite technique si nécessaire."),
]


def _elec_context(site):
    ctx = _base_context(site)
    ctx.update({
        # Opaque par defaut : seule l'accueil pose son en-tete sur une
        # photo. Le defaut le plus sur est celui qui reste lisible.
        'entete_sur_photo': False,
        'page_courante': '',
        'elec_portfolio': site.btp_portfolio_projects.filter(is_published=True).order_by('order')[:6],
        'elec_reviews': site.btp_reviews.filter(is_published=True).order_by('order')[:6],
        'services': translate_static_items(ELECTRICITE_SERVICES, 'electricite.service'),
    })
    return ctx


# ─── Les visuels livres avec le site ─────────────────────────────────────────
#
# Neuf photographies accompagnent le site (voir
# static/img/sites/sparkling-peace/CREDITS.md). Elles ne sont qu'un REPLI :
# des qu'un service ou une realisation porte sa propre image, c'est elle qui
# s'affiche. L'exploitant remplace donc les visuels un par un, depuis l'ERP,
# sans jamais passer par le code — et sans qu'une page reste vide en
# attendant qu'il le fasse.

PHOTOS_DE_SERVICE = [
    'service-electricite.jpg',
    'service-mise-aux-normes.jpg',
    'service-etancheite-toiture.jpg',
    'service-etancheite-terrasse.jpg',
]

PHOTOS_DE_REALISATION = [
    'realisation-electricite.jpg',
    'realisation-etancheite.jpg',
    'realisation-renovation.jpg',
    'realisation-maintenance.jpg',
]


def _photo_livree(nom):
    return static(f'img/sites/sparkling-peace/{nom}')


def _cartes_de_services(proposes, types):
    """Les quatre cartes de la page d'accueil, visuel resolu.

    La resolution se fait ICI et non dans le gabarit : un gabarit qui doit
    choisir entre l'image d'un objet et une liste indexee par le compteur de
    boucle demande un filtre sur mesure, et devient illisible. La vue rend
    quatre dictionnaires prets a afficher.
    """
    cartes = []
    source = proposes or []

    for index in range(4):
        photo = _photo_livree(PHOTOS_DE_SERVICE[index])

        if index < len(source):
            service = source[index]
            cartes.append({
                'titre': service.title,
                'texte': service.description,
                'icone': service.icon or 'bi-lightning-charge-fill',
                # L'image de l'exploitant prime ; la notre comble le vide.
                'image': service.image.url if service.image else photo,
            })
        elif index < len(types):
            cartes.append({
                'titre': types[index]['name'],
                'texte': types[index]['desc'],
                'icone': types[index]['icon'],
                'image': photo,
            })

    return cartes


def _vignettes(portfolio):
    """Les quatre vignettes de realisations, visuel resolu."""
    vignettes = []
    projets = list(portfolio)[:4]

    for index in range(4):
        if index < len(projets):
            projet = projets[index]
            image = projet.after_image or projet.before_image
            vignettes.append({
                'titre': projet.title,
                'image': image.url if image else _photo_livree(PHOTOS_DE_REALISATION[index]),
            })
        else:
            vignettes.append({
                'titre': '',
                'image': _photo_livree(PHOTOS_DE_REALISATION[index]),
            })

    return vignettes


def electricite_home(request, site_slug):
    site = _get_electricite_site(site_slug)
    ctx = _elec_context(site)
    # « entete_sur_photo » : sur l'accueil l'en-tete est POSE sur la photo
    # du hero, donc transparent avec du texte clair. Ailleurs il n'y a pas
    # de photo derriere — il redevient opaque, sans quoi ce meme texte
    # clair se poserait sur un fond clair. Un seul gabarit d'en-tete, deux
    # situations, et c'est ce drapeau qui les distingue.
    #
    # La photo du hero vient de la premiere realisation publiee : elle
    # montre un vrai chantier de l'entreprise plutot qu'une image de
    # banque. Facultative — sans elle le degrade tient la page.
    vedette = next((p for p in ctx['elec_portfolio'] if p.after_image), None)
    proposes = list(site.services.filter(is_active=True).order_by('order')[:4])

    ctx.update({
        'featured_services': proposes or None,
        'cartes_services': _cartes_de_services(proposes, ctx['services']),
        'vignettes': _vignettes(ctx['elec_portfolio']),
        'hero_image': (vedette.after_image.url if vedette
                       else static('img/sites/sparkling-peace/hero-villa.jpg')),
        'entete_sur_photo': True,
        'page_courante': 'accueil',
        'page_title': site.meta_title or f'{site.company.name} — Électricité & Étanchéité',
    })
    return render(request, 'websites/public/electricite/home.html', ctx)


def electricite_about(request, site_slug):
    site = _get_electricite_site(site_slug)
    ctx = _elec_context(site)
    ctx['page_title'] = _('À propos')
    return render(request, 'websites/public/electricite/about.html', ctx)


def electricite_services(request, site_slug):
    site = _get_electricite_site(site_slug)
    ctx = _elec_context(site)
    ctx.update({
        'website_services': site.services.filter(is_active=True).order_by('order'),
        'page_title': _('Nos services'),
    })
    return render(request, 'websites/public/electricite/services.html', ctx)


def electricite_service_detail(request, site_slug, service_slug):
    site = _get_electricite_site(site_slug)
    ctx = _elec_context(site)
    website_service = site.services.filter(slug=service_slug, is_active=True).first()
    static_service = next((s for s in translate_static_items(ELECTRICITE_SERVICES, 'electricite.service') if s['slug'] == service_slug), None)
    if not website_service and not static_service:
        from django.http import Http404
        raise Http404
    ctx.update({
        'website_service': website_service,
        'static_service': static_service,
        'page_title': (website_service.title if website_service else static_service['name']),
    })
    return render(request, 'websites/public/electricite/service_detail.html', ctx)


def electricite_portfolio(request, site_slug):
    site = _get_electricite_site(site_slug)
    ctx = _elec_context(site)
    ctx.update({
        'portfolio_projects': site.btp_portfolio_projects.filter(is_published=True).order_by('order', '-created_at'),
        'page_title': _('Nos réalisations'),
    })
    return render(request, 'websites/public/electricite/realisations.html', ctx)


def electricite_reviews(request, site_slug):
    site = _get_electricite_site(site_slug)
    ctx = _elec_context(site)
    reviews = site.btp_reviews.filter(is_published=True).order_by('order', '-created_at')
    avg_rating = (sum(r.rating for r in reviews) / reviews.count()) if reviews.exists() else None
    ctx.update({'reviews': reviews, 'avg_rating': avg_rating, 'page_title': _('Avis clients')})
    return render(request, 'websites/public/electricite/avis.html', ctx)


def electricite_faq(request, site_slug):
    site = _get_electricite_site(site_slug)
    ctx = _elec_context(site)
    ctx.update({'faq_items': translate_faq_items(FAQ_ITEMS, 'electricite.faq'), 'page_title': _('FAQ')})
    return render(request, 'websites/public/electricite/faq.html', ctx)


def electricite_calculateur(request, site_slug):
    """Calculateur énergétique — consommation, puissance, coût, ROI solaire/batterie/borne VE."""
    site = _get_electricite_site(site_slug)
    ctx = _elec_context(site)
    ctx['page_title'] = _('Calculateur énergétique')
    return render(request, 'websites/public/electricite/calculateur.html', ctx)


def electricite_contact(request, site_slug):
    site = _get_electricite_site(site_slug)
    ctx = _elec_context(site)
    ctx['page_title'] = _('Nous contacter')
    if request.method == 'POST' and not request.POST.get('website_url_field'):
        from .models import ContactMessage
        msg = ContactMessage.objects.create(
            website=site,
            name=request.POST.get('name', '').strip()[:200],
            email=request.POST.get('email', '').strip()[:254],
            phone=request.POST.get('phone', '').strip()[:20],
            subject=request.POST.get('subject', '').strip()[:200],
            message=request.POST.get('message', '').strip(),
            ip_address=_get_ip(request),
        )
        _notify_erp(site, f'Nouveau message de {msg.name}', msg.message[:200],
                     'Nouveau message contact', 'electricite_contact')
        ctx['success'] = True
    return render(request, 'websites/public/electricite/contact.html', ctx)


def electricite_client_access(request, site_slug):
    site = _get_electricite_site(site_slug)
    ctx = _elec_context(site)
    ctx['page_title'] = _('Espace client')
    if request.method == 'POST' and not request.POST.get('website_url_field') and request.POST.get('form_type') == 'access_request':
        access = BTPClientAccessRequest.objects.create(
            website=site,
            first_name=request.POST.get('first_name', '').strip()[:100],
            last_name=request.POST.get('last_name', '').strip()[:100],
            email=request.POST.get('email', '').strip()[:254],
            phone=request.POST.get('phone', '').strip()[:20],
            message=request.POST.get('message', '').strip(),
            reference=request.POST.get('reference', '').strip()[:100],
            ip_address=_get_ip(request),
        )
        _notify_erp(site, f"Demande d'accès portail — {access.first_name} {access.last_name}",
                     f"Email : {access.email}  |  Réf : {access.reference or 'non renseignée'}",
                     "Demande accès espace client", 'client_access_request')
        ctx['access_success'] = True
    return render(request, 'websites/public/electricite/espace_client.html', ctx)


def electricite_mentions_legales(request, site_slug):
    site = _get_electricite_site(site_slug)
    ctx = _elec_context(site)
    ctx['page_title'] = _('Mentions légales')
    return render(request, 'websites/public/electricite/mentions_legales.html', ctx)


def electricite_confidentialite(request, site_slug):
    site = _get_electricite_site(site_slug)
    ctx = _elec_context(site)
    ctx['page_title'] = _('Politique de confidentialité')
    return render(request, 'websites/public/electricite/confidentialite.html', ctx)
