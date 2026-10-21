"""
apps/websites/cloudflare_service.py — Service de connexion Cloudflare pour Orion ERP

Fonctions pour :
- Tester un token API Cloudflare
- Récupérer les infos du compte
- Lister les zones (domaines)
- Vérifier les permissions du token
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models_domains import CloudflareAccount

CF_BASE = 'https://api.cloudflare.com/client/v4'


def _headers(api_token: str) -> dict:
    # .strip() : un jeton copié depuis le dashboard arrive souvent avec une
    # espace ou un retour à la ligne, qui rend l'en-tête Authorization
    # invalide et fait répondre « Token invalide » sans autre explication.
    return {
        'Authorization': f'Bearer {(api_token or "").strip()}',
        'Content-Type': 'application/json',
    }


def _diagnostic_forme_jeton(api_token: str) -> str:
    """Message d'erreur quand le jeton n'a visiblement pas la bonne forme.

    Cloudflare expose deux objets très différents, souvent confondus :
    un JETON D'API (My Profile > API Tokens, ~40 caractères) qui pilote
    l'API, et un JETON DE CONNECTEUR (Zero Trust > Tunnels > Install,
    plus de 150 caractères) qui sert uniquement à lancer cloudflared.
    Seul le premier est attendu ici ; le second échoue sur
    /user/tokens/verify avec un message incompréhensible.

    Retourne '' si la forme est plausible.
    """
    jeton = (api_token or '').strip()
    if not jeton:
        return 'Jeton vide.'
    if len(jeton) > 100:
        return (f'Ce jeton fait {len(jeton)} caractères : il s\'agit probablement d\'un '
                'JETON DE CONNECTEUR (Zero Trust > Tunnels > Install connector), '
                'et non d\'un JETON D\'API. Celui attendu ici se crée dans '
                'Mon profil > Jetons d\'API et fait une quarantaine de caractères.')
    if len(jeton) < 20:
        return (f'Jeton trop court ({len(jeton)} caractères) : copie probablement '
                'incomplète.')
    return ''


def test_token(api_token: str) -> dict:
    """
    Vérifie qu'un token API Cloudflare est valide et retourne les infos associées.
    Retourne : {success, account_id, email, account_name, error}
    """
    # Un jeton vide ne vaut pas un appel réseau. Les autres anomalies de forme
    # ne BLOQUENT pas : elles servent d'indice ajouté au message si le test
    # fonctionnel échoue aussi. Rejeter sur la seule apparence reproduirait le
    # bug corrigé ici — refuser un jeton qui fonctionne.
    indice_forme = _diagnostic_forme_jeton(api_token)
    if not (api_token or '').strip():
        return {'success': False, 'error': indice_forme or 'Jeton vide.'}

    try:
        import requests
        r = requests.get(f'{CF_BASE}/user/tokens/verify', headers=_headers(api_token), timeout=10)
        data = r.json()

        # /user/tokens/verify ne connaît que les jetons d'UTILISATEUR (Mon
        # profil > Jetons d'API). Un jeton de COMPTE (Gérer le compte >
        # Jetons d'API) y répond 401 « Invalid API Token » alors qu'il
        # fonctionne parfaitement sur les endpoints réels. Constaté en
        # production : /zones et /accounts répondaient 200 avec des résultats,
        # pendant que /verify refusait le même jeton — et l'ERP le rejetait
        # donc à l'enregistrement. On valide désormais sur ce que le jeton
        # FAIT, et non sur un seul endpoint de vérification.
        account_info = _get_account_info(api_token)

        if data.get('success'):
            return {
                'success': True,
                'token_status': data.get('result', {}).get('status', 'active'),
                **account_info,
            }

        if account_info.get('account_id'):
            return {
                'success': True,
                'token_status': 'account-scoped',
                **account_info,
            }

        errors = data.get('errors', [])
        msg = errors[0].get('message', 'Token invalide') if errors else 'Token invalide'
        # Le jeton echoue a la fois a la verification ET a la lecture des
        # comptes : la cause est donc reelle.
        if indice_forme:
            # Forme suspecte ET inopérant : l'indice devient l'explication la
            # plus probable (jeton de connecteur collé à la place, copie
            # tronquée).
            msg += f' — {indice_forme}'
        elif 'invalid' in msg.lower():
            msg += (" — le jeton ne permet ni de se vérifier ni de lire un compte. "
                    "Vérifiez qu'il est copié en entier, non révoqué, et qu'il porte "
                    "au moins une permission avec la ressource correspondante "
                    "sélectionnée (Account Resources ou Zone Resources).")
        return {'success': False, 'error': msg}
    except ImportError:
        return {'success': False, 'error': "Le package 'requests' n'est pas installé."}
    except Exception as exc:
        return {'success': False, 'error': f'Erreur réseau : {exc}'}


def _get_account_info(api_token: str) -> dict:
    """Récupère account_id, email, account_name depuis l'API Cloudflare."""
    try:
        import requests
        r = requests.get(f'{CF_BASE}/accounts', headers=_headers(api_token), timeout=10)
        data = r.json()
        if data.get('success') and data.get('result'):
            acc = data['result'][0]
            return {
                'account_id': acc.get('id', ''),
                'account_name': acc.get('name', ''),
            }
    except Exception:
        pass
    return {'account_id': '', 'account_name': ''}


