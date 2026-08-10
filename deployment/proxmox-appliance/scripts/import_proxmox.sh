#!/usr/bin/env bash
# Orion ERP Appliance — Import de l'image qcow2 dans Proxmox VE.
# À exécuter SUR le host Proxmox (nécessite la commande `qm`), depuis le
# dossier build/ produit par build.sh (qcow2 + fichiers cloud-init).
#
# Usage :
#   ./import_proxmox.sh [options]
#   ./import_proxmox.sh --list-storage      # liste les stockages disponibles et quitte
#   ./import_proxmox.sh --list-bridges      # liste les bridges réseau disponibles et quitte
#
# Options :
#   --vmid ID              ID de la VM (def: 9000)
#   --name NAME             Nom de la VM (def: OrionERP)
#   --storage STORAGE       Stockage du disque d'installation (def: local-lvm)
#                           Voir --list-storage pour les stockages disponibles.
#   --snippets-storage S    Stockage contenant "snippets" pour le cloud-init custom (def: local)
#   --bridge BRIDGE         Bridge réseau (def: vmbr0). Voir --list-bridges.
#   --memory MB              RAM en Mo (def: 8192)
#   --cores N                vCPU (def: 4)
#   --disk PATH              Chemin du qcow2 (def: ./OrionERP.qcow2)
#   --disk-size SIZE         Taille cible du disque virtuel, ex: 80G, 120G, 500G (def: 80G)
#   --ip IP/CIDR             IP statique (ex: 192.168.1.50/24). Omis = DHCP.
#   --gateway IP             Passerelle (requis si --ip fourni)
#   --dns IP                 Serveur DNS (def: identique à --gateway si omis)
#   --sshkey PATH             Clé publique SSH à injecter (def: aucune)
#   --as-template             Convertit la VM en template Proxmox après import
#   --start                   Démarre la VM après import
#   -h, --help                Affiche cette aide

set -euo pipefail

VMID=9000
VM_NAME="OrionERP"
STORAGE="local-lvm"
SNIPPETS_STORAGE="local"
BRIDGE="vmbr0"
MEMORY=8192
CORES=4
DISK_PATH="./OrionERP.qcow2"
DISK_SIZE="80G"
STATIC_IP=""
GATEWAY=""
DNS=""
SSHKEY=""
AS_TEMPLATE=0
START_VM=0

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
USERDATA_FILE="$SCRIPT_DIR/OrionERP.cloudinit-userdata.yaml"
NETWORK_FILE="$SCRIPT_DIR/OrionERP.cloudinit-network-config.yaml"

usage() { sed -n '2,28p' "$0" | sed 's/^# \{0,1\}//'; }

list_storage() {
  command -v pvesm >/dev/null 2>&1 || { echo "ERREUR: pvesm introuvable (hôte non-Proxmox)." >&2; exit 1; }
  echo "Stockages disponibles (contenu 'images') :"
  pvesm status --content images
  echo ""
  echo "Stockages disponibles (contenu 'snippets') :"
  pvesm status --content snippets
}

list_bridges() {
  echo "Bridges réseau disponibles :"
  ip -o link show type bridge 2>/dev/null | awk -F': ' '{print "  " $2}' | sed 's/@.*//'
}

if [ "${1:-}" = "--list-storage" ]; then list_storage; exit 0; fi
if [ "${1:-}" = "--list-bridges" ]; then list_bridges; exit 0; fi

while [ $# -gt 0 ]; do
  case "$1" in
    --vmid) VMID="$2"; shift 2 ;;
    --name) VM_NAME="$2"; shift 2 ;;
    --storage) STORAGE="$2"; shift 2 ;;
    --snippets-storage) SNIPPETS_STORAGE="$2"; shift 2 ;;
    --bridge) BRIDGE="$2"; shift 2 ;;
    --memory) MEMORY="$2"; shift 2 ;;
    --cores) CORES="$2"; shift 2 ;;
    --disk) DISK_PATH="$2"; shift 2 ;;
    --disk-size) DISK_SIZE="$2"; shift 2 ;;
    --ip) STATIC_IP="$2"; shift 2 ;;
    --gateway) GATEWAY="$2"; shift 2 ;;
    --dns) DNS="$2"; shift 2 ;;
    --sshkey) SSHKEY="$2"; shift 2 ;;
    --as-template) AS_TEMPLATE=1; shift ;;
    --start) START_VM=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Option inconnue : $1" >&2; usage; exit 1 ;;
  esac
done

command -v qm >/dev/null 2>&1 || { echo "ERREUR: commande 'qm' introuvable — ce script doit tourner sur un host Proxmox VE."; exit 1; }
[ -f "$DISK_PATH" ] || { echo "ERREUR: image introuvable : $DISK_PATH"; exit 1; }
[[ "$DISK_SIZE" =~ ^[0-9]+[GgTt]$ ]] || { echo "ERREUR: --disk-size invalide ('$DISK_SIZE') — format attendu : 80G, 120G, 1T..."; exit 1; }
if [ -n "$STATIC_IP" ] && [ -z "$GATEWAY" ]; then
  echo "ERREUR: --gateway est requis quand --ip est fourni."; exit 1
fi

