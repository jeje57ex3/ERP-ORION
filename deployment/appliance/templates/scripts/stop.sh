#!/usr/bin/env bash

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."

echo "Arrêt Orion ERP..."
docker compose down

echo "Services arrêtés."
