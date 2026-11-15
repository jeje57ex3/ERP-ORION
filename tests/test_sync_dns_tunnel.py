"""« Le sync DNS se déclenche mais ne marche pas pour les tunnels Cloudflare. »

TROIS DÉFAUTS, ET LE PREMIER EXPLIQUE LE SYMPTÔME

1. LA ZONE ÉTAIT DEVINÉE EN DÉCOUPANT LE NOM. « les deux derniers
   segments » donne « exemple.fr » pour « orion.exemple.fr » — juste — mais
   « co.uk » pour « boutique.exemple.co.uk », qui n'existe pas. On demande
   désormais ses zones à Cloudflare et on retient la plus longue qui
   termine le nom d'hôte.

2. TOUTE EXCEPTION ÉTAIT AVALÉE. `_get_zone_id` enveloppait son appel dans
   un « except Exception: pass » et rendait None. Un jeton invalide, un
   réseau coupé ou un délai dépassé se lisaient donc tous « Zone Cloudflare
   introuvable » — et l'on cherchait un domaine mal orthographié pendant
   que le vrai coupable était le jeton.

3. SEULS LES CNAME ÉTAIENT CHERCHÉS. Quand un enregistrement A existait
   déjà pour ce nom — le cas courant d'un domaine qui pointait vers un
   serveur avant de passer au tunnel — aucun n'était trouvé, un CNAME était
   créé, et Cloudflare refusait : un nom ne peut pas porter les deux.

Les réponses de Cloudflare sont SIMULÉES ici. On ne teste pas Cloudflare :
on teste que chaque réponse possible produit un message exploitable plutôt
qu'un verdict trompeur.
"""
import pytest
import requests

from apps.websites import tunnel_service

# « requests » est importe DANS les fonctions de tunnel_service, pas au
# niveau du module : il n'y a donc pas d'attribut « requests »
# a remplacer. On agit sur le module lui-meme, que l'import local retrouve
# dans sys.modules — on patche ainsi le code reel, sans l'avoir modifie
# pour les besoins du test.


class FausseReponse:
    def __init__(self, charge, status_code=200):
        self._charge = charge
        self.status_code = status_code

    def json(self):
        if self._charge is _ILLISIBLE:
            raise ValueError('pas du JSON')
        return self._charge


_ILLISIBLE = object()


def _zones(*noms):
    return {'success': True,
            'result': [{'id': f'id-{n}', 'name': n} for n in noms],
            'result_info': {'total_pages': 1}}


# ── 1. Trouver la bonne zone ─────────────────────────────────────────────────

def test_une_zone_a_suffixe_double_est_trouvee(monkeypatch):
    """LE CAS QUE LE DÉCOUPAGE RATAIT : « .co.uk » compte deux segments."""
    monkeypatch.setattr(requests, 'get',
                        lambda *a, **k: FausseReponse(_zones('exemple.co.uk')))

    zone, erreur = tunnel_service._trouver_la_zone('jeton',
                                                   'boutique.exemple.co.uk')

    assert erreur == ''
    assert zone['name'] == 'exemple.co.uk'


def test_la_zone_la_plus_longue_l_emporte(monkeypatch):
    """Si le compte heberge « exemple.fr » ET « client.exemple.fr », c'est la
    seconde qui gouverne « www.client.exemple.fr »."""
    monkeypatch.setattr(
        requests, 'get',
        lambda *a, **k: FausseReponse(_zones('exemple.fr', 'client.exemple.fr')))

    zone, _ = tunnel_service._trouver_la_zone('jeton', 'www.client.exemple.fr')

    assert zone['name'] == 'client.exemple.fr'


def test_le_nom_de_zone_lui_meme_est_accepte(monkeypatch):
    monkeypatch.setattr(requests, 'get',
                        lambda *a, **k: FausseReponse(_zones('exemple.fr')))

    zone, _ = tunnel_service._trouver_la_zone('jeton', 'exemple.fr')

    assert zone['name'] == 'exemple.fr'


def test_un_suffixe_partiel_ne_compte_pas(monkeypatch):
    """« pasexemple.fr » ne doit pas tomber dans la zone « exemple.fr » : un
    « endswith » nu les confondrait."""
    monkeypatch.setattr(requests, 'get',
                        lambda *a, **k: FausseReponse(_zones('exemple.fr')))

    zone, erreur = tunnel_service._trouver_la_zone('jeton', 'pasexemple.fr')

    assert zone is None
    assert 'Aucune zone' in erreur


# ── 2. Dire la vraie cause ───────────────────────────────────────────────────

