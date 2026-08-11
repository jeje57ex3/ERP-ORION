# Import Proxmox

## Tout-en-un (recommandé) — build + import + démarrage

`deploy.sh` s'exécute **directement sur le host Proxmox** (Shell du nœud dans
l'UI, ou SSH `root@proxmox`) : Proxmox fournit déjà `qemu-img`/`qm`/`pvesh`/
`pvesm` nativement, donc build et import se font en une seule commande, sans
aller-retour SCP :

```bash
git clone https://github.com/jeje57ex3/ERP-ORION.git
cd ERP-ORION
./deploy_proxmox_vm.sh
```

Lancé sans option depuis un terminal, `deploy_proxmox_vm.sh` ouvre un
**assistant interactif** qui pose les questions dans l'ordre :

1. Version du build (reconstruire ou réutiliser un build existant).
2. Nom de la VM et VMID (un ID libre est suggéré via `pvesh get /cluster/nextid`).
3. **Disque d'installation** : liste les stockages Proxmox disponibles
   (`pvesm status --content images`) sous forme de menu numéroté à choisir,
   puis la **taille du disque virtuel** (80G par défaut, personnalisable —
   120G, 500G, 1T...).
4. Stockage pour le cloud-init personnalisé (`snippets`).
5. **Réseau** : bridge à choisir dans un menu (détection des `vmbr*`
   existants), puis DHCP ou IP statique (adresse/CIDR, passerelle, DNS).
