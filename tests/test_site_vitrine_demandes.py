# -*- coding: utf-8 -*-
"""Quatre demandes sur le site vitrine, et les défauts qu'elles ont révélés.

**« Pas d'accès au message envoyé depuis le site. »** Le menu y menait, la
liste s'affichait — et elle montrait le nom, le courriel, le sujet, le site,
le statut et la date. Jamais `message`. Aucune vue de détail n'existait, et
le corps du message ne sortait de la base que tronqué à 200 caractères dans
une notification. On apprenait qu'on avait reçu un message, de qui, à quelle
heure, et pas ce qu'il disait. `read_at` était déclaré et jamais renseigné.

**« Le bleu foncé avec texte illisible. »** `WebsiteSection` porte deux
champs, `bg_color` et `text_color`. `page.html` applique les deux depuis
toujours ; `home.html` n'appliquait que le fond, dans ses dix sections, et
jetait la couleur de texte. Choisir un fond bleu nuit et un texte clair dans
l'éditeur donnait du `#111827` — presque noir — sur du `#0F172A`. S'y
ajoutait `.nav-link { color: var(--site-text) !important }`, qui rendait les
liens presque noirs sur un en-tête sombre, le `!important` interdisant de
corriger ailleurs.

**« Un bouton traduction, en cinq langues. »** Le sélecteur existait. Mais
l'allemand était empêché par trois raisons superposées, chacune suffisante :
`locale/de/` n'existait pas, la langue était semée avec `is_active: False`
— et `set_site_language` refuse un code inactif, en silence —, et elle était
absente des cinq langues proposées par défaut, qui offraient de l'italien à
sa place. Les langues n'étaient d'ailleurs créées que par une commande en
terminal, ce que les règles de ce projet interdisent pour un réglage
d'exploitation.

**« Préciser que l'entreprise intervient dans la région de Leiria. »** Aucun
champ ne portait cette information, et rien sur le site ne disait où
l'entreprise travaille. L'adresse ne le dit pas : une entreprise installée à
Leiria peut intervenir sur une commune ou sur toute la région.
"""
import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ── Le décor ────────────────────────────────────────────────────────────────

def _entreprise(nom='Sparkling Peace', slug='sparkling-peace'):
    from apps.core.models import Company
    return Company.objects.create(name=nom, slug=slug)


def _salarie(client, django_user_model, entreprise, identifiant='salarie'):
    from apps.accounts.models import UserProfile

    utilisateur = django_user_model.objects.create_user(identifiant,
                                                        password='x')
    profil, _ = UserProfile.objects.get_or_create(user=utilisateur)
    profil.companies.add(entreprise)
    profil.current_company = entreprise
    profil.save()

    client.force_login(django_user_model.objects.get(pk=utilisateur.pk))
    session = client.session
    session['current_company_id'] = entreprise.pk
    session.save()
    return utilisateur


def _site(entreprise, nom='Sparkling Peace', domaine='s-peace.com'):
    from apps.websites.models import Website
    return Website.objects.create(
        company=entreprise, name=nom, domain=domaine,
        site_type='showcase', status='published', is_active=True)


def _message(site, **champs):
    from apps.websites.models import ContactMessage

    defauts = dict(name='Ana Ferreira', email='ana@exemple.pt',
                   subject='Demande de renseignements',
                   message='Bonjour,\n\nPouvez-vous intervenir à Pombal ?\n\nMerci.')
    defauts.update(champs)
    return ContactMessage.objects.create(website=site, **defauts)


# ═══ 1. LE MESSAGE ENVOYÉ DEPUIS LE SITE ════════════════════════════════════

def test_le_corps_du_message_s_affiche(client, django_user_model):
    """LA DEMANDE, et le défaut exactement.

    La liste montre tout d'un message sauf ce qu'il dit. Ce test exige le
    texte lui-même, et non la présence d'un écran : un écran de détail qui
    afficherait le nom et le sujet sans le corps n'aurait rien réparé.
    """
    entreprise = _entreprise()
    _salarie(client, django_user_model, entreprise)
    message = _message(_site(entreprise))

    reponse = client.get(reverse('websites:message_detail',
                                 args=[message.pk]))
    corps = reponse.content.decode('utf-8')

    assert reponse.status_code == 200
    assert 'Pouvez-vous intervenir à Pombal ?' in corps


