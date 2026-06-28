#!/usr/bin/env bash

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."

echo "======================================"
echo " Mise à jour Orion ERP Appliance"
echo "======================================"

# Sauvegarde préventive
echo "[0/7] Sauvegarde préventive..."
./scripts/backup.sh

# Pull Git si disponible
echo "[1/7] Récupération des mises à jour..."
if [ -d ".git" ]; then
  git pull || echo "  (pas de git remote ou déjà à jour)"
else
  echo "  (pas de dépôt Git — mise à jour manuelle)"
fi

# Rebuild images
echo "[2/7] Rebuild des images Docker..."
docker compose build --parallel

# Rebuild frontends
echo "[3/7] Rebuild des frontends..."
docker compose --profile build run --rm orion-siecle-builder || true
docker compose --profile build run --rm orion-lunea-builder || true

# Migrations
echo "[4/7] Migrations..."
docker compose run --rm orion-backend python manage.py migrate --noinput

# Collectstatic
echo "[5/7] Collectstatic..."
docker compose run --rm orion-backend python manage.py collectstatic --noinput

# Redémarrage
echo "[6/7] Redémarrage des services..."
docker compose up -d

echo "[7/7] Vérification santé..."
sleep 5
docker compose ps

echo ""
echo "Mise à jour terminée avec succès."
