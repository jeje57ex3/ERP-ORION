# Changelog — Appliance Proxmox Orion ERP

## 2026.10.14

Révision de la chaîne d'installation, après cinq pannes de provisioning sans
symptôme commun — 502 Bad Gateway, erreur 500 sur toutes les pages, exit 127
muet, « command not found » sur un script présent, assistant IA en 404. Leur
point commun n'était pas la cause mais la **distance** entre la cause et le
symptôme : jusqu'à trois étapes, et jamais un message désignant la vraie
origine. Les corrections portent donc sur les causes communes, et sur la
constatation des pannes là où elles surviennent.

- **Le `.env` n'est plus exécuté.** Il était lu par `set -a; . .env`, c'est-à-dire
  *sourcé* — une seule valeur à espaces non citée
  (`ORION_UPDATE_CELERY_RESTART_COMMAND=sudo -n systemctl …`) faisait lire
  « VAR=sudo » au shell, qui exécutait ensuite la commande « -n » : exit 127 sur
  un message ne nommant ni la clé ni le fichier, et tout le provisioning d'une
  VM neuve s'arrêtait là. `charger_env` (nouveau `provisioning/lib/commun.sh`)
  parse le fichier sans jamais interpréter une valeur. Les sept scripts
  concernés ont été convertis, dont `backup.sh` — lancé par cron à 2 h, il
  arrêtait les sauvegardes en silence.
- **Toutes les valeurs du `.env` généré sont citées**, y compris celles qui n'en
  ont pas besoin : une règle uniforme se vérifie, une exception se perd. Vérifié
  que les trois lecteurs (python-decouple, `EnvironmentFile` de systemd,
  `charger_env`) rendent la même chaîne. Le fichier est désormais **validé à
  l'écriture** par ses deux lecteurs réels, au lieu de révéler son défaut
  plusieurs étapes plus loin.
- **`$HOME` est garanti.** `qm guest exec` — seul accès à une appliance sans clé
  SSH — n'en définit aucun, et cloud-init ne le garantit pas. git refuse alors sa
  configuration, la CLI Ollama panique (« panic: $HOME is not defined »), npm
  écrit dans `/.npm`. Posé une fois pour toutes dans `commun.sh`, avec
  l'autorisation `safe.directory` qui rend les dépôts d'`orion` lisibles par
  root (le provisioning clone en root puis `chown`).
- **Nouvelle étape finale : `scripts/orion-verifier.sh`**, relançable à tout
  moment. Elle contrôle ce qu'un navigateur constate — les pages répondent-elles
  ? — et non ce que les scripts croient avoir fait : services, ports, schéma,
  présence de `staticfiles.json`, réponses HTTP (dont `/setup/` et la sonde HA
  sous son vrai nom d'hôte), modèle IA téléchargé, dépôt git lisible. C'est le
  seul contrôle qui aurait attrapé le 502 **et** le 500 : les deux fois, le
  provisioning s'était déclaré « Terminé ».
- **L'ordre des étapes est devenu du code** (`provisioning/00-provisionner.sh`).
  Il vivait dans le gabarit cloud-init, où le fait que 07 doive précéder 03
  n'était qu'un commentaire YAML — alors que l'inverser laisse les services sans
  leurs `ExecStartPre`, donc morts, donc nginx en 502. L'orchestrateur pose aussi
  les bits d'exécution (git conserve le mode : un script en 100644 échoue en
  « command not found »), continue malgré l'échec d'une étape, et écrit dans
  `/etc/motd` l'état réel de l'installation. cloud-init n'annonce plus
  « prête » sans l'avoir vérifié.
- `03-systemd-units.sh` vérifie `staticfiles.json` : son absence met **toutes**
  les pages en 500 (stockage à manifeste) alors que la cause — un
  `collectstatic` manqué — était deux étapes plus haut.
- `refresh_allowed_hosts.sh` ne peut plus empêcher un démarrage : lecture par
  `valeur_env` (une clé absente tuait le script, donc les deux services, donc
  502) et l'IP de la VM n'est plus une condition — sans route par défaut au
  boot, les domaines n'étaient pas réécrits du tout.
- `update_orion.sh` se vérifie lui-même à la fin, et propage `commun.sh`.
  `lib/20-build-cloud-init-seed.sh` refuse de construire une image dont le
  payload serait incomplet.
- Tests : `deployment/proxmox-appliance/tests/test_commun.sh` (23 contrôles,
  rejouant les pannes réelles) et `tests/test_installation_appliance.py`
  (20 invariants).

## 2026.10.10

- Activation de Cloudflare Tunnel après l'installation :
  `scripts/orion-cloudflare.sh` (état, pose du token, désactivation). La
  procédure documentée jusqu'ici passait par `ssh orion@<ip>`, impossible
  sans clé SSH fournie au déploiement, et plaçait le token en argument de
  commande — donc dans l'historique du shell et la liste des processus. Le
  script le lit sur l'entrée standard, valide sa longueur, et vérifie que la
  connexion au réseau Cloudflare est bien établie au lieu de s'arrêter à
  « service installé ».
- `orion-disk.sh` : correction du calcul de l'espace non alloué, qui ne
  comparait la taille du disque qu'à la partition racine. Les images cloud
  Ubuntu en portent d'autres (`/boot`, `/boot/efi`, BIOS boot, ~1 Go), d'où
  un faux « 1025 Mo non alloués » alors que `growpart` répondait `NOCHANGE`.
  La somme de toutes les partitions est désormais prise en compte.