def test_la_liste_mene_au_message(client, django_user_model):
    """Une vue de détail que rien ne lie n'existe pas pour l'utilisateur."""
    entreprise = _entreprise()
    _salarie(client, django_user_model, entreprise)
    message = _message(_site(entreprise))

    corps = client.get(reverse('websites:message_list')).content.decode('utf-8')

    assert reverse('websites:message_detail', args=[message.pk]) in corps


def test_le_message_d_une_autre_entreprise_est_refuse(client,
                                                      django_user_model):
    """Le bornage de la liste, reproduit : `website__company`.

    Sans lui, changer le numéro dans l'adresse donnerait le courrier
    adressé au site d'une AUTRE entreprise — un message de contact porte un
    nom, un courriel et un numéro de téléphone.
    """
    autre = _entreprise('Concurrent', 'concurrent')
    message = _message(_site(autre, 'Autre site', 'autre.com'))

    mienne = _entreprise('Sparkling Peace', 'sp-2')
    _salarie(client, django_user_model, mienne)

    reponse = client.get(reverse('websites:message_detail',
                                 args=[message.pk]))
    assert reponse.status_code == 404


def test_ouvrir_un_message_le_marque_lu(client, django_user_model):
    """`read_at` était déclaré sur le modèle et renseigné nulle part.

    Le statut restait donc « nouveau » pour toujours, et le compteur de
    nouveaux messages de l'écran d'accueil ne redescendait jamais.
    """
    entreprise = _entreprise()
    _salarie(client, django_user_model, entreprise)
    message = _message(_site(entreprise))
    assert message.status == 'new'
    assert message.read_at is None

    client.get(reverse('websites:message_detail', args=[message.pk]))

    message.refresh_from_db()
    assert message.status == 'read'
    assert message.read_at is not None


def test_un_message_deja_repondu_ne_redevient_pas_lu(client,
                                                     django_user_model):
    """L'ouverture ne marque QUE depuis « nouveau ».

    Sans cette borne, consulter un message classé « répondu » le ferait
    régresser, et la liste filtrée par statut perdrait son sens.
    """
    entreprise = _entreprise()
    _salarie(client, django_user_model, entreprise)
    message = _message(_site(entreprise), status='replied')

    client.get(reverse('websites:message_detail', args=[message.pk]))

    message.refresh_from_db()
    assert message.status == 'replied'


def test_le_statut_se_change_par_POST(client, django_user_model):
    entreprise = _entreprise()
    _salarie(client, django_user_model, entreprise)
    message = _message(_site(entreprise))

    client.post(reverse('websites:message_detail', args=[message.pk]),
                {'status': 'replied'})

    message.refresh_from_db()
    assert message.status == 'replied'


def test_un_statut_hors_liste_est_refuse(client, django_user_model):
    """La famille de défauts la plus tenace de ce projet.

    Les `choices` de Django ne sont vérifiés qu'au `full_clean`, que
    `save()` n'appelle pas. Un statut arbitraire s'écrirait donc tel quel en
    base, et la liste n'afficherait plus aucun libellé pour cette ligne —
    la cascade de `{% if %}` du gabarit ne reconnaîtrait rien et
    retomberait sur « Archivé », ce qui serait un mensonge.
    """
    entreprise = _entreprise()
    _salarie(client, django_user_model, entreprise)
    message = _message(_site(entreprise))

    client.post(reverse('websites:message_detail', args=[message.pk]),
                {'status': 'nimporte_quoi'})

    message.refresh_from_db()
    assert message.status in dict(message.STATUS_CHOICES)


# ═══ 2. LE BLEU FONCÉ AVEC TEXTE ILLISIBLE ══════════════════════════════════

def test_la_luminance_suit_la_formule_wcag():
    """Une moyenne des composantes jugerait le bleu aussi clair que le vert.

    `#0000FF` et `#008000` ont la même moyenne de composantes. À l'œil, le
    vert est bien plus lumineux — la formule WCAG le dit, en pondérant le
    vert à près des trois quarts.
    """
    from apps.websites.templatetags.website_extras import luminance_relative

    assert luminance_relative('#008000') > luminance_relative('#0000FF')
    assert luminance_relative('#FFFFFF') == pytest.approx(1.0)
    assert luminance_relative('#000000') == pytest.approx(0.0)