6. RAM / vCPU.
7. Clé SSH à injecter (détection automatique des `~/.ssh/*.pub` disponibles,
   ou saisie manuelle d'un chemin).
8. Comportement final : démarrer la VM, la laisser arrêtée, ou la convertir
   en template Proxmox.
9. Récapitulatif complet avant toute action — rien n'est créé sans confirmation.

### Mode non-interactif (scripts, CI, déploiements répétés)

Passer au moins une option désactive l'assistant et utilise les valeurs
fournies (auto-détection pour le reste) :

```bash
./deploy_proxmox_vm.sh 2026.08.05 \
  --name OrionERP-Client1 \
  --storage local-lvm \
  --disk-size 120G \
  --bridge vmbr0 \
  --ip 192.168.1.50/24 --gateway 192.168.1.1 \
  --sshkey ~/.ssh/id_ed25519.pub
```

Toutes les options : `--vmid`, `--name`, `--storage`, `--disk-size`,
`--snippets-storage`, `--bridge`, `--ip`/`--gateway`/`--dns` (IP statique —
omis = DHCP), `--memory`, `--cores`, `--sshkey`,
`--login-domain`/`--orion-domain`/`--siecle-domain`/`--lunea-domain`
(domaines publics, omis = accès par IP), `--cf-token` (Cloudflare Tunnel),
`--as-template`, `--rebuild`, `--skip-build`. Forcer l'assistant malgré des
options fournies : `-i` / `--interactive`. Voir `./deploy_proxmox_vm.sh --help`
pour le détail.

Lister les stockages/bridges disponibles sans lancer l'assistant :

```bash
cd build && ./import_proxmox.sh --list-storage
cd build && ./import_proxmox.sh --list-bridges
```

Relancer pour une **nouvelle VM à partir du même build** (utile pour déployer
plusieurs clients) : `./deploy_proxmox_vm.sh --skip-build --name OrionERP-Client2`.

## Étape par étape (build ailleurs que sur le host Proxmox)

Si le build a lieu sur un autre hôte Linux (CI, VM de build dédiée), copier
`build/` sur le host Proxmox puis lancer l'import séparément :

```bash
cd build/                     # ou le dossier scp'é sur le host Proxmox
./import_proxmox.sh --start
```

Options utiles (voir `import_proxmox.sh --help`) :

```bash
./import_proxmox.sh \
  --vmid 9000 \
  --name OrionERP \
  --storage local-lvm \
  --disk-size 120G \
  --snippets-storage local \
  --bridge vmbr0 \
  --ip 192.168.1.50/24 --gateway 192.168.1.1 --dns 192.168.1.1 \
  --memory 8192 \
  --cores 4 \
  --sshkey ~/.ssh/id_ed25519.pub \
  --login-domain login.exemple.fr --orion-domain orion.exemple.fr \
  --siecle-domain siecle.exemple.fr --lunea-domain lunea.exemple.fr \
  --cf-token "$CF_TOKEN" \
  --start
```

Lister les stockages/bridges disponibles sur ce host avant de choisir :
`./import_proxmox.sh --list-storage` / `--list-bridges`.

Ce que fait le script :

1. `qm create` — VM q35, BIOS OVMF (UEFI), VirtIO SCSI + réseau.
2. `qm set --efidisk0` — disque EFI, sur le stockage choisi (`--storage`).
3. `qm importdisk` — importe `OrionERP.qcow2` dans le stockage cible.
4. `qm set --scsi0 ...,discard=on,ssd=1,iothread=1` — attache le disque
   (TRIM/discard actif).
5. `qm set --ide2 storage:cloudinit` + `--cicustom` — pointe le cloud-init
   Proxmox vers `OrionERP.cloudinit-userdata.yaml` /
   `OrionERP.cloudinit-network-config.yaml` (copiés dans le dossier
   `snippets` du stockage choisi — ce stockage doit autoriser le contenu
   **Snippets** dans Datacenter → Stockage → *storage* → Contenu).
6. `qm set --ipconfig0` — IP statique (`--ip`/`--gateway`/`--dns`) ou DHCP
   par défaut.
7. `qm resize scsi0 <taille>` — applique la taille de disque choisie
   (`--disk-size`, 80G par défaut).
8. Démarre la VM (`--start`) ou la convertit en template (`--as-template`).

## Stockage "snippets"

Si le stockage choisi (`--snippets-storage`, `local` par défaut) n'autorise
pas le contenu **Snippets**, l'activer avant l'import :

```
Proxmox UI → Datacenter → Stockage → local → Modifier → Contenu → cocher "Snippets"
```

Ou en CLI : `pvesm set local --content ...,snippets`

## Premier démarrage

Le provisioning (Stage A) est **entièrement automatique, sans aucune étape
interactive sur la console** — domaines et token Cloudflare (si fournis à
`deploy.sh`, voir plus haut) sont déjà connus au démarrage, nginx et les
services applicatifs (backend, frontends SIÈCLE/LUNEA si un domaine Login a
été fourni, supervision `orion-health.timer`) démarrent seuls, ~3-8 min après
le premier boot selon la taille des paquets à installer.

Une fois le provisioning terminé, **ouvrir un navigateur** sur le domaine
Login (ou directement sur l'IP de la VM, même sans DNS configuré — le vhost
Login répond en `default_server`) : la page affiche automatiquement
l'assistant de premier accès (`/setup/`) tant qu'aucun compte n'existe —
nom de l'entreprise, email/mot de passe administrateur, fuseau horaire.
Cette étape ne se déroule qu'une seule fois ; une fois complétée, `/setup/`
redirige vers la page de connexion normale.

## Activer Cloudflare Tunnel après coup

Si aucun token n'a été fourni à `deploy.sh` au moment du déploiement :

```bash
ssh orion@<ip-vm>
sudo cloudflared service install <TOKEN>
```

Puis déclarer les 4 hostnames publics dans le dashboard Cloudflare Zero Trust
(Tunnels → *tunnel* → Public Hostname), chacun pointant vers
`http://localhost:<port>` (9000/5172/5173/5174 — voir tableau dans README.md).

**Alternative avancée (tunnel géré localement, sans dashboard)** : un modèle
d'ingress prêt à l'emploi existe dans `/etc/cloudflared/config.yml.tmpl`
(installé par `provisioning/05-cloudflared-config.sh`). Utile si vous préférez
un tunnel nommé classique (`cloudflared tunnel create` + `tunnel route dns` +
fichier de credentials) plutôt qu'un tunnel à token géré depuis le dashboard.
Remplacer les `__*_DOMAIN__` par les domaines réels et l'utiliser comme
`/etc/cloudflared/config.yml`.

## IP statique (au lieu de DHCP)

Après import, avant le premier démarrage :

```bash
qm set <VMID> --ipconfig0 ip=192.168.1.50/24,gw=192.168.1.1
```

## Réseau / pare-feu

Ports UFW ouverts nativement dans la VM : `22, 80, 443, 5172, 5173, 5174, 9000`.
Si un tunnel Cloudflare est utilisé exclusivement, seul le port `22` (accès
SSH d'administration) doit rester exposé côté réseau physique/Proxmox — les
autres peuvent être filtrés en amont sans casser le tunnel (`cloudflared`
initie une connexion sortante, aucun port entrant public n'est requis).

## Dépannage

```bash
# Statut général
sudo /opt/orion/scripts/orion-dashboard.sh

# Vérification de santé manuelle (sans réparation)
sudo python3 /opt/orion/scripts/orion_health_check.py --dry-run --json

# Logs de provisioning Stage A (installation, .env, migrations, nginx...)
sudo tail -f /var/log/orion-provision.log

# Statut du backend Django (créé le compte admin via /setup/ dans le navigateur)
sudo systemctl status orion-backend.service
```
