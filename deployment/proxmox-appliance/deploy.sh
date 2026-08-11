#!/usr/bin/env bash
# Orion ERP — Déploiement Proxmox 100% automatique (avec assistant interactif).
#
# À exécuter DIRECTEMENT sur le host Proxmox (Shell du nœud dans l'UI, ou SSH
# root@proxmox). Proxmox VE fournit déjà qemu-img/qm/pvesh/pvesm nativement —
# aucune installation manuelle requise. Enchaîne : build de l'image (si besoin)
# + choix du stockage/disque/réseau + import + démarrage de la VM.
#
# Usage :
#   ./deploy.sh                    Lance l'assistant interactif (recommandé)
#   ./deploy.sh [VERSION] [options]  Mode non-interactif (automatisation/CI)
#
# Options du mode non-interactif (toutes optionnelles — valeurs auto-détectées sinon) :
#   --vmid ID              ID de VM (def: prochain ID libre — pvesh get /cluster/nextid)
#   --name NAME             Nom de la VM (def: OrionERP)
#   --storage STORAGE       Stockage du disque d'installation (def: 1er stockage "images")
#   --disk-size SIZE        Taille du disque virtuel, ex: 80G, 120G, 500G (def: 80G)
#   --snippets-storage S    Stockage pour le cloud-init personnalisé (def: idem, sinon "local")
#   --bridge BRIDGE         Bridge réseau (def: 1er vmbr* détecté, sinon vmbr0)
#   --ip IP/CIDR            IP statique (ex: 192.168.1.50/24) — def: DHCP
#   --gateway IP             Passerelle (requis si --ip fourni)
#   --dns IP                 Serveur DNS (def: identique à --gateway)
#   --memory MB              RAM en Mo (def: 8192)
#   --cores N                vCPU (def: 4)
#   --sshkey PATH             Clé publique SSH à injecter (def: aucune)
#   --login-domain DOMAIN     Domaine ERP/admin (ex: login.exemple.fr) — def: aucun (accès par IP)
#   --orion-domain DOMAIN     Domaine vitrine (ex: orion.exemple.fr) — def: aucun
#   --siecle-domain DOMAIN    Domaine boutique SIÈCLE — def: aucun
#   --lunea-domain DOMAIN     Domaine boutique LUNEA — def: aucun
#   --cf-token TOKEN          Token Cloudflare Tunnel — def: aucun (tunnel désactivé)
#   --as-template             Convertit la VM en template après import (pas de démarrage)
#   --rebuild                 Reconstruit l'image même si build/OrionERP.qcow2 existe déjà
#   --skip-build               Réutilise le build/ existant sans reconstruire (échoue s'il est absent)
#   -i, --interactive           Force l'assistant interactif même avec des options fournies
#   -h, --help                  Affiche cette aide

set -euo pipefail

VERSION=""
VMID=""
VM_NAME="OrionERP"
STORAGE=""
DISK_SIZE="80G"
SNIPPETS_STORAGE=""
BRIDGE=""
STATIC_IP=""
GATEWAY=""
DNS=""
MEMORY=8192
CORES=4
SSHKEY=""
LOGIN_DOMAIN=""
ORION_DOMAIN=""
SIECLE_DOMAIN=""
LUNEA_DOMAIN=""
CF_TOKEN=""
AS_TEMPLATE=0
START_VM=1
REBUILD=0
SKIP_BUILD=0
FORCE_INTERACTIVE=0

usage() { sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'; }

# Le premier argument positionnel (s'il ne commence pas par --) est la VERSION.
if [ $# -gt 0 ] && [[ "$1" != --* ]] && [ "$1" != "-h" ] && [ "$1" != "-i" ]; then
  VERSION="$1"; shift
fi

while [ $# -gt 0 ]; do
  case "$1" in
    --vmid) VMID="$2"; shift 2 ;;
    --name) VM_NAME="$2"; shift 2 ;;
    --storage) STORAGE="$2"; shift 2 ;;
    --disk-size) DISK_SIZE="$2"; shift 2 ;;
    --snippets-storage) SNIPPETS_STORAGE="$2"; shift 2 ;;
    --bridge) BRIDGE="$2"; shift 2 ;;
    --ip) STATIC_IP="$2"; shift 2 ;;
    --gateway) GATEWAY="$2"; shift 2 ;;
    --dns) DNS="$2"; shift 2 ;;
    --memory) MEMORY="$2"; shift 2 ;;
    --cores) CORES="$2"; shift 2 ;;
    --sshkey) SSHKEY="$2"; shift 2 ;;
    --login-domain) LOGIN_DOMAIN="$2"; shift 2 ;;
    --orion-domain) ORION_DOMAIN="$2"; shift 2 ;;
    --siecle-domain) SIECLE_DOMAIN="$2"; shift 2 ;;
    --lunea-domain) LUNEA_DOMAIN="$2"; shift 2 ;;
    --cf-token) CF_TOKEN="$2"; shift 2 ;;
    --as-template) AS_TEMPLATE=1; START_VM=0; shift ;;
    --rebuild) REBUILD=1; shift ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    -i|--interactive) FORCE_INTERACTIVE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Option inconnue : $1" >&2; usage; exit 1 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="$ROOT_DIR/build"

