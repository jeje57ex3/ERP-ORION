#!/usr/bin/env bash
# lib/30 — Exporte OrionERP.ova (OVF + VMDK streamOptimized + manifest SHA1)
# à partir de OrionERP.qcow2, pour la portabilité hors Proxmox (VMware, etc.).
# Proxmox lui-même utilise directement le .qcow2 (import_proxmox.sh) — l'OVA
# est un format de distribution alternatif, pas le chemin d'import principal.
# Variables attendues : BUILD_DIR, WORK_DIR, VERSION

set -euo pipefail

: "${BUILD_DIR:?BUILD_DIR non défini}"
: "${WORK_DIR:?WORK_DIR non défini}"
: "${VERSION:?VERSION non défini}"

command -v qemu-img >/dev/null 2>&1 || { echo "ERREUR: qemu-img introuvable." >&2; exit 1; }

QCOW2="$BUILD_DIR/OrionERP.qcow2"
[ -f "$QCOW2" ] || { echo "ERREUR: $QCOW2 introuvable — lancer lib/10 d'abord." >&2; exit 1; }

OVA_WORK="$WORK_DIR/ova"
rm -rf "$OVA_WORK"
mkdir -p "$OVA_WORK"

VMDK="$OVA_WORK/OrionERP-disk1.vmdk"
OVF="$OVA_WORK/OrionERP.ovf"
MF="$OVA_WORK/OrionERP.mf"

echo "[30] Conversion qcow2 -> vmdk (streamOptimized)..."
qemu-img convert -O vmdk -o subformat=streamOptimized "$QCOW2" "$VMDK"

VMDK_SIZE=$(stat -c%s "$VMDK" 2>/dev/null || stat -f%z "$VMDK")
DISK_CAPACITY_GB=$(qemu-img info --output=json "$QCOW2" | python3 -c "import json,sys; print(json.load(sys.stdin)['virtual-size'] // (1024**3))")

echo "[30] Génération du descripteur OVF..."
cat > "$OVF" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<Envelope xmlns="http://schemas.dmtf.org/ovf/envelope/1"
          xmlns:ovf="http://schemas.dmtf.org/ovf/envelope/1"
          xmlns:rasd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_ResourceAllocationSettingData"
          xmlns:vssd="http://schemas.dmtf.org/wbem/wscim/1/cim-schema/2/CIM_VirtualSystemSettingData"
          xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <References>
    <File ovf:href="OrionERP-disk1.vmdk" ovf:id="file1" ovf:size="${VMDK_SIZE}"/>
  </References>
  <DiskSection>
    <Info>Virtual disk information</Info>
    <Disk ovf:capacity="${DISK_CAPACITY_GB}" ovf:capacityAllocationUnits="byte * 2^30"
          ovf:diskId="vmdisk1" ovf:fileRef="file1"
          ovf:format="http://www.vmware.com/interfaces/specifications/vmdk.html#streamOptimized"/>
  </DiskSection>
  <NetworkSection>
    <Info>The list of logical networks</Info>
    <Network ovf:name="VM Network">
      <Description>Réseau bridgé — associer au bridge cible à l'import</Description>
    </Network>
  </NetworkSection>
  <VirtualSystem ovf:id="OrionERP">
    <Info>Orion ERP Appliance ${VERSION}</Info>
    <Name>OrionERP</Name>
    <OperatingSystemSection ovf:id="94">
      <Info>Guest Operating System</Info>
      <Description>Ubuntu Server 24.04 LTS (64-bit)</Description>
    </OperatingSystemSection>
    <VirtualHardwareSection>
      <Info>Virtual hardware requirements</Info>
      <System>
        <vssd:ElementName>Virtual Hardware Family</vssd:ElementName>
        <vssd:InstanceID>0</vssd:InstanceID>
        <vssd:VirtualSystemIdentifier>OrionERP</vssd:VirtualSystemIdentifier>
        <vssd:VirtualSystemType>vmx-19</vssd:VirtualSystemType>
      </System>
      <Item>
        <rasd:AllocationUnits>hertz * 10^6</rasd:AllocationUnits>
        <rasd:Description>Number of Virtual CPUs</rasd:Description>
        <rasd:ElementName>4 virtual CPU(s)</rasd:ElementName>
        <rasd:InstanceID>1</rasd:InstanceID>
        <rasd:ResourceType>3</rasd:ResourceType>
        <rasd:VirtualQuantity>4</rasd:VirtualQuantity>
      </Item>
      <Item>
        <rasd:AllocationUnits>byte * 2^20</rasd:AllocationUnits>
        <rasd:Description>Memory Size</rasd:Description>
        <rasd:ElementName>8192MB of memory</rasd:ElementName>
        <rasd:InstanceID>2</rasd:InstanceID>
        <rasd:ResourceType>4</rasd:ResourceType>
        <rasd:VirtualQuantity>8192</rasd:VirtualQuantity>
      </Item>
      <Item>
        <rasd:Address>0</rasd:Address>
        <rasd:Description>SCSI Controller</rasd:Description>
        <rasd:ElementName>SCSI Controller 0</rasd:ElementName>
        <rasd:InstanceID>3</rasd:InstanceID>
        <rasd:ResourceSubType>VirtualSCSI</rasd:ResourceSubType>
        <rasd:ResourceType>6</rasd:ResourceType>
      </Item>
      <Item>
        <rasd:AddressOnParent>0</rasd:AddressOnParent>
        <rasd:ElementName>Hard Disk 1</rasd:ElementName>
        <rasd:HostResource>ovf:/disk/vmdisk1</rasd:HostResource>
        <rasd:InstanceID>4</rasd:InstanceID>
        <rasd:Parent>3</rasd:Parent>
        <rasd:ResourceType>17</rasd:ResourceType>
      </Item>
      <Item>
        <rasd:AddressOnParent>1</rasd:AddressOnParent>
        <rasd:AutomaticAllocation>true</rasd:AutomaticAllocation>
        <rasd:Connection>VM Network</rasd:Connection>
        <rasd:ElementName>Network adapter 1</rasd:ElementName>
        <rasd:InstanceID>5</rasd:InstanceID>
        <rasd:ResourceSubType>VmxNet3</rasd:ResourceSubType>
        <rasd:ResourceType>10</rasd:ResourceType>
      </Item>
    </VirtualHardwareSection>
  </VirtualSystem>
</Envelope>
EOF

echo "[30] Génération du manifest OVF (SHA1)..."
{
  printf 'SHA1(%s)= %s\n' "OrionERP.ovf" "$(sha1sum "$OVF" | awk '{print $1}')"
  printf 'SHA1(%s)= %s\n' "OrionERP-disk1.vmdk" "$(sha1sum "$VMDK" | awk '{print $1}')"
} > "$MF"

echo "[30] Assemblage de l'archive OVA..."
tar -cf "$BUILD_DIR/OrionERP.ova" -C "$OVA_WORK" OrionERP.ovf OrionERP.mf OrionERP-disk1.vmdk

rm -rf "$OVA_WORK"

echo "[30] OVA généré : $BUILD_DIR/OrionERP.ova ($(du -sh "$BUILD_DIR/OrionERP.ova" | cut -f1))"
