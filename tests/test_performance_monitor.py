# -*- coding: utf-8 -*-
"""Le module Performance mesure vraiment quelque chose.

RAPPORTÉ DEPUIS L'ÉCRAN : « le module performances ne m'affiche rien ».
C'était exact, et pour deux raisons superposées.

1. **Le middleware n'était déclaré nulle part.** L'application figurait
   dans `INSTALLED_APPS`, son modèle existait, sa vue était correcte, son
   gabarit aussi — et rien ne mesurait quoi que ce soit. La table restait
   vide, la page muette. C'est le même défaut que celui dont la docstring
   de la vue garde la trace : « l'application n'étant pas déclarée,
   personne ne l'avait jamais vue ».

2. **Il n'enregistrait que les requêtes dépassant 800 ms.** Même branché,
   un ERP qui se porte bien n'aurait rien affiché — et on en aurait conclu
   qu'il était encore cassé. D'où l'échantillonnage : une requête sur N est
   enregistrée telle quelle, ce qui donne une LATENCE et non un simple
   journal des incidents.

Et un troisième défaut, invisible à l'œil nu : `len(connection.queries)`
ne vaut quelque chose QUE si `DEBUG` est vrai. La colonne « SQL » aurait
affiché 0 partout en production. Une colonne qui ment est pire qu'une
colonne absente, parce qu'on la croit.
"""

import pytest
from django.conf import settings
from django.test import RequestFactory

pytestmark = pytest.mark.django_db


CHEMIN_DU_MIDDLEWARE = (
    'apps.performance_monitor.middleware.PerformanceMiddleware')


# ─── Le défaut principal : il n'était branché nulle part ──────────────────

def test_le_middleware_est_declare():
    """Sans cette ligne, rien n'est jamais mesuré et la page reste vide."""
    assert CHEMIN_DU_MIDDLEWARE in settings.MIDDLEWARE, (
        "le module Performance n'affichera rien tant que son middleware "
        "n'est pas dans MIDDLEWARE")


def test_le_middleware_est_tout_en_haut_de_la_pile():
    """Il doit mesurer ce que le navigateur subit, pas ce qui reste.

    Placé plus bas, la durée qu'il relève exclut tout ce que les
    middlewares précédents ont consommé — et une lenteur venue de l'un
    d'eux serait invisible, c'est-à-dire précisément celle qu'on cherche.
    """
    position = settings.MIDDLEWARE.index(CHEMIN_DU_MIDDLEWARE)

    assert position <= 1, (
        'place en %d : la mesure exclurait les middlewares precedents'
        % position)


# ─── Le comptage SQL, qui mentait hors DEBUG ──────────────────────────────

def _middleware(reponse_factice=None, **reglages):
    """Instancie le middleware avec ses propres réglages.

    Django n'instancie ses middlewares qu'UNE fois par processus : modifier
    le réglage après coup ne changerait rien à celui qui tourne. On
    construit donc le nôtre, ce qui teste exactement la décision voulue.
    """
    from django.http import HttpResponse

    from apps.performance_monitor.middleware import PerformanceMiddleware

    def repondre(request):
        if reponse_factice is not None:
            return reponse_factice(request)
        return HttpResponse('ok')

    intergiciel = PerformanceMiddleware(repondre)
    for nom, valeur in reglages.items():
        setattr(intergiciel, nom, valeur)
    return intergiciel


def test_les_requetes_sql_sont_comptees_meme_hors_debug(settings):
    """`len(connection.queries)` est vide quand DEBUG est faux.

    C'est ce que faisait la version précédente : la colonne SQL aurait
    affiché 0 sur chaque ligne en production.
    """
    from django.contrib.auth import get_user_model
    from django.http import HttpResponse

    settings.DEBUG = False

    def repondre(request):
        # Une vraie requete SQL, pendant le traitement.
        get_user_model().objects.count()
        return HttpResponse('ok')

    intergiciel = _middleware(repondre)
    reponse = intergiciel(RequestFactory().get('/une-page/'))

    assert int(reponse['X-Orion-SQL-Count']) >= 1, (
        'le comptage SQL retombe a zero hors DEBUG')


def test_la_duree_est_posee_sur_toutes_les_reponses():
    """Y compris celles qu'on n'enregistre pas.

    L'en-tête ne coûte rien et permet de mesurer une page précise depuis
    le navigateur, sans attendre qu'elle tombe dans l'échantillon.
    """
    intergiciel = _middleware(taux=1000000)
    reponse = intergiciel(RequestFactory().get('/une-page/'))

    assert 'X-Orion-Response-Time-ms' in reponse
    assert int(reponse['X-Orion-Response-Time-ms']) >= 0


# ─── L'échantillonnage : ce qui donne une latence ─────────────────────────

def _compter():
    from apps.performance_monitor.models import PerformanceEvent
    return PerformanceEvent.objects.count()


def test_une_requete_rapide_peut_etre_enregistree():
    """Sans cela, un ERP en bonne santé n'affiche rien du tout."""
    intergiciel = _middleware(taux=1, seuil_lent_ms=100000)
    avant = _compter()

    intergiciel(RequestFactory().get('/une-page/'))

    assert _compter() == avant + 1


