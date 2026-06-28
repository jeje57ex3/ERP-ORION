#!/usr/bin/env bash

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."

echo "Démarrage Orion ERP..."
docker compose up -d

echo ""
echo "Statut des services :"
docker compose ps

echo ""
echo "Orion ERP disponible sur http://localhost"
