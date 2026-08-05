# Changelog — Appliance Proxmox Orion ERP

## 2026.08.05

- Première version : pipeline de build complet (Ubuntu 24.04 cloud image +
  cloud-init NoCloud, sans Packer) produisant `OrionERP.qcow2`, `OrionERP.ova`,
  `OrionERP.manifest`, `checksum.sha256`.
- Topologie native systemd reproduisant la production réelle : 4 services
  applicatifs (`orion-backend` 9000, `orion-frontend` 5172, `siecle-frontend`
  5173, `lunea-frontend` 5174) + MySQL/Redis en Docker (`orion-db-stack`).
- Premier démarrage en deux étapes : provisioning automatique (cloud-init)
  puis assistant interactif sur la console (tty1).
- Supervision `orion-health.timer` (60s), sauvegardes quotidiennes (2h),
  scripts `update_orion.sh` / `cleanup.sh`, tableau de bord terminal.
- Pare-feu UFW + fail2ban, Cloudflare Tunnel (activation par token au premier
  démarrage), Nginx + Certbot pour l'accès direct.
- `import_proxmox.sh` : automatise `qm create/importdisk/set/resize` et le
  cloud-init personnalisé Proxmox (`--cicustom`).
