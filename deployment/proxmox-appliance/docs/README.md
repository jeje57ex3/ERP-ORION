# Orion ERP — Appliance Proxmox

Image VM Proxmox prête à l'emploi (`.qcow2` / `.ova`) pour déployer Orion ERP
en une seule VM : Django (login + vitrine), SIÈCLE, LUNEA, MySQL, Redis,
Nginx, Cloudflare Tunnel, sauvegardes automatiques et supervision.

Distinct du packager `deployment/appliance/` (archive Docker Compose à
déployer sur un serveur déjà existant) : celui-ci produit une **VM complète**
à importer directement dans Proxmox VE.

## Vue d'ensemble

| Domaine | Port local | Service | Rôle |
|---|---|---|---|
| `login.<domaine>` | 9000 | `orion-backend` | Django ERP / admin |
| `orion.<domaine>` | 5172 | `orion-frontend` | Django Vitrine (même code) |
| `siecle.<domaine>` | 5173 | `siecle-frontend` | SPA React SIÈCLE |
| `lunea.<domaine>` | 5174 | `lunea-frontend` | SPA React LUNEA |

MySQL 8.0 et Redis 7 tournent en conteneurs Docker (`orion-db-stack.service`) ;
les 4 services applicatifs tournent nativement (systemd) pour rester
individuellement pilotables — topologie identique à la production réelle
(voir `server_tools/orion_cloudflare_guard.py` à la racine du projet).

## Démarrage rapide

```bash
# 1. Sur un hôte Linux avec qemu-img (ex: le host Proxmox lui-même)
git clone https://github.com/jeje57ex3/ERP-ORION.git
cd ERP-ORION
./build_proxmox_appliance.sh 2026.08.05

# 2. Copier build/ sur le host Proxmox si le build a eu lieu ailleurs
scp -r build/ root@proxmox:/root/orion-appliance-2026.08.05

# 3. Importer et démarrer
ssh root@proxmox
cd /root/orion-appliance-2026.08.05
./import_proxmox.sh --start

# 4. Ouvrir la console noVNC de la VM dans Proxmox et suivre l'assistant
```

Voir [PROXMOX.md](PROXMOX.md) pour le détail complet, [INSTALL.md](INSTALL.md)
pour les prérequis de build, [BACKUP.md](BACKUP.md) et [UPDATE.md](UPDATE.md)
pour l'exploitation.

## Contenu de `build/`

```
build/
  OrionERP.qcow2                        # disque de la VM
  OrionERP.ova                          # export portable (VMware, etc.)
  OrionERP.manifest                     # JSON : versions, modules, ports
  checksum.sha256                       # SHA256 du qcow2 et de l'ova
  OrionERP.cloudinit-userdata.yaml      # provisioning automatique (Stage A)
  OrionERP.cloudinit-network-config.yaml
  import_proxmox.sh                     # à exécuter sur le host Proxmox
```

## Premier démarrage

Deux étapes, automatiques puis interactives :

1. **cloud-init (Stage A)** — install des paquets, code source, services —
   entièrement automatique, ~2-5 min.
2. **Assistant console (Stage B)** — sur la console de la VM (tty1, visible
   via noVNC dans Proxmox) : entreprise, domaines, admin, fuseau horaire,
   token Cloudflare (optionnel). Écrit `.env`, migre la base, construit les
   frontends, démarre tous les services.

Aucune configuration manuelle au-delà de ces questions.
