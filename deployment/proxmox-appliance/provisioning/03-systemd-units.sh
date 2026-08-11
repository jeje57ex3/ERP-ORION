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
"$PAYLOAD_DIR/scripts/wait_for_port.sh" 127.0.0.1 6379 60

# Le port 3306 peut répondre pendant l'initialisation interne de l'image
# MySQL (bootstrap de la base/des identifiants) avant que le VRAI serveur ne
# démarre — un simple test de port peut donc réussir juste avant que MySQL
# ne se redémarre en interne, coupant la connexion de migrate en plein vol
# ("Lost connection to MySQL server during query"). On attend plutôt le
# statut "healthy" du conteneur (healthcheck docker-compose.yml, qui teste
# une vraie authentification avec les identifiants réels).
echo "[03] Attente de MySQL (healthcheck du conteneur)..."
DB_HEALTHY=0
DB_STATUS="starting"
for i in $(seq 1 60); do
  DB_STATUS="$(docker inspect --format='{{.State.Health.Status}}' orion-db 2>/dev/null || echo "starting")"
  if [ "$DB_STATUS" = "healthy" ]; then DB_HEALTHY=1; break; fi
  sleep 3
done
if [ "$DB_HEALTHY" -ne 1 ]; then
  echo "ATTENTION: orion-db pas 'healthy' après ~180s (statut: $DB_STATUS) — on continue quand même." >&2
fi

# ─── Migrations + fichiers statiques ───────────────────────────────────────────
echo "[03] Migrations Django..."
set -a; . "$ENV_FILE"; set +a

# Même une fois "healthy", MySQL (image officielle) peut encore redémarrer
# une dernière fois en interne juste après avoir répondu au ping — la toute
# première tentative de connexion peut donc tomber sur cette micro-coupure
# ("Lost connection to MySQL server during query"). On réessaie plutôt que
# d'essayer d'affiner encore le timing du healthcheck.
MIGRATE_OK=0
for attempt in 1 2 3 4 5; do
  if sudo -u orion -E "$VENV_PY" "$MANAGE" migrate --noinput; then
    MIGRATE_OK=1
    break
  fi
  echo "[03] migrate a échoué (tentative $attempt/5) — nouvelle tentative dans 10s..." >&2
  sleep 10
done
if [ "$MIGRATE_OK" -ne 1 ]; then
  echo "[03] ERREUR: migrate a échoué après 5 tentatives." >&2
  exit 1
fi

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
