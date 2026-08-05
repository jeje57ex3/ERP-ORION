#!/usr/bin/env bash
# lib/40 — Génère build/OrionERP.manifest (JSON) et build/checksum.sha256.
# Variables attendues : BUILD_DIR, VERSION, BUILD_DATE, ORION_GIT_REPO_URL,
#                        ORION_GIT_BRANCH, ROOT_DIR

set -euo pipefail

: "${BUILD_DIR:?BUILD_DIR non défini}"
: "${VERSION:?VERSION non défini}"
: "${BUILD_DATE:?BUILD_DATE non défini}"
: "${ORION_GIT_REPO_URL:?ORION_GIT_REPO_URL non défini}"
: "${ORION_GIT_BRANCH:?ORION_GIT_BRANCH non défini}"
: "${ROOT_DIR:?ROOT_DIR non défini}"

GIT_COMMIT="$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"

echo "[40] Génération du manifeste..."
python3 - "$BUILD_DIR/OrionERP.manifest" <<PYEOF
import json, sys

out = {
    "name": "Orion ERP Appliance",
    "version": "$VERSION",
    "build_date": "$BUILD_DATE",
    "format": "proxmox-qcow2 + ova",
    "ubuntu_version": "24.04 LTS (Noble Numbat)",
    "python_version": "3.12",
    "node_version": "20 LTS",
    "database": "MySQL 8.0 (Docker)",
    "cache_broker": "Redis 7 (Docker)",
    "orion_git_repo": "$ORION_GIT_REPO_URL",
    "orion_git_branch": "$ORION_GIT_BRANCH",
    "orion_git_commit": "$GIT_COMMIT",
    "vm": {
        "cpu": 4,
        "memory_mb": 8192,
        "disk_gb": 80,
        "disk_format": "qcow2",
        "firmware": "OVMF (UEFI)",
        "machine": "q35",
        "nic": "virtio",
        "disk_bus": "virtio-scsi",
        "guest_agent": True,
    },
    "services": [
        "orion-db-stack", "orion-backend", "orion-frontend",
        "siecle-frontend", "lunea-frontend", "orion-health",
        "nginx", "cloudflared", "fail2ban",
    ],
    "ports": {
        "login (orion-backend)": 9000,
        "orion (orion-frontend)": 5172,
        "siecle (siecle-frontend)": 5173,
        "lunea (lunea-frontend)": 5174,
        "http": 80,
        "https": 443,
        "ssh": 22,
    },
    "modules_installed": [
        "docker-ce", "docker-compose-plugin", "git", "python3.12", "nodejs20",
        "nginx", "certbot", "cloudflared", "fail2ban", "ufw", "qemu-guest-agent",
    ],
    "first_boot": "assistant interactif sur la console (tty1) — voir PROXMOX.md",
    "files": {
        "disk": "OrionERP.qcow2",
        "ova": "OrionERP.ova",
        "cloudinit_userdata": "OrionERP.cloudinit-userdata.yaml",
        "cloudinit_network_config": "OrionERP.cloudinit-network-config.yaml",
    },
}

with open(sys.argv[1], "w", encoding="utf-8") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)
    f.write("\n")
PYEOF

echo "[40] Calcul des checksums SHA256..."
cd "$BUILD_DIR"
: > checksum.sha256
for f in OrionERP.qcow2 OrionERP.ova; do
  [ -f "$f" ] && sha256sum "$f" >> checksum.sha256
done

echo "[40] Terminé :"
cat checksum.sha256