# Interactif par défaut si aucune option n'a été passée et qu'un terminal est attaché.
NO_ARGS_GIVEN=$([ -z "$VMID$STORAGE$SNIPPETS_STORAGE$BRIDGE$STATIC_IP" ] && [ "$REBUILD" -eq 0 ] && [ "$SKIP_BUILD" -eq 0 ] && echo 1 || echo 0)
INTERACTIVE=0
if [ "$FORCE_INTERACTIVE" -eq 1 ]; then INTERACTIVE=1
elif [ "$NO_ARGS_GIVEN" -eq 1 ] && [ -t 0 ]; then INTERACTIVE=1
fi

command -v qm >/dev/null 2>&1 || {
  echo "ERREUR: commande 'qm' introuvable — ce script doit s'exécuter sur un host Proxmox VE." >&2
  exit 1
}

# ═══════════════════════════════════════════════════════════════════════════
# Assistant interactif
# ═══════════════════════════════════════════════════════════════════════════

ask() {
  local prompt="$1" default="${2:-}" var
  if [ -n "$default" ]; then
    read -r -p "$prompt [$default] : " var
    echo "${var:-$default}"
  else
    while true; do
      read -r -p "$prompt : " var
      [ -n "$var" ] && { echo "$var"; return; }
      echo "  -> requis." >&2
    done
  fi
}

ask_yesno() {
  local prompt="$1" default="${2:-n}" var
  read -r -p "$prompt [$([ "$default" = o ] && echo O/n || echo o/N)] : " var
  var="${var:-$default}"
  [[ "$var" =~ ^[oOyY] ]]
}

# Comme ask(), mais un champ vide est accepté tel quel (pas de boucle "requis").
ask_optional() {
  local prompt="$1" default="${2:-}" var
  read -r -p "$prompt${default:+ [$default]} (laisser vide pour ignorer) : " var
  echo "${var:-$default}"
}

ask_secret() {
  local prompt="$1" var
  read -r -s -p "$prompt (laisser vide pour ignorer) : " var; echo
  echo "$var"
}

# choose_from_list PROMPT DEFAULT_INDEX item1 item2 ... -> imprime l'item choisi sur stdout
choose_from_list() {
  local prompt="$1" default_idx="$2"; shift 2
  local items=("$@") i choice
  {
    echo "$prompt"
    for i in "${!items[@]}"; do printf '  %d) %s\n' "$((i + 1))" "${items[$i]}"; done
  } >&2
  read -r -p "Choix [$default_idx] : " choice
  choice="${choice:-$default_idx}"
  if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt "${#items[@]}" ]; then
    echo "  -> choix invalide, valeur par défaut retenue." >&2
    choice="$default_idx"
  fi
  echo "${items[$((choice - 1))]}"
}

