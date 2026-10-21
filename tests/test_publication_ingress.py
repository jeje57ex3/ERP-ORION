"""Publication de l'ingress d'un tunnel dans la configuration Cloudflare.

Ce fichier existe pour une raison précise. L'API Cloudflare n'offre aucun
moyen d'**ajouter** une règle d'ingress : seulement de remplacer la
configuration entière du tunnel (`PUT .../configurations`). La fonction
testée ici est donc, par construction, capable de détruire la route
`login.elysiums.fr` — celle par laquelle passe l'accès à l'ERP lui-même.

Trois propriétés, par ordre de gravité décroissante :

**Aucun nom d'hôte existant n'est supprimé.** La fusion part toujours de
l'existant lu chez Cloudflare, y compris les hôtes dont l'ERP n'a jamais
entendu parler.

**Une lecture échouée interdit l'écriture.** Si l'on ne sait pas ce qui est
en place, la seule écriture possible est destructrice. On refuse.

**Le catch-all reste en dernier.** Le routage s'arrête à la première
correspondance : une règle sans hostname placée en tête rendrait toutes les
autres mortes, et le tunnel répondrait 404 partout.

Aucun test n'a besoin de la base : `fusionner_ingress` est une fonction pure
et `publier_ingress` ne reçoit qu'un objet porteur d'un `account_id` et d'un
`api_token`. C'est ce qui rend la pièce dangereuse entièrement vérifiable.
"""

import pytest

from apps.websites.cloudflare_service import (
    fusionner_ingress,
    lire_configuration,
    publier_ingress,
    _normaliser_hostname,
)


# ── Terrain ─────────────────────────────────────────────────────────────────

class CompteFactice:
    """Le strict minimum que publier_ingress lit sur un CloudflareAccount."""

    def __init__(self, account_id='cpt-1', api_token='jeton-de-test'):
        self.account_id = account_id
        self.api_token = api_token


class ReponseFactice:
    def __init__(self, charge, status_code=200):
        self._charge = charge
        self.status_code = status_code

    def json(self):
        return self._charge


@pytest.fixture
def compte():
    return CompteFactice()


# La configuration réelle de l'utilisateur, réduite à l'essentiel : l'accès
# à l'ERP, et le catch-all obligatoire.
CONFIG_REELLE = {
    'ingress': [
        {'hostname': 'login.elysiums.fr', 'service': 'http://localhost:9000'},
        {'hostname': 'orion.elysiums.fr', 'service': 'http://localhost:9000'},
        {'service': 'http_status:404'},
    ],
    'warp-routing': {'enabled': False},
}


@pytest.fixture
def reseau(monkeypatch):
    """Intercepte requests.get / requests.put et enregistre les appels.

    Le module importe `requests` dans le corps de chaque fonction ; on
    remplace donc les attributs du module `requests` lui-même.
    """
    import requests

    journal = {'get': [], 'put': []}
    etat = {
        'config': CONFIG_REELLE,
        'source': 'cloudflare',
        'get_ok': True,
        'put_ok': True,
        'put_status': 200,
    }

    def faux_get(url, **kwargs):
        journal['get'].append({'url': url, 'kwargs': kwargs})
        if not etat['get_ok']:
            return ReponseFactice(
                {'success': False,
                 'errors': [{'message': 'Authentication error'}]},
                status_code=403,
            )
        return ReponseFactice({
            'success': True,
            'result': {'config': etat['config'], 'source': etat['source']},
        })

    def faux_put(url, **kwargs):
        journal['put'].append({'url': url, 'kwargs': kwargs})
        if not etat['put_ok']:
            return ReponseFactice(
                {'success': False, 'errors': [{'message': 'Forbidden'}]},
                status_code=etat['put_status'],
            )
        return ReponseFactice({'success': True, 'result': {}})

    monkeypatch.setattr(requests, 'get', faux_get)
    monkeypatch.setattr(requests, 'put', faux_put)
    return {'journal': journal, 'etat': etat}


def hotes(config):
    return [e['hostname'] for e in config['ingress'] if e.get('hostname')]


