#!/usr/bin/env bash
# Orion ERP Appliance — Stage A / 06
# Pare-feu (UFW) + protection anti-bruteforce (fail2ban).

set -euo pipefail
exec >> /var/log/orion-provision.log 2>&1

echo "=== [06] UFW / fail2ban — $(date -u +%FT%TZ) ==="

ufw --force reset >/dev/null
ufw default deny incoming
ufw default allow outgoing

for PORT in 22 80 443 5172 5173 5174 9000; do
  ufw allow "${PORT}/tcp"
done

ufw --force enable

cat > /etc/fail2ban/jail.local <<'EOF'
[DEFAULT]
bantime  = 1h
findtime = 10m
maxretry = 5

[sshd]
enabled = true

[nginx-http-auth]
enabled = true

[nginx-botsearch]
enabled = true
EOF

systemctl enable --now fail2ban
systemctl restart fail2ban

echo "[06] Terminé."
