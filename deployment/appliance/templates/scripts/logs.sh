#!/usr/bin/env bash

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."

SERVICE="${1:-}"

if [ -z "$SERVICE" ]; then
  echo "Usage : ./scripts/logs.sh [service]"
  echo ""
  echo "Services disponibles :"
  echo "  orion-backend"
  echo "  orion-celery"
  echo "  orion-celery-beat"
  echo "  orion-nginx"
  echo "  orion-db"
  echo "  orion-redis"
  echo ""
  echo "Sans argument — affiche tous les logs :"
  docker compose logs -f --tail=100
else
  docker compose logs -f --tail=100 "$SERVICE"
fi
