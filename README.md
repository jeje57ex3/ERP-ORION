# Orion ERP

ERP interne multi-modules pour la gestion de SIÈCLE Créations et LUNEA Beauty.
Développé en Django 5 + Python 3.12.

> **Dépôt privé.** Ne jamais partager les clés, tokens, fichiers `.env`, bases locales ou backups.

---

## Modules

| Module | Description |
|---|---|
| `orion_admin` | Interface d'administration interne Orion |
| `private_suite` | Espace privé — gestion avancée |
| `enterprise` | Fonctionnalités entreprise multi-sites |
| `system_updates` | Mises à jour système via git |
| `dashboard_widgets` | Widgets configurables du tableau de bord |
| `website_shop_settings` | Paramètres boutiques SIÈCLE / LUNEA |
| `continuous_improvement` | Suivi des améliorations et KPIs |
| `orion_ai` | Intégration IA (GPT-4o, analyse, génération) |
| `high_availability` | Réplication et haute disponibilité |
| `lunea_beauty_profile` | Profils beauté clients LUNEA |
| `siecle_creations` | Gestion créations SIÈCLE |
| `client_portal` | Portail client externe |
| `electricity` | Gestion facturation électricité |
| `core` | Noyau commun : menus, permissions, middlewares |

---

## Manuel d'installation

### Prérequis

