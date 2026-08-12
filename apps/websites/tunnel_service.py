"""
apps/websites/tunnel_service.py — Service Cloudflare Tunnel pour Orion ERP

Fonctions utilitaires pour :
- Générer un config.yml à partir des règles d'ingress
- Écrire le config.yml sur disque
- Vérifier si cloudflared.exe tourne (Windows)
- Synchroniser les enregistrements DNS CNAME via l'API Cloudflare
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models_domains import CloudflareTunnel, TunnelIngressRule


# ─── Génération config.yml ────────────────────────────────────────────────────

def generate_config_yml(tunnel: "CloudflareTunnel") -> str:
    """
    Génère le contenu d'un fichier config.yml pour cloudflared.
    Seules les règles actives sont incluses, triées par ordre.
    La dernière règle est toujours le catch-all http_status:404.
    """
    lines = []

    if tunnel.tunnel_id:
        lines.append(f'tunnel: {tunnel.tunnel_id}')
    if tunnel.credentials_file:
        creds = tunnel.credentials_file.replace('\\', '/')
        lines.append(f'credentials-file: {creds}')

    lines.append('')
    lines.append('ingress:')

    active_rules = tunnel.ingress_rules.filter(is_active=True).order_by('order', 'hostname')
    for rule in active_rules:
        lines.append(f'  - hostname: {rule.hostname}')
        lines.append(f'    service: {rule.service}')

    # catch-all obligatoire
    lines.append('  - service: http_status:404')

    return '\n'.join(lines) + '\n'


def write_config_yml(tunnel: "CloudflareTunnel") -> tuple[bool, str]:
    """
    Écrit le config.yml sur disque au chemin défini dans tunnel.config_file.
    Retourne (success, message).
    """
    if not tunnel.config_file:
        return False, "Aucun chemin de config.yml défini sur ce tunnel."

    try:
        content = generate_config_yml(tunnel)
        path = Path(tunnel.config_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
        return True, f"config.yml écrit : {tunnel.config_file}"
    except Exception as exc:
        return False, f"Erreur écriture config.yml : {exc}"


# ─── Manipulation directe du config.yml (toggle hostname) ───────────────────

def toggle_hostname_in_config(config_path: str, hostname: str, enabled: bool) -> tuple[bool, str]:
    """
    Active (enabled=True) ou désactive (enabled=False) une règle hostname
    dans le config.yml cloudflared en modifiant le fichier directement.

    Les règles désactivées sont conservées sous forme de commentaires :
        # [disabled] - hostname: lunea.elysiums.fr
        # [disabled]   service: http://localhost:5174

    Retourne (success, message).
    """
    path = Path(config_path)
    if not path.exists():
        return False, f'config.yml introuvable : {config_path}'

    try:
        lines = path.read_text(encoding='utf-8').splitlines(keepends=True)
        new_lines: list[str] = []
        i = 0
        found = False

        while i < len(lines):
            line = lines[i]
            bare = line.rstrip('\r\n')

            if not enabled:
                # Cherche la règle active :  "  - hostname: <hostname>"
                if bare in (f'  - hostname: {hostname}',):
                    service_line = lines[i + 1] if i + 1 < len(lines) else ''
                    new_lines.append(f'  # [disabled] - hostname: {hostname}\n')
                    new_lines.append(f'  # [disabled]   {service_line.lstrip()}')
                    i += 2
                    found = True
                    continue
            else:
                # Cherche la règle commentée : "  # [disabled] - hostname: <hostname>"
                if f'# [disabled] - hostname: {hostname}' in bare:
                    service_line = lines[i + 1] if i + 1 < len(lines) else ''
                    svc = service_line.replace('# [disabled]', '').strip()
                    new_lines.append(f'  - hostname: {hostname}\n')
                    new_lines.append(f'    {svc}\n')
                    i += 2
                    found = True
                    continue

            new_lines.append(line)
            i += 1

        if not found:
            verb = 'activer' if enabled else 'désactiver'
            return False, f'Règle {hostname} non trouvée à {verb} dans config.yml.'

        path.write_text(''.join(new_lines), encoding='utf-8')
        verb = 'activée' if enabled else 'désactivée'
        return True, f'Règle {hostname} {verb} dans config.yml.'

    except Exception as exc:
        return False, f'Erreur modification config.yml : {exc}'


# ─── Reload / restart cloudflared ────────────────────────────────────────────

def reload_cloudflared() -> tuple[bool, str]:
    """
    Redémarre cloudflared pour appliquer le nouveau config.yml.
    Windows : tente service (Restart-Service), sinon kill + relaunch du processus.
    Linux   : systemctl restart cloudflared.
    Retourne (success, message).
    """
    import time

    try:
        if sys.platform == 'win32':
            # Tentative 1 : service Windows
            r = subprocess.run(
                ['powershell', '-Command', 'Restart-Service cloudflared -ErrorAction Stop'],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                return True, 'cloudflared redémarré (service Windows).'

            # Tentative 2 : processus autonome — récupère la commande exacte via CIM
            r_cmd = subprocess.run(
                ['powershell', '-Command',
                 "(Get-CimInstance Win32_Process -Filter \"Name='cloudflared.exe'\").CommandLine"],
                capture_output=True, text=True, timeout=10,
            )
            cmdline = r_cmd.stdout.strip()

            subprocess.run(
                ['taskkill', '/F', '/IM', 'cloudflared.exe'],
                capture_output=True, timeout=10,
            )
            time.sleep(2)

            if cmdline:
                # Start-Process lance cloudflared indépendamment du processus Python/Django
                ps_cmd = f'Start-Process -FilePath "{exe}" -ArgumentList "tunnel", "run" -WindowStyle Hidden'
                # Extraire le chemin de l'exécutable depuis la cmdline
                import re as _re
                exe_match = _re.match(r'"([^"]+)"', cmdline)
                exe = exe_match.group(1) if exe_match else 'cloudflared'
                ps_cmd = (
                    f'Start-Process -FilePath "{exe}" '
                    f'-ArgumentList "tunnel", "run" -WindowStyle Hidden'
                )
                subprocess.run(
                    ['powershell', '-Command', ps_cmd],
                    capture_output=True, timeout=10,
                )
                return True, 'cloudflared redémarré (processus détaché).'

            return (
                False,
                'cloudflared arrêté mais ligne de commande introuvable — relancez-le manuellement.',
            )

        else:
            r = subprocess.run(
                ['systemctl', 'restart', 'cloudflared'],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                return True, 'cloudflared redémarré (systemctl).'
            return False, f'systemctl restart cloudflared : {r.stderr.strip()}'

    except Exception as exc:
        return False, f'Erreur lors du redémarrage cloudflared : {exc}'


# ─── Statut cloudflared ───────────────────────────────────────────────────────

def get_cloudflared_status() -> dict:
    """
    Vérifie si cloudflared.exe est en cours d'exécution.
    Fonctionne sur Windows (tasklist) et Linux/Mac (pgrep).
    Retourne un dict: {running: bool, pids: list[str], error: str|None}
    """
    try:
        if sys.platform == 'win32':
            result = subprocess.run(
                ['tasklist', '/FI', 'IMAGENAME eq cloudflared.exe', '/FO', 'CSV', '/NH'],
                capture_output=True, text=True, timeout=5,
            )
            lines = [l for l in result.stdout.strip().splitlines() if 'cloudflared' in l.lower()]
            pids = []
            for line in lines:
                parts = line.strip('"').split('","')
                if len(parts) >= 2:
                    pids.append(parts[1])
            return {'running': bool(pids), 'pids': pids, 'error': None}
        else:
            result = subprocess.run(['pgrep', '-x', 'cloudflared'], capture_output=True, text=True, timeout=5)
            pids = result.stdout.strip().splitlines()
            return {'running': bool(pids), 'pids': pids, 'error': None}
    except Exception as exc:
        return {'running': False, 'pids': [], 'error': str(exc)}


# ─── Import depuis config.yml ────────────────────────────────────────────────

def parse_config_yml(path: str) -> dict:
    """
    Parse un fichier config.yml cloudflared sans dépendance externe.
    Retourne: {success, tunnel_id, credentials_file, config_file, ingress: [{hostname, service}], error}
    """
    try:
        content = Path(path).read_text(encoding='utf-8')
    except Exception as exc:
        return {'success': False, 'error': f'Impossible de lire le fichier : {exc}'}

    tunnel_id = ''
    credentials_file = ''
    ingress = []
    in_ingress = False
    pending_hostname = None

    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        if stripped.startswith('tunnel:'):
            tunnel_id = stripped[len('tunnel:'):].strip()
        elif stripped.startswith('credentials-file:'):
            credentials_file = stripped[len('credentials-file:'):].strip()
        elif stripped == 'ingress:':
            in_ingress = True
        elif in_ingress:
            if '- hostname:' in stripped:
                pending_hostname = stripped.split('- hostname:', 1)[1].strip()
            elif stripped.startswith('service:') and pending_hostname:
                service_val = stripped[len('service:'):].strip()
                ingress.append({'hostname': pending_hostname, 'service': service_val})
                pending_hostname = None
            elif '- service:' in stripped and not pending_hostname:
                # catch-all — ignoré
                pass

    return {
        'success': True,
        'tunnel_id': tunnel_id,
        'credentials_file': credentials_file,
        'config_file': path,
        'ingress': ingress,
    }


# ─── Sync DNS Cloudflare API ─────────────────────────────────────────────────

def _cf_headers(api_token: str) -> dict:
    return {'Authorization': f'Bearer {api_token}', 'Content-Type': 'application/json'}


def _get_zone_id(api_token: str, zone_name: str) -> str | None:
    """Trouve l'ID de zone Cloudflare pour un domaine racine."""
    try:
        import requests
        r = requests.get(
            'https://api.cloudflare.com/client/v4/zones',
            params={'name': zone_name},
            headers=_cf_headers(api_token),
            timeout=10,
        )
        data = r.json()
        if data.get('success') and data.get('result'):
            return data['result'][0]['id']
    except Exception:
        pass
    return None


