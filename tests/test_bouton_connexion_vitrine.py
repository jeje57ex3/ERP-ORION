# -*- coding: utf-8 -*-
"""Le bouton d'accès à l'espace client sur la vitrine, et le 404 qu'il cachait.

**LE DÉFAUT TROUVÉ AVANT D'AVOIR ÉCRIT LE BOUTON.** La vitrine portait
déjà DEUX liens vers `client_portal:login` — un dans le pied de page, un
sur la page « espace client ». Les deux rendaient **404** dès qu'on y
accédait par le domaine du site.

La cause : `CHEMINS_RESERVES` de
`apps/websites/domaine_vitrine_middleware.py` ne contenait pas `/client/`.
La réécriture transformait donc `/client/connexion/` en
`/sites/<slug>/client/connexion/`, qui ne correspond à aucune route.

Mesuré : 404 par le domaine, 200 par un hôte interne. Et c'est pour cela
que personne ne l'avait vu — on développe et on essaie depuis l'adresse
interne, où tout fonctionne. Le défaut n'attendait qu'un client cliquant
depuis s-peace.com, c'est-à-dire la seule personne pour qui ces liens
existent.

**LE BOUTON LUI-MÊME N'EST PAS UN `sp-btn`, ET C'EST MESURÉ.** La feuille
du site porte `.sp-entete__actions .sp-btn { display: none }` sous 940 px.
Un bouton de connexion ainsi stylé aurait disparu au téléphone —
l'appareil depuis lequel un client regarde son chantier.
"""
import os
import re

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from apps.core.models import Company

pytestmark = pytest.mark.django_db

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEUILLE = os.path.join(RACINE, 'static', 'css', 'sites',
                       'sparkling-peace.css')
ENTETE = os.path.join(RACINE, 'templates', 'websites', 'public',
                      'electricite', 'components', 'header.html')

DOMAINE = 's-peace.test'
HOTES = ['testserver', DOMAINE]


# ═══════════════════════════════════════════════════════════════════════════
#  Décor
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def vitrine(db):
    """La vitrine ÉLECTRICITÉ, avec son domaine propre.

    Le type « electricite » n'est pas décoratif : `_prefixe_public` route
    par `site_type`, et un site d'un autre type serait servi par un autre
    dessin — le piège qui m'a déjà coûté deux tours sur ce site.
    """
    from apps.core import middleware
    from apps.websites.models import Website, WebsiteDomain, WebsiteTheme

    middleware._setup_complete_cache = None
    entreprise = Company.objects.create(name='Sparkling Peace',
                                        slug='sp-elec-bouton')
    theme = WebsiteTheme.objects.create(
        name='SP', primary_color='#0B1220', secondary_color='#F5B93D',
        font_primary='Inter')
    site = Website.objects.create(
        company=entreprise, name='Sparkling Peace Électricité',
        slug='sp-elec-bouton', site_type='electricite', is_active=True,
        is_published=True, status='published', theme=theme)
    WebsiteDomain.objects.create(
        website=site, company=entreprise, domain=DOMAINE,
        full_domain=DOMAINE, status='active', is_active_flag=True,
        dns_verified=True, verification_status='verified')
    yield site
    middleware._setup_complete_cache = None


# ═══════════════════════════════════════════════════════════════════════════
#  1. L'espace client est atteignable depuis le domaine de la vitrine
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(ALLOWED_HOSTS=HOTES)
def test_la_connexion_client_repond_depuis_le_domaine_du_site(vitrine, client):
    """LE DÉFAUT CENTRAL, et il rendait 404.

    C'est la seule mesure qui compte : un visiteur de s-peace.com qui
    clique sur « Espace client ». Le reste du test de ce fichier vérifie
    que le bouton existe ; celui-ci vérifie qu'il mène quelque part.
    """
    reponse = client.get(reverse('client_portal:login'), HTTP_HOST=DOMAINE)
    assert reponse.status_code == 200, (
        'la connexion client rend %s depuis le domaine de la vitrine'
        % reponse.status_code)


@override_settings(ALLOWED_HOSTS=HOTES)
def test_la_reecriture_ne_touche_plus_aux_chemins_du_portail(vitrine):
    """Mesuré sur le middleware lui-même, pour nommer la cause.

    Le test précédent constate le symptôme ; celui-ci montre que la
    réécriture laisse le chemin intact. Les deux ensemble disent « ça
    marche » ET « pourquoi ».
    """
    from django.test import RequestFactory

    from apps.websites.middleware import WebsiteResolverMiddleware
    from apps.websites.domaine_vitrine_middleware import (
        VitrineParDomaineMiddleware,
    )

    requete = RequestFactory().get('/client/connexion/', HTTP_HOST=DOMAINE)
    WebsiteResolverMiddleware(lambda r: None).process_request(requete)
    VitrineParDomaineMiddleware(lambda r: None).process_request(requete)

    assert requete.path_info == '/client/connexion/', (
        'le chemin a été réécrit en %s' % requete.path_info)


@override_settings(ALLOWED_HOSTS=HOTES)
def test_la_reecriture_fonctionne_toujours_pour_les_pages_du_site(vitrine):
    """L'exemption ne doit pas désarmer la réécriture.

    Ajouter un préfixe réservé de trop ferait servir la racine de l'ERP —
    l'écran de connexion des salariés — à la place du site.
    """
    from django.test import RequestFactory

    from apps.websites.middleware import WebsiteResolverMiddleware
    from apps.websites.domaine_vitrine_middleware import (
        VitrineParDomaineMiddleware,
    )

    requete = RequestFactory().get('/', HTTP_HOST=DOMAINE)
    WebsiteResolverMiddleware(lambda r: None).process_request(requete)
    VitrineParDomaineMiddleware(lambda r: None).process_request(requete)

    assert requete.path_info.startswith('/sites/'), requete.path_info
    assert 'electricite' in requete.path_info, requete.path_info


