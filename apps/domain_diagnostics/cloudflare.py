import requests
from django.conf import settings


class CloudflareAPIError(Exception):
    pass


class CloudflareClient:
    BASE_URL = 'https://api.cloudflare.com/client/v4'

    def __init__(self, api_token=None):
        self.api_token = api_token or getattr(settings, 'ORION_CLOUDFLARE_API_TOKEN', '')
        if not self.api_token:
            raise CloudflareAPIError('Token Cloudflare manquant. Configurez ORION_CLOUDFLARE_API_TOKEN dans .env.')

    @property
    def _headers(self):
        return {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json',
        }

    def _request(self, method, path, **kwargs):
        url = f'{self.BASE_URL}{path}'
        try:
            response = requests.request(method, url, headers=self._headers, timeout=20, **kwargs)
        except requests.RequestException as exc:
            raise CloudflareAPIError(f'Erreur réseau Cloudflare : {exc}')
        try:
            data = response.json()
        except Exception:
            raise CloudflareAPIError(f'Réponse Cloudflare invalide (HTTP {response.status_code})')
        if not data.get('success', False):
            errors = data.get('errors', [])
            msg = '; '.join(e.get('message', str(e)) for e in errors) if errors else str(response.status_code)
            raise CloudflareAPIError(f'Erreur Cloudflare : {msg}')
        return data.get('result')

    def verify_token(self):
        return self._request('GET', '/user/tokens/verify')

    def list_zones(self, name=None):
        params = {}
        if name:
            params['name'] = name
        return self._request('GET', '/zones', params=params) or []

    def get_zone_id(self, zone_name):
        zones = self.list_zones(name=zone_name)
        if not zones:
            raise CloudflareAPIError(f'Zone Cloudflare introuvable : {zone_name}')
        return zones[0]['id']

    def list_dns_records(self, zone_id, name=None, record_type=None):
        params = {}
        if name:
            params['name'] = name
        if record_type:
            params['type'] = record_type
        return self._request('GET', f'/zones/{zone_id}/dns_records', params=params) or []

    def create_dns_record(self, zone_id, record_type, name, content, proxied=True, ttl=1):
        return self._request('POST', f'/zones/{zone_id}/dns_records', json={
            'type': record_type, 'name': name, 'content': content,
            'ttl': ttl, 'proxied': proxied,
        })

    def update_dns_record(self, zone_id, record_id, record_type, name, content, proxied=True, ttl=1):
        return self._request('PUT', f'/zones/{zone_id}/dns_records/{record_id}', json={
            'type': record_type, 'name': name, 'content': content,
            'ttl': ttl, 'proxied': proxied,
        })

    def patch_dns_record(self, zone_id, record_id, **payload):
        return self._request('PATCH', f'/zones/{zone_id}/dns_records/{record_id}', json=payload)

    def get_zone_setting(self, zone_id, setting_name):
        return self._request('GET', f'/zones/{zone_id}/settings/{setting_name}')

    def edit_zone_setting(self, zone_id, setting_name, value):
        return self._request('PATCH', f'/zones/{zone_id}/settings/{setting_name}', json={'value': value})

    def get_ssl_mode(self, zone_id):
        result = self.get_zone_setting(zone_id, 'ssl')
        return result.get('value') if result else None

    def set_ssl_mode(self, zone_id, value):
        valid = {'off', 'flexible', 'full', 'strict', 'origin_pull'}
        if value not in valid:
            raise CloudflareAPIError(f'Mode SSL invalide : {value}. Valeurs acceptées : {", ".join(valid)}')
        return self.edit_zone_setting(zone_id, 'ssl', value)

    def set_always_use_https(self, zone_id, enabled=True):
        return self.edit_zone_setting(zone_id, 'always_use_https', 'on' if enabled else 'off')
