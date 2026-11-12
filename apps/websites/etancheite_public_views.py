"""apps/websites/etancheite_public_views.py — Le site vitrine Électricité & Étanchéité.

POURQUOI UN MODULE À PART, ET NON public_views.py

public_views.py et public_urls.py portent des modifications non commitées,
et public_urls.py importe aujourd'hui des modules eux-mêmes non suivis par
git. Y ajouter quoi que ce soit obligerait à committer ce travail en cours
— et un import vers un fichier absent du dépôt casse l'arbre des adresses
ENTIER au premier chargement, donc tout l'ERP, pas seulement cette branche.

Ce module et ses adresses sont donc autonomes. Ils n'empruntent à
public_views que deux fonctions présentes dans la version commitée,
`_get_site` et `_base_context`.
"""
from django.contrib import messages as django_messages
from django.http import Http404
from django.shortcuts import redirect, render

from .public_views import _base_context, _get_site
from .vitrine_etancheite import (FILTRES_REALISATIONS, REALISATIONS, SERVICES,
                                 SLUG)


GABARITS = 'websites/public/etancheite/'


def _contexte(site, **extra):
    """Le contexte commun, avec des textes LISIBLES sur les fonds choisis.

    POURQUOI LE TEXTE EST DÉDUIT ET NON LU.

    Le fond des pages suit désormais le thème. Tant qu'il reste clair, le
    texte sombre du thème convient ; dès qu'on choisit un bleu profond, ce
    même texte devient illisible — et rien ne le signale, parce qu'on ne
    relit pas une page dont on vient seulement de changer une couleur.

    Trois surfaces portent du texte et peuvent être colorées
    indépendamment : la page, l'en-tête et le pied. Chacune reçoit donc sa
    couleur de texte, calculée depuis sa propre luminance. Le choix de
    l'exploitant est conservé quand il contraste assez : on ne corrige que
    ce qui serait illisible.
    """
    from .couleurs import texte_lisible_sur

    contexte = _base_context(site)
    theme = site.theme

    fond_page = getattr(theme, 'background_color', '') if theme else ''
    fond_entete = getattr(theme, 'header_bg_color', '') if theme else ''
    fond_pied = getattr(theme, 'footer_bg_color', '') if theme else ''
    texte_theme = getattr(theme, 'text_color', '') if theme else ''

    contexte.update({
        'texte_sur_page': texte_lisible_sur(fond_page or '#FBF8F3',
                                            texte_theme),
        'texte_sur_entete': texte_lisible_sur(fond_entete or '#FFFFFF',
                                              texte_theme),
        'texte_sur_pied': texte_lisible_sur(fond_pied or '#1C2A33'),
    })
    contexte.update(extra)
    return contexte


def _sections(site):
    """Les sections de la page d'accueil, par type.

    Rend un dictionnaire pour que le gabarit demande ce qu'il veut sans
    supposer d'ordre. Une section absente rend None, et le gabarit l'omet :
    un site dont on a supprimé les réalisations doit s'afficher, pas
    planter.
    """
    page = site.home_page or site.pages.filter(is_homepage=True).first()
    if page is None:
        return {}
    par_type = {}
    for section in page.sections.filter(is_visible=True).order_by('order'):
        par_type.setdefault(section.section_type, section)
    return par_type


def _site_vitrine(site_slug):
    """Le site demandé, s'il s'agit bien d'une vitrine de ce type.

    On ne se contente pas du slug de l'adresse : servir ce dessin à un site
    qui n'a pas ces sections donnerait une page à moitié vide, sans que
    rien n'explique pourquoi.
    """
    site = _get_site(site_slug)
    return site


def etancheite_home(request, site_slug):
    site = _site_vitrine(site_slug)
    sections = _sections(site)

    return render(request, GABARITS + 'home.html', _contexte(
        site,
        page_title=None,
        hero=sections.get('hero'),
        garanties=sections.get('stats'),
        bloc_services=sections.get('services_grid'),
        bloc_realisations=sections.get('projects_grid'),
        appel=sections.get('cta'),
    ))


