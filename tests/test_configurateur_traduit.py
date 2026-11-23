# -*- coding: utf-8 -*-
"""Le configurateur de devis ELECTRICITE, traduit jusqu'aux options.

**LE DÉFAUT CORRIGÉ.** Les sept gabarits du configurateur chargent `i18n` et
portent une centaine de `{% trans %}` : titres, boutons et intitulés étaient
bien traduits. Mais les CHOIX — tout ce que le visiteur lit et clique
réellement : pièces, équipements, types de bâtiment, types de projet, gammes,
pannes — arrivaient du contexte de la vue en chaînes de caractères
ordinaires, rendues par `{{ label }}`. Le configurateur s'affichait donc avec
des titres portugais et des options françaises.

C'est le piège propre à `{% trans %}` : il ne traduit qu'un littéral écrit
DANS le gabarit. Une valeur qui vient du contexte le traverse intacte, et
rien ne le signale — la page s'affiche, simplement pas dans la bonne langue.
Mesurer la présence de `{% trans %}` dans les gabarits, comme on serait
tenté de le faire, aurait donc validé le défaut.

**D'OÙ LA FORME DE CES TESTS.** Ils demandent les vraies pages par le client
HTTP, en portugais, et cherchent les mots portugais dans le HTML rendu.
C'est la seule mesure qui prouve quelque chose ici.

**ET LE SECOND PIÈGE, celui qui compte le plus.** Les libellés d'équipement
ne servent pas qu'à l'écran : ils sont ÉCRITS EN BASE comme lignes du devis,
que l'exploitant lit dans l'ERP et qui partent dans le PDF. Traduits
naïvement, un visiteur portugais aurait créé un devis en portugais dans un
ERP tenu en français. Le texte stocké est donc forcé à la langue de
l'installation, et un test le garde.
"""
import pytest
from django.test import override_settings
from django.urls import reverse

pytestmark = pytest.mark.django_db

HOTES = ['testserver', 's-peace.com']

LANGUES = ('en', 'de', 'es', 'pt', 'it')


# ═══════════════════════════════════════════════════════════════════════════
#  Décor
# ═══════════════════════════════════════════════════════════════════════════

def _site_electricite(slug='sp-elec', langues=('fr', 'pt', 'de')):
    """Une vitrine électricité, avec ses langues activées.

    Le type « electricite » n'est pas décoratif : `_get_electricite_site`
    le préfère explicitement, parce que servir ce dessin à une boutique
    afficherait une page d'électricien sur un site de vente.
    """
    from apps.core.models import Company
    from apps.translations.models import Language, WebsiteLanguageSettings
    from apps.websites.models import Website

    entreprise = Company.objects.create(name='Sparkling Peace', slug=slug)
    site = Website.objects.create(
        company=entreprise, name='Sparkling Peace Électricité', slug=slug,
        site_type='electricite', status='published', is_active=True,
        is_published=True)

    reglages, _cree = WebsiteLanguageSettings.objects.get_or_create(
        website=site)
    reglages.enabled_languages.set(
        Language.objects.filter(code__in=langues, is_active=True))
    reglages.default_language = Language.objects.filter(code='fr').first()
    reglages.save()
    return site


def _page(client, site, nom, langue=None, **kwargs):
    """Une page du configurateur, dans la langue demandée.

    Le « ?lang= » est la voie que le résolveur par site lit en premier, et
    c'est aussi celle du bouton de traduction : on emprunte donc le chemin
    réel du visiteur plutôt qu'un réglage interne.
    """
    url = reverse('public_websites:%s' % nom,
                  kwargs=dict(site_slug=site.slug, **kwargs))
    if langue:
        url += '?lang=%s' % langue
    return client.get(url)


# ═══════════════════════════════════════════════════════════════════════════
#  1. Les options sont traduites dans la page rendue
# ═══════════════════════════════════════════════════════════════════════════