def get_zones(api_token: str, page: int = 1) -> dict:
    """
    Retourne les zones (domaines) accessibles avec ce token.
    Retourne : {success, zones: [...], total, error}
    """
    try:
        import requests
        r = requests.get(
            f'{CF_BASE}/zones',
            params={'page': page, 'per_page': 50},
            headers=_headers(api_token),
            timeout=10,
        )
        data = r.json()
        if data.get('success'):
            return {
                'success': True,
                'zones': data.get('result', []),
                'total': data.get('result_info', {}).get('total_count', 0),
            }
        errors = data.get('errors', [])
        msg = errors[0].get('message', 'Erreur') if errors else 'Erreur'
        return {'success': False, 'zones': [], 'total': 0, 'error': msg}
    except Exception as exc:
        return {'success': False, 'zones': [], 'total': 0, 'error': str(exc)}


def get_token_permissions(api_token: str) -> list[dict]:
    """Récupère les permissions attachées au token."""
    try:
        import requests
        r = requests.get(f'{CF_BASE}/user/tokens', headers=_headers(api_token), timeout=10)
        data = r.json()
        if data.get('success') and data.get('result'):
            tokens = data['result']
            for token in tokens:
                if token.get('status') == 'active':
                    return token.get('policies', [])
    except Exception:
        pass
    return []


def fetch_cf_tunnels(account: "CloudflareAccount") -> dict:
    """
    Récupère les Named Tunnels depuis l'API Cloudflare pour un compte donné.
    Nécessite account.account_id.
    Retourne: {success, tunnels: [{id, name, status, ...}], error}
    """
    if not account.account_id:
        return {'success': False, 'tunnels': [], 'error': "account_id manquant — testez d'abord la connexion."}
    try:
        import requests
        r = requests.get(
            f'{CF_BASE}/accounts/{account.account_id}/cfd_tunnel',
            params={'is_deleted': 'false', 'per_page': 50},
            headers=_headers(account.api_token),
            timeout=10,
        )
        data = r.json()
        if data.get('success'):
            return {'success': True, 'tunnels': data.get('result', [])}
        errors = data.get('errors', [])
        msg = errors[0].get('message', 'Erreur') if errors else 'Erreur'
        return {'success': False, 'tunnels': [], 'error': msg}
    except Exception as exc:
        return {'success': False, 'tunnels': [], 'error': str(exc)}


def fetch_tunnel_token(account: "CloudflareAccount", tunnel_id: str) -> dict:
    """
    Récupère le jeton de connecteur d'un Named Tunnel.

    C'est la seule donnée de l'API qui permette de FAIRE TOURNER un tunnel :
    lister les tunnels (fetch_cf_tunnels) et lire leur ingress
    (fetch_tunnel_ingress) renseigne l'ERP mais ne démarre rien. Sans ce jeton
    — ou sans le fichier de credentials produit par « cloudflared tunnel
    create » sur la machine d'origine — aucun connecteur ne peut se lancer,
    d'où l'impression trompeuse qu'un compte Cloudflare connecté suffit.

    Le jeton d'API du compte doit porter la permission
    « Cloudflare Tunnel: Edit » ; en lecture seule, Cloudflare refuse cet
    endpoint.

    Retourne: {success, token, error}
    """
    if not account.account_id:
        return {'success': False, 'token': '', 'error': "account_id manquant — testez d'abord la connexion."}
    if not tunnel_id:
        return {'success': False, 'token': '', 'error': 'ID de tunnel manquant.'}
    try:
        import requests
        r = requests.get(
            f'{CF_BASE}/accounts/{account.account_id}/cfd_tunnel/{tunnel_id}/token',
            headers=_headers(account.api_token),
            timeout=10,
        )
        data = r.json()
        if data.get('success'):
            token = data.get('result') or ''
            if not token:
                return {'success': False, 'token': '', 'error': 'Réponse de l\'API sans jeton.'}
            return {'success': True, 'token': token}
        errors = data.get('errors', [])
        msg = errors[0].get('message', 'Erreur') if errors else 'Erreur'
        return {'success': False, 'token': '', 'error': msg}
    except Exception as exc:
        return {'success': False, 'token': '', 'error': str(exc)}