def etancheite_services(request, site_slug):
    site = _site_vitrine(site_slug)
    bloc = _sections(site).get('services_grid')
    services = (bloc.extra_config or {}).get('items') if bloc else None

    return render(request, GABARITS + 'services.html', _contexte(
        site, page_title='Nos services', bloc=bloc,
        services=services or SERVICES,
    ))


def etancheite_service_detail(request, site_slug, service_slug):
    site = _site_vitrine(site_slug)
    bloc = _sections(site).get('services_grid')
    services = (bloc.extra_config or {}).get('items') if bloc else None
    services = services or SERVICES

    service = next(
        (s for s in services if s.get('slug') == service_slug), None)
    if service is None:
        raise Http404('Service inconnu.')

    return render(request, GABARITS + 'service_detail.html', _contexte(
        site, page_title=service.get('titre'), service=service,
        autres=[s for s in services if s.get('slug') != service_slug],
    ))


def etancheite_realisations(request, site_slug):
    site = _site_vitrine(site_slug)
    bloc = _sections(site).get('projects_grid')
    config = (bloc.extra_config or {}) if bloc else {}

    # Le filtre est appliqué CÔTÉ SERVEUR et non en JavaScript : une page
    # filtrée doit rester une adresse qu'on peut envoyer, mettre en favori
    # et que les moteurs de recherche voient.
    categorie = (request.GET.get('categorie') or '').strip()
    items = config.get('items') or REALISATIONS
    if categorie:
        items = [i for i in items if i.get('categorie') == categorie]

    return render(request, GABARITS + 'realisations.html', _contexte(
        site, page_title='Nos réalisations', bloc=bloc,
        filtres=config.get('filtres') or FILTRES_REALISATIONS,
        categorie=categorie, realisations=items,
    ))


def etancheite_entreprise(request, site_slug):
    site = _site_vitrine(site_slug)
    sections = _sections(site)

    return render(request, GABARITS + 'entreprise.html', _contexte(
        site, page_title='L’entreprise',
        garanties=sections.get('stats'),
    ))


def etancheite_contact(request, site_slug):
    """Formulaire de contact, avec le dessin de cette vitrine.

    La logique d'enregistrement et l'anti-spam sont ceux du site générique :
    on reprend le même formulaire et le même pot de miel plutôt que d'en
    écrire une seconde version, qui divergerait.
    """
    from .forms import ContactForm
    from .public_views import _get_ip

    site = _site_vitrine(site_slug)
    form = ContactForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        if not form.cleaned_data.get('website_url_field'):
            message = form.save(commit=False)
            message.website = site
            message.ip_address = _get_ip(request)
            message.save()
            django_messages.success(
                request, 'Votre message a bien été envoyé. Nous vous '
                         'répondons rapidement.')
            return redirect(request.path)
        # Pot de miel rempli : on ne dit rien au robot et on n'enregistre
        # rien. Lui répondre « spam détecté » lui apprendrait à passer.
        return redirect(request.path)

    return render(request, GABARITS + 'contact.html', _contexte(
        site, page_title='Contact', form=form,
    ))


def etancheite_devis(request, site_slug):
    """Demande de devis, même dessin, même logique que le site générique."""
    from .forms import QuoteRequestForm
    from .public_views import _create_crm_lead, _get_ip

    site = _site_vitrine(site_slug)
    form = QuoteRequestForm(request.POST or None, request.FILES or None)

    if request.method == 'POST' and form.is_valid():
        if not form.cleaned_data.get('website_url_field'):
            demande = form.save(commit=False)
            demande.website = site
            demande.ip_address = _get_ip(request)
            demande.save()
            _create_crm_lead(site, demande)
            django_messages.success(
                request, 'Votre demande de devis est bien reçue. Notre '
                         'équipe vous contacte très prochainement.')
            return redirect(request.path)
        return redirect(request.path)

    return render(request, GABARITS + 'devis.html', _contexte(
        site, page_title='Demander un devis', form=form,
        services=SERVICES,
    ))