@pytest.mark.parametrize('fond,attendu', [
    ('#0F172A', '#FFFFFF'),   # le bleu nuit des thèmes
    ('#111827', '#FFFFFF'),   # la couleur de texte par défaut, en fond
    ('#2563EB', '#FFFFFF'),   # le bleu primaire par défaut
    ('#FFFFFF', '#111827'),
    ('#F3F4F6', '#111827'),
    ('#abc', '#111827'),      # forme à trois chiffres
])
def test_la_couleur_de_texte_se_deduit_du_fond(fond, attendu):
    from apps.websites.templatetags.website_extras import couleur_lisible

    assert couleur_lisible(fond) == attendu


@pytest.mark.parametrize('valeur', [
    'var(--site-primary)',
    'linear-gradient(135deg, #fff, #000)',
    'rgba(0,0,0,.5)',
    'transparent',
    '',
    None,
    '#xyz',
])
def test_un_fond_indechiffrable_n_impose_aucune_couleur(valeur):
    """« Je ne sais pas » doit se dire, et non se deviner.

    Imposer du blanc par précaution serait pire que de ne rien imposer : sur
    un dégradé clair, on rendrait illisible ce qui l'était. Le champ est un
    texte libre de cinquante caractères et contient ce que l'exploitant a
    tapé.
    """
    from apps.websites.templatetags.website_extras import (
        couleur_lisible, est_fond_sombre)

    assert couleur_lisible(valeur) == ''
    assert est_fond_sombre(valeur) is False


def test_la_couleur_choisie_par_l_exploitant_l_emporte():
    """La déduction ne doit jamais écraser un choix explicite."""
    from apps.websites.templatetags.website_extras import style_de_section

    class Section:
        bg_color = '#0F172A'
        text_color = '#E2E8F0'

    assert style_de_section(Section()) == 'background:#0F172A;color:#E2E8F0'


def test_une_section_bleu_nuit_recoit_du_texte_clair():
    """LE DÉFAUT MESURÉ SUR LE HTML RENDU, et non sur le gabarit.

    Avant : `<section class="py-5" style="background:#0F172A">`, le texte
    retombant sur `--site-text`. C'est exactement « le bleu foncé avec texte
    illisible ».
    """
    from django.template.loader import get_template

    class Faux:
        def __init__(self, **champs):
            for cle, valeur in champs.items():
                setattr(self, cle, valeur)

        def __getattr__(self, nom):
            return ''

    section = Faux(section_type='text', title='Nos engagements',
                   content='<p>Texte.</p>', bg_color='#0F172A',
                   text_color='', is_visible=True)
    site = Faux(name='Sparkling Peace', public_slug='sp', slug='sp')

    html = get_template('websites/public/home.html').render({
        'site': site, 'theme': None, 'sections': [section],
        'menu_items': [], 'footer_links': [], 'company': Faux(name='SP'),
        'website_languages': [],
    })

    assert 'background:#0F172A;color:#FFFFFF' in html
    # Et la classe qui entraîne titre, sous-titre et texte atténué : le
    # titre est peint en `--site-secondary`, c'est-à-dire le bleu nuit
    # lui-même. Sans elle, il disparaissait dans son propre fond.
    assert 'ws-fond-sombre' in html


def test_les_liens_de_navigation_suivent_le_fond_de_l_en_tete():
    """`.nav-link` était peint en `--site-text`, quel que soit l'en-tête.

    Un en-tête sombre donnait donc des liens presque noirs, et le
    `!important` empêchait de corriger par ailleurs.
    """
    from django.template.loader import get_template

    class Faux:
        def __init__(self, **champs):
            for cle, valeur in champs.items():
                setattr(self, cle, valeur)

        def __getattr__(self, nom):
            return ''

    # `public_slug` doit être renseigné : les `{% url %}` du gabarit
    # l'emploient, et une chaîne vide ne correspond à aucune route.
    site = Faux(name='Sparkling Peace', public_slug='sp', slug='sp')

    html = get_template('websites/public/base.html').render({
        'site': site, 'theme': None, 'menu_items': [], 'footer_links': [],
        'company': Faux(name='SP'), 'website_languages': [],
    })

    assert 'color: var(--site-header-text) !important' in html
    assert 'color: var(--site-text) !important' not in html