def fetch_tunnel_ingress(account: "CloudflareAccount", tunnel_id: str) -> dict:
    """
    Récupère les règles d'ingress d'un Named Tunnel depuis l'API Cloudflare.
    Retourne: {success, ingress: [{hostname, service}], error}
    """
    try:
        import requests
        r = requests.get(
            f'{CF_BASE}/accounts/{account.account_id}/cfd_tunnel/{tunnel_id}/configurations',
            headers=_headers(account.api_token),
            timeout=10,
        )
        data = r.json()
        if data.get('success'):
            config = data.get('result', {}).get('config', {})
            ingress = [
                {'hostname': item.get('hostname', ''), 'service': item.get('service', '')}
                for item in config.get('ingress', [])
                if item.get('hostname')  # ignore le catch-all sans hostname
            ]
            return {'success': True, 'ingress': ingress}
        return {'success': False, 'ingress': [], 'error': 'Config ingress introuvable via API.'}
    except Exception as exc:
        return {'success': False, 'ingress': [], 'error': str(exc)}


def lire_configuration(account: "CloudflareAccount", tunnel_id: str) -> dict:
    """Lit la configuration distante BRUTE d'un tunnel, sans rien filtrer.

    Distincte de fetch_tunnel_ingress(), qui ne retourne que les couples
    hostname/service pour l'affichage et JETTE tout le reste : le catch-all
    final (entree sans hostname), les eventuels « path », et les blocs
    « originRequest » (noTLSVerify, httpHostHeader, timeouts...). Publier
    une configuration reconstruite a partir de cette sortie filtree
    DETRUIRAIT ces reglages. Toute ecriture doit donc partir d'ici.

    Retourne {success, config, source, error}.

    config est le dictionnaire tel que Cloudflare le renvoie, ou {} quand le
    tunnel n'a jamais eu de configuration distante -- cas legitime, a
    distinguer d'un echec : seul success permet de trancher, et seul
    success=True autorise une ecriture.

    source vaut 'cloudflare' (configuration distante, celle que le
    connecteur lance par jeton applique) ou 'local' (le connecteur lit son
    propre config.yml et ignorera ce qu'on ecrit ici).
    """
    if not account.account_id:
        return {'success': False, 'config': {}, 'source': '',
                'error': "account_id manquant — testez d'abord la connexion."}
    if not tunnel_id:
        return {'success': False, 'config': {}, 'source': '',
                'error': 'ID de tunnel manquant.'}
    try:
        import requests
        r = requests.get(
            f'{CF_BASE}/accounts/{account.account_id}/cfd_tunnel/{tunnel_id}/configurations',
            headers=_headers(account.api_token),
            timeout=15,
        )
        data = r.json()
        if not data.get('success'):
            errors = data.get('errors', [])
            msg = errors[0].get('message', 'Erreur') if errors else 'Erreur'
            if r.status_code in (403, 9109):
                msg = (f'{msg} — le jeton d\'API doit porter la permission '
                       '« Account > Cloudflare Tunnel > Edit ».')
            return {'success': False, 'config': {}, 'source': '', 'error': msg}

        # result peut etre None : tunnel existant jamais configure a distance.
        resultat = data.get('result') or {}
        config = resultat.get('config')
        if not isinstance(config, dict):
            config = {}
        return {'success': True, 'config': config,
                'source': resultat.get('source', '') or '', 'error': ''}
    except Exception as exc:
        return {'success': False, 'config': {}, 'source': '', 'error': str(exc)}


def _normaliser_hostname(valeur: str) -> str:
    """Forme comparable d'un nom d'hote.

    Sans cela « NS.Elysiums.fr », « ns.elysiums.fr. » et
    « https://ns.elysiums.fr » seraient vus comme trois hotes differents, et
    publier l'un creerait un doublon au lieu de modifier l'autre. Cloudflare
    accepterait les deux entrees ; seule la premiere servirait, et le
    changement paraitrait sans effet.
    """
    hote = (valeur or '').strip().lower()
    for prefixe in ('https://', 'http://'):
        if hote.startswith(prefixe):
            hote = hote[len(prefixe):]
    return hote.rstrip('/').rstrip('.')


