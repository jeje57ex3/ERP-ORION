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

# Fonctions communes : $HOME garanti, lecture du .env sans l'exécuter,
# vérifications. Voir lib/commun.sh pour les quatre pannes qu'elles suppriment.
# shellcheck source=lib/commun.sh
. "$(dirname "${BASH_SOURCE[0]}")/lib/commun.sh"
ORION_ETAPE='02'
journaliser_vers_fichier_et_console

echo "=== [02] Déploiement Orion ERP — $(date -u +%FT%TZ) ==="

# git clone en root, puis chown vers orion : sans cette autorisation, toute
# commande git ultérieure lancée par root (mise à jour depuis l'interface,
# diagnostic par « qm guest exec ») est refusée pour « dubious ownership ».
autoriser_git_systeme

ORION_HOME="/opt/orion"
ORION_GIT_REPO_URL="${ORION_GIT_REPO_URL:-https://github.com/jeje57ex3/ERP-ORION.git}"
ORION_GIT_BRANCH="${ORION_GIT_BRANCH:-main}"

mkdir -p "$ORION_HOME"/{uploads,logs,backups,docker,nginx,scripts}

# ─── Code source (git clone) ────────────────────────────────────────────────────
# Si le dépôt est privé, GITHUB_TOKEN (deploy-info.env, --github-token au
# déploiement) est injecté via un en-tête HTTP temporaire (-c
# http.extraheader) plutôt que dans l'URL — n'est jamais écrit dans
# .git/config ni journalisé en clair (voir apps/system_updates/git_service.py
# pour le même mécanisme côté mises à jour applicatives).
GIT_AUTH_ARGS=()
if [ -n "${GITHUB_TOKEN:-}" ]; then
  GIT_AUTH_HEADER="AUTHORIZATION: basic $(printf '%s' "x-access-token:$GITHUB_TOKEN" | base64 -w0)"
  GIT_AUTH_ARGS=(-c "http.extraheader=$GIT_AUTH_HEADER")
fi

if [ ! -d "$ORION_HOME/backend/.git" ]; then
  echo "[02] git clone $ORION_GIT_REPO_URL (branche $ORION_GIT_BRANCH) -> $ORION_HOME/backend"
  git "${GIT_AUTH_ARGS[@]}" clone --branch "$ORION_GIT_BRANCH" --depth 1 "$ORION_GIT_REPO_URL" "$ORION_HOME/backend"
else
  echo "[02] Dépôt déjà cloné — pull..."
  git -C "$ORION_HOME/backend" "${GIT_AUTH_ARGS[@]}" pull --ff-only || true
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

# ─── Dépendances Node des frontends (installation seule, build différé) ───────
# neostructura-site est un site vitrine, pas une boutique, mais vit dans le même
# dossier frontend/ et se construit de la même façon.
for store in siecle-store lunea-store neostructura-site; do
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
VM_IP="$(ip route get 1.1.1.1 2>/dev/null | awk '{for (i=1;i<=NF;i++) if ($i=="src") print $(i+1)}' | head -1)" || true

ALLOWED_HOSTS="localhost,127.0.0.1${VM_IP:+,$VM_IP}"
CSRF_ORIGINS=""
CORS_ORIGINS=""
# NS_DOMAIN est ici et non dans le groupe suivant : le SPA NÉOSTRUCTURA est
# servi par Nginx sur la MÊME origine que l'API qu'il appelle en relatif, il
# n'a donc pas besoin d'entrée CORS — seulement d'être un hôte autorisé.
# NODE_DOMAIN est le sous-domaine propre à cette machine (haute
# disponibilité) : les autres nœuds appellent /ha/health/ dessus, et il sert
# de cible à l'enregistrement d'indirection de la bascule. Sans lui dans
# ALLOWED_HOSTS, chaque battement de cœur repart en 400 DisallowedHost.
for d in "${LOGIN_DOMAIN:-}" "${ORION_DOMAIN:-}" "${NS_DOMAIN:-}" "${NODE_DOMAIN:-}"; do
  [ -n "$d" ] && { ALLOWED_HOSTS="$ALLOWED_HOSTS,$d"; CSRF_ORIGINS="${CSRF_ORIGINS:+$CSRF_ORIGINS,}https://$d"; }
done
for d in "${SIECLE_DOMAIN:-}" "${LUNEA_DOMAIN:-}"; do
  [ -n "$d" ] && { ALLOWED_HOSTS="$ALLOWED_HOSTS,$d"; CSRF_ORIGINS="${CSRF_ORIGINS:+$CSRF_ORIGINS,}https://$d"; CORS_ORIGINS="${CORS_ORIGINS:+$CORS_ORIGINS,}https://$d"; }
done

