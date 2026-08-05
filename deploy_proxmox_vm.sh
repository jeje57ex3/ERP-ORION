#!/usr/bin/env bash
# À exécuter SUR le host Proxmox (build + import + démarrage en une commande).
# Voir deployment/proxmox-appliance/deploy.sh --help pour les options.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec "$SCRIPT_DIR/deployment/proxmox-appliance/deploy.sh" "$@"