def test_un_jeton_refuse_le_dit(monkeypatch):
    """LE DÉFAUT CENTRAL : ceci se lisait « zone introuvable »."""
    monkeypatch.setattr(
        requests, 'get',
        lambda *a, **k: FausseReponse(
            {'success': False,
             'errors': [{'code': 9109, 'message': 'Invalid access token'}]}))

    zone, erreur = tunnel_service._trouver_la_zone('mauvais', 'a.exemple.fr')

    assert zone is None
    assert 'Invalid access token' in erreur
    assert 'jeton' in erreur.lower()


def test_un_reseau_coupe_le_dit(monkeypatch):
    def tombe(*a, **k):
        raise OSError('connexion refusée')

    monkeypatch.setattr(requests, 'get', tombe)

    zone, erreur = tunnel_service._trouver_la_zone('jeton', 'a.exemple.fr')

    assert zone is None
    assert 'injoignable' in erreur.lower()


def test_une_reponse_illisible_ne_fait_pas_tomber_l_ecran(monkeypatch):
    monkeypatch.setattr(requests, 'get',
                        lambda *a, **k: FausseReponse(_ILLISIBLE, 502))

    zone, erreur = tunnel_service._trouver_la_zone('jeton', 'a.exemple.fr')

    assert zone is None
    assert '502' in erreur


def test_un_jeton_sans_zone_visible_le_dit(monkeypatch):
    monkeypatch.setattr(
        requests, 'get',
        lambda *a, **k: FausseReponse(
            {'success': True, 'result': [], 'result_info': {'total_pages': 1}}))

    zone, erreur = tunnel_service._trouver_la_zone('jeton', 'a.exemple.fr')

    assert zone is None
    assert 'Aucune zone' in erreur


def test_les_zones_sont_lues_sur_plusieurs_pages(monkeypatch):
    """Un compte de plus de cinquante zones : la seconde page doit etre lue,
    sinon la zone cherchee peut n'etre jamais vue."""
    pages = {
        1: {'success': True,
            'result': [{'id': 'a', 'name': 'autre.fr'}],
            'result_info': {'total_pages': 2}},
        2: {'success': True,
            'result': [{'id': 'b', 'name': 'exemple.fr'}],
            'result_info': {'total_pages': 2}},
    }
    monkeypatch.setattr(
        requests, 'get',
        lambda *a, **k: FausseReponse(pages[k['params']['page']]))

    zone, erreur = tunnel_service._trouver_la_zone('jeton', 'www.exemple.fr')

    assert erreur == ''
    assert zone['name'] == 'exemple.fr'


# ── 3. Le conflit avec un enregistrement A ───────────────────────────────────

@pytest.fixture
def regle(db):
    from apps.core.models import Company
    from apps.websites.models_domains import (CloudflareAccount,
                                              CloudflareTunnel,
                                              TunnelIngressRule)

    entreprise = Company.objects.create(name='Martin SA', slug='martin-sa')
    compte = CloudflareAccount.objects.create(
        company=entreprise, label='Compte', api_token='jeton', is_active=True)
    tunnel = CloudflareTunnel.objects.create(
        company=entreprise, cloudflare_account=compte, name='Tunnel',
        tunnel_id='640137d9-fd65-4d2b-bda7-ba1de14c82a8')
    return TunnelIngressRule.objects.create(
        tunnel=tunnel, hostname='orion.exemple.fr', service='http://localhost:9000')


@pytest.mark.django_db
def test_un_enregistrement_A_existant_est_nomme(regle, monkeypatch):
    """LE TROISIÈME DÉFAUT.

    Cloudflare interdit un A et un CNAME sur le même nom. L'ancienne
    version ne cherchait que les CNAME, n'en trouvait aucun, tentait de
    créer — et le refus ne disait ni quel enregistrement gênait, ni où.
    """
    def get(url, **k):
        if url.endswith('/zones'):
            return FausseReponse(_zones('exemple.fr'))
        return FausseReponse({'success': True, 'result': [
            {'id': 'r1', 'type': 'A', 'content': '203.0.113.7'}]})

    monkeypatch.setattr(requests, 'get', get)

    ok, message = tunnel_service.sync_tunnel_dns(regle)

    assert ok is False
    assert 'A' in message and '203.0.113.7' in message
    assert 'CNAME' in message


