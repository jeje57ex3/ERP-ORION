#!/usr/bin/env bash
# Orion ERP Appliance — Stage A / 04
# Copie le template Nginx en place. Les domaines réels (__*__) sont substitués
# par first-boot-wizard.sh une fois connus ; jusque-là, Nginx sert un vhost
# placeholder pour ne pas planter au démarrage.

set -euo pipefail
exec >> /var/log/orion-provision.log 2>&1

echo "=== [04] Nginx — $(date -u +%FT%TZ) ==="

PAYLOAD_DIR="/opt/orion-appliance"
mkdir -p /opt/orion/nginx

cp "$PAYLOAD_DIR/nginx/orion-proxmox.conf.tmpl" /opt/orion/nginx/orion-proxmox.conf.tmpl

# Vhost placeholder (domaines .invalid) tant que le wizard n'a pas tourné —
# évite une erreur de résolution nginx -t sur des server_name vides.
sed \
  -e 's/__LOGIN_DOMAIN__/login.invalid/g' \
  -e 's/__ORION_DOMAIN__/orion.invalid/g' \
  -e 's/__SIECLE_DOMAIN__/siecle.invalid/g' \
  -e 's/__LUNEA_DOMAIN__/lunea.invalid/g' \
  "$PAYLOAD_DIR/nginx/orion-proxmox.conf.tmpl" > /etc/nginx/sites-available/orion.conf

ln -sfn /etc/nginx/sites-available/orion.conf /etc/nginx/sites-enabled/orion.conf
rm -f /etc/nginx/sites-enabled/default

nginx -t && systemctl enable --now nginx && systemctl reload nginx || true

echo "[04] Terminé."
