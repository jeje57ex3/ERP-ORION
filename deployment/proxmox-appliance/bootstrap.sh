#!/usr/bin/env bash
# Orion ERP — Point d'entrée "une ligne" pour créer une VM Proxmox.
#
# À coller directement dans le Shell du nœud Proxmox (UI) ou en SSH root@proxmox.
# Récupère le dépôt puis délègue tout le travail à deploy.sh (build de l'image +
# détection stockage/réseau + import + démarrage).
#
# Usage (une ligne) — dépôt public :
#
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/jeje57ex3/ERP-ORION/main/deployment/proxmox-appliance/bootstrap.sh)"
#
# Dépôt privé : le token doit être EXPORTÉ avant la commande. Le préfixer sur la
# même ligne (GITHUB_TOKEN=xxx bash -c "$(curl -H "...$GITHUB_TOKEN...")") ne
# marche pas : le shell évalue la substitution de commande avant d'appliquer
# l'affectation, curl reçoit donc un en-tête vide et GitHub refuse le dépôt.
#
#   export GITHUB_TOKEN=ghp_xxx
#   bash -c "$(curl -fsSL -H "Authorization: token $GITHUB_TOKEN" \
#     https://raw.githubusercontent.com/jeje57ex3/ERP-ORION/main/deployment/proxmox-appliance/bootstrap.sh)"
#
# Sans arguments, deploy.sh lance son assistant interactif (recommandé — détecte
# automatiquement les stockages/réseaux Proxmox disponibles et pose les questions
# une à une). Pour un mode non-interactif, ajouter les options de deploy.sh à la
# suite du bootstrap, ex : ... bootstrap.sh)" -- --vmid 210 --name OrionERP-Client
# (voir deploy.sh --help pour la liste complète). La VM démarre automatiquement,
# sauf --as-template.
#
# Variables reconnues :
#   GITHUB_TOKEN      Token d'accès (scope "repo") — uniquement si le dépôt est
#                      privé ; inutile sur un dépôt public.
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
# git est fourni par les depots Debian, pas par ceux de Proxmox. Or sur un host
# sans abonnement « apt-get update » sort en erreur sur les depots enterprise
# (401 Unauthorized) : chainer « update && install » laissait donc l'hote sans
# git, et le clone echouait plus loin sur un « git: command not found » qui
# masquait completement la cause. On tente l'installation directe d'abord (les
# listes Debian sont generalement deja la), et l'echec de l'update ne bloque
# plus rien.
if ! command -v git >/dev/null 2>&1; then
  echo "git absent - installation..."
  export DEBIAN_FRONTEND=noninteractive
  if ! apt-get install -y -qq git >/dev/null 2>&1; then
    apt-get update -qq || true
    if ! apt-get install -y -qq git; then
      echo "ERREUR: impossible d'installer git." >&2
      echo "  Les depots 'enterprise' de Proxmox exigent un abonnement. Sans lui," >&2
      echo "  activez le depot no-subscription (UI Proxmox : noeud > Updates >" >&2
      echo "  Repositories > Add), ou installez git a la main, puis relancez." >&2
      exit 1
    fi
  fi
  if ! command -v git >/dev/null 2>&1; then
    echo "ERREUR: git introuvable malgre une installation signalee reussie." >&2
    exit 1
  fi
  echo "  git installe."
fi

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
