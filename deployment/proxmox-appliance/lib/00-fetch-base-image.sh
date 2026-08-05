#!/usr/bin/env bash
# lib/00 — Télécharge l'image cloud Ubuntu 24.04 officielle et vérifie son SHA256.
# Variables attendues (exportées par build.sh) : WORK_DIR, UBUNTU_IMG_URL, UBUNTU_SHASUMS_URL

set -euo pipefail

: "${WORK_DIR:?WORK_DIR non défini}"
: "${UBUNTU_IMG_URL:?UBUNTU_IMG_URL non défini}"
: "${UBUNTU_SHASUMS_URL:?UBUNTU_SHASUMS_URL non défini}"

mkdir -p "$WORK_DIR"
IMG_FILE="$WORK_DIR/ubuntu-base.img"
IMG_NAME="$(basename "$UBUNTU_IMG_URL")"

echo "[00] Image de base : $UBUNTU_IMG_URL"

if [ -f "$IMG_FILE" ] && [ -f "$IMG_FILE.sha256_ok" ]; then
  echo "[00] Déjà téléchargée et vérifiée — réutilisation ($IMG_FILE)."
  exit 0
fi

echo "[00] Téléchargement (peut prendre plusieurs minutes)..."
curl -fL --progress-bar "$UBUNTU_IMG_URL" -o "$IMG_FILE.part"
mv "$IMG_FILE.part" "$IMG_FILE"

echo "[00] Vérification SHA256SUMS officiel..."
curl -fsSL "$UBUNTU_SHASUMS_URL" -o "$WORK_DIR/SHA256SUMS"

EXPECTED="$(awk -v f="$IMG_NAME" '{name=$2; sub(/^\*/, "", name); if (name == f) { print $1; exit }}' "$WORK_DIR/SHA256SUMS")"
if [ -z "$EXPECTED" ]; then
  echo "ERREUR: entrée SHA256 introuvable pour $IMG_NAME dans SHA256SUMS." >&2
  exit 1
fi

ACTUAL="$(sha256sum "$IMG_FILE" | awk '{print $1}')"
if [ "$EXPECTED" != "$ACTUAL" ]; then
  echo "ERREUR: SHA256 invalide pour $IMG_FILE" >&2
  echo "  attendu : $EXPECTED" >&2
  echo "  obtenu  : $ACTUAL" >&2
  rm -f "$IMG_FILE"
  exit 1
fi

touch "$IMG_FILE.sha256_ok"
echo "[00] Intégrité vérifiée (SHA256 OK)."
