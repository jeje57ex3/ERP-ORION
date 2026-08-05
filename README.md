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

### 1 — Construire l'image (sur un hôte Linux avec `qemu-img`)

Le build **doit** s'exécuter sur Linux — typiquement le serveur Proxmox
lui-même via SSH (pas sur un poste Windows sans WSL/qemu-img) :

```bash
sudo apt-get install -y qemu-utils curl python3 git tar coreutils gawk

git clone https://github.com/jeje57ex3/ERP-ORION.git
cd ERP-ORION
./build_proxmox_appliance.sh 2026.08.05
```

Produit dans `build/` :

```
OrionERP.qcow2                          # disque de la VM
OrionERP.ova                            # export portable (VMware, etc.)
OrionERP.manifest                       # JSON : versions, modules, ports
checksum.sha256                         # SHA256 du qcow2 et de l'ova
OrionERP.cloudinit-userdata.yaml        # provisioning automatique (Stage A)
OrionERP.cloudinit-network-config.yaml
import_proxmox.sh                       # script d'import (étape suivante)
```

### 2 — Importer dans Proxmox

Si le build a eu lieu ailleurs, copier `build/` sur le host Proxmox :

```bash
scp -r build/ root@proxmox:/root/orion-appliance-2026.08.05
ssh root@proxmox
cd /root/orion-appliance-2026.08.05
```

Puis importer et démarrer la VM :

```bash
./import_proxmox.sh \
  --vmid 9000 \
  --name OrionERP \
  --storage local-lvm \
  --snippets-storage local \
  --bridge vmbr0 \
  --sshkey ~/.ssh/id_ed25519.pub \
  --start
```

Le script exécute `qm create` (q35, OVMF, VirtIO), `qm importdisk`,
`qm set` (disque + cloud-init personnalisé via `--cicustom`), `qm resize`,
puis démarre la VM (`--start`) ou la convertit en template (`--as-template`).

> Le stockage `--snippets-storage` doit autoriser le contenu **Snippets**
> (Datacenter → Stockage → *storage* → Contenu, ou `pvesm set local --content ...,snippets`).

### 3 — Premier démarrage (assistant interactif)

1. Ouvrir la **console noVNC** de la VM dans Proxmox.
2. Attendre la fin du provisioning automatique (Stage A, ~2-5 min).
3. L'assistant apparaît automatiquement sur la console (Stage B) et demande :
   entreprise, nom ERP, domaines (Login/Orion/SIÈCLE/LUNEA), email et mot de
   passe administrateur, fuseau horaire, token Cloudflare Tunnel (optionnel).
4. À la fin : `.env` écrit, base migrée, frontends construits, les 4 services
   et la supervision (`orion-health.timer`) démarrent automatiquement.

Aucune configuration manuelle au-delà de ces questions.

### 4 — Exploitation

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
