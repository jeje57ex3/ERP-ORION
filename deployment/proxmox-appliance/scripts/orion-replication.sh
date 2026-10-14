#!/usr/bin/env bash
# ============================================================================
# Orion ERP Appliance — Réplication MySQL entre sites
#
# Sans réplication, la haute disponibilité est décorative : une bascule
# promouvrait une base dépourvue des données de l'autre site. Les devis, les
# clients, les factures du serveur 1 seraient simplement absents du serveur 2.
#
# MySQL n'écoute que sur 127.0.0.1:3306 (docker-compose.yml), donc inatteignable
# depuis l'extérieur de la VM. C'est volontaire et il ne faut PAS l'ouvrir au
# public : la réplication voyagerait en clair sur Internet. Ce script ne
# desserre l'écoute que vers l'adresse du réseau privé WireGuard, jamais vers
# 0.0.0.0.
#
# Usage, sur le SERVEUR SOURCE (rang 1) :
#   orion-replication.sh expose           Écoute aussi sur l'adresse privée
#   orion-replication.sh grant RANG       Crée le compte de réplication du réplica
#   orion-replication.sh coordonnees      Position courante du journal binaire
#
# Usage, sur le RÉPLICA :
#   orion-replication.sh follow RANG_SOURCE MOT_DE_PASSE
#   orion-replication.sh status
#   orion-replication.sh stop
#
# L'ordre compte : expose puis grant sur la source, follow sur le réplica.
# ============================================================================

set -euo pipefail

ORION_HOME="/opt/orion"
ENV_FILE="$ORION_HOME/backend/.env"
# commun.sh : lecture du .env sans l'executer, et $HOME garanti. Une seule
# valeur a espaces non citee suffisait a tuer ce script sur un
# « -n: command not found » (exit 127) qui ne nommait ni la cle ni le fichier.
ICI_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for _candidat in \
  "$ICI_SCRIPT/commun.sh" \
  /opt/orion/scripts/commun.sh \
  /opt/orion/backend/deployment/proxmox-appliance/provisioning/lib/commun.sh
do
  if [ -f "$_candidat" ]; then . "$_candidat"; break; fi
done
if ! declare -f charger_env >/dev/null 2>&1; then
  echo "ERREUR: commun.sh introuvable (attendu dans /opt/orion/scripts/)." >&2
  exit 1
fi
VENV_PY="$ORION_HOME/backend/.venv/bin/python"
MANAGE="$ORION_HOME/backend/manage.py"
COMPOSE="$ORION_HOME/docker/docker-compose.yml"
CONTENEUR="orion-db"
UTILISATEUR_REPL="orion_repl"

usage() { sed -n '2,25p' "$0"; exit "${1:-0}"; }

exiger_root() { [ "$(id -u)" -eq 0 ] || { echo "ERREUR: à lancer en root." >&2; exit 1; }; }

charger_env() {
  [ -f "$ENV_FILE" ] || { echo "ERREUR: $ENV_FILE introuvable." >&2; exit 1; }
  # Même normalisation que les autres scripts : une valeur à espaces non
  # protégée rend le sourçage fatal et parfaitement opaque.
  if grep -qE '^[A-Za-z_]*_COMMAND=[^"]*[[:space:]]' "$ENV_FILE"; then
    sed -i -E 's/^([A-Za-z_]*_COMMAND)=([^"].*)$/\1="\2"/' "$ENV_FILE"
  fi
  charger_env "$ENV_FILE"
}

adresse_privee_du_rang() {
  sudo -u orion -E "$VENV_PY" -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_btp.settings.production')
django.setup()
from apps.high_availability.mesh import adresse_overlay
from apps.high_availability.models import OrionHASettings
print(adresse_overlay(OrionHASettings.get_solo(), $1))
"
}

notre_adresse_privee() {
  sudo -u orion -E "$VENV_PY" "$MANAGE" ha_mesh_config \
    | sed -n 's/^ORION_MESH_ADDRESS=//p'
}

sql_root() {
  docker exec -i "$CONTENEUR" mysql -uroot -p"$DB_ROOT_PASSWORD" --batch --skip-column-names "$@"
}

# ─── Sur la source : ouvrir l'écoute vers le réseau privé seulement ──────────
cmd_expose() {
  exiger_root
  charger_env

  local privee
  privee="$(notre_adresse_privee)"
  [ -n "$privee" ] || { echo "ERREUR: adresse privée inconnue — lancez orion-mesh.sh init." >&2; exit 1; }

  if grep -q "\"$privee:3306:3306\"" "$COMPOSE"; then
    echo "[repl] L'écoute sur $privee:3306 est déjà en place."
    return 0
  fi

  cp "$COMPOSE" "$COMPOSE.avant-replication"

  # On AJOUTE une liaison, on ne remplace pas 127.0.0.1 : l'application y
  # accède toujours par la boucle locale (DB_HOST=127.0.0.1), et la couper
  # arrêterait l'ERP net.
  sed -i "s#\"127.0.0.1:3306:3306\"#\"127.0.0.1:3306:3306\"\n      - \"$privee:3306:3306\"#" "$COMPOSE"

  if ! grep -q "\"$privee:3306:3306\"" "$COMPOSE"; then
    echo "ERREUR: la liaison n'a pas pu être ajoutée — $COMPOSE inchangé." >&2
    mv "$COMPOSE.avant-replication" "$COMPOSE"
    exit 1
  fi

  echo "[repl] Redémarrage du conteneur de base..."
  docker compose -f "$COMPOSE" up -d

  if command -v ufw >/dev/null 2>&1; then
    local sous_reseau
    sous_reseau="$(sudo -u orion -E "$VENV_PY" "$MANAGE" ha_mesh_config | sed -n 's/^ORION_MESH_SUBNET=//p')"
    [ -n "$sous_reseau" ] && ufw allow from "$sous_reseau" to any port 3306 proto tcp >/dev/null 2>&1 || true
    echo "[repl] Pare-feu : 3306 ouvert au seul sous-réseau privé $sous_reseau."
  fi

  echo "[repl] MySQL écoute désormais sur 127.0.0.1 ET $privee — jamais en public."
}