# ── 1. Ce qui existe n'est jamais supprimé ──────────────────────────────────

def test_publier_un_nouvel_hote_conserve_les_anciens():
    """La propriété qui justifie tout le reste.

    Un PUT construit à partir de la seule règle voulue aurait effacé
    login.elysiums.fr, donc l'accès à l'ERP. C'est le défaut que cette
    fonction est faite pour rendre impossible.
    """
    fusion = fusionner_ingress(
        CONFIG_REELLE,
        [{'hostname': 'ns.elysiums.fr', 'service': 'http://localhost:80'}],
    )
    assert hotes(fusion['config']) == [
        'login.elysiums.fr', 'orion.elysiums.fr', 'ns.elysiums.fr',
    ]


def test_les_hotes_conserves_sont_nommes():
    """Le rapport dit lesquels ont survécu, pas seulement combien.

    Sans cette liste, l'utilisateur n'aurait aucun moyen de vérifier avant
    de cliquer que sa propre route d'accès figure bien dans ce qui sera
    écrit.
    """
    fusion = fusionner_ingress(
        CONFIG_REELLE,
        [{'hostname': 'ns.elysiums.fr', 'service': 'http://localhost:80'}],
    )
    noms = [item['hostname'] for item in fusion['conserves']]
    assert noms == ['login.elysiums.fr', 'orion.elysiums.fr']


def test_un_hote_inconnu_de_l_erp_survit():
    """L'ERP ne connaît pas forcément tout le compte Cloudflare.

    Un nom d'hôte déclaré à la main dans le tableau de bord, ou par un
    autre serveur partageant le tunnel, doit traverser la publication
    intact.
    """
    depart = {'ingress': [
        {'hostname': 'vpn.exemple.fr', 'service': 'ssh://localhost:22'},
        {'service': 'http_status:404'},
    ]}
    fusion = fusionner_ingress(
        depart, [{'hostname': 'ns.elysiums.fr', 'service': 'http://localhost:80'}])
    assert 'vpn.exemple.fr' in hotes(fusion['config'])


def test_les_reglages_fins_d_une_entree_intacte_sont_recopies():
    """originRequest porte noTLSVerify, httpHostHeader, les délais…

    fetch_tunnel_ingress() ne retourne que hostname et service : publier à
    partir de sa sortie aurait silencieusement effacé ces réglages, et
    l'origine aurait cessé de répondre sans que rien ne l'explique.
    """
    depart = {'ingress': [
        {'hostname': 'interne.exemple.fr',
         'service': 'https://localhost:8443',
         'originRequest': {'noTLSVerify': True, 'connectTimeout': 30}},
        {'service': 'http_status:404'},
    ]}
    fusion = fusionner_ingress(
        depart, [{'hostname': 'ns.elysiums.fr', 'service': 'http://localhost:80'}])
    entree = fusion['config']['ingress'][0]
    assert entree['originRequest'] == {'noTLSVerify': True, 'connectTimeout': 30}


def test_les_clefs_de_tete_sont_recopiees():
    """warp-routing et consorts ne sont pas de l'ingress, et restent."""
    fusion = fusionner_ingress(
        CONFIG_REELLE,
        [{'hostname': 'ns.elysiums.fr', 'service': 'http://localhost:80'}])
    assert fusion['config']['warp-routing'] == {'enabled': False}


# ── 2. Le catch-all ─────────────────────────────────────────────────────────

def test_le_catch_all_reste_en_dernier():
    """Le routage s'arrête à la première correspondance.

    Un catch-all remonté avant les règles nommées les rendrait toutes
    inatteignables : le tunnel répondrait 404 sur tous les domaines, y
    compris ceux qui marchaient avant.
    """
    fusion = fusionner_ingress(
        CONFIG_REELLE,
        [{'hostname': 'ns.elysiums.fr', 'service': 'http://localhost:80'}])
    derniere = fusion['config']['ingress'][-1]
    assert 'hostname' not in derniere
    assert derniere['service'] == 'http_status:404'


