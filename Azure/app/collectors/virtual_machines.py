"""Collector for Azure Virtual Machines."""

import logging

from azure_client import AzureClient
from constants import API_VERSIONS, OBJ_VIRTUAL_MACHINE, OBJ_RESOURCE_GROUP
from helpers import make_identifiers, extract_resource_group, safe_property

logger = logging.getLogger(__name__)


def collect_virtual_machines(client: AzureClient, result, adapter_kind: str,
                             subscriptions: list):
    """Collect virtual machines across all subscriptions with instance view."""
    logger.info("Collecting virtual machines")
    total = 0

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]

        # List all VMs in subscription
        # Try with instanceView first, fall back without it
        try:
            vms = client.get_all(
                path=f"/subscriptions/{sub_id}/providers/Microsoft.Compute/virtualMachines",
                api_version=API_VERSIONS["virtual_machines"],
                params={"$expand": "instanceView"},
            )
        except Exception:
            logger.warning("instanceView expand failed for sub %s, retrying without", sub_id)
            vms = client.get_all(
                path=f"/subscriptions/{sub_id}/providers/Microsoft.Compute/virtualMachines",
                api_version=API_VERSIONS["virtual_machines"],
            )

        for vm in vms:
            vm_name = vm["name"]
            rg_name = extract_resource_group(vm.get("id", ""))
            props = vm.get("properties", {})

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_VIRTUAL_MACHINE,
                name=vm_name,
                identifiers=make_identifiers([
                    ("subscription_id", sub_id),
                    ("resource_group", rg_name),
                    ("vm_name", vm_name),
                ]),
            )

            # Core properties
            safe_property(obj, "vm_name", vm_name)
            safe_property(obj, "resource_id", vm.get("id", ""))
            safe_property(obj, "location", vm.get("location", ""))
            safe_property(obj, "vm_id", props.get("vmId", ""))
            safe_property(obj, "provisioning_state",
                          props.get("provisioningState", ""))
            safe_property(obj, "subscription_id", sub_id)
            safe_property(obj, "resource_group", rg_name)

            # Hardware
            hw = props.get("hardwareProfile", {})
            safe_property(obj, "vm_size", hw.get("vmSize", ""))

            # OS
            os_profile = props.get("osProfile", {})
            safe_property(obj, "computer_name",
                          os_profile.get("computerName", ""))
            safe_property(obj, "admin_username",
                          os_profile.get("adminUsername", ""))

            # Image reference
            storage = props.get("storageProfile", {})
            image_ref = storage.get("imageReference", {})
            safe_property(obj, "image_publisher", image_ref.get("publisher", ""))
            safe_property(obj, "image_offer", image_ref.get("offer", ""))
            safe_property(obj, "image_sku", image_ref.get("sku", ""))
            safe_property(obj, "image_version", image_ref.get("version", ""))

            # OS Disk
            os_disk = storage.get("osDisk", {})
            safe_property(obj, "os_type", os_disk.get("osType", ""))
            safe_property(obj, "os_disk_name", os_disk.get("name", ""))
            safe_property(obj, "os_disk_size_gb",
                          os_disk.get("diskSizeGB", ""))
            safe_property(obj, "os_disk_caching", os_disk.get("caching", ""))

            managed = os_disk.get("managedDisk", {})
            safe_property(obj, "os_disk_storage_type",
                          managed.get("storageAccountType", ""))

            # Data disk count
            data_disks = storage.get("dataDisks", [])
            safe_property(obj, "data_disk_count", len(data_disks))

            # Network interfaces (IDs)
            net_profile = props.get("networkProfile", {})
            nic_ids = [
                nic.get("id", "")
                for nic in net_profile.get("networkInterfaces", [])
            ]
            safe_property(obj, "network_interface_ids", ", ".join(nic_ids))
            safe_property(obj, "nic_count", len(nic_ids))

            # Power state from instance view
            power_state = _extract_power_state(props.get("instanceView", {}))
            safe_property(obj, "power_state", power_state)

            # Security profile
            security = props.get("securityProfile", {})
            safe_property(obj, "secure_boot_enabled",
                          str(security.get("uefiSettings", {}).get(
                              "secureBootEnabled", "")))
            safe_property(obj, "vtpm_enabled",
                          str(security.get("uefiSettings", {}).get(
                              "vTpmEnabled", "")))

            # Boot diagnostics
            diag = props.get("diagnosticsProfile", {})
            boot_diag = diag.get("bootDiagnostics", {})
            safe_property(obj, "boot_diagnostics_enabled",
                          str(boot_diag.get("enabled", "")))

            # Tags
            tags = vm.get("tags", {})
            if tags:
                for key, value in tags.items():
                    safe_property(obj, f"tag_{key}", value)

            # Zones
            zones = vm.get("zones", [])
            if zones:
                safe_property(obj, "availability_zone", ", ".join(zones))

            # Relationship: VM -> Resource Group (parent)
            if rg_name:
                rg_obj = result.object(
                    adapter_kind=adapter_kind,
                    object_kind=OBJ_RESOURCE_GROUP,
                    name=rg_name,
                    identifiers=make_identifiers([
                        ("subscription_id", sub_id),
                        ("resource_group_name", rg_name),
                    ]),
                )
                obj.add_parent(rg_obj)

        total += len(vms)

    logger.info("Collected %d virtual machines", total)



def _extract_power_state(instance_view: dict) -> str:
    """Extract power state from VM instance view statuses."""
    for status in instance_view.get("statuses", []):
        code = status.get("code", "")
        if code.startswith("PowerState/"):
            return code.replace("PowerState/", "")
    return "unknown"
