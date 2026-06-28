#!/usr/bin/env bash

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."

# Charger les variables .env
set -a
[ -f .env ] && source .env
set +a

BACKUP_FILE="${1:-}"

if [ -z "$BACKUP_FILE" ]; then
  echo "Usage : ./scripts/restore.sh backups/orion_backup_YYYYMMDD_HHMMSS.tar.gz"
  echo ""
  echo "Sauvegardes disponibles :"
  ls -lh backups/orion_backup_*.tar.gz 2>/dev/null || echo "  (aucune)"
  exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
  echo "ERREUR: Fichier introuvable : $BACKUP_FILE"
  exit 1
fi

echo "======================================"
echo " Restauration Orion ERP"
echo " Fichier : $BACKUP_FILE"
echo "======================================"
echo ""
read -p "ATTENTION: Cette opération va écraser la base de données. Continuer ? [y/N] " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
  echo "Annulé."
  exit 0
fi

TMP_DIR="./runtime/restore_tmp_$(date +%s)"
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"

echo "[1/4] Extraction de la sauvegarde..."
tar -xzf "$BACKUP_FILE" -C "$TMP_DIR"

BACKUP_FOLDER="$(find "$TMP_DIR" -maxdepth 1 -mindepth 1 -type d | head -n 1)"
if [ -z "$BACKUP_FOLDER" ]; then
  echo "ERREUR: Archive corrompue ou vide."
  rm -rf "$TMP_DIR"
  exit 1
fi

echo "[2/4] Restauration de la base de données..."
cat "$BACKUP_FOLDER/database.sql" | docker compose exec -T orion-db mysql \
  -u"${MYSQL_USER:-orion}" \
  -p"${MYSQL_PASSWORD:-changeme}" \
  "${MYSQL_DATABASE:-orion}" || {
    echo "ERREUR: Restauration base de données échouée."
    rm -rf "$TMP_DIR"
    exit 1
  }

echo "[3/4] Restauration des fichiers media..."
if [ -f "$BACKUP_FOLDER/media.tar.gz" ]; then
  rm -rf media
  tar -xzf "$BACKUP_FOLDER/media.tar.gz" -C .
  echo "  -> Media restaurés."
else
  echo "  -> (pas de media dans cette sauvegarde)"
fi

echo "[4/4] Nettoyage..."
rm -rf "$TMP_DIR"

echo ""
echo "Restauration terminée."
echo "Redémarrage recommandé : ./scripts/restart.sh"
