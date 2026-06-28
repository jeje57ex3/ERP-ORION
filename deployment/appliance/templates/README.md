# Orion ERP Appliance Package

> Appliance serveur portable basée sur Docker — prête à déployer sur Linux.

## Installation rapide

```bash
cp .env.example .env
nano .env          # configurer les variables critiques
./scripts/install.sh
```

Accéder à Orion :

```
http://localhost
http://localhost/orion-admin/
```

---

## Prérequis

- Linux (Ubuntu 22.04+ recommandé) ou tout OS avec Docker
- Docker Engine 24+ et Docker Compose Plugin v2
- 2 Go RAM minimum (4 Go recommandés)
- 20 Go disque minimum

---

## Variables .env critiques

| Variable | Description |
|---|---|
| `SECRET_KEY` | Clé secrète Django — générer avec `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `MYSQL_PASSWORD` | Mot de passe base de données |
| `MYSQL_ROOT_PASSWORD` | Mot de passe root MySQL |
| `ORION_SECRET_ENCRYPTION_KEY` | Clé Fernet — générer avec `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `ORION_SUPERADMIN_EMAIL` | Email du premier admin |
| `ORION_SUPERADMIN_PASSWORD` | Mot de passe du premier admin |
| `ALLOWED_HOSTS` | Domaines autorisés (séparés par virgule) |
| `CSRF_TRUSTED_ORIGINS` | Origines CSRF (ex: `https://erp.mondomaine.fr`) |

---

## Scripts

```bash
./scripts/install.sh              # Installation complète
./scripts/start.sh                # Démarrer tous les services
./scripts/stop.sh                 # Arrêter tous les services
./scripts/restart.sh              # Redémarrer
./scripts/update.sh               # Mettre à jour (sauvegarde auto)
./scripts/backup.sh               # Créer une sauvegarde
./scripts/restore.sh <fichier>    # Restaurer une sauvegarde
./scripts/health.sh               # Vérifier la santé
./scripts/logs.sh [service]       # Voir les logs
./scripts/migrate.sh              # Lancer les migrations Django
./scripts/createsuperuser.sh      # Créer un superadmin
```

## Avec Makefile

```bash
make install
make start
make stop
make restart
make update
make backup
make restore FILE=backups/orion_backup_20240101_120000.tar.gz
make health
make logs SERVICE=orion-backend
make migrate
make superuser
```

---

## Service systemd (démarrage automatique)

Pour que Orion démarre automatiquement au boot du serveur :

```bash
sudo cp systemd/orion-appliance.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable orion-appliance
sudo systemctl start orion-appliance

# Vérifier le statut
sudo systemctl status orion-appliance
```

---

## Dossiers

| Dossier | Contenu |
|---|---|
| `backend/` | Code Django — Orion ERP |
| `frontend/siecle-store/` | Source React SIÈCLE |
| `frontend/lunea-store/` | Source React LUNEA |
| `nginx/` | Configuration Nginx |
| `static/` | Assets statiques et frontends buildés |
| `media/` | Fichiers uploadés (images, documents) |
| `backups/` | Sauvegardes automatiques |
| `logs/` | Logs backend et Nginx |
| `mysql/` | Données MySQL (volume Docker) |
| `redis/` | Données Redis (volume Docker) |
| `runtime/` | Fichiers temporaires, certificats SSL |
| `systemd/` | Service systemd optionnel |
| `scripts/` | Scripts de gestion |

---

## Services Docker

| Conteneur | Rôle | Port interne |
|---|---|---|
| `orion-backend` | Django + Gunicorn | 8000 |
| `orion-celery` | Worker Celery | — |
| `orion-celery-beat` | Planificateur Celery | — |
| `orion-db` | MySQL 8.0 | 3306 |
| `orion-redis` | Redis 7 | 6379 |
| `orion-nginx` | Reverse proxy | 80, 443 |

---

## HTTPS / SSL

Placer les certificats dans `runtime/certs/` :

```
runtime/certs/fullchain.pem
runtime/certs/privkey.pem
```

Puis modifier `nginx/orion.conf` pour ajouter le bloc SSL :

```nginx
server {
    listen 443 ssl;
    server_name erp.mondomaine.fr;
    ssl_certificate /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;
    ...
}
```

Pour Let's Encrypt automatique, utiliser `certbot` ou Caddy.

---

## Sécurité — checklist post-installation

- [ ] Changer tous les mots de passe dans `.env`
- [ ] `SECRET_KEY` unique et aléatoire (50+ caractères)
- [ ] `DEBUG=False` confirmé
- [ ] `ALLOWED_HOSTS` limité aux vrais domaines
- [ ] Fichier `.env` non exposé publiquement
- [ ] HTTPS configuré en production
- [ ] Sauvegardes automatiques planifiées (cron)
- [ ] Accès SSH sécurisé (clé, pas mot de passe)

---

## Sauvegardes automatiques (cron)

Ajouter dans crontab (`crontab -e`) :

```cron
# Sauvegarde Orion ERP chaque nuit à 2h00
0 2 * * * /opt/OrionERP-Appliance/scripts/backup.sh >> /opt/OrionERP-Appliance/logs/backup.log 2>&1
```

---

## Version

Voir le fichier `VERSION` pour la version de l'appliance.

---

*Orion ERP Appliance Package — Format `.tar.gz` — Docker Compose*
