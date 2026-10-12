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