# ─── Identité du nœud, déduite de son sous-domaine ────────────────────────────
# Ces trois clés n'étaient écrites nulle part : toutes les machines prenaient
# donc les valeurs par défaut des settings, « orion-primary » et rang 1. Deux
# conséquences graves et parfaitement silencieuses :
#
#   - l'adhésion à la grappe voyait partout le même identifiant, et refusait
#     chaque nouveau serveur comme un doublon ;
#   - la protection anti-divergence compare ORION_NODE_ID au verrou de grappe,
#     si bien que CHAQUE serveur se croyait titulaire de la main — la
#     protection la plus importante du module était inerte.
#
# La convention de nommage fournit tout : « serveur2.exemple.fr » donne
# l'identifiant « serveur2 » et le rang 2. Sans --node-domain, on retombe
# exactement sur les anciennes valeurs par défaut, donc aucun changement pour
# une installation à serveur unique.
NODE_LABEL="${NODE_DOMAIN%%.*}"
NODE_RANK="$(printf '%s' "$NODE_LABEL" | tr -dc '0-9')"
NODE_RANK="${NODE_RANK:-1}"
NODE_ID="${NODE_LABEL:-orion-primary}"
if [ "$NODE_RANK" = "1" ]; then NODE_ROLE="primary"; else NODE_ROLE="secondary"; fi
echo "[02] Identité du nœud : $NODE_ID (rang $NODE_RANK, rôle $NODE_ROLE)"

cat > "$ENV_FILE" <<EOF
# Généré par 02-deploy-orion.sh — $(date -u +%FT%TZ)
#
# TOUTES les valeurs sont entre guillemets, y compris celles qui n'en ont
# aucun besoin. Une seule valeur à espaces laissée nue a déjà rendu le
# provisioning d'une VM neuve fatal ET muet : le shell lisait « VAR=sudo »
# puis exécutait « -n », d'où un exit 127 qui ne nommait ni la clé ni le
# fichier, et un symptôme final — toutes les pages en 500 — sans rapport
# apparent. Une règle uniforme se vérifie d'un coup d'œil ; une exception
# « seulement là où c'est nécessaire » se perd au premier ajout de clé.
#
# Les trois lecteurs de ce fichier sont indifférents aux guillemets, vérifié :
# python-decouple (Django), l'EnvironmentFile de systemd, et charger_env
# (lib/commun.sh). Ne jamais sourcer ce fichier avec « . » : les guillemets
# doubles n'y protègent ni « \$ » ni l'accent grave.
DJANGO_SETTINGS_MODULE="erp_btp.settings.production"
SECRET_KEY="$SECRET_KEY"
DEBUG="False"
# Désactivés par défaut : l'assistant de premier accès (/setup/) doit rester
# joignable — et son formulaire soumissible (cookie CSRF) — en HTTP nu tant
# que TLS (certbot ou Cloudflare Tunnel) n'est pas en place. Un cookie
# "Secure" ne revient jamais au serveur sur une connexion HTTP, ce qui
# ferait échouer toute soumission de formulaire avec un 403 CSRF. À repasser
# les trois à True une fois HTTPS confirmé (voir PROXMOX.md).
SECURE_SSL_REDIRECT="False"
SESSION_COOKIE_SECURE="False"
CSRF_COOKIE_SECURE="False"

ALLOWED_HOSTS="$ALLOWED_HOSTS"
CSRF_TRUSTED_ORIGINS="$CSRF_ORIGINS"
CORS_ALLOWED_ORIGINS="$CORS_ORIGINS"

DB_ENGINE="django.db.backends.mysql"
DB_NAME="orion_core"
DB_USER="orion"
DB_PASSWORD="$DB_PASSWORD"
DB_ROOT_PASSWORD="$DB_ROOT_PASSWORD"
DB_HOST="127.0.0.1"
DB_PORT="3306"

REDIS_URL="redis://127.0.0.1:6379/0"
CACHE_URL="redis://127.0.0.1:6379/1"

ORION_SECRET_ENCRYPTION_KEY="$FERNET_KEY"
ORION_HA_SECRET="$HA_SECRET"

# Identité de CE serveur dans la grappe. Doit être distincte sur chaque
# machine : c'est cet identifiant que la protection anti-divergence compare au
# verrou de grappe, et celui que les autres serveurs relèvent à l'adhésion.
ORION_NODE_ID="$NODE_ID"
ORION_NODE_ROLE="$NODE_ROLE"
ORION_NODE_PRIORITY="$NODE_RANK"
ORION_ENV="production"
ORION_GIT_REMOTE="origin"
ORION_GIT_BRANCH="$ORION_GIT_BRANCH"

SIECLE_STORE_DOMAIN="${SIECLE_DOMAIN:-}"
LUNEA_STORE_DOMAIN="${LUNEA_DOMAIN:-}"
SIECLE_STORE_URL="${SIECLE_DOMAIN:+https://$SIECLE_DOMAIN}"
LUNEA_STORE_URL="${LUNEA_DOMAIN:+https://$LUNEA_DOMAIN}"

