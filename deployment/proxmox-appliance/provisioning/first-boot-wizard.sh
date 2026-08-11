#!/usr/bin/env bash
# Orion ERP Appliance — Stage B : assistant interactif de premier démarrage.
# Exécuté sur la console série (ttyS0) par orion-first-boot.service, une seule
# fois (protégé par le flag /opt/orion/.awaiting-setup).

set -euo pipefail

ORION_HOME="/opt/orion"
ENV_FILE="$ORION_HOME/backend/.env"
FLAG_FILE="$ORION_HOME/.awaiting-setup"
LOG_FILE="$ORION_HOME/logs/first-boot-wizard.log"
VENV_PY="$ORION_HOME/backend/.venv/bin/python"
MANAGE="$ORION_HOME/backend/manage.py"

mkdir -p "$ORION_HOME/logs"
exec > >(tee -a "$LOG_FILE") 2>&1

c_reset="\e[0m"; c_bold="\e[1m"; c_cyan="\e[36m"; c_green="\e[32m"; c_yellow="\e[33m"

clear
echo -e "${c_bold}${c_cyan}"
echo "============================================================"
echo "   Orion ERP — Assistant de premier démarrage"
echo "============================================================"
echo -e "${c_reset}"
echo "Cette configuration ne s'exécute qu'une seule fois."
echo ""

ask() {
  local prompt="$1" default="${2:-}" var
  if [ -n "$default" ]; then
    read -r -p "$prompt [$default] : " var
    echo "${var:-$default}"
  else
    while true; do
      read -r -p "$prompt : " var
      [ -n "$var" ] && { echo "$var"; return; }
      echo "  -> requis." >&2
    done
  fi
}

ask_secret() {
  local prompt="$1" var confirm
  while true; do
    read -r -s -p "$prompt : " var; echo
    read -r -s -p "Confirmer : " confirm; echo
    [ "$var" = "$confirm" ] && [ -n "$var" ] && { echo "$var"; return; }
    echo "  -> les deux saisies ne correspondent pas, réessayer." >&2
  done
}

ask_optional_secret() {
  local prompt="$1" var
  read -r -s -p "$prompt (laisser vide pour ignorer) : " var; echo
  echo "$var"
}

ask_yesno() {
  local prompt="$1" default="${2:-n}" var
  read -r -p "$prompt [o/N] : " var
  var="${var:-$default}"
  [[ "$var" =~ ^[oOyY] ]]
}

echo -e "${c_bold}--- Entreprise ---${c_reset}"
COMPANY_NAME="$(ask "Nom de l'entreprise")"
ERP_NAME="$(ask "Nom de l'ERP" "Orion ERP")"

echo ""
echo -e "${c_bold}--- Domaines publics ---${c_reset}"
LOGIN_DOMAIN="$(ask "Domaine Login (ERP / admin)")"
ORION_DOMAIN="$(ask "Domaine Orion (vitrine)")"
SIECLE_DOMAIN="$(ask "Domaine SIÈCLE")"
LUNEA_DOMAIN="$(ask "Domaine LUNEA")"

echo ""
echo -e "${c_bold}--- Administrateur ---${c_reset}"
ADMIN_EMAIL="$(ask "Email administrateur")"
ADMIN_PASSWORD="$(ask_secret "Mot de passe administrateur")"

echo ""
echo -e "${c_bold}--- Système ---${c_reset}"
DEFAULT_TZ="$(timedatectl show -p Timezone --value 2>/dev/null || echo UTC)"
while true; do
  TIMEZONE="$(ask "Fuseau horaire (ex: Europe/Paris)" "$DEFAULT_TZ")"
  timedatectl list-timezones 2>/dev/null | grep -qx "$TIMEZONE" && break
  echo "  -> fuseau horaire inconnu, réessayer." >&2
done

echo ""
echo -e "${c_bold}--- Cloudflare Tunnel (optionnel) ---${c_reset}"
CF_TOKEN="$(ask_optional_secret "Cloudflare Tunnel Token")"

echo ""
echo -e "${c_yellow}Récapitulatif :${c_reset}"
echo "  Entreprise      : $COMPANY_NAME"
echo "  ERP             : $ERP_NAME"
echo "  Login           : $LOGIN_DOMAIN"
echo "  Orion           : $ORION_DOMAIN"
echo "  SIÈCLE          : $SIECLE_DOMAIN"
echo "  LUNEA           : $LUNEA_DOMAIN"
echo "  Admin           : $ADMIN_EMAIL"
echo "  Fuseau horaire  : $TIMEZONE"
echo "  Cloudflare      : $([ -n "$CF_TOKEN" ] && echo "token fourni" || echo "non configuré (activable plus tard)")"
echo ""
if ! ask_yesno "Confirmer et lancer la configuration ?" "o"; then
  echo "Annulé — l'assistant se relancera au prochain démarrage."
  exit 1
fi

echo ""
echo "=== Configuration en cours — cela peut prendre plusieurs minutes ==="

