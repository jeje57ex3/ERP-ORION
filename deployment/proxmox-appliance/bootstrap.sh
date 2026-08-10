#!/usr/bin/env bash
# Orion ERP — Point d'entrée "une ligne" pour créer une VM Proxmox.
#
# À coller directement dans le Shell du nœud Proxmox (UI) ou en SSH root@proxmox.
# Récupère le dépôt (privé — nécessite GITHUB_TOKEN) puis délègue tout le travail
# à deploy.sh (build de l'image + détection stockage/réseau + import + démarrage).
#
# Usage (une ligne) :
#
#   GITHUB_TOKEN=ghp_xxx bash -c "$(curl -fsSL -H \"Authorization: token $GITHUB_TOKEN\" \
#     https://raw.githubusercontent.com/jeje57ex3/ERP-ORION/main/deployment/proxmox-appliance/bootstrap.sh)"
#
# Sans arguments, deploy.sh lance son assistant interactif (recommandé — détecte
# automatiquement les stockages/réseaux Proxmox disponibles et pose les questions
# une à une). Pour un mode non-interactif, ajouter les options de deploy.sh à la
# suite du bootstrap, ex : ... bootstrap.sh)" -- --vmid 210 --name OrionERP-Client
# (voir deploy.sh --help pour la liste complète).
#
# Variables reconnues :
#   GITHUB_TOKEN      Token d'accès au dépôt privé (scope "repo") — requis tant
#                      que le dépôt reste privé.
#   ORION_GIT_REPO     URL du dépôt (def: https://github.com/jeje57ex3/ERP-ORION.git)
#   ORION_GIT_BRANCH    Branche à cloner (def: main)
#   ORION_BUILD_SRC     Répertoire où cloner le code source (def: /root/orion-erp-src)

set -euo pipefail

GITHUB_TOKEN="${GITHUB_TOKEN:-}"
ORION_GIT_REPO="${ORION_GIT_REPO:-https://github.com/jeje57ex3/ERP-ORION.git}"
ORION_GIT_BRANCH="${ORION_GIT_BRANCH:-main}"
ORION_BUILD_SRC="${ORION_BUILD_SRC:-/root/orion-erp-src}"

echo "======================================================"
echo " Orion ERP — Bootstrap déploiement Proxmox"
echo "======================================================"

command -v qm >/dev/null 2>&1 || {
  echo "ERREUR: commande 'qm' introuvable — ce script doit s'exécuter sur un host Proxmox VE." >&2
  exit 1
}
command -v git >/dev/null 2>&1 || { apt-get update -qq && apt-get install -y -qq git; }

CLONE_URL="$ORION_GIT_REPO"
if [ -n "$GITHUB_TOKEN" ]; then
  CLONE_URL="$(echo "$ORION_GIT_REPO" | sed "s#https://#https://${GITHUB_TOKEN}@#")"
fi

if [ -d "$ORION_BUILD_SRC/.git" ]; then
  echo "[1/2] Dépôt déjà présent dans $ORION_BUILD_SRC, mise à jour (git pull)..."
  git -C "$ORION_BUILD_SRC" pull --ff-only origin "$ORION_GIT_BRANCH"
else
  echo "[1/2] Clonage du dépôt dans $ORION_BUILD_SRC..."
  git clone --branch "$ORION_GIT_BRANCH" --depth 1 "$CLONE_URL" "$ORION_BUILD_SRC"
fi

DEPLOY_SCRIPT="$ORION_BUILD_SRC/deployment/proxmox-appliance/deploy.sh"
[ -f "$DEPLOY_SCRIPT" ] || {
  echo "ERREUR: deploy.sh introuvable dans le dépôt cloné ($DEPLOY_SCRIPT)." >&2
  exit 1
}
chmod +x "$DEPLOY_SCRIPT"

echo "[2/2] Lancement de deploy.sh..."
echo ""
exec "$DEPLOY_SCRIPT" "$@"
