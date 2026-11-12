"""apps/websites/vitrine_etancheite.py — Le site vitrine Électricité & Étanchéité.

CE QUE CE MODULE EST, ET CE QU'IL N'EST PAS

Il décrit le CONTENU d'un site vitrine pour une entreprise d'électricité et
d'étanchéité, et sait le créer pour une entreprise donnée. Il ne décrit
aucune mise en page : celle-ci vit dans
templates/websites/public/etancheite/.

POURQUOI DES DONNÉES ET NON UN GABARIT FIGÉ

Un site vitrine dont les textes sont écrits en dur dans un gabarit ne
s'édite pas depuis l'ERP : il faut un accès au code pour changer un numéro
de téléphone. Tout ce qui est du contenu — titres, accroches, services,
coordonnées — passe donc par Website, WebsitePage et WebsiteSection, les
modèles que l'éditeur de sites manipule déjà. Seule la mise en page reste
dans les gabarits, parce que c'est du dessin et non du texte.

POURQUOI PAS UNE MIGRATION DE DONNÉES

Une migration qui sèmerait ce site s'exécuterait sur TOUTES les
installations, y compris celles d'un autre métier, et y déposerait une
vitrine d'électricien que personne n'a demandée. La création est donc un
geste : un bouton dans l'ERP, pour l'entreprise de son choix. Le code,
lui, arrive bien par la mise à jour.

IDEMPOTENT

Rappeler `creer_le_site` pour la même entreprise ne crée pas un second
site : il rend celui qui existe. Reconstruire son contenu est un geste
séparé et explicite, parce que cela écraserait des textes retouchés à la
main.
"""
from django.utils import timezone


SLUG = 'electricite-etancheite'

# La palette du dessin : ardoise profonde, sable chaud, or discret. Les noms
# de champs sont ceux de WebsiteTheme, pour que l'éditeur de thèmes de l'ERP
# puisse ensuite les retoucher sans surprise.
THEME = {
    'name': 'Électricité & Étanchéité',
    'primary_color': '#1C2A33',      # ardoise, fonds sombres
    'secondary_color': '#2E3F4A',    # ardoise claire
    'accent_color': '#C9A227',       # or discret, filets et icônes
    'background_color': '#FBF8F3',   # sable très clair
    'text_color': '#1C2A33',
    'button_color': '#E8D9BE',       # sable, boutons principaux
    'header_bg_color': '#FFFFFF',
    'footer_bg_color': '#1C2A33',
}

SITE = {
    'name': 'Électricité & Étanchéité',
    'site_type': 'showcase',
    'meta_title': 'Expert BTP en électricité & étanchéité',
    'meta_description': (
        "Installations électriques et solutions d'étanchéité pour vos "
        "projets de construction neuve et de rénovation."),
    'contact_phone': '06 12 34 56 78',
    'country': 'France',
    'language': 'fr',
}

# Les quatre gages de confiance de la bande claire, sous l'image.
GARANTIES = [
    {'icone': 'bi-award', 'titre': '15+ ans d’expérience',
     'texte': 'Un savoir-faire reconnu en électricité et en étanchéité (BTP).'},
    {'icone': 'bi-patch-check', 'titre': 'Interventions certifiées',
     'texte': 'Des installations conformes aux normes en vigueur '
              '(NF, C15-100…).'},
    {'icone': 'bi-layers', 'titre': 'Qualité & durabilité',
     'texte': 'Des solutions fiables et performantes pour une protection '
              'longue durée.'},
    {'icone': 'bi-geo-alt', 'titre': 'Réactivité & proximité',
     'texte': 'Une équipe disponible et à votre écoute pour des '
              'interventions rapides.'},
]

SERVICES = [
    {'slug': 'electricite-generale', 'icone': 'bi-lightning-charge',
     'titre': 'Électricité générale',
     'texte': 'Installations électriques complètes pour logements, villas '
              'et bâtiments.'},
    {'slug': 'mise-aux-normes', 'icone': 'bi-clipboard-check',
     'titre': 'Mise aux normes',
     'texte': 'Rénovation, sécurité, tableaux électriques, conformité.'},
    {'slug': 'etancheite-toiture', 'icone': 'bi-layers',
     'titre': 'Étanchéité toiture',
     'texte': 'Toitures plates, membranes, protection durable.'},
    {'slug': 'etancheite-terrasses', 'icone': 'bi-droplet',
     'titre': 'Étanchéité terrasses',
     'texte': 'Terrasses, balcons, murs enterrés, prévention des '
              'infiltrations.'},
]

# Les filtres de la bande sombre. « tous » est traité à part par le gabarit.
FILTRES_REALISATIONS = [
    {'slug': 'electricite', 'libelle': 'Électricité'},
    {'slug': 'etancheite', 'libelle': 'Étanchéité'},
    {'slug': 'renovation', 'libelle': 'Rénovation'},
    {'slug': 'maintenance', 'libelle': 'Maintenance'},
]