def fusionner_ingress(config: dict, regles: list[dict]) -> dict:
    """Fusionne des regles dans une configuration existante. Sans reseau.

    Fonction pure, et c'est voulu : c'est la piece qui decide ce qui sera
    ecrit, donc celle qui doit etre verifiable sans toucher a Cloudflare.

    Trois garanties, dans cet ordre d'importance :

    1. AUCUN hostname existant n'est supprime. Un PUT remplace la
       configuration entiere ; ecrire la seule regle que l'on veut ajouter
       effacerait les autres -- ici, login.elysiums.fr, c'est-a-dire l'acces
       a l'ERP lui-meme. La fusion part donc toujours de l'existant.
    2. Le catch-all reste en DERNIER. Cloudflare exige une regle finale sans
       hostname ; placee avant les autres, elle les rendrait toutes mortes
       puisque le routage s'arrete a la premiere correspondance.
    3. Les clefs qu'on ne gere pas sont recopiees telles quelles -- les clefs
       de tete (warp-routing...) comme celles de chaque entree (path,
       originRequest).

    Retourne {config, ajouts, modifications, inchangees, conserves}.
    """
    import copy

    base = copy.deepcopy(config) if isinstance(config, dict) else {}
    entrees = base.get('ingress')
    if not isinstance(entrees, list):
        entrees = []

    nommees = [e for e in entrees if isinstance(e, dict) and e.get('hostname')]
    # On garde le premier catch-all rencontre. S'il y en avait plusieurs, les
    # suivants etaient de toute facon inatteignables.
    catch_all = next(
        (e for e in entrees if isinstance(e, dict) and not e.get('hostname')),
        None,
    )

    ajouts, modifications, inchangees = [], [], []

    for regle in regles:
        hote = _normaliser_hostname(regle.get('hostname', ''))
        service = (regle.get('service') or '').strip()
        if not hote or not service:
            continue

        # Une entree porteuse d'un « path » ne vise qu'une partie du site :
        # lui changer son service detournerait une regle qui ne nous
        # concerne pas. On ne modifie donc que l'entree generale de cet
        # hote, et a defaut on en ajoute une -- apres les entrees a path,
        # qui doivent rester prioritaires.
        cible = next(
            (e for e in nommees
             if _normaliser_hostname(e.get('hostname', '')) == hote
             and not e.get('path')),
            None,
        )

        if cible is None:
            nommees.append({'hostname': hote, 'service': service})
            ajouts.append({'hostname': hote, 'service': service})
        elif (cible.get('service') or '') == service:
            inchangees.append({'hostname': hote, 'service': service})
        else:
            modifications.append({
                'hostname': hote,
                'avant': cible.get('service') or '',
                'apres': service,
            })
            cible['service'] = service

    demandes = {_normaliser_hostname(r.get('hostname', '')) for r in regles}
    conserves = [
        {'hostname': e.get('hostname', ''), 'service': e.get('service') or ''}
        for e in nommees
        if _normaliser_hostname(e.get('hostname', '')) not in demandes
    ]

    if catch_all is None:
        catch_all = {'service': 'http_status:404'}
    base['ingress'] = nommees + [catch_all]

    return {
        'config': base,
        'ajouts': ajouts,
        'modifications': modifications,
        'inchangees': inchangees,
        'conserves': conserves,
    }


