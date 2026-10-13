#!/usr/bin/env bash
# ============================================================================
# Orion ERP Appliance — Mise à jour complète (OS + Docker + Node + Python + ERP)
#
# Trois modes, parce que la voie applicative ne doit pas être la seule.
# `manage.py run_system_update` apporte la trace d'audit, le point de rollback
# et les vérifications post-update, mais sa PREMIÈRE instruction est une
# lecture en base (SystemUpdateSettings). Elle est donc indisponible
# précisément quand on en a le plus besoin : base injoignable, migration
# cassée, Django qui ne démarre pas, ou simplement `update_enabled` à faux.
#
#   --direct       git pull + migrations + statiques + builds, SANS Django.
#                  Aucune dépendance à la base ni au mécanisme applicatif.
#                  À utiliser quand l'ERP est en panne.
#   --django-only  n'utilise que le mécanisme applicatif, sans repli.
#   (par défaut)   mécanisme applicatif, repli direct s'il échoue, puis
#                  nouvelle tentative pour restaurer la trace d'audit.
#
# Rollback applicatif : manage.py rollback_system_update
# ============================================================================

set -euo pipefail

ORION_HOME="/opt/orion"
ENV_FILE="$ORION_HOME/backend/.env"
VENV_PY="$ORION_HOME/backend/.venv/bin/python"
MANAGE="$ORION_HOME/backend/manage.py"

MODE='auto'
while [ $# -gt 0 ]; do
  case "$1" in
    --direct)      MODE='direct' ;;
    --django-only) MODE='django' ;;
    -h|--help)     sed -n '2,20p' "$0"; exit 0 ;;
    *)             echo "Option inconnue : $1" >&2; sed -n '11,16p' "$0" >&2; exit 2 ;;
  esac
  shift
done

[ -f "$ENV_FILE" ] || { echo "ERREUR: $ENV_FILE introuvable — appliance non configurée."; exit 1; }
set -a; . "$ENV_FILE"; set +a

echo "======================================"
echo " Mise à jour Orion ERP Appliance"
echo "======================================"

echo "[1/6] Mise à jour Ubuntu..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y

echo "[2/6] Mise à jour images Docker (MySQL/Redis)..."
docker compose -f "$ORION_HOME/docker/docker-compose.yml" pull
docker compose -f "$ORION_HOME/docker/docker-compose.yml" up -d

echo "[3/6] Mise à jour Node.js (paquets globaux) et dépendances Python (venv)..."
npm update -g --silent || true
"$VENV_PY" -m pip install --upgrade pip --quiet
"$VENV_PY" -m pip install --no-cache-dir -r "$ORION_HOME/backend/requirements.txt"

echo "[4/6] Mise à jour applicative Orion ERP (git pull + migrations)..."

# Mise à jour sans aucune dépendance au mécanisme applicatif : seuls git, pip
# et les commandes Django de base sont requis. C'est la voie de survie quand
# l'ERP est en panne — un bug DANS le mécanisme de mise à jour serait sinon
# irrécupérable, son propre correctif ne pouvant arriver que par lui.
# Constaté en production avec « Commande de sauvegarde non configurée », qui
# bloquait toute mise à jour par défaut.
maj_directe() {
  if ! sudo -u orion git -C "$ORION_HOME/backend" pull --ff-only; then
    echo "  ERREUR: git pull impossible (arbre modifié, ou branche suivie différente)." >&2
    echo "          Vérifiez : git -C $ORION_HOME/backend status" >&2
    return 1
  fi
  sudo -u orion -E "$VENV_PY" "$MANAGE" migrate --noinput
  sudo -u orion -E "$VENV_PY" "$MANAGE" collectstatic --noinput >/dev/null
  echo "  code récupéré, schéma migré, statiques collectés."
}

maj_applicative() {
  sudo -u orion -E "$VENV_PY" "$MANAGE" run_system_update --no-confirm
}

case "$MODE" in
  direct)
    echo "  mode --direct : le mécanisme applicatif est volontairement ignoré."
    maj_directe || echo "  ATTENTION: mise à jour directe échouée." >&2
    ;;
  django)
    echo "  mode --django-only : aucun repli."
    maj_applicative || echo "  ATTENTION: run_system_update a échoué." >&2
    ;;
  *)
    if ! maj_applicative; then
      echo "  ATTENTION: run_system_update a échoué — repli sur une mise à jour directe." >&2
      if maj_directe; then
        # Nouvelle tentative avec le code à jour : si l'échec venait du
        # mécanisme lui-même, il est désormais corrigé. Cela restaure la trace
        # SystemUpdateRun et le point de rollback, que le repli ne crée pas.
        echo "  nouvelle tentative du mécanisme normal..."
        maj_applicative \
          || echo "  ATTENTION: run_system_update échoue encore — cause applicative, voir /opt/orion/logs/errors.log." >&2
      fi
    fi
    ;;
esac

