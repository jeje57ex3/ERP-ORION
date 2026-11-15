"""« Je veux connecter le site Sparkling Peace au domaine s-peace.com. »

LE CHAÎNON QUI MANQUAIT

Brancher un domaine sur un site demande quatre choses, et seules trois
existaient :

  1. un enregistrement WebsiteDomain  — l'écran des domaines le crée ;
  2. un CNAME chez Cloudflare         — le « Sync DNS » du tunnel le pose ;
  3. une règle d'ingress vers Django  — l'écran du tunnel la publie ;
  4. quelque chose qui serve la vitrine quand on demande « / ».

Faute du quatrième, « https://s-peace.com/ » arrivait sur la racine de
l'ERP — l'écran de connexion — et non sur le site. Les trois premières
étapes pouvaient être parfaites, le résultat restait faux. C'est le défaut
le plus décourageant de la série : tout semble en place, et rien ne marche.

CE QUE CES TESTS SURVEILLENT EN PRIORITÉ

Pas que la vitrine s'affiche — mais que l'ERP reste JOIGNABLE. Un
middleware qui réécrit les chemins de toutes les requêtes peut, sur une
erreur de réglage, rendre inaccessible l'écran où l'on corrigerait ce
réglage. La moitié de ce fichier vérifie qu'on n'a pas ouvert cette porte.
"""
import pytest
from django.test import override_settings


@pytest.fixture
def site_et_domaine(db):
    from apps.core.models import Company
    from apps.websites.models import WebsiteDomain
    from apps.websites.vitrine_etancheite import creer_le_site

    entreprise = Company.objects.create(name='Volt SARL', slug='volt-sarl')
    site, _ = creer_le_site(entreprise)
    site.is_active = True
    site.is_published = True
    site.status = 'published'
    site.save()

    domaine = WebsiteDomain.objects.create(
        website=site, company=entreprise, domain='s-peace.com',
        status='active', dns_verified=True)

    return {'entreprise': entreprise, 'site': site, 'domaine': domaine}


HOTES = ['testserver', 's-peace.com']


# ── 1. Le site répond à la racine de son domaine ─────────────────────────────

@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=HOTES)
def test_la_racine_du_domaine_sert_la_vitrine(client, site_et_domaine):
    """LA DEMANDE : « s-peace.com » doit afficher Sparkling Peace."""
    reponse = client.get('/', HTTP_HOST='s-peace.com')

    assert reponse.status_code == 200
    # Le gabarit de la vitrine, et non celui de l'ERP.
    gabarits = [t.name for t in reponse.templates if t.name]
    assert any('public/etancheite' in nom for nom in gabarits), gabarits


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=HOTES)
def test_les_pages_internes_suivent(client, site_et_domaine):
    """Une vitrine n'est pas qu'une page d'accueil."""
    reponse = client.get('/contact/', HTTP_HOST='s-peace.com')

    assert reponse.status_code == 200


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=HOTES)
def test_l_adresse_publique_reste_affichee(client, site_et_domaine):
    """ON RÉÉCRIT, ON NE REDIRIGE PAS.

    Une redirection afficherait « /sites/electricite-etancheite/etancheite/ »
    dans la barre d'adresse : le domaine qu'on vient de brancher
    disparaîtrait dès la première page.
    """
    reponse = client.get('/', HTTP_HOST='s-peace.com')

    assert reponse.status_code == 200, 'une redirection rendrait 301/302'


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=HOTES)
def test_le_prefixe_ne_s_empile_pas(client, site_et_domaine):
    """Sans garde, une page déjà sous le bon préfixe le recevrait une
    seconde fois à chaque requête."""
    chemin = f"/sites/{site_et_domaine['site'].slug}/etancheite/"

    reponse = client.get(chemin, HTTP_HOST='s-peace.com')

    assert reponse.status_code == 200


# ── 2. Ce qui ne doit JAMAIS être réécrit ────────────────────────────────────

