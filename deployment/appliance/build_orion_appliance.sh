#!/usr/bin/env bash

set -euo pipefail

APP_NAME="OrionERP-Appliance"
VERSION="${1:-dev}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$ROOT_DIR/build/$APP_NAME"
DIST_DIR="$ROOT_DIR/dist"
TEMPLATE_DIR="$SCRIPT_DIR/templates"
ARCHIVE_NAME="OrionERP-Appliance-${VERSION}.tar.gz"

echo "======================================"
echo " Orion ERP Appliance Package Builder"
echo " Version : $VERSION"
echo " Source  : $ROOT_DIR"
echo " Output  : $DIST_DIR/$ARCHIVE_NAME"
echo "======================================"

# ─── Vérifications préalables ─────────────────────────────────────────────────

echo ""
echo "[CHECK] Vérifications..."

if [ ! -f "$ROOT_DIR/requirements.txt" ]; then
  echo "ERREUR: requirements.txt introuvable dans $ROOT_DIR"
  exit 1
fi

if [ ! -f "$ROOT_DIR/Dockerfile" ]; then
  echo "ERREUR: Dockerfile introuvable dans $ROOT_DIR"
  exit 1
fi

if [ ! -f "$ROOT_DIR/manage.py" ]; then
  echo "ERREUR: manage.py introuvable — vérifier que ROOT_DIR pointe sur le projet Django."
  exit 1
fi

if [ ! -d "$TEMPLATE_DIR" ]; then
  echo "ERREUR: Templates appliance introuvables : $TEMPLATE_DIR"
  exit 1
fi

if [ ! -d "$ROOT_DIR/frontend/siecle-store" ]; then
  echo "ATTENTION: frontend/siecle-store introuvable — sera ignoré."
fi

if [ ! -d "$ROOT_DIR/frontend/lunea-store" ]; then
  echo "ATTENTION: frontend/lunea-store introuvable — sera ignoré."
fi

echo "[CHECK] OK"

# ─── Nettoyage et structure ────────────────────────────────────────────────────

echo ""
echo "[1/9] Création de la structure appliance..."

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"
mkdir -p "$DIST_DIR"

mkdir -p "$BUILD_DIR/backend"
mkdir -p "$BUILD_DIR/frontend/siecle-store"
mkdir -p "$BUILD_DIR/frontend/lunea-store"
mkdir -p "$BUILD_DIR/nginx"
mkdir -p "$BUILD_DIR/scripts"
mkdir -p "$BUILD_DIR/systemd"
mkdir -p "$BUILD_DIR/media"
mkdir -p "$BUILD_DIR/static/siecle"
mkdir -p "$BUILD_DIR/static/lunea"
mkdir -p "$BUILD_DIR/backups"
mkdir -p "$BUILD_DIR/logs/nginx"
mkdir -p "$BUILD_DIR/runtime/certs"
mkdir -p "$BUILD_DIR/mysql"
mkdir -p "$BUILD_DIR/redis"

# Fichier .gitkeep pour préserver les dossiers vides dans l'archive
for d in media backups logs/nginx runtime/certs mysql redis; do
  touch "$BUILD_DIR/$d/.gitkeep"
done

# ─── Backend Django ────────────────────────────────────────────────────────────

echo "[2/9] Copie du backend Django (projet racine → backend/)..."

RSYNC_EXCLUDES=(
  "--exclude=.venv"
  "--exclude=venv"
  "--exclude=.env"
  "--exclude=.git"
  "--exclude=.gitignore"
  "--exclude=__pycache__"
  "--exclude=*.pyc"
  "--exclude=*.pyo"
  "--exclude=db.sqlite3"
  "--exclude=db_local.sqlite3"
  "--exclude=media"
  "--exclude=staticfiles"
  "--exclude=.pytest_cache"
  "--exclude=.coverage"
  "--exclude=node_modules"
  "--exclude=dist"
  "--exclude=build"
  "--exclude=frontend"
  "--exclude=deployment"
)

rsync -a "${RSYNC_EXCLUDES[@]}" "$ROOT_DIR/" "$BUILD_DIR/backend/"

echo "  -> $(find "$BUILD_DIR/backend" -type f | wc -l) fichiers copiés"

# ─── Frontends ────────────────────────────────────────────────────────────────

echo "[3/9] Copie des frontends..."

if [ -d "$ROOT_DIR/frontend/siecle-store" ]; then
  rsync -a \
    --exclude "node_modules" \
    --exclude "dist" \
    --exclude ".env" \
    --exclude ".env.local" \
    "$ROOT_DIR/frontend/siecle-store/" "$BUILD_DIR/frontend/siecle-store/"
  echo "  -> SIÈCLE : $(find "$BUILD_DIR/frontend/siecle-store" -type f | wc -l) fichiers"
else
  echo "  -> SIÈCLE : ignoré (absent)"
fi

