#!/usr/bin/env bash
# ============================================================================
# Orion ERP Appliance — Réseau privé entre sites (WireGuard)
#
# En production les serveurs ne partagent aucun réseau local. Les relier par
# leurs adresses publiques supposerait d'ouvrir des ports à chaque site, de
# dépendre d'IP qui changent, et de faire voyager la réplication MySQL en
# clair sur Internet — ce dernier point à lui seul l'interdit.
#
# Tout passe donc par un seul chemin privé : battements de cœur, validation
# d'adhésion, réplication, synchronisation des médias.
#
# L'adresse privée se déduit du rang du serveur, comme son nom d'hôte :
#
#     rang 1  ->  serveur1.exemple.fr  ->  10.10.0.1
#     rang 2  ->  serveur2.exemple.fr  ->  10.10.0.2
#
# La dérivation n'est PAS recopiée ici : elle est lue depuis l'application
# (manage.py ha_mesh_config), seule source de vérité.
#
# Usage :
#   orion-mesh.sh init                              Pose la configuration locale
#   orion-mesh.sh pubkey                            Clé publique à donner aux autres
#   orion-mesh.sh add-peer RANG CLE [ENDPOINT]      Déclare un pair
#   orion-mesh.sh hosts                             Résolution privée des noms
#   orion-mesh.sh media-key                         Clé SSH de synchro des médias
#   orion-mesh.sh trust RANG "CLE"                  Accepte la clé SSH d'un pair
#   orion-mesh.sh status                            État des liaisons
#   orion-mesh.sh up | down                         Active / désactive
#
# L'échange de clés est manuel, et c'est irréductible : chaque serveur doit
# connaître la clé publique de l'autre, et aucune des deux n'existe avant que
# les deux machines soient installées.
# ============================================================================

set -euo pipefail

ORION_HOME="/opt/orion"
VENV_PY="$ORION_HOME/backend/.venv/bin/python"
MANAGE="$ORION_HOME/backend/manage.py"
IFACE="orion0"
CONF="/etc/wireguard/$IFACE.conf"
CLE_PRIVEE="/etc/wireguard/$IFACE.key"
CLE_PUBLIQUE="/etc/wireguard/$IFACE.pub"
MARQUEUR="# --- orion-mesh ---"

usage() { sed -n '2,33p' "$0"; exit "${1:-0}"; }

exiger_root() {
  [ "$(id -u)" -eq 0 ] || { echo "ERREUR: à lancer en root." >&2; exit 1; }
}

charger_config() {
  # La dérivation vient de l'application. Si elle échoue, c'est que le
  # sous-réseau privé ou le rang du serveur ne sont pas réglés — on le dit
  # plutôt que de poser une configuration inventée.
  local sortie
  if ! sortie="$(sudo -u orion -E "$VENV_PY" "$MANAGE" ha_mesh_config 2>&1)"; then
    echo "ERREUR: configuration du réseau privé indisponible :" >&2
    echo "$sortie" >&2
    exit 1
  fi
  eval "$sortie"
  : "${ORION_MESH_ADDRESS:?adresse privée absente}"
  : "${ORION_MESH_PREFIX:?préfixe absent}"
  : "${ORION_MESH_PORT:?port absent}"
}

installer_wireguard() {
  command -v wg >/dev/null 2>&1 && return 0
  echo "[mesh] Installation de WireGuard..."
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y >/dev/null
  apt-get install -y wireguard wireguard-tools >/dev/null
}

cmd_init() {
  exiger_root
  installer_wireguard
  charger_config

  mkdir -p /etc/wireguard
  chmod 700 /etc/wireguard

  if [ ! -f "$CLE_PRIVEE" ]; then
    echo "[mesh] Génération de la paire de clés..."
    # umask avant génération : la clé privée ne doit jamais exister, même une
    # fraction de seconde, avec des droits de lecture pour autrui.
    ( umask 077; wg genkey > "$CLE_PRIVEE" )
    wg pubkey < "$CLE_PRIVEE" > "$CLE_PUBLIQUE"
    chmod 600 "$CLE_PRIVEE"
    chmod 644 "$CLE_PUBLIQUE"
  else
    echo "[mesh] Clés déjà présentes — conservées."
  fi

  if [ -f "$CONF" ] && grep -q "^\[Peer\]" "$CONF"; then
    echo "[mesh] $CONF contient déjà des pairs — en-tête mis à jour sans les perdre."
    local pairs
    pairs="$(sed -n '/^\[Peer\]/,$p' "$CONF")"
  else
    local pairs=""
  fi

  {
    echo "$MARQUEUR"
    echo "# Généré par orion-mesh.sh — rang ${ORION_MESH_RANK:-?}, hôte ${ORION_MESH_HOST:-?}"
    echo "[Interface]"
    echo "Address = $ORION_MESH_ADDRESS/$ORION_MESH_PREFIX"
    echo "ListenPort = $ORION_MESH_PORT"
    echo "PrivateKey = $(cat "$CLE_PRIVEE")"
    # SaveConfig volontairement absent : il réécrirait ce fichier à l'arrêt du
    # service et effacerait les commentaires, rendant la configuration
    # illisible pour qui la relit six mois plus tard.
    echo ""
    [ -n "$pairs" ] && echo "$pairs"
  } > "$CONF.nouveau"

  mv "$CONF.nouveau" "$CONF"
  chmod 600 "$CONF"

  if command -v ufw >/dev/null 2>&1; then
    ufw allow "$ORION_MESH_PORT"/udp >/dev/null 2>&1 || true
    echo "[mesh] Pare-feu : port $ORION_MESH_PORT/udp autorisé."
  fi

  systemctl enable "wg-quick@$IFACE" >/dev/null 2>&1 || true
  echo "[mesh] Configuration posée : $ORION_MESH_ADDRESS/$ORION_MESH_PREFIX sur $IFACE."
  echo "[mesh] Clé publique à communiquer aux autres serveurs :"
  cat "$CLE_PUBLIQUE"
}

