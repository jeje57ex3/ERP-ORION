#!/usr/bin/env bash
# Orion ERP Appliance — Stage A / 02
# Récupère le code source (git clone), installe les dépendances Python/Node,
# et génère backend/.env avec les domaines connus depuis deploy-info.env
# (fournis au déploiement, voir deploy.sh) et des secrets générés à la volée.
# Ne démarre pas encore les services (orion-db-stack, backend...) : les
# unités systemd ne sont installées qu'à l'étape 03 — voir 03-systemd-units.sh
# pour la suite (démarrage DB, migrations, collectstatic, build des
# frontends, démarrage des services applicatifs).
# Le compte administrateur, lui, se crée via le navigateur (/setup/) — plus
# de wizard console.

set -euo pipefail
exec >> /var/log/orion-provision.log 2>&1

echo "=== [02] Déploiement Orion ERP — $(date -u +%FT%TZ) ==="

ORION_HOME="/opt/orion"
ORION_GIT_REPO_URL="${ORION_GIT_REPO_URL:-https://github.com/jeje57ex3/ERP-ORION.git}"
ORION_GIT_BRANCH="${ORION_GIT_BRANCH:-main}"

mkdir -p "$ORION_HOME"/{uploads,logs,backups,docker,nginx,scripts}

# ─── Code source (git clone) ────────────────────────────────────────────────────
if [ ! -d "$ORION_HOME/backend/.git" ]; then
  echo "[02] git clone $ORION_GIT_REPO_URL (branche $ORION_GIT_BRANCH) -> $ORION_HOME/backend"
  git clone --branch "$ORION_GIT_BRANCH" --depth 1 "$ORION_GIT_REPO_URL" "$ORION_HOME/backend"
else
  echo "[02] Dépôt déjà cloné — pull..."
  git -C "$ORION_HOME/backend" pull --ff-only || true
fi

# Alias de compatibilité avec l'arborescence demandée : "login" == même backend
# Django que "backend" (deux domaines, un seul projet — voir server_tools/orion_cloudflare_guard.py)
ln -sfn "$ORION_HOME/backend" "$ORION_HOME/login"
ln -sfn "$ORION_HOME/backend/frontend" "$ORION_HOME/frontend"

# media/ et logs/ du projet Django pointent vers les volumes persistants dédiés
mkdir -p "$ORION_HOME/backend/media" "$ORION_HOME/backend/logs"
rmdir "$ORION_HOME/backend/media" 2>/dev/null || true
rmdir "$ORION_HOME/backend/logs" 2>/dev/null || true
ln -sfn "$ORION_HOME/uploads" "$ORION_HOME/backend/media"
ln -sfn "$ORION_HOME/logs" "$ORION_HOME/backend/logs"

# ─── Environnement virtuel Python ───────────────────────────────────────────────
echo "[02] Environnement virtuel Python..."
python3 -m venv "$ORION_HOME/backend/.venv"
"$ORION_HOME/backend/.venv/bin/pip" install --upgrade pip --quiet
"$ORION_HOME/backend/.venv/bin/pip" install --no-cache-dir -r "$ORION_HOME/backend/requirements.txt"

# ─── Dépendances Node des stores (installation seule, build différé) ──────────
for store in siecle-store lunea-store; do
  DIR="$ORION_HOME/backend/frontend/$store"
  if [ -d "$DIR" ]; then
    echo "[02] npm ci — $store..."
    (cd "$DIR" && npm ci --silent)
  else
    echo "[02] ATTENTION : $DIR introuvable — ignoré."
  fi
done

# ─── docker-compose (MySQL + Redis) ────────────────────────────────────────────
cp /opt/orion-appliance/docker/docker-compose.yml "$ORION_HOME/docker/docker-compose.yml"

# ─── Fichier .env (secrets générés + domaines de ce déploiement) ──────────────
echo "[02] Génération de $ORION_HOME/backend/.env..."
VENV_PY="$ORION_HOME/backend/.venv/bin/python"
ENV_FILE="$ORION_HOME/backend/.env"

