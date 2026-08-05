#!/usr/bin/env bash
# Orion ERP — Déploiement Proxmox 100% automatique.
#
# À exécuter DIRECTEMENT sur le host Proxmox (Shell du nœud dans l'UI, ou SSH
# root@proxmox). Proxmox VE fournit déjà qemu-img/qm/pvesh/pvesm nativement —
# aucune installation manuelle requise. Enchaîne : build de l'image (si besoin)
# + détection auto du stockage/bridge/VMID + import + démarrage de la VM.
#
# Usage :
#   ./deploy.sh [VERSION] [options]
#
# Options (toutes optionnelles — valeurs auto-détectées sinon) :
#   --vmid ID              ID de VM (def: prochain ID libre — pvesh get /cluster/nextid)
#   --name NAME             Nom de la VM (def: OrionERP)
#   --storage STORAGE       Stockage disque (def: 1er stockage supportant "images")
#   --snippets-storage S    Stockage pour le cloud-init personnalisé (def: idem, sinon "local")
#   --bridge BRIDGE         Bridge réseau (def: 1er vmbr* détecté, sinon vmbr0)
#   --memory MB             RAM en Mo (def: 8192)
#   --cores N               vCPU (def: 4)
#   --sshkey PATH           Clé publique SSH à injecter (def: aucune)
#   --as-template           Convertit la VM en template après import (pas de démarrage)
#   --rebuild                Reconstruit l'image même si build/OrionERP.qcow2 existe déjà
#   --skip-build             Réutilise le build/ existant sans reconstruire (échoue s'il est absent)
#   -h, --help                Affiche cette aide

set -euo pipefail

VERSION=""
VMID=""
VM_NAME="OrionERP"
STORAGE=""
SNIPPETS_STORAGE=""
BRIDGE=""
MEMORY=8192
CORES=4
SSHKEY=""
AS_TEMPLATE=0
REBUILD=0
SKIP_BUILD=0

usage() { sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'; }

# Le premier argument positionnel (s'il ne commence pas par --) est la VERSION.
if [ $# -gt 0 ] && [[ "$1" != --* ]] && [ "$1" != "-h" ]; then
  VERSION="$1"; shift
fi

while [ $# -gt 0 ]; do
  case "$1" in
    --vmid) VMID="$2"; shift 2 ;;
    --name) VM_NAME="$2"; shift 2 ;;
    --storage) STORAGE="$2"; shift 2 ;;
    --snippets-storage) SNIPPETS_STORAGE="$2"; shift 2 ;;
    --bridge) BRIDGE="$2"; shift 2 ;;
    --memory) MEMORY="$2"; shift 2 ;;
    --cores) CORES="$2"; shift 2 ;;
    --sshkey) SSHKEY="$2"; shift 2 ;;
    --as-template) AS_TEMPLATE=1; shift ;;
    --rebuild) REBUILD=1; shift ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Option inconnue : $1" >&2; usage; exit 1 ;;
  esac
done

VERSION="${VERSION:-$(date -u +%Y.%m.%d)}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$ROOT_DIR/build"

echo "======================================================"
echo " Orion ERP — Déploiement automatique Proxmox"
echo "======================================================"

# ─── Vérifie qu'on est bien sur un host Proxmox ────────────────────────────────
command -v qm >/dev/null 2>&1 || {
  echo "ERREUR: commande 'qm' introuvable — ce script doit s'exécuter sur un host Proxmox VE." >&2
  exit 1
}

# ─── Étape 1 — Build de l'image (Proxmox fournit déjà qemu-img) ───────────────
if [ "$SKIP_BUILD" -eq 1 ]; then
  echo "[1/3] --skip-build : réutilisation de $BUILD_DIR tel quel."
  [ -f "$BUILD_DIR/OrionERP.qcow2" ] || { echo "ERREUR: $BUILD_DIR/OrionERP.qcow2 introuvable." >&2; exit 1; }
elif [ "$REBUILD" -eq 0 ] && [ -f "$BUILD_DIR/OrionERP.qcow2" ]; then
  echo "[1/3] Image déjà construite ($BUILD_DIR/OrionERP.qcow2) — réutilisation."
  echo "      (utiliser --rebuild pour forcer une reconstruction)"
else
  echo "[1/3] Construction de l'image (version $VERSION)..."
  "$SCRIPT_DIR/build.sh" "$VERSION"
fi

# ─── Étape 2 — Détection automatique des paramètres Proxmox ───────────────────
echo ""
echo "[2/3] Détection automatique de l'environnement Proxmox..."

if [ -z "$VMID" ]; then
  VMID="$(pvesh get /cluster/nextid 2>/dev/null | tr -d '[:space:]')"
  VMID="${VMID:-9000}"
fi

if [ -z "$STORAGE" ]; then
  STORAGE="$(pvesm status --content images 2>/dev/null | awk 'NR==2{print $1}')"
  STORAGE="${STORAGE:-local-lvm}"
fi

if [ -z "$SNIPPETS_STORAGE" ]; then
  SNIPPETS_STORAGE="$(pvesm status --content snippets 2>/dev/null | awk 'NR==2{print $1}')"
  SNIPPETS_STORAGE="${SNIPPETS_STORAGE:-local}"
fi

if [ -z "$BRIDGE" ]; then
  BRIDGE="$(ip -o link show type bridge 2>/dev/null | awk -F': ' '{print $2}' | grep '^vmbr' | head -1)"
  BRIDGE="${BRIDGE:-vmbr0}"
fi

echo "  VMID               : $VMID (auto si non précisé)"
echo "  Nom                : $VM_NAME"
echo "  Stockage disque    : $STORAGE"
echo "  Stockage snippets  : $SNIPPETS_STORAGE"
echo "  Bridge             : $BRIDGE"
echo "  RAM / vCPU         : ${MEMORY}Mo / ${CORES}"

# ─── Étape 3 — Import + démarrage ──────────────────────────────────────────────
echo ""
echo "[3/3] Création de la VM..."

IMPORT_ARGS=(
  --vmid "$VMID" --name "$VM_NAME" --storage "$STORAGE"
  --snippets-storage "$SNIPPETS_STORAGE" --bridge "$BRIDGE"
  --memory "$MEMORY" --cores "$CORES"
  --disk "$BUILD_DIR/OrionERP.qcow2"
)
[ -n "$SSHKEY" ] && IMPORT_ARGS+=(--sshkey "$SSHKEY")
if [ "$AS_TEMPLATE" -eq 1 ]; then
  IMPORT_ARGS+=(--as-template)
else
  IMPORT_ARGS+=(--start)
fi

# import_proxmox.sh cherche les fichiers cloud-init à côté de lui-même : on
# l'exécute donc directement depuis build/, où build.sh les a tous rassemblés.
(cd "$BUILD_DIR" && bash ./import_proxmox.sh "${IMPORT_ARGS[@]}")

echo ""
echo "======================================================"
echo " Terminé — VM $VMID ($VM_NAME) prête."
echo "======================================================"
if [ "$AS_TEMPLATE" -eq 0 ]; then
  echo ""
  echo "Suivre le premier démarrage via la console noVNC :"
  echo "  Proxmox UI -> $VM_NAME -> Console"
  echo "(~2-5 min de provisioning automatique, puis l'assistant interactif démarre)"
fi