def test_le_catch_all_est_cree_s_il_manque():
    """Cloudflare refuse une configuration sans règle finale."""
    depart = {'ingress': [
        {'hostname': 'login.elysiums.fr', 'service': 'http://localhost:9000'},
    ]}
    fusion = fusionner_ingress(
        depart, [{'hostname': 'ns.elysiums.fr', 'service': 'http://localhost:80'}])
    assert fusion['config']['ingress'][-1] == {'service': 'http_status:404'}


def test_le_catch_all_existant_est_preserve_tel_quel():
    """Un catch-all personnalisé n'est pas remplacé par le 404 par défaut."""
    depart = {'ingress': [
        {'hostname': 'login.elysiums.fr', 'service': 'http://localhost:9000'},
        {'service': 'http://localhost:9000'},
    ]}
    fusion = fusionner_ingress(
        depart, [{'hostname': 'ns.elysiums.fr', 'service': 'http://localhost:80'}])
    assert fusion['config']['ingress'][-1] == {'service': 'http://localhost:9000'}


def test_configuration_vide_ou_absente():
    """Un tunnel jamais configuré à distance renvoie result: null.

    Cas légitime, à ne pas confondre avec un échec : la publication doit
    partir de zéro et produire une configuration valide.
    """
    for depart in ({}, {'ingress': []}, {'ingress': None}):
        fusion = fusionner_ingress(
            depart, [{'hostname': 'ns.elysiums.fr', 'service': 'http://localhost:80'}])
        assert fusion['config']['ingress'] == [
            {'hostname': 'ns.elysiums.fr', 'service': 'http://localhost:80'},
            {'service': 'http_status:404'},
        ]


# ── 3. Modification plutôt que doublon ──────────────────────────────────────

def test_un_hote_deja_present_est_modifie_sans_doublon():
    """Deux entrées pour le même hôte : seule la première servirait.

    Le changement paraîtrait sans effet, et la cause serait invisible dans
    le tableau de bord, où les deux lignes s'affichent côte à côte.
    """
    fusion = fusionner_ingress(
        CONFIG_REELLE,
        [{'hostname': 'login.elysiums.fr', 'service': 'http://localhost:8000'}])
    assert hotes(fusion['config']).count('login.elysiums.fr') == 1
    assert fusion['config']['ingress'][0]['service'] == 'http://localhost:8000'
    assert fusion['modifications'] == [{
        'hostname': 'login.elysiums.fr',
        'avant': 'http://localhost:9000',
        'apres': 'http://localhost:8000',
    }]


def test_un_service_identique_est_signale_inchange():
    """Rien à écrire : la publication ne doit pas se croire utile."""
    fusion = fusionner_ingress(
        CONFIG_REELLE,
        [{'hostname': 'login.elysiums.fr', 'service': 'http://localhost:9000'}])
    assert fusion['modifications'] == []
    assert fusion['inchangees'] == [
        {'hostname': 'login.elysiums.fr', 'service': 'http://localhost:9000'}]


@pytest.mark.parametrize('ecriture', [
    'NS.Elysiums.FR', 'ns.elysiums.fr.', 'https://ns.elysiums.fr',
    '  ns.elysiums.fr  ',
])
def test_les_variantes_d_ecriture_visent_la_meme_entree(ecriture):
    """Sinon on créerait un doublon au lieu de modifier l'existant."""
    depart = {'ingress': [
        {'hostname': 'ns.elysiums.fr', 'service': 'http://localhost:9999'},
        {'service': 'http_status:404'},
    ]}
    fusion = fusionner_ingress(
        depart, [{'hostname': ecriture, 'service': 'http://localhost:80'}])
    assert hotes(fusion['config']) == ['ns.elysiums.fr']
    assert fusion['config']['ingress'][0]['service'] == 'http://localhost:80'


