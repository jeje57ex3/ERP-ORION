# Sauvegardes

## Automatique

Cron quotidien à 2h (`/etc/cron.d/orion-backup`, installé par
`provisioning/07-backup-cron.sh`) :

```
0 2 * * * root /opt/orion/scripts/backup.sh >> /opt/orion/logs/backup.log 2>&1
```

`backup.sh` effectue :

1. Dump MySQL brut (`mysqldump` dans le conteneur `orion-db`) — indépendant
   de Django, garantie de base même si l'application est en panne.
2. Sauvegarde applicative via `manage.py backup_all` (base centrale + toutes
   les entreprises actives — réutilise `apps.backups`, pas de logique
   dupliquée).
3. Copie de `.env` (configuration).
4. Compression en une archive unique `orion_backup_<date>.tar.gz` dans
   `/opt/orion/backups/`.
5. Purge des sauvegardes de plus de `ORION_BACKUP_RETENTION_DAYS` jours
   (défaut : 14 — modifiable dans `.env`).

## Manuel

```bash
sudo /opt/orion/scripts/backup.sh
```

## Restauration

Base de données (depuis le dump brut inclus dans l'archive) :

```bash
tar xzf /opt/orion/backups/orion_backup_<date>.tar.gz -C /tmp
docker compose -f /opt/orion/docker/docker-compose.yml exec -T orion-db \
  mysql -uorion -p"$DB_PASSWORD" orion_core < /tmp/orion_backup_<date>/database.sql
```

Sauvegardes applicatives (par entreprise) :

```bash
sudo -u orion /opt/orion/backend/.venv/bin/python /opt/orion/backend/manage.py restore_backup --help
```

## Vérification

```bash
sudo -u orion /opt/orion/backend/.venv/bin/python /opt/orion/backend/manage.py check_backups
```

## Emplacement

- Archives : `/opt/orion/backups/orion_backup_*.tar.gz`
- Journal : `/opt/orion/logs/backup.log`
