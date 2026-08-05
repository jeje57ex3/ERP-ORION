#!/usr/bin/env bash
# lib/10 — Prépare OrionERP.qcow2 : conversion qcow2 + redimensionnement du
# disque virtuel à 80G. L'extension du système de fichiers se fait au premier
# boot via cloud-init (growpart + resize_rootfs, voir user-data.yaml.tmpl) —
# on ne touche pas au filesystem ici, seulement à la taille du fichier disque.
# Variables attendues : WORK_DIR, BUILD_DIR, DISK_SIZE

set -euo pipefail

: "${WORK_DIR:?WORK_DIR non défini}"
: "${BUILD_DIR:?BUILD_DIR non défini}"
: "${DISK_SIZE:?DISK_SIZE non défini}"

command -v qemu-img >/dev/null 2>&1 || {
  echo "ERREUR: qemu-img introuvable. Installer le paquet qemu-utils sur cet hôte Linux." >&2
  exit 1
}

SRC_IMG="$WORK_DIR/ubuntu-base.img"
[ -f "$SRC_IMG" ] || { echo "ERREUR: $SRC_IMG introuvable — lancer lib/00 d'abord." >&2; exit 1; }

mkdir -p "$BUILD_DIR"
DEST_IMG="$BUILD_DIR/OrionERP.qcow2"

echo "[10] Conversion vers qcow2 (compression, format propre)..."
qemu-img convert -O qcow2 -c "$SRC_IMG" "$DEST_IMG"

echo "[10] Redimensionnement du disque virtuel à $DISK_SIZE..."
qemu-img resize "$DEST_IMG" "$DISK_SIZE"

echo "[10] Info disque final :"
qemu-img info "$DEST_IMG"
