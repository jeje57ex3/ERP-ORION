#!/usr/bin/env bash
# ============================================================================
# Orion ERP — Activation de Cloudflare Tunnel après l'installation
#
# Le provisioning n'installe le tunnel que si un token a été fourni à
# deploy.sh (--cf-token) ; sinon le service est désactivé. Ce script permet de
# l'activer plus tard, sans redéployer la VM.
#
# Le token est lu sur l'ENTRÉE STANDARD, jamais en argument : un token passé
# en paramètre se retrouverait dans l'historique du shell et dans la liste des
# processus, où n'importe quel utilisateur de la machine peut le lire.
#
# Usage :
#   orion-cloudflare.sh status                 état du tunnel (défaut)
#   echo '<token>' | orion-cloudflare.sh set-token
#   orion-cloudflare.sh set-token --from-file /chemin/token.txt
#   orion-cloudflare.sh disable                arrête et désactive le service
#
# Depuis l'hyperviseur Proxmox, sans session SSH dans la VM :
#   qm guest exec <vmid> --pass-stdin 1 -- \
#     /bin/bash -c '/opt/orion/scripts/orion-cloudflare.sh set-token' < token.txt
# ============================================================================
set -uo pipefail

UNIT='cloudflared.service'
CONFIG='/etc/cloudflared/config.yml'

titre() { echo ""; echo "=== $* ==="; }
ok()    { echo "  [OK] $*"; }
avert() { echo "  [!!] $*"; }
err()   { echo "  [XX] $*" >&2; }

besoin_root() {
  if [ "$(id -u)" -ne 0 ]; then
    err "À lancer en root (sudo)."
    exit 1
  fi
}

# Mode d'un tunnel déjà installé : token (géré depuis le dashboard Zero Trust)
# ou fichier de configuration local. Les deux s'excluent.
mode_actuel() {
  if [ -f "/etc/systemd/system/$UNIT" ] || [ -f "/lib/systemd/system/$UNIT" ]; then
    # « service install <token> » inscrit le token dans l'ExecStart de l'unité.
    if systemctl cat "$UNIT" 2>/dev/null | grep -q 'tunnel.*run.*--token'; then
      echo 'token'
    elif systemctl cat "$UNIT" 2>/dev/null | grep -q -- '--config'; then
      echo 'fichier'
    else
      echo 'inconnu'
    fi
  else
    echo 'absent'
  fi
}

cmd_status() {
  titre "Service cloudflared"
  local mode
  mode="$(mode_actuel)"
  case "$mode" in
    absent)
      avert "aucune unité systemd : le tunnel n'a jamais été installé"
      echo "       activez-le avec : echo '<token>' | $0 set-token"
      ;;
    token)   ok "installé en mode TOKEN (ingress géré dans le dashboard Zero Trust)" ;;
    fichier) ok "installé en mode FICHIER ($CONFIG)" ;;
    *)       avert "unité présente mais mode indéterminé" ;;
  esac

  if [ "$mode" != 'absent' ]; then
    echo "  actif     : $(systemctl is-active "$UNIT" 2>/dev/null)"
    echo "  au démarrage : $(systemctl is-enabled "$UNIT" 2>/dev/null)"
  fi

  if [ -f "$CONFIG" ]; then
    titre "Hostnames du config.yml"
    grep -E '^\s*-?\s*hostname:' "$CONFIG" 2>/dev/null | sed 's/^/  /' || echo "  aucun"
  fi

  # Pas de journal à montrer si le service n'a jamais existé : afficher des
  # lignes résiduelles donnerait l'illusion d'un tunnel installé.
  if [ "$mode" != 'absent' ]; then
    titre "Dernières lignes du journal"
    journalctl -u "$UNIT" -n 8 --no-pager -o cat 2>/dev/null | sed 's/^/  /' \
      || echo "  (journal indisponible)"
  fi
}

