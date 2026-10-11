#!/usr/bin/env bash
# ============================================================================
# Orion ERP — Gestion des disques de l'appliance
#
# L'appliance tient sur UN seul système de fichiers (/), mais les données y
# sont réparties entre des emplacements aux cycles de vie très différents :
# certains sont purgés automatiquement, d'autres grossissent indéfiniment.
# Ce script donne cette vue détaillée, et sait étendre le système de fichiers
# après un agrandissement du disque virtuel côté Proxmox.
#
# Usage :
#   orion-disk.sh              état des volumes et des emplacements (défaut)
#   orion-disk.sh status       idem
#   orion-disk.sh top [N]      les N plus gros répertoires et fichiers (déf. 15)
#   orion-disk.sh grow         étend partition + système de fichiers
#   orion-disk.sh prune        sauvegardes purgeables (simulation)
#   orion-disk.sh prune --yes  les supprime réellement
#
# Depuis l'hyperviseur Proxmox :
#   qm guest exec <vmid> -- /bin/bash -c '/opt/orion/scripts/orion-disk.sh'
# ============================================================================
set -uo pipefail

ORION_HOME="${ORION_HOME:-/opt/orion}"
BACKEND="$ORION_HOME/backend"
APPLIANCE="${ORION_APPLIANCE:-/opt/orion-appliance}"
RETENTION="${ORION_BACKUP_RETENTION_DAYS:-14}"

titre() { echo ""; echo "=== $* ==="; }
avert() { echo "  [!!] $*"; }
err()   { echo "  [XX] $*" >&2; }

# Taille lisible d'un chemin, "-" s'il n'existe pas. -L suit les liens : media/
# et logs/ du projet Django en sont (voir provisioning/02-deploy-orion.sh).
taille() {
  if [ -e "$1" ]; then
    du -shL "$1" 2>/dev/null | cut -f1
  else
    echo "-"
  fi
}

mo() { awk -v o="$1" 'BEGIN { printf "%.1f Mo", o / 1048576 }'; }

# ─── Inventaire des emplacements ────────────────────────────────────────────
# chemin | contenu | politique de purge
# À tenir à jour avec provisioning/02-deploy-orion.sh (liens symboliques),
# docker/docker-compose.yml (volumes) et apps/backups/services.py (chemins).
emplacements() {
  # Heredoc NON quoté : les chemins suivent $ORION_HOME au lieu d'être figés
  # sur /opt/orion, pour rester cohérent avec les autres commandes et testable
  # sur une arborescence de démonstration.
  cat <<TABLE
$ORION_HOME/docker/mysql|Données MySQL (volume du conteneur orion-db)|aucune : grossit avec vos données
$ORION_HOME/docker/redis|Persistance Redis|aucune : volume faible
$ORION_HOME/uploads|Médias, lien de backend/media : photos, PDF, APK mobiles|AUCUNE : jamais purgé
$BACKEND/storage/backups|Sauvegardes de l'ERP, celles qu'on télécharge|seulement si rattachées à une planification active
$ORION_HOME/backups|Archives nocturnes orion_backup_*.tar.gz|oui : ORION_BACKUP_RETENTION_DAYS
$ORION_HOME/logs|Journaux Django, gunicorn, Celery (lien de backend/logs)|rotation 10 Mo x 10 par fichier
$BACKEND/.venv|Environnement Python|remplacé aux mises à jour
$BACKEND/staticfiles|Fichiers statiques collectés|écrasé à chaque collectstatic
$BACKEND/frontend|Sources et node_modules des frontends|réinstallé aux mises à jour
$ORION_HOME/siecle|Build React SIÈCLE, servi par serve sur 5173|écrasé à chaque build
$ORION_HOME/lunea|Build React LUNEA, servi par serve sur 5174|écrasé à chaque build
$ORION_HOME/neostructura|Build React NÉOSTRUCTURA, servi par Nginx|écrasé à chaque build
$APPLIANCE|Payload de provisioning du premier démarrage|aucune : supprimable après installation
TABLE
}

# Racine : périphérique, type, disque parent, numéro de partition.
racine_src()    { findmnt -n -o SOURCE / 2>/dev/null | cut -d'[' -f1; }
racine_fstype() { findmnt -n -o FSTYPE / 2>/dev/null; }

cmd_status() {
  titre "Systèmes de fichiers"
  df -h -x tmpfs -x devtmpfs -x overlay -x squashfs 2>/dev/null | awk 'NR==1 || /^\/dev/'

  titre "Disques et partitions"
  if command -v lsblk >/dev/null 2>&1; then
    lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT 2>/dev/null | grep -v loop
  else
    avert "lsblk indisponible"
  fi

  titre "Espace non alloué (après un qm resize côté Proxmox)"
  local src disque octets_disque octets_parts ecart
  src="$(racine_src)"
  disque="$(lsblk -no pkname "$src" 2>/dev/null | head -1)"
  if [ -n "$disque" ]; then
    octets_disque="$(lsblk -bdno SIZE "/dev/$disque" 2>/dev/null | head -1)"

    # Somme de TOUTES les partitions du disque, pas seulement la racine :
    # les images cloud Ubuntu en portent d'autres (/boot, /boot/efi, BIOS
    # boot), ~1 Go au total. Ne comparer qu'à la racine faisait annoncer
    # 1 Go « non alloué » alors que growpart répondait NOCHANGE.
    octets_parts="$(lsblk -bnr -o SIZE,TYPE "/dev/$disque" 2>/dev/null \
      | awk '$2 == "part" { total += $1 } END { print total + 0 }')"

    echo "  disque /dev/$disque : $(mo "$octets_disque")"
    echo "  somme des partitions : $(mo "$octets_parts")"
    ecart=$(( (octets_disque - octets_parts) / 1048576 ))
    if [ "$ecart" -gt 512 ]; then
      avert "$ecart Mo non alloués — récupérez-les avec : $0 grow"
    else
      echo "  disque entièrement alloué ($ecart Mo de reste), rien à récupérer"
    fi
  else
    avert "racine non identifiée (LVM ou montage inhabituel) : à vérifier à la main"
  fi

  titre "Où vont les données"
  printf '  %-40s %9s  %s\n' "EMPLACEMENT" "TAILLE" "PURGE"
  local chemin desc purge
  while IFS='|' read -r chemin desc purge; do
    [ -n "$chemin" ] || continue
    printf '  %-40s %9s  %s\n' "$chemin" "$(taille "$chemin")" "$purge"
    printf '  %-40s %9s  %s\n' "" "" "-> $desc"
  done < <(emplacements)
}