def test_le_prefixe_du_portail_est_bien_declare_reserve():
    """Une garde nommée, pour que la cause reste lisible.

    Si quelqu'un retire `/client/` de cette liste, les deux tests
    ci-dessus tomberaient — mais sans dire quoi chercher.
    """
    from apps.websites.domaine_vitrine_middleware import CHEMINS_RESERVES

    assert '/client/' in CHEMINS_RESERVES


# ═══════════════════════════════════════════════════════════════════════════
#  2. Le bouton est dans l'en-tête, donc sur toutes les pages
# ═══════════════════════════════════════════════════════════════════════════

def _page(client, vitrine, nom):
    return client.get(
        reverse('public_websites:%s' % nom,
                kwargs={'site_slug': vitrine.slug})).content.decode()


@override_settings(ALLOWED_HOSTS=HOTES)
@pytest.mark.parametrize('page', [
    'electricite_home', 'electricite_services', 'electricite_contact',
    'electricite_portfolio', 'electricite_about',
])
def test_le_bouton_parait_sur_toutes_les_pages(vitrine, client, page):
    """Il est dans l'en-tête, donc partout — c'était le manque.

    Le site portait déjà un lien dans le pied de page et un sur la page
    « espace client ». Un client qui revient voir son chantier arrivait sur
    l'accueil et devait deviner où chercher.
    """
    corps = _page(client, vitrine, page)
    assert 'sp-connexion' in corps, 'le bouton manque sur %s' % page
    assert reverse('client_portal:login') in corps


@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_bouton_porte_un_nom_pour_les_lecteurs_d_ecran(vitrine, client):
    """Son libellé est masqué au téléphone : sans `aria-label`, un lecteur
    d'écran annoncerait un lien sans nom."""
    corps = _page(client, vitrine, 'electricite_home')
    trouve = re.search(r'class="sp-connexion"[^>]*aria-label="([^"]+)"',
                       corps)
    assert trouve, 'le bouton n’a pas d’aria-label'
    assert trouve.group(1).strip()


@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_bouton_suit_la_langue_du_site(vitrine, client):
    """Un bouton français sur une vitrine portugaise se remarque.

    Les quatre autres chaînes de ce bouton étaient déjà au catalogue ;
    celle-ci a été ajoutée.
    """
    from apps.translations.models import Language, WebsiteLanguageSettings

    reglages, _c = WebsiteLanguageSettings.objects.get_or_create(
        website=vitrine)
    reglages.enabled_languages.set(
        Language.objects.filter(code__in=('fr', 'pt'), is_active=True))
    reglages.default_language = Language.objects.filter(code='fr').first()
    reglages.save()

    url = reverse('public_websites:electricite_home',
                  kwargs={'site_slug': vitrine.slug}) + '?lang=pt'
    corps = client.get(url).content.decode()

    assert 'Área de cliente' in corps, 'le bouton reste en français'


# ═══════════════════════════════════════════════════════════════════════════
#  3. Il survit au téléphone
# ═══════════════════════════════════════════════════════════════════════════

def _feuille():
    with open(FEUILLE, encoding='utf-8') as flux:
        return flux.read()


def test_le_bouton_n_est_pas_un_sp_btn():
    """LA RAISON EXACTE : la feuille masque les `sp-btn` de l'en-tête.

    `.sp-entete__actions .sp-btn { display: none }` sous 940 px. Un bouton
    de connexion ainsi stylé aurait disparu au téléphone, c'est-à-dire sur
    l'appareil depuis lequel un client regarde son chantier.
    """
    with open(ENTETE, encoding='utf-8') as flux:
        entete = flux.read()

    bloc = re.search(r'<a[^>]*class="sp-connexion"[^>]*>', entete)
    assert bloc, 'le bouton n’est pas dans l’en-tête'
    assert 'sp-btn' not in bloc.group(0), (
        'le bouton porte la classe sp-btn : il disparaîtra au téléphone')


def test_la_regle_qui_masque_les_boutons_existe_toujours():
    """Garde la garde : si cette règle disparaissait, le test ci-dessus
    n'aurait plus de raison d'être et son commentaire mentirait."""
    assert '.sp-entete__actions .sp-btn { display: none; }' in _feuille()


def test_le_libelle_part_au_telephone_mais_pas_le_bouton():
    """Réduit à son icône plutôt que masqué : la place manque, pas l'usage."""
    feuille = _feuille()
    assert '.sp-connexion__texte { display: none; }' in feuille
    assert '.sp-connexion { display: none' not in feuille, (
        'le bouton entier est masqué quelque part')


def test_la_couleur_du_bouton_pese_assez_lourd():
    """LE PIÈGE DE SPÉCIFICITÉ DE CE SITE, et il a déjà frappé.

    `.orion-site a { color: inherit }` pèse 0,1,1 et bat `.sp-connexion`,
    0,1,0 : le lien aurait hérité de la couleur de l'en-tête — donc du
    blanc, sur fond blanc, partout ailleurs que sur la photo du hero.
    La feuille qualifie déjà `.sp-site a.sp-tel` et `.sp-site a.sp-btn--or`
    pour cette raison ; le nouveau bouton doit l'être aussi.
    """
    feuille = _feuille()
    assert '.sp-site a.sp-connexion' in feuille, (
        'la couleur du bouton sera écrasée par « .orion-site a »')
    assert 'a.sp-connexion { color: #FFFFFF; }' in feuille.replace(
        '.sp-site .sp-entete:not(.sp-entete--opaque) ', ''), (
        'la variante sur photo n’est pas qualifiée')
