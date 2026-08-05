#!/usr/bin/env bash
# Orion ERP Appliance — Stage A / 03
# Installe les unités systemd. Ne démarre PAS les services applicatifs
# (backend/frontend/siecle/lunea/health) : ils attendent le wizard (Stage B),
# qui écrit .env, construit les frontends et les démarre.

set -euo pipefail
exec >> /var/log/orion-provision.log 2>&1

echo "=== [03] Unités systemd — $(date -u +%FT%TZ) ==="

PAYLOAD_DIR="/opt/orion-appliance"

cp "$PAYLOAD_DIR"/systemd/*.service "$PAYLOAD_DIR"/systemd/*.timer /etc/systemd/system/

systemctl daemon-reload

# Infra DB/Redis : activée mais démarrée seulement par le wizard, une fois .env
# écrit (docker-compose.yml lit les identifiants MySQL depuis ce fichier).
systemctl enable orion-db-stack.service

# Services applicatifs : activés (démarrage auto aux reboots suivants) mais pas
# démarrés — le wizard s'en charge une fois .env écrit et les frontends buildés.
systemctl enable orion-backend.service
systemctl enable orion-frontend.service
systemctl enable siecle-frontend.service
systemctl enable lunea-frontend.service

# Le wizard démarre lui-même le timer de santé une fois les services actifs.
systemctl disable orion-health.timer 2>/dev/null || true

systemctl enable orion-first-boot.service

echo "[03] Terminé."