cmd_pubkey() {
  [ -f "$CLE_PUBLIQUE" ] || { echo "ERREUR: pas de clé — lancez 'init'." >&2; exit 1; }
  cat "$CLE_PUBLIQUE"
}

cmd_add_peer() {
  exiger_root
  local rang="${1:-}" cle="${2:-}" endpoint="${3:-}"
  [ -n "$rang" ] && [ -n "$cle" ] || { echo "Usage: add-peer RANG CLE [ENDPOINT]" >&2; exit 2; }
  [ -f "$CONF" ] || { echo "ERREUR: lancez 'init' d'abord." >&2; exit 1; }

  charger_config
  local adresse
  adresse="$(sudo -u orion -E "$VENV_PY" -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_btp.settings.production')
django.setup()
from apps.high_availability.mesh import adresse_overlay
from apps.high_availability.models import OrionHASettings
print(adresse_overlay(OrionHASettings.get_solo(), $rang))
")" || { echo "ERREUR: rang $rang hors du sous-réseau privé." >&2; exit 1; }

  if grep -q "PublicKey = $cle" "$CONF"; then
    echo "[mesh] Ce pair est déjà déclaré — rien à faire."
    return 0
  fi

  {
    echo ""
    echo "# Pair de rang $rang"
    echo "[Peer]"
    echo "PublicKey = $cle"
    # /32 et non /24 : chaque pair ne doit router QUE sa propre adresse. Un
    # /24 ferait se disputer la route par tous les pairs, et WireGuard
    # refuserait la seconde déclaration.
    echo "AllowedIPs = $adresse/32"
    [ -n "$endpoint" ] && echo "Endpoint = $endpoint"
    # Indispensable derrière un NAT : sans trafic sortant régulier, la
    # correspondance d'adresse du routeur expire et le pair devient
    # injoignable dans ce sens.
    echo "PersistentKeepalive = 25"
  } >> "$CONF"

  echo "[mesh] Pair de rang $rang ajouté ($adresse/32)."
  systemctl is-active --quiet "wg-quick@$IFACE" && cmd_up || true
}

cmd_hosts() {
  exiger_root
  local lignes
  lignes="$(sudo -u orion -E "$VENV_PY" "$MANAGE" ha_mesh_config --hosts)" || {
    echo "ERREUR: résolution privée indisponible — réglez le domaine de la grappe." >&2
    exit 1
  }
  [ -n "$lignes" ] || { echo "[mesh] Aucun nom à poser."; return 0; }

  # Le bloc entier est remplacé, jamais complété : des entrées accumulées au
  # fil des changements de rang laisseraient d'anciens noms pointer vers de
  # mauvaises adresses, ce qui est pire que pas d'entrée du tout.
  local tmp
  tmp="$(mktemp)"
  sed "/$MARQUEUR/,/# --- fin orion-mesh ---/d" /etc/hosts > "$tmp"
  {
    echo "$MARQUEUR"
    echo "$lignes"
    echo "# --- fin orion-mesh ---"
  } >> "$tmp"
  cat "$tmp" > /etc/hosts
  rm -f "$tmp"

  echo "[mesh] Résolution privée posée dans /etc/hosts :"
  echo "$lignes" | sed 's/^/  /'
}

# ─── Confiance SSH pour la synchronisation des médias ───────────────────────
# rsync passe par ssh en tant que compte orion. Sans paire de clés, la copie
# échoue en demandant un mot de passe — que BatchMode refuse de fournir, donc
# sans message exploitable. L'échange est manuel pour la même raison que celui
# des clés WireGuard : aucune des deux clés n'existe avant que les deux
# machines soient installées.
SSH_DIR="$ORION_HOME/.ssh"
CLE_MEDIA="$SSH_DIR/id_ed25519"