if [ -d "$ROOT_DIR/frontend/lunea-store" ]; then
  rsync -a \
    --exclude "node_modules" \
    --exclude "dist" \
    --exclude ".env" \
    --exclude ".env.local" \
    "$ROOT_DIR/frontend/lunea-store/" "$BUILD_DIR/frontend/lunea-store/"
  echo "  -> LUNEA  : $(find "$BUILD_DIR/frontend/lunea-store" -type f | wc -l) fichiers"
else
  echo "  -> LUNEA : ignoré (absent)"
fi

# ─── Shared (si présent) ──────────────────────────────────────────────────────

if [ -d "$ROOT_DIR/frontend/shared" ]; then
  mkdir -p "$BUILD_DIR/frontend/shared"
  rsync -a \
    --exclude "node_modules" \
    "$ROOT_DIR/frontend/shared/" "$BUILD_DIR/frontend/shared/"
  echo "  -> Shared : $(find "$BUILD_DIR/frontend/shared" -type f | wc -l) fichiers"
fi

# ─── Templates de déploiement ─────────────────────────────────────────────────

echo "[4/9] Copie des templates de déploiement..."

cp "$TEMPLATE_DIR/docker-compose.yml"  "$BUILD_DIR/docker-compose.yml"
cp "$TEMPLATE_DIR/.env.example"        "$BUILD_DIR/.env.example"
cp "$TEMPLATE_DIR/Makefile"            "$BUILD_DIR/Makefile"
cp "$TEMPLATE_DIR/nginx/nginx.conf"    "$BUILD_DIR/nginx/nginx.conf"
cp "$TEMPLATE_DIR/nginx/orion.conf"    "$BUILD_DIR/nginx/orion.conf"
cp "$TEMPLATE_DIR/systemd/orion-appliance.service" \
                                       "$BUILD_DIR/systemd/orion-appliance.service"

cp "$TEMPLATE_DIR/scripts/"*.sh "$BUILD_DIR/scripts/"
chmod +x "$BUILD_DIR/scripts/"*.sh

# ─── README ───────────────────────────────────────────────────────────────────

echo "[5/9] Création du README..."
cp "$TEMPLATE_DIR/README.md" "$BUILD_DIR/README.md"

# ─── VERSION ──────────────────────────────────────────────────────────────────

echo "[6/9] Création du fichier VERSION..."

cat > "$BUILD_DIR/VERSION" <<EOF
ORION_APPLIANCE_VERSION=$VERSION
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
BUILD_HOST=$(hostname)
EOF

# ─── Manifest JSON ────────────────────────────────────────────────────────────

echo "[7/9] Création du manifest.json..."

cat > "$BUILD_DIR/manifest.json" <<EOF
{
  "name": "Orion ERP Appliance Package",
  "version": "$VERSION",
  "build_date": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "format": "docker-compose-appliance",
  "django_project": "erp_btp",
  "wsgi_module": "erp_btp.wsgi:application",
  "celery_app": "erp_btp",
  "services": [
    "orion-backend",
    "orion-celery",
    "orion-celery-beat",
    "orion-db",
    "orion-redis",
    "orion-nginx"
  ],
  "frontends": [
    "siecle-store",
    "lunea-store"
  ],
  "install": "./scripts/install.sh",
  "docs": "README.md"
}
EOF

# ─── Nettoyage ────────────────────────────────────────────────────────────────

echo "[8/9] Nettoyage fichiers inutiles..."

find "$BUILD_DIR" -name ".DS_Store" -delete 2>/dev/null || true
find "$BUILD_DIR" -name "Thumbs.db" -delete 2>/dev/null || true
find "$BUILD_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -name "*.pyc" -delete 2>/dev/null || true
find "$BUILD_DIR" -name "*.pyo" -delete 2>/dev/null || true
find "$BUILD_DIR" -name ".pytest_cache" -type d -exec rm -rf {} + 2>/dev/null || true

# ─── Compression ──────────────────────────────────────────────────────────────

echo "[9/9] Compression de l'archive..."

cd "$ROOT_DIR/build"
tar -czf "$DIST_DIR/$ARCHIVE_NAME" "$APP_NAME"

ARCHIVE_SIZE=$(du -sh "$DIST_DIR/$ARCHIVE_NAME" | cut -f1)

echo ""
echo "======================================"
echo " Appliance générée avec succès !"
echo "======================================"
echo ""
echo " Fichier  : $DIST_DIR/$ARCHIVE_NAME"
echo " Taille   : $ARCHIVE_SIZE"
echo ""
echo " Aperçu du contenu :"
tar -tzf "$DIST_DIR/$ARCHIVE_NAME" | grep -v "/$" | head -30
echo " ..."
echo ""
echo " Pour déployer sur le serveur :"
echo "   scp $DIST_DIR/$ARCHIVE_NAME user@server:/opt/"
echo "   ssh user@server"
echo "   cd /opt && tar -xzf $ARCHIVE_NAME"
echo "   cd $APP_NAME"
echo "   cp .env.example .env && nano .env"
echo "   ./scripts/install.sh"
echo ""
