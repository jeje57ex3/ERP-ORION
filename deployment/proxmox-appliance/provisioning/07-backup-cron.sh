#!/usr/bin/env bash
# Orion ERP Appliance — Stage A / 07
# Installe les scripts opérationnels dans /opt/orion/scripts et programme la
# sauvegarde quotidienne à 2h.

set -euo pipefail
exec >> /var/log/orion-provision.log 2>&1

echo "=== [07] Scripts + cron sauvegarde — $(date -u +%FT%TZ) ==="

PAYLOAD_DIR="/opt/orion-appliance"

cp "$PAYLOAD_DIR"/scripts/*.sh /opt/orion/scripts/
cp "$PAYLOAD_DIR"/scripts/*.py /opt/orion/scripts/
chmod +x /opt/orion/scripts/*.sh /opt/orion/scripts/*.py
chown -R orion:orion /opt/orion/scripts

cat > /etc/cron.d/orion-backup <<'EOF'
# Orion ERP Appliance — sauvegarde quotidienne (DB + uploads + config)
0 2 * * * root /opt/orion/scripts/backup.sh >> /opt/orion/logs/backup.log 2>&1
EOF
chmod 0644 /etc/cron.d/orion-backup

echo "[07] Terminé."
