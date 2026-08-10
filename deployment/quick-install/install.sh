#!/usr/bin/env bash
# Orion ERP — Installation rapide sur un serveur Linux vierge (Ubuntu 22.04/24.04,
# Debian 12). Installe Docker (MySQL + Redis), Python/venv, Nginx, clone le dépôt,
# configure l'app, et démarre le tout via systemd.
#
# Usage (une ligne, avec variables d'environnement en préfixe) :
#
#   ORION_DOMAIN=erp.mondomaine.fr \
#   ORION_ADMIN_EMAIL=admin@mondomaine.fr \
#   GITHUB_TOKEN=ghp_xxx \
#   bash -c "$(curl -fsSL -H \"Authorization: token $GITHUB_TOKEN\" \
#     https://raw.githubusercontent.com/jeje57ex3/ERP-ORION/main/deployment/quick-install/install.sh)"
#
# Variables reconnues (toutes optionnelles sauf ORION_DOMAIN) :
#   ORION_DOMAIN          Domaine public de l'ERP (ex: erp.mondomaine.fr) — REQUIS
#   ORION_ADMIN_EMAIL      Email du super-admin créé (def: admin@$ORION_DOMAIN)
#   ORION_ADMIN_PASSWORD   Mot de passe du super-admin (def: généré aléatoirement)
#   ORION_COMPANY_NAME     Nom de la première entreprise créée (def: "Mon Entreprise")
#   GITHUB_TOKEN           Token d'accès au dépôt privé (obligatoire si le repo est privé)
#   ORION_GIT_REPO         URL du dépôt (def: https://github.com/jeje57ex3/ERP-ORION.git)
#   ORION_GIT_BRANCH       Branche à cloner (def: main)
#   ORION_HOME             Répertoire d'installation (def: /opt/orion)
#
# Le script est idempotent-friendly : relancer après un échec reprend proprement
# (git pull au lieu de clone si déjà présent, etc.), mais n'est pas conçu pour
# mettre à jour une install existante — voir scripts/update_orion.sh pour ça une
# fois installé.

set -euo pipefail

# ─── Configuration ──────────────────────────────────────────────────────────────

ORION_DOMAIN="${ORION_DOMAIN:-}"
ORION_ADMIN_EMAIL="${ORION_ADMIN_EMAIL:-}"
ORION_ADMIN_PASSWORD="${ORION_ADMIN_PASSWORD:-}"
ORION_COMPANY_NAME="${ORION_COMPANY_NAME:-Mon Entreprise}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
ORION_GIT_REPO="${ORION_GIT_REPO:-https://github.com/jeje57ex3/ERP-ORION.git}"
ORION_GIT_BRANCH="${ORION_GIT_BRANCH:-main}"
ORION_HOME="${ORION_HOME:-/opt/orion}"

