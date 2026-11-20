# -*- coding: utf-8 -*-
"""La langue d'un site public est décidée par CE site.

LE MODULE DORMAIT. `apps/websites/services/language_resolver.py` porte la
résolution par site : il ne retient qu'une langue activée pour ce site-là,
et ne consulte le navigateur que si l'exploitant a coché « choisir la langue
du visiteur automatiquement ». Rien ne l'appelait — ni vue, ni middleware,
seulement des tests. Ce qui tournait était `OrionLanguageMiddleware`,
global : il consultait le navigateur pour tout le monde et validait contre
les langues de toute l'installation, sans savoir quel site était servi.

Deux conséquences. Le réglage par site était décoratif — y compris
l'interrupteur exposé dans l'écran des langues. Et une langue qu'un site ne
proposait pas pouvait quand même s'activer dessus.

LE PIÈGE QU'IL FALLAIT VOIR AVANT DE BRANCHER, et que ce fichier garde.

Le bouton de traduction passe par `set_site_language`, qui écrit la clé de
session « _language ». Le résolveur écrivait et lisait la sienne,
« site_<pk>_lang ». Tant qu'il dormait, la divergence ne coûtait rien.
Branché sans lire la première clé, il aurait rendu le bouton inopérant : on
aurait cliqué sur une langue, et la page serait revenue à la langue par
défaut du site — un défaut introduit par la correction elle-même, et
invisible à la lecture du code puisque chaque moitié est correcte.
"""
import pytest
from django.test import override_settings
from django.urls import reverse

pytestmark = pytest.mark.django_db

HOTES = ['testserver', 's-peace.com']


# ── Le décor ────────────────────────────────────────────────────────────────

def _site(langues=('fr', 'en', 'de'), defaut='fr', auto=None, slug='sp-site'):
    """Un site public avec ses langues, prêt à être visité."""
    from apps.core.models import Company
    from apps.translations.models import Language, WebsiteLanguageSettings
    from apps.websites.models import Website, WebsitePage

    entreprise = Company.objects.create(name='Sparkling Peace', slug=slug)
    site = Website.objects.create(
        company=entreprise, name='Sparkling Peace', slug=slug,
        site_type='showcase', status='published', is_active=True,
        is_published=True)
    WebsitePage.objects.create(
        website=site, title='Accueil', slug='accueil', is_homepage=True,
        status='published', page_type='home')

    reglages, _cree = WebsiteLanguageSettings.objects.get_or_create(
        website=site)
    reglages.enabled_languages.set(
        Language.objects.filter(code__in=langues, is_active=True))
    reglages.default_language = Language.objects.filter(code=defaut).first()
    if auto is not None:
        reglages.auto_redirect_by_browser = auto
    reglages.save()
    return site


def _langue_active(client, site):
    """La langue que le middleware retient pour une visite de ce site."""
    from apps.translations.middleware import OrionLanguageMiddleware

    reponse = client.get('/sites/%s/' % site.slug)
    # `Content-Language` est posé par le middleware depuis la langue qu'il a
    # retenue : on mesure donc sa décision, et non une supposition.
    assert OrionLanguageMiddleware is not None
    return reponse.get('Content-Language', '')


# ── 1. Le module est branché ────────────────────────────────────────────────

def test_le_resolveur_est_appele_par_le_middleware():
    """Il n'était importé que par des tests.

    Ce test lit la source plutôt que de simuler : c'est le branchement
    lui-même qui manquait, et un simulacre prouverait seulement qu'on sait
    appeler la fonction.
    """
    import inspect

    from apps.translations import middleware

    source = inspect.getsource(middleware)
    assert 'get_website_language_from_request' in source, (
        'le middleware ne delegue pas au resolveur par site : le reglage '
        'par site reste decoratif.')


def test_une_requete_d_erp_n_interroge_aucun_site():
    """Le motif ne doit reconnaître que les adresses publiques.

    Ce middleware tourne sur CHAQUE requête, y compris celles de l'ERP. Une
    résolution de site sur chacune ajouterait une interrogation de base à
    tout l'ERP pour rien.
    """
    from apps.translations.middleware import MOTIF_SITE_PUBLIC

    for chemin in ['/', '/websites/messages/', '/accounts/profile/',
                   '/admin/', '/orion-admin/application-pc/']:
        assert MOTIF_SITE_PUBLIC.match(chemin) is None, chemin

    trouve = MOTIF_SITE_PUBLIC.match('/sites/electricite-etancheite/')
    assert trouve is not None
    assert trouve.group('slug') == 'electricite-etancheite'
    # Le domaine personnalisé arrive sous la même forme, le middleware de
    # domaine ayant déjà réécrit le chemin.
    assert MOTIF_SITE_PUBLIC.match(
        '/sites/electricite-etancheite/etancheite/') is not None


# ── 2. LE PIÈGE : le bouton de traduction doit continuer de marcher ─────────