def test_une_requete_rapide_est_notee_info_et_non_lente():
    from apps.performance_monitor.models import PerformanceEvent

    intergiciel = _middleware(taux=1, seuil_lent_ms=100000)
    intergiciel(RequestFactory().get('/une-page-rapide/'))

    mesure = PerformanceEvent.objects.order_by('-pk').first()
    assert mesure.level == 'info'


def test_une_requete_lente_est_toujours_enregistree():
    """Une lenteur ne doit jamais dépendre d'un tirage au sort."""
    from apps.performance_monitor.models import PerformanceEvent

    # Taux enorme : l'echantillonnage ne retiendrait quasiment jamais.
    # Seuil a zero : tout est « lent ».
    intergiciel = _middleware(taux=1000000, seuil_lent_ms=0)
    intergiciel(RequestFactory().get('/une-page-lente/'))

    mesure = PerformanceEvent.objects.order_by('-pk').first()
    assert mesure is not None
    assert mesure.level == 'slow'
    assert mesure.path == '/une-page-lente/'


@pytest.mark.parametrize('chemin', [
    '/static/css/orion.css',
    '/media/project_documents/photo.jpg',
    '/favicon.ico',
    '/ha/health/',
])
def test_les_fichiers_statiques_ne_sont_jamais_mesures(chemin):
    """Leur rapidité ferait tomber la médiane à quelques millisecondes.

    Un CSS rendu par WhiteNoise et une page de l'ERP ne se comparent pas :
    les mélanger masquerait complètement la lenteur des pages, qui est la
    seule chose qu'on veuille voir ici.
    """
    intergiciel = _middleware(taux=1, seuil_lent_ms=0)
    avant = _compter()

    intergiciel(RequestFactory().get(chemin))

    assert _compter() == avant, 'chemin mesure a tort : %s' % chemin


def test_un_echec_d_enregistrement_ne_casse_pas_la_requete(monkeypatch):
    """Mesurer la performance ne doit jamais faire échouer la requête.

    Base injoignable, table absente avant migration, disque plein : la
    page doit sortir quand même.
    """
    from apps.performance_monitor import models

    def exploser(*args, **kwargs):
        raise RuntimeError('base injoignable')

    monkeypatch.setattr(models.PerformanceEvent.objects, 'create', exploser)

    intergiciel = _middleware(taux=1, seuil_lent_ms=0)
    reponse = intergiciel(RequestFactory().get('/une-page/'))

    assert reponse.status_code == 200


# ─── La latence affichée : centiles, pas moyenne seule ────────────────────

def test_les_centiles_sont_justes():
    from apps.performance_monitor.views import _centile

    valeurs = list(range(1, 101))
    assert _centile(valeurs, 0.50) == 51
    assert _centile(valeurs, 0.95) == 95
    assert _centile([], 0.95) == 0
    assert _centile([42], 0.95) == 42


def test_la_mediane_resiste_a_une_requete_hors_du_lot():
    """La raison d'être des centiles.

    Une page à dix secondes noyée dans cent pages à cinquante
    millisecondes déplace la moyenne d'un bon tiers, et on chercherait une
    lenteur générale qui n'existe pas. La médiane, elle, ne bouge pas.
    """
    from apps.performance_monitor.views import _centile

    valeurs = sorted([50] * 100 + [10000])
    moyenne = sum(valeurs) / len(valeurs)

    assert _centile(valeurs, 0.50) == 50
    assert moyenne > 140, 'la moyenne devrait etre tiree vers le haut'


@pytest.fixture
def super_admin(client, django_user_model):
    """Un super-administrateur, et une entreprise.

    L'entreprise n'est pas facultative : `SetupRequiredMiddleware` renvoie
    vers l'assistant de premier accès tant qu'il n'en existe aucune, et la
    page de performance ne serait jamais rendue. Deux de ces tests ont
    d'abord échoué pour cette raison, et c'étaient eux qui avaient tort.
    """
    from apps.core.models import Company

    entreprise = Company.objects.create(name='Volt SARL', slug='volt-sarl')
    utilisateur = django_user_model.objects.create_superuser(
        username='chef', password='motdepasse-test', email='chef@exemple.fr')
    utilisateur.profile.companies.add(entreprise)
    utilisateur.profile.current_company = entreprise
    utilisateur.profile.save()
    client.force_login(utilisateur)
    return client


def test_le_tableau_de_bord_affiche_la_latence(super_admin):
    from django.urls import reverse

    from apps.performance_monitor.models import PerformanceEvent

    for duree in (40, 60, 80, 2500):
        PerformanceEvent.objects.create(
            path='/btp/chantiers/', method='GET', status_code=200,
            response_ms=duree, sql_count=3,
            level='slow' if duree >= 800 else 'info')

    contenu = super_admin.get(
        reverse('performance_monitor:dashboard')).content.decode()

    assert 'Latence médiane' in contenu
    assert '95' in contenu
    assert '2500' in contenu


def test_sans_mesure_la_page_explique_pourquoi(super_admin):
    """Une page vide qui ne s'explique pas fait croire à un module cassé.

    C'est exactement ce qui s'est passé : elle est restée vide des mois
    parce que son middleware n'était déclaré nulle part.
    """
    from django.urls import reverse

    contenu = super_admin.get(
        reverse('performance_monitor:dashboard')).content.decode()

    assert 'Aucune mesure' in contenu
    assert 'échantillonnage' in contenu
