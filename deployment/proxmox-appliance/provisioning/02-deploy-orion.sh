#!/usr/bin/env bash
# Orion ERP Appliance — Stage A / 02
# Récupère le code source (git clone) et installe les dépendances.
# Ne construit PAS encore les frontends SIÈCLE/LUNEA : leur build Vite embarque
# des URLs d'API qui dépendent des domaines saisis dans l'assistant de premier
# démarrage (Stage B) — voir first-boot-wizard.sh.

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

chown -R orion:orion "$ORION_HOME"

echo "[02] Terminé."
