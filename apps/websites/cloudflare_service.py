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
    return {'Authorization': f'Bearer {api_token}', 'Content-Type': 'application/json'}


def test_token(api_token: str) -> dict:
    """
    Vérifie qu'un token API Cloudflare est valide et retourne les infos associées.
    Retourne : {success, account_id, email, account_name, error}
    """
    try:
        import requests
        r = requests.get(f'{CF_BASE}/user/tokens/verify', headers=_headers(api_token), timeout=10)
        data = r.json()
        if not data.get('success'):
            errors = data.get('errors', [])
            msg = errors[0].get('message', 'Token invalide') if errors else 'Token invalide'
            return {'success': False, 'error': msg}

        # Token valide — récupérer les infos du compte
        account_info = _get_account_info(api_token)
        return {
            'success': True,
            'token_status': data.get('result', {}).get('status', 'active'),
            **account_info,
        }
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