if qm status "$VMID" >/dev/null 2>&1; then
  echo "ERREUR: une VM avec l'ID $VMID existe déjà. Choisir un autre --vmid."
  exit 1
fi

echo "======================================"
echo " Import Orion ERP Appliance -> Proxmox"
echo "======================================"
echo " VMID              : $VMID"
echo " Nom                : $VM_NAME"
echo " Stockage disque    : $STORAGE"
echo " Taille disque       : $DISK_SIZE"
echo " Stockage snippets  : $SNIPPETS_STORAGE"
echo " Bridge             : $BRIDGE"
echo " RAM / vCPU         : ${MEMORY}Mo / ${CORES}"
echo " Réseau              : $([ -n "$STATIC_IP" ] && echo "statique $STATIC_IP (gw $GATEWAY)" || echo "DHCP")"
echo " Image               : $DISK_PATH"
echo "======================================"

echo "[1/6] Création de la VM (q35, UEFI/OVMF, VirtIO)..."
qm create "$VMID" \
  --name "$VM_NAME" \
  --memory "$MEMORY" \
  --balloon $((MEMORY / 4)) \
  --cores "$CORES" \
  --cpu host \
  --machine q35 \
  --bios ovmf \
  --scsihw virtio-scsi-pci \
  --net0 "virtio,bridge=${BRIDGE}" \
  --agent enabled=1 \
  --ostype l26

echo "[2/6] Ajout du disque EFI (OVMF)..."
qm set "$VMID" --efidisk0 "${STORAGE}:0,efitype=4m,pre-enrolled-keys=1"

echo "[3/6] Import du disque qcow2 sur '${STORAGE}'..."
qm importdisk "$VMID" "$DISK_PATH" "$STORAGE"

echo "[4/6] Attache et configuration du disque (VirtIO SCSI, discard/ssd, trim)..."
qm set "$VMID" --scsi0 "${STORAGE}:vm-${VMID}-disk-1,discard=on,ssd=1,iothread=1"
qm set "$VMID" --boot order=scsi0
qm set "$VMID" --serial0 socket --vga serial0

echo "[5/6] Cloud-init : lecteur ide2 + user-data/network-config personnalisés..."
qm set "$VMID" --ide2 "${STORAGE}:cloudinit"

if [ -f "$USERDATA_FILE" ] && [ -f "$NETWORK_FILE" ]; then
  SNIPPETS_DIR="/var/lib/vz/snippets"
  if [ "$SNIPPETS_STORAGE" != "local" ]; then
    SNIPPETS_DIR="$(pvesm path "${SNIPPETS_STORAGE}:snippets" 2>/dev/null || echo "/var/lib/vz/snippets")"
  fi
  mkdir -p "$SNIPPETS_DIR"
  # Nommage par VMID : deux VM ne doivent jamais partager le même fichier
  # snippet, sinon un nouveau build peut écraser (et faire lire à moitié
  # écrit) le cloud-init d'une VM déjà en train de démarrer.
  USERDATA_SNIPPET="OrionERP-${VMID}.cloudinit-userdata.yaml"
  NETWORK_SNIPPET="OrionERP-${VMID}.cloudinit-network-config.yaml"
  cp "$USERDATA_FILE" "$SNIPPETS_DIR/$USERDATA_SNIPPET"
  cp "$NETWORK_FILE" "$SNIPPETS_DIR/$NETWORK_SNIPPET"
  qm set "$VMID" --cicustom "user=${SNIPPETS_STORAGE}:snippets/${USERDATA_SNIPPET},network=${SNIPPETS_STORAGE}:snippets/${NETWORK_SNIPPET}"
  echo "  -> cloud-init personnalisé activé (stockage '${SNIPPETS_STORAGE}' doit autoriser le contenu 'snippets')."
else
  echo "  ATTENTION: fichiers cloud-init introuvables à côté du script — VM créée sans provisioning automatique."
  echo "             Relancer build.sh, ou copier OrionERP.cloudinit-*.yaml à côté de import_proxmox.sh."
fi

if [ -n "$STATIC_IP" ]; then
  DNS="${DNS:-$GATEWAY}"
  qm set "$VMID" --ipconfig0 "ip=${STATIC_IP},gw=${GATEWAY}"
  qm set "$VMID" --nameserver "$DNS"
else
  qm set "$VMID" --ipconfig0 ip=dhcp
fi
[ -n "$SSHKEY" ] && qm set "$VMID" --sshkeys "$SSHKEY"

echo "[6/6] Finalisation (redimensionnement à ${DISK_SIZE})..."
qm resize "$VMID" scsi0 "$DISK_SIZE" || echo "  (déjà à la taille cible, ou redimensionnement ignoré)"

if [ "$AS_TEMPLATE" -eq 1 ]; then
  qm template "$VMID"
  echo "VM $VMID convertie en template."
elif [ "$START_VM" -eq 1 ]; then
  qm start "$VMID"
  echo "VM $VMID démarrée — suivre l'assistant via la console (noVNC) : premier boot ~2-5 min avant l'apparition du wizard."
else
  echo "VM $VMID créée (arrêtée). Démarrer avec : qm start $VMID"
fi

echo ""
echo "Terminé."
