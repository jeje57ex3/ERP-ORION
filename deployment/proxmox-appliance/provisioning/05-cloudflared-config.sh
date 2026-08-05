#!/usr/bin/env bash
# Orion ERP Appliance — Stage A / 05
# Prépare /etc/cloudflared/config.yml (service cloudflared laissé désactivé —
# le wizard l'active seulement si un token Cloudflare est saisi).

set -euo pipefail
exec >> /var/log/orion-provision.log 2>&1

echo "=== [05] Cloudflare Tunnel — $(date -u +%FT%TZ) ==="

PAYLOAD_DIR="/opt/orion-appliance"
mkdir -p /etc/cloudflared

cp "$PAYLOAD_DIR/provisioning/05-cloudflared-config.tmpl.yml" /etc/cloudflared/config.yml.tmpl

systemctl disable cloudflared 2>/dev/null || true

echo "[05] Terminé (tunnel inactif tant qu'aucun token n'est fourni)."