cmd_set_token() {
  besoin_root

  local token=''
  if [ "${1:-}" = '--from-file' ]; then
    local fichier="${2:-}"
    [ -n "$fichier" ] && [ -f "$fichier" ] || { err "Fichier introuvable : ${fichier:-<vide>}"; exit 1; }
    token="$(tr -d ' \t\r\n' < "$fichier")"
  else
    if [ -t 0 ]; then
      err "Aucun token sur l'entrée standard."
      err "Usage : echo '<token>' | $0 set-token"
      err "   ou : $0 set-token --from-file /chemin/token.txt"
      exit 1
    fi
    token="$(tr -d ' \t\r\n')"
  fi

  if [ -z "$token" ]; then
    err "Token vide."
    exit 1
  fi

  # Un token de connecteur est un blob base64 d'environ 180 caractères. Ce
  # contrôle attrape les erreurs de copier-coller les plus courantes (ligne
  # tronquée, identifiant de tunnel collé à la place du token) avant de
  # casser une configuration qui fonctionnait.
  if [ "${#token}" -lt 80 ]; then
    err "Token trop court (${#token} caractères) : attendu un jeton de connecteur"
    err "d'environ 180 caractères, copié depuis Zero Trust > Tunnels > Install."
    exit 1
  fi

  local mode
  mode="$(mode_actuel)"
  if [ "$mode" = 'fichier' ]; then
    avert "Un tunnel en mode FICHIER est déjà installé ($CONFIG)."
    avert "Le passage en mode token va le remplacer : l'ingress ne viendra plus"
    avert "de ce fichier mais du dashboard Zero Trust. Le fichier est conservé."
  fi

  titre "Installation du service"
  # cloudflared inscrit lui-même le token dans l'unité systemd qu'il crée :
  # il n'y a rien à stocker dans le .env, et rien à nettoyer ici.
  if ! cloudflared service install "$token" 2>&1 | sed 's/^/  /'; then
    avert "« service install » a signalé une erreur — l'unité a pu être créée quand même."
  fi

  systemctl daemon-reload 2>/dev/null || true
  systemctl enable "$UNIT" >/dev/null 2>&1 || true
  systemctl restart "$UNIT" 2>/dev/null || true

  # Laisse au connecteur le temps d'ouvrir ses connexions sortantes avant de
  # juger : un démarrage réussi met quelques secondes.
  local i
  for i in 1 2 3 4 5 6 7 8 9 10; do
    [ "$(systemctl is-active "$UNIT" 2>/dev/null)" = 'active' ] && break
    sleep 1
  done

  titre "Résultat"
  if [ "$(systemctl is-active "$UNIT" 2>/dev/null)" = 'active' ]; then
    ok "cloudflared actif"
    if journalctl -u "$UNIT" -n 40 --no-pager -o cat 2>/dev/null | grep -qi 'Registered tunnel connection'; then
      ok "connexion au réseau Cloudflare établie"
    else
      avert "service actif mais aucune connexion confirmée dans le journal."
      avert "Vérifiez dans quelques secondes : journalctl -u $UNIT -n 20"
    fi
    echo ""
    echo "  Déclarez maintenant les hostnames publics dans Zero Trust"
    echo "  (Tunnels > votre tunnel > Public Hostname) :"
    echo "    login    -> http://localhost:9000"
    echo "    orion    -> http://localhost:5172"
    echo "    siecle   -> http://localhost:5173"
    echo "    lunea    -> http://localhost:5174"
    echo "    ns       -> http://localhost:80    (Nginx, pas un port direct)"
  else
    err "cloudflared n'est pas actif. Journal :"
    journalctl -u "$UNIT" -n 12 --no-pager -o cat 2>/dev/null | sed 's/^/    /'
    exit 1
  fi
}

cmd_disable() {
  besoin_root
  titre "Désactivation de cloudflared"
  systemctl stop "$UNIT" 2>/dev/null && ok "arrêté" || avert "déjà arrêté"
  systemctl disable "$UNIT" >/dev/null 2>&1 && ok "désactivé au démarrage" || true
  avert "L'unité et le token qu'elle contient sont conservés : relancez avec"
  avert "systemctl start $UNIT, ou reposez un token avec « set-token »."
}

case "${1:-status}" in
  status|'')  cmd_status ;;
  set-token)  shift; cmd_set_token "$@" ;;
  disable)    cmd_disable ;;
  -h|--help)  sed -n '2,22p' "$0" ;;
  *)          err "Commande inconnue : $1"; sed -n '13,19p' "$0"; exit 2 ;;
esac
