#!/usr/bin/env bash
# Orion ERP Appliance — recalcule ALLOWED_HOSTS à CHAQUE démarrage du service
# (ExecStartPre de orion-backend/orion-frontend), pas seulement pendant le
# provisioning : le bail DHCP de la VM peut changer entre deux redémarrages,
# et ALLOWED_HOSTS n'est lu qu'une fois par gunicorn (EnvironmentFile) — une
# IP figée au premier boot casserait l'accès par IP après un simple reboot.
set -euo pipefail

ENV_FILE="/opt/orion/backend/.env"
[ -f "$ENV_FILE" ] || exit 0

VM_IP="$(ip route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="src") print $(i+1)}' | head -1)" || true
[ -n "${VM_IP:-}" ] || exit 0

get_field() { grep "^$1=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2-; }

HOSTS="localhost,127.0.0.1"
for domain in "$(get_field ORION_LOGIN_DOMAIN)" "$(get_field ORION_FRONTEND_DOMAIN)" \
              "$(get_field SIECLE_STORE_DOMAIN)" "$(get_field LUNEA_STORE_DOMAIN)"; do
  [ -n "$domain" ] && HOSTS="$HOSTS,$domain"
done
HOSTS="$HOSTS,$VM_IP"

if grep -q '^ALLOWED_HOSTS=' "$ENV_FILE"; then
  sed -i "s#^ALLOWED_HOSTS=.*#ALLOWED_HOSTS=${HOSTS}#" "$ENV_FILE"
else
  echo "ALLOWED_HOSTS=${HOSTS}" >> "$ENV_FILE"
fi