def test_les_dix_sections_de_l_accueil_posent_une_couleur_de_texte():
    """La garde qui survivra à ce travail.

    Le défaut n'était pas dans une section mais dans dix, écrites sur le
    même patron. Quelqu'un qui ajoutera la onzième recopiera la ligne
    voisine — ce test échoue si cette ligne redevient un fond sans couleur.
    """
    import os
    import re

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    chemin = os.path.join(racine, 'templates', 'websites', 'public',
                          'home.html')
    with open(chemin, encoding='utf-8') as fichier:
        contenu = fichier.read()

    nus = re.findall(r'style="background:\s*\{\{\s*section\.bg_color\s*\}\}"',
                     contenu)
    assert not nus, (
        '%d section(s) posent un fond sans couleur de texte. Employez '
        '{%% style_de_section section %%}, qui honore `text_color` et, a '
        'defaut, deduit une couleur lisible du fond.' % len(nus))


# ═══ 3. LES CINQ LANGUES, ET LE BOUTON ══════════════════════════════════════

CINQ = ['fr', 'en', 'de', 'es', 'pt']


def test_les_cinq_langues_existent_et_sont_actives():
    """Les migrations suffisent : aucun terminal.

    Les lignes de `Language` n'étaient créées que par
    `manage.py seed_languages` — vérifié sur tout le dépôt. Sur une
    installation où la commande n'a jamais tourné, la table est vide, et le
    sélecteur de langue DISPARAÎT sans un mot, son gabarit étant gardé par
    un `{% if website_languages %}`.
    """
    from apps.translations.models import Language

    actives = set(Language.objects.filter(is_active=True)
                  .values_list('code', flat=True))
    manquantes = set(CINQ) - actives
    assert not manquantes, (
        'langues absentes ou inactives : %s' % sorted(manquantes))


def test_l_allemand_est_actif():
    """Il était semé avec `is_active: False`, et c'était fatal en silence.

    `set_site_language` ne retient un code que si la langue est active :
    on pouvait cliquer « Deutsch », la vue refusait, et la page revenait
    sans rien expliquer.
    """
    from apps.translations.models import Language

    allemand = Language.objects.filter(code='de').first()
    assert allemand is not None
    assert allemand.is_active is True


def test_les_langues_par_defaut_d_un_site_contiennent_l_allemand():
    """Elles contenaient de l'italien à sa place.

    `LANGUAGES` dans les réglages Django déclare bien l'allemand : seul ce
    défaut-ci privait un nouveau site de la langue.
    """
    from apps.websites.public_views import DEFAULT_SITE_LANGUAGES

    assert set(DEFAULT_SITE_LANGUAGES) == set(CINQ)


def test_le_catalogue_allemand_traduit_le_site():
    """`locale/de/` n'existait pas du tout.

    Les quatre autres langues portent chacune ~4 300 chaînes. Ce test ne
    vérifie pas un nombre mais un résultat : trois chaînes du site vitrine,
    en allemand.
    """
    from django.utils import translation

    with translation.override('de'):
        assert translation.gettext('Contactez-nous') == 'Kontaktieren Sie uns'
        assert translation.gettext('Changer de langue') == 'Sprache wechseln'
        assert translation.gettext("Zone d'intervention") == 'Einsatzgebiet'


@pytest.mark.parametrize('langue,attendu', [
    ('en', 'Service area'),
    ('es', 'Zona de intervención'),
    # « Zona de intervenção » et non « Área » : le libellé existait déjà
    # dans le catalogue portugais, employé ailleurs dans l'ERP. On garde la
    # traduction en place plutôt que d'en imposer une seconde au même sens.
    ('pt', 'Zona de intervenção'),
    ('de', 'Einsatzgebiet'),
])
def test_la_zone_d_intervention_est_traduite(langue, attendu):
    from django.utils import translation

    with translation.override(langue):
        assert translation.gettext("Zone d'intervention") == attendu


def test_le_selecteur_propose_les_cinq_langues(client, django_user_model):
    """Le bouton de traduction, mesuré sur le HTML du site public."""
    entreprise = _entreprise()
    site = _site(entreprise)
    from apps.websites.public_views import _get_website_languages

    langues = _get_website_languages(site)

    assert {langue['code'] for langue in langues} == set(CINQ)


def test_le_site_accepte_de_passer_en_allemand(client):
    """`set_site_language` refusait « de » parce que la langue était inactive."""
    reponse = client.get(reverse('public_websites:set_site_language'),
                         {'lang': 'de', 'next': '/'})

    assert reponse.status_code == 302
    assert client.session.get('_language') == 'de'


