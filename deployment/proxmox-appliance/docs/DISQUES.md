# Disques, volumes et emplacement des données

L'appliance tient sur **un seul système de fichiers** (`/`). Il n'y a pas de
volume séparé pour la base, les médias ou les sauvegardes : tout partage le
même espace, et c'est ce qui rend important de savoir ce qui grossit.

Outil de référence, installé dans la VM par le provisioning :

```bash
/opt/orion/scripts/orion-disk.sh            # état des volumes et emplacements
/opt/orion/scripts/orion-disk.sh top 20     # les plus gros consommateurs
/opt/orion/scripts/orion-disk.sh grow       # étendre après un qm resize
/opt/orion/scripts/orion-disk.sh prune      # sauvegardes purgeables (simulation)
```

Depuis l'hyperviseur, sans ouvrir de session dans la VM :

```bash
qm guest exec <vmid> -- /bin/bash -c '/opt/orion/scripts/orion-disk.sh'
```

## Où vont les données

| Emplacement | Contenu | Purge |
|---|---|---|
| `/opt/orion/docker/mysql` | **Données MySQL** (volume du conteneur `orion-db`) | aucune — grossit avec vos données |
| `/opt/orion/docker/redis` | Persistance Redis | aucune — volume faible |
| `/opt/orion/uploads` | **Médias** : photos, PDF, APK mobiles, téléchargements publics | **aucune — jamais purgé** |
| `/opt/orion/backend/storage/backups` | **Sauvegardes de l'ERP** : celles qu'on télécharge depuis l'interface | seulement si rattachées à une planification active |
| `/opt/orion/backups` | Archives nocturnes `orion_backup_*.tar.gz` | oui — `ORION_BACKUP_RETENTION_DAYS` (14 j par défaut) |
| `/opt/orion/logs` | Journaux Django, gunicorn, Celery | rotation 10 Mo × 10 par fichier |
| `/opt/orion/backend/.venv` | Environnement Python | remplacé aux mises à jour |
| `/opt/orion/backend/staticfiles` | Fichiers statiques collectés | écrasé à chaque `collectstatic` |
| `/opt/orion/backend/frontend` | Sources et `node_modules` des frontends | réinstallé aux mises à jour |
| `/opt/orion/siecle`, `/opt/orion/lunea`, `/opt/orion/neostructura` | Builds React servis en production | écrasés à chaque build |
| `/opt/orion-appliance` | Payload de provisioning du premier démarrage | aucune — supprimable après installation |

`backend/media` et `backend/logs` sont des **liens symboliques** vers
`/opt/orion/uploads` et `/opt/orion/logs` : le code Django écrit dans son
arborescence habituelle, les données vivent hors du clone Git et survivent aux
mises à jour (voir `provisioning/02-deploy-orion.sh`).

## Les deux systèmes de sauvegarde

C'est la source de confusion la plus fréquente : **il y en a deux**, à des
emplacements différents et avec des politiques de purge différentes.

**1. Les archives de l'appliance** — `/opt/orion/backups`

Produites chaque nuit à 2 h par `scripts/backup.sh` (cron). Chaque archive
contient un dump MySQL brut, les sauvegardes applicatives et le `.env`. Ce
répertoire est aussi monté dans le conteneur MySQL sous `/backups`.

Purge automatique : `backup.sh` supprime les `orion_backup_*.tar.gz` de plus de
`ORION_BACKUP_RETENTION_DAYS` jours. Attention, **seuls les fichiers portant ce
nom** sont concernés : tout autre fichier déposé là reste indéfiniment.

**2. Les sauvegardes de l'ERP** — `/opt/orion/backend/storage/backups`

Celles que crée l'interface (menu Sauvegardes) et que l'on télécharge, y
compris les exports portables. Elles sont **à l'intérieur du clone Git**, et non
dans un volume dédié.

Purge automatique : `cleanup_old_backups()` ne traite que les sauvegardes
rattachées à une **planification active** dont la rétention est > 0. Une
sauvegarde lancée à la main — ou un export portable — **n'est donc jamais
purgée**. C'est le principal mécanisme de remplissage silencieux du disque.

Pour les supprimer, passez par l'ERP plutôt que par `rm` : effacer les fichiers
laisserait des `BackupJob` en base pointant vers le vide.

## Ce qui remplit le disque, en pratique

Par ordre de volume constaté :

1. **Les builds mobiles** (`.apk`) dans `/opt/orion/uploads`. Ce sont des
   artefacts reconstructibles : un seul en pèse ~85 Mo, et six suffisent à
   occuper 1 Go. Ils sont désormais exclus des exports portables par défaut,
   mais restent sur le disque.
2. **Les exports portables accumulés** dans `storage/backups`, jamais purgés.
3. **Les données MySQL** dans `/opt/orion/docker/mysql` — croissance normale,
   proportionnelle à l'usage.
4. **`node_modules`** des trois frontends, réinstallés à chaque mise à jour.

`orion-disk.sh top 20` donne le classement réel de votre installation.

## Agrandir le disque

Deux étapes, et **la seconde est indispensable** : agrandir le disque virtuel
côté Proxmox ne fait rien gagner tant que la partition et le système de
fichiers n'ont pas été étendus à l'intérieur de la VM. `growpart` ne tourne
automatiquement qu'au **premier** démarrage (cloud-init), pas aux suivants.

**1. Côté Proxmox**, à chaud, sans arrêter la VM :

```bash
qm resize <vmid> scsi0 +40G
```

**2. Dans la VM** :

```bash
qm guest exec <vmid> -- /bin/bash -c '/opt/orion/scripts/orion-disk.sh grow'
```

La commande détecte la partition racine et son type (`ext4`, `xfs`, `btrfs`),
appelle `growpart` puis l'outil d'extension correspondant, et affiche l'espace
avant/après. Elle est idempotente : relancée sans rien à récupérer, elle le
signale sans échouer.

Pour vérifier qu'il reste de l'espace non alloué :

```bash
qm guest exec <vmid> -- /bin/bash -c '/opt/orion/scripts/orion-disk.sh' | grep -A3 "non alloué"
```

> Si la racine est sur du LVM ou un partitionnement inhabituel, le script
> s'arrête en le disant plutôt que de tenter une manipulation hasardeuse.

## Surveillance

L'ERP mesure déjà l'espace disque et alerte tout seul :

| Capteur | Alerte | Critique |
|---|---|---|
| `disk_usage` (% utilisé) | > 80 % | > 95 % |
| `disk_free_gb` (Go libres) | < 5 Go | < 2 Go |

Ces seuils sont posés par `manage.py setup_health_thresholds` et modifiables
depuis l'ERP. `apps/orion_ops` calcule en plus une tendance sur 7 et 30 jours,
qui permet d'anticiper la saturation plutôt que de la découvrir.

Et dans l'ERP, **Santé système → Disques & stockage** présente visuellement
les volumes montés, les allocations du disque (partitions et espace non
alloué) et la répartition des données avec leur politique de purge.

Vue rapide côté système :

```bash
/opt/orion/scripts/orion-dashboard.sh     # dont une ligne « Disque »
```

## Voir aussi

- [BACKUP.md](BACKUP.md) — fonctionnement et restauration des sauvegardes
- [DATA-MIGRATION.md](DATA-MIGRATION.md) — importer les données d'un autre poste
- [PROXMOX.md](PROXMOX.md) — options de déploiement, dont `--disk-size`
