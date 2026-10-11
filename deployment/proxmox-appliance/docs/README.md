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
| `ns.<domaine>` | 80 (Nginx) | `nginx` | SPA React NÉOSTRUCTURA |

MySQL 8.0 et Redis 7 tournent en conteneurs Docker (`orion-db-stack.service`) ;
les 4 services applicatifs tournent nativement (systemd) pour rester
individuellement pilotables — topologie identique à la production réelle
(voir `server_tools/orion_cloudflare_guard.py` à la racine du projet).

NÉOSTRUCTURA fait exception : il n'a pas de service dédié, Nginx sert son
build statique et proxifie `/api` et `/media` vers Django. Son client API
appelle en effet des chemins relatifs, le SPA et l'API doivent donc partager
la même origine — ce qu'un serveur de fichiers statiques ne sait pas faire.
Conséquence : dans le tunnel Cloudflare, ce domaine vise Nginx (port 80) et
non un port applicatif direct.

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
pour l'exploitation. L'appliance démarre avec une base vide :
[DATA-MIGRATION.md](DATA-MIGRATION.md) explique comment y transférer les
données réelles d'un poste existant. [DISQUES.md](DISQUES.md) détaille où
vont les données, quels emplacements sont purgés et comment agrandir le
disque après coup.

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

1. **cloud-init** — paquets, code source, `.env`, migrations, build des
   frontends, nginx, services : **entièrement automatique**, aucune étape
   interactive sur la console, ~3-8 min.
2. **Assistant de premier accès** — dans un **navigateur**, sur le domaine
   Login ou directement sur l'IP de la VM : nom de l'entreprise, email et
   mot de passe administrateur, fuseau horaire. `SetupRequiredMiddleware`
   affiche `/setup/` tant qu'aucune entreprise n'existe en base, puis la
   route redirige vers la connexion normale.

Il n'y a **pas** d'assistant sur la console série de la VM : le formulaire web
`/setup/` l'a remplacé (voir `apps/core/setup_views.py`). Les domaines et le
token Cloudflare se fournissent à `deploy.sh` au moment du déploiement, pas
au premier démarrage.