# Rafraichit /opt/orion/scripts/ depuis le depot.
#
# Ces scripts n'arrivaient QUE par le payload cloud-init, copie une seule
# fois au provisioning (07-backup-cron.sh). Aucune mise a jour ne les
# touchait : un correctif apporte a refresh_allowed_hosts.sh, orion-disk.sh
# ou orion-cloudflare.sh n'atteignait jamais une appliance deja installee,
# alors meme que le code applicatif, lui, se mettait a jour.
#
# Le renommage (mv) est essentiel : bash lit son script au fur et a mesure de
# l'execution. Un cp ecraserait le fichier EN PLACE, et le shell en cours
# reprendrait sa lecture a son ancien decalage dans le nouveau contenu --
# donc au milieu d'une ligne. Un mv cree un nouvel inode ; le processus en
# cours garde l'ancien ouvert et se termine proprement sur la version avec
# laquelle il a demarre.
rafraichir_scripts() {
  local source_scripts="$ORION_HOME/backend/deployment/proxmox-appliance/scripts"
  if [ ! -d "$source_scripts" ]; then
    echo "  scripts absents du depot ($source_scripts) — ignores."
    return 0
  fi

  local sas
  sas="$(mktemp -d)"
  cp "$source_scripts"/*.sh "$sas"/ 2>/dev/null || true
  cp "$source_scripts"/*.py "$sas"/ 2>/dev/null || true

  local poses=0
  for fichier in "$sas"/*; do
    [ -f "$fichier" ] || continue
    chmod +x "$fichier"
    mv -f "$fichier" "$ORION_HOME/scripts/$(basename "$fichier")"
    poses=$((poses + 1))
  done
  rm -rf "$sas"

  chown -R orion:orion "$ORION_HOME/scripts" 2>/dev/null || true
  echo "  $poses script(s) d'exploitation rafraichis depuis le depot."
  echo "  (update_orion.sh lui-meme prendra effet au prochain lancement)"
}
rafraichir_scripts || echo "  ATTENTION: rafraichissement des scripts echoue." >&2

# Rafraichit aussi les unites systemd, pour la meme raison que les scripts :
# elles n'arrivaient que par le provisioning (03-systemd-units.sh), donc un
# correctif apporte a orion-backend.service n'atteignait jamais une appliance
# deja installee. Constate douloureusement : le prefixe ExecStartPre=- qui
# empeche un script de confort de rendre l'ERP indemarrable n'aurait pas pu
# etre livre par une mise a jour.
#
# Un cp suffit ici, contrairement aux scripts : systemd relit les unites au
# daemon-reload et ne tient pas de descripteur ouvert sur le fichier. Le
# depot est la source de verite, le provisioning les copiant deja telles
# quelles, sans rendu de variables.
rafraichir_unites_systemd() {
  local source_unites="$ORION_HOME/backend/deployment/proxmox-appliance/systemd"
  if [ ! -d "$source_unites" ]; then
    echo "  unites systemd absentes du depot — ignorees."
    return 0
  fi
  cp "$source_unites"/*.service /etc/systemd/system/ 2>/dev/null || true
  cp "$source_unites"/*.timer   /etc/systemd/system/ 2>/dev/null || true
  systemctl daemon-reload
  echo "  unites systemd rafraichies depuis le depot."
}
rafraichir_unites_systemd || echo "  ATTENTION: rafraichissement des unites echoue." >&2

# Recompile les catalogues : un .po mis a jour par le git pull resterait
# sans effet tant que son .mo n'est pas regenere.
sudo -u orion -E "$VENV_PY" "$MANAGE" compilemessages \
  || echo "  ATTENTION: compilemessages a echoue, traductions inchangees."

echo "[5/6] Reconstruction des frontends SIÈCLE / LUNEA / NÉOSTRUCTURA..."
for store in siecle-store:siecle lunea-store:lunea; do
  SRC_DIR="${store%%:*}"; DEST_NAME="${store##*:}"
  STORE_PATH="$ORION_HOME/backend/frontend/$SRC_DIR"
  if [ -d "$STORE_PATH" ]; then
    (cd "$STORE_PATH" && npm ci --silent && \
      VITE_API_BASE_URL="https://${ORION_LOGIN_DOMAIN:-$ORION_FRONTEND_DOMAIN}/api/v1" npm run build) \
      && rm -rf "$ORION_HOME/$DEST_NAME"/* \
      && cp -r "$STORE_PATH/dist/." "$ORION_HOME/$DEST_NAME/" \
      || echo "  ATTENTION: build $SRC_DIR échoué — version précédente conservée."
  fi
done
chown -R orion:orion "$ORION_HOME/siecle" "$ORION_HOME/lunea"

# NÉOSTRUCTURA à part : aucune URL d'API à injecter au build (appels relatifs,
# proxifiés par Nginx), et pas de service applicatif à redémarrer puisque c'est
# Nginx qui sert les fichiers — d'où le chmod, www-data doit pouvoir les lire.
NS_PATH="$ORION_HOME/backend/frontend/neostructura-site"
if [ -d "$NS_PATH" ]; then
  if (cd "$NS_PATH" && npm ci --silent && npm run build); then
    mkdir -p "$ORION_HOME/neostructura"
    rm -rf "$ORION_HOME/neostructura"/*
    cp -r "$NS_PATH/dist/." "$ORION_HOME/neostructura/"
    chown -R orion:orion "$ORION_HOME/neostructura"
    chmod -R a+rX "$ORION_HOME/neostructura"
  else
    echo "  ATTENTION: build NÉOSTRUCTURA échoué — version précédente conservée."
  fi
fi

echo "[6/6] Redémarrage des services..."
systemctl restart orion-backend.service orion-frontend.service
systemctl restart siecle-frontend.service lunea-frontend.service
# Celery charge le code applicatif au demarrage : sans redemarrage, les
# taches continueraient de tourner sur l'ancienne version.
systemctl restart orion-celery.service orion-celery-beat.service || true
systemctl reload nginx || true

sleep 3
systemctl --no-pager status orion-backend.service orion-frontend.service \
  siecle-frontend.service lunea-frontend.service --lines=0 || true

echo ""
echo "Mise à jour terminée."
echo "En cas de problème : sudo -u orion $VENV_PY $MANAGE rollback_system_update"
