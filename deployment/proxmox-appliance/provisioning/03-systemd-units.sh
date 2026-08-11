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
set -a; . "$ENV_FILE"; set +a

echo "[03] Démarrage MySQL / Redis..."
systemctl enable --now orion-db-stack.service
"$PAYLOAD_DIR/scripts/wait_for_port.sh" 127.0.0.1 6379 60

# L'image MySQL officielle démarre un serveur TEMPORAIRE pour le bootstrap
# (création base/utilisateur) qui n'écoute QUE sur le socket Unix local, pas
# sur le port 3306 (confirmé dans les logs du conteneur : "port: 0"). Le
# healthcheck docker-compose.yml utilise `-h localhost`, donc mysqladmin s'y
# connecte via CE socket et peut répondre "healthy" alors que le port 3306
# (celui que Django utilise réellement, DB_HOST=127.0.0.1) ne sera prêt que
# quelques secondes plus tard, une fois le VRAI serveur démarré. On teste
# donc ici exactement le même chemin que Django : une vraie connexion TCP.
echo "[03] Attente de MySQL sur le port TCP 3306 (pas juste le socket local)..."
DB_READY=0
for i in $(seq 1 60); do
  if docker exec orion-db mysqladmin ping -h 127.0.0.1 -P 3306 \
      -u"${DB_USER:-orion}" -p"${DB_PASSWORD:-}" --silent >/dev/null 2>&1; then
    DB_READY=1
    break
  fi
  sleep 3
done
if [ "$DB_READY" -ne 1 ]; then
  echo "ATTENTION: MySQL ne répond pas sur le port 3306 après ~180s — on continue quand même." >&2
fi

# ─── Migrations + fichiers statiques ───────────────────────────────────────────
echo "[03] Migrations Django..."

# Filet de sécurité supplémentaire : même le test TCP ci-dessus pourrait dans
# de rares cas taper une micro-coupure ("Lost connection to MySQL server
# during query"). On réessaie plutôt que d'essayer d'affiner encore le
# timing.
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

echo "[03] Peuplement du catalogue de widgets dashboard..."
sudo -u orion -E "$VENV_PY" "$MANAGE" seed_dashboard_widgets

echo "[03] Peuplement des langues (sélecteur de langue ERP)..."
sudo -u orion -E "$VENV_PY" "$MANAGE" seed_languages

echo "[03] Paramètres mises à jour (+ jeton GitHub si dépôt privé)..."
sudo -u orion -E "$VENV_PY" "$MANAGE" seed_system_updates

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