def test_une_langue_inconnue_ne_change_rien(client):
    client.get(reverse('public_websites:set_site_language'),
               {'lang': 'kl', 'next': '/'})
    assert client.session.get('_language') is None


def test_les_langues_du_site_se_reglent_depuis_l_ERP(client,
                                                     django_user_model):
    """« Pas de ligne de commande » : la règle de ce projet.

    Les langues d'un site vivaient dans l'admin Django, et la table des
    langues n'était peuplée que par une commande. Changer la langue d'un
    site demandait donc un terminal.
    """
    from apps.translations.models import Language, WebsiteLanguageSettings

    entreprise = _entreprise()
    site = _site(entreprise)
    _salarie(client, django_user_model, entreprise)

    adresse = reverse('websites:website_languages', args=[site.pk])
    assert client.get(adresse).status_code == 200

    retenues = list(Language.objects.filter(code__in=['fr', 'de'])
                    .values_list('pk', flat=True))
    francais = Language.objects.get(code='fr')
    client.post(adresse, {
        'enabled_languages': retenues,
        'default_language': francais.pk,
        'show_language_switcher': 'on',
    })

    reglages = WebsiteLanguageSettings.objects.get(website=site)
    assert set(reglages.enabled_languages.values_list('code', flat=True)) == {
        'fr', 'de'}


def test_une_langue_par_defaut_non_cochee_est_refusee(client,
                                                      django_user_model):
    """Elle serait servie sans que le sélecteur permette d'en sortir."""
    from apps.translations.models import Language, WebsiteLanguageSettings

    entreprise = _entreprise()
    site = _site(entreprise)
    _salarie(client, django_user_model, entreprise)

    francais = Language.objects.get(code='fr')
    allemand = Language.objects.get(code='de')

    reponse = client.post(
        reverse('websites:website_languages', args=[site.pk]),
        {'enabled_languages': [francais.pk],
         'default_language': allemand.pk,
         'show_language_switcher': 'on'})

    assert reponse.status_code == 200
    assert 'default_language' in reponse.context['form'].errors
    reglages = WebsiteLanguageSettings.objects.filter(website=site).first()
    if reglages is not None:
        assert allemand.pk not in set(
            reglages.enabled_languages.values_list('pk', flat=True))


# ═══ 4. LA ZONE D'INTERVENTION ══════════════════════════════════════════════

def test_le_champ_de_zone_d_intervention_existe():
    from apps.websites.models import Website

    champ = Website._meta.get_field('service_area')
    assert champ.blank is True


def test_la_zone_s_affiche_au_pied_de_chaque_page():
    """Au pied de CHAQUE page, et pas seulement sur la page de contact.

    Un visiteur arrive souvent par une page de service, pas par l'accueil.
    """
    from django.template.loader import get_template

    class Faux:
        def __init__(self, **champs):
            for cle, valeur in champs.items():
                setattr(self, cle, valeur)

        def __getattr__(self, nom):
            return ''

    site = Faux(name='Sparkling Peace', public_slug='sp', slug='sp',
                service_area='Région de Leiria, Portugal')

    html = get_template('websites/public/base.html').render({
        'site': site, 'theme': None, 'menu_items': [], 'footer_links': [],
        'company': Faux(name='SP'), 'website_languages': [],
    })

    assert 'Région de Leiria, Portugal' in html


def test_le_champ_est_dans_le_FORMULAIRE_ET_DANS_LE_GABARIT():
    """LE PIÈGE DE CE PROJET, rencontré une fois de plus.

    `templates/websites/website_form.html` nomme ses champs un par un.
    Ajouter un champ au formulaire ne le fait donc PAS apparaître à
    l'écran — et un champ qu'aucun écran n'affiche est un champ qui n'existe
    pas pour l'exploitant. C'est ainsi que « country » est resté invisible
    depuis le début, laissant un site portugais marqué « France ».
    """
    import os

    from apps.websites.forms import WebsiteAdminForm

    assert 'service_area' in WebsiteAdminForm().fields

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    chemin = os.path.join(racine, 'templates', 'websites',
                          'website_form.html')
    with open(chemin, encoding='utf-8') as fichier:
        gabarit = fichier.read()

    assert '{{ form.service_area }}' in gabarit, (
        'le champ est dans le formulaire mais le gabarit ne le rend pas : '
        'il nomme ses champs un par un.')
    assert '{{ form.country }}' in gabarit, (
        'country etait dans le formulaire et affiche nulle part.')


