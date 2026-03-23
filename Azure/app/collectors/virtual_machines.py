"""Collector for Azure Virtual Machines."""

import logging

from azure_client import AzureClient
from constants import API_VERSIONS, OBJ_VIRTUAL_MACHINE, OBJ_RESOURCE_GROUP

logger = logging.getLogger(__name__)


def collect_virtual_machines(client: AzureClient, result, adapter_kind: str,
                             subscriptions: list):
    """Collect virtual machines across all subscriptions with instance view."""
    logger.info("Collecting virtual machines")
    total = 0

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]

        # List all VMs in subscription with instance view for power state
        vms = client.get_all(
            path=f"/subscriptions/{sub_id}/providers/Microsoft.Compute/virtualMachines",
            api_version=API_VERSIONS["virtual_machines"],
            params={"$expand": "instanceView"},
        )

        for vm in vms:
            vm_name = vm["name"]
            rg_name = _extract_resource_group(vm.get("id", ""))
            props = vm.get("properties", {})

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_VIRTUAL_MACHINE,
                name=vm_name,
                identifiers=[
                    ("subscription_id", sub_id),
                    ("resource_group", rg_name),
                    ("vm_name", vm_name),
                ],
            )

            # Core properties
            obj.with_property("vm_name", vm_name)
            obj.with_property("resource_id", vm.get("id", ""))
            obj.with_property("location", vm.get("location", ""))
            obj.with_property("vm_id", props.get("vmId", ""))
            obj.with_property("provisioning_state",
                              props.get("provisioningState", ""))
            obj.with_property("subscription_id", sub_id)
            obj.with_property("resource_group", rg_name)

            # Hardware
            hw = props.get("hardwareProfile", {})
            obj.with_property("vm_size", hw.get("vmSize", ""))

            # OS
            os_profile = props.get("osProfile", {})
            obj.with_property("computer_name",
                              os_profile.get("computerName", ""))
            obj.with_property("admin_username",
                              os_profile.get("adminUsername", ""))

            # Image reference
            storage = props.get("storageProfile", {})
            image_ref = storage.get("imageReference", {})
            obj.with_property("image_publisher", image_ref.get("publisher", ""))
            obj.with_property("image_offer", image_ref.get("offer", ""))
            obj.with_property("image_sku", image_ref.get("sku", ""))
            obj.with_property("image_version", image_ref.get("version", ""))

            # OS Disk
            os_disk = storage.get("osDisk", {})
            obj.with_property("os_type", os_disk.get("osType", ""))
            obj.with_property("os_disk_name", os_disk.get("name", ""))
            obj.with_property("os_disk_size_gb",
                              os_disk.get("diskSizeGB", ""))
            obj.with_property("os_disk_caching", os_disk.get("caching", ""))

            managed = os_disk.get("managedDisk", {})
            obj.with_property("os_disk_storage_type",
                              managed.get("storageAccountType", ""))

            # Data disk count
            data_disks = storage.get("dataDisks", [])
            obj.with_property("data_disk_count", len(data_disks))

            # Network interfaces (IDs)
            net_profile = props.get("networkProfile", {})
            nic_ids = [
                nic.get("id", "")
                for nic in net_profile.get("networkInterfaces", [])
            ]
            obj.with_property("network_interface_ids", ", ".join(nic_ids))
            obj.with_property("nic_count", len(nic_ids))

            # Power state from instance view
            power_state = _extract_power_state(props.get("instanceView", {}))
            obj.with_property("power_state", power_state)

            # Security profile
            security = props.get("securityProfile", {})
            obj.with_property("secure_boot_enabled",
                              str(security.get("uefiSettings", {}).get(
                                  "secureBootEnabled", "")))
            obj.with_property("vtpm_enabled",
                              str(security.get("uefiSettings", {}).get(
                                  "vTpmEnabled", "")))

            # Boot diagnostics
            diag = props.get("diagnosticsProfile", {})
            boot_diag = diag.get("bootDiagnostics", {})
            obj.with_property("boot_diagnostics_enabled",
                              str(boot_diag.get("enabled", "")))

            # Tags
            tags = vm.get("tags", {})
            if tags:
                for key, value in tags.items():
                    obj.with_property(f"tag_{key}", value)

            # Zones
            zones = vm.get("zones", [])
            if zones:
                obj.with_property("availability_zone", ", ".join(zones))

            # Relationship: VM -> Resource Group (parent)
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

        total += len(vms)

    logger.info("Collected %d virtual machines", total)


def _extract_resource_group(resource_id: str) -> str:
    """Extract resource group name from an Azure resource ID."""
    parts = resource_id.split("/")
    for i, part in enumerate(parts):
        if part.lower() == "resourcegroups" and i + 1 < len(parts):
            return parts[i + 1]
    return ""


def _extract_power_state(instance_view: dict) -> str:
    """Extract power state from VM instance view statuses."""
    for status in instance_view.get("statuses", []):
        code = status.get("code", "")
        if code.startswith("PowerState/"):
            return code.replace("PowerState/", "")
    return "unknown"
