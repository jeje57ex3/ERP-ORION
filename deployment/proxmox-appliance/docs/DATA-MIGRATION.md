# Migration des données vers l'appliance

L'appliance Proxmox installe le **code** (cloné depuis Git au premier boot)
et démarre avec une base **vide**. Ce document décrit comment y transférer les
**données réelles** d'un poste existant : base MySQL complète, médias,
paramètres par entreprise.

Deux scripts, un aller-retour :

| Script | Où | Rôle |
|---|---|---|
| `scripts/export_orion_data.ps1` | poste Windows source | produit une archive horodatée + son SHA-256 |
| `scripts/install_orion_data.sh` | VM Proxmox cible | vérifie, sauvegarde, restaure, migre, redémarre |

À ne pas confondre avec [BACKUP.md](BACKUP.md), qui décrit les sauvegardes
quotidiennes *de l'appliance elle-même*. Ici, on amorce une appliance neuve
avec des données venues d'ailleurs.

## 1. Export depuis le poste source

```powershell
cd C:\Users\<vous>\Downloads\erp-btp-starter
.\deployment\proxmox-appliance\scripts\export_orion_data.ps1
```

Le script lit `.env` à la racine du projet (`DB_NAME`, `DB_USER`,
`DB_PASSWORD`, `DB_HOST`, `DB_PORT`) : aucun paramètre de connexion à saisir.
MySQL doit tourner.

Il produit dans `build/` :

```
build/
  orion-data-<horodatage>.tar.gz          # archive à transférer
  orion-data-<horodatage>.tar.gz.sha256   # empreinte, à transférer aussi
```

L'archive contient `database.sql` (dump complet : schéma, données, procédures,
déclencheurs), `media/` et `manifest.json` (horodatage, poste source, nom de
la base, commit Git, nombre de tables, empreinte du dump).

### Options

| Option | Effet |
|---|---|
| `-IncludeMobileBuilds` | inclut les `.apk`/`.aab` de `media/` (~1 Go), exclus par défaut |
| `-SkipMedia` | base de données seule |
| `-OutputDir <chemin>` | répertoire de sortie (défaut : `build/`) |
| `-EnvFile <chemin>` | autre fichier `.env` |
| `-MysqlBin <chemin>` | dossier des binaires MySQL (défaut : `C:\xampp\mysql\bin`) |

Les builds mobiles sont des artefacts reconstructibles : les exclure fait
passer l'archive de ~1 Go à une vingtaine de Mo.

### Garde-fous

- Le mot de passe passe par un fichier d'options temporaire, jamais par la
  ligne de commande (où il serait visible dans la liste des processus) ; le
  fichier est supprimé même en cas d'erreur.
- Le dump est écrit en octets bruts via `Start-Process`. Un `| Out-File`
  ajouterait un BOM UTF-8, que MySQL rejette (`ERROR 1064 ... near '﻿'`), et
  ré-encoderait le texte en abîmant les accents. Le script vérifie l'absence
  de BOM et échoue plutôt que de livrer une archive non restaurable.
- Un dump de moins de 1 Ko est considéré comme suspect et interrompt l'export.

## 2. Transfert

```bash
scp build/orion-data-<horodatage>.tar.gz* root@<ip-vm>:/tmp/
```

Transférez **les deux fichiers** : sans le `.sha256`, l'intégrité n'est pas
vérifiée et le script se contente d'un avertissement.

## 3. Import sur l'appliance

```bash
ssh root@<ip-vm>
/opt/orion/backend/deployment/proxmox-appliance/scripts/install_orion_data.sh \
  /tmp/orion-data-<horodatage>.tar.gz
```

Déroulé :

1. **Vérification** — contrôle du SHA-256, puis affichage du manifeste
   (source, date, commit, volume) pour confirmer qu'on importe la bonne
   archive.
2. **Confirmation** — la base de l'appliance va être écrasée ; il faut
   répondre `oui`.
3. **Arrêt** des services applicatifs (`orion-backend`, `orion-frontend`,
   `siecle-frontend`, `lunea-frontend`). La base Docker reste debout.
4. **Sauvegarde de sécurité** dans `/opt/orion/backups/pre-import-<date>.sql.gz`
   — l'état d'avant import reste récupérable.
5. **Restauration** : `DROP` / `CREATE` de la base cible puis chargement du
   dump.
6. **Médias** fusionnés dans `/opt/orion/uploads` (sans suppression : les
   fichiers déjà présents sont conservés), propriétaire `orion`.
7. **`migrate` + `collectstatic`** — si le dump vient d'un code plus ancien
   que celui de l'appliance, les migrations manquantes sont rejouées.
8. **Redémarrage** des services.

### Options

| Option | Effet |
|---|---|
| `--yes`, `-y` | pas de demande de confirmation (usage non interactif) |
| `--no-backup` | pas de sauvegarde préalable (première installation) |

### Pourquoi le dump ne contient pas `CREATE DATABASE`

Le poste de développement utilise la base `erp_btp`, l'appliance `orion_core`.
Le dump est donc neutre : `install_orion_data.sh` crée la base cible lue dans
le `.env` de la VM (`DB_NAME`) et y charge les tables. Un dump avec
`CREATE DATABASE` recréerait `erp_btp` à côté, que Django ne lirait jamais.

## 4. Vérification

```bash
/opt/orion/backend/deployment/proxmox-appliance/scripts/orion-dashboard.sh
```

Puis une connexion à `https://login.<domaine>` avec un compte existant du
poste source : les identifiants sont ceux de la base importée, pas ceux saisis
dans l'assistant de premier démarrage.

## En cas d'échec de la restauration

Le script s'arrête avant le redémarrage des services et affiche les dernières
lignes de l'erreur MySQL. La sauvegarde de sécurité permet de revenir en
arrière :

```bash
source /opt/orion/backend/.env
gunzip -c /opt/orion/backups/pre-import-<date>.sql.gz | \
  docker compose -f /opt/orion/docker/docker-compose.yml exec -T orion-db \
  mysql -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME"
```

## Notes

- L'opération est rejouable : un nouvel import écrase la base et refusionne
  les médias.
- Les archives et dumps sont exclus du dépôt Git (`.gitignore`) : ils
  contiennent des données clients réelles et des empreintes de mots de passe.
- Le dump est produit par MariaDB 10.4 (XAMPP) et restauré sous MySQL 8.0 ;
  cette combinaison a été testée en mode `STRICT_ALL_TABLES`, accents compris.