@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=HOTES)
@pytest.mark.parametrize('chemin', [
    '/static/css/orion-ui.css', '/media/x.png', '/api/v1/ping/',
    '/orion-admin/', '/accounts/login/', '/admin/',
])
def test_les_chemins_techniques_passent_sans_reecriture(client, site_et_domaine,
                                                        chemin):
    """LA GARANTIE LA PLUS IMPORTANTE DE CE FICHIER.

    Un middleware qui reecrit tout peut rendre inaccessible l'ecran ou l'on
    corrigerait le reglage fautif. On ne verifie pas que ces adresses
    repondent 200 — certaines redirigent vers la connexion, c'est normal —
    mais qu'elles ne sont PAS detournees vers la vitrine.
    """
    reponse = client.get(chemin, HTTP_HOST='s-peace.com')

    gabarits = [t.name for t in getattr(reponse, 'templates', []) if t.name]
    assert not any('public/etancheite' in nom for nom in gabarits), (
        f'{chemin} a ete detourne vers la vitrine')


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=HOTES)
def test_un_hote_interne_n_est_jamais_reecrit(client, site_et_domaine):
    """L'ERP doit rester lui-meme sur « localhost » et sur son propre
    domaine, quoi qu'on ait branche ailleurs."""
    reponse = client.get('/', HTTP_HOST='testserver')

    gabarits = [t.name for t in getattr(reponse, 'templates', []) if t.name]
    assert not any('public/etancheite' in nom for nom in gabarits)


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=HOTES + ['inconnu.test'])
def test_un_domaine_sans_site_laisse_l_ERP_tranquille(client, site_et_domaine):
    """Un nom d'hote qu'aucun WebsiteDomain ne reclame ne doit rien
    declencher."""
    reponse = client.get('/', HTTP_HOST='inconnu.test')

    gabarits = [t.name for t in getattr(reponse, 'templates', []) if t.name]
    assert not any('public/etancheite' in nom for nom in gabarits)


# ── 3. L'état du domaine compte ──────────────────────────────────────────────

@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=HOTES)
def test_un_domaine_non_verifie_ne_sert_rien(client, site_et_domaine):
    """Un domaine ajouté mais ni actif ni vérifié ne doit pas encore
    détourner le trafic : on pourrait l'avoir saisi par erreur."""
    domaine = site_et_domaine['domaine']
    domaine.status = 'pending'
    domaine.dns_verified = False
    domaine.save()

    reponse = client.get('/', HTTP_HOST='s-peace.com')

    gabarits = [t.name for t in getattr(reponse, 'templates', []) if t.name]
    assert not any('public/etancheite' in nom for nom in gabarits)


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=HOTES)
def test_un_site_en_maintenance_le_dit(client, site_et_domaine):
    """Le resolveur rend deja la page de maintenance : la reecriture ne doit
    pas passer devant."""
    site = site_et_domaine['site']
    site.maintenance_mode = True
    site.save()

    reponse = client.get('/', HTTP_HOST='s-peace.com')

    assert reponse.status_code == 503


# ── 4. ALLOWED_HOSTS : le cinquième chaînon ──────────────────────────────────

"""`ALLOWED_HOSTS` est figé au provisionnement. Un domaine branché ensuite
n'y figure pas : Django répond 400 DisallowedHost avant d'atteindre la
moindre vue, et le message ne parle ni du site ni du domaine. Le corriger
demandait d'éditer le .env en SSH puis de redémarrer gunicorn.

Ces tests vérifient l'ouverture — et surtout qu'elle reste ÉTROITE."""


@pytest.fixture(autouse=True)
def _cache_propre():
    """Le middleware met ses verdicts en cache. Sans vidage entre deux
    tests, le second lirait la réponse du premier."""
    from django.core.cache import cache
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=['testserver'])
def test_un_domaine_connecte_devient_joignable_sans_redemarrage(client,
                                                                site_et_domaine):
    """LE BUT : « s-peace.com » n'est pas dans ALLOWED_HOSTS, et répond."""
    reponse = client.get('/', HTTP_HOST='s-peace.com')

    assert reponse.status_code == 200


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=['testserver'])
def test_un_hote_inconnu_reste_refuse(client, site_et_domaine):
    """LA GARANTIE DE SÉCURITÉ.

    On n'ouvre pas ALLOWED_HOSTS : on y ajoute les seuls noms qu'un
    WebsiteDomain actif réclame. Tout le reste est refusé comme avant.
    """
    reponse = client.get('/', HTTP_HOST='pirate.test')

    assert reponse.status_code == 400, (
        'un hote quelconque a ete accepte — la protection contre '
        'l’empoisonnement de l’en-tete Host est tombee')


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=['testserver'])
def test_un_domaine_non_verifie_n_ouvre_pas_la_porte(client, site_et_domaine):
    """Un domaine saisi mais ni actif ni vérifié ne doit pas suffire : il a
    pu être ajouté par erreur, ou pour un site qu'on n'a pas encore voulu
    exposer."""
    domaine = site_et_domaine['domaine']
    domaine.status = 'pending'
    domaine.dns_verified = False
    domaine.save()

    reponse = client.get('/', HTTP_HOST='s-peace.com')

    assert reponse.status_code == 400


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=['testserver'])
def test_un_site_desactive_n_ouvre_pas_la_porte(client, site_et_domaine):
    site = site_et_domaine['site']
    site.is_active = False
    site.save()

    reponse = client.get('/', HTTP_HOST='s-peace.com')

    assert reponse.status_code == 400


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=['testserver'])
def test_le_verdict_negatif_est_mis_en_cache(client, site_et_domaine,
                                              django_assert_num_queries):
    """Sans mise en cache des REFUS, il suffirait d'envoyer des noms au
    hasard pour faire travailler la base a volonte."""
    from django.core.cache import cache

    client.get('/', HTTP_HOST='pirate.test')

    assert cache.get('hote-de-site:pirate.test') is False


