# Manuel Orion ERP

ERP multi-entreprises couvrant le BTP et l'électricité, le commerce et
l'e-commerce, la production, l'audiovisuel et la gestion de sites web. Une
seule installation sert plusieurs sociétés, chacune avec ses données, ses
modules activés et ses domaines.

Ce manuel est l'entrée du reste de la documentation. Les inventaires qu'il
référence sont **générés depuis le code** : ils ne peuvent pas décrire une
version imaginaire du logiciel.

## Par où commencer

| Vous voulez… | Document |
|---|---|
| Installer en local pour développer | [INSTALL.md](../INSTALL.md) — pas à pas, depuis Python et XAMPP |
| Déployer en production sur Proxmox | [deployment/proxmox-appliance/docs/README.md](../deployment/proxmox-appliance/docs/README.md) |
| Connaître toutes les options de configuration | [PARAMETRES.md](PARAMETRES.md) — 76 variables |
| Savoir quelles pages existent et où | [MODULES.md](MODULES.md) — 27 modules, 110 pages |
| Comprendre où vont les données | [DISQUES.md](../deployment/proxmox-appliance/docs/DISQUES.md) |
| Sauvegarder ou restaurer | [BACKUP.md](../deployment/proxmox-appliance/docs/BACKUP.md) |
| Transférer les données d'un poste vers un serveur | [DATA-MIGRATION.md](../deployment/proxmox-appliance/docs/DATA-MIGRATION.md) |
| Répartir sur plusieurs serveurs, un seul domaine | [HAUTE-DISPONIBILITE.md](HAUTE-DISPONIBILITE.md) |
| Utiliser l'IA locale Orion | [ORION-IA.md](ORION-IA.md) |
| Travailler depuis un téléphone | [VERSION-TELEPHONE.md](VERSION-TELEPHONE.md) |
| Faire sortir les devis sur votre propre papier à en-tête | [MODELES-DE-DEVIS.md](MODELES-DE-DEVIS.md) |

## Ce qui compose l'application

| Brique | Rôle | Port en développement |
|---|---|---|
| Django (ERP) | Interface de gestion, API, administration | 9000 |
| Django (vitrine) | Site vitrine Orion, même code, autre domaine | 5172 |
| SIÈCLE | Boutique React | 5173 |
| LUNEA | Boutique React | 5174 |
| NÉOSTRUCTURA | Site vitrine BTP React, avec configurateur | 5175 |
| MySQL | Base centrale et bases par entreprise | 3306 |
| Redis | Courtier Celery et cache | 6379 |
| Celery | Tâches planifiées : santé, sauvegardes, alertes | — |

Socle : **Django 4.2** sur **Python 3.12+**, 56 applications internes,
19 intergiciels, 2044 routes. Les trois frontends sont des SPA React
construites avec Vite.

En production sur l'appliance, MySQL et Redis tournent en conteneurs Docker,
les services applicatifs nativement sous systemd, et Nginx assure l'accès
local comme la terminaison TLS.

## Le modèle multi-entreprises

Tout tourne autour de `core.Company`. `CompanyMiddleware` résout l'entreprise
active à chaque requête et la dépose sur `request.current_company` ; les
modèles métier héritent de `CompanyBaseModel`, qui porte la clé étrangère vers
l'entreprise.

**Conséquence à retenir** : une donnée sans entreprise, ou rattachée à une
autre que l'entreprise active, est invisible — y compris pour un
superutilisateur. C'est voulu, et c'est la première chose à vérifier quand un
enregistrement « disparaît ».

Les modules visibles dans le menu dépendent de ceux activés pour l'entreprise
(`apps.private_saas`). Un module désactivé n'apparaît pas : son absence du
menu n'est pas un dysfonctionnement.

## Premier accès

L'application n'a **pas** d'assistant en ligne de commande. Après
l'installation, ouvrez un navigateur sur l'ERP : tant qu'aucune entreprise
n'existe en base, `SetupRequiredMiddleware` affiche le formulaire `/setup/`
qui crée l'entreprise et le compte administrateur. Une fois complété, cette
adresse redirige vers la connexion normale.

## Exploitation courante

### Sauvegardes

Il existe **deux systèmes distincts**, à des emplacements différents et avec
des politiques de purge différentes — c'est la source de confusion la plus
fréquente :

| Système | Emplacement | Purge |
|---|---|---|
| Archives de l'appliance | `/opt/orion/backups` | automatique, `ORION_BACKUP_RETENTION_DAYS` |
| Sauvegardes de l'interface | `backend/storage/backups` | **seulement si planifiées** |

Une sauvegarde lancée à la main, ou un export portable, **n'est jamais purgé
automatiquement**. C'est le principal remplissage silencieux du disque. Les
supprimer depuis l'interface plutôt qu'au niveau du système, afin que la base
reste cohérente.

### Mises à jour

Depuis l'interface (**Super Admin → Mises à jour**) ou en ligne de commande.
Sur l'appliance, `scripts/update_orion.sh` traite l'OS, Docker, Node, Python
puis l'applicatif.