SECRET_KEY="$("$VENV_PY" -c 'import secrets; print(secrets.token_urlsafe(50))')"
FERNET_KEY="$("$VENV_PY" -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
DB_PASSWORD="$("$VENV_PY" -c 'import secrets; print(secrets.token_urlsafe(24))')"
DB_ROOT_PASSWORD="$("$VENV_PY" -c 'import secrets; print(secrets.token_urlsafe(24))')"
HA_SECRET="$("$VENV_PY" -c 'import secrets; print(secrets.token_urlsafe(32))')"

# deploy-info.env est déjà sourcé dans l'environnement par le runcmd qui a
# lancé ce script (LOGIN_DOMAIN/ORION_DOMAIN/SIECLE_DOMAIN/LUNEA_DOMAIN),
# chacun potentiellement vide si laissé de côté au déploiement.
# IP réelle de la VM (route par défaut, fiable même après l'installation de
# Docker qui ajoute ses propres interfaces bridge à `hostname -I`) : ajoutée
# à ALLOWED_HOSTS pour que le vhost nginx default_server (accès par IP avant
# tout DNS) ne se heurte pas au rejet Django "DisallowedHost" (400).
VM_IP="$(ip route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="src") print $(i+1)}' | head -1)"

ALLOWED_HOSTS="localhost,127.0.0.1${VM_IP:+,$VM_IP}"
CSRF_ORIGINS=""
CORS_ORIGINS=""
for d in "${LOGIN_DOMAIN:-}" "${ORION_DOMAIN:-}"; do
  [ -n "$d" ] && { ALLOWED_HOSTS="$ALLOWED_HOSTS,$d"; CSRF_ORIGINS="${CSRF_ORIGINS:+$CSRF_ORIGINS,}https://$d"; }
done
for d in "${SIECLE_DOMAIN:-}" "${LUNEA_DOMAIN:-}"; do
  [ -n "$d" ] && { ALLOWED_HOSTS="$ALLOWED_HOSTS,$d"; CSRF_ORIGINS="${CSRF_ORIGINS:+$CSRF_ORIGINS,}https://$d"; CORS_ORIGINS="${CORS_ORIGINS:+$CORS_ORIGINS,}https://$d"; }
done

cat > "$ENV_FILE" <<EOF
# Généré par 02-deploy-orion.sh — $(date -u +%FT%TZ)
DJANGO_SETTINGS_MODULE=erp_btp.settings.production
SECRET_KEY=$SECRET_KEY
DEBUG=False
# Désactivé par défaut : l'assistant de premier accès (/setup/) doit rester
# joignable en HTTP nu tant que TLS (certbot ou Cloudflare Tunnel) n'est pas
# en place. À repasser à True une fois HTTPS confirmé (voir PROXMOX.md).
SECURE_SSL_REDIRECT=False

ALLOWED_HOSTS=$ALLOWED_HOSTS
CSRF_TRUSTED_ORIGINS=$CSRF_ORIGINS
CORS_ALLOWED_ORIGINS=$CORS_ORIGINS

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
ORION_HA_SECRET=$HA_SECRET
ORION_ENV=production
ORION_GIT_REMOTE=origin
ORION_GIT_BRANCH=$ORION_GIT_BRANCH

SIECLE_STORE_DOMAIN=${SIECLE_DOMAIN:-}
LUNEA_STORE_DOMAIN=${LUNEA_DOMAIN:-}
SIECLE_STORE_URL=${SIECLE_DOMAIN:+https://$SIECLE_DOMAIN}
LUNEA_STORE_URL=${LUNEA_DOMAIN:+https://$LUNEA_DOMAIN}

ORION_LOGIN_DOMAIN=${LOGIN_DOMAIN:-}
ORION_FRONTEND_DOMAIN=${ORION_DOMAIN:-}

MEDIA_ROOT=media/
STATIC_ROOT=staticfiles/
BACKUP_DIR=/opt/orion/backups/
LOG_DIR=/opt/orion/logs/
EOF
chmod 600 "$ENV_FILE"

# docker compose résout les ${VARS} de docker-compose.yml via un .env situé
# dans son propre dossier de travail (distinct de env_file: qui n'alimente
# que les conteneurs) — un lien symbolique suffit, même contenu que
# backend/.env (démarrage réel du stack : voir 03-systemd-units.sh, une fois
# les unités installées).
ln -sfn "$ENV_FILE" "$ORION_HOME/docker/.env"

chown -R orion:orion "$ORION_HOME"

echo "[02] Terminé."
