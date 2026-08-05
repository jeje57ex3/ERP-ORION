#!/usr/bin/env bash
# Orion ERP — Appliance Proxmox — Orchestrateur de build
#
# Doit être exécuté sur un hôte LINUX disposant de qemu-img (paquet qemu-utils),
# curl, python3, tar, sha1sum/sha256sum — typiquement le serveur Proxmox
# lui-même via SSH, ou toute VM/CI Linux. Ne fonctionne PAS sur Windows natif.
#
# Usage : ./build.sh [VERSION]
#   VERSION  Étiquette de version (def: date du jour, ex: 2026.08.05)
#
# Variables d'environnement optionnelles :
#   ORION_GIT_REPO_URL   Dépôt à cloner sur la VM au premier boot
#                         (def: https://github.com/jeje57ex3/ERP-ORION.git)
#   ORION_GIT_BRANCH      Branche à cloner (def: main)
#   UBUNTU_IMG_URL         URL de l'image cloud Ubuntu 24.04 (def: image officielle)
#   DISK_SIZE               Taille du disque virtuel (def: 80G)

set -euo pipefail

VERSION="${1:-$(date -u +%Y.%m.%d)}"
BUILD_DATE="$(date -u +%FT%TZ)"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export APPLIANCE_DIR="$SCRIPT_DIR"
export ROOT_DIR="$(cd "$APPLIANCE_DIR/../.." && pwd)"
export BUILD_DIR="$ROOT_DIR/build"
export WORK_DIR="$BUILD_DIR/.work"
export VERSION
export BUILD_DATE

export ORION_GIT_REPO_URL="${ORION_GIT_REPO_URL:-https://github.com/jeje57ex3/ERP-ORION.git}"
export ORION_GIT_BRANCH="${ORION_GIT_BRANCH:-main}"
export DISK_SIZE="${DISK_SIZE:-80G}"
export UBUNTU_IMG_URL="${UBUNTU_IMG_URL:-https://cloud-images.ubuntu.com/releases/24.04/release/ubuntu-24.04-server-cloudimg-amd64.img}"
export UBUNTU_SHASUMS_URL="${UBUNTU_SHASUMS_URL:-https://cloud-images.ubuntu.com/releases/24.04/release/SHA256SUMS}"

echo "======================================================"
echo " Orion ERP — Build Appliance Proxmox"
echo " Version     : $VERSION"
echo " Build date  : $BUILD_DATE"
echo " Dépôt Orion : $ORION_GIT_REPO_URL ($ORION_GIT_BRANCH)"
echo " Sortie      : $BUILD_DIR"
echo "======================================================"

echo ""
echo "[CHECK] Prérequis sur cet hôte..."
MISSING=0
for bin in qemu-img curl python3 tar sha256sum sha1sum awk; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    echo "  MANQUANT: $bin"
    MISSING=1
  fi
done
if [ "$MISSING" -eq 1 ]; then
  echo ""
  echo "ERREUR: outils manquants. Sur Ubuntu/Debian :"
  echo "  sudo apt-get install -y qemu-utils curl python3 tar coreutils gawk"
  exit 1
fi
echo "[CHECK] OK"

mkdir -p "$BUILD_DIR" "$WORK_DIR"

echo ""
echo "--- [1/5] Image de base Ubuntu 24.04 ---"
bash "$APPLIANCE_DIR/lib/00-fetch-base-image.sh"

echo ""
echo "--- [2/5] Préparation du disque qcow2 (${DISK_SIZE}) ---"
bash "$APPLIANCE_DIR/lib/10-prepare-qcow2.sh"

echo ""
echo "--- [3/5] Cloud-init (payload de provisioning + user-data) ---"
bash "$APPLIANCE_DIR/lib/20-build-cloud-init-seed.sh"

echo ""
echo "--- [4/5] Export OVA ---"
bash "$APPLIANCE_DIR/lib/30-export-ova.sh"

echo ""
echo "--- [5/5] Manifeste + checksums ---"
bash "$APPLIANCE_DIR/lib/40-generate-manifest.sh"

echo ""
echo "--- Fichiers compagnons (import_proxmox.sh) ---"
cp "$APPLIANCE_DIR/scripts/import_proxmox.sh" "$BUILD_DIR/import_proxmox.sh"
chmod +x "$BUILD_DIR/import_proxmox.sh"

rm -rf "$WORK_DIR"

echo ""
echo "======================================================"
echo " Build terminé avec succès"
echo "======================================================"
echo ""
ls -lh "$BUILD_DIR"
echo ""
echo "Prochaine étape (sur le host Proxmox) :"
echo "  scp -r $BUILD_DIR root@proxmox-host:/root/orion-appliance-$VERSION"
echo "  ssh root@proxmox-host"
echo "  cd /root/orion-appliance-$VERSION && ./import_proxmox.sh --start"
echo ""
echo "Voir deployment/proxmox-appliance/docs/PROXMOX.md pour le détail."