cmd_top() {
  local n="${1:-15}"

  titre "Les $n plus gros répertoires sous $ORION_HOME"
  du -hL --max-depth=3 "$ORION_HOME" 2>/dev/null | sort -rh | head -n "$n"

  titre "Les $n plus gros fichiers sous $ORION_HOME"
  find -L "$ORION_HOME" -type f -size +1M 2>/dev/null -printf '%s\t%p\n' \
    | sort -rn | head -n "$n" \
    | awk -F'\t' '{ printf "  %9.1f Mo  %s\n", $1 / 1048576, $2 }'
}

cmd_grow() {
  if [ "$(id -u)" -ne 0 ]; then
    err "À lancer en root (sudo)."
    exit 1
  fi

  local src fstype disque numero
  src="$(racine_src)"
  fstype="$(racine_fstype)"
  disque="$(lsblk -no pkname "$src" 2>/dev/null | head -1)"
  numero="${src##*[!0-9]}"

  if [ -z "$disque" ] || [ -z "$numero" ]; then
    err "Impossible de déduire disque et partition depuis « $src »."
    err "Cas LVM ou partitionnement inhabituel : intervenir à la main."
    exit 1
  fi

  titre "Extension de $src ($fstype) sur /dev/$disque"
  echo "  avant : $(df -h / | awk 'NR==2 { print $2" total, "$4" libres" }')"

  if ! command -v growpart >/dev/null 2>&1; then
    err "growpart absent. Installez-le : apt-get install -y cloud-guest-utils"
    exit 1
  fi

  # growpart est idempotent : il sort en NOCHANGE quand il n'y a rien à
  # récupérer, ce qui n'est pas une erreur.
  growpart "/dev/$disque" "$numero" || avert "growpart : rien à étendre"

  case "$fstype" in
    ext2|ext3|ext4) resize2fs "$src" ;;
    xfs)            xfs_growfs / ;;
    btrfs)          btrfs filesystem resize max / ;;
    *)              err "Système de fichiers « $fstype » non géré ici."; exit 1 ;;
  esac

  echo "  après : $(df -h / | awk 'NR==2 { print $2" total, "$4" libres" }')"
}

cmd_prune() {
  local confirme=0
  if [ "${1:-}" = "--yes" ]; then
    confirme=1
  fi

  titre "Archives nocturnes de plus de $RETENTION jours"
  local vieilles
  vieilles="$(find "$ORION_HOME/backups" -maxdepth 1 -name 'orion_backup_*.tar.gz' -mtime "+$RETENTION" 2>/dev/null)"
  if [ -z "$vieilles" ]; then
    echo "  aucune"
  else
    echo "$vieilles" | while read -r f; do
      [ -n "$f" ] && echo "  $(mo "$(stat -c%s "$f")")  $f"
    done
    if [ "$confirme" -eq 1 ]; then
      echo "$vieilles" | xargs -r rm -f
      echo "  supprimées."
    else
      avert "simulation : relancez avec --yes pour supprimer"
    fi
  fi

  titre "Sauvegardes de l'ERP (storage/backups)"
  local dir="$BACKEND/storage/backups"
  if [ ! -d "$dir" ]; then
    echo "  répertoire absent"
    return
  fi
  echo "  total occupé : $(taille "$dir")"
  find "$dir" -type f -printf '%s\t%TY-%Tm-%Td\t%p\n' 2>/dev/null \
    | sort -rn | head -10 \
    | awk -F'\t' '{ printf "  %9.1f Mo  %s  %s\n", $1 / 1048576, $2, $3 }'
  echo ""
  avert "Ces fichiers ne sont PAS purgés automatiquement, sauf s'ils sont"
  avert "rattachés à une planification active (cleanup_old_backups)."
  avert "Supprimez-les depuis l'ERP (menu Sauvegardes) plutôt qu'ici : effacer"
  avert "les fichiers laisserait des BackupJob pointant vers le vide."
}

case "${1:-status}" in
  status|'') cmd_status ;;
  top)       cmd_top "${2:-15}" ;;
  grow)      cmd_grow ;;
  prune)     cmd_prune "${2:-}" ;;
  -h|--help) sed -n '2,21p' "$0" ;;
  *)         err "Commande inconnue : $1"; sed -n '11,19p' "$0"; exit 2 ;;
esac