c_bold="\033[1m"; c_green="\033[32m"; c_yellow="\033[33m"; c_red="\033[31m"; c_reset="\033[0m"
log()  { echo -e "${c_bold}==>${c_reset} $*"; }
warn() { echo -e "${c_yellow}ATTENTION:${c_reset} $*" >&2; }
die()  { echo -e "${c_red}ERREUR:${c_reset} $*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Ce script doit être lancé en root (sudo)."

if [ -z "$ORION_DOMAIN" ]; then
  if [ -t 0 ]; then
    read -rp "Domaine public de l'ERP (ex: erp.mondomaine.fr) : " ORION_DOMAIN
  fi
  [ -n "$ORION_DOMAIN" ] || die "ORION_DOMAIN est requis (variable d'environnement ou saisie interactive)."
fi
[ -n "$ORION_ADMIN_EMAIL" ] || ORION_ADMIN_EMAIL="admin@${ORION_DOMAIN}"

GENERATED_PASSWORD=0
if [ -z "$ORION_ADMIN_PASSWORD" ]; then
  ORION_ADMIN_PASSWORD="$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 20)"
  GENERATED_PASSWORD=1
fi

echo "======================================================================"
echo " Orion ERP — Installation rapide"
echo "   Domaine   : $ORION_DOMAIN"
echo "   Admin     : $ORION_ADMIN_EMAIL"
echo "   Entreprise: $ORION_COMPANY_NAME"
echo "   Cible     : $ORION_HOME"
echo "======================================================================"

# ─── [1/9] Paquets système ───────────────────────────────────────────────────

log "[1/9] Installation des paquets système..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
  git curl ca-certificates gnupg lsb-release \
  python3 python3-venv python3-pip python3-dev \
  build-essential pkg-config default-libmysqlclient-dev \
  nginx >/dev/null

if ! command -v docker >/dev/null 2>&1; then
  log "Installation de Docker..."
  curl -fsSL https://get.docker.com | sh >/dev/null
fi
systemctl enable --now docker >/dev/null

# ─── [2/9] Récupération du code ──────────────────────────────────────────────

log "[2/9] Récupération du code source..."
mkdir -p "$ORION_HOME"
CLONE_URL="$ORION_GIT_REPO"
if [ -n "$GITHUB_TOKEN" ]; then
  CLONE_URL="$(echo "$ORION_GIT_REPO" | sed "s#https://#https://${GITHUB_TOKEN}@#")"
fi

if [ -d "$ORION_HOME/backend/.git" ]; then
  log "Dépôt déjà présent, mise à jour (git pull)..."
  git -C "$ORION_HOME/backend" pull --ff-only origin "$ORION_GIT_BRANCH"
else
  git clone --branch "$ORION_GIT_BRANCH" --depth 1 "$CLONE_URL" "$ORION_HOME/backend"
fi

DEPLOY_DIR="$ORION_HOME/backend/deployment/quick-install"
[ -d "$DEPLOY_DIR" ] || die "deployment/quick-install introuvable dans le dépôt cloné."

mkdir -p "$ORION_HOME/docker" "$ORION_HOME/systemd" "$ORION_HOME/scripts" \
         "$ORION_HOME/logs" "$ORION_HOME/backups" \
         "$ORION_HOME/backend/media" "$ORION_HOME/backend/staticfiles"

sed "s#/opt/orion#${ORION_HOME}#g" "$DEPLOY_DIR/docker-compose.yml" > "$ORION_HOME/docker/docker-compose.yml"
cp "$DEPLOY_DIR/wait_for_port.sh" "$ORION_HOME/scripts/wait_for_port.sh"
chmod +x "$ORION_HOME/scripts/wait_for_port.sh"

# ─── [3/9] Utilisateur système ───────────────────────────────────────────────

log "[3/9] Création de l'utilisateur système 'orion'..."
id -u orion >/dev/null 2>&1 || useradd --system --home "$ORION_HOME" --shell /usr/sbin/nologin orion

# ─── [4/9] Configuration (.env) ──────────────────────────────────────────────

log "[4/9] Génération de la configuration (.env)..."
ENV_FILE="$ORION_HOME/backend/.env"
if [ ! -f "$ENV_FILE" ]; then
  DB_NAME="orion_core"
  DB_USER="orion"
  DB_PASSWORD="$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32)"
  DB_ROOT_PASSWORD="$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32)"
  SECRET_KEY="$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 64)"

  cp "$ORION_HOME/backend/.env.example" "$ENV_FILE"
  # Remplacements ciblés (évite d'écraser les clés non gérées ici, ex. Stripe/AI restent à REMPLACER)
  sed -i \
    -e "s#^DJANGO_SETTINGS_MODULE=.*#DJANGO_SETTINGS_MODULE=erp_btp.settings.production#" \
    -e "s#^SECRET_KEY=.*#SECRET_KEY=${SECRET_KEY}#" \
    -e "s#^DEBUG=.*#DEBUG=False#" \
    -e "s#^ALLOWED_HOSTS=.*#ALLOWED_HOSTS=${ORION_DOMAIN}#" \
    -e "s#^CSRF_TRUSTED_ORIGINS=.*#CSRF_TRUSTED_ORIGINS=https://${ORION_DOMAIN}#" \
    -e "s#^DB_NAME=.*#DB_NAME=${DB_NAME}#" \
    -e "s#^DB_USER=.*#DB_USER=${DB_USER}#" \
    -e "s#^DB_PASSWORD=.*#DB_PASSWORD=${DB_PASSWORD}#" \
    -e "s#^DB_HOST=.*#DB_HOST=127.0.0.1#" \
    -e "s#^DATABASE_URL=.*#DATABASE_URL=mysql://${DB_USER}:${DB_PASSWORD}@127.0.0.1:3306/${DB_NAME}#" \
    -e "s#^SECURE_SSL_REDIRECT=.*#SECURE_SSL_REDIRECT=True#" \
    -e "s#^SESSION_COOKIE_SECURE=.*#SESSION_COOKIE_SECURE=True#" \
    -e "s#^CSRF_COOKIE_SECURE=.*#CSRF_COOKIE_SECURE=True#" \
    "$ENV_FILE"
  {
    echo ""
    echo "DB_ROOT_PASSWORD=${DB_ROOT_PASSWORD}"
  } >> "$ENV_FILE"
  chmod 600 "$ENV_FILE"
else
  log ".env déjà présent, conservé tel quel."
fi

# ─── [5/9] Base de données (Docker : MySQL + Redis) ──────────────────────────

log "[5/9] Démarrage de MySQL + Redis (Docker)..."
( cd "$ORION_HOME/docker" && docker compose --env-file "$ENV_FILE" up -d )
"$ORION_HOME/scripts/wait_for_port.sh" 127.0.0.1 3306 90
"$ORION_HOME/scripts/wait_for_port.sh" 127.0.0.1 6379 30

# ─── [6/9] Environnement Python ──────────────────────────────────────────────

log "[6/9] Installation de l'environnement Python (venv + dépendances)..."
cd "$ORION_HOME/backend"
python3 -m venv .venv
".venv/bin/pip" install --upgrade pip --quiet
".venv/bin/pip" install -r requirements.txt --quiet
".venv/bin/pip" install gunicorn --quiet

# ─── [7/9] Migrations, fichiers statiques, super-admin ───────────────────────

log "[7/9] Migrations et création du super-administrateur..."
set -a; source "$ENV_FILE"; set +a
".venv/bin/python" manage.py migrate --noinput
".venv/bin/python" manage.py collectstatic --noinput >/dev/null

ORION_BOOTSTRAP_EMAIL="$ORION_ADMIN_EMAIL" \
ORION_BOOTSTRAP_PASSWORD="$ORION_ADMIN_PASSWORD" \
ORION_BOOTSTRAP_COMPANY="$ORION_COMPANY_NAME" \
".venv/bin/python" manage.py shell -c "
import os
from django.contrib.auth import get_user_model
from apps.core.models import Company
User = get_user_model()
email = os.environ['ORION_BOOTSTRAP_EMAIL']
password = os.environ['ORION_BOOTSTRAP_PASSWORD']
company_name = os.environ['ORION_BOOTSTRAP_COMPANY']
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser(username='admin', email=email, password=password)
    print('Super-admin créé : admin')
else:
    print('Super-admin déjà existant, non modifié.')
if not Company.objects.exists():
    Company.objects.create(name=company_name, is_active=True)
    print('Entreprise créée :', company_name)
"

chown -R orion:orion "$ORION_HOME"

# ─── [8/9] Services systemd ───────────────────────────────────────────────────

log "[8/9] Installation des services systemd..."
cp "$DEPLOY_DIR/orion-db-stack.service" /etc/systemd/system/orion-db-stack.service
sed "s#/opt/orion#${ORION_HOME}#g" "$DEPLOY_DIR/orion-backend.service" > /etc/systemd/system/orion-backend.service
sed -i "s#/opt/orion#${ORION_HOME}#g" /etc/systemd/system/orion-db-stack.service

systemctl daemon-reload
systemctl enable --now orion-db-stack.service
systemctl enable --now orion-backend.service

# ─── [9/9] Nginx ──────────────────────────────────────────────────────────────

log "[9/9] Configuration Nginx..."
sed "s#__ORION_DOMAIN__#${ORION_DOMAIN}#g" "$DEPLOY_DIR/nginx.conf.tmpl" > "/etc/nginx/sites-available/orion.conf"
ln -sf /etc/nginx/sites-available/orion.conf /etc/nginx/sites-enabled/orion.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo ""
echo "======================================================================"
echo -e " ${c_green}Installation terminée.${c_reset}"
echo "======================================================================"
echo "  URL          : http://${ORION_DOMAIN}  (HTTP pour l'instant)"
echo "  Admin        : ${ORION_ADMIN_EMAIL} (identifiant : admin)"
if [ "$GENERATED_PASSWORD" -eq 1 ]; then
echo "  Mot de passe : ${ORION_ADMIN_PASSWORD}  (généré — à changer après connexion)"
fi
echo "  Config       : ${ORION_HOME}/backend/.env"
echo "  Logs         : journalctl -u orion-backend -f"
echo ""
echo "  Pour activer HTTPS (une fois le DNS de ${ORION_DOMAIN} propagé) :"
echo "    sudo apt-get install -y certbot python3-certbot-nginx"
echo "    sudo certbot --nginx -d ${ORION_DOMAIN}"
echo ""
echo "  Pour l'envoi d'emails réels (relais SMTP auto-hébergé) :"
echo "    sudo DOMAIN=<votre-domaine-racine> ${ORION_HOME}/backend/deployment/proxmox-appliance/scripts/setup_mail_relay.sh"
echo "======================================================================"