@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_bouton_de_traduction_fonctionne_toujours():
    """LE TEST QUI COMPTE DANS CE FICHIER.

    Le sélecteur écrit « _language ». Le résolveur lisait « site_<pk>_lang ».
    Branché sans lire la clé du sélecteur, cliquer sur une langue n'aurait
    plus rien changé.
    """
    from django.test import Client

    site = _site(langues=('fr', 'en', 'de'), defaut='fr', auto=False)
    client = Client()

    client.get(reverse('public_websites:set_site_language'),
               {'lang': 'de', 'next': '/sites/%s/' % site.slug})
    assert client.session.get('_language') == 'de'

    assert _langue_active(client, site) == 'de'


@override_settings(ALLOWED_HOSTS=HOTES)
def test_une_langue_que_le_site_ne_propose_pas_ne_s_applique_pas():
    """Ce que la résolution globale laissait passer.

    Elle validait contre les langues actives de toute l'installation. Un
    site qui ne propose que le français et le portugais pouvait donc
    basculer en allemand, et son sélecteur n'offrait aucun moyen de revenir.
    """
    from django.test import Client

    site = _site(langues=('fr', 'pt'), defaut='fr', auto=False,
                 slug='sp-sans-de')
    client = Client()

    session = client.session
    session['_language'] = 'de'
    session.save()

    assert _langue_active(client, site) == 'fr'


# ── 3. La détection automatique, et son interrupteur ───────────────────────

@override_settings(ALLOWED_HOSTS=HOTES)
def test_la_langue_du_visiteur_est_prise_quand_c_est_coche():
    """« Traduction automatique selon le pays », par la langue du navigateur.

    C'est ce que l'en-tête `Accept-Language` porte : la langue réglée sur
    l'appareil du visiteur, qui suit son pays dans la grande majorité des
    cas. Rien dans une requête HTTP ne donne le pays de façon fiable sans
    service tiers.
    """
    from django.test import Client

    site = _site(langues=('fr', 'en', 'de'), defaut='fr', auto=True,
                 slug='sp-auto')
    client = Client(HTTP_ACCEPT_LANGUAGE='de-DE,de;q=0.9,en;q=0.8')

    assert _langue_active(client, site) == 'de'


@override_settings(ALLOWED_HOSTS=HOTES)
def test_decoche_le_site_reste_dans_sa_langue():
    """L'interrupteur fait enfin quelque chose.

    Il était exposé dans l'écran des langues et lu par rien : la détection
    s'appliquait de toute façon.
    """
    from django.test import Client

    site = _site(langues=('fr', 'en', 'de'), defaut='fr', auto=False,
                 slug='sp-sans-auto')
    client = Client(HTTP_ACCEPT_LANGUAGE='de-DE,de;q=0.9')

    assert _langue_active(client, site) == 'fr'


@override_settings(ALLOWED_HOSTS=HOTES)
def test_une_langue_du_navigateur_non_proposee_est_ignoree():
    """La détection ne doit pas sortir des langues du site."""
    from django.test import Client

    site = _site(langues=('fr', 'pt'), defaut='pt', auto=True,
                 slug='sp-auto-sans-de')
    client = Client(HTTP_ACCEPT_LANGUAGE='de-DE,de;q=0.9')

    assert _langue_active(client, site) == 'pt'


@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_choix_explicite_bat_la_detection():
    """Un visiteur qui a cliqué ne doit pas être corrigé par son navigateur."""
    from django.test import Client

    site = _site(langues=('fr', 'en', 'de'), defaut='fr', auto=True,
                 slug='sp-choix')
    client = Client(HTTP_ACCEPT_LANGUAGE='de-DE,de;q=0.9')

    client.get(reverse('public_websites:set_site_language'),
               {'lang': 'en', 'next': '/sites/%s/' % site.slug})

    assert _langue_active(client, site) == 'en'


# ── 4. Le réglage par défaut conserve le comportement en place ──────────────

def test_la_detection_est_active_par_defaut():
    """Elle l'était déjà, pour tous les sites, sans que rien ne le dise.

    `OrionLanguageMiddleware` consultait `Accept-Language` sans condition.
    Brancher le réglage en le laissant à faux aurait donc RETIRÉ la
    détection à tous les sites qui en bénéficiaient. Une correction qui
    enlève une fonctionnalité en passant n'est pas une correction.
    """
    from apps.translations.models import WebsiteLanguageSettings

    champ = WebsiteLanguageSettings._meta.get_field(
        'auto_redirect_by_browser')
    assert champ.default is True


def test_les_reglages_existants_ont_ete_repris():
    """La migration de données, éprouvée sur son effet.

    Un site dont les réglages existaient déjà avec le réglage à faux doit
    l'avoir à vrai après la mise à jour, sans quoi il perd sa détection.
    """
    import importlib

    from django.apps import apps as registre

    from apps.translations.models import WebsiteLanguageSettings

    site = _site(auto=False, slug='sp-repris')
    reglages = WebsiteLanguageSettings.objects.get(website=site)
    assert reglages.auto_redirect_by_browser is False

    module = importlib.import_module(
        'apps.translations.migrations.'
        '0004_detection_auto_sur_les_sites_existants')
    module.activer(registre, None)

    reglages.refresh_from_db()
    assert reglages.auto_redirect_by_browser is True