def _migration_de_la_zone():
    """Le module de la migration de données, importé par son vrai nom.

    `importlib` sait charger un module dont le nom commence par un chiffre,
    là où une instruction `import` ne le pourrait pas.
    """
    import importlib

    return importlib.import_module(
        'apps.websites.migrations.0029_zone_intervention_leiria')


def test_la_migration_renseigne_le_site_nomme():
    """La mise à jour doit livrer un RÉSULTAT, pas un champ vide.

    Sans la migration de données, la mention n'apparaîtrait qu'après que
    quelqu'un ait pensé à ouvrir l'écran et à la taper. Le site est désigné
    par son DOMAINE et non par une clé primaire, qui diffère d'une
    installation à l'autre.
    """
    from django.apps import apps as registre

    entreprise = _entreprise()
    site = _site(entreprise)
    assert site.service_area == ''
    assert site.country == 'France'

    _migration_de_la_zone().renseigner(registre, None)

    site.refresh_from_db()
    assert 'Leiria' in site.service_area
    assert site.country == 'Portugal'


def test_la_migration_n_ecrase_jamais_une_valeur_saisie():
    """Une migration de contenu qui écrase est une migration qu'on regrette.

    Elle est rejouée sur chaque base, y compris après que l'exploitant a
    corrigé la formulation.
    """
    from django.apps import apps as registre

    entreprise = _entreprise()
    site = _site(entreprise)
    site.service_area = 'Tout le district de Leiria et Coimbra'
    site.country = 'Portugal'
    site.save()

    _migration_de_la_zone().renseigner(registre, None)

    site.refresh_from_db()
    assert site.service_area == 'Tout le district de Leiria et Coimbra'


def test_la_migration_ignore_les_sites_d_un_autre_domaine():
    """Elle ne doit toucher que le site qu'on lui a nommé."""
    from django.apps import apps as registre

    entreprise = _entreprise('Autre', 'autre')
    site = _site(entreprise, 'Autre site', 'exemple.fr')

    _migration_de_la_zone().renseigner(registre, None)

    site.refresh_from_db()
    assert site.service_area == ''
    assert site.country == 'France'


def test_la_valeur_se_lit_seule():
    """Elle n'est pas enchâssée dans une phrase, et c'est un choix.

    Une phrase traduite autour d'une valeur qui, elle, ne l'est pas —
    `service_area` est un champ unique, non traduit — donnerait en allemand
    « Wir sind in der région de Leiria tätig ». Le gabarit affiche donc un
    libellé traduit suivi de la valeur telle quelle, ce qui fonctionne dans
    les cinq langues et avec n'importe quelle formulation.
    """
    import os

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for nom in ('base.html', 'contact.html'):
        chemin = os.path.join(racine, 'templates', 'websites', 'public', nom)
        with open(chemin, encoding='utf-8') as fichier:
            contenu = fichier.read()
        assert 'Nous intervenons dans la' not in contenu, (
            '%s enchasse la valeur dans une phrase' % nom)


# ═══ 5. CE QUI AURAIT EMPÊCHÉ LA LIVRAISON D'ARRIVER ════════════════════════


def test_un_guillemet_dans_la_couleur_ne_sort_pas_de_l_attribut():
    """`bg_color` est un champ texte libre, réinjecté dans un `style`.

    La balise ne marque donc RIEN comme sûr : c'est le gabarit qui échappe,
    comme le faisait `{{ section.bg_color }}` avant elle. Passer par une
    balise ne doit pas perdre cette propriété — c'est le genre de
    régression qu'on n'introduit jamais exprès.
    """
    from django.template import Context, Template

    class Section:
        bg_color = 'red" onmouseover="alert(1)'
        text_color = ''

    rendu = Template(
        '{% load website_extras %}'
        '<section style="{% style_de_section s %}">'
    ).render(Context({'s': Section()}))

    assert '&quot;' in rendu
    assert 'onmouseover="alert' not in rendu