def publier_ingress(account: "CloudflareAccount", tunnel_id: str,
                    regles: list[dict], a_blanc: bool = False) -> dict:
    """Publie des regles d'ingress dans la configuration DISTANTE du tunnel.

    C'est la piece qui manquait. L'ERP savait deja ecrire un config.yml
    local et synchroniser le DNS ; mais un connecteur lance par jeton
    (« cloudflared tunnel run --token-file ») applique la configuration
    DISTANTE de Cloudflare et ignore totalement ce config.yml. Les noms
    d'hote renvoyaient donc une erreur 1033 : le DNS pointait vers le
    tunnel, et le tunnel ne savait pas quoi en faire.

    L'API n'offre pas d'ajout d'une regle : seulement le remplacement de la
    configuration entiere (PUT .../configurations). D'ou la sequence
    lecture -> fusion -> ecriture, et le refus d'ecrire si la lecture a
    echoue : publier a l'aveugle effacerait les regles existantes, dont
    celle qui donne acces a l'ERP.

    a_blanc=True calcule et retourne tout sans rien ecrire.

    Retourne {success, error, a_blanc, source, avertissement, config,
              ajouts, modifications, inchangees, conserves}.
    """
    vide = {'ajouts': [], 'modifications': [], 'inchangees': [],
            'conserves': [], 'config': {}, 'source': '', 'avertissement': '',
            'a_blanc': a_blanc}

    if not regles:
        return {**vide, 'success': False,
                'error': 'Aucune règle à publier.'}

    lecture = lire_configuration(account, tunnel_id)
    if not lecture['success']:
        # Refus delibere. Le PUT remplace tout : sans l'etat actuel sous les
        # yeux, la seule ecriture possible serait destructrice.
        return {**vide, 'success': False, 'error': (
            f"Lecture de la configuration impossible : {lecture['error']} — "
            "rien n'a été écrit. La publication remplace la configuration "
            "entière du tunnel ; sans avoir pu lire les règles existantes, "
            "l'écriture les supprimerait, y compris celle qui donne accès "
            "à l'ERP.")}

    avant = lecture['config']
    fusion = fusionner_ingress(avant, regles)

    # Garde-fou : la fusion ne doit jamais faire disparaitre un hote. Ce
    # controle ne protege pas d'une erreur de l'API mais d'une erreur de
    # notre code, dont la consequence serait la meme.
    def _hotes(cfg):
        entrees = cfg.get('ingress') if isinstance(cfg, dict) else None
        return {_normaliser_hostname(e.get('hostname', ''))
                for e in (entrees or []) if isinstance(e, dict) and e.get('hostname')}

    perdus = _hotes(avant) - _hotes(fusion['config'])
    if perdus:
        return {**vide, 'success': False, 'error': (
            'Publication annulée : la fusion aurait supprimé '
            f'{", ".join(sorted(perdus))}. Rien n\'a été écrit.')}

    avertissement = ''
    if lecture['source'] == 'local':
        avertissement = (
            "Ce tunnel est en configuration LOCALE : son connecteur lit son "
            "propre config.yml. La configuration écrite ici est enregistrée "
            "chez Cloudflare mais ne sera pas appliquée tant que le "
            "connecteur n'est pas lancé par jeton "
            "(cloudflared tunnel run --token-file).")

    resultat = {
        'success': True, 'error': '', 'a_blanc': a_blanc,
        'source': lecture['source'], 'avertissement': avertissement,
        'config': fusion['config'],
        'ajouts': fusion['ajouts'],
        'modifications': fusion['modifications'],
        'inchangees': fusion['inchangees'],
        'conserves': fusion['conserves'],
    }

    if a_blanc:
        return resultat

    if not fusion['ajouts'] and not fusion['modifications']:
        # Rien a changer : on n'ecrit pas. Un PUT inutile reste un PUT, et
        # chaque ecriture est une occasion de casser une configuration qui
        # fonctionne.
        return resultat

    try:
        import requests
        r = requests.put(
            f'{CF_BASE}/accounts/{account.account_id}/cfd_tunnel/{tunnel_id}/configurations',
            headers=_headers(account.api_token),
            json={'config': fusion['config']},
            timeout=20,
        )
        data = r.json()
        if data.get('success'):
            return resultat
        errors = data.get('errors', [])
        msg = errors[0].get('message', 'Erreur') if errors else 'Erreur'
        if r.status_code == 403:
            msg = (f'{msg} — le jeton d\'API doit porter la permission '
                   '« Account > Cloudflare Tunnel > Edit ». En lecture seule, '
                   'Cloudflare refuse cette écriture.')
        return {**vide, 'success': False,
                'error': f'Cloudflare a refusé l\'écriture : {msg}'}
    except Exception as exc:
        return {**vide, 'success': False,
                'error': f'Écriture impossible : {exc}'}


def refresh_account(account: "CloudflareAccount") -> dict:
    """
    Teste la connexion d'un compte CloudflareAccount enregistré et met à jour
    account_id + email si nécessaire.
    Retourne {success, zones_count, error}.
    """
    result = test_token(account.api_token)
    if not result['success']:
        return result

    changed = False
    if result.get('account_id') and not account.account_id:
        account.account_id = result['account_id']
        changed = True

    if changed:
        account.save(update_fields=[f for f in ['account_id', 'email'] if changed])

    zones_result = get_zones(account.api_token)
    return {
        'success': True,
        'account_name': result.get('account_name', ''),
        'zones_count': zones_result.get('total', 0),
        'zones': zones_result.get('zones', []),
    }