- `update_orion.sh` : repli automatique si `run_system_update` échoue (git pull
  + migrate + collectstatic directs, puis nouvelle tentative du mécanisme
  normal). Sans ce repli, un bug dans la mise à jour était irrécupérable :
  `run_system_update` est seul à déclencher le `git pull`, donc son propre
  correctif ne pouvait jamais arriver et il fallait intervenir à la main
  depuis l'hyperviseur.
- Gestion des disques : nouveau `scripts/orion-disk.sh` (état des volumes et
  de chaque emplacement de données, classement des plus gros consommateurs,
  extension partition + système de fichiers après un `qm resize`, revue des
  sauvegardes purgeables) et [DISQUES.md](DISQUES.md). Rien n'outillait ce
  sujet : `growpart` ne tourne qu'au premier démarrage, donc un `qm resize`
  ultérieur laissait l'espace ajouté inutilisable sans intervention manuelle.
- Documenté au passage un piège réel : les sauvegardes de l'ERP vivent dans
  `backend/storage/backups` et non dans `/opt/orion/backups`, et
  `cleanup_old_backups()` ne purge que celles rattachées à une planification
  active — une sauvegarde manuelle ou un export portable n'est donc jamais
  supprimé automatiquement.
- Site NÉOSTRUCTURA pris en charge par l'appliance : il n'y figurait nulle
  part (aucune unit, aucun vhost, aucune option de domaine) et n'avait donc
  jamais de mode de service en production — il ne tournait qu'en serveur de
  développement Vite. Nouvelle option `--ns-domain` propagée de `deploy.sh`
  jusqu'à `deploy-info.env`, build au provisioning, vhost Nginx, ingress du
  tunnel et reconstruction dans `update_orion.sh`.
- Contrairement aux boutiques SIÈCLE/LUNEA, ce site n'a **pas** de service
  dédié : Nginx sert son build statique et proxifie `/api` et `/media` vers
  Django. Son client API appelle des chemins relatifs (en développement c'est
  le proxy Vite qui les redirige), le SPA et l'API doivent donc partager la
  même origine — ce qu'un serveur de fichiers statiques ne sait pas faire.
  Conséquence : dans le tunnel, ce domaine vise Nginx (port 80) et non un
  port applicatif direct.
- Son build n'est pas conditionné à `--login-domain`, à la différence des
  boutiques : aucune URL d'API n'est à injecter à la compilation.
- `frontend/neostructura-site` : sortie du build déplacée de
  `static/neostructura-site` vers `dist/`. Le premier est dans
  `STATICFILES_DIRS`, le build passait donc dans `collectstatic` et son
  `ManifestStaticFilesStorage`, qui échoue dès qu'un asset référence une
  ressource non résolvable.
- Documentation : le README décrivait un « assistant console (Stage B) » sur
  `tty1` qui n'existe pas — remplacé par le formulaire web `/setup/`
  (`apps/core/setup_views.py`). L'exemple non-interactif de PROXMOX.md
  passait `--start`, une option que `deploy.sh` rejette (son parser sort en
  erreur sur toute option inconnue) ; la VM démarre par défaut et
  `--as-template` fait l'inverse.

## 2026.10.09

- Migration des données vers l'appliance : `scripts/export_orion_data.ps1`
  (poste Windows → archive horodatée base + médias + manifeste, empreinte
  SHA-256) et `scripts/install_orion_data.sh` (VM → vérification d'empreinte,
  sauvegarde de sécurité, restauration, fusion des médias, `migrate` +
  `collectstatic`, redémarrage des services). L'appliance démarrait jusqu'ici
  avec une base vide, sans chemin outillé pour y porter des données
  existantes. Documenté dans [DATA-MIGRATION.md](DATA-MIGRATION.md).
- Les builds mobiles (`.apk`/`.aab`, ~1 Go d'artefacts reconstructibles) sont
  exclus de l'export par défaut (`-IncludeMobileBuilds` pour les inclure).

## 2026.08.06

- `deploy_proxmox_vm.sh` : ajout d'un assistant interactif (choix du disque/
  stockage d'installation via menu détecté par `pvesm`, taille du disque
  virtuel personnalisable, bridge réseau, IP statique ou DHCP, clé SSH avec
  détection des `~/.ssh/*.pub`, choix démarrer/laisser arrêtée/template,
  récapitulatif avant confirmation). Actif par défaut sans option sur un
  terminal interactif ; mode non-interactif (flags) inchangé pour
  l'automatisation/CI.
- `import_proxmox.sh` : nouvelles options `--disk-size`, `--ip`/`--gateway`/
  `--dns` (IP statique), `--list-storage`, `--list-bridges`.

## 2026.08.05

- Première version : pipeline de build complet (Ubuntu 24.04 cloud image +
  cloud-init NoCloud, sans Packer) produisant `OrionERP.qcow2`, `OrionERP.ova`,
  `OrionERP.manifest`, `checksum.sha256`.
- Topologie native systemd reproduisant la production réelle : 4 services
  applicatifs (`orion-backend` 9000, `orion-frontend` 5172, `siecle-frontend`
  5173, `lunea-frontend` 5174) + MySQL/Redis en Docker (`orion-db-stack`).
- Premier démarrage en deux étapes : provisioning automatique (cloud-init)
  puis assistant interactif sur la console (tty1).
- Supervision `orion-health.timer` (60s), sauvegardes quotidiennes (2h),
  scripts `update_orion.sh` / `cleanup.sh`, tableau de bord terminal.
- Pare-feu UFW + fail2ban, Cloudflare Tunnel (activation par token au premier
  démarrage), Nginx + Certbot pour l'accès direct.
- `import_proxmox.sh` : automatise `qm create/importdisk/set/resize` et le
  cloud-init personnalisé Proxmox (`--cicustom`).
