"""Collector for Azure Virtual Machines."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_VIRTUAL_MACHINE, OBJ_RESOURCE_GROUP, OBJ_DEDICATED_HOST,
    RES_IDENT_SUB, RES_IDENT_RG, RES_IDENT_REGION, RES_IDENT_ID,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE, AZURE_SERVICE_NAMES,
)
from helpers import (make_identifiers, extract_resource_group,
                     reference_resource_group, safe_property, sanitize_tag_key)
from collectors.metrics import collect_metrics_for_objects

logger = logging.getLogger(__name__)


def collect_virtual_machines(client: AzureClient, result, adapter_kind: str,
                             subscriptions: list, vm_lookup: dict = None,
                             rg_lookup: dict = None):
    """Collect virtual machines across all subscriptions with instance view.

    Args:
        client: Azure REST client.
        result: CollectResult to populate.
        adapter_kind: Adapter kind string.
        subscriptions: List of subscription dicts.
        vm_lookup: Optional pre-fetched dict mapping VM resource ID (lowered)
                   to VM API dict. If provided, skips the API call and uses
                   this data instead.
        rg_lookup: Canonical RG lookup from resource_groups.py (see
                   helpers.build_rg_lookup). Required for VM->RG parent
                   edges; without it those edges are skipped.
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
            vms = client.get_all(
                path=f"/subscriptions/{sub_id}/providers/Microsoft.Compute/virtualMachines",
                api_version=API_VERSIONS["virtual_machines"],
            )

        # Power states — needed in BOTH code paths above (2026-07-10 fix:
        # this block previously lived inside the else, so when vm_lookup was
        # provided, power_lookup was undefined and the per-VM loop crashed on
        # first use, stripping properties/metrics/relationships from every VM).
        #
        # The subscription-level VM list does NOT honor $expand=instanceView
        # (Azure quirk). statusOnly=true returns the same VM set with
        # instanceView populated (and little else), so we fetch it as a
        # dedicated second call and build a lookup keyed on lowered ID.
        power_lookup = {}
        try:
            status_vms = client.get_all(
                path=f"/subscriptions/{sub_id}/providers/Microsoft.Compute/virtualMachines",
                api_version=API_VERSIONS["virtual_machines"],
                params={"statusOnly": "true"},
            )
            for sv in status_vms:
                iv = sv.get("properties", {}).get("instanceView", {})
                if iv:
                    power_lookup[sv.get("id", "").lower()] = iv
        except Exception as e:
            logger.warning("statusOnly power-state fetch failed for sub %s: %s",
                           sub_id, e)

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
                ], OBJ_VIRTUAL_MACHINE),
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

            # Power state from instance view (inline if present, else from
            # the per-subscription statusOnly lookup)
            power_state = _extract_power_state(
                props.get("instanceView")
                or power_lookup.get(resource_id.lower(), {})
            )
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
                # Extract host's rg + group + host names from resource ID.
                # The DH stub identifiers MUST match dedicated_hosts.py — it
                # uses the host's RG (not the VM's). VMs can be in a different
                # RG than the dedicated host they're placed on.
                # Format: /subscriptions/{sub}/resourceGroups/{rg}/providers
                #         /Microsoft.Compute/hostGroups/{group}/hosts/{host}
                parts = host_id.split("/")
                dh_host_name = ""
                dh_group_name = ""
                dh_rg_name = ""
                for i, part in enumerate(parts):
                    if part.lower() == "resourcegroups" and i + 1 < len(parts):
                        dh_rg_name = parts[i + 1]
                    if part.lower() == "hostgroups" and i + 1 < len(parts):
                        dh_group_name = parts[i + 1]
                    if part.lower() == "hosts" and i + 1 < len(parts):
                        dh_host_name = parts[i + 1]

                if dh_host_name and dh_group_name:
                    safe_property(obj, "dedicated_host_name", dh_host_name)
                    safe_property(obj, "dedicated_host_group", dh_group_name)

                    # Relationship: VM -> Dedicated Host (parent).
                    # Identifiers are lowercased so they dedup with the
                    # canonical host objects produced by dedicated_hosts.py
                    # regardless of how Azure cased the IDs in either API.
                    #
                    # NOTE (2026-07-16 casing audit): this lowercase recipe
                    # is DELIBERATE and matches dedicated_hosts.py's own
                    # declarations byte-for-byte — both sides of every DH
                    # edge use the same recipe, so these edges resolve.
                    # This is the accepted canonical convention for the
                    # AZURE_DEDICATE_HOST kind; do not "fix" one side to
                    # original casing without changing the other in the
                    # same commit.
                    dh_obj = result.object(
                        adapter_kind=adapter_kind,
                        object_kind=OBJ_DEDICATED_HOST,
                        name=dh_host_name,
                        identifiers=make_identifiers([
                            (RES_IDENT_SUB, sub_id),
                            (RES_IDENT_RG, dh_rg_name.lower()),
                            (RES_IDENT_REGION, location.lower()),
                            (RES_IDENT_ID, host_id.lower()),
                            ("hostGroupName", dh_group_name.lower()),
                        ], OBJ_DEDICATED_HOST),
                    )
                    obj.add_parent(dh_obj)

            # Relationship: VM -> Resource Group (parent).
            # 2026-07-16 fix: previously built an f-string rg_id with
            # .lower(), which could never resolve against the original-cased
            # RG objects in Aria Ops (the "zero relationships" defect). Now
            # resolves through the canonical rg_lookup; on a miss (deleted
            # RG / out-of-scope subscription) the edge is skipped — never
            # fabricate an RG identifier.
            if rg_name:
                rg_obj = reference_resource_group(
                    result, adapter_kind, sub_id, rg_name, rg_lookup)
                if rg_obj is not None:
                    obj.add_parent(rg_obj)
            else:
                # VM ID didn't yield an RG — likely an Arc-managed VM or
                # a non-standard resource shape. Log the resource_id once
                # so the operator can audit which kinds of VMs are
                # affected and decide whether to fall back to the
                # subscription-level parent.
                logger.warning(
                    "VM %s has no resource group (id=%s); skipping RG parent edge",
                    vm_name, resource_id,
                )

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
        collect_metrics_for_objects(client, vm_objects, "virtual_machines_extended")


