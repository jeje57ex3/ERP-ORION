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

Ce script :
1. Construit l'image (`build.sh`) si `build/OrionERP.qcow2` n'existe pas déjà
   (`--rebuild` pour forcer, `--skip-build` pour réutiliser un build existant).
2. Détecte automatiquement : le prochain VMID libre (`pvesh get /cluster/nextid`),
   le premier stockage supportant le contenu `images`, celui supportant
   `snippets`, et le premier bridge `vmbr*` — tout est surchargeable
   (`--vmid`, `--storage`, `--snippets-storage`, `--bridge`, `--memory`,
   `--cores`, `--sshkey`, `--as-template`).
3. Importe et démarre la VM (`import_proxmox.sh` en interne).

```bash
# Exemple avec paramètres explicites
./deploy_proxmox_vm.sh 2026.08.05 \
  --name OrionERP-Client1 \
  --storage local-lvm \
  --bridge vmbr0 \
  --sshkey ~/.ssh/id_ed25519.pub
```

Relancer plus tard pour une **nouvelle VM à partir du même build** (utile pour
déployer plusieurs clients) : `./deploy_proxmox_vm.sh --skip-build --name OrionERP-Client2`.

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
  --snippets-storage local \
  --bridge vmbr0 \
  --memory 8192 \
  --cores 4 \
  --sshkey ~/.ssh/id_ed25519.pub \
  --start
```

Ce que fait le script :

1. `qm create` — VM q35, BIOS OVMF (UEFI), VirtIO SCSI + réseau.
2. `qm set --efidisk0` — disque EFI.
3. `qm importdisk` — importe `OrionERP.qcow2` dans le stockage cible.
4. `qm set --scsi0 ...,discard=on,ssd=1,iothread=1` — attache le disque
   (TRIM/discard actif).
5. `qm set --ide2 storage:cloudinit` + `--cicustom` — pointe le cloud-init
   Proxmox vers `OrionERP.cloudinit-userdata.yaml` /
   `OrionERP.cloudinit-network-config.yaml` (copiés dans le dossier
   `snippets` du stockage choisi — ce stockage doit autoriser le contenu
   **Snippets** dans Datacenter → Stockage → *storage* → Contenu).
6. `qm resize scsi0 80G` — garantit la taille cible.
7. Démarre la VM (`--start`) ou la convertit en template (`--as-template`).

## Stockage "snippets"

Si le stockage choisi (`--snippets-storage`, `local` par défaut) n'autorise
pas le contenu **Snippets**, l'activer avant l'import :

```
Proxmox UI → Datacenter → Stockage → local → Modifier → Contenu → cocher "Snippets"
```

Ou en CLI : `pvesm set local --content ...,snippets`

## Premier démarrage

1. Ouvrir la **console noVNC** de la VM dans l'interface Proxmox.
2. Attendre la fin du provisioning automatique (Stage A, ~2-5 min — messages
   cloud-init défilent, terminé par `Orion ERP Appliance prête`).
3. L'assistant interactif (Stage B) apparaît automatiquement sur la console :
   Entreprise, Nom ERP, domaines (Login/Orion/SIÈCLE/LUNEA), email/mot de
   passe administrateur, fuseau horaire, token Cloudflare Tunnel (optionnel).
4. À la fin, les 4 services applicatifs et la supervision (`orion-health.timer`)
   démarrent automatiquement.

Si le boot est interrompu avant la fin du wizard, il se relance
automatiquement au prochain démarrage (protégé par `/opt/orion/.awaiting-setup`).

## Activer Cloudflare Tunnel après coup

Si aucun token n'a été saisi au premier démarrage :

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

# Rejouer le wizard manuellement
sudo touch /opt/orion/.awaiting-setup
sudo systemctl restart orion-first-boot.service

# Logs de provisioning Stage A
sudo tail -f /var/log/orion-provision.log

# Logs du wizard Stage B
sudo tail -f /opt/orion/logs/first-boot-wizard.log
```