cmd_media_key() {
  exiger_root
  charger_config
  mkdir -p "$SSH_DIR"
  chown orion:orion "$SSH_DIR"
  chmod 700 "$SSH_DIR"

  if [ ! -f "$CLE_MEDIA" ]; then
    echo "[mesh] Génération de la clé de synchronisation..."
    sudo -u orion ssh-keygen -t ed25519 -N '' -C 'orion-media-sync' -f "$CLE_MEDIA" >/dev/null
  else
    echo "[mesh] Clé de synchronisation déjà présente — conservée."
  fi

  echo "[mesh] Clé publique à déclarer sur les AUTRES serveurs :"
  echo ""
  cat "$CLE_MEDIA.pub"
  echo ""
  echo "Sur chaque autre serveur, et en indiquant LE RANG DE CELUI-CI :"
  echo "  orion-mesh.sh trust ${ORION_MESH_RANK:-<rang>} \"\$(cat cle.pub)\""
}

cmd_trust() {
  exiger_root
  local rang="${1:-}" cle="${2:-}"
  [ -n "$rang" ] && [ -n "$cle" ] || { echo "Usage: trust RANG \"CLE_PUBLIQUE\"" >&2; exit 2; }

  local adresse
  adresse="$(sudo -u orion -E "$VENV_PY" -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_btp.settings.production')
django.setup()
from apps.high_availability.mesh import adresse_overlay
from apps.high_availability.models import OrionHASettings
print(adresse_overlay(OrionHASettings.get_solo(), $rang))
")" || { echo "ERREUR: rang $rang hors du sous-réseau privé." >&2; exit 1; }

  mkdir -p "$SSH_DIR"
  touch "$SSH_DIR/authorized_keys"
  chown -R orion:orion "$SSH_DIR"
  chmod 700 "$SSH_DIR"
  chmod 600 "$SSH_DIR/authorized_keys"

  local empreinte
  empreinte="$(printf '%s' "$cle" | awk '{print $2}')"
  if [ -n "$empreinte" ] && grep -q "$empreinte" "$SSH_DIR/authorized_keys"; then
    echo "[mesh] Cette clé est déjà déclarée — rien à faire."
    return 0
  fi

  # « from= » restreint la clé à l'adresse privée du pair : même divulguée,
  # elle ne servirait à rien depuis ailleurs. Les restrictions suivantes
  # réduisent le compte à ce dont rsync a besoin, rien de plus.
  printf 'from="%s",no-agent-forwarding,no-port-forwarding,no-pty,no-X11-forwarding %s\n' \
    "$adresse" "$cle" >> "$SSH_DIR/authorized_keys"

  echo "[mesh] Clé du serveur de rang $rang acceptée, restreinte à $adresse."
}

cmd_up()   { exiger_root; systemctl restart "wg-quick@$IFACE"; echo "[mesh] $IFACE actif."; }
cmd_down() { exiger_root; systemctl stop "wg-quick@$IFACE" || true; echo "[mesh] $IFACE arrêté."; }

cmd_status() {
  if ! command -v wg >/dev/null 2>&1; then
    echo "WireGuard n'est pas installé — lancez 'init'."
    return 0
  fi
  echo "=== Interface ==="
  wg show "$IFACE" 2>/dev/null || echo "  $IFACE inactive."
  echo ""
  echo "=== Pairs attendus d'après la grappe ==="
  sudo -u orion -E "$VENV_PY" "$MANAGE" ha_mesh_config --peers 2>/dev/null \
    | awk '{printf "  rang %s  %-16s %s\n", $1, $2, $3}' \
    || echo "  (indisponible)"
  echo ""
  echo "=== Joignabilité privée ==="
  sudo -u orion -E "$VENV_PY" "$MANAGE" ha_mesh_config --peers 2>/dev/null \
    | while read -r rang adresse hote reste; do
        if ping -c 1 -W 2 "$adresse" >/dev/null 2>&1; then
          echo "  $adresse ($hote) : OK"
        else
          echo "  $adresse ($hote) : AUCUNE REPONSE"
        fi
      done
}

case "${1:-}" in
  init)      shift; cmd_init "$@" ;;
  pubkey)    shift; cmd_pubkey "$@" ;;
  add-peer)  shift; cmd_add_peer "$@" ;;
  hosts)     shift; cmd_hosts "$@" ;;
  media-key) shift; cmd_media_key "$@" ;;
  trust)     shift; cmd_trust "$@" ;;
  up)        shift; cmd_up "$@" ;;
  down)      shift; cmd_down "$@" ;;
  status)    shift; cmd_status "$@" ;;
  -h|--help|'') usage 0 ;;
  *)         echo "Commande inconnue : $1" >&2; usage 2 ;;
esac
