#!/usr/bin/env bash
# Orion ERP Appliance — Stage A / 05
# Prépare /etc/cloudflared/config.yml. Si un token Cloudflare Tunnel a été
# fourni au déploiement (deploy-info.env, voir deploy.sh), installe et
# démarre directement le service — sinon le tunnel reste inactif (activable
# plus tard, voir PROXMOX.md).

set -euo pipefail
exec >> /var/log/orion-provision.log 2>&1

echo "=== [05] Cloudflare Tunnel — $(date -u +%FT%TZ) ==="

PAYLOAD_DIR="/opt/orion-appliance"
mkdir -p /etc/cloudflared

cp "$PAYLOAD_DIR/provisioning/05-cloudflared-config.tmpl.yml" /etc/cloudflared/config.yml.tmpl

if [ -n "${CF_TUNNEL_TOKEN:-}" ]; then
  echo "[05] Installation du tunnel Cloudflare..."
  cloudflared service install "$CF_TUNNEL_TOKEN" \
    && echo "  -> Pense à déclarer les hostnames dans le dashboard Zero Trust :" \
    && echo "     ${LOGIN_DOMAIN:-<login>}  -> http://localhost:9000" \
    && echo "     ${ORION_DOMAIN:-<orion>}  -> http://localhost:5172" \
    && echo "     ${SIECLE_DOMAIN:-<siecle>} -> http://localhost:5173" \
    && echo "     ${LUNEA_DOMAIN:-<lunea>}  -> http://localhost:5174" \
    || echo "ATTENTION: installation du tunnel échouée — relancer : cloudflared service install <token>"
else
  systemctl disable cloudflared 2>/dev/null || true
  echo "[05] Terminé (tunnel inactif — aucun token fourni)."
fi