# ─── Fuseau horaire ─────────────────────────────────────────────────────────
timedatectl set-timezone "$TIMEZONE" || echo "ATTENTION: impossible de définir le fuseau horaire."

# ─── Génération des secrets ─────────────────────────────────────────────────
echo "[1/9] Génération des secrets..."
SECRET_KEY="$("$VENV_PY" -c 'import secrets; print(secrets.token_urlsafe(50))')"
FERNET_KEY="$("$VENV_PY" -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
DB_PASSWORD="$("$VENV_PY" -c 'import secrets; print(secrets.token_urlsafe(24))')"
DB_ROOT_PASSWORD="$("$VENV_PY" -c 'import secrets; print(secrets.token_urlsafe(24))')"
HA_SECRET="$("$VENV_PY" -c 'import secrets; print(secrets.token_urlsafe(32))')"

# ─── Fichier .env ────────────────────────────────────────────────────────────
echo "[2/9] Écriture de $ENV_FILE..."
cat > "$ENV_FILE" <<EOF
# Généré par first-boot-wizard.sh — $(date -u +%FT%TZ)
DJANGO_SETTINGS_MODULE=erp_btp.settings.production
SECRET_KEY=$SECRET_KEY
DEBUG=False

ALLOWED_HOSTS=$LOGIN_DOMAIN,$ORION_DOMAIN,$SIECLE_DOMAIN,$LUNEA_DOMAIN,localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=https://$LOGIN_DOMAIN,https://$ORION_DOMAIN,https://$SIECLE_DOMAIN,https://$LUNEA_DOMAIN
CORS_ALLOWED_ORIGINS=https://$SIECLE_DOMAIN,https://$LUNEA_DOMAIN

DB_ENGINE=django.db.backends.mysql
DB_NAME=orion_core
DB_USER=orion
DB_PASSWORD=$DB_PASSWORD
DB_ROOT_PASSWORD=$DB_ROOT_PASSWORD
DB_HOST=127.0.0.1
DB_PORT=3306

REDIS_URL=redis://127.0.0.1:6379/0
CACHE_URL=redis://127.0.0.1:6379/1

ORION_SECRET_ENCRYPTION_KEY=$FERNET_KEY
ORION_SUPERADMIN_EMAIL=$ADMIN_EMAIL
ORION_HA_SECRET=$HA_SECRET

ORION_COMPANY_NAME=$COMPANY_NAME
ORION_ERP_DISPLAY_NAME=$ERP_NAME
ORION_ENV=production
ORION_GIT_REMOTE=origin
ORION_GIT_BRANCH=main

SIECLE_STORE_DOMAIN=$SIECLE_DOMAIN
LUNEA_STORE_DOMAIN=$LUNEA_DOMAIN
SIECLE_STORE_URL=https://$SIECLE_DOMAIN
LUNEA_STORE_URL=https://$LUNEA_DOMAIN

ORION_LOGIN_DOMAIN=$LOGIN_DOMAIN
ORION_FRONTEND_DOMAIN=$ORION_DOMAIN

MEDIA_ROOT=media/
STATIC_ROOT=staticfiles/
BACKUP_DIR=/opt/orion/backups/
LOG_DIR=/opt/orion/logs/
EOF
chown orion:orion "$ENV_FILE"
chmod 600 "$ENV_FILE"

# ─── Infrastructure MySQL / Redis ──────────────────────────────────────────────
echo "[3/9] Démarrage MySQL / Redis..."
# docker compose résout les ${VARS} de docker-compose.yml via un .env situé
# dans son propre dossier de travail (distinct de env_file: qui n'alimente que
# les conteneurs) — un lien symbolique suffit, même contenu que backend/.env.
ln -sfn "$ENV_FILE" "$ORION_HOME/docker/.env"
systemctl start orion-db-stack.service
/opt/orion/scripts/wait_for_port.sh 127.0.0.1 3306 120
/opt/orion/scripts/wait_for_port.sh 127.0.0.1 6379 60
sleep 5

# ─── Migrations, collectstatic, superadmin ─────────────────────────────────────
echo "[4/9] Migrations Django..."
set -a; . "$ENV_FILE"; set +a
sudo -u orion -E "$VENV_PY" "$MANAGE" migrate --noinput

echo "[5/9] Collecte des fichiers statiques..."
sudo -u orion -E "$VENV_PY" "$MANAGE" collectstatic --noinput

echo "[6/9] Création du compte administrateur..."
# Passage par variables d'environnement (et non interpolation shell directe
# dans la source Python) : un mot de passe/email contenant un guillemet
# simple casserait la syntaxe Python, voire s'y injecterait.
export ORION_BOOTSTRAP_ADMIN_EMAIL="$ADMIN_EMAIL"
export ORION_BOOTSTRAP_ADMIN_PASSWORD="$ADMIN_PASSWORD"
sudo -u orion -E "$VENV_PY" "$MANAGE" shell -c "
import os
from django.contrib.auth import get_user_model
User = get_user_model()
email = os.environ['ORION_BOOTSTRAP_ADMIN_EMAIL']
password = os.environ['ORION_BOOTSTRAP_ADMIN_PASSWORD']
if not User.objects.filter(email=email).exists():
    User.objects.create_superuser(username='admin', email=email, password=password)
    print('Superadmin créé:', email)
