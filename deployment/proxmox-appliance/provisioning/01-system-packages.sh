#!/usr/bin/env bash
# Orion ERP Appliance — Stage A / 01
# Installe tous les paquets système requis (Docker, Node, Python, Nginx, etc.)
# Idempotent : peut être relancé sans effet de bord.

set -euo pipefail
exec > >(tee -a /var/log/orion-provision.log) 2>&1

echo "=== [01] Paquets système — $(date -u +%FT%TZ) ==="

export DEBIAN_FRONTEND=noninteractive

echo "[01] apt-get update..."
apt-get update -y

echo "[01] Paquets de base..."
apt-get install -y --no-install-recommends \
  ca-certificates curl gnupg lsb-release git \
  build-essential pkg-config default-libmysqlclient-dev \
  python3 python3-venv python3-dev python3-pip \
  nginx certbot python3-certbot-nginx \
  fail2ban ufw \
  qemu-guest-agent \
  jq unzip \
  default-mysql-client

echo "[01] QEMU Guest Agent..."
systemctl enable --now qemu-guest-agent

# ─── Docker Engine + Compose plugin (dépôt officiel Docker) ────────────────────
if ! command -v docker >/dev/null 2>&1; then
  echo "[01] Installation Docker Engine..."
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  UBUNTU_CODENAME="$(. /etc/os-release && echo "$VERSION_CODENAME")"
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $UBUNTU_CODENAME stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y --no-install-recommends \
    docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
  systemctl enable --now docker
else
  echo "[01] Docker déjà installé — ignoré."
fi

usermod -aG docker orion || true

# ─── Node.js 20 LTS (dépôt NodeSource) ──────────────────────────────────────────
if ! command -v node >/dev/null 2>&1; then
  echo "[01] Installation Node.js 20..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y --no-install-recommends nodejs
else
  echo "[01] Node.js déjà installé — ignoré ($(node -v))."
fi

npm install -g serve --silent

# ─── Cloudflared (paquet .deb officiel) ────────────────────────────────────────
if ! command -v cloudflared >/dev/null 2>&1; then
  echo "[01] Installation cloudflared..."
  ARCH="$(dpkg --print-architecture)"
  curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${ARCH}.deb" \
    -o /tmp/cloudflared.deb
  dpkg -i /tmp/cloudflared.deb
  rm -f /tmp/cloudflared.deb
else
  echo "[01] cloudflared déjà installé — ignoré."
fi

echo "[01] Terminé."
