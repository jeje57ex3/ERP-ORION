#!/usr/bin/env bash
# ============================================================================
# Orion ERP — Installation des données sur l'appliance Proxmox
#
# Restaure une archive produite par export_orion_data.ps1 : base MySQL,
# médias, puis migrations et collectstatic. L'appliance fournit le CODE
# (cloné depuis Git au premier boot) ; ce script apporte les DONNÉES.
#
# Usage :
#   ./install_orion_data.sh /tmp/orion-data-20261009-204500.tar.gz
#   ./install_orion_data.sh --yes archive.tar.gz      # sans confirmation
#   ./install_orion_data.sh --no-backup archive.tar.gz
#
# L'opération ÉCRASE la base existante de l'appliance. Une sauvegarde de
# sécurité est prise au préalable (sauf --no-backup) dans /opt/orion/backups.
# ============================================================================
set -euo pipefail

ORION_HOME="${ORION_HOME:-/opt/orion}"
ENV_FILE="$ORION_HOME/backend/.env"
COMPOSE_FILE="$ORION_HOME/docker/docker-compose.yml"
UPLOADS_DIR="$ORION_HOME/uploads"
BACKUP_DIR="$ORION_HOME/backups"
SERVICES=(orion-backend orion-frontend siecle-frontend lunea-frontend)

ASSUME_YES=0
MAKE_BACKUP=1
ARCHIVE=""

while [ $# -gt 0 ]; do
  case "$1" in
    --yes|-y)     ASSUME_YES=1 ;;
    --no-backup)  MAKE_BACKUP=0 ;;
    -h|--help)    sed -n '2,20p' "$0"; exit 0 ;;
    -*)           echo "Option inconnue : $1" >&2; exit 2 ;;
    *)            ARCHIVE="$1" ;;
  esac
  shift
done

log()  { echo -e "\n\033[36m[>>]\033[0m $*"; }
ok()   { echo -e "  \033[32m[OK]\033[0m $*"; }
warn() { echo -e "  \033[33m[!!]\033[0m $*"; }
die()  { echo -e "  \033[31m[ERREUR]\033[0m $*" >&2; exit 1; }

[ -n "$ARCHIVE" ] || die "Archive manquante. Usage : $0 <archive.tar.gz>"
[ -f "$ARCHIVE" ] || die "Archive introuvable : $ARCHIVE"
[ "$(id -u)" -eq 0 ] || die "Ce script doit être lancé en root (sudo)."
[ -f "$ENV_FILE" ] || die "$ENV_FILE introuvable — l'appliance n'est pas configurée."
[ -f "$COMPOSE_FILE" ] || die "$COMPOSE_FILE introuvable — stack Docker absente."

set -a; . "$ENV_FILE"; set +a
DB_NAME="${DB_NAME:-orion_core}"
DB_USER="${DB_USER:-orion}"
[ -n "${DB_PASSWORD:-}" ] || die "DB_PASSWORD absent de $ENV_FILE"

# ── 1. Vérification de l'archive ────────────────────────────────────────────
log "Vérification de l'archive"

if [ -f "$ARCHIVE.sha256" ]; then
  (cd "$(dirname "$ARCHIVE")" && sha256sum -c "$(basename "$ARCHIVE").sha256" >/dev/null 2>&1) \
    && ok "Empreinte SHA-256 conforme" \
    || die "Empreinte SHA-256 invalide — archive corrompue ou incomplète."
else
  warn "Pas de fichier .sha256 à côté de l'archive — intégrité non vérifiée."
fi

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT
tar -xzf "$ARCHIVE" -C "$WORK_DIR" || die "Extraction impossible."

BUNDLE_DIR="$(find "$WORK_DIR" -mindepth 1 -maxdepth 1 -type d | head -n1)"
[ -n "$BUNDLE_DIR" ] || die "Archive vide ou structure inattendue."
SQL_FILE="$BUNDLE_DIR/database.sql"
[ -f "$SQL_FILE" ] || die "database.sql absent de l'archive."

if [ -f "$BUNDLE_DIR/manifest.json" ]; then
  python3 - "$BUNDLE_DIR/manifest.json" <<'PY' || warn "Manifeste illisible."
import json, sys
m = json.load(open(sys.argv[1], encoding='utf-8'))
print(f"  Source   : {m.get('source_host','?')} / base {m.get('source_db','?')}")
print(f"  Créée le : {m.get('created_at','?')}")
print(f"  Code     : commit {m.get('git_commit','?')} ({m.get('git_branch','?')})")
print(f"  Contenu  : {m.get('database_tables','?')} tables, {m.get('media_files',0)} média(s)")
PY
fi
ok "Archive valide : $(du -h "$SQL_FILE" | cut -f1) de SQL"

# ── 2. Confirmation ─────────────────────────────────────────────────────────
if [ "$ASSUME_YES" -ne 1 ]; then
  echo ""
  warn "La base « $DB_NAME » de cette appliance va être ÉCRASÉE."
  read -r -p "  Continuer ? [oui/N] " answer
  case "$answer" in
    oui|OUI|o|O|yes|y) ;;
    *) echo "  Annulé."; exit 0 ;;
  esac
fi

# ── 3. Arrêt des services applicatifs ───────────────────────────────────────
log "Arrêt des services applicatifs"
for svc in "${SERVICES[@]}"; do
  if systemctl is-active --quiet "$svc" 2>/dev/null; then
    systemctl stop "$svc" && ok "$svc arrêté"
  fi
