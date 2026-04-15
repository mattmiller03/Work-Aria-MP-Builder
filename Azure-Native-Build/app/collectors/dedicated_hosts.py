"""Collector for Azure Dedicated Host Groups and Hosts."""

import logging
from collections import Counter

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_HOST_GROUP, OBJ_DEDICATED_HOST, OBJ_RESOURCE_GROUP,
    RES_IDENT_SUB, RES_IDENT_RG, RES_IDENT_REGION, RES_IDENT_ID,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE, AZURE_SERVICE_NAMES,
)
from helpers import make_identifiers, extract_resource_group, safe_property, sanitize_tag_key
from pricing import get_dedicated_host_prices

logger = logging.getLogger(__name__)


def collect_dedicated_hosts(client: AzureClient, result, adapter_kind: str,
                            subscriptions: list, vm_lookup: dict = None):
    """Collect dedicated host groups and hosts across all subscriptions.

    Args:
        client: Azure REST client.
        result: CollectResult to populate.
        adapter_kind: Adapter kind string.
        subscriptions: List of subscription dicts.
        vm_lookup: Optional dict mapping VM resource ID (lowered) to VM dict
                   from the Azure API. Used to enrich hosts with VM size
                   breakdowns and disk info.
    """
    logger.info("Collecting dedicated host groups and hosts")
    if vm_lookup is None:
        vm_lookup = {}
    total_groups = 0
    total_hosts = 0

    # Cache pricing per region — fetched lazily on first use
    region_prices = {}  # region -> {sku_name: hourly_rate}

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
            group_resource_id = group.get("id", "")
            group_location = group.get("location", "")
            group_props = group.get("properties", {})
            group_zones = group.get("zones", [])

            group_obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_HOST_GROUP,
                name=group_name,
                identifiers=make_identifiers([
                    (RES_IDENT_SUB, sub_id),
                    (RES_IDENT_RG, rg_name),
                    (RES_IDENT_REGION, group_location),
                    (RES_IDENT_ID, group_resource_id),
                ]),
            )

            # SERVICE_DESCRIPTORS
            safe_property(group_obj, SD_SUBSCRIPTION, sub_id)
            safe_property(group_obj, SD_RESOURCE_GROUP, rg_name)
            safe_property(group_obj, SD_REGION, group_location)
            safe_property(group_obj, SD_SERVICE, AZURE_SERVICE_NAMES.get(OBJ_HOST_GROUP, ""))

            # Native pak summary properties
            safe_property(group_obj, "summary|name", group_name)
            safe_property(group_obj, "summary|id", group_resource_id)
            safe_property(group_obj, "summary|type", group.get("type", ""))
            safe_property(group_obj, "summary|tags", str(group.get("tags", {})))
            safe_property(group_obj, "summary|platformFaultDomainCount",
                          group_props.get("platformFaultDomainCount", ""))
            safe_property(group_obj, "summary|supportAutomaticPlacement",
                          str(group_props.get("supportAutomaticPlacement", "")))
            safe_property(group_obj, "summary|zones",
                          ", ".join(group_zones) if group_zones else "")

            # Generic summary properties
            safe_property(group_obj, "genericsummary|Name", group_name)
            safe_property(group_obj, "genericsummary|Location", group_location)
            safe_property(group_obj, "genericsummary|Id", group_resource_id)
            safe_property(group_obj, "genericsummary|Sku", "")
            safe_property(group_obj, "genericsummary|Type", group.get("type", ""))

            # Additive custom properties
            safe_property(group_obj, "subscription_id", sub_id)
            safe_property(group_obj, "resource_group", rg_name)
            safe_property(group_obj, "provisioning_state",
                          group_props.get("provisioningState", ""))

            # Tags
            tags = group.get("tags", {})
            if tags:
                for key, value in tags.items():
                    safe_property(group_obj, f"tag_{sanitize_tag_key(key)}", value)

            # Relationship: Host Group -> Resource Group
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
                host_resource_id = host.get("id", "")
                host_location = host.get("location", "")
                host_props = host.get("properties", {})
                host_sku = host.get("sku", {})
                instance_view = host_props.get("instanceView", {})

                host_obj = result.object(
                    adapter_kind=adapter_kind,
                    object_kind=OBJ_DEDICATED_HOST,
                    name=host_name,
                    identifiers=make_identifiers([
                        (RES_IDENT_SUB, sub_id),
                        (RES_IDENT_RG, rg_name),
                        (RES_IDENT_REGION, host_location),
                        (RES_IDENT_ID, host_resource_id),
                        ("hostGroupName", group_name),
                    ]),
                )

                # SERVICE_DESCRIPTORS
                safe_property(host_obj, SD_SUBSCRIPTION, sub_id)
                safe_property(host_obj, SD_RESOURCE_GROUP, rg_name)
                safe_property(host_obj, SD_REGION, host_location)
                safe_property(host_obj, SD_SERVICE, AZURE_SERVICE_NAMES.get(OBJ_DEDICATED_HOST, ""))

                # Native pak summary properties
                safe_property(host_obj, "summary|name", host_name)
                safe_property(host_obj, "summary|id", host_resource_id)
                safe_property(host_obj, "summary|type", host.get("type", ""))
                safe_property(host_obj, "summary|tags", str(host.get("tags", {})))
                safe_property(host_obj, "summary|hostId", host_props.get("hostId", ""))
                safe_property(host_obj, "summary|platformFaultDomain",
                              host_props.get("platformFaultDomain", ""))
                safe_property(host_obj, "summary|autoReplaceOnFailure",
                              str(host_props.get("autoReplaceOnFailure", "")))
                safe_property(host_obj, "summary|provisioningState",
                              host_props.get("provisioningState", ""))
                safe_property(host_obj, "summary|regionName", host_location)
                safe_property(host_obj, "summary|provisioningTime",
                              host_props.get("provisioningTime", ""))
                safe_property(host_obj, "summary|instanceView", str(instance_view))
                safe_property(host_obj, "summary|licenseTypes",
                              str(host_props.get("licenseType", "")))

                # Generic summary properties
                safe_property(host_obj, "genericsummary|Name", host_name)
                safe_property(host_obj, "genericsummary|Location", host_location)
                safe_property(host_obj, "genericsummary|Id", host_resource_id)
                safe_property(host_obj, "genericsummary|Sku", host_sku.get("name", ""))
                safe_property(host_obj, "genericsummary|Type", host.get("type", ""))

                # Additive custom properties
                safe_property(host_obj, "subscription_id", sub_id)
                safe_property(host_obj, "resource_group", rg_name)
                safe_property(host_obj, "host_group_name", group_name)
                safe_property(host_obj, "sku_name", host_sku.get("name", ""))

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

                # --- VM size breakdown from vm_lookup ---
                vm_size_counts = Counter()
                vm_disk_skus = set()
                for vm_id in vm_ids:
                    vm_data = vm_lookup.get(vm_id.lower())
                    if vm_data:
                        vm_hw = vm_data.get("properties", {}).get(
                            "hardwareProfile", {})
                        size = vm_hw.get("vmSize", "unknown")
                        vm_size_counts[size] += 1

                        # Collect disk SKUs from this VM's storage profile
                        storage = vm_data.get("properties", {}).get(
                            "storageProfile", {})
                        os_managed = storage.get("osDisk", {}).get(
                            "managedDisk", {})
                        os_sku = os_managed.get("storageAccountType", "")
                        if os_sku:
                            vm_disk_skus.add(os_sku)
                        for dd in storage.get("dataDisks", []):
                            dd_sku = dd.get("managedDisk", {}).get(
                                "storageAccountType", "")
                            if dd_sku:
                                vm_disk_skus.add(dd_sku)

                # VM size summary: "Standard_D2s_v3 x4, Standard_D4s_v3 x2"
                size_parts = [f"{size} x{cnt}"
                              for size, cnt in vm_size_counts.most_common()]
                safe_property(host_obj, "vm_size_summary",
                              ", ".join(size_parts) if size_parts else "")
                safe_property(host_obj, "vm_size_distinct_count",
                              len(vm_size_counts))

                # --- VM memory aggregation per host ---
                # Calculate total allocated memory across all VMs on this host
                total_memory_gb = 0.0
                vm_memory_details = []
                for vm_id in vm_ids:
                    vm_data = vm_lookup.get(vm_id.lower())
                    if vm_data:
                        vm_hw = vm_data.get("properties", {}).get(
                            "hardwareProfile", {})
                        size = vm_hw.get("vmSize", "unknown")
                        vm_name_short = vm_id.split("/")[-1] if vm_id else ""
                        # Try to get memory from instance view if available
                        iv = vm_data.get("properties", {}).get("instanceView", {})
                        # Azure doesn't include memory in the VM API directly —
                        # we use the VM size to memory mapping from the SKU API.
                        # For now, record the size; memory_gb is enriched below.
                        vm_memory_details.append((vm_name_short, size))

                # Use Azure compute resource SKUs to get memory per VM size
                # Cache SKU info at the subscription level
                if vm_ids and not hasattr(collect_dedicated_hosts, '_sku_cache'):
                    collect_dedicated_hosts._sku_cache = {}
                if vm_ids and sub_id not in getattr(collect_dedicated_hosts, '_sku_cache', {}):
                    try:
                        skus = client.get_all(
                            path=f"/subscriptions/{sub_id}/providers/Microsoft.Compute/skus",
                            api_version="2021-07-01",
                            params={"$filter": f"location eq '{host_location}'"},
                        )
                        sku_memory = {}
                        for sku in skus:
                            if sku.get("resourceType") == "virtualMachines":
                                sku_name_val = sku.get("name", "")
                                for cap in sku.get("capabilities", []):
                                    if cap.get("name") == "MemoryGB":
                                        try:
                                            sku_memory[sku_name_val] = float(cap["value"])
                                        except (ValueError, KeyError):
                                            pass
                        collect_dedicated_hosts._sku_cache[sub_id] = sku_memory
                        logger.info("Cached %d VM SKU memory mappings for %s",
                                    len(sku_memory), host_location)
                    except Exception as e:
                        logger.warning("Failed to fetch VM SKUs for memory mapping: %s", e)
                        collect_dedicated_hosts._sku_cache[sub_id] = {}

                sku_memory = getattr(collect_dedicated_hosts, '_sku_cache', {}).get(sub_id, {})
                memory_breakdown = []
                for vm_name_short, size in vm_memory_details:
                    mem_gb = sku_memory.get(size, 0)
                    total_memory_gb += mem_gb
                    if mem_gb:
                        memory_breakdown.append(f"{vm_name_short}: {mem_gb}GB ({size})")

                safe_property(host_obj, "total_vm_memory_gb", total_memory_gb)
                safe_property(host_obj, "vm_memory_breakdown",
                              ", ".join(memory_breakdown) if memory_breakdown else "")

                # Get host SKU memory capacity from the same SKU cache
                # Dedicated host SKU names map to host-level capacity
                host_sku_name = host_sku.get("name", "")
                host_memory_gb = 0.0
                if host_sku_name:
                    # Try fetching dedicated host SKU capacity
                    if not hasattr(collect_dedicated_hosts, '_host_sku_cache'):
                        collect_dedicated_hosts._host_sku_cache = {}
                    cache_key = f"{sub_id}_{host_location}"
                    if cache_key not in collect_dedicated_hosts._host_sku_cache:
                        try:
                            host_skus = client.get_all(
                                path=f"/subscriptions/{sub_id}/providers/Microsoft.Compute/skus",
                                api_version="2021-07-01",
                                params={"$filter": f"location eq '{host_location}'"},
                            )
                            host_mem_map = {}
                            for sku in host_skus:
                                if sku.get("resourceType") == "dedicatedHosts":
                                    for cap in sku.get("capabilities", []):
                                        if cap.get("name") == "MemoryGB":
                                            try:
                                                host_mem_map[sku.get("name", "")] = float(cap["value"])
                                            except (ValueError, KeyError):
                                                pass
                            collect_dedicated_hosts._host_sku_cache[cache_key] = host_mem_map
                        except Exception as e:
                            logger.warning("Failed to fetch host SKU memory: %s", e)
                            collect_dedicated_hosts._host_sku_cache[cache_key] = {}

                    host_memory_gb = collect_dedicated_hosts._host_sku_cache.get(
                        cache_key, {}).get(host_sku_name, 0)

                safe_property(host_obj, "host_memory_capacity_gb", host_memory_gb)
                if host_memory_gb > 0:
                    memory_utilization = round((total_memory_gb / host_memory_gb) * 100, 1)
                    safe_property(host_obj, "memory_utilization_pct", memory_utilization)
                    safe_property(host_obj, "memory_available_gb",
                                  round(host_memory_gb - total_memory_gb, 1))

                # Disk SKUs across all VMs on this host
                safe_property(host_obj, "vm_disk_skus",
                              ", ".join(sorted(vm_disk_skus))
                              if vm_disk_skus else "")

                # Instance view — available capacity and health

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

                    # Capacity summary: "Standard_D2s_v3: 12, Standard_D4s_v3: 6"
                    capacity_parts = [
                        f"{s.get('vmSize', '')}: {s.get('count', 0)}"
                        for s in allocatable if s.get("vmSize")
                    ]
                    safe_property(host_obj, "allocatable_vm_summary",
                                  ", ".join(capacity_parts))

                # --- Hourly rate from Azure Retail Prices API ---
                sku_name = host_sku.get("name", "")
                price_region = host_location.lower()
                if price_region and price_region not in region_prices:
                    try:
                        region_prices[price_region] = (
                            get_dedicated_host_prices(price_region))
                    except Exception as e:
                        logger.warning("Pricing fetch failed for %s: %s",
                                       price_region, e)
                        region_prices[price_region] = {}

                hourly_rate = region_prices.get(price_region, {}).get(
                    sku_name, 0.0)
                safe_property(host_obj, "hourly_rate", hourly_rate)
                safe_property(host_obj, "monthly_rate_estimate",
                              round(hourly_rate * 730, 2))

                # Tags
                host_tags = host.get("tags", {})
                if host_tags:
                    for key, value in host_tags.items():
                        safe_property(host_obj, f"tag_{sanitize_tag_key(key)}", value)

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

                    # Find the existing host object — use the same
                    # identifiers as the primary collector.  We don't
                    # have the full resource_id / location here, so
                    # build them from what the group detail gives us.
                    iv_host_id = iv_host.get("assetId", "")
                    iv_location = group_detail.get("location", "")
                    host_obj = result.object(
                        adapter_kind=adapter_kind,
                        object_kind=OBJ_DEDICATED_HOST,
                        name=host_name,
                        identifiers=make_identifiers([
                            (RES_IDENT_SUB, sub_id),
                            (RES_IDENT_RG, rg_name),
                            (RES_IDENT_REGION, iv_location),
                            (RES_IDENT_ID, iv_host_id),
                            ("hostGroupName", group_name),
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
