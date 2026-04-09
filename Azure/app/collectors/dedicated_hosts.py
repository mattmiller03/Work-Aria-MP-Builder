"""Collector for Azure Dedicated Host Groups and Hosts."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_HOST_GROUP, OBJ_DEDICATED_HOST, OBJ_RESOURCE_GROUP,
)
from helpers import make_identifiers, extract_resource_group, safe_property

logger = logging.getLogger(__name__)


def collect_dedicated_hosts(client: AzureClient, result, adapter_kind: str,
                            subscriptions: list):
    """Collect dedicated host groups and hosts across all subscriptions."""
    logger.info("Collecting dedicated host groups and hosts")
    total_groups = 0
    total_hosts = 0

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]

        # List all host groups in subscription
        host_groups = client.get_all(
            path=f"/subscriptions/{sub_id}/providers/Microsoft.Compute/hostGroups",
            api_version=API_VERSIONS["host_groups"],
        )

        for group in host_groups:
            group_name = group["name"]
            rg_name = extract_resource_group(group.get("id", ""))
            group_props = group.get("properties", {})

            group_obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_HOST_GROUP,
                name=group_name,
                identifiers=make_identifiers([
                    ("subscription_id", sub_id),
                    ("resource_group", rg_name),
                    ("host_group_name", group_name),
                ]),
            )

            safe_property(group_obj, "host_group_name", group_name)
            safe_property(group_obj, "resource_id", group.get("id", ""))
            safe_property(group_obj, "location", group.get("location", ""))
            safe_property(group_obj, "subscription_id", sub_id)
            safe_property(group_obj, "resource_group", rg_name)
            safe_property(group_obj, "platform_fault_domain_count",
                          group_props.get("platformFaultDomainCount", ""))
            safe_property(group_obj, "support_automatic_placement",
                          str(group_props.get("supportAutomaticPlacement", "")))
            safe_property(group_obj, "provisioning_state",
                          group_props.get("provisioningState", ""))

            # Tags
            tags = group.get("tags", {})
            if tags:
                for key, value in tags.items():
                    safe_property(group_obj, f"tag_{key}", value)

            # Relationship: Host Group -> Resource Group
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
                group_obj.add_parent(rg_obj)

            total_groups += 1

            # Now get each host in this group with instance view
            hosts = client.get_all(
                path=(f"/subscriptions/{sub_id}/resourceGroups/{rg_name}"
                      f"/providers/Microsoft.Compute/hostGroups/{group_name}/hosts"),
                api_version=API_VERSIONS["dedicated_hosts"],
            )

            for host in hosts:
                host_name = host["name"]
                host_props = host.get("properties", {})
                host_sku = host.get("sku", {})

                host_obj = result.object(
                    adapter_kind=adapter_kind,
                    object_kind=OBJ_DEDICATED_HOST,
                    name=host_name,
                    identifiers=make_identifiers([
                        ("subscription_id", sub_id),
                        ("host_group_name", group_name),
                        ("host_name", host_name),
                    ]),
                )

                safe_property(host_obj, "host_name", host_name)
                safe_property(host_obj, "resource_id", host.get("id", ""))
                safe_property(host_obj, "location", host.get("location", ""))
                safe_property(host_obj, "subscription_id", sub_id)
                safe_property(host_obj, "resource_group", rg_name)
                safe_property(host_obj, "host_group_name", group_name)
                safe_property(host_obj, "sku_name", host_sku.get("name", ""))
                safe_property(host_obj, "platform_fault_domain",
                              host_props.get("platformFaultDomain", ""))
                safe_property(host_obj, "auto_replace_on_failure",
                              str(host_props.get("autoReplaceOnFailure", "")))
                safe_property(host_obj, "host_id", host_props.get("hostId", ""))
                safe_property(host_obj, "provisioning_state",
                              host_props.get("provisioningState", ""))
                safe_property(host_obj, "provisioning_time",
                              host_props.get("provisioningTime", ""))

                # VMs placed on this host
                vms = host_props.get("virtualMachines", [])
                vm_ids = [vm.get("id", "") for vm in vms]
                safe_property(host_obj, "vm_count", len(vms))
                safe_property(host_obj, "vm_ids", ", ".join(vm_ids))

                # Extract VM names for readability
                vm_names = []
                for vm_id in vm_ids:
                    parts = vm_id.split("/")
                    if parts:
                        vm_names.append(parts[-1])
                safe_property(host_obj, "vm_names", ", ".join(vm_names))

                # Instance view — available capacity and health
                instance_view = host_props.get("instanceView", {})

                # Health status
                statuses = instance_view.get("statuses", [])
                health_state = ""
                for status in statuses:
                    code = status.get("code", "")
                    if code.startswith("HealthState/"):
                        health_state = code.replace("HealthState/", "")
                safe_property(host_obj, "health_state", health_state)

                # Available capacity — per VM size
                available = instance_view.get("availableCapacity", {})
                allocatable = available.get("allocatableVMs", [])

                # Store each VM size's available count as a property
                for slot in allocatable:
                    vm_size = slot.get("vmSize", "")
                    count = slot.get("count", 0)
                    if vm_size:
                        # Create a property like "available_Standard_D2s_v3" = "28"
                        safe_property(host_obj, f"available_{vm_size}", count)

                # Summary: total allocatable (smallest VM size = max slots)
                if allocatable:
                    max_slots = max(slot.get("count", 0) for slot in allocatable)
                    safe_property(host_obj, "max_available_slots", max_slots)
                    # The smallest VM size gives the theoretical max
                    smallest_vm = allocatable[0] if allocatable else {}
                    safe_property(host_obj, "smallest_vm_size",
                                  smallest_vm.get("vmSize", ""))
                    safe_property(host_obj, "smallest_vm_available",
                                  smallest_vm.get("count", 0))

                # Tags
                host_tags = host.get("tags", {})
                if host_tags:
                    for key, value in host_tags.items():
                        safe_property(host_obj, f"tag_{key}", value)

                # Relationship: Host -> Host Group (parent)
                host_obj.add_parent(group_obj)

                total_hosts += 1

    logger.info("Collected %d host groups, %d dedicated hosts",
                total_groups, total_hosts)


def collect_dedicated_hosts_with_instance_view(client: AzureClient, result,
                                                adapter_kind: str,
                                                subscriptions: list):
    """Collect dedicated hosts with full instance view for capacity data.

    This makes an additional API call per host to get the instance view,
    which contains the available capacity breakdown. Use this if the
    list call doesn't include instance view data.
    """
    logger.info("Enriching dedicated hosts with instance view")

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]

        host_groups = client.get_all(
            path=f"/subscriptions/{sub_id}/providers/Microsoft.Compute/hostGroups",
            api_version=API_VERSIONS["host_groups"],
        )

        for group in host_groups:
            group_name = group["name"]
            rg_name = extract_resource_group(group.get("id", ""))

            # Get host group with instance view (includes per-host capacity)
            try:
                group_detail = client.get(
                    path=(f"/subscriptions/{sub_id}/resourceGroups/{rg_name}"
                          f"/providers/Microsoft.Compute/hostGroups/{group_name}"),
                    api_version=API_VERSIONS["host_groups"],
                    params={"$expand": "instanceView"},
                )

                instance_view = group_detail.get("properties", {}).get("instanceView", {})
                iv_hosts = instance_view.get("hosts", [])

                for iv_host in iv_hosts:
                    host_name = iv_host.get("name", "")
                    if not host_name:
                        continue

                    # Find the existing host object
                    host_obj = result.object(
                        adapter_kind=adapter_kind,
                        object_kind=OBJ_DEDICATED_HOST,
                        name=host_name,
                        identifiers=make_identifiers([
                            ("subscription_id", sub_id),
                            ("host_group_name", group_name),
                            ("host_name", host_name),
                        ]),
                    )

                    # Update with instance view capacity data
                    available = iv_host.get("availableCapacity", {})
                    allocatable = available.get("allocatableVMs", [])

                    for slot in allocatable:
                        vm_size = slot.get("vmSize", "")
                        count = slot.get("count", 0)
                        if vm_size:
                            safe_property(host_obj, f"available_{vm_size}", count)

                    if allocatable:
                        max_slots = max(slot.get("count", 0) for slot in allocatable)
                        safe_property(host_obj, "max_available_slots", max_slots)

            except Exception as e:
                logger.warning("Failed to get instance view for host group %s: %s",
                               group_name, e)
