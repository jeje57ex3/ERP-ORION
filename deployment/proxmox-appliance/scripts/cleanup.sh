#!/usr/bin/env bash
# Orion ERP Appliance — Nettoyage (logs anciens, caches, Docker inutilisé, backups expirés).

set -euo pipefail

ORION_HOME="/opt/orion"
ENV_FILE="$ORION_HOME/backend/.env"
# commun.sh : lecture du .env sans l'executer, et $HOME garanti. Une seule
# valeur a espaces non citee suffisait a tuer ce script sur un
# « -n: command not found » (exit 127) qui ne nommait ni la cle ni le fichier.
ICI_SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for _candidat in \
  "$ICI_SCRIPT/commun.sh" \
  /opt/orion/scripts/commun.sh \
  /opt/orion/backend/deployment/proxmox-appliance/provisioning/lib/commun.sh
do
  if [ -f "$_candidat" ]; then . "$_candidat"; break; fi
done
if ! declare -f charger_env >/dev/null 2>&1; then
  echo "ERREUR: commun.sh introuvable (attendu dans /opt/orion/scripts/)." >&2
  exit 1
fi
[ -f "$ENV_FILE" ] && charger_env "$ENV_FILE" || true
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