def test_la_bibliotheque_de_balises_est_bien_dans_le_depot():
    """ELLE N'Y ÉTAIT PAS, et un gabarit SUIVI la chargeait déjà.

    `apps/websites/templatetags/` n'a jamais été versionné — il n'est pas
    ignoré, c'est un simple oubli d'ajout. Tout fonctionnait sur le poste de
    développement, où le fichier existe. Mais
    `templates/electricity/base_electricity.html`, lui, est suivi et fait
    `{% load website_extras %}` : sur l'appliance, qui tire `main`, ce
    gabarit levait `TemplateSyntaxError`.

    Ce test ne regarde pas le disque — le fichier y est toujours, c'est tout
    le piège — mais ce que git connaît.
    """
    import os
    import subprocess

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    resultat = subprocess.run(
        ['git', 'ls-files', 'apps/websites/templatetags/'],
        cwd=racine, capture_output=True, text=True)
    if resultat.returncode != 0:
        pytest.skip('git indisponible ici.')

    suivis = resultat.stdout.split()
    assert any(nom.endswith('website_extras.py') for nom in suivis), (
        'apps/websites/templatetags/website_extras.py n-est pas dans le '
        'depot. Les gabarits qui font {% load website_extras %} leveront '
        'TemplateSyntaxError sur le serveur, ou le fichier n-existe pas.')


def test_les_catalogues_compiles_ne_sont_pas_versionnes():
    """Le fait dont découle le test suivant, vérifié et non supposé.

    Si les `.mo` étaient dans le dépôt, la compilation serait inutile et le
    test suivant n'aurait aucun sens. C'est parce qu'ils sont ignorés qu'ils
    DOIVENT être compilés par la mise à jour.
    """
    import os

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(racine, '.gitignore'), encoding='utf-8') as fichier:
        ignore = fichier.read()

    assert 'locale/*/LC_MESSAGES/*.mo' in ignore


def test_les_deux_chemins_de_mise_a_jour_compilent_les_traductions():
    """LA LANGUE AJOUTÉE N'ARRIVAIT PAS SUR L'APPLIANCE.

    Les `.mo` sont ignorés par git : seuls les `.po` voyagent. Ils doivent
    donc être compilés à l'arrivée. `update_orion.sh` le faisait ; le
    metteur à jour de l'INTERFACE — celui qu'on lance depuis l'écran, et que
    les règles de ce projet désignent comme le chemin normal — ne le faisait
    pas. Il lançait `migrate` et `collectstatic`, rien de plus.

    Conséquence exacte : ce travail aurait livré `locale/de/django.po` sans
    aucun effet visible, et rien ne l'aurait dit — la page se serait
    affichée en français. Corriger un chemin sans l'autre laisse le défaut
    en place, et ce test tient les deux.
    """
    import os

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    chemins = [
        os.path.join(racine, 'apps', 'system_updates', 'update_runner.py'),
        os.path.join(racine, 'deployment', 'proxmox-appliance', 'scripts',
                     'update_orion.sh'),
    ]
    for chemin in chemins:
        if not os.path.exists(chemin):
            pytest.skip('%s absent de cette copie.' % chemin)
        with open(chemin, encoding='utf-8', errors='replace') as fichier:
            contenu = fichier.read()
        assert 'compilemessages' in contenu, (
            '%s ne compile pas les catalogues : une langue ajoutee dans un '
            '.po restera sans effet par ce chemin de mise a jour.'
            % os.path.basename(chemin))


def test_la_compilation_des_traductions_n_arrete_pas_la_mise_a_jour():
    """Une traduction manquante ne doit pas couper une mise à jour.

    `run_shell_step` lève sur échec, ce qui interrompt tout. C'est juste
    pour `migrate` : une base à moitié migrée est pire que rien. Ce n'est
    pas juste pour `compilemessages` : si `msgfmt` manque, l'ERP fonctionne
    en français, et s'arrêter là laisserait l'installation entre deux
    états pour un défaut d'affichage.

    L'étape passe donc par `log_step` avec le niveau « warning », et le
    journal de la mise à jour porte l'avertissement.
    """
    import inspect

    from apps.system_updates import update_runner

    source = inspect.getsource(update_runner.run_system_update)
    debut = source.index('compilemessages')
    bloc = source[debut - 400:debut + 1200]

    assert "level='success' if resultat_i18n['ok'] else 'warning'" in bloc, (
        "l'etape de compilation doit journaliser un avertissement, pas "
        'lever')
    assert 'run_shell_step(update_run, \'compilemessages\'' not in source, (
        'run_shell_step leve sur echec : il interromprait la mise a jour '
        'pour une traduction non compilee.')
