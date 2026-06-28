#!/usr/bin/env bash

set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."

echo "======================================"
echo " Santé Orion ERP Appliance"
echo "======================================"
echo ""

echo "Services Docker :"
docker compose ps
echo ""

echo "Test backend HTTP..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/ --max-time 10 || echo "0")
if [ "$HTTP_STATUS" = "200" ] || [ "$HTTP_STATUS" = "302" ]; then
  echo "  Backend : OK (HTTP $HTTP_STATUS)"
else
  echo "  Backend : ERREUR (HTTP $HTTP_STATUS)"
fi

echo ""
echo "Endpoint de santé Orion..."
HEALTH=$(curl -s http://localhost/ha/public-health/ --max-time 10 2>/dev/null || echo '{"status":"unreachable"}')
echo "  $HEALTH"

echo ""
echo "Logs backend (20 dernières lignes) :"
echo "--------------------------------------"
docker compose logs --tail=20 orion-backend 2>/dev/null || true
echo ""

echo "Utilisation disque :"
df -h . 2>/dev/null || true
echo ""

echo "Dossiers appliance :"
for d in media static backups logs mysql redis; do
  if [ -d "$d" ]; then
    SIZE=$(du -sh "$d" 2>/dev/null | cut -f1)
    echo "  $d/ : $SIZE"
  fi
done
