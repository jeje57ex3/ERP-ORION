#!/usr/bin/env bash

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."

echo "Migrations Orion ERP..."
docker compose exec orion-backend python manage.py migrate --noinput

echo "Collectstatic..."
docker compose exec orion-backend python manage.py collectstatic --noinput

echo "Terminé."
