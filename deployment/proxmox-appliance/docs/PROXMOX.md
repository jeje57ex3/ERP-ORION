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
`--login-domain`/`--orion-domain`/`--siecle-domain`/`--lunea-domain`/`--ns-domain`
(domaines publics, omis = accès par IP), `--cf-token` (Cloudflare Tunnel),
`--github-token` (jeton d'accès GitHub, requis si `ORION_GIT_REPO_URL` est un
dépôt privé — sinon le git clone de Stage A échoue ; peut aussi être
configuré/renouvelé après coup depuis l'ERP en Réglages > Mises à jour),
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
  --ns-domain ns.exemple.fr \
  --cf-token "$CF_TOKEN" \
  --github-token "$GITHUB_TOKEN"
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

Le provisioning est orchestré par un seul script,
`provisioning/00-provisionner.sh`, qui enchaîne les étapes dans l'ordre,
**continue** si l'une échoue, et termine par une vérification complète. À la
fin, le message d'accueil de la console (`/etc/motd`) dit ce qui s'est
réellement passé : « appliance prête », ou la liste des étapes en échec. Ne
pas se fier à autre chose — l'ERP peut démarrer et renvoyer 500 sur toutes ses
pages si une étape intermédiaire a manqué.

```bash
# Verdict du provisioning (aussi affiché à la connexion console)
qm guest exec <vmid> -- /bin/cat /etc/motd

# Récapitulatif étape par étape
qm guest exec <vmid> -- /bin/cat /opt/orion/logs/provisioning.txt

# Revérifier à tout moment (après une mise à jour, un changement de domaine...)
qm guest exec <vmid> -- /bin/bash /opt/orion/scripts/orion-verifier.sh
```

`orion-verifier.sh` contrôle ce qu'un navigateur constate — les pages
répondent-elles ? — et non ce que les scripts croient avoir fait : services,
ports, schéma de base, présence de `staticfiles.json` (sans lui, toutes les
pages renvoient 500), réponses HTTP, sonde de haute disponibilité sous le vrai
nom d'hôte, modèle IA téléchargé, et dépôt git lisible. Il distingue les
défauts bloquants des composants simplement non installés, et sort en erreur
seulement dans le premier cas.

Une fois le provisioning terminé, **ouvrir un navigateur** sur le domaine
Login (ou directement sur l'IP de la VM, même sans DNS configuré — le vhost
Login répond en `default_server`) : la page affiche automatiquement
l'assistant de premier accès (`/setup/`) tant qu'aucun compte n'existe —
nom de l'entreprise, email/mot de passe administrateur, fuseau horaire.
Cette étape ne se déroule qu'une seule fois ; une fois complétée, `/setup/`
redirige vers la page de connexion normale.

## Activer Cloudflare Tunnel après coup

Si aucun token n'a été fourni à `deploy.sh` au moment du déploiement, le
service est désactivé. `scripts/orion-cloudflare.sh` l'active sans redéployer :

```bash
qm guest exec <vmid> -- /bin/bash -c '/opt/orion/scripts/orion-cloudflare.sh'
```

donne l'état courant (mode token ou fichier, service actif, hostnames,
journal). Pour poser le token :

```bash
# depuis l'hyperviseur, le token ne touche jamais le disque de la VM
qm guest exec <vmid> --pass-stdin 1 -- /bin/bash -c '/opt/orion/scripts/orion-cloudflare.sh set-token' < token.txt
```

Le token est lu sur **l'entrée standard**, jamais en argument : passé en
paramètre, il se retrouverait dans l'historique du shell et dans la liste des
processus, lisible par tout utilisateur de la machine. Le script valide sa
longueur, installe l'unité systemd, l'active, puis **vérifie que la connexion
au réseau Cloudflare est établie** avant de rendre la main — et affiche le
journal en cas d'échec.

Cette commande passe par l'agent invité et ne requiert donc **aucune clé
SSH** : sans `--sshkey` au déploiement, la VM n'est de toute façon pas
joignable en SSH (`ssh_pwauth` est à `false` et les mots de passe sont
verrouillés).

Pour désactiver le tunnel sans perdre le token :

```bash
qm guest exec <vmid> -- /bin/bash -c '/opt/orion/scripts/orion-cloudflare.sh disable'
```

Puis déclarer les hostnames publics dans le dashboard Cloudflare Zero Trust
(Tunnels → *tunnel* → Public Hostname), chacun pointant vers
`http://localhost:<port>` (9000/5172/5173/5174 — voir tableau dans README.md).

Le domaine NÉOSTRUCTURA est le seul à viser `http://localhost:80` : Nginx sert
son build statique et proxifie `/api` vers Django, parce que son client API
utilise des chemins relatifs et exige donc la même origine. Le pointer vers un
port applicatif direct casserait tous ses appels API.

