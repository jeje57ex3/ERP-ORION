#!/usr/bin/env bash

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."

echo "Redémarrage Orion ERP..."
docker compose restart

echo ""
echo "Statut :"
docker compose ps