run_wizard() {
  echo "======================================================"
  echo " Orion ERP — Assistant de déploiement Proxmox"
  echo "======================================================"
  echo ""

  # ── Version / build ─────────────────────────────────────────────────────
  VERSION="$(ask 'Version du build' "${VERSION:-$(date -u +%Y.%m.%d)}")"
  if [ -f "$BUILD_DIR/OrionERP.qcow2" ]; then
    if ask_yesno "Un build existe déjà (build/OrionERP.qcow2) — reconstruire ?" n; then
      REBUILD=1
    else
      SKIP_BUILD=1
    fi
  fi

  # ── Identité de la VM ────────────────────────────────────────────────────
  echo ""
  echo "--- Identité de la VM ---"
  VM_NAME="$(ask 'Nom de la VM' "$VM_NAME")"
  local suggested_vmid
  suggested_vmid="$(pvesh get /cluster/nextid 2>/dev/null | tr -d '[:space:]' || true)"
  suggested_vmid="${suggested_vmid:-9000}"
  VMID="$(ask 'ID de la VM (VMID)' "$suggested_vmid")"

  # ── Disque d'installation ────────────────────────────────────────────────
  echo ""
  echo "--- Disque d'installation ---"
  local storages=() line name
  while IFS= read -r line; do
    name="$(awk '{print $1}' <<<"$line")"
    [ -n "$name" ] && [ "$name" != "Name" ] && storages+=("$name")
  done < <(pvesm status --content images 2>/dev/null | tail -n +2)
  if [ "${#storages[@]}" -eq 0 ]; then
    echo "  Aucun stockage 'images' détecté automatiquement." >&2
    STORAGE="$(ask 'Nom du stockage disque' 'local-lvm')"
  else
    STORAGE="$(choose_from_list 'Sur quel stockage installer le disque de la VM ?' 1 "${storages[@]}")"
  fi
  echo "  -> Stockage retenu : $STORAGE"

  DISK_SIZE="$(ask 'Taille du disque virtuel (ex: 80G, 120G, 500G)' "$DISK_SIZE")"
  while ! [[ "$DISK_SIZE" =~ ^[0-9]+[GgTt]$ ]]; do
    echo "  -> format invalide (attendu: nombre + G ou T, ex: 80G)." >&2
    DISK_SIZE="$(ask 'Taille du disque virtuel' '80G')"
  done

  # ── Stockage snippets (cloud-init) ──────────────────────────────────────
  local snip_storages=()
  while IFS= read -r line; do
    name="$(awk '{print $1}' <<<"$line")"
    [ -n "$name" ] && [ "$name" != "Name" ] && snip_storages+=("$name")
  done < <(pvesm status --content snippets 2>/dev/null | tail -n +2)
  if [ "${#snip_storages[@]}" -eq 0 ]; then
    echo "  Aucun stockage 'snippets' détecté — 'local' sera utilisé (voir PROXMOX.md pour l'activer)." >&2
    SNIPPETS_STORAGE="local"
  else
    SNIPPETS_STORAGE="$(choose_from_list 'Stockage pour le cloud-init personnalisé (snippets) ?' 1 "${snip_storages[@]}")"
  fi

  # ── Réseau ───────────────────────────────────────────────────────────────
  echo ""
  echo "--- Réseau ---"
  local bridges=()
  while IFS= read -r line; do
    [ -n "$line" ] && bridges+=("$line")
  done < <(ip -o link show type bridge 2>/dev/null | awk -F': ' '{print $2}' | sed 's/@.*//')
  if [ "${#bridges[@]}" -eq 0 ]; then
    BRIDGE="$(ask 'Bridge réseau' 'vmbr0')"
  else
    BRIDGE="$(choose_from_list 'Quel bridge réseau utiliser ?' 1 "${bridges[@]}")"
  fi

  if ask_yesno 'Configurer une adresse IP statique (sinon DHCP) ?' n; then
    STATIC_IP="$(ask 'Adresse IP + masque (ex: 192.168.1.50/24)')"
    GATEWAY="$(ask 'Passerelle (gateway)')"
    DNS="$(ask 'Serveur DNS' "$GATEWAY")"
  fi

  # ── Ressources ───────────────────────────────────────────────────────────
  echo ""
  echo "--- Ressources ---"
  MEMORY="$(ask 'RAM en Mo' "$MEMORY")"
  CORES="$(ask 'Nombre de vCPU' "$CORES")"

  # ── Clé SSH ──────────────────────────────────────────────────────────────
  echo ""
  echo "--- Accès SSH ---"
  local ssh_keys=() f
  for f in "$HOME"/.ssh/*.pub; do [ -f "$f" ] && ssh_keys+=("$f"); done
  if [ "${#ssh_keys[@]}" -gt 0 ]; then
    ssh_keys+=("(aucune / saisir un chemin)")
    local picked
    picked="$(choose_from_list 'Clé publique SSH à injecter ?' 1 "${ssh_keys[@]}")"
    if [ "$picked" != "(aucune / saisir un chemin)" ]; then SSHKEY="$picked"; fi
  fi
  if [ -z "$SSHKEY" ] && ask_yesno 'Indiquer un chemin de clé publique SSH manuellement ?' n; then
    SSHKEY="$(ask 'Chemin de la clé publique (.pub)')"
  fi

  # ── Domaines & Cloudflare ────────────────────────────────────────────────
  # Récupérés ici (shell fiable du host Proxmox) plutôt que par un wizard
  # interactif sur la console série de la VM — Stage A configure nginx et
  # démarre les services avec les vrais domaines dès le premier boot, sans
  # étape bloquante côté VM. Seule la création du compte administrateur se
  # fait ensuite, via le navigateur (assistant web /setup/).
  echo ""
  echo "--- Domaines & Cloudflare (optionnel — laisser vide pour accès par IP) ---"
  LOGIN_DOMAIN="$(ask_optional "Domaine Login (ERP / admin)" "$LOGIN_DOMAIN")"
  ORION_DOMAIN="$(ask_optional "Domaine Orion (vitrine)" "$ORION_DOMAIN")"
  SIECLE_DOMAIN="$(ask_optional "Domaine SIÈCLE" "$SIECLE_DOMAIN")"
  LUNEA_DOMAIN="$(ask_optional "Domaine LUNEA" "$LUNEA_DOMAIN")"
  CF_TOKEN="$(ask_secret "Cloudflare Tunnel Token")"

  # ── Comportement final ───────────────────────────────────────────────────
  echo ""
  echo "--- Finalisation ---"
  local final_choice
  final_choice="$(choose_from_list 'Que faire une fois la VM importée ?' 1 \
    'Démarrer la VM immédiatement' 'Créer la VM sans la démarrer' 'Convertir en template Proxmox')"
  case "$final_choice" in
    'Démarrer la VM immédiatement') START_VM=1; AS_TEMPLATE=0 ;;
    'Créer la VM sans la démarrer') START_VM=0; AS_TEMPLATE=0 ;;
    'Convertir en template Proxmox') START_VM=0; AS_TEMPLATE=1 ;;
  esac

  # ── Récapitulatif ────────────────────────────────────────────────────────
  echo ""
  echo "======================================================"
  echo " Récapitulatif"
  echo "======================================================"
  local build_note=""
  [ "$REBUILD" -eq 1 ] && build_note="(reconstruction)"
  [ "$SKIP_BUILD" -eq 1 ] && build_note="(build existant réutilisé)"
  echo " Version build      : $VERSION $build_note"
  echo " VM                 : $VM_NAME (VMID $VMID)"
  echo " Disque              : $STORAGE — $DISK_SIZE"
  echo " Snippets            : $SNIPPETS_STORAGE"
  echo " Réseau              : $BRIDGE — $([ -n "$STATIC_IP" ] && echo "IP statique $STATIC_IP (gw $GATEWAY, dns $DNS)" || echo "DHCP")"
  echo " Ressources          : ${MEMORY} Mo RAM / ${CORES} vCPU"
  echo " Clé SSH             : ${SSHKEY:-aucune}"
  echo " Domaines            : $([ -n "$LOGIN_DOMAIN$ORION_DOMAIN$SIECLE_DOMAIN$LUNEA_DOMAIN" ] && echo "login=${LOGIN_DOMAIN:-—} orion=${ORION_DOMAIN:-—} siecle=${SIECLE_DOMAIN:-—} lunea=${LUNEA_DOMAIN:-—}" || echo "aucun (accès par IP)")"
  echo " Cloudflare Tunnel   : $([ -n "$CF_TOKEN" ] && echo "token fourni" || echo "non configuré")"
  echo " Action finale       : $final_choice"
  echo "======================================================"
  if ! ask_yesno 'Confirmer et lancer le déploiement ?' o; then
    echo "Annulé."
    exit 1
  fi
}

if [ "$INTERACTIVE" -eq 1 ]; then
  run_wizard
fi

VERSION="${VERSION:-$(date -u +%Y.%m.%d)}"

echo ""
echo "======================================================"
echo " Orion ERP — Déploiement automatique Proxmox"
echo "======================================================"

# ─── Étape 1 — Build de l'image (Proxmox fournit déjà qemu-img) ───────────
if [ "$SKIP_BUILD" -eq 1 ]; then
  echo "[1/3] --skip-build : réutilisation de $BUILD_DIR tel quel."
  [ -f "$BUILD_DIR/OrionERP.qcow2" ] || { echo "ERREUR: $BUILD_DIR/OrionERP.qcow2 introuvable." >&2; exit 1; }
elif [ "$REBUILD" -eq 0 ] && [ -f "$BUILD_DIR/OrionERP.qcow2" ]; then
  echo "[1/3] Image déjà construite ($BUILD_DIR/OrionERP.qcow2) — réutilisation."
  echo "      (utiliser --rebuild pour forcer une reconstruction)"
else
  echo "[1/3] Construction de l'image (version $VERSION)..."
  DISK_SIZE="$DISK_SIZE" "$SCRIPT_DIR/build.sh" "$VERSION"
fi

# ─── Étape 2 — Détection automatique des paramètres restants ──────────────
echo ""
echo "[2/3] Finalisation des paramètres Proxmox..."

if [ -z "$VMID" ]; then
  VMID="$(pvesh get /cluster/nextid 2>/dev/null | tr -d '[:space:]' || true)"
  VMID="${VMID:-9000}"
fi
if [ -z "$STORAGE" ]; then
  STORAGE="$(pvesm status --content images 2>/dev/null | awk 'NR==2{print $1}' || true)"
  STORAGE="${STORAGE:-local-lvm}"
fi
if [ -z "$SNIPPETS_STORAGE" ]; then
  SNIPPETS_STORAGE="$(pvesm status --content snippets 2>/dev/null | awk 'NR==2{print $1}' || true)"
  SNIPPETS_STORAGE="${SNIPPETS_STORAGE:-local}"
fi
if [ -z "$BRIDGE" ]; then
  BRIDGE="$(ip -o link show type bridge 2>/dev/null | awk -F': ' '{print $2}' | sed 's/@.*//' | grep '^vmbr' | head -1 || true)"
  BRIDGE="${BRIDGE:-vmbr0}"
fi

echo "  VMID               : $VMID"
echo "  Nom                : $VM_NAME"
echo "  Stockage disque    : $STORAGE ($DISK_SIZE)"
echo "  Stockage snippets  : $SNIPPETS_STORAGE"
echo "  Bridge             : $BRIDGE"
echo "  RAM / vCPU         : ${MEMORY}Mo / ${CORES}"
echo "  Réseau              : $([ -n "$STATIC_IP" ] && echo "statique $STATIC_IP" || echo "DHCP")"

# ─── Étape 3 — Import + démarrage ──────────────────────────────────────────
echo ""
echo "[3/3] Création de la VM..."

IMPORT_ARGS=(
  --vmid "$VMID" --name "$VM_NAME" --storage "$STORAGE" --disk-size "$DISK_SIZE"
  --snippets-storage "$SNIPPETS_STORAGE" --bridge "$BRIDGE"
  --memory "$MEMORY" --cores "$CORES"
  --disk "$BUILD_DIR/OrionERP.qcow2"
)
[ -n "$SSHKEY" ] && IMPORT_ARGS+=(--sshkey "$SSHKEY")
if [ -n "$STATIC_IP" ]; then
  IMPORT_ARGS+=(--ip "$STATIC_IP" --gateway "$GATEWAY")
  [ -n "$DNS" ] && IMPORT_ARGS+=(--dns "$DNS")
fi
[ -n "$LOGIN_DOMAIN" ] && IMPORT_ARGS+=(--login-domain "$LOGIN_DOMAIN")
[ -n "$ORION_DOMAIN" ] && IMPORT_ARGS+=(--orion-domain "$ORION_DOMAIN")
[ -n "$SIECLE_DOMAIN" ] && IMPORT_ARGS+=(--siecle-domain "$SIECLE_DOMAIN")
[ -n "$LUNEA_DOMAIN" ] && IMPORT_ARGS+=(--lunea-domain "$LUNEA_DOMAIN")
[ -n "$CF_TOKEN" ] && IMPORT_ARGS+=(--cf-token "$CF_TOKEN")
if [ "$AS_TEMPLATE" -eq 1 ]; then
  IMPORT_ARGS+=(--as-template)
elif [ "$START_VM" -eq 1 ]; then
  IMPORT_ARGS+=(--start)
fi

# import_proxmox.sh cherche les fichiers cloud-init à côté de lui-même : on
# l'exécute donc directement depuis build/, où build.sh les a tous rassemblés.
(cd "$BUILD_DIR" && bash ./import_proxmox.sh "${IMPORT_ARGS[@]}")

echo ""
echo "======================================================"
echo " Terminé — VM $VMID ($VM_NAME) prête."
echo "======================================================"
if [ "$AS_TEMPLATE" -eq 0 ] && [ "$START_VM" -eq 1 ]; then
  echo ""
  echo "Suivre le premier démarrage via la console noVNC :"
  echo "  Proxmox UI -> $VM_NAME -> Console"
  echo "(~2-5 min de provisioning automatique, puis l'assistant interactif démarre)"
fi
