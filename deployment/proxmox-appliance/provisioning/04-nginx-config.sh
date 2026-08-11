#!/usr/bin/env bash
# Orion ERP Appliance — Stage A / 04
# Rend le template Nginx avec les domaines réels de ce déploiement
# (deploy-info.env, fournis à deploy.sh) — un domaine laissé vide retombe sur
# un server_name .invalid pour ce vhost précis, sans faire planter nginx -t.

set -euo pipefail
exec >> /var/log/orion-provision.log 2>&1

echo "=== [04] Nginx — $(date -u +%FT%TZ) ==="

PAYLOAD_DIR="/opt/orion-appliance"
mkdir -p /opt/orion/nginx

cp "$PAYLOAD_DIR/nginx/orion-proxmox.conf.tmpl" /opt/orion/nginx/orion-proxmox.conf.tmpl

sed \
  -e "s/__LOGIN_DOMAIN__/${LOGIN_DOMAIN:-login.invalid}/g" \
  -e "s/__ORION_DOMAIN__/${ORION_DOMAIN:-orion.invalid}/g" \
  -e "s/__SIECLE_DOMAIN__/${SIECLE_DOMAIN:-siecle.invalid}/g" \
  -e "s/__LUNEA_DOMAIN__/${LUNEA_DOMAIN:-lunea.invalid}/g" \
  "$PAYLOAD_DIR/nginx/orion-proxmox.conf.tmpl" > /etc/nginx/sites-available/orion.conf

ln -sfn /etc/nginx/sites-available/orion.conf /etc/nginx/sites-enabled/orion.conf
rm -f /etc/nginx/sites-enabled/default

nginx -t && systemctl enable --now nginx && systemctl reload nginx || true

echo "[04] Terminé."