@override_settings(ALLOWED_HOSTS=HOTES)
def test_etape_1_les_types_de_batiment_sont_traduits(client):
    """« Maison » et « Appartement » étaient les plus visibles du défaut.

    Ils ouvrent la première page du configurateur : un visiteur portugais
    lisait un titre portugais au-dessus de sept options françaises.
    """
    site = _site_electricite()
    corps = _page(client, site, 'electricite_wizard_start',
                  langue='pt').content.decode()

    assert 'Apartamento' in corps, 'les types de bâtiment restent en français'
    assert 'Escritório' in corps
    assert 'Appartement' not in corps


@override_settings(ALLOWED_HOSTS=HOTES)
def test_etape_1_les_types_de_projet_sont_traduits(client):
    site = _site_electricite()
    corps = _page(client, site, 'electricite_wizard_start',
                  langue='pt').content.decode()

    assert 'Construção nova' in corps
    assert 'Renovação' in corps


@override_settings(ALLOWED_HOSTS=HOTES)
def test_en_francais_rien_ne_change(client):
    """La traduction ne doit pas abîmer la langue d'origine.

    Un libellé enveloppé mais absent du catalogue rend le français : c'est
    le comportement voulu, et il faut vérifier qu'il tient — sans quoi on
    aurait pu casser la version française sans s'en apercevoir, puisque
    c'est celle que personne ne pense à regarder après coup.
    """
    site = _site_electricite()
    corps = _page(client, site, 'electricite_wizard_start',
                  langue='fr').content.decode()

    assert 'Maison' in corps
    assert 'Appartement' in corps
    assert 'Rénovation' in corps


@override_settings(ALLOWED_HOSTS=HOTES)
def test_etape_2_depannage_les_pannes_sont_traduites(client):
    """Ces six libellés étaient écrits AU MILIEU DE LA VUE.

    Ils étaient les seuls du configurateur à ne figurer nulle part
    ailleurs, et c'est précisément pour cela qu'on ne les voyait pas. Ils
    sont désormais au niveau du module, sous le regard.
    """
    site = _site_electricite()
    session = client.session
    session['elec_request_type'] = 'depannage'
    session.save()

    corps = _page(client, site, 'electricite_wizard_step2',
                  langue='pt').content.decode()

    assert 'Sem energia em toda a casa' in corps
    assert 'O disjuntor dispara' in corps
    assert 'Plus de courant' not in corps


@override_settings(ALLOWED_HOSTS=HOTES)
def test_etape_2_chantier_pieces_equipements_et_gammes(client):
    """La page la plus chargée : 8 pièces, 16 équipements, 3 gammes.

    C'est elle qui porte l'essentiel du texte lu par le visiteur, et elle
    était intégralement en français sous un titre traduit.
    """
    site = _site_electricite()
    session = client.session
    session['elec_request_type'] = 'renovation'
    session.save()

    corps = _page(client, site, 'electricite_wizard_step2',
                  langue='pt').content.decode()

    assert 'Cozinha' in corps, 'les pièces restent en français'
    assert 'Casa de banho' in corps
    assert 'Tomadas' in corps, 'les équipements restent en français'
    assert 'Painéis fotovoltaicos' in corps
    assert 'Padrão' in corps, 'les gammes restent en français'
    assert 'Cuisine' not in corps


@override_settings(ALLOWED_HOSTS=HOTES)
def test_la_traduction_vaut_aussi_en_allemand(client):
    """L'allemand est le catalogue le plus incomplet du projet.

    Il comptait 301 entrées contre 4566 pour les autres : une correction
    vérifiée seulement en portugais aurait très bien pu le laisser de côté.
    """
    site = _site_electricite()
    corps = _page(client, site, 'electricite_wizard_start',
                  langue='de').content.decode()

    assert 'Wohnung' in corps
    assert 'Neubau' in corps