ORION_LOGIN_DOMAIN="${LOGIN_DOMAIN:-}"
ORION_FRONTEND_DOMAIN="${ORION_DOMAIN:-}"
# Lu par refresh_allowed_hosts.sh, qui réécrit ALLOWED_HOSTS à chaque
# démarrage de service : sans ce champ, le domaine NÉOSTRUCTURA en était
# effacé au premier redémarrage.
ORION_NS_DOMAIN="${NS_DOMAIN:-}"
# Sous-domaine de CETTE machine, également relu par refresh_allowed_hosts.sh.
# Vide sur une installation isolée : la haute disponibilité est alors inutile.
ORION_NODE_DOMAIN="${NODE_DOMAIN:-}"

# Redémarrage de Celery après une mise à jour lancée depuis l'interface.
# ORION_UPDATE_RESTART_COMMAND est volontairement laissé VIDE : il
# redémarrerait orion-backend, c'est-à-dire le processus qui exécute la mise à
# jour, qui serait tué avant de pouvoir l'enregistrer. Le redémarrage du
# backend est fait par update_orion.sh, depuis l'extérieur.
ORION_UPDATE_CELERY_RESTART_COMMAND="sudo -n systemctl restart orion-celery"
ORION_UPDATE_CELERY_BEAT_RESTART_COMMAND="sudo -n systemctl restart orion-celery-beat"

MEDIA_ROOT="media/"
STATIC_ROOT="staticfiles/"
BACKUP_DIR="/opt/orion/backups/"
LOG_DIR="/opt/orion/logs/"
EOF
chmod 600 "$ENV_FILE"

# ─── Validation immédiate, par les lecteurs réels ─────────────────────────────
# Un .env malformé ne se voyait qu'en aval, et jamais sous son vrai nom : une
# étape ultérieure mourait en exit 127, les services ne démarraient pas, nginx
# renvoyait 502 — ou, pire, l'ERP démarrait et toutes ses pages renvoyaient 500
# parce que collectstatic avait été sauté. On le valide donc ici, à l'endroit
# et à l'instant où il est écrit, par les deux lecteurs qui compteront
# vraiment : charger_env côté scripts, python-decouple côté Django.
if ! ( charger_env "$ENV_FILE" ) >/dev/null 2>&1; then
  echo "[02] ERREUR : $ENV_FILE illisible par charger_env — arrêt." >&2
  exit 1
fi

CLES_MANQUANTES=()
for cle in SECRET_KEY ALLOWED_HOSTS DB_NAME DB_USER DB_PASSWORD DB_HOST            ORION_SECRET_ENCRYPTION_KEY ORION_NODE_ID; do
  [ -n "$(valeur_env "$ENV_FILE" "$cle")" ] || CLES_MANQUANTES+=("$cle")
done
if [ ${#CLES_MANQUANTES[@]} -gt 0 ]; then
  echo "[02] ERREUR : clés vides ou absentes dans $ENV_FILE :" >&2
  echo "[02]   ${CLES_MANQUANTES[*]}" >&2
  echo "[02] Django ne démarrerait pas, ou démarrerait mal. Arrêt." >&2
  exit 1
fi

# Le vrai lecteur de Django, pas une approximation : python-decouple refuse
# certaines formes que le shell accepte, et l'inverse est vrai aussi.
if ! "$VENV_PY" - "$ENV_FILE" <<'PYVERIF'
import sys
from decouple import Config, RepositoryEnv

chemin = sys.argv[1]
config = Config(RepositoryEnv(chemin))
for cle in ('SECRET_KEY', 'ALLOWED_HOSTS', 'DB_PASSWORD',
            'ORION_SECRET_ENCRYPTION_KEY', 'ORION_NODE_ID'):
    valeur = config.get(cle, default='')
    if not valeur:
        print('cle vide pour python-decouple : %s' % cle, file=sys.stderr)
        raise SystemExit(1)
    # Un guillemet résiduel signalerait un double niveau de citation : la
    # valeur serait alors utilisée AVEC ses guillemets, et un mot de passe de
    # base ou une clé Fernet ainsi déformés échouent sans dire pourquoi.
    if valeur.startswith('"') or valeur.endswith('"'):
        print('guillemet residuel dans %s : %r' % (cle, valeur), file=sys.stderr)
        raise SystemExit(1)
PYVERIF
then
  echo "[02] ERREUR : $ENV_FILE rejeté par python-decouple (détail ci-dessus)." >&2
  exit 1
fi
dire ".env validé par charger_env et par python-decouple."

# docker compose résout les ${VARS} de docker-compose.yml via un .env situé
# dans son propre dossier de travail (distinct de env_file: qui n'alimente
# que les conteneurs) — un lien symbolique suffit, même contenu que
# backend/.env (démarrage réel du stack : voir 03-systemd-units.sh, une fois
# les unités installées).
ln -sfn "$ENV_FILE" "$ORION_HOME/docker/.env"

chown -R orion:orion "$ORION_HOME"

echo "[02] Terminé."