@pytest.mark.django_db
def test_un_cname_existant_est_mis_a_jour(regle, monkeypatch):
    appels = {}

    def get(url, **k):
        if url.endswith('/zones'):
            return FausseReponse(_zones('exemple.fr'))
        return FausseReponse({'success': True, 'result': [
            {'id': 'r1', 'type': 'CNAME', 'content': 'ancien.cfargotunnel.com'}]})

    def put(url, json=None, **k):
        appels['put'] = (url, json)
        return FausseReponse({'success': True})

    monkeypatch.setattr(requests, 'get', get)
    monkeypatch.setattr(requests, 'put', put)

    ok, message = tunnel_service.sync_tunnel_dns(regle)

    assert ok is True, message
    url, charge = appels['put']
    assert url.endswith('/r1')
    assert charge['content'] == '640137d9-fd65-4d2b-bda7-ba1de14c82a8.cfargotunnel.com'
    # « proxied » est indispensable : un CNAME vers cfargotunnel.com non
    # proxifie ne resout rien.
    assert charge['proxied'] is True

    regle.refresh_from_db()
    assert regle.dns_synced is True


@pytest.mark.django_db
def test_le_succes_rappelle_de_publier_l_ingress(regle, monkeypatch):
    """LA SECONDE MOITIÉ DU PROBLÈME.

    Un tunnel lancé par jeton ignore le config.yml local : ses routes sont
    détenues par Cloudflare. Le CNAME peut être parfait et le nom répondre
    « erreur 1033 » tant que l'ingress n'a pas été publié. Le message de
    succès doit le dire, sans quoi on croit la synchronisation terminée.
    """
    def get(url, **k):
        if url.endswith('/zones'):
            return FausseReponse(_zones('exemple.fr'))
        return FausseReponse({'success': True, 'result': []})

    monkeypatch.setattr(requests, 'get', get)
    monkeypatch.setattr(requests, 'post',
                        lambda *a, **k: FausseReponse({'success': True}))

    ok, message = tunnel_service.sync_tunnel_dns(regle)

    assert ok is True
    assert '1033' in message


@pytest.mark.django_db
def test_sans_compte_cloudflare_le_message_est_clair(regle):
    regle.tunnel.cloudflare_account = None
    regle.tunnel.save()

    ok, message = tunnel_service.sync_tunnel_dns(regle)

    assert ok is False
    assert 'compte Cloudflare' in message


# ── 4. Remplacer l'enregistrement qui bloque ─────────────────────────────────

"""LE CAS REELLEMENT RENCONTRE

    Cloudflare API : An A, AAAA, or CNAME record with that host already
    exists.

Un enregistrement existait deja sur « s-peace.com ». Savoir pourquoi ne
suffit pas : il faut pouvoir le regler depuis l'interface. Un second bouton
« Remplacer » supprime l'enregistrement bloquant puis pose le CNAME.

Il est SEPARE du premier, et c'est tout le propos : cet enregistrement peut
servir a autre chose que ce tunnel.
"""


def _get_avec_A(url, **k):
    if url.endswith('/zones'):
        return FausseReponse(_zones('exemple.fr'))
    return FausseReponse({'success': True, 'result': [
        {'id': 'r1', 'type': 'A', 'content': '203.0.113.7'},
        {'id': 'r2', 'type': 'AAAA', 'content': '2001:db8::1'},
    ]})


@pytest.mark.django_db
def test_sans_demande_explicite_rien_n_est_supprime(regle, monkeypatch):
    """LA GARANTIE LA PLUS IMPORTANTE DE CETTE SECTION."""
    suppressions = []
    monkeypatch.setattr(requests, 'get', _get_avec_A)
    monkeypatch.setattr(requests, 'delete',
                        lambda *a, **k: suppressions.append(a) or FausseReponse({'success': True}))

    ok, message = tunnel_service.sync_tunnel_dns(regle)

    assert ok is False
    assert suppressions == [], 'un enregistrement a ete supprime sans demande'
    assert 'Remplacer' in message


@pytest.mark.django_db
def test_remplacer_supprime_tous_les_enregistrements_bloquants(regle, monkeypatch):
    """TOUS, pas seulement le premier : un nom peut porter un A ET un AAAA,
    et en laisser un suffirait a faire echouer la creation du CNAME."""
    supprimes = []

    def delete(url, **k):
        supprimes.append(url.rsplit('/', 1)[-1])
        return FausseReponse({'success': True})

    monkeypatch.setattr(requests, 'get', _get_avec_A)
    monkeypatch.setattr(requests, 'delete', delete)
    monkeypatch.setattr(requests, 'post',
                        lambda *a, **k: FausseReponse({'success': True}))

    ok, message = tunnel_service.sync_tunnel_dns(regle, remplacer=True)

    assert ok is True, message
    assert sorted(supprimes) == ['r1', 'r2']
    assert '203.0.113.7' in message, 'le message doit dire ce qui a ete supprime'


