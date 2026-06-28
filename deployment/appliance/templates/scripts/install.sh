#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APPLIANCE_DIR="$(dirname "$SCRIPT_DIR")"

cd "$APPLIANCE_DIR"

echo "======================================"
echo " Installation Orion ERP Appliance"
echo "======================================"

# Vérifications préalables
if ! command -v docker >/dev/null 2>&1; then
  echo ""
  echo "ERREUR: Docker n'est pas installé."
  echo "Installer Docker : https://docs.docker.com/engine/install/"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo ""
  echo "ERREUR: Docker Compose (plugin v2) n'est pas disponible."
  echo "Vérifier : docker compose version"
  exit 1
fi

if [ ! -f ".env" ]; then
  echo ""
  echo "ERREUR: Fichier .env manquant."
  echo ""
  echo "Créer et configurer le fichier .env :"
  echo "  cp .env.example .env"
  echo "  nano .env"
  echo ""
  echo "Variables critiques à modifier :"
  echo "  SECRET_KEY, MYSQL_PASSWORD, MYSQL_ROOT_PASSWORD,"
  echo "  ORION_SECRET_ENCRYPTION_KEY, ORION_SUPERADMIN_PASSWORD"
  exit 1
fi

# Créer les dossiers nécessaires
echo "[0/6] Création des dossiers..."
mkdir -p media static backups logs runtime mysql redis
mkdir -p logs/nginx runtime/certs
mkdir -p static/siecle static/lunea

# Build des images Docker
echo "[1/6] Build des images Docker..."
docker compose build --parallel

# Build des frontends React
echo "[2/6] Build des frontends SIÈCLE et LUNEA..."
echo "  -> SIÈCLE..."
docker compose --profile build run --rm orion-siecle-builder || {
  echo "  ATTENTION: Build SIÈCLE échoué (les assets doivent être pré-buildés)."
}
echo "  -> LUNEA..."
docker compose --profile build run --rm orion-lunea-builder || {
  echo "  ATTENTION: Build LUNEA échoué (les assets doivent être pré-buildés)."
}

# Démarrer les services infrastructure
echo "[3/6] Démarrage des services..."
docker compose up -d orion-db orion-redis
echo "  Attente base de données..."
sleep 10

# Migrations et collectstatic
echo "[4/6] Migrations base de données..."
docker compose run --rm orion-backend python manage.py migrate --noinput

echo "[5/6] Collecte des fichiers statiques..."
docker compose run --rm orion-backend python manage.py collectstatic --noinput

# Créer le superadmin depuis .env si défini
echo "[6/6] Configuration initiale..."
ADMIN_EMAIL="${ORION_SUPERADMIN_EMAIL:-}"
ADMIN_PASS="${ORION_SUPERADMIN_PASSWORD:-}"
if [ -n "$ADMIN_EMAIL" ] && [ -n "$ADMIN_PASS" ]; then
  docker compose run --rm orion-backend python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(email='$ADMIN_EMAIL').exists():
    User.objects.create_superuser(username='admin', email='$ADMIN_EMAIL', password='$ADMIN_PASS')
    print('Superadmin créé:', '$ADMIN_EMAIL')
else:
    print('Superadmin existant:', '$ADMIN_EMAIL')
" || true
fi

# Démarrer tous les services
docker compose up -d

echo ""
echo "======================================"
echo " Orion ERP installé avec succès !"
echo "======================================"
echo ""
echo " URL : http://localhost"
echo " Admin : http://localhost/orion-admin/"
echo ""
echo " Commandes utiles :"
echo "   ./scripts/start.sh    — démarrer"
echo "   ./scripts/stop.sh     — arrêter"
echo "   ./scripts/health.sh   — vérifier"
echo "   ./scripts/logs.sh     — voir les logs"
echo ""
