#!/usr/bin/env bash

set -euo pipefail

VERSION="${1:-dev}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec "$SCRIPT_DIR/deployment/appliance/build_orion_appliance.sh" "$VERSION"