@pytest.mark.django_db
def test_un_refus_de_suppression_est_rapporte(regle, monkeypatch):
    """Si Cloudflare refuse la suppression, on ne doit pas enchainer sur la
    creation du CNAME : elle echouerait avec le meme message qu'avant, et
    l'on tournerait en rond."""
    monkeypatch.setattr(requests, 'get', _get_avec_A)
    monkeypatch.setattr(
        requests, 'delete',
        lambda *a, **k: FausseReponse(
            {'success': False,
             'errors': [{'message': 'Record is locked'}]}))

    ok, message = tunnel_service.sync_tunnel_dns(regle, remplacer=True)

    assert ok is False
    assert 'Record is locked' in message


@pytest.mark.django_db
def test_remplacer_sans_rien_a_supprimer_fonctionne(regle, monkeypatch):
    """Cliquer « Remplacer » alors qu'aucun enregistrement ne bloque doit
    simplement creer le CNAME, pas echouer."""
    def get(url, **k):
        if url.endswith('/zones'):
            return FausseReponse(_zones('exemple.fr'))
        return FausseReponse({'success': True, 'result': []})

    monkeypatch.setattr(requests, 'get', get)
    monkeypatch.setattr(requests, 'post',
                        lambda *a, **k: FausseReponse({'success': True}))

    ok, message = tunnel_service.sync_tunnel_dns(regle, remplacer=True)

    assert ok is True, message


def test_l_ecran_propose_les_deux_boutons_separement():
    """Le remplacement ne doit pas pouvoir se declencher par megarde : deux
    formulaires distincts, et une confirmation sur le second."""
    from pathlib import Path

    gabarit = Path('templates/websites/tunnel/tunnel_detail.html').read_text(
        encoding='utf-8')

    assert 'name="remplacer" value="1"' in gabarit
    assert 'onclick="return confirm(' in gabarit


# ── 5. Le diagnostic de l'erreur 1033 ────────────────────────────────────────

"""« Error 1033 — Cloudflare is currently unable to resolve it » ne dit pas
laquelle de ses deux causes s'applique : aucun connecteur relie, ou aucune
route publiee pour ce nom. Les deux produisent le meme ecran. Sans les
distinguer, on redemarre un connecteur qui tournait deja, ou l'on republie
une route qui existait.
"""


def _verdict(etapes, nom):
    return next(e for e in etapes if e['nom'] == nom)


@pytest.mark.django_db
def test_une_route_absente_est_nommee_comme_cause(regle, monkeypatch):
    """LA CAUSE LA PLUS FRÉQUENTE : le tunnel tourne, la route manque."""
    from apps.websites import cloudflare_service

    monkeypatch.setattr(cloudflare_service, 'fetch_cf_tunnels',
                        lambda c: {'success': True, 'tunnels': [
                            {'id': regle.tunnel.tunnel_id, 'name': 'T',
                             'status': 'healthy', 'connections': [{}]}]})
    monkeypatch.setattr(cloudflare_service, 'fetch_tunnel_ingress',
                        lambda c, t: {'success': True, 'ingress': [
                            {'hostname': 'autre.exemple.fr',
                             'service': 'http://localhost:9000'}]})

    etapes = tunnel_service.diagnostiquer_hote(regle)

    assert _verdict(etapes, 'Connecteur')['etat'] == 'ok'
    route = _verdict(etapes, 'Route distante')
    assert route['etat'] == 'erreur'
    assert 'Publier' in route['action']
    # Les noms REELLEMENT publies sont cites : sans eux on ne sait pas si
    # l'on s'est trompe de tunnel ou de nom d'hote.
    assert 'autre.exemple.fr' in route['detail']


@pytest.mark.django_db
def test_un_connecteur_absent_est_distingue_de_la_route(regle, monkeypatch):
    """L'AUTRE CAUSE. « cloudflared actif » sur la machine ne prouve pas que
    le processus parle a CE tunnel : on demande son avis a Cloudflare."""
    from apps.websites import cloudflare_service

    monkeypatch.setattr(cloudflare_service, 'fetch_cf_tunnels',
                        lambda c: {'success': True, 'tunnels': [
                            {'id': regle.tunnel.tunnel_id, 'name': 'T',
                             'status': 'down', 'connections': []}]})
    monkeypatch.setattr(cloudflare_service, 'fetch_tunnel_ingress',
                        lambda c, t: {'success': True, 'ingress': [
                            {'hostname': regle.hostname,
                             'service': 'http://localhost:9000'}]})

    etapes = tunnel_service.diagnostiquer_hote(regle)

    assert _verdict(etapes, 'Connecteur')['etat'] == 'erreur'
    assert _verdict(etapes, 'Route distante')['etat'] == 'ok'


