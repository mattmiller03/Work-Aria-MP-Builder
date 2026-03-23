"""Collector for Azure Managed Disks."""

import logging

from azure_client import AzureClient
from constants import API_VERSIONS, OBJ_DISK, OBJ_RESOURCE_GROUP

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
            rg_name = _extract_rg(disk.get("id", ""))
            props = disk.get("properties", {})
            sku = disk.get("sku", {})

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_DISK,
                name=disk_name,
                identifiers=[
                    ("subscription_id", sub_id),
                    ("resource_group", rg_name),
                    ("disk_name", disk_name),
                ],
            )

            obj.with_property("disk_name", disk_name)
            obj.with_property("resource_id", disk.get("id", ""))
            obj.with_property("location", disk.get("location", ""))
            obj.with_property("subscription_id", sub_id)
            obj.with_property("resource_group", rg_name)
            obj.with_property("sku_name", sku.get("name", ""))
            obj.with_property("sku_tier", sku.get("tier", ""))
            obj.with_property("disk_size_gb", props.get("diskSizeGB", ""))
            obj.with_property("disk_iops_read_write",
                              props.get("diskIOPSReadWrite", ""))
            obj.with_property("disk_mbps_read_write",
                              props.get("diskMBpsReadWrite", ""))
            obj.with_property("disk_state", props.get("diskState", ""))
            obj.with_property("os_type", props.get("osType", ""))
            obj.with_property("time_created", props.get("timeCreated", ""))
            obj.with_property("provisioning_state",
                              props.get("provisioningState", ""))
            obj.with_property("encryption_type",
                              props.get("encryption", {}).get("type", ""))
            obj.with_property("network_access_policy",
                              props.get("networkAccessPolicy", ""))

            # Tags
            tags = disk.get("tags", {})
            if tags:
                for key, value in tags.items():
                    obj.with_property(f"tag_{key}", value)

            # Zones
            zones = disk.get("zones", [])
            if zones:
                obj.with_property("availability_zone", ", ".join(zones))

            # Relationship: Disk -> Resource Group
            if rg_name:
                result.add_relationship(
                    parent=result.object(
                        adapter_kind=adapter_kind,
                        object_kind=OBJ_RESOURCE_GROUP,
                        name=rg_name,
                        identifiers=[
                            ("subscription_id", sub_id),
                            ("resource_group_name", rg_name),
                        ],
                    ),
                    child=obj,
                )

        total += len(disks)

    logger.info("Collected %d disks", total)


def _extract_rg(resource_id: str) -> str:
    parts = resource_id.split("/")
    for i, part in enumerate(parts):
        if part.lower() == "resourcegroups" and i + 1 < len(parts):
            return parts[i + 1]
    return ""
