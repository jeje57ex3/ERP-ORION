"""
apps/websites/tunnel_service.py — Service Cloudflare Tunnel pour Orion ERP

Fonctions utilitaires pour :
- Générer un config.yml à partir des règles d'ingress
- Écrire le config.yml sur disque
- Vérifier si cloudflared tourne (Windows et Linux)
- Synchroniser les enregistrements DNS CNAME via l'API Cloudflare
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models_domains import CloudflareTunnel, TunnelIngressRule


# --- Chemins par defaut --------------------------------------------------

def default_cloudflared_paths() -> dict:
    """Emplacements habituels de cloudflared selon la plateforme.

    Ces chemins etaient codes en dur sur le poste de developpement
    (C:\\<dev>\\.cloudflared), ce qui les rendait absurdes sur
    l'appliance Linux ou cloudflared s'installe dans /etc/cloudflared.
    """
    if sys.platform == 'win32':
        base = Path(os.path.expanduser('~')) / '.cloudflared'
    else:
        # PurePosixPath et non Path : evaluee depuis Windows, Path produirait
        # des antislashs pour un chemin Linux.
        base = PurePosixPath('/etc/cloudflared')
    return {
        'dir': str(base),
        'config': str(base / 'config.yml'),
        'credentials': str(base / '<tunnel-id>.json'),
    }


def path_is_foreign(raw: str) -> bool:
    """Vrai si ce chemin appartient a une AUTRE plateforme que l'hote.

    Un chemin Windows sur un hote POSIX n'est pas vu comme absolu : Path le
    traite comme un nom de fichier relatif contenant des antislashs.
    write_config_yml creait alors un fichier litteralement nomme
    "C:[...]config.yml" dans le repertoire de travail de Django et renvoyait
    un SUCCES, alors que cloudflared ne voyait jamais la configuration.
    Cas reel : base importee d'un poste Windows vers l'appliance Linux, ou
    les chemins stockes en base restent ceux du poste d'origine.
    """
    raw = (raw or "").strip()
    if not raw:
        return False
    if sys.platform == 'win32':
        return raw.startswith('/')
    return bool(re.match(r'^[A-Za-z]:[\\/]', raw)) or raw.startswith(chr(92) * 2)


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

    if path_is_foreign(tunnel.config_file):
        attendu = default_cloudflared_paths()['config']
        return False, (
            f"Le chemin « {tunnel.config_file} » appartient à une autre "
            f"plateforme que ce serveur. Sans ce contrôle, un fichier portant "
            f"ce nom littéral serait créé dans le répertoire de travail et "
            f"cloudflared ne le lirait jamais. Corrigez le champ « Fichier "
            f"config.yml » du tunnel, par exemple : {attendu}"
        )

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


def regles_pour_publication(tunnel: "CloudflareTunnel") -> list[dict]:
    """Les regles actives du tunnel, dans la forme attendue par l'API.

    Memes regles et meme tri que generate_config_yml() : ce qui part chez
    Cloudflare et ce qu'ecrit le config.yml local doivent decrire le meme
    routage, sinon le comportement du site dependrait de la facon dont le
    connecteur a ete lance.
    """
    return [
        {'hostname': regle.hostname, 'service': regle.service}
        for regle in tunnel.ingress_rules.filter(is_active=True)
                                         .order_by('order', 'hostname')
        if regle.hostname and regle.service
    ]


def publier_ingress_du_tunnel(tunnel: "CloudflareTunnel",
                              a_blanc: bool = False) -> dict:
    """Publie les regles du tunnel dans la configuration distante Cloudflare.

    Pendant complementaire de write_config_yml() : celui-ci ne sert qu'un
    connecteur lance avec « --config », tandis qu'un connecteur lance par
    jeton applique la configuration distante et ignore le fichier. Les deux
    voies existent donc, et celle-ci etait la seule absente.
    """
    vide = {'ajouts': [], 'modifications': [], 'inchangees': [],
            'conserves': [], 'config': {}, 'source': '', 'avertissement': '',
            'a_blanc': a_blanc}

    account = tunnel.cloudflare_account
    if account is None:
        return {**vide, 'success': False, 'error': (
            "Aucun compte Cloudflare rattaché à ce tunnel. Rattachez-le dans "
            "« Modifier le tunnel » : la publication passe par l'API, donc "
            "par le jeton de ce compte.")}
    if not tunnel.tunnel_id:
        return {**vide, 'success': False, 'error': (
            "Ce tunnel n'a pas d'UUID renseigné — l'API ne peut pas savoir "
            "quelle configuration écrire.")}

    regles = regles_pour_publication(tunnel)
    if not regles:
        return {**vide, 'success': False, 'error': (
            "Aucune règle d'ingress active sur ce tunnel : il n'y a rien à "
            "publier. Publier une liste vide effacerait la configuration "
            "distante, ce qui est refusé.")}

    from .cloudflare_service import publier_ingress
    return publier_ingress(account, tunnel.tunnel_id, regles, a_blanc=a_blanc)


def install_connector_from_account(tunnel) -> tuple[bool, str]:
    """Installe et démarre le connecteur local depuis le compte Cloudflare.

    Évite de copier à la main le fichier de credentials depuis la machine où
    le tunnel a été créé : le jeton de connecteur est récupéré par l'API avec
    le compte déjà enregistré dans l'ERP. En mode jeton, l'ingress vient du
    dashboard Zero Trust et non du config.yml local.

    Le jeton transite en argument de « cloudflared service install », faute
    d'option d'entrée standard côté cloudflared : il est donc visible une
    fraction de seconde dans la liste des processus locaux. Il n'y a en
    revanche aucune trace en historique de shell, et cloudflared l'inscrit
    ensuite lui-même dans l'unité systemd, lisible par root seul.

    Retourne (success, message).
    """
    account = getattr(tunnel, 'cloudflare_account', None)
    if account is None:
        return False, ("Aucun compte Cloudflare rattaché à ce tunnel. "
                       "Associez-en un pour récupérer son jeton de connecteur.")
    if not tunnel.tunnel_id:
        return False, "Ce tunnel n'a pas d'identifiant (UUID) renseigné."

    from .cloudflare_service import fetch_tunnel_token
    resultat = fetch_tunnel_token(account, tunnel.tunnel_id)
    if not resultat['success']:
        return False, (f"Jeton de connecteur indisponible : {resultat['error']}. "
                       "Le jeton d'API doit porter la permission "
                       "« Cloudflare Tunnel: Edit ».")

    return _installer_connecteur(resultat['token'], origine='le compte Cloudflare')


def install_connector_with_token(token: str) -> tuple[bool, str]:
    """Installe le connecteur avec un jeton copié à la main.

    Voie de secours quand l'API n'est pas exploitable : jeton d'API sans
    portée de compte (« Not authorized » sur /cfd_tunnel/<uuid>/token), ou
    tunnel appartenant à un autre compte que celui enregistré dans l'ERP. Le
    jeton se copie dans Zero Trust > Networks > Tunnels > Configure >
    Install connector.

    Retourne (success, message).
    """
    token = (token or '').strip()
    if not token:
        return False, 'Jeton de connecteur vide.'
    # Un jeton de connecteur est un blob base64 d'environ 180 caracteres. Ce
    # controle distingue surtout un JETON D'API (~40) collé par erreur.
    if len(token) < 80:
        return False, (f'Jeton trop court ({len(token)} caractères). Un jeton de '
                       'connecteur fait environ 180 caractères et se copie dans '
                       'Zero Trust > Tunnels > Configure > Install connector. '
                       "Un jeton d'API (~40 caractères) ne convient pas ici.")
    return _installer_connecteur(token, origine='le jeton fourni')


def _installer_connecteur(token: str, origine: str) -> tuple[bool, str]:
    """Pose l'unité systemd cloudflared avec ce jeton, la démarre, la vérifie.

    Le jeton transite en argument de « cloudflared service install », faute
    d'option d'entrée standard côté cloudflared : il est donc visible une
    fraction de seconde dans la liste des processus locaux. Il n'y a en
    revanche aucune trace en historique de shell (subprocess sans shell), et
    cloudflared l'inscrit ensuite lui-même dans l'unité systemd, lisible par
    root seul.
    """
    exe = shutil.which('cloudflared')
    if not exe:
        return False, "cloudflared n'est pas installé sur ce serveur."

    # systemctl et « service install » exigent root ; Django tourne sous
    # l'utilisateur applicatif, qui dispose de sudo sans mot de passe.
    prefixe = [] if (os.name == 'posix' and os.geteuid() == 0) else ['sudo', '-n']
    try:
        # Une unité déjà installée porte l'ancienne configuration — typiquement
        # « --config /etc/cloudflared/config.yml », donc le mode FICHIER. La
        # conserver ferait redémarrer cloudflared sur cette configuration et le
        # jeton ne serait jamais utilisé : « service install » refuse d'ailleurs
        # d'écraser, avec « cloudflared service is already installed at ... ».
        # On désinstalle donc avant de reposer l'unité. Échec ignoré : il n'y a
        # simplement rien à désinstaller la première fois.
        subprocess.run(
            prefixe + [exe, 'service', 'uninstall'],
            capture_output=True, text=True, timeout=60,
        )

        pose = subprocess.run(
            prefixe + [exe, 'service', 'install', token],
            capture_output=True, text=True, timeout=60,
        )
        if pose.returncode != 0:
            detail = (pose.stderr or pose.stdout).strip()[:300]
            # Les deux formulations rencontrées selon les versions de
            # cloudflared ; « already installed » est celle observée en
            # production. Ni l'une ni l'autre n'est un échec à ce stade.
            deja = ('already exists' in detail.lower()
                    or 'already installed' in detail.lower())
            if not deja:
                return False, f"Installation du service échouée : {detail}"

        for cmd in (['systemctl', 'enable', 'cloudflared'],
                    ['systemctl', 'restart', 'cloudflared']):
            subprocess.run(prefixe + cmd, capture_output=True, text=True, timeout=30)

        etat = subprocess.run(
            ['systemctl', 'is-active', 'cloudflared'],
            capture_output=True, text=True, timeout=10,
        )
        if etat.stdout.strip() == 'active':
            return True, (f"Connecteur installé et démarré depuis {origine}. "
                          "En mode jeton, déclarez les hostnames dans Zero Trust "
                          "(Tunnels > Public Hostname).")
        return False, ("Service installé mais inactif. Journal : "
                       "journalctl -u cloudflared -n 20")
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"Erreur lors de l'installation du connecteur : {exc}"


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
            # systemctl exige les droits root. Django tourne sous
            # l'utilisateur applicatif (orion sur l'appliance), qui dispose
            # de sudo sans mot de passe : sans sudo, systemctl repond
            # « Interactive authentication required » et le redemarrage
            # echouait systematiquement.
            tentatives = [['systemctl', 'restart', 'cloudflared']]
            if os.geteuid() != 0:
                tentatives.insert(
                    0, ['sudo', '-n', 'systemctl', 'restart', 'cloudflared'])
            detail = ''
            for cmd in tentatives:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if r.returncode == 0:
                    return True, 'cloudflared redémarré (systemctl).'
                detail = (r.stderr or r.stdout).strip() or f'code {r.returncode}'
            return False, f'systemctl restart cloudflared : {detail}'

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
    """Trouve l'ID de zone Cloudflare pour un nom de zone EXACT."""
    zone, _ = _trouver_la_zone(api_token, zone_name)
    return zone['id'] if zone else None


