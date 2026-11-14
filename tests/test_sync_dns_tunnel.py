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
