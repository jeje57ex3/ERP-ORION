#!/usr/bin/env bash
# Orion ERP Appliance — Nettoyage (logs anciens, caches, Docker inutilisé, backups expirés).

set -euo pipefail

ORION_HOME="/opt/orion"
ENV_FILE="$ORION_HOME/backend/.env"
[ -f "$ENV_FILE" ] && { set -a; . "$ENV_FILE"; set +a; }
RETENTION="${ORION_BACKUP_RETENTION_DAYS:-14}"
LOG_RETENTION_DAYS=30

echo "======================================"
echo " Nettoyage Orion ERP Appliance"
echo "======================================"

echo "[1/5] Logs applicatifs > ${LOG_RETENTION_DAYS} jours..."
find "$ORION_HOME/logs" -maxdepth 1 -name "*.log" -mtime "+${LOG_RETENTION_DAYS}" -delete 2>/dev/null || true

echo "[2/5] Journaux systemd (> 2 semaines, max 500 Mo)..."
journalctl --vacuum-time=2weeks --vacuum-size=500M || true

echo "[3/5] Caches npm / pip..."
npm cache clean --force --silent 2>/dev/null || true
sudo -u orion "$ORION_HOME/backend/.venv/bin/pip" cache purge 2>/dev/null || true

echo "[4/5] Docker : images/conteneurs/volumes inutilisés..."
docker system prune -f || true

echo "[5/5] Sauvegardes expirées (> ${RETENTION} jours)..."
find "$ORION_HOME/backups" -maxdepth 1 -name "orion_backup_*.tar.gz" -mtime "+${RETENTION}" -delete 2>/dev/null || true

echo "[+] Paquets APT inutilisés..."
apt-get autoremove -y -qq || true
apt-get autoclean -y -qq || true

echo ""
echo "Nettoyage terminé."
df -h / | tail -1
