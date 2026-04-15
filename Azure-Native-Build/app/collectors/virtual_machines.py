"""Collector for Azure Virtual Machines."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_VIRTUAL_MACHINE, OBJ_RESOURCE_GROUP, OBJ_DEDICATED_HOST,
    RES_IDENT_SUB, RES_IDENT_RG, RES_IDENT_REGION, RES_IDENT_ID,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE, AZURE_SERVICE_NAMES,
)
from helpers import make_identifiers, extract_resource_group, safe_property, sanitize_tag_key
from collectors.metrics import collect_metrics_for_objects

logger = logging.getLogger(__name__)


def collect_virtual_machines(client: AzureClient, result, adapter_kind: str,
                             subscriptions: list, vm_lookup: dict = None):
    """Collect virtual machines across all subscriptions with instance view.

    Args:
        client: Azure REST client.
        result: CollectResult to populate.
        adapter_kind: Adapter kind string.
        subscriptions: List of subscription dicts.
        vm_lookup: Optional pre-fetched dict mapping VM resource ID (lowered)
                   to VM API dict. If provided, skips the API call and uses
                   this data instead.
    """
    logger.info("Collecting virtual machines")
    total = 0
    vm_objects = {}  # resource_id -> aria obj, for metrics collection

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]

        # Use pre-fetched VM data if available, otherwise call API
        if vm_lookup is not None:
            vms = [v for v in vm_lookup.values()
                   if v.get("id", "").lower().startswith(
                       f"/subscriptions/{sub_id}".lower())]
        else:
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
            resource_id = vm.get("id", "")
            rg_name = extract_resource_group(resource_id)
            location = vm.get("location", "")
            props = vm.get("properties", {})

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_VIRTUAL_MACHINE,
                name=vm_name,
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
            safe_property(obj, SD_SERVICE, AZURE_SERVICE_NAMES.get(OBJ_VIRTUAL_MACHINE, ""))

            # Core properties
            safe_property(obj, "vm_name", vm_name)
            safe_property(obj, "resource_id", resource_id)
            safe_property(obj, "location", location)
            safe_property(obj, "vm_id", props.get("vmId", ""))
            safe_property(obj, "provisioning_state",
                          props.get("provisioningState", ""))
            safe_property(obj, "subscription_id", sub_id)
            safe_property(obj, "resource_group", rg_name)

            # Hardware
            hw = props.get("hardwareProfile", {})
            safe_property(obj, "summary|SIZING_TIER", hw.get("vmSize", ""))

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
            safe_property(obj, "summary|OS_TYPE", os_disk.get("osType", ""))
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
            safe_property(obj, "summary|runtime|powerState", power_state)
            # general|running — numeric metric: 1.0 if powered on, 0.0 if not
            obj.with_metric("general|running", 1.0 if power_state == "Powered On" else 0.0)

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
                    safe_property(obj, f"summary|tags|{key}", value)

            # Zones
            zones = vm.get("zones", [])
            if zones:
                safe_property(obj, "summary|availabilityZones", ", ".join(zones))

            # Dedicated Host placement
            host_ref = props.get("host", {})
            host_id = host_ref.get("id", "") if host_ref else ""
            safe_property(obj, "dedicated_host_id", host_id)
            if host_id:
                # Extract host group name and host name from resource ID
                # Format: .../hostGroups/{group}/hosts/{host}
                parts = host_id.split("/")
                dh_host_name = ""
                dh_group_name = ""
                for i, part in enumerate(parts):
                    if part.lower() == "hostgroups" and i + 1 < len(parts):
                        dh_group_name = parts[i + 1]
                    if part.lower() == "hosts" and i + 1 < len(parts):
                        dh_host_name = parts[i + 1]

                if dh_host_name and dh_group_name:
                    safe_property(obj, "dedicated_host_name", dh_host_name)
                    safe_property(obj, "dedicated_host_group", dh_group_name)

                    # Relationship: VM -> Dedicated Host (parent)
                    dh_obj = result.object(
                        adapter_kind=adapter_kind,
                        object_kind=OBJ_DEDICATED_HOST,
                        name=dh_host_name,
                        identifiers=make_identifiers([
                            (RES_IDENT_SUB, sub_id),
                            (RES_IDENT_RG, rg_name),
                            (RES_IDENT_REGION, location),
                            (RES_IDENT_ID, host_id),
                            ("hostGroupName", dh_group_name),
                        ]),
                    )
                    obj.add_parent(dh_obj)

            # Relationship: VM -> Resource Group (parent)
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

            # Track for metrics collection
            # CPU capacity reference for Aria Ops capacity planning
            obj.with_metric("CPU|capacity", 100.0)

            if resource_id:
                vm_objects[resource_id] = obj

        total += len(vms)

    logger.info("Collected %d virtual machines", total)

    # Collect Azure Monitor metrics for all VMs
    if vm_objects:
        collect_metrics_for_objects(client, vm_objects, "virtual_machines")



# Power state mapping — matches native pak MicrosoftAzureAdapter exactly
# Alerts check for "Powered On" / "Powered Off" / "Unknown"
_POWER_STATE_MAP = {
    "PowerState/stopping": "Powered Off",
    "PowerState/stopped": "Powered Off",
    "PowerState/starting": "Powered On",
    "PowerState/running": "Powered On",
    "PowerState/deallocating": "Unknown",
    "PowerState/deallocated": "Unknown",
}


def _extract_power_state(instance_view: dict) -> str:
    """Extract power state from VM instance view statuses.

    Returns native pak compatible values: 'Powered On', 'Powered Off', 'Unknown'.
    """
    for status in instance_view.get("statuses", []):
        code = status.get("code", "")
        if code.startswith("PowerState/"):
            return _POWER_STATE_MAP.get(code, "Unknown")
    return "Unknown"