**Alternative avancée (tunnel géré localement, sans dashboard)** : un modèle
d'ingress prêt à l'emploi existe dans `/etc/cloudflared/config.yml.tmpl`
(installé par `provisioning/05-cloudflared-config.sh`). Utile si vous préférez
un tunnel nommé classique (`cloudflared tunnel create` + `tunnel route dns` +
fichier de credentials) plutôt qu'un tunnel à token géré depuis le dashboard.
Remplacer les `__*_DOMAIN__` par les domaines réels et l'utiliser comme
`/etc/cloudflared/config.yml`.

## Mettre à jour sans passer par l'interface web

L'interface web ne doit **jamais** être une dépendance de la mise à jour.
Elle l'était, et cela se payait : le mécanisme applicatif
(`manage.py run_system_update`, derrière le bouton de l'ERP) lit la base
avant tout, tourne dans un worker gunicorn, et sous l'utilisateur `orion`
qui n'est pas administrateur. Donc indisponible quand MySQL est tombé,
interrompu si le backend est tué faute de mémoire, et incapable de
rafraîchir les paquets apt, `/etc/sudoers.d/`, `/usr/local/sbin/` ou les
unités systemd — c'est ainsi que l'assistant de préparation des disques est
resté absent d'une machine pourtant mise à jour plusieurs fois.

La mise à jour est donc portée par une unité systemd, qui appelle le script
root. Depuis l'hyperviseur, sans session dans la VM et sans que Django ni la
base soient en état :

```bash
qm guest exec <vmid> --timeout 60 -- systemctl --no-block start orion-update.service
```

Elle tourne en root, détachée de toute requête HTTP et de toute session :
elle survit à un onglet fermé, à un redémarrage du backend et à un
`qm guest exec` interrompu. Elle n'est **pas** activée au démarrage et ne se
lance jamais d'elle-même.

`--no-block` n'est pas facultatif. `systemctl start` sur une unité
`Type=oneshot` est **synchrone** : il attend la sortie du processus, donc
jusqu'à 5400 s ici. Sans cette option, `qm guest exec` coupe au bout de son
délai, et le bouton de l'ERP attendrait la mise à jour entière dans un
worker gunicorn — ce que tout ce dispositif existe pour éviter.

En conséquence, un code de retour nul signifie « travail accepté », et non
« mise à jour réussie ». Le verdict se lit dans l'état et dans le journal,
ci-dessous — jamais dans le code de retour du déclenchement.

Suivre son avancement, sans la base :

```bash
qm guest exec <vmid> --timeout 60 -- cat /opt/orion/logs/maj-etat.json
qm guest exec <vmid> --timeout 60 -- journalctl -u orion-update -n 60 --no-pager
```

Le fichier d'état porte l'étape, le mode, le code de sortie et l'horodatage.
Il est écrit par un piège sur `EXIT`, pour qu'une mise à jour tuée en route
n'y reste pas marquée « en cours ».

### Le contrôle préalable

Le script refuse de commencer si la machine ne peut pas encaisser le
travail — moins de 2 Go libres sur `/`, ou moins de 600 Mo de mémoire
disponible :

```
[0/6] Controle prealable : 1400 Mo libres sur /, 420 Mo de memoire disponible.
  ECHEC: moins de 2048 Mo libres sur /. ...
  Mise a jour NON DEMARREE : rien n'a ete modifie.
```

C'est voulu : un refus net ne laisse rien à rattraper, contrairement à un
échec au milieu d'un `apt upgrade` ou d'un `CREATE TABLE`. Les deux pannes
de mise à jour de cette appliance sont arrivées sur une machine à 85 % de
disque et à bout de mémoire.

### Première mise en route

L'unité et la règle sudo sont posées par le provisioning et rafraîchies par
`update_orion.sh`. Sur une appliance installée avant leur arrivée, il faut
donc **un premier lancement en root** pour les installer :

```bash
qm guest exec <vmid> --timeout 60 -- /bin/bash -lc 'nohup /opt/orion/scripts/update_orion.sh --direct > /opt/orion/logs/maj-manuelle.log 2>&1 & echo lancee'
```

Ensuite seulement, `systemctl --no-block start orion-update.service` et le bouton de
l'ERP existent.

### Le bouton de l'ERP

Il ne fait plus le travail : il déclenche l'unité, puis rend la main. La page
affiche l'état lu sur le disque et auprès de systemd, jamais en base. Le
droit correspondant est une règle sudo **exacte**, sans joker, dans
`sudoers/orion-maj` — un motif `systemctl *` donnerait à `orion` le contrôle
de tous les services de la machine.

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

La **première** commande à lancer devant un symptôme (502, 500, page
blanche) : elle nomme la cause au lieu de la laisser deviner.

```bash
# Vérification complète — à lancer en premier
sudo bash /opt/orion/scripts/orion-verifier.sh

# Statut général
sudo /opt/orion/scripts/orion-dashboard.sh

# Vérification de santé manuelle (sans réparation)
sudo python3 /opt/orion/scripts/orion_health_check.py --dry-run --json

# Logs de provisioning Stage A (installation, .env, migrations, nginx...)
sudo tail -f /var/log/orion-provision.log

# Statut du backend Django (créé le compte admin via /setup/ dans le navigateur)
sudo systemctl status orion-backend.service
```