done

# La base, elle, doit rester disponible pour la restauration.
docker compose -f "$COMPOSE_FILE" up -d orion-db >/dev/null 2>&1 || true
for _ in $(seq 1 30); do
  docker compose -f "$COMPOSE_FILE" exec -T orion-db \
    mysqladmin ping -u"$DB_USER" -p"$DB_PASSWORD" --silent >/dev/null 2>&1 && break
  sleep 2
done

# ── 4. Sauvegarde de sécurité ───────────────────────────────────────────────
if [ "$MAKE_BACKUP" -eq 1 ]; then
  log "Sauvegarde de sécurité de la base actuelle"
  mkdir -p "$BACKUP_DIR"
  SAFETY="$BACKUP_DIR/pre-import-$(date +%Y%m%d_%H%M%S).sql.gz"
  if docker compose -f "$COMPOSE_FILE" exec -T orion-db \
       mysqldump -u"$DB_USER" -p"$DB_PASSWORD" --single-transaction --routines \
       --triggers --no-tablespaces "$DB_NAME" 2>/dev/null | gzip > "$SAFETY"; then
    ok "Sauvegarde : $SAFETY ($(du -h "$SAFETY" | cut -f1))"
  else
    rm -f "$SAFETY"
    warn "Base actuelle vide ou inaccessible — pas de sauvegarde (premier import ?)"
  fi
fi

# ── 5. Restauration de la base ──────────────────────────────────────────────
log "Restauration de la base « $DB_NAME »"

# Le dump ne contient pas de CREATE DATABASE : le nom de base diffère entre le
# poste de dev et l'appliance. On repart donc d'un schéma vide côté cible.
docker compose -f "$COMPOSE_FILE" exec -T orion-db \
  mysql -u"$DB_USER" -p"$DB_PASSWORD" -e \
  "DROP DATABASE IF EXISTS \`$DB_NAME\`; CREATE DATABASE \`$DB_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;" \
  2>/dev/null || die "Impossible de réinitialiser la base."

if ! docker compose -f "$COMPOSE_FILE" exec -T orion-db \
     mysql -u"$DB_USER" -p"$DB_PASSWORD" --default-character-set=utf8mb4 "$DB_NAME" \
     < "$SQL_FILE" 2>/tmp/orion-import-err.log; then
  echo "--- Détail de l'erreur ---" >&2
  tail -n 15 /tmp/orion-import-err.log >&2
  die "Restauration échouée. La sauvegarde de sécurité est dans $BACKUP_DIR."
fi

RESTORED=$(docker compose -f "$COMPOSE_FILE" exec -T orion-db \
  mysql -u"$DB_USER" -p"$DB_PASSWORD" -N -B -e \
  "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$DB_NAME';" 2>/dev/null | tr -d '\r')
ok "$RESTORED table(s) restaurée(s)"

# ── 6. Médias ───────────────────────────────────────────────────────────────
if [ -d "$BUNDLE_DIR/media" ]; then
  log "Restauration des médias"
  mkdir -p "$UPLOADS_DIR"
  # Fusion sans suppression : d'éventuels fichiers déjà présents sur
  # l'appliance (générés depuis l'import précédent) sont conservés.
  cp -a "$BUNDLE_DIR/media/." "$UPLOADS_DIR/"
  chown -R orion:orion "$UPLOADS_DIR" 2>/dev/null || true
  ok "$(find "$UPLOADS_DIR" -type f | wc -l) fichier(s) dans $UPLOADS_DIR"
else
  warn "Pas de médias dans l'archive."
fi

# ── 7. Migrations et fichiers statiques ─────────────────────────────────────
log "Mise à niveau du schéma et des statiques"
PYTHON="$ORION_HOME/backend/.venv/bin/python"
MANAGE="$ORION_HOME/backend/manage.py"

if [ -x "$PYTHON" ] && [ -f "$MANAGE" ]; then
  # Le dump peut venir d'une version antérieure du code : on rejoue les
  # migrations manquantes avant de redémarrer.
  sudo -u orion -E "$PYTHON" "$MANAGE" migrate --noinput && ok 'Migrations appliquées'
  sudo -u orion -E "$PYTHON" "$MANAGE" collectstatic --noinput >/dev/null && ok 'Fichiers statiques collectés'
else
  warn "Environnement Python introuvable — lancez migrate/collectstatic à la main."
fi

# ── 8. Redémarrage ──────────────────────────────────────────────────────────
log "Redémarrage des services"
for svc in "${SERVICES[@]}"; do
  if systemctl list-unit-files "$svc.service" >/dev/null 2>&1; then
    systemctl start "$svc" && ok "$svc démarré"
  fi
done

echo ""
echo -e "\033[32m============================================================\033[0m"
echo -e "\033[32m Données Orion ERP installées\033[0m"
echo -e "\033[32m============================================================\033[0m"
echo "  Base      : $DB_NAME ($RESTORED tables)"
echo "  Médias    : $UPLOADS_DIR"
[ "$MAKE_BACKUP" -eq 1 ] && echo "  Sauvegarde: $BACKUP_DIR (état avant import)"
echo ""
echo "  Vérifiez l'état de l'appliance :"
echo "    $ORION_HOME/backend/deployment/proxmox-appliance/scripts/orion-dashboard.sh"
echo ""