else:
    print('Superadmin existant:', email)
"
unset ORION_BOOTSTRAP_ADMIN_PASSWORD

# ─── Build des frontends (URLs d'API désormais connues) ───────────────────────
echo "[7/9] Build des frontends SIÈCLE / LUNEA..."
mkdir -p "$ORION_HOME/siecle" "$ORION_HOME/lunea"

if [ -d "$ORION_HOME/backend/frontend/siecle-store" ]; then
  (cd "$ORION_HOME/backend/frontend/siecle-store" && \
    VITE_API_BASE_URL="https://$LOGIN_DOMAIN/api/v1" npm run build) \
    && rm -rf "$ORION_HOME/siecle"/* \
    && cp -r "$ORION_HOME/backend/frontend/siecle-store/dist/." "$ORION_HOME/siecle/" \
    || echo "ATTENTION: build SIÈCLE échoué — le service siecle-frontend restera vide."
fi

if [ -d "$ORION_HOME/backend/frontend/lunea-store" ]; then
  (cd "$ORION_HOME/backend/frontend/lunea-store" && \
    VITE_API_BASE_URL="https://$LOGIN_DOMAIN/api/v1" npm run build) \
    && rm -rf "$ORION_HOME/lunea"/* \
    && cp -r "$ORION_HOME/backend/frontend/lunea-store/dist/." "$ORION_HOME/lunea/" \
    || echo "ATTENTION: build LUNEA échoué — le service lunea-frontend restera vide."
fi
chown -R orion:orion "$ORION_HOME/siecle" "$ORION_HOME/lunea"

# ─── Nginx (domaines réels) ─────────────────────────────────────────────────────
echo "[8/9] Configuration Nginx..."
sed \
  -e "s/__LOGIN_DOMAIN__/$LOGIN_DOMAIN/g" \
  -e "s/__ORION_DOMAIN__/$ORION_DOMAIN/g" \
  -e "s/__SIECLE_DOMAIN__/$SIECLE_DOMAIN/g" \
  -e "s/__LUNEA_DOMAIN__/$LUNEA_DOMAIN/g" \
  "$ORION_HOME/nginx/orion-proxmox.conf.tmpl" > /etc/nginx/sites-available/orion.conf
nginx -t && systemctl reload nginx

if ask_yesno "Configurer Let's Encrypt maintenant (nécessite le port 80 accessible publiquement) ?" "n"; then
  certbot --nginx --non-interactive --agree-tos -m "$ADMIN_EMAIL" \
    -d "$LOGIN_DOMAIN" -d "$ORION_DOMAIN" -d "$SIECLE_DOMAIN" -d "$LUNEA_DOMAIN" \
    || echo "ATTENTION: certbot a échoué — à relancer manuellement plus tard (voir PROXMOX.md)."
fi

# ─── Cloudflare Tunnel ───────────────────────────────────────────────────────────
if [ -n "$CF_TOKEN" ]; then
  echo "[9/9] Activation du tunnel Cloudflare..."
  cloudflared service install "$CF_TOKEN" \
    && echo "  -> Pense à déclarer les 4 hostnames dans le dashboard Zero Trust :" \
    && echo "     $LOGIN_DOMAIN  -> http://localhost:9000" \
    && echo "     $ORION_DOMAIN  -> http://localhost:5172" \
    && echo "     $SIECLE_DOMAIN -> http://localhost:5173" \
    && echo "     $LUNEA_DOMAIN  -> http://localhost:5174" \
    || echo "ATTENTION: installation du tunnel échouée — relancer : cloudflared service install <token>"
else
  echo "[9/9] Aucun token Cloudflare fourni — tunnel désactivé (voir PROXMOX.md pour l'activer plus tard)."
fi

# ─── Démarrage des services applicatifs ────────────────────────────────────────
echo ""
echo "Démarrage des services Orion..."
systemctl start orion-backend.service
systemctl start orion-frontend.service
systemctl start siecle-frontend.service
systemctl start lunea-frontend.service
systemctl enable --now orion-health.timer

rm -f "$FLAG_FILE"

echo ""
echo -e "${c_bold}${c_green}"
echo "============================================================"
echo "   Orion ERP est prêt !"
echo "============================================================"
echo -e "${c_reset}"
echo "  Login  : https://$LOGIN_DOMAIN  (admin: $ADMIN_EMAIL)"
echo "  Orion  : https://$ORION_DOMAIN"
echo "  SIÈCLE : https://$SIECLE_DOMAIN"
echo "  LUNEA  : https://$LUNEA_DOMAIN"
echo ""
echo "  Tableau de bord système : sudo /opt/orion/scripts/orion-dashboard.sh"
echo "  Journal de cette installation : $LOG_FILE"
echo ""
read -r -p "Appuyer sur Entrée pour continuer..." _ || true
