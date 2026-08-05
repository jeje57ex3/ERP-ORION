# Installation — Build de l'appliance

## Prérequis (hôte de build)

Le build **doit** s'exécuter sur un hôte **Linux** — pas sur ce poste Windows
(pas de `qemu-img` disponible ici). Le plus simple : lancer le build
directement sur le serveur Proxmox via SSH.

Paquets requis :

```bash
sudo apt-get update
sudo apt-get install -y qemu-utils curl python3 git tar coreutils gawk
```

Espace disque : prévoir ~6-8 Go libres dans `build/` (image de base + qcow2 +
ova simultanément pendant le build).

Accès réseau sortant requis (téléchargement de l'image cloud Ubuntu officielle
et vérification de sa somme SHA256 officielle).

## Build

```bash
git clone https://github.com/jeje57ex3/ERP-ORION.git
cd ERP-ORION
./build_proxmox_appliance.sh [VERSION]
```

`VERSION` est optionnelle (date du jour par défaut, ex: `2026.08.05`).

Variables d'environnement optionnelles (voir `build.sh` pour le détail) :

| Variable | Rôle | Défaut |
|---|---|---|
| `ORION_GIT_REPO_URL` | Dépôt cloné par la VM au premier boot | `https://github.com/jeje57ex3/ERP-ORION.git` |
| `ORION_GIT_BRANCH` | Branche clonée | `main` |
| `UBUNTU_IMG_URL` | Image cloud Ubuntu source | image officielle 24.04 |
| `DISK_SIZE` | Taille du disque virtuel | `80G` |

Exemple pour un fork/déploiement client dédié :

```bash
ORION_GIT_REPO_URL=https://github.com/monclient/ERP-ORION.git \
ORION_GIT_BRANCH=production \
./build_proxmox_appliance.sh 2026.08.05
```

## Étapes du build (`deployment/proxmox-appliance/build.sh`)

1. `lib/00-fetch-base-image.sh` — télécharge et vérifie (SHA256) l'image
   cloud Ubuntu 24.04 officielle.
2. `lib/10-prepare-qcow2.sh` — convertit/redimensionne le disque à la taille
   cible (extension réelle du filesystem au premier boot via cloud-init).
3. `lib/20-build-cloud-init-seed.sh` — empaquette `provisioning/`, `systemd/`,
   `nginx/`, `scripts/`, `docker/` en un payload base64 embarqué dans le
   user-data cloud-init.
4. `lib/30-export-ova.sh` — génère l'export OVA (OVF + VMDK streamOptimized +
   manifest SHA1).
5. `lib/40-generate-manifest.sh` — écrit `OrionERP.manifest` (JSON) et
   `checksum.sha256`.

Chaque étape est idempotente : relancer `build.sh` réutilise l'image de base
déjà téléchargée et vérifiée.

## Vérification post-build

```bash
cd build
sha256sum -c checksum.sha256
python3 -m json.tool OrionERP.manifest
qemu-img info OrionERP.qcow2
```

Étape suivante : [PROXMOX.md](PROXMOX.md) pour l'import.