def _trouver_la_zone(api_token: str, hostname: str):
    """La zone Cloudflare qui contient ce nom d'hôte.

    POURQUOI ON NE DÉCOUPE PLUS LE NOM

    La version précédente prenait « les deux derniers segments » comme nom
    de zone. C'est faux dès que le suffixe en compte deux : « .co.uk »,
    « .com.br », « .asso.fr »… Pour « boutique.exemple.co.uk » elle
    cherchait la zone « co.uk », qui n'existe évidemment pas, et concluait
    « zone introuvable ».

    On demande donc à Cloudflare SES zones, et on retient la plus longue
    qui termine le nom d'hôte. Le plus long l'emporte : si le compte
    héberge « exemple.fr » ET « client.exemple.fr », c'est la seconde qui
    gouverne « www.client.exemple.fr ».

    Rend (zone, erreur). L'erreur est une PHRASE EXPLOITABLE, jamais None
    silencieux : la version précédente avalait toute exception — jeton
    invalide, réseau coupé, délai dépassé — et rendait None, si bien qu'un
    problème d'authentification se lisait « zone introuvable ». On
    cherchait alors un domaine mal orthographié pendant que le vrai
    coupable était le jeton.
    """
    try:
        import requests
    except ImportError:
        return None, "Le package 'requests' n'est pas installé."

    hostname = (hostname or '').strip().rstrip('.').lower()
    if not hostname:
        return None, "Nom d'hôte vide."

    zones = []
    page = 1
    while True:
        try:
            reponse = requests.get(
                'https://api.cloudflare.com/client/v4/zones',
                params={'per_page': 50, 'page': page},
                headers=_cf_headers(api_token),
                timeout=10,
            )
        except Exception as exc:
            return None, f"Cloudflare injoignable : {exc}"

        try:
            data = reponse.json()
        except ValueError:
            return None, (f"Réponse illisible de Cloudflare "
                          f"(code HTTP {reponse.status_code}).")

        if not data.get('success'):
            erreurs = data.get('errors') or []
            detail = erreurs[0].get('message') if erreurs else 'erreur inconnue'
            # 9109 / 10000 : jeton invalide ou droits insuffisants. Le dire,
            # plutot que de laisser chercher un domaine mal ecrit.
            return None, (f"Cloudflare refuse la lecture des zones : {detail}. "
                          "Vérifiez le jeton d’API et ses permissions "
                          "(Zone → DNS → Modifier).")

        lot = data.get('result') or []
        zones.extend(lot)

        infos = data.get('result_info') or {}
        if page >= (infos.get('total_pages') or 1) or not lot:
            break
        page += 1

    if not zones:
        return None, ("Aucune zone n’est visible avec ce jeton d’API. "
                      "Le jeton doit avoir accès à la zone du domaine.")

    candidates = [
        z for z in zones
        if hostname == (z.get('name') or '').lower()
        or hostname.endswith('.' + (z.get('name') or '').lower())
    ]
    if not candidates:
        connues = ', '.join(sorted((z.get('name') or '') for z in zones)[:8])
        return None, (f"Aucune zone Cloudflare ne contient « {hostname} ». "
                      f"Zones visibles avec ce jeton : {connues}.")

    # La plus longue l'emporte : « client.exemple.fr » prime sur
    # « exemple.fr » pour « www.client.exemple.fr ».
    return max(candidates, key=lambda z: len(z.get('name') or '')), ""



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

    hostname = (rule.hostname or '').strip().rstrip('.').lower()
    if not hostname:
        return False, "Cette règle n’a pas de nom d’hôte."

    zone, erreur = _trouver_la_zone(account.api_token, hostname)
    if zone is None:
        return False, erreur

    zone_id = zone['id']
    cname_target = f'{tunnel.tunnel_id}.cfargotunnel.com'
    headers = _cf_headers(account.api_token)
    list_url = f'https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records'

    # On cherche TOUS les types, pas seulement les CNAME.
    #
    # La version precedente ne listait que les CNAME. Quand un
    # enregistrement A existait deja pour ce nom — le cas courant d'un
    # domaine qui pointait vers un serveur avant de passer au tunnel —
    # elle n'en trouvait aucun, tentait de CREER un CNAME, et Cloudflare
    # refusait : un nom ne peut pas porter a la fois un A et un CNAME. Le
    # message renvoye parlait de conflit d'enregistrement, sans dire lequel
    # ni ou le trouver.
    try:
        reponse = requests.get(list_url, params={'name': hostname},
                               headers=headers, timeout=10)
        donnees = reponse.json()
    except Exception as exc:
        return False, f"Cloudflare injoignable : {exc}"

    if not donnees.get('success'):
        erreurs = donnees.get('errors') or []
        detail = erreurs[0].get('message') if erreurs else 'erreur inconnue'
        return False, f"Lecture DNS refusee par Cloudflare : {detail}"

    existants = donnees.get('result') or []
    cname = next((e for e in existants if e.get('type') == 'CNAME'), None)
    bloquant = next(
        (e for e in existants if e.get('type') in ('A', 'AAAA')), None)

    if bloquant is not None:
        return False, (
            f"Un enregistrement {bloquant.get('type')} existe deja pour "
            f"« {hostname} » (il pointe vers {bloquant.get('content')}). "
            "Un tunnel exige un CNAME, et Cloudflare interdit les deux sur "
            "le meme nom. Supprimez-le dans le tableau de bord Cloudflare, "
            "puis relancez la synchronisation.")

    charge = {'type': 'CNAME', 'name': hostname,
              'content': cname_target, 'proxied': True}

    try:
        if cname is not None:
            resp = requests.put(f"{list_url}/{cname['id']}", json=charge,
                                headers=headers, timeout=10)
            action = 'mis à jour'
        else:
            resp = requests.post(list_url, json=charge, headers=headers,
                                 timeout=10)
            action = 'créé'
        data = resp.json()
    except Exception as exc:
        return False, f"Cloudflare injoignable : {exc}"

    if not data.get('success'):
        errors = data.get('errors') or []
        msg = errors[0].get('message', 'Erreur inconnue') if errors else 'Erreur inconnue'
        return False, f"Cloudflare API : {msg}"

    rule.dns_synced = True
    rule.dns_synced_at = timezone.now()
    rule.save(update_fields=['dns_synced', 'dns_synced_at'])

    # LE DNS NE SUFFIT PAS, ET C'EST LA SECONDE MOITIE DU PROBLEME.
    #
    # Un tunnel lance PAR JETON ignore le config.yml local : sa liste de
    # routes est detenue par Cloudflare. Le CNAME peut donc etre parfait et
    # le nom repondre « erreur 1033 » tant que la regle d'ingress n'a pas
    # ete PUBLIEE chez Cloudflare. On le dit dans le message de succes,
    # sans quoi on croit la synchronisation terminee.
    # Le rappel est INCONDITIONNEL, et c'est volontaire : aucun champ ne
    # retient si l'ingress a ete publie chez Cloudflare. Pretendre le
    # savoir — en testant un attribut qui n'existe pas — donnerait un
    # silence rassurant dans le cas meme ou l'avertissement est utile.
    rappel = (" Si le connecteur est lance par jeton, pensez a publier "
              "l’ingress chez Cloudflare : sans cette route, le nom "
              "repondra « erreur 1033 » malgre un DNS correct.")

    return True, (f"Enregistrement DNS CNAME {action} : {hostname} → "
                  f"{cname_target} (zone {zone.get('name')}).{rappel}")
