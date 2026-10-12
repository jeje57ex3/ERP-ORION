#!/usr/bin/env bash
# Orion ERP Appliance — Mise à jour complète (OS + Docker + Node + Python + Orion ERP).
# La partie applicative (git pull, migrations) est déléguée à
# apps.system_updates (manage.py run_system_update), qui gère déjà la
# sauvegarde préventive et les vérifications post-update — on ne la réimplémente pas.
# Rollback applicatif disponible via : manage.py rollback_system_update

set -euo pipefail

ORION_HOME="/opt/orion"
ENV_FILE="$ORION_HOME/backend/.env"
VENV_PY="$ORION_HOME/backend/.venv/bin/python"
MANAGE="$ORION_HOME/backend/manage.py"

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

# Repli indispensable : sans lui, un bug DANS le mécanisme de mise à jour est
# irrécupérable. run_system_update est seul à déclencher le git pull, donc son
# propre correctif ne peut jamais arriver — il faut alors intervenir à la main
# depuis l'hyperviseur. Constaté en production avec « Commande de sauvegarde
# non configurée », qui bloquait toute mise à jour par défaut.
if ! sudo -u orion -E "$VENV_PY" "$MANAGE" run_system_update --no-confirm; then
  echo "  ATTENTION: run_system_update a échoué — repli sur une mise à jour directe." >&2

  if sudo -u orion git -C "$ORION_HOME/backend" pull --ff-only; then
    sudo -u orion -E "$VENV_PY" "$MANAGE" migrate --noinput
    sudo -u orion -E "$VENV_PY" "$MANAGE" collectstatic --noinput >/dev/null
    echo "  code récupéré et schéma migré par le repli."

    # Nouvelle tentative avec le code à jour : si l'échec venait du mécanisme
    # lui-même, il est désormais corrigé. Cela restaure aussi la trace
    # SystemUpdateRun et le point de rollback, que le repli ne crée pas.
    echo "  nouvelle tentative du mécanisme normal..."
    sudo -u orion -E "$VENV_PY" "$MANAGE" run_system_update --no-confirm \
      || echo "  ATTENTION: run_system_update échoue encore — cause applicative, voir /opt/orion/logs/errors.log." >&2
  else
    echo "  ERREUR: git pull impossible (arbre modifié, ou branche suivie différente)." >&2
    echo "          Vérifiez : git -C $ORION_HOME/backend status" >&2
  fi
fi

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
