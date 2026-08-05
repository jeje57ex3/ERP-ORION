#!/usr/bin/env bash
# Orion ERP Appliance — Sauvegarde quotidienne (DB + uploads + config).
# Installé par cron à 2h (voir /etc/cron.d/orion-backup).
# Réutilise le pipeline applicatif existant (apps.backups) pour les fichiers,
# et un dump MySQL natif pour la base — ne dépend pas de Django pour la partie DB.

set -euo pipefail

ORION_HOME="/opt/orion"
ENV_FILE="$ORION_HOME/backend/.env"
BACKUP_DIR="$ORION_HOME/backups"
DATE="$(date +%Y%m%d_%H%M%S)"
BACKUP_NAME="orion_backup_$DATE"
BACKUP_TMP="$BACKUP_DIR/$BACKUP_NAME"

[ -f "$ENV_FILE" ] || { echo "ERREUR: $ENV_FILE introuvable — appliance non configurée."; exit 1; }
set -a; . "$ENV_FILE"; set +a

mkdir -p "$BACKUP_TMP"
echo "=== Sauvegarde Orion ERP — $BACKUP_TMP ==="

echo "[1/3] Dump MySQL..."
docker compose -f "$ORION_HOME/docker/docker-compose.yml" exec -T orion-db \
  mysqldump -u"${DB_USER:-orion}" -p"${DB_PASSWORD}" --single-transaction --routines --triggers \
  "${DB_NAME:-orion_core}" > "$BACKUP_TMP/database.sql" \
  || { echo "ERREUR: dump MySQL échoué."; rm -rf "$BACKUP_TMP"; exit 1; }
echo "  -> $(wc -c < "$BACKUP_TMP/database.sql") octets"

echo "[2/3] Sauvegarde applicative (base centrale + entreprises) via Django..."
sudo -u orion -E "$ORION_HOME/backend/.venv/bin/python" "$ORION_HOME/backend/manage.py" backup_all \
  || echo "  ATTENTION: backup_all a échoué (voir logs) — dump MySQL brut conservé ci-dessus."

cp "$ENV_FILE" "$BACKUP_TMP/env.backup"

echo "[3/3] Compression..."
tar -czf "$BACKUP_DIR/$BACKUP_NAME.tar.gz" -C "$BACKUP_DIR" "$BACKUP_NAME"
rm -rf "$BACKUP_TMP"

SIZE="$(du -sh "$BACKUP_DIR/$BACKUP_NAME.tar.gz" | cut -f1)"
echo "Sauvegarde créée : $BACKUP_DIR/$BACKUP_NAME.tar.gz ($SIZE)"

RETENTION="${ORION_BACKUP_RETENTION_DAYS:-14}"
echo "Purge des sauvegardes > ${RETENTION} jours..."
find "$BACKUP_DIR" -maxdepth 1 -name "orion_backup_*.tar.gz" -mtime "+${RETENTION}" -delete

echo "Terminé."
