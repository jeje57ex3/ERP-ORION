#!/usr/bin/env bash
# lib/20 — Construit le payload de provisioning (tar+base64) et rend le
# user-data cloud-init final. Ces fichiers sont des COMPAGNONS du qcow2 (pas
# embarqués dedans) : Proxmox les attache via --cicustom (voir import_proxmox.sh).
# Variables attendues : APPLIANCE_DIR, WORK_DIR, BUILD_DIR, VERSION, BUILD_DATE,
#                        ORION_GIT_REPO_URL, ORION_GIT_BRANCH

set -euo pipefail

: "${APPLIANCE_DIR:?APPLIANCE_DIR non défini}"
: "${WORK_DIR:?WORK_DIR non défini}"
: "${BUILD_DIR:?BUILD_DIR non défini}"
: "${VERSION:?VERSION non défini}"
: "${BUILD_DATE:?BUILD_DATE non défini}"
: "${ORION_GIT_REPO_URL:?ORION_GIT_REPO_URL non défini}"
: "${ORION_GIT_BRANCH:?ORION_GIT_BRANCH non défini}"

mkdir -p "$WORK_DIR" "$BUILD_DIR"

echo "[20] Empaquetage du payload de provisioning..."
tar czf "$WORK_DIR/payload.tar.gz" \
  -C "$APPLIANCE_DIR" \
  provisioning systemd nginx scripts docker

echo "[20] Encodage base64..."
# Encodage replié (largeur par défaut, ~76 col) et NON en une seule ligne
# géante (-w0) : une ligne YAML unique de plusieurs dizaines de Ko s'est
# révélée corrompue/tronquée après passage dans le pipeline cloud-init de
# Proxmox (génération de l'ISO ide2). base64 -d et cloud-init (Python
# base64.b64decode) ignorent tous deux les retours à la ligne au décodage,
# donc replier n'affecte pas la validité — uniquement la robustesse du
# transport en tant que bloc YAML "|".
base64 "$WORK_DIR/payload.tar.gz" > "$WORK_DIR/payload.b64"

PAYLOAD_SIZE_KB=$(( $(stat -c%s "$WORK_DIR/payload.b64" 2>/dev/null || stat -f%z "$WORK_DIR/payload.b64") / 1024 ))
echo "[20] Payload encodé : ${PAYLOAD_SIZE_KB} Ko"

echo "[20] Vérification d'intégrité du payload (détecte un disque plein / une écriture tronquée)..."
if ! base64 -d "$WORK_DIR/payload.b64" | tar tz >/dev/null 2>&1; then
  echo "[20] ERREUR: le payload généré est corrompu (base64/tar invalide)." >&2
  echo "        Cause probable : espace disque insuffisant pendant la génération." >&2
  df -h "$WORK_DIR" >&2 || true
  exit 1
fi

# Version pré-indentée (6 espaces par ligne) pour insertion directe dans le
# bloc YAML "content: |" du template — voir user-data.yaml.tmpl.
awk '{ print "      " $0 }' "$WORK_DIR/payload.b64" > "$WORK_DIR/payload.b64.indented"

echo "[20] Rendu du user-data cloud-init..."
python3 "$APPLIANCE_DIR/lib/_render.py" \
  "$APPLIANCE_DIR/cloud-init/user-data.yaml.tmpl" \
  "$BUILD_DIR/OrionERP.cloudinit-userdata.yaml" \
  "ORION_VERSION=$VERSION" \
  "BUILD_DATE=$BUILD_DATE" \
  "ORION_GIT_REPO_URL=$ORION_GIT_REPO_URL" \
  "ORION_GIT_BRANCH=$ORION_GIT_BRANCH" \
  "PAYLOAD_B64=@$WORK_DIR/payload.b64.indented"

cp "$APPLIANCE_DIR/cloud-init/network-config" "$BUILD_DIR/OrionERP.cloudinit-network-config.yaml"

echo "[20] Fichiers générés :"
echo "  - $BUILD_DIR/OrionERP.cloudinit-userdata.yaml"
echo "  - $BUILD_DIR/OrionERP.cloudinit-network-config.yaml"
