#!/usr/bin/env bash
# Orion ERP Appliance — Tableau de bord système (terminal).
# Usage : orion-dashboard.sh          (une fois)
#         watch -n5 orion-dashboard.sh (rafraîchi toutes les 5s)

set -uo pipefail

ORION_HOME="/opt/orion"
ENV_FILE="$ORION_HOME/backend/.env"
[ -f "$ENV_FILE" ] && { set -a; . "$ENV_FILE"; set +a; }

c_bold="\e[1m"; c_reset="\e[0m"; c_green="\e[32m"; c_red="\e[31m"; c_yellow="\e[33m"

status_dot() {
  if systemctl is-active --quiet "$1"; then echo -e "${c_green}●${c_reset}"; else echo -e "${c_red}●${c_reset}"; fi
}

echo -e "${c_bold}============================================================${c_reset}"
echo -e "${c_bold} Orion ERP Appliance — Tableau de bord — $(date '+%Y-%m-%d %H:%M:%S')${c_reset}"
echo -e "${c_bold}============================================================${c_reset}"

echo ""
echo -e "${c_bold}CPU / RAM / Disque${c_reset}"
echo "  CPU   : $(uptime | grep -oP 'load average:\s*\K.*') (load avg 1/5/15m)"
free -h | awk 'NR==2{printf "  RAM   : %s utilisés / %s total (%s libres)\n", $3, $2, $7}'
df -h / | awk 'NR==2{printf "  Disque: %s utilisés / %s total (%s libres, %s)\n", $3, $2, $4, $5}'

if command -v sensors >/dev/null 2>&1; then
  TEMP="$(sensors 2>/dev/null | grep -m1 -oP '\+\K[0-9.]+(?=°C)')"
  echo "  Temp. : ${TEMP:-n/a}°C (best-effort — souvent indisponible en VM)"
else
  echo "  Temp. : n/a (lm-sensors non installé — normal en VM)"
fi

echo ""
echo -e "${c_bold}Services${c_reset}"
for unit in orion-db-stack orion-backend orion-frontend siecle-frontend lunea-frontend nginx cloudflared fail2ban orion-health.timer; do
  printf "  %b %s\n" "$(status_dot "$unit")" "$unit"
done

echo ""
echo -e "${c_bold}Cloudflare${c_reset}"
if systemctl is-active --quiet cloudflared; then
  echo -e "  Tunnel : ${c_green}actif${c_reset}"
else
  echo -e "  Tunnel : ${c_yellow}inactif${c_reset} (aucun token configuré, ou wizard non exécuté)"
fi

echo ""
echo -e "${c_bold}SSL (Let's Encrypt)${c_reset}"
if command -v certbot >/dev/null 2>&1; then
  certbot certificates 2>/dev/null | grep -E "Certificate Name|Expiry Date" | sed 's/^/  /' \
    || echo "  Aucun certificat Certbot trouvé."
else
  echo "  certbot non installé."
fi

echo ""
echo -e "${c_bold}Sauvegardes${c_reset}"
if [ -d "$ORION_HOME/backups" ]; then
  LAST="$(ls -t "$ORION_HOME/backups"/orion_backup_*.tar.gz 2>/dev/null | head -1)"
  COUNT="$(ls "$ORION_HOME/backups"/orion_backup_*.tar.gz 2>/dev/null | wc -l)"
  if [ -n "$LAST" ]; then
    echo "  Dernière : $(basename "$LAST") ($(du -sh "$LAST" | cut -f1), $(date -r "$LAST" '+%Y-%m-%d %H:%M'))"
  else
    echo "  Aucune sauvegarde trouvée."
  fi
  echo "  Total    : $COUNT sauvegarde(s), $(du -sh "$ORION_HOME/backups" 2>/dev/null | cut -f1)"
fi

echo ""
echo -e "${c_bold}Logs récents (orion-health)${c_reset}"
tail -n 5 "$ORION_HOME/logs/orion_health.log" 2>/dev/null | sed 's/^/  /' || echo "  (pas encore de journal)"

echo ""
echo -e "${c_bold}============================================================${c_reset}"
