# Changelog — Appliance Proxmox Orion ERP

## 2026.10.10

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