# ═══════════════════════════════════════════════════════════════════════════
#  2. Ce qui est enregistré reste en français
# ═══════════════════════════════════════════════════════════════════════════

def test_le_libelle_stocke_ne_suit_pas_la_langue_du_visiteur():
    """LE PIÈGE DE LA CORRECTION, et il valait mieux que la panne.

    `add(category, label)` écrit ces libellés dans des
    `GuidedQuoteEstimateItem` : ils deviennent les lignes du devis que
    l'exploitant lit dans l'ERP et qui partent dans le PDF. Depuis que les
    libellés sont traduits paresseusement, une simple conversion en chaîne
    les résoudrait dans la langue du VISITEUR — un devis en portugais ou en
    allemand dans un ERP tenu en français, selon qui a rempli le formulaire
    ce jour-là.

    On mesure la source parce que c'est là que la décision se prend : le
    chemin complet passe par une estimation tarifaire qui demande une
    bibliothèque de prix, et on veut ici une mesure qui ne dépende que de
    ce point.
    """
    import inspect

    from apps.websites import electricite_wizard_views as vues

    source = inspect.getsource(vues)
    assert 'with override(reglages.LANGUAGE_CODE):' in source, (
        'le libellé stocké n’est plus forcé à la langue de l’installation')


def test_forcer_la_langue_rend_bien_le_francais():
    """Et la mécanique employée doit faire ce qu'on croit.

    `override` est vérifié ici pour lui-même : s'il ne ramenait pas au
    français, le test ci-dessus garderait une ligne de code sans effet.
    """
    from django.conf import settings
    from django.utils.translation import activate, override

    from apps.websites.electricite_wizard_views import LIBELLE_EQUIPEMENT

    activate('pt')
    assert str(LIBELLE_EQUIPEMENT['prises']) == 'Tomadas'

    with override(settings.LANGUAGE_CODE):
        assert str(LIBELLE_EQUIPEMENT['prises']) == 'Prises'


# ═══════════════════════════════════════════════════════════════════════════
#  3. Gardes : ce qui ferait revenir le défaut
# ═══════════════════════════════════════════════════════════════════════════

def _toutes_les_listes():
    from apps.websites import electricite_wizard_views as vues

    return (
        ('ROOM_CHOICES', [(k, l) for k, l in vues.ROOM_CHOICES]),
        ('EQUIPMENT_CHOICES', [(k, l) for k, l, _c in vues.EQUIPMENT_CHOICES]),
        ('BUILDING_TYPE_CHOICES', list(vues.BUILDING_TYPE_CHOICES)),
        ('PROJECT_TYPE_CHOICES', list(vues.PROJECT_TYPE_CHOICES)),
        ('GAMMES_CHOICES', list(vues.GAMMES_CHOICES)),
        ('PANNES_CHOICES', list(vues.PANNES_CHOICES)),
    )


def test_aucun_libelle_n_est_une_chaine_nue():
    """Un libellé ajouté demain sans enveloppe recréerait le défaut.

    Et il le recréerait silencieusement : la page s'afficherait, avec une
    option de plus en français au milieu des autres.
    """
    from django.utils.functional import Promise

    nues = []
    for nom, paires in _toutes_les_listes():
        for cle, libelle in paires:
            if not isinstance(libelle, Promise):
                nues.append('%s[%s] = %r' % (nom, cle, libelle))

    assert not nues, (
        'Ces libellés ne sont pas traduits paresseusement :\n  '
        + '\n  '.join(nues))


