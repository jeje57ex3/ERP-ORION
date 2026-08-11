#!/usr/bin/env bash
# Orion ERP Appliance — Stage A / 03
# Installe les unités systemd, démarre l'infrastructure (MySQL/Redis) et le
# backend Django (migrations + collectstatic déjà faisables ici, backend.env
# généré par 02-deploy-orion.sh) puis build+démarre les frontends SIÈCLE/LUNEA
# si un domaine Login a été fourni au déploiement (deploy-info.env).
# Aucune étape interactive : le compte administrateur se crée ensuite via le
# navigateur (/setup/).

set -euo pipefail
exec >> /var/log/orion-provision.log 2>&1

echo "=== [03] Unités systemd + démarrage des services — $(date -u +%FT%TZ) ==="

PAYLOAD_DIR="/opt/orion-appliance"
ORION_HOME="/opt/orion"
ENV_FILE="$ORION_HOME/backend/.env"
VENV_PY="$ORION_HOME/backend/.venv/bin/python"
MANAGE="$ORION_HOME/backend/manage.py"

cp "$PAYLOAD_DIR"/systemd/*.service "$PAYLOAD_DIR"/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload

# ─── Infrastructure MySQL / Redis ──────────────────────────────────────────────
echo "[03] Démarrage MySQL / Redis..."
systemctl enable --now orion-db-stack.service
"$PAYLOAD_DIR/scripts/wait_for_port.sh" 127.0.0.1 3306 120
"$PAYLOAD_DIR/scripts/wait_for_port.sh" 127.0.0.1 6379 60
sleep 5

# ─── Migrations + fichiers statiques ───────────────────────────────────────────
echo "[03] Migrations Django..."
set -a; . "$ENV_FILE"; set +a
sudo -u orion -E "$VENV_PY" "$MANAGE" migrate --noinput

echo "[03] Collecte des fichiers statiques..."
sudo -u orion -E "$VENV_PY" "$MANAGE" collectstatic --noinput

# ─── Backend Django ─────────────────────────────────────────────────────────────
echo "[03] Démarrage orion-backend..."
systemctl enable --now orion-backend.service
systemctl enable --now orion-frontend.service

# ─── Frontends SIÈCLE / LUNEA (nécessitent un domaine Login connu) ─────────────
if [ -n "${LOGIN_DOMAIN:-}" ]; then
  echo "[03] Build des frontends SIÈCLE / LUNEA (API: https://$LOGIN_DOMAIN/api/v1)..."
  mkdir -p "$ORION_HOME/siecle" "$ORION_HOME/lunea"

  if [ -d "$ORION_HOME/backend/frontend/siecle-store" ]; then
    (cd "$ORION_HOME/backend/frontend/siecle-store" && \
      VITE_API_BASE_URL="https://$LOGIN_DOMAIN/api/v1" npm run build) \
      && rm -rf "$ORION_HOME/siecle"/* \
      && cp -r "$ORION_HOME/backend/frontend/siecle-store/dist/." "$ORION_HOME/siecle/" \
      && { chown -R orion:orion "$ORION_HOME/siecle"; systemctl enable --now siecle-frontend.service; } \
      || echo "ATTENTION: build SIÈCLE échoué — service non démarré."
  fi

  if [ -d "$ORION_HOME/backend/frontend/lunea-store" ]; then
    (cd "$ORION_HOME/backend/frontend/lunea-store" && \
      VITE_API_BASE_URL="https://$LOGIN_DOMAIN/api/v1" npm run build) \
      && rm -rf "$ORION_HOME/lunea"/* \
      && cp -r "$ORION_HOME/backend/frontend/lunea-store/dist/." "$ORION_HOME/lunea/" \
      && { chown -R orion:orion "$ORION_HOME/lunea"; systemctl enable --now lunea-frontend.service; } \
      || echo "ATTENTION: build LUNEA échoué — service non démarré."
  fi
else
  echo "[03] Aucun domaine Login fourni au déploiement — frontends SIÈCLE/LUNEA non construits."
  echo "     (les construire plus tard une fois un domaine configuré, voir PROXMOX.md)"
fi

systemctl enable --now orion-health.timer

echo "[03] Terminé."