| Outil | Version | Notes |
|---|---|---|
| Python | 3.12 (3.10+ accepté) | [python.org](https://www.python.org/downloads/) — cocher "Add to PATH" sous Windows |
| MySQL | 8.0 | Natif, ou via [XAMPP](https://www.apachefriends.org/) pour un poste de dev Windows |
| Node.js | 20 LTS | Requis uniquement pour les boutiques SIÈCLE / LUNEA (`frontend/`) |
| Git | — | — |

### 1 — Cloner le dépôt

```bash
git clone https://github.com/jeje57ex3/ERP-ORION.git
cd ERP-ORION
```

### 2 — Créer la base de données MySQL

```sql
CREATE DATABASE orion_core CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Avec XAMPP : démarrer **MySQL** dans le panneau de contrôle, puis exécuter la
commande ci-dessus depuis phpMyAdmin (http://localhost/phpmyadmin/) ou la
CLI `mysql`.

### 3 — Environnement virtuel et dépendances

```powershell
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

```bash
# Linux / macOS
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> **Erreur `mysqlclient` sous Windows** : installer le binaire précompilé
> (`pip install --only-binary=:all: mysqlclient`) ou basculer sur
> `pip install PyMySQL` puis ajouter dans `erp_btp/__init__.py` :
> `import pymysql; pymysql.install_as_MySQLdb()`.

### 4 — Configurer les variables d'environnement

```bash
cp .env.example .env      # Copy-Item .env.example .env  (PowerShell)
```

Variables critiques à renseigner dans `.env` :

| Variable | Rôle |
|---|---|
| `SECRET_KEY` | Clé Django — `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `DEBUG` | `True` en dev, `False` en production |
| `ALLOWED_HOSTS` | `localhost,127.0.0.1` en local |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | Connexion MySQL (créée à l'étape 2) |
| `ORION_SECRET_ENCRYPTION_KEY` | Clé Fernet — `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |

### 5 — Migrations et compte administrateur

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

### 6 — Données de démonstration (optionnel)

```bash
python manage.py create_demo_data
```

Crée 5 entreprises de démo (BTP, e-commerce, commerce, production, audio),
7 comptes utilisateurs (mot de passe `Demo@2024!`) et des sites publics
d'exemple. Réinitialiser avec `python manage.py create_demo_data --reset`.

### 7 — Lancer le serveur

```bash
python manage.py runserver 9000
```

Boutiques SIÈCLE et LUNEA (optionnel, nécessite Node.js 20) :

```bash
cd frontend/siecle-store && npm install && npm run dev   # http://localhost:5173
cd frontend/lunea-store  && npm install && npm run dev   # http://localhost:5174
```

Sous Windows, `./start-dev.ps1` démarre MySQL (XAMPP), Django et les deux
boutiques en une seule commande.

### 8 — Accéder à l'application

| URL | Contenu |
|---|---|
| http://localhost:9000/ | ERP |
| http://localhost:9000/admin/ | Admin Django |
| http://localhost:9000/accounts/login/ | Connexion |
| http://localhost:5173/ | Boutique SIÈCLE (si lancée) |
| http://localhost:5174/ | Boutique LUNEA (si lancée) |

Comptes de démonstration (si l'étape 6 a été exécutée) :

| Utilisateur | Mot de passe | Rôle |
|---|---|---|
| `admin` | `Admin@2024!` | Superadmin |
| `admin_btp` | `Demo@2024!` | Admin — BTP Lefèvre |
| `admin_ecom` | `Demo@2024!` | Admin — E-Shop Tendance |
| `commercial1` | `Demo@2024!` | Commercial — BTP Lefèvre |

### Résolution de problèmes courants

```bash
# Conflit de migrations
python manage.py makemigrations --merge
python manage.py migrate --run-syncdb

# Réinitialiser les données de démo
python manage.py create_demo_data --reset
```

### Pour aller plus loin

Le guide [`INSTALL.md`](INSTALL.md) détaille en plus : la structure complète
du projet, la roadmap par phases, et le build de l'application mobile Flutter
(Android/iOS).

---

## Installation rapide — Serveur Linux vierge (une ligne)

Pour un déploiement simple et rapide sur un serveur Ubuntu 22.04/24.04 ou
Debian 12 fraîchement installé (VPS ou machine physique), sans passer par
l'appliance Proxmox complète : [`deployment/quick-install/install.sh`](deployment/quick-install/install.sh)
installe et configure tout en une seule commande — Docker (MySQL + Redis),
Python/venv, Nginx, l'application, un compte super-admin, et les services
systemd.

```bash
ORION_DOMAIN=erp.mondomaine.fr \
ORION_ADMIN_EMAIL=admin@mondomaine.fr \
bash -c "$(curl -fsSL https://raw.githubusercontent.com/jeje57ex3/ERP-ORION/main/deployment/quick-install/install.sh)"
```

Variables disponibles : voir l'en-tête de
[`install.sh`](deployment/quick-install/install.sh) (mot de passe admin,
nom d'entreprise, branche, répertoire d'installation...).

À la fin de l'installation, le script affiche l'URL, l'email admin et le
mot de passe généré (si non fourni). HTTPS (Certbot) et l'envoi d'emails
réels (relais SMTP auto-hébergé, réutilise
[`setup_mail_relay.sh`](deployment/proxmox-appliance/scripts/setup_mail_relay.sh))
sont à activer ensuite, les commandes exactes sont affichées en fin de script.

---

## Manuel d'installation — Appliance Proxmox (production)

Déploiement production packagé en **VM Proxmox clé en main** : Ubuntu 24.04,
Django (login + vitrine), SIÈCLE, LUNEA, MySQL, Redis, Nginx, Cloudflare
Tunnel, pare-feu, sauvegardes et supervision automatiques. Détails complets
dans [`deployment/proxmox-appliance/docs/`](deployment/proxmox-appliance/docs/)
(README, INSTALL, PROXMOX, BACKUP, UPDATE, CHANGELOG) — résumé ci-dessous.

### Topologie de la VM

| Domaine | Port local | Service systemd | Rôle |
|---|---|---|---|
| `login.<domaine>` | 9000 | `orion-backend` | Django ERP / admin |
| `orion.<domaine>` | 5172 | `orion-frontend` | Django Vitrine (même code) |
| `siecle.<domaine>` | 5173 | `siecle-frontend` | SPA React SIÈCLE |
| `lunea.<domaine>` | 5174 | `lunea-frontend` | SPA React LUNEA |

MySQL 8.0 et Redis 7 tournent en conteneurs Docker (`orion-db-stack`) ; les 4
services applicatifs tournent nativement (systemd) pour rester individuellement
pilotables — topologie identique à la production réelle.

Ressources VM : 4 vCPU, 8 Go RAM, disque 80 Go (VirtIO, discard/TRIM), BIOS
UEFI (OVMF), machine `q35`.

### 1 — Créer la VM (tout-en-un, recommandé)

`deploy_proxmox_vm.sh` s'exécute **directement sur le host Proxmox** (Shell
du nœud dans l'UI, ou SSH `root@proxmox` — Proxmox fournit déjà `qemu-img` /
`qm` / `pvesh` / `pvesm` nativement) et enchaîne build + import + démarrage.

Lancé sans option, il ouvre un **assistant interactif** : choix du disque
d'installation (liste des stockages Proxmox détectés), de sa taille, du
bridge réseau (DHCP ou IP statique), de la RAM/vCPU, de la clé SSH (détection
des `~/.ssh/*.pub`), puis récapitulatif avant de créer la VM.

**Ligne unique** (façon scripts communautaires Proxmox) — à coller dans le
Shell du nœud (UI Proxmox) ou en SSH `root@proxmox`, clone le dépôt puis
lance l'assistant interactif :

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/jeje57ex3/ERP-ORION/main/deployment/proxmox-appliance/bootstrap.sh)"
```

Pour passer directement des options non-interactives, ajouter `bash` (place-
holder `$0` requis par la syntaxe `bash -c`) puis les options de `deploy.sh`
à la suite de la ligne ci-dessus :

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/jeje57ex3/ERP-ORION/main/deployment/proxmox-appliance/bootstrap.sh)" bash --vmid 210 --name OrionERP-Client
```

Ou, si le dépôt est déjà cloné localement sur le host Proxmox :

```bash
git clone https://github.com/jeje57ex3/ERP-ORION.git
cd ERP-ORION
./deploy_proxmox_vm.sh
```

Mode non-interactif (paramètres explicites, pour scripts/CI) :

```bash
./deploy_proxmox_vm.sh 2026.08.05 \
  --name OrionERP \
  --storage local-lvm \
  --disk-size 120G \
  --bridge vmbr0 \
  --ip 192.168.1.50/24 --gateway 192.168.1.1 \
  --sshkey ~/.ssh/id_ed25519.pub
```

Redéployer une nouvelle VM à partir du même build (multi-clients) :
`./deploy_proxmox_vm.sh --skip-build --name OrionERP-Client2`. Voir
`./deploy_proxmox_vm.sh --help` pour toutes les options.

<details>
<summary>Étape par étape (si le build a lieu sur un autre hôte Linux que le host Proxmox)</summary>

```bash
# Sur l'hôte de build (n'importe quel Linux avec qemu-img)
sudo apt-get install -y qemu-utils curl python3 git tar coreutils gawk
git clone https://github.com/jeje57ex3/ERP-ORION.git
cd ERP-ORION
./build_proxmox_appliance.sh 2026.08.05

# Copier build/ sur le host Proxmox
scp -r build/ root@proxmox:/root/orion-appliance-2026.08.05
ssh root@proxmox
cd /root/orion-appliance-2026.08.05

# Importer et démarrer
./import_proxmox.sh \
  --vmid 9000 --name OrionERP \
  --storage local-lvm --snippets-storage local --bridge vmbr0 \
  --sshkey ~/.ssh/id_ed25519.pub --start
```

`build/` contient `OrionERP.qcow2`, `OrionERP.ova`, `OrionERP.manifest`,
`checksum.sha256`, les fichiers cloud-init et `import_proxmox.sh`.
</details>

Sous le capot : `qm create` (q35, OVMF, VirtIO), `qm importdisk`, `qm set`
(disque + cloud-init personnalisé via `--cicustom`), `qm resize`, puis
démarrage (ou `--as-template` pour convertir en template au lieu de démarrer).

> Le stockage snippets doit autoriser le contenu **Snippets**
> (Datacenter → Stockage → *storage* → Contenu, ou `pvesm set local --content ...,snippets`).

### 2 — Premier démarrage (aucune étape interactive)

1. Domaines et token Cloudflare (optionnels) se saisissent **avant** la
   création de la VM, dans l'assistant de `deploy.sh` (ou via
   `--login-domain`/`--orion-domain`/`--siecle-domain`/`--lunea-domain`/`--cf-token`
   en mode non-interactif).
2. Le provisioning (Stage A, ~3-8 min) est entièrement automatique : `.env`
   écrit, base migrée, nginx configuré avec les vrais domaines, frontends
   construits, les services applicatifs et la supervision
   (`orion-health.timer`) démarrent seuls. Rien à surveiller sur la console.
3. Une fois terminé, **ouvrir un navigateur** sur le domaine Login (ou l'IP
   de la VM) : l'assistant web de premier accès (`/setup/`) s'affiche
   automatiquement — entreprise, email et mot de passe administrateur,
   fuseau horaire. Une seule fois, comme la plupart des logiciels
   auto-hébergés (Nextcloud, WordPress...).

### 3 — Exploitation

```bash
# Tableau de bord système (CPU/RAM/disque/services/SSL/backups)
sudo /opt/orion/scripts/orion-dashboard.sh

# Sauvegarde manuelle (auto tous les jours à 2h)
sudo /opt/orion/scripts/backup.sh

# Mise à jour complète (OS + Docker + Node + Python + Orion ERP)
sudo /opt/orion/scripts/update_orion.sh

# Nettoyage (logs, caches, Docker, backups expirés)
sudo /opt/orion/scripts/cleanup.sh

# Vérification de santé manuelle
sudo python3 /opt/orion/scripts/orion_health_check.py --dry-run --json
```

Activer Cloudflare Tunnel après coup (si aucun token saisi au premier
démarrage) : `sudo cloudflared service install <TOKEN>`, puis déclarer les 4
hostnames publics dans le dashboard Cloudflare Zero Trust vers
`http://localhost:<port>`.

Détails, dépannage et rollback : voir
[`deployment/proxmox-appliance/docs/PROXMOX.md`](deployment/proxmox-appliance/docs/PROXMOX.md),
[`BACKUP.md`](deployment/proxmox-appliance/docs/BACKUP.md) et
[`UPDATE.md`](deployment/proxmox-appliance/docs/UPDATE.md).

---

## Architecture UI interne

L'interface interne Orion utilise un design system isolé (`orion-internal`) qui n'interfère
pas avec les boutiques publiques SIÈCLE et LUNEA.

```
static/orion/css/
├── orion-internal.css          # Point d'entrée (imports)
├── orion-core-theme.css        # Variables CSS, couleurs, typographie
├── orion-internal-layout.css   # App shell, sidebar, topbar
├── orion-internal-components.css
├── orion-internal-forms.css
├── orion-internal-tables.css
├── orion-internal-badges.css
├── orion-internal-widgets.css
├── orion-internal-utilities.css
└── orion-internal-overrides.css

templates/layouts/
├── orion_internal.html         # Layout standalone (Bootstrap 5.3.3 CDN)
├── orion_admin.html            # Extend orion_internal.html
├── private_suite.html
└── enterprise.html
```

**Règle absolue** : jamais de classes ou CSS `orion-internal` dans les templates publics
(`templates/store/`, `frontend/siecle-store/`, `frontend/lunea-store/`).

---

## Scripts de maintenance

```bash
# Vérifier les secrets avant commit
python scripts/check_secrets_before_commit.py

# Vérifier la cohérence du thème interne
python scripts/check_orion_internal_ui_consistency.py

# Vérifier qu'aucun CSS interne ne fuite vers les boutiques
python scripts/check_no_internal_theme_on_public_sites.py

# Détecter les doublons UI
python scripts/find_duplicate_internal_elements.py

# Commande management — audit UI
python manage.py orion_ui_cleanup
python manage.py orion_ui_cleanup --list-widgets
python manage.py orion_ui_cleanup --list-duplicates
```

---

## Sécurité — règles absolues

- **Ne jamais committer** : `.env`, bases SQLite locales, backups, `media/` clients,
  clés Stripe live (`sk_live_`), tokens API, fichiers `.pem` ou clés privées.
- Le hook `pre-commit` bloque automatiquement les commits contenant des secrets détectés.
- Toutes les variables sensibles doivent être dans `.env` (non commité).
- `.env.example` est le seul fichier d'environnement commité — avec des valeurs fictives.

---

## Branches

| Branche | Rôle |
|---|---|
| `main` | Production stable |
| `develop` | Intégration continue |
| `feature/*` | Nouvelles fonctionnalités |
| `hotfix/*` | Correctifs urgents production |

---

## Confidentialité

Ce dépôt est **privé**. Ne pas le rendre public. Ne pas partager l'URL avec des tiers
sans accord explicite. Les données clients, configurations de sites, et paramètres de
paiement ne doivent jamais apparaître dans ce dépôt.