@pytest.mark.parametrize('langue', LANGUES)
def test_chaque_libelle_a_sa_traduction_dans_chaque_langue(langue):
    """ENVELOPPÉ N'EST PAS TRADUIT, et c'est le piège qui reste.

    `gettext_lazy` rend le français sans broncher quand la chaîne manque au
    catalogue. Entourer un libellé donne donc l'impression du travail fait,
    et la page reste en français — exactement l'état d'avant, mais avec du
    code qui a l'air correct.

    Ce test lit les catalogues COMPILÉS (`.mo`), ceux que Django consulte
    vraiment, et non les `.po`. Les quatre catalogues de ce projet étaient
    d'ailleurs plus anciens que leurs sources au moment de ce correctif :
    mesurer le `.po` aurait validé des traductions que rien ne servait.
    """
    import gettext

    from django.utils.translation import override

    chemin = 'locale/%s/LC_MESSAGES/django.mo' % langue
    with open(chemin, 'rb') as flux:
        catalogue = gettext.GNUTranslations(flux)

    # ON MESURE LA PRÉSENCE AU CATALOGUE, et non « la traduction diffère du
    # français ». Une première version de ce test comparait les deux
    # chaînes, et réclamait donc une traduction pour « Commerce », dont la
    # version anglaise est... « Commerce ». Elle aurait exigé une liste
    # d'exceptions, à rallonger chaque fois qu'un mot se trouve identique
    # dans deux langues — une garde qui demande qu'on l'entretienne finit
    # par être désactivée.
    present = set(catalogue._catalog)

    manquantes = []
    for nom, paires in _toutes_les_listes():
        for _cle, libelle in paires:
            # La chaîne SOURCE, et non `str(libelle)` : celui-ci résoudrait
            # la traduction dans la langue active du test et on chercherait
            # alors le portugais dans le catalogue portugais.
            with override('fr'):
                source = str(libelle)
            if source not in present:
                manquantes.append('%s / %s' % (nom, source))

    assert not manquantes, (
        'Absentes du catalogue compilé %s (donc rendues en français) :\n  '
        % langue + '\n  '.join(manquantes))


def test_les_gammes_suivent_toujours_le_modele():
    """La duplication assumée doit rester alignée.

    `GAMMES_CHOICES` redit les clés de
    `GuidedQuoteRequest.QUALITY_LEVEL_CHOICES` pour éviter une migration sur
    un changement de `choices` sans effet en base. Le risque est qu'elle
    divorce du modèle sans que personne ne le voie : une gamme ajoutée au
    modèle n'apparaîtrait pas dans le configurateur, et une clé renommée
    enverrait une valeur que le modèle refuse.
    """
    from apps.btp.models import GuidedQuoteRequest
    from apps.websites.electricite_wizard_views import GAMMES_CHOICES

    du_modele = [cle for cle, _l in GuidedQuoteRequest.QUALITY_LEVEL_CHOICES]
    du_configurateur = [cle for cle, _l in GAMMES_CHOICES]
    assert du_configurateur == du_modele


def test_les_multiplicateurs_couvrent_toutes_les_gammes():
    """Une gamme sans multiplicateur ferait tomber l'estimation.

    `QUALITY_MULTIPLIERS[quality]` est lu sans défaut lors du chiffrage :
    une clé manquante lève une KeyError au milieu d'une demande de devis
    déjà enregistrée.
    """
    from apps.websites.electricite_wizard_views import (
        GAMMES_CHOICES, QUALITY_MULTIPLIERS,
    )

    for cle, _libelle in GAMMES_CHOICES:
        assert cle in QUALITY_MULTIPLIERS, cle


def test_la_carte_des_categories_couvre_tous_les_equipements():
    """Elle est dérivée de la même liste : le test garde cette dérivation.

    Écrite à la main, elle aurait fini par oublier un équipement — qui
    serait alors chiffré dans la catégorie « autre », donc au mauvais prix,
    sans que rien ne le signale.
    """
    from apps.websites.electricite_wizard_views import (
        EQUIPMENT_CATEGORY_MAP, EQUIPMENT_CHOICES, LIBELLE_EQUIPEMENT,
    )

    for cle, _libelle, _cat in EQUIPMENT_CHOICES:
        assert cle in EQUIPMENT_CATEGORY_MAP
        assert cle in LIBELLE_EQUIPEMENT
