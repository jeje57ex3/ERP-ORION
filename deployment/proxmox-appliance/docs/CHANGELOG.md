# Changelog — Appliance Proxmox Orion ERP

## 2026.10.09

- Migration des données vers l'appliance : `scripts/export_orion_data.ps1`
  (poste Windows → archive horodatée base + médias + manifeste, empreinte
  SHA-256) et `scripts/install_orion_data.sh` (VM → vérification d'empreinte,
  sauvegarde de sécurité, restauration, fusion des médias, `migrate` +
  `collectstatic`, redémarrage des services). L'appliance démarrait jusqu'ici
  avec une base vide, sans chemin outillé pour y porter des données
  existantes. Documenté dans [DATA-MIGRATION.md](DATA-MIGRATION.md).
- Les builds mobiles (`.apk`/`.aab`, ~1 Go d'artefacts reconstructibles) sont
  exclus de l'export par défaut (`-IncludeMobileBuilds` pour les inclure).

## 2026.08.06

- `deploy_proxmox_vm.sh` : ajout d'un assistant interactif (choix du disque/
  stockage d'installation via menu détecté par `pvesm`, taille du disque
  virtuel personnalisable, bridge réseau, IP statique ou DHCP, clé SSH avec
  détection des `~/.ssh/*.pub`, choix démarrer/laisser arrêtée/template,
  récapitulatif avant confirmation). Actif par défaut sans option sur un
  terminal interactif ; mode non-interactif (flags) inchangé pour
  l'automatisation/CI.
- `import_proxmox.sh` : nouvelles options `--disk-size`, `--ip`/`--gateway`/
  `--dns` (IP statique), `--list-storage`, `--list-bridges`.

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