@pytest.mark.django_db
def test_toutes_les_etapes_sont_evaluees_malgre_un_echec(regle, monkeypatch):
    """Un diagnostic qui s'arrete au premier defaut oblige a autant
    d'allers-retours qu'il y a de defauts."""
    from apps.websites import cloudflare_service

    monkeypatch.setattr(cloudflare_service, 'fetch_cf_tunnels',
                        lambda c: {'success': False, 'tunnels': [],
                                   'error': 'jeton invalide'})
    monkeypatch.setattr(cloudflare_service, 'fetch_tunnel_ingress',
                        lambda c, t: {'success': False, 'ingress': [],
                                      'error': 'illisible'})

    etapes = tunnel_service.diagnostiquer_hote(regle)

    noms = {e['nom'] for e in etapes}
    assert {'Connecteur', 'Route distante', 'Service local'} <= noms


@pytest.mark.django_db
def test_un_port_de_frontend_est_signale(regle, monkeypatch):
    """Le piege rencontre : une vitrine est rendue par DJANGO, et Django
    n'ecoute pas sur les ports des frontends compiles."""
    from apps.core.models import Company
    from apps.websites import cloudflare_service
    from apps.websites.models import Website

    site = Website.objects.create(
        company=regle.tunnel.company, name='Sparkling Peace', slug='sp')
    regle.website = site
    regle.service = 'http://localhost:5172'
    regle.save()

    monkeypatch.setattr(cloudflare_service, 'fetch_cf_tunnels',
                        lambda c: {'success': True, 'tunnels': []})
    monkeypatch.setattr(cloudflare_service, 'fetch_tunnel_ingress',
                        lambda c, t: {'success': True, 'ingress': []})

    etapes = tunnel_service.diagnostiquer_hote(regle)
    service = _verdict(etapes, 'Service local')

    assert service['etat'] == 'attention'
    assert '9000' in service['action']


@pytest.mark.django_db
def test_un_domaine_absent_de_l_ERP_est_signale(regle, monkeypatch):
    """Sans WebsiteDomain actif, Django repond 400 : le tunnel aurait beau
    fonctionner, la page serait une erreur."""
    from apps.websites import cloudflare_service

    monkeypatch.setattr(cloudflare_service, 'fetch_cf_tunnels',
                        lambda c: {'success': True, 'tunnels': []})
    monkeypatch.setattr(cloudflare_service, 'fetch_tunnel_ingress',
                        lambda c, t: {'success': True, 'ingress': []})

    etapes = tunnel_service.diagnostiquer_hote(regle)

    assert _verdict(etapes, 'Domaine dans l’ERP')['etat'] == 'erreur'


def test_les_actions_restent_visibles_une_fois_le_dns_synchronise():
    """LE DEFAUT RAPPORTE : « je n'ai pas de bouton diagnostic ».

    « Remplacer » et « Diagnostic » etaient places dans la branche
    « {% else %} » de « {% if rule.dns_synced %} ». Des que la
    synchronisation avait reussi, ils disparaissaient — c'est-a-dire
    PRECISEMENT quand on en a besoin : un CNAME pose ne garantit ni que le
    connecteur tourne, ni que la route est publiee, ni que le CNAME vise le
    bon tunnel.

    Le cas reel : un CNAME correct vers un tunnel sans connecteur. Le badge
    affichait « Sync », le site repondait 1033, et le bouton qui l'aurait
    explique etait cache.

    Le test lit la STRUCTURE du gabarit : le lien de diagnostic doit se
    trouver APRES la fermeture du bloc conditionnel.
    """
    from pathlib import Path

    gabarit = Path('templates/websites/tunnel/tunnel_detail.html').read_text(
        encoding='utf-8')

    debut = gabarit.index('{% if rule.dns_synced %}')
    fin = gabarit.index('{% endif %}', debut)
    conditionnel = gabarit[debut:fin]

    assert 'ingress_diagnostic' not in conditionnel, (
        'le bouton Diagnostic est cache des que le DNS est synchronise')
    assert 'name="remplacer"' not in conditionnel, (
        'le bouton Remplacer est cache des que le DNS est synchronise')
    # Et ils doivent bien exister quelque part.
    assert 'ingress_diagnostic' in gabarit
    assert 'name="remplacer" value="1"' in gabarit