def test_une_entree_avec_path_n_est_pas_detournee():
    """Une règle « hostname + path » ne vise qu'une partie du site.

    Lui changer son service redirigerait un chemin précis vers une origine
    qui ne le sert pas. On ajoute donc une entrée générale, APRÈS elle —
    l'ordre importe, la règle à path doit rester prioritaire.
    """
    depart = {'ingress': [
        {'hostname': 'ns.elysiums.fr', 'path': '/api/*',
         'service': 'http://localhost:9000'},
        {'service': 'http_status:404'},
    ]}
    fusion = fusionner_ingress(
        depart, [{'hostname': 'ns.elysiums.fr', 'service': 'http://localhost:80'}])
    entrees = fusion['config']['ingress']
    assert entrees[0] == {'hostname': 'ns.elysiums.fr', 'path': '/api/*',
                          'service': 'http://localhost:9000'}
    assert entrees[1] == {'hostname': 'ns.elysiums.fr',
                          'service': 'http://localhost:80'}


def test_la_configuration_d_origine_n_est_pas_modifiee():
    """La fusion travaille sur une copie.

    Sans cela, l'aperçu modifierait l'objet lu et la comparaison
    « avant / après » comparerait deux fois l'après.
    """
    depart = {'ingress': [
        {'hostname': 'login.elysiums.fr', 'service': 'http://localhost:9000'},
        {'service': 'http_status:404'},
    ]}
    fusionner_ingress(
        depart, [{'hostname': 'login.elysiums.fr', 'service': 'http://autre:1'}])
    assert depart['ingress'][0]['service'] == 'http://localhost:9000'


def test_une_regle_incomplete_est_ignoree():
    """Un service vide écrirait une route morte."""
    fusion = fusionner_ingress(CONFIG_REELLE, [
        {'hostname': 'ns.elysiums.fr', 'service': ''},
        {'hostname': '', 'service': 'http://localhost:80'},
    ])
    assert fusion['ajouts'] == []
    assert hotes(fusion['config']) == ['login.elysiums.fr', 'orion.elysiums.fr']


@pytest.mark.parametrize('brut,attendu', [
    ('NS.Elysiums.FR', 'ns.elysiums.fr'),
    ('ns.elysiums.fr.', 'ns.elysiums.fr'),
    ('https://ns.elysiums.fr/', 'ns.elysiums.fr'),
    ('http://ns.elysiums.fr', 'ns.elysiums.fr'),
    ('', ''),
    (None, ''),
])
def test_normalisation(brut, attendu):
    assert _normaliser_hostname(brut) == attendu


# ── 4. Une lecture échouée interdit l'écriture ──────────────────────────────

def test_lecture_impossible_n_ecrit_rien(compte, reseau):
    """LE garde-fou.

    Sans lui, un jeton expiré ou une coupure réseau conduirait à publier
    une configuration construite à partir de rien — c'est-à-dire à effacer
    toutes les routes du compte.
    """
    reseau['etat']['get_ok'] = False
    rapport = publier_ingress(
        compte, 'uuid-1',
        [{'hostname': 'ns.elysiums.fr', 'service': 'http://localhost:80'}])
    assert rapport['success'] is False
    assert reseau['journal']['put'] == []
    assert 'supprimerait' in rapport['error']


def test_liste_de_regles_vide_refusee(compte, reseau):
    """Publier « rien » effacerait tout. On ne lit même pas."""
    rapport = publier_ingress(compte, 'uuid-1', [])
    assert rapport['success'] is False
    assert reseau['journal']['get'] == []
    assert reseau['journal']['put'] == []


def test_sans_account_id_rien_n_est_tente(reseau):
    rapport = lire_configuration(CompteFactice(account_id=''), 'uuid-1')
    assert rapport['success'] is False
    assert reseau['journal']['get'] == []


def test_le_403_nomme_la_permission_manquante(compte, reseau):
    """« Authentication error » seul n'aide personne.

    La permission à cocher est « Account > Cloudflare Tunnel > Edit » ;
    sans elle, Cloudflare refuse aussi bien la lecture que l'écriture.
    """
    reseau['etat']['get_ok'] = False
    rapport = lire_configuration(compte, 'uuid-1')
    assert 'Cloudflare Tunnel' in rapport['error']


# ── 5. L'écriture ───────────────────────────────────────────────────────────