# Power state mapping — matches native pak MicrosoftAzureAdapter exactly
# Alerts check for "Powered On" / "Powered Off" / "Unknown"
_POWER_STATE_MAP = {
    "PowerState/stopping": "Powered Off",
    "PowerState/stopped": "Powered Off",
    "PowerState/starting": "Powered On",
    "PowerState/running": "Powered On",
    "PowerState/deallocating": "Powered Off",
    "PowerState/deallocated": "Powered Off",
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


def link_boot_diagnostics_storage(result, adapter_kind, vm_lookup):
    """Link each VM to its boot-diagnostics storage account.

    The native pak surfaces the boot-diagnostics storage account in a VM's
    relationships (e.g. 'stagevirginiabootdiags'), and because that storage
    account lives in its own RG (e.g. 'stage-bootdiagnostics'), the VM ends
    up with a SECOND resource-group ancestor in the native relationship tree.
    Our VM collector only read diagnosticsProfile.bootDiagnostics.enabled for
    a property and never built the edge, so both the storage account and its
    RG were missing from the VM view.

    Azure exposes the account only as a blob endpoint URI
    (properties.diagnosticsProfile.bootDiagnostics.storageUri ->
    https://<account>.blob.core.usgovcloudapi.net/), so we parse the account
    name from the URI and match it against the AZURE_STORAGE_ACCOUNT objects
    already collected. Storage-account names are globally unique and
    lowercase, so a name match is exact — no identifier reconstruction (and
    thus none of the byte-match / silent-drop risk that plagued the phantom-VM
    and RG-casing bugs); we bind two objects that both already exist in
    `result`.

    Direction: the storage account is made a PARENT of the VM
    (vm.add_parent(storage)). The native tree shows the boot-diag storage —
    and, transitively, its resource group — as ANCESTORS of the VM (this is
    what produces the VM's second Resource Group). A shared boot-diag account
    simply gains one VM child per VM that uses it (multi-child is expected).

    Must run AFTER both collect_virtual_machines and collect_storage_accounts
    have populated `result`.

    Args:
        result: CollectResult already populated by both collectors.
        adapter_kind: Adapter kind string (unused today; kept for symmetry
            with the other collectors and future reference helpers).
        vm_lookup: {lowercased VM resource id -> raw VM dict} built in
            adapter.collect(); carries the raw storageUri the VM objects drop.

    Returns:
        Number of VM -> boot-diagnostics-storage edges added.
    """
    from constants import OBJ_VIRTUAL_MACHINE, OBJ_STORAGE_ACCOUNT, RES_IDENT_ID

    # AZURE_STORAGE_ACCOUNT objects keyed by lowercased account name.
    storage_by_name = {}
    # AZURE_VIRTUAL_MACHINE objects keyed by lowercased ARM resource id.
    vm_by_id = {}
    for obj in list(result.objects.values()):
        kind = obj.get_key().object_kind
        if kind == OBJ_STORAGE_ACCOUNT:
            name = obj.get_key().name
            if name:
                storage_by_name[name.lower()] = obj
        elif kind == OBJ_VIRTUAL_MACHINE:
            for ident in obj.get_key().identifiers.values():
                if ident.key == RES_IDENT_ID and ident.value:
                    vm_by_id[ident.value.lower()] = obj
                    break

    linked = 0
    missing_account = 0
    for vm_id_lower, raw in vm_lookup.items():
        uri = (raw.get("properties", {})
                  .get("diagnosticsProfile", {})
                  .get("bootDiagnostics", {})
                  .get("storageUri", "") or "")
        if not uri:
            continue
        # https://<account>.blob.core.usgovcloudapi.net/  ->  <account>
        host = uri.split("://", 1)[-1].split("/", 1)[0]
        account = host.split(".", 1)[0].lower()
        if not account:
            continue

        vm_obj = vm_by_id.get(vm_id_lower)
        storage_obj = storage_by_name.get(account)
        if vm_obj is None:
            continue
        if storage_obj is None:
            # Boot-diag account not in inventory (e.g. in an unenumerated sub,
            # or a managed-storage boot-diag that reports no account). Skip —
            # never fabricate a storage object, mirroring reference_vm.
            missing_account += 1
            continue
        vm_obj.add_parent(storage_obj)
        linked += 1

    logger.info(
        "Linked %d VM->boot-diagnostics-storage edges (%d VMs referenced a "
        "storage account not in inventory)", linked, missing_account,
    )
    return linked