**Ne dépendez pas de l'interface pour vous mettre à jour.** La première
instruction du mécanisme applicatif est une lecture en base
(`SystemUpdateSettings`) : il est donc indisponible exactement quand il
servirait le plus — base injoignable, migration cassée, Django qui ne démarre
pas, ou simplement `update_enabled` à faux. D'où trois modes :

| Commande | Comportement |
|---|---|
| `update_orion.sh` | mécanisme applicatif, repli direct s'il échoue, puis nouvelle tentative pour restaurer la trace d'audit |
| `update_orion.sh --direct` | `git pull`, migrations, statiques et builds **sans Django** — aucune dépendance à la base ni au mécanisme applicatif |
| `update_orion.sh --django-only` | mécanisme applicatif seul, sans repli |

Le mode par défaut conserve ce que l'interface apporte — trace `SystemUpdateRun`,
point de rollback, vérifications post-update. Le mode `--direct` est la voie de
survie : c'est celui à utiliser quand l'ERP est en panne.

Depuis l'hyperviseur, sans session SSH dans la VM :

```bash
qm guest exec <vmid> -- /bin/bash -c '/opt/orion/scripts/update_orion.sh --direct'
```

Après un `git pull` manuel, **redémarrez les services** : gunicorn garde
l'ancien code en mémoire, et une migration non appliquée laisse la base
décalée du modèle.

### Disques

`scripts/orion-disk.sh` donne l'état des volumes, la répartition des données
et l'espace non alloué, et sait étendre le système de fichiers après un
agrandissement du disque virtuel. Voir [DISQUES.md](../deployment/proxmox-appliance/docs/DISQUES.md).

### Domaines et tunnels Cloudflare

Un domaine se raccorde dans **Sites web → Domaines → Ajouter un domaine**. Le
champ **Cible** choisit le service : site vitrine, boutique, portail client,
**Orion ERP**, landing page ou blog. Le champ « Site web relié » ne liste que
les sites du CMS et se masque automatiquement lorsque la cible est l'ERP —
l'ERP n'est pas un site, c'est une cible.

Pour les tunnels, deux modes s'excluent :

| | Mode fichier | Mode jeton |
|---|---|---|
| Configuration | `config.yml` local | dashboard Zero Trust |
| Identifiants | fichier `.json` du tunnel | jeton de connecteur |
| Mise en place | copier le `.json` sur le serveur | bouton de l'interface, ou `orion-cloudflare.sh set-token` |

## Pièges rencontrés en production

Ces symptômes ont tous une cause précise, et chacun a déjà fait perdre du
temps.

**400 Bad Request servi par Django.** Le domaine n'est pas dans
`ALLOWED_HOSTS`. Sur l'appliance, renseignez les domaines dans le `.env` et
redémarrez : les valeurs sont recalculées au démarrage.

**403 CSRF à la soumission du formulaire de connexion.** Le domaine est dans
`ALLOWED_HOSTS` mais absent de `CSRF_TRUSTED_ORIGINS`. Même cause, deux
symptômes successifs.

**530 sur un domaine Cloudflare.** Aucun connecteur n'est connecté : le
service `cloudflared` est arrêté ou en échec.

**502 Bad Gateway sur un domaine Cloudflare.** Le tunnel est connecté mais
n'atteint pas le service. Vérifiez la cible déclarée pour ce hostname — une
adresse IP codée en dur cesse de fonctionner au moindre changement de bail
DHCP. Utilisez `http://localhost:<port>`.

**« Token invalide » sur un jeton Cloudflare pourtant correct.** Cloudflare
distingue les jetons d'**utilisateur** (Mon profil, ~40 caractères) et de
**compte** (Gérer le compte). Seuls les premiers répondent à
`/user/tokens/verify`. L'ERP valide désormais sur ce que le jeton *fait*.
Attention aussi à ne pas confondre un jeton d'**API** avec un jeton de
**connecteur** (Zero Trust, plus de 150 caractères) : ils n'ont pas le même
usage.

**« Une mise à jour est déjà en cours » alors qu'aucune ne tourne.** Verrou
abandonné par un processus tué. Il est désormais repris automatiquement au-delà
de 3 h, et le message indique le chemin du fichier.

**Une page introuvable dans le menu.** Le module n'est pas activé pour
l'entreprise, ou la page n'a aucune entrée de navigation. `reverse()` depuis un
shell Django donne son adresse exacte.

## Conventions du projet

- Les paramètres réels sont dans `erp_btp/settings/base.py` et ses variantes,
  **pas** dans un `erp_btp/settings.py` : le paquet masque ce fichier.
- L'internationalisation des contenus métier passe par des tables sœurs
  `<Modèle>Translation` et une fonction d'overlay, non par `apps.translations`,
  réservé aux chaînes statiques.
- Les secrets stockés en base sont chiffrés avec `ORION_SECRET_ENCRYPTION_KEY`.
  La perdre les rend illisibles.
- Les montants, prix d'achat, marges, coûts internes et coefficients ne doivent
  **jamais** être exposés à un frontend public.