def test_l_ecriture_envoie_la_configuration_fusionnee(compte, reseau):
    rapport = publier_ingress(
        compte, 'uuid-1',
        [{'hostname': 'ns.elysiums.fr', 'service': 'http://localhost:80'}])
    assert rapport['success'] is True
    assert len(reseau['journal']['put']) == 1

    envoye = reseau['journal']['put'][0]['kwargs']['json']['config']
    assert hotes(envoye) == [
        'login.elysiums.fr', 'orion.elysiums.fr', 'ns.elysiums.fr']
    assert envoye['ingress'][-1] == {'service': 'http_status:404'}


def test_l_ecriture_vise_le_bon_point_d_entree(compte, reseau):
    publier_ingress(
        compte, 'uuid-1',
        [{'hostname': 'ns.elysiums.fr', 'service': 'http://localhost:80'}])
    url = reseau['journal']['put'][0]['url']
    assert url.endswith('/accounts/cpt-1/cfd_tunnel/uuid-1/configurations')


def test_a_blanc_n_ecrit_pas(compte, reseau):
    """L'aperçu doit pouvoir être cliqué sans conséquence."""
    rapport = publier_ingress(
        compte, 'uuid-1',
        [{'hostname': 'ns.elysiums.fr', 'service': 'http://localhost:80'}],
        a_blanc=True)
    assert rapport['success'] is True
    assert rapport['a_blanc'] is True
    assert rapport['ajouts'] == [
        {'hostname': 'ns.elysiums.fr', 'service': 'http://localhost:80'}]
    assert reseau['journal']['put'] == []


def test_rien_a_changer_n_ecrit_pas(compte, reseau):
    """Chaque écriture est une occasion de casser ce qui marche."""
    rapport = publier_ingress(compte, 'uuid-1', [
        {'hostname': 'login.elysiums.fr', 'service': 'http://localhost:9000'},
        {'hostname': 'orion.elysiums.fr', 'service': 'http://localhost:9000'},
    ])
    assert rapport['success'] is True
    assert reseau['journal']['put'] == []


def test_un_refus_de_cloudflare_est_rapporte(compte, reseau):
    reseau['etat']['put_ok'] = False
    reseau['etat']['put_status'] = 403
    rapport = publier_ingress(
        compte, 'uuid-1',
        [{'hostname': 'ns.elysiums.fr', 'service': 'http://localhost:80'}])
    assert rapport['success'] is False
    assert 'Cloudflare Tunnel' in rapport['error']


def test_une_coupure_reseau_pendant_l_ecriture_est_rapportee(compte, reseau,
                                                            monkeypatch):
    import requests

    def put_qui_echoue(url, **kwargs):
        raise OSError('connexion interrompue')

    monkeypatch.setattr(requests, 'put', put_qui_echoue)
    rapport = publier_ingress(
        compte, 'uuid-1',
        [{'hostname': 'ns.elysiums.fr', 'service': 'http://localhost:80'}])
    assert rapport['success'] is False
    assert 'connexion interrompue' in rapport['error']


# ── 6. Configuration locale : écrire ne suffira pas ─────────────────────────

def test_un_tunnel_en_configuration_locale_est_signale(compte, reseau):
    """Le connecteur lit son propre config.yml et ignorera ce qu'on écrit.

    Sans cet avertissement, la publication réussirait, le site resterait en
    1033, et rien n'indiquerait pourquoi. On écrit quand même — la
    configuration sera appliquée dès que le connecteur passera au jeton.
    """
    reseau['etat']['source'] = 'local'
    rapport = publier_ingress(
        compte, 'uuid-1',
        [{'hostname': 'ns.elysiums.fr', 'service': 'http://localhost:80'}])
    assert rapport['success'] is True
    assert rapport['source'] == 'local'
    assert 'config.yml' in rapport['avertissement']
    assert len(reseau['journal']['put']) == 1


def test_un_tunnel_distant_ne_declenche_aucun_avertissement(compte, reseau):
    rapport = publier_ingress(
        compte, 'uuid-1',
        [{'hostname': 'ns.elysiums.fr', 'service': 'http://localhost:80'}],
        a_blanc=True)
    assert rapport['avertissement'] == ''
