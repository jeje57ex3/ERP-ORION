#!/usr/bin/env bash

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."

# Charger les variables .env
set -a
[ -f .env ] && source .env
set +a

BACKUP_DIR="./backups"
DATE="$(date +"%Y%m%d_%H%M%S")"
BACKUP_NAME="orion_backup_$DATE"
BACKUP_TMP="$BACKUP_DIR/$BACKUP_NAME"

mkdir -p "$BACKUP_TMP"

echo "======================================"
echo " Sauvegarde Orion ERP"
echo " Dossier : $BACKUP_TMP"
echo "======================================"

# Dump MySQL
echo "[1/4] Dump base de données MySQL..."
docker compose exec -T orion-db mysqldump \
  -u"${MYSQL_USER:-orion}" \
  -p"${MYSQL_PASSWORD:-changeme}" \
  --single-transaction \
  --routines \
  --triggers \
  "${MYSQL_DATABASE:-orion}" \
  > "$BACKUP_TMP/database.sql" 2>/dev/null || {
    echo "ERREUR: Impossible de dumper la base de données."
    rm -rf "$BACKUP_TMP"
    exit 1
  }

echo "  -> $(wc -c < "$BACKUP_TMP/database.sql") octets"

# Sauvegarde media
echo "[2/4] Sauvegarde des fichiers media..."
if [ -d "media" ] && [ "$(ls -A media 2>/dev/null)" ]; then
  tar -czf "$BACKUP_TMP/media.tar.gz" media/
  echo "  -> $(du -sh "$BACKUP_TMP/media.tar.gz" | cut -f1)"
else
  echo "  -> (media vide, ignoré)"
fi

# Sauvegarde .env
echo "[3/4] Sauvegarde configuration .env..."
cp .env "$BACKUP_TMP/env.backup"

# Compression finale
echo "[4/4] Compression de la sauvegarde..."
tar -czf "$BACKUP_DIR/$BACKUP_NAME.tar.gz" -C "$BACKUP_DIR" "$BACKUP_NAME"
rm -rf "$BACKUP_TMP"

SIZE="$(du -sh "$BACKUP_DIR/$BACKUP_NAME.tar.gz" | cut -f1)"
echo ""
echo "Sauvegarde créée : $BACKUP_DIR/$BACKUP_NAME.tar.gz ($SIZE)"

# Purge des anciennes sauvegardes
RETENTION="${ORION_BACKUP_RETENTION_DAYS:-14}"
echo "Purge des sauvegardes > ${RETENTION} jours..."
find "$BACKUP_DIR" -name "orion_backup_*.tar.gz" -mtime +${RETENTION} -delete
echo "Terminé."
