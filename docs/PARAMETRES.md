# Paramètres de configuration

Référence des **76 variables** lues par Orion ERP dans son fichier
`.env`, à la racine du projet. Les valeurs par défaut ci-dessous sont extraites
automatiquement de `erp_btp/settings/` : elles reflètent le code, pas une
description écrite à la main.

Un paramètre absent du `.env` prend sa valeur par défaut. Une valeur **présente
mais vide** n'est pas la même chose qu'une valeur absente : plusieurs listes
filtrent les entrées vides pour cette raison.

## Sommaire

- [Sécurité](#sécurité) — 7 paramètre(s)
- [Base de données](#base-de-données) — 7 paramètre(s)
- [Chemins](#chemins) — 6 paramètre(s)
- [Courrier](#courrier) — 6 paramètre(s)
- [Domaines et DNS](#domaines-et-dns) — 7 paramètre(s)
- [Mises à jour](#mises-à-jour) — 14 paramètre(s)
- [Haute disponibilité](#haute-disponibilité) — 13 paramètre(s)
- [Intelligence artificielle](#intelligence-artificielle) — 13 paramètre(s)
- [Paiement](#paiement) — 3 paramètre(s)

## Sécurité

Ces valeurs conditionnent l'accès à l'application. Deux erreurs reviennent sans cesse : un domaine absent d'`ALLOWED_HOSTS` donne un **400**, et le même domaine absent de `CSRF_TRUSTED_ORIGINS` donne un **403** à la soumission du formulaire de connexion — deux symptômes différents pour une seule cause.

| Paramètre | Défaut | Rôle |
|---|---|---|
| `ALLOWED_HOSTS` | *(vide)* | Noms d'hôtes acceptés, séparés par des virgules. Un hôte absent provoque une réponse **400 Bad Request** (DisallowedHost). Sur l'appliance, recalculé à chaque démarrage par `refresh_allowed_hosts.sh`. |
| `CSRF_COOKIE_SECURE` | True · `bool` | Cookie CSRF réservé à HTTPS. À laisser à `False` tant que TLS n'est pas en place, sinon aucun formulaire n'est soumissible en HTTP. |
| `CSRF_TRUSTED_ORIGINS` | *(vide)* | Origines autorisées à soumettre des formulaires, avec le schéma (`https://exemple.fr`). Un domaine absent donne un **403 CSRF** à la soumission, même si l'hôte est autorisé. |
| `ORION_SECRET_ENCRYPTION_KEY` | *(vide)* | Clé Fernet chiffrant les secrets stockés en base (identifiants SMTP, Stripe, SMB…). **La perdre rend ces secrets illisibles** ; la changer a le même effet. |
| `SECRET_KEY` | 'django-insecure-erp-btp-dev-key-change-in-production' | Clé de signature Django (sessions, jetons). **Obligatoire en production**, unique par installation. La divulguer permet de forger des sessions. |
| `SECURE_SSL_REDIRECT` | True · `bool` | Redirige tout HTTP vers HTTPS. À activer seulement derrière un terminaison TLS fonctionnelle. |
| `SESSION_COOKIE_SECURE` | True · `bool` | Cookie de session réservé à HTTPS. Même réserve que ci-dessus. |

## Base de données

| Paramètre | Défaut | Rôle |
|---|---|---|
| `DB_ENGINE` | 'django.db.backends.mysql' | Moteur Django. MySQL/MariaDB en production. |
| `DB_HOST` | '127.0.0.1' | Hôte MySQL. Sous Windows, préférer `127.0.0.1` à `localhost` : ce dernier force le canal nommé. |
| `DB_NAME` | 'orion_core' | Nom de la base centrale. `erp_btp` en développement, `orion_core` sur l'appliance — d'où un dump sans `CREATE DATABASE`. |
| `DB_PASSWORD` | *(vide)* | Mot de passe MySQL. Généré aléatoirement par le provisioning de l'appliance. |
| `DB_PORT` | '3306' | Port MySQL. |
| `DB_USER` | 'root' | Utilisateur MySQL. |
| `REDIS_URL` | 'redis://127.0.0.1:6379/0' | URL Redis, utilisée comme courtier Celery et comme cache. |

## Chemins

| Paramètre | Défaut | Rôle |
|---|---|---|
| `BACKUP_DIR` | 'backups' | Répertoire des sauvegardes système. |
| `LOG_DIR` | 'logs' | Répertoire des journaux, relatif à la racine du projet. Sur l'appliance, lien symbolique vers `/opt/orion/logs`. |
| `ORION_BACKEND_PATH` | *(vide)* | Racine du code Django, utilisée par le mécanisme de mise à jour. |
| `ORION_FRONTEND_LUNEA_PATH` | *(vide)* | Sources du frontend LUNEA, idem. |
| `ORION_FRONTEND_SIECLE_PATH` | *(vide)* | Sources du frontend SIÈCLE, pour la reconstruction automatique. |
| `ORION_PROJECT_ROOT` | *(vide)* | Racine du dépôt Git, là où le `git pull` des mises à jour est exécuté. |

## Courrier

| Paramètre | Défaut | Rôle |
|---|---|---|
| `DEFAULT_FROM_EMAIL` | 'no-reply@orion-erp.local' | Expéditeur par défaut des messages envoyés par l'ERP. |
| `EMAIL_HOST` | 'localhost' | Serveur SMTP sortant. |
| `EMAIL_HOST_PASSWORD` | *(vide)* | Mot de passe SMTP. |
| `EMAIL_HOST_USER` | *(vide)* | Compte SMTP. |
| `EMAIL_PORT` | 25 · `int` | Port SMTP. |
| `EMAIL_USE_TLS` | False · `bool` | STARTTLS sur la connexion SMTP. |

## Domaines et DNS

Ces valeurs alimentent les instructions DNS affichées aux clients. Elles n'ouvrent aucun accès : le raccordement effectif d'un domaine se fait dans **Sites web → Domaines**.

| Paramètre | Défaut | Rôle |
|---|---|---|
| `ORION_CLIENT_PORTAL_CNAME` | 'client.orion-erp.com' | Cible CNAME pour le portail client. |
| `ORION_CLOUDFLARE_API_TOKEN` | *(vide)* | Jeton d'API Cloudflare au niveau installation. Les comptes Cloudflare par entreprise se configurent plutôt dans l'interface. |
| `ORION_ERP_CNAME` | 'erp.orion-erp.com' | Cible CNAME proposée aux clients pour pointer leur domaine vers l'ERP. |
| `ORION_PUBLIC_ERP_URL` | *(vide)* | URL publique de l'ERP, utilisée dans les courriels et les liens absolus. |
| `ORION_PUBLIC_IP` | '0.0.0.0' | IP publique annoncée dans les instructions DNS de type A. |
| `ORION_SITES_CNAME` | 'sites.orion-erp.com' | Cible CNAME pour les sites vitrines et boutiques. |
| `ORION_TEMP_DOMAIN_SUFFIX` | 'orion-sites.local' | Suffixe des sous-domaines temporaires attribués avant qu'un domaine propre soit raccordé. |

## Mises à jour

Le mécanisme sait se réparer : si `run_system_update` échoue, `update_orion.sh` effectue lui-même `git pull`, migrations et collecte des statiques, puis réessaie. Sans ce repli, un bug *dans* la mise à jour était irrécupérable, son correctif ne pouvant arriver que par elle.

| Paramètre | Défaut | Rôle |
|---|---|---|
| `ORION_GIT_BRANCH` | 'main' | Branche tirée. L'appliance suit `main`. |
| `ORION_GIT_REMOTE` | 'origin' | Dépôt distant tiré par la mise à jour. |
| `ORION_UPDATES_ENABLED` | False · `bool` | Interrupteur général du mécanisme de mise à jour. |
| `ORION_UPDATE_ALLOW_ROLLBACK` | True · `bool` | Autorise `manage.py rollback_system_update`. |
| `ORION_UPDATE_BACKUP_COMMAND` | *(vide)* | Commande de sauvegarde préalable. **Si vide, l'ERP se rabat sur `manage.py backup_all`** plutôt que d'échouer — une étape obligatoire sans valeur par défaut rendait toute mise à jour impossible. |
| `ORION_UPDATE_CELERY_BEAT_RESTART_COMMAND` | *(vide)* | Redémarrage du planificateur Celery beat. |
| `ORION_UPDATE_CELERY_RESTART_COMMAND` | *(vide)* | Redémarrage du worker Celery. |
| `ORION_UPDATE_FRONTEND_BUILD_COMMAND` | 'npm run build' | Commande de build des frontends. |
| `ORION_UPDATE_FRONTEND_BUILD_ENABLED` | True · `bool` | Reconstruit les frontends React pendant la mise à jour. |
| `ORION_UPDATE_LOCK_FILE` | '/tmp/orion_update.lock' | Verrou empêchant deux mises à jour simultanées. Il porte désormais son PID et son horodatage : un verrou abandonné (processus tué, VM redémarrée) est repris automatiquement au-delà de 3 h. |
| `ORION_UPDATE_MODE` | 'manual' | Stratégie de mise à jour. |
| `ORION_UPDATE_REQUIRE_BACKUP` | True · `bool` | Exige une sauvegarde avant de migrer. À laisser actif. |
| `ORION_UPDATE_REQUIRE_HEALTH_CHECK` | True · `bool` | Vérifie la santé applicative après mise à jour et échoue sinon. |
| `ORION_UPDATE_RESTART_COMMAND` | *(vide)* | Commande de redémarrage du service applicatif. |

## Haute disponibilité

| Paramètre | Défaut | Rôle |
|---|---|---|
| `ORION_HA_AUTOMATIC_FAILOVER_ENABLED` | False · `bool` | Bascule automatique vers un secondaire. |
| `ORION_HA_ENABLED` | False · `bool` | Active le module de haute disponibilité. |
| `ORION_HA_FAILOVER_AFTER_SECONDS` | 120 · `int` | Délai d'indisponibilité avant bascule. |
| `ORION_HA_MAX_REPLICATION_LAG_SECONDS` | 10 · `int` | Retard de réplication au-delà duquel la bascule est refusée, pour ne pas promouvoir un nœud en retard. |
| `ORION_HA_REQUIRE_MANUAL_CONFIRMATION` | True · `bool` | Exige une confirmation humaine avant de basculer. |
| `ORION_HA_SECRET` | 'CHANGE_ME' | Secret partagé authentifiant les échanges entre nœuds. |
| `ORION_NODE_ID` | 'orion-primary' | Identifiant de ce nœud. |
| `ORION_NODE_PRIORITY` | 1 · `int` | Priorité à la promotion ; le plus élevé gagne. |
| `ORION_NODE_REGION` | 'local' | Région du nœud, à titre informatif. |
| `ORION_NODE_ROLE` | 'primary' | Rôle du nœud (primaire ou secondaire). |
| `ORION_PRIMARY_URL` | *(vide)* | URL du nœud primaire. |
| `ORION_SECONDARY_1_URL` | *(vide)* | URL du premier secondaire. |
| `ORION_SECONDARY_2_URL` | *(vide)* | URL du second secondaire. |

## Intelligence artificielle

| Paramètre | Défaut | Rôle |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(vide)* | Clé API Anthropic. |
| `LOCAL_AI_BASE_URL` | 'http://localhost:11434' | URL d'un modèle auto-hébergé compatible OpenAI. |
| `OPENAI_API_KEY` | *(vide)* | Clé API OpenAI. |
| `ORION_AI_ALLOW_DANGEROUS_ACTIONS` | False · `bool` | Autorise les actions à effet de bord. **À laisser désactivé** sauf besoin explicite. |
| `ORION_AI_ALLOW_TOOLS` | True · `bool` | Autorise l'assistant à appeler des outils internes. |
| `ORION_AI_DEFAULT_MODEL` | 'gpt-4.1-mini' | Modèle par défaut. |
| `ORION_AI_DEFAULT_PROVIDER` | 'openai' | Fournisseur par défaut. |
| `ORION_AI_ENABLED` | False · `bool` | Active l'assistant intégré. |
| `ORION_AI_LOG_CONVERSATIONS` | True · `bool` | Journalise les conversations. Attention aux données personnelles. |
| `ORION_AI_MAX_HISTORY_MESSAGES` | 20 · `int` | Messages d'historique transmis au modèle. |
| `ORION_AI_MAX_INPUT_CHARS` | 20000 · `int` | Taille maximale d'une requête. |
| `ORION_AI_SUPPORT_EMAIL` | *(vide)* | Adresse de contact proposée par l'assistant. |
| `ORION_AI_SYSTEM_NAME` | 'Assistant Orion' | Nom sous lequel l'assistant se présente. |

## Paiement

| Paramètre | Défaut | Rôle |
|---|---|---|
| `STRIPE_PUBLIC_KEY` | *(vide)* | Clé publique Stripe, exposée au navigateur. |
| `STRIPE_SECRET_KEY` | *(vide)* | Clé secrète Stripe. Ne jamais l'exposer au frontend. |
| `STRIPE_WEBHOOK_SECRET` | *(vide)* | Secret de signature des webhooks Stripe, qui authentifie les notifications reçues. |

## Où ces valeurs sont définies

| Contexte | Fichier |
|---|---|
| Développement local | `.env` à la racine du dépôt |
| Appliance Proxmox | `/opt/orion/backend/.env`, généré par `provisioning/02-deploy-orion.sh` |

Sur l'appliance, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` et
`CORS_ALLOWED_ORIGINS` sont **recalculés à chaque démarrage** des services par
`scripts/refresh_allowed_hosts.sh`, à partir des domaines du `.env` et de l'IP
courante de la VM. Les modifier à la main dans le `.env` est donc inutile :
renseignez plutôt `ORION_LOGIN_DOMAIN`, `ORION_FRONTEND_DOMAIN`,
`SIECLE_STORE_DOMAIN`, `LUNEA_STORE_DOMAIN` et `ORION_NS_DOMAIN`, puis
redémarrez. Ce recalcul existe parce qu'un bail DHCP qui change rendait
l'accès par IP impossible après un simple redémarrage.