def sync_tunnel_dns(rule: "TunnelIngressRule") -> tuple[bool, str]:
    """
    Crée ou met à jour l'enregistrement DNS CNAME pour cette règle d'ingress
    chez Cloudflare (hostname → <tunnel_id>.cfargotunnel.com).

    Nécessite que le tunnel soit lié à un CloudflareAccount actif.
    """
    from django.utils import timezone

    tunnel = rule.tunnel
    account = tunnel.cloudflare_account
    if not account or not account.api_token:
        return False, "Aucun compte Cloudflare associé à ce tunnel."
    if not tunnel.tunnel_id:
        return False, "L'ID du tunnel est manquant."

    try:
        import requests
    except ImportError:
        return False, "Le package 'requests' n'est pas installé."

    hostname = rule.hostname
    # Trouver le domaine racine (les 2 derniers segments)
    parts = hostname.split('.')
    zone_name = '.'.join(parts[-2:]) if len(parts) >= 2 else hostname
    zone_id = _get_zone_id(account.api_token, zone_name)
    if not zone_id:
        return False, f"Zone Cloudflare introuvable pour '{zone_name}'."

    cname_target = f'{tunnel.tunnel_id}.cfargotunnel.com'
    headers = _cf_headers(account.api_token)

    # Chercher un enregistrement existant
    list_url = f'https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records'
    r = requests.get(list_url, params={'type': 'CNAME', 'name': hostname}, headers=headers, timeout=10)
    existing = r.json().get('result', [])

    if existing:
        record_id = existing[0]['id']
        patch_url = f'{list_url}/{record_id}'
        payload = {'type': 'CNAME', 'name': hostname, 'content': cname_target, 'proxied': True}
        resp = requests.put(patch_url, json=payload, headers=headers, timeout=10)
        action = 'mis à jour'
    else:
        payload = {'type': 'CNAME', 'name': hostname, 'content': cname_target, 'proxied': True}
        resp = requests.post(list_url, json=payload, headers=headers, timeout=10)
        action = 'créé'

    data = resp.json()
    if data.get('success'):
        rule.dns_synced = True
        rule.dns_synced_at = timezone.now()
        rule.save(update_fields=['dns_synced', 'dns_synced_at'])
        return True, f"Enregistrement DNS CNAME {action} : {hostname} → {cname_target}"
    else:
        errors = data.get('errors', [])
        msg = errors[0].get('message', 'Erreur inconnue') if errors else 'Erreur inconnue'
        return False, f"Cloudflare API : {msg}"