REALISATIONS = [
    {'titre': 'Villa contemporaine — éclairage et domotique',
     'categorie': 'electricite',
     'texte': 'Installation complète, pilotage centralisé, éclairage '
              'architectural.'},
    {'titre': 'Tableaux et armoires — bâtiment tertiaire',
     'categorie': 'electricite',
     'texte': 'Mise aux normes, repérage, protection différentielle.'},
    {'titre': 'Toiture plate — membrane bitumineuse',
     'categorie': 'etancheite',
     'texte': 'Reprise complète, relevés, évacuations et lanterneau.'},
    {'titre': 'Terrasse sur plots — étanchéité et finition',
     'categorie': 'etancheite',
     'texte': 'Protection, isolation, dalle sur plots et garde-corps.'},
]


def _texte_hero():
    return {
        'eyebrow': 'EXPERT BTP EN ÉLECTRICITÉ & ÉTANCHÉITÉ',
        'titre': 'Sécuriser, alimenter, protéger vos bâtiments',
        'texte': 'Notre expertise en installations électriques et en '
                 'solutions d’étanchéité pour vos projets de construction '
                 'neuve et de rénovation.',
        'bouton': 'Demander un devis gratuit',
        'bouton_secondaire': 'Découvrir nos réalisations',
    }


# ── Construction ─────────────────────────────────────────────────────────────

def _obtenir_le_theme(company):
    from .models import WebsiteTheme

    theme, _ = WebsiteTheme.objects.get_or_create(
        company=company, name=THEME['name'],
        defaults={cle: valeur for cle, valeur in THEME.items()
                  if cle != 'name'},
    )
    return theme


def site_existant(company):
    """Le site de cette entreprise, ou None."""
    from .models import Website

    return Website.objects.filter(company=company, slug=SLUG).first()


def creer_le_site(company, user=None, *, reconstruire_le_contenu=False):
    """Crée le site vitrine pour cette entreprise. Rend (site, cree).

    `reconstruire_le_contenu` RÉÉCRIT les sections de la page d'accueil.
    C'est destructeur pour des textes retouchés à la main, donc jamais
    fait tout seul — c'est la leçon du semis des modules, qui effaçait un
    choix d'exploitant à chaque affichage de page.
    """
    from .models import Website, WebsitePage

    if company is None:
        raise ValueError('Une entreprise est nécessaire pour créer un site.')

    site = site_existant(company)
    cree = False

    if site is None:
        site = Website.objects.create(
            company=company,
            slug=SLUG,
            theme=_obtenir_le_theme(company),
            status='published',
            is_active=True,
            is_published=True,
            published_at=timezone.now(),
            **SITE,
        )
        cree = True

    accueil = WebsitePage.objects.filter(
        website=site, slug='accueil').first()
    if accueil is None:
        accueil = WebsitePage.objects.create(
            website=site, slug='accueil', title='Accueil',
            page_type='home', status='published',
            is_homepage=True, show_in_menu=True, order=0,
        )
        site.home_page = accueil
        site.save(update_fields=['home_page'])
        _construire_les_sections(accueil)
    elif reconstruire_le_contenu:
        accueil.sections.all().delete()
        _construire_les_sections(accueil)

    return site, cree


def _construire_les_sections(page):
    """Pose les sections de la page d'accueil, dans l'ordre du dessin."""
    from .models import WebsiteSection

    hero = _texte_hero()
    sections = [
        dict(section_type='hero', order=0,
             title=hero['titre'], subtitle=hero['eyebrow'],
             content=hero['texte'],
             button_text=hero['bouton'], button_link='devis',
             button_secondary_text=hero['bouton_secondaire'],
             button_secondary_link='realisations',
             extra_config={}),

        dict(section_type='stats', order=1, title='', content='',
             extra_config={'items': GARANTIES}),

        dict(section_type='services_grid', order=2,
             subtitle='NOS SERVICES',
             title='Un accompagnement complet pour tous vos projets '
                   'd’électricité et d’étanchéité',
             button_text='Voir tous nos services', button_link='services',
             extra_config={'items': SERVICES}),

        dict(section_type='projects_grid', order=3,
             subtitle='NOS RÉALISATIONS',
             title='Des réalisations concrètes qui illustrent notre '
                   'expertise en électricité et étanchéité',
             button_text='Voir toutes nos réalisations',
             button_link='realisations',
             extra_config={'filtres': FILTRES_REALISATIONS,
                           'items': REALISATIONS}),

        dict(section_type='cta', order=4,
             title='Un projet d’électricité ou d’étanchéité ?',
             content='Parlons-en. Nous étudions votre besoin et vous '
                     'répondons sous 48 heures.',
             button_text='Demander un devis gratuit', button_link='devis',
             extra_config={}),
    ]

    for donnees in sections:
        WebsiteSection.objects.create(page=page, is_visible=True, **donnees)