@pytest.mark.django_db
@override_settings(ALLOWED_HOSTS=['testserver'])
def test_le_port_et_la_casse_ne_trompent_pas_le_filtre(client, site_et_domaine):
    """« S-PEACE.COM:443 » designe le meme hote : un filtre sensible a la
    casse ou au port le refuserait a tort."""
    reponse = client.get('/', HTTP_HOST='S-PEACE.COM:443')

    assert reponse.status_code == 200


# ── 5. Le routage suit le TYPE du site ───────────────────────────────────────

"""La premiere version ne connaissait qu'un cas, la vitrine « etancheite »,
reconnue a son slug. Un site de type « electricite » — « SPARKLING PEACE –
Electricite » — tombait sur les vues generiques : la page s'affichait,
simplement ce n'etait pas la bonne.

On s'aligne desormais sur « home_redirect » (erp_btp/urls.py), qui route
deja par site_type. Deux endroits qui decident du meme routage avec des
regles differentes finissent toujours par se contredire."""


@pytest.mark.parametrize('site_type, slug, attendu', [
    ('electricite', 'sparkling-peace-electricite',
     '/sites/sparkling-peace-electricite/electricite/'),
    ('btp', 'neostructura', '/sites/neostructura/btp/'),
    ('showcase', 'vitrine-simple', '/sites/vitrine-simple/'),
    ('ecommerce', 'siecle', '/sites/siecle/'),
])
@pytest.mark.django_db
def test_chaque_type_de_site_a_son_prefixe(db, site_type, slug, attendu):
    from apps.core.models import Company
    from apps.websites.domaine_vitrine_middleware import _prefixe_public
    from apps.websites.models import Website

    entreprise = Company.objects.create(name='T SA', slug='t-sa')
    site = Website.objects.create(
        company=entreprise, name='Site', slug=slug, site_type=site_type)

    assert _prefixe_public(site) == attendu


@pytest.mark.django_db
def test_la_vitrine_etancheite_garde_son_prefixe(db):
    """Elle n'a pas de site_type dedie : elle se reconnait au slug, et ce
    cas doit passer AVANT le type."""
    from apps.core.models import Company
    from apps.websites.domaine_vitrine_middleware import _prefixe_public
    from apps.websites.models import Website
    from apps.websites.vitrine_etancheite import SLUG

    entreprise = Company.objects.create(name='V SA', slug='v-sa')
    site = Website.objects.create(
        company=entreprise, name='Vitrine', slug=SLUG, site_type='showcase')

    assert _prefixe_public(site) == f'/sites/{SLUG}/etancheite/'


@pytest.mark.django_db
def test_un_site_sans_slug_retombe_sur_celui_de_l_entreprise(db):
    """« public_slug » et non « slug » : c'est ce que les adresses publiques
    emploient."""
    from apps.core.models import Company
    from apps.websites.domaine_vitrine_middleware import _prefixe_public
    from apps.websites.models import Website

    entreprise = Company.objects.create(name='Sans Slug SA', slug='sans-slug')
    site = Website.objects.create(
        company=entreprise, name='Site', site_type='electricite')
    # « save() » recalcule le slug depuis le nom : on ecrit donc en base
    # sans passer par lui, pour obtenir l'etat qu'on veut eprouver.
    Website.objects.filter(pk=site.pk).update(slug='')
    site.refresh_from_db()

    assert _prefixe_public(site) == '/sites/sans-slug/electricite/'
