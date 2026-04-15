"""Collector for Azure Managed Disks."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_DISK, OBJ_RESOURCE_GROUP, OBJ_VIRTUAL_MACHINE,
    RES_IDENT_SUB, RES_IDENT_RG, RES_IDENT_REGION, RES_IDENT_ID,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE, AZURE_SERVICE_NAMES,
)
from helpers import make_identifiers, extract_resource_group, safe_property, sanitize_tag_key

logger = logging.getLogger(__name__)


def collect_disks(client: AzureClient, result, adapter_kind: str,
                  subscriptions: list):
    """Collect managed disks across all subscriptions."""
    logger.info("Collecting disks")
    total = 0

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
                ]),
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

            # Relationship: Disk -> Resource Group
            if rg_name:
                rg_id = f"/subscriptions/{sub_id}/resourceGroups/{rg_name}"
                rg_obj = result.object(
                    adapter_kind=adapter_kind,
                    object_kind=OBJ_RESOURCE_GROUP,
                    name=rg_name,
                    identifiers=make_identifiers([
                        (RES_IDENT_SUB, sub_id),
                        (RES_IDENT_ID, rg_id),
                    ]),
                )
                obj.add_parent(rg_obj)

            # Relationship: Disk -> VM (parent) via managedBy
            managed_by = disk.get("managedBy", "")
            safe_property(obj, "summary|virtualMachineId", managed_by)
            safe_property(obj, "summary|isAttachedToVirtualMachine",
                          str(bool(managed_by)))
            if managed_by:
                vm_name = managed_by.split("/")[-1] if managed_by else ""
                vm_rg = extract_resource_group(managed_by)
                if vm_name and vm_rg:
                    safe_property(obj, "attached_vm_name", vm_name)
                    # Derive VM location from disk location (same region)
                    vm_obj = result.object(
                        adapter_kind=adapter_kind,
                        object_kind=OBJ_VIRTUAL_MACHINE,
                        name=vm_name,
                        identifiers=make_identifiers([
                            (RES_IDENT_SUB, sub_id),
                            (RES_IDENT_RG, vm_rg),
                            (RES_IDENT_REGION, location),
                            (RES_IDENT_ID, managed_by),
                        ]),
                    )
                    obj.add_parent(vm_obj)

        total += len(disks)

    logger.info("Collected %d disks", total)