# ─── Sur la source : compte de réplication pour un réplica donné ────────────
cmd_grant() {
  exiger_root
  charger_env
  local rang="${1:-}"
  [ -n "$rang" ] || { echo "Usage: grant RANG" >&2; exit 2; }

  local hote_replica mot_de_passe
  hote_replica="$(adresse_privee_du_rang "$rang")"
  mot_de_passe="$("$VENV_PY" -c 'import secrets; print(secrets.token_urlsafe(24))')"

  # Le compte est restreint à l'adresse privée du réplica : même si le port
  # était un jour exposé par erreur, ces identifiants ne serviraient à rien
  # depuis ailleurs.
  sql_root <<SQL
CREATE USER IF NOT EXISTS '$UTILISATEUR_REPL'@'$hote_replica' IDENTIFIED BY '$mot_de_passe';
ALTER USER '$UTILISATEUR_REPL'@'$hote_replica' IDENTIFIED BY '$mot_de_passe';
GRANT REPLICATION SLAVE, REPLICATION CLIENT ON *.* TO '$UTILISATEUR_REPL'@'$hote_replica';
FLUSH PRIVILEGES;
SQL

  echo "[repl] Compte '$UTILISATEUR_REPL'@'$hote_replica' créé."
  echo ""
  echo "Lancez ceci sur le serveur de rang $rang, en remplaçant le mot de passe :"
  echo ""
  echo "  orion-replication.sh follow $(sudo -u orion -E "$VENV_PY" "$MANAGE" ha_mesh_config | sed -n 's/^ORION_MESH_RANK=//p') '$mot_de_passe'"
  echo ""
  echo "Le mot de passe n'est affiché qu'ici et n'est stocké nulle part :"
  echo "relancez 'grant' si vous le perdez, il sera simplement remplacé."
}

cmd_coordonnees() {
  exiger_root
  charger_env
  echo "=== Position du journal binaire ==="
  sql_root -e "SHOW MASTER STATUS\G" 2>/dev/null \
    || sql_root -e "SHOW BINARY LOG STATUS\G" 2>/dev/null \
    || echo "  Journal binaire indisponible : log_bin est-il actif ?"
}

# ─── Sur le réplica : suivre la source ──────────────────────────────────────
cmd_follow() {
  exiger_root
  charger_env
  local rang_source="${1:-}" mot_de_passe="${2:-}"
  [ -n "$rang_source" ] && [ -n "$mot_de_passe" ] \
    || { echo "Usage: follow RANG_SOURCE MOT_DE_PASSE" >&2; exit 2; }

  local hote_source
  hote_source="$(adresse_privee_du_rang "$rang_source")"

  echo "[repl] Vérification de la joignabilité de $hote_source:3306..."
  if ! timeout 6 bash -c "echo > /dev/tcp/$hote_source/3306" 2>/dev/null; then
    echo "ERREUR: $hote_source:3306 injoignable." >&2
    echo "        Le réseau privé est-il actif (orion-mesh.sh status) et" >&2
    echo "        'expose' a-t-il été lancé sur la source ?" >&2
    exit 1
  fi

  # STOP avant CHANGE : MySQL refuse de modifier la source tant que les fils
  # tournent, avec un message qui ne le dit pas clairement.
  sql_root -e "STOP REPLICA" 2>/dev/null || sql_root -e "STOP SLAVE" 2>/dev/null || true

  if ! sql_root <<SQL
CHANGE REPLICATION SOURCE TO
  SOURCE_HOST='$hote_source',
  SOURCE_PORT=3306,
  SOURCE_USER='$UTILISATEUR_REPL',
  SOURCE_PASSWORD='$mot_de_passe',
  SOURCE_AUTO_POSITION=1,
  GET_SOURCE_PUBLIC_KEY=1;
START REPLICA;
SQL
  then
    echo "[repl] Syntaxe MySQL 8 refusée — tentative en syntaxe ancienne (MariaDB)..."
    sql_root <<SQL
CHANGE MASTER TO
  MASTER_HOST='$hote_source',
  MASTER_PORT=3306,
  MASTER_USER='$UTILISATEUR_REPL',
  MASTER_PASSWORD='$mot_de_passe',
  MASTER_USE_GTID=slave_pos;
START SLAVE;
SQL
  fi

  echo "[repl] Réplication démarrée depuis $hote_source."
  sleep 3
  cmd_status
}

cmd_status() {
  charger_env
  echo "=== État de la réplication (vu du serveur local) ==="
  sudo -u orion -E "$VENV_PY" "$MANAGE" ha_replication_status || true
}

cmd_stop() {
  exiger_root
  charger_env
  sql_root -e "STOP REPLICA" 2>/dev/null || sql_root -e "STOP SLAVE" 2>/dev/null || true
  echo "[repl] Réplication arrêtée. La base reste inscriptible ou non selon read_only."
}

case "${1:-}" in
  expose)      shift; cmd_expose "$@" ;;
  grant)       shift; cmd_grant "$@" ;;
  coordonnees) shift; cmd_coordonnees "$@" ;;
  follow)      shift; cmd_follow "$@" ;;
  status)      shift; cmd_status "$@" ;;
  stop)        shift; cmd_stop "$@" ;;
  -h|--help|'') usage 0 ;;
  *)           echo "Commande inconnue : $1" >&2; usage 2 ;;
esac
