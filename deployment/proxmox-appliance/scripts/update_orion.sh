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
sudo -u orion -E "$VENV_PY" "$MANAGE" run_system_update --no-confirm

echo "[5/6] Reconstruction des frontends SIÈCLE / LUNEA..."
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

echo "[6/6] Redémarrage des services..."
systemctl restart orion-backend.service orion-frontend.service
systemctl restart siecle-frontend.service lunea-frontend.service
systemctl reload nginx || true

sleep 3
systemctl --no-pager status orion-backend.service orion-frontend.service \
  siecle-frontend.service lunea-frontend.service --lines=0 || true

echo ""
echo "Mise à jour terminée."
echo "En cas de problème : sudo -u orion $VENV_PY $MANAGE rollback_system_update"
