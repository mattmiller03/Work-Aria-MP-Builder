"""Collector for Azure Managed Disks."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_DISK, OBJ_RESOURCE_GROUP,
    RES_IDENT_SUB, RES_IDENT_RG, RES_IDENT_REGION, RES_IDENT_ID,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE, AZURE_SERVICE_NAMES,
)
from helpers import (
    make_identifiers, extract_resource_group, safe_property, sanitize_tag_key,
    reference_vm, reference_resource_group,
)

logger = logging.getLogger(__name__)

from typing import Optional

def collect_disks(client: AzureClient, result, adapter_kind: str,
                  subscriptions: list, vm_lookup: Optional[dict] = None,
                  rg_lookup: Optional[dict] = None):
    """Collect managed disks across all subscriptions.

    Args:
        client: Azure REST client.
        result: CollectResult to populate.
        adapter_kind: Adapter kind string.
        subscriptions: List of subscription dicts.
        vm_lookup: Dict mapping lowercased VM resource IDs to VM dicts
            from the Azure VM API (populated by virtual_machines.py,
            which runs before this collector). Used to resolve managedBy
            references to canonical VM objects. Without it, Disk->VM
            relationships are skipped rather than risk creating phantom
            VM objects (see helpers.reference_vm docstring).
        rg_lookup: Canonical RG lookup from resource_groups.py (see
            helpers.build_rg_lookup). Used to resolve Disk->RG parent
            edges with original-cased IDs. Without it, RG edges are
            skipped rather than risk minting duplicate RG objects.
    """
    logger.info("Collecting disks")
    if vm_lookup is None:
        vm_lookup = {}
    total = 0
    skipped_vm_refs = 0

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]
        disks = client.get_all(
            path=f"/subscriptions/{sub_id}/providers/Microsoft.Compute/disks",
            api_version=API_VERSIONS["disks"],
        )

        for disk in disks:
            disk_name = disk["name"]
            resource_id = disk.get("id", "")
            rg_name = extract_resource_group(resource_id)
            location = disk.get("location", "")
            props = disk.get("properties", {})
            sku = disk.get("sku", {})

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_DISK,
                name=disk_name,
                identifiers=make_identifiers([
                    (RES_IDENT_SUB, sub_id),
                    (RES_IDENT_RG, rg_name),
                    (RES_IDENT_REGION, location),
                    (RES_IDENT_ID, resource_id),
                ], OBJ_DISK),
            )

            # SERVICE_DESCRIPTORS
            safe_property(obj, SD_SUBSCRIPTION, sub_id)
            safe_property(obj, SD_RESOURCE_GROUP, rg_name)
            safe_property(obj, SD_REGION, location)
            safe_property(obj, SD_SERVICE, AZURE_SERVICE_NAMES.get(OBJ_DISK, ""))

            safe_property(obj, "summary|name", disk_name)
            safe_property(obj, "resource_id", resource_id)
            safe_property(obj, "location", location)
            safe_property(obj, "subscription_id", sub_id)
            safe_property(obj, "resource_group", rg_name)
            safe_property(obj, "summary|type", sku.get("name", ""))
            safe_property(obj, "summary|sku", sku.get("tier", ""))
            safe_property(obj, "summary|sizeInGB", props.get("diskSizeGB", ""))
            safe_property(obj, "disk_iops_read_write",
                          props.get("diskIOPSReadWrite", ""))
            safe_property(obj, "disk_mbps_read_write",
                          props.get("diskMBpsReadWrite", ""))
            safe_property(obj, "disk_state", props.get("diskState", ""))
            safe_property(obj, "summary|osType", props.get("osType", ""))
            safe_property(obj, "time_created", props.get("timeCreated", ""))
            safe_property(obj, "provisioning_state",
                          props.get("provisioningState", ""))
            safe_property(obj, "encryption_type",
                          props.get("encryption", {}).get("type", ""))
            safe_property(obj, "network_access_policy",
                          props.get("networkAccessPolicy", ""))
            safe_property(obj, "summary|creationMethod",
                          props.get("creationData", {}).get("createOption", ""))
            safe_property(obj, "summary|source",
                          props.get("creationData", {}).get("sourceResourceId", ""))

            # Tags
            tags = disk.get("tags", {})
            if tags:
                for key, value in tags.items():
                    safe_property(obj, f"summary|tags|{key}", value)

            # Zones
            zones = disk.get("zones", [])
            if zones:
                safe_property(obj, "availability_zone", ", ".join(zones))

            # Relationship: Disk -> Resource Group (parent).
            # 2026-07-16 fix: previously built an f-string rg_id with
            # .lower(), which could never resolve against the original-cased
            # RG objects in Aria Ops (the "zero relationships" defect). Now
            # resolves through the canonical rg_lookup; on a miss the edge
            # is skipped — never fabricate an RG identifier.
            if rg_name:
                rg_obj = reference_resource_group(
                    result, adapter_kind, sub_id, rg_name, rg_lookup)
                if rg_obj is not None:
                    obj.add_parent(rg_obj)

            # Relationship: Disk -> VM (parent) via managedBy.
            #
            # PHANTOM-VM FIX (2026-07-09): previously this block built the
            # VM reference directly from the disk API's managedBy string.
            # Azure APIs disagree on resource-ID casing between endpoints,
            # so those identifiers didn't byte-match the canonical VM
            # objects from virtual_machines.py — the SDK minted a second,
            # property-less "phantom" VM per real VM (684 collected vs 332
            # real). Now we resolve managedBy through vm_lookup via
            # helpers.reference_vm, which reconstructs the reference from
            # the VM API's own field values. If the VM isn't in inventory
            # (deleted VM, stale managedBy), we SKIP the edge — never
            # create a fallback object.
            managed_by = disk.get("managedBy", "")
            safe_property(obj, "summary|virtualMachineId", managed_by)
            safe_property(obj, "summary|isAttachedToVirtualMachine",
                          str(bool(managed_by)))
            if managed_by:
                vm_name = managed_by.split("/")[-1]
                safe_property(obj, "attached_vm_name", vm_name)
                vm_obj = reference_vm(result, adapter_kind, sub_id,
                                      managed_by, vm_lookup)
                if vm_obj is not None:
                    obj.add_parent(vm_obj)
                else:
                    skipped_vm_refs += 1
                    logger.info(
                        "Disk %s: managedBy VM not in inventory "
                        "(deleted or out of scope): %s",
                        disk_name, managed_by,
                    )

        total += len(disks)

    if skipped_vm_refs:
        logger.warning(
            "Skipped %d Disk->VM relationship(s) for VMs not in inventory",
            skipped_vm_refs,
        )
    logger.info("Collected %d disks", total)
