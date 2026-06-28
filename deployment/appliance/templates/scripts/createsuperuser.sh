#!/usr/bin/env bash

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."

echo "Création du superadmin Orion ERP..."
docker compose exec orion-backend python manage.py createsuperuser
