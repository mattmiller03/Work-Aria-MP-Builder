"""Collector for Azure Network Interfaces."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_NETWORK_INTERFACE, OBJ_RESOURCE_GROUP,
    RES_IDENT_SUB, RES_IDENT_RG, RES_IDENT_REGION, RES_IDENT_ID,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE, AZURE_SERVICE_NAMES,
)
from helpers import (
    make_identifiers, extract_resource_group, safe_property, sanitize_tag_key,
    reference_resource_group, reference_vm,
)
from collectors.metrics import collect_metrics_for_objects

logger = logging.getLogger(__name__)


def collect_network_interfaces(client: AzureClient, result, adapter_kind: str,
                               subscriptions: list,
                               vm_lookup: dict = None,
                               rg_lookup: dict = None):
    """Collect network interfaces across all subscriptions.

    vm_lookup (from virtual_machines.py, keyed on lowercased VM resource IDs)
    is used to resolve the NIC's attached VM (properties.virtualMachine.id) to
    the canonical VM object so the NIC becomes a child of its VM — matching the
    native model, where a VM's Related-Objects lists its NICs. Without it, or
    on a miss (unattached NIC / VM out of scope), the NIC->VM edge is skipped
    rather than risk a phantom VM (see helpers.reference_vm).
    """
    logger.info("Collecting network interfaces")
    if vm_lookup is None:
        vm_lookup = {}
    total = 0
    skipped_vm_refs = 0
    nic_objects = {}  # resource_id -> aria obj

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]
        nics = client.get_all(
            path=f"/subscriptions/{sub_id}/providers/Microsoft.Network/networkInterfaces",
            api_version=API_VERSIONS["network_interfaces"],
        )

        for nic in nics:
            nic_name = nic["name"]
            resource_id = nic.get("id", "")
            rg_name = extract_resource_group(resource_id)
            location = nic.get("location", "")
            props = nic.get("properties", {})

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_NETWORK_INTERFACE,
                name=nic_name,
                identifiers=make_identifiers([
                    (RES_IDENT_SUB, sub_id),
                    (RES_IDENT_RG, rg_name),
                    (RES_IDENT_REGION, location),
                    (RES_IDENT_ID, resource_id),
                ], OBJ_NETWORK_INTERFACE),
            )

            # SERVICE_DESCRIPTORS
            safe_property(obj, SD_SUBSCRIPTION, sub_id)
            safe_property(obj, SD_RESOURCE_GROUP, rg_name)
            safe_property(obj, SD_REGION, location)
            safe_property(obj, SD_SERVICE, AZURE_SERVICE_NAMES.get(OBJ_NETWORK_INTERFACE, ""))

            safe_property(obj, "nic_name", nic_name)
            safe_property(obj, "resource_id", resource_id)
            safe_property(obj, "location", location)
            safe_property(obj, "subscription_id", sub_id)
            safe_property(obj, "resource_group", rg_name)
            safe_property(obj, "mac_address", props.get("macAddress", ""))
            safe_property(obj, "is_primary", str(props.get("primary", "")))
            safe_property(obj, "enable_ip_forwarding",
                          str(props.get("enableIPForwarding", "")))
            safe_property(obj, "provisioning_state",
                          props.get("provisioningState", ""))

            # NSG
            nsg = props.get("networkSecurityGroup", {})
            safe_property(obj, "nsg_id", nsg.get("id", ""))

            # Associated VM
            vm_ref = props.get("virtualMachine", {})
            safe_property(obj, "attached_vm_id", vm_ref.get("id", ""))

            # IP configurations
            ip_configs = props.get("ipConfigurations", [])
            private_ips = []
            subnet_ids = []
            public_ip_ids = []

            for ip_cfg in ip_configs:
                ip_props = ip_cfg.get("properties", {})
                private_ip = ip_props.get("privateIPAddress", "")
                if private_ip:
                    private_ips.append(private_ip)

                subnet = ip_props.get("subnet", {})
                if subnet.get("id"):
                    subnet_ids.append(subnet["id"])

                public_ip = ip_props.get("publicIPAddress", {})
                if public_ip.get("id"):
                    public_ip_ids.append(public_ip["id"])

                safe_property(obj, "private_ip_allocation_method",
                              ip_props.get("privateIPAllocationMethod", ""))

            safe_property(obj, "private_ip_addresses", ", ".join(private_ips))
            safe_property(obj, "subnet_ids", ", ".join(subnet_ids))
            safe_property(obj, "public_ip_ids", ", ".join(public_ip_ids))
            safe_property(obj, "ip_config_count", len(ip_configs))

            # DNS
            dns = props.get("dnsSettings", {})
            safe_property(obj, "dns_servers",
                          ", ".join(dns.get("dnsServers", [])))
            safe_property(obj, "applied_dns_servers",
                          ", ".join(dns.get("appliedDnsServers", [])))

            # Tags
            tags = nic.get("tags", {})
            if tags:
                for key, value in tags.items():
                    safe_property(obj, f"summary|tags|{key}", value)

            # Relationship: NIC -> Resource Group
            if rg_name:
                # 2026-07-16 fix: previously built an f-string rg_id with
                # .lower(), which could never resolve against the original-cased
                # RG objects in Aria Ops (the "zero relationships" defect). Now
                # resolves through the canonical rg_lookup; on a miss the edge
                # is skipped — never fabricate an RG identifier.
                rg_obj = reference_resource_group(
                    result, adapter_kind, sub_id, rg_name, rg_lookup)
                if rg_obj is not None:
                    obj.add_parent(rg_obj)

            # Relationship: NIC -> VM (parent). The native model hangs NICs
            # under their VM (a VM's Related-Objects view lists its NICs).
            # Resolve the attached VM via properties.virtualMachine.id through
            # vm_lookup — the same phantom-safe recipe disks use. Skip on a
            # miss (unattached NIC, or VM outside the enumerated subs); never
            # fabricate a VM object.
            vm_id = vm_ref.get("id", "")
            if vm_id:
                vm_obj = reference_vm(result, adapter_kind, sub_id, vm_id,
                                      vm_lookup)
                if vm_obj is not None:
                    obj.add_parent(vm_obj)
                else:
                    skipped_vm_refs += 1

            if resource_id:
                nic_objects[resource_id] = obj

        total += len(nics)

    if skipped_vm_refs:
        logger.warning(
            "Skipped %d NIC->VM relationship(s) for VMs not in inventory",
            skipped_vm_refs,
        )
    logger.info("Collected %d network interfaces", total)

    if nic_objects:
        collect_metrics_for_objects(client, nic_objects, "network_interfaces")


def link_network_interfaces_to_vms(result, adapter_kind, vm_lookup):
    """Link each NIC to its VM using the VM's networkProfile (VM-side resolve).

    collect_network_interfaces builds the NIC->VM edge from the NIC's own
    properties.virtualMachine.id back-reference — but the subscription-scoped
    networkInterfaces LIST in Azure Gov frequently OMITS that field, so vm_id
    is empty and the edge never fires (disks bind fine because the disk list
    DOES return managedBy). Confirmed against Prod: the native pak shows NICs
    as children of their VM, so the edge is correct — we just weren't creating
    it.

    The VM API reliably returns properties.networkProfile.networkInterfaces[],
    so we resolve the edge from the VM side instead: for every collected VM,
    attach each NIC it references as a child (nic.add_parent(vm)). Uses
    vm_lookup (raw VM dicts already fetched in adapter.collect()) for the
    networkProfile, and matches NIC references against the AZURE_NW_INTERFACE
    objects already in `result` by resource id (exact match, no identifier
    reconstruction / silent-drop risk). Idempotent with the in-collector edge
    when the back-reference IS present.

    Run AFTER collect_virtual_machines and collect_network_interfaces have
    populated `result`.

    Args:
        result: CollectResult already populated by both collectors.
        adapter_kind: Adapter kind string (unused; kept for call symmetry).
        vm_lookup: {lowercased VM resource id -> raw VM dict}.

    Returns:
        Number of NIC -> VM edges added.
    """
    from constants import (OBJ_VIRTUAL_MACHINE, OBJ_NETWORK_INTERFACE,
                           RES_IDENT_ID)

    # AZURE_NW_INTERFACE objects keyed by lowercased ARM resource id.
    nic_by_id = {}
    # AZURE_VIRTUAL_MACHINE objects keyed by lowercased ARM resource id.
    vm_by_id = {}
    for obj in list(result.objects.values()):
        kind = obj.get_key().object_kind
        if kind == OBJ_NETWORK_INTERFACE:
            for ident in obj.get_key().identifiers.values():
                if ident.key == RES_IDENT_ID and ident.value:
                    nic_by_id[ident.value.lower()] = obj
                    break
        elif kind == OBJ_VIRTUAL_MACHINE:
            for ident in obj.get_key().identifiers.values():
                if ident.key == RES_IDENT_ID and ident.value:
                    vm_by_id[ident.value.lower()] = obj
                    break

    linked = 0
    missing_nic = 0
    for vm_id_lower, raw in vm_lookup.items():
        vm_obj = vm_by_id.get(vm_id_lower)
        if vm_obj is None:
            continue
        nic_refs = (raw.get("properties", {})
                       .get("networkProfile", {})
                       .get("networkInterfaces", []) or [])
        for ref in nic_refs:
            nic_id = (ref.get("id") or "").lower()
            if not nic_id:
                continue
            nic_obj = nic_by_id.get(nic_id)
            if nic_obj is None:
                # NIC referenced by the VM but not in inventory (deleted, or
                # outside the enumerated sub). Skip — never fabricate.
                missing_nic += 1
                continue
            nic_obj.add_parent(vm_obj)
            linked += 1

    logger.info(
        "Linked %d NIC->VM edges from VM networkProfile (%d referenced NICs "
        "not in inventory)", linked, missing_nic,
    )
    return linked
