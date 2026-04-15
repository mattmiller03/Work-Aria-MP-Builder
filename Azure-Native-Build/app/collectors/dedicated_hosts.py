"""Collector for Azure Dedicated Host Groups and Hosts."""

import logging
from collections import Counter
from datetime import datetime, timedelta

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

    # Subscription-level caches for enrichment APIs
    cost_cache = {}      # sub_id -> {resource_id_lower: {cost, currency, cost_30d}}
    advisor_cache = {}   # sub_id -> {resource_id_lower: {count, descriptions, impact, categories}}

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]

        # --- Subscription-level: Cost Management (API 1) ---
        if sub_id not in cost_cache:
            try:
                # MonthToDate actual cost
                mtd_body = {
                    "type": "ActualCost",
                    "timeframe": "MonthToDate",
                    "dataset": {
                        "granularity": "None",
                        "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
                        "filter": {
                            "dimensions": {
                                "name": "ResourceType",
                                "operator": "In",
                                "values": ["Microsoft.Compute/hostGroups/hosts"],
                            }
                        },
                        "grouping": [{"type": "Dimension", "name": "ResourceId"}],
                    },
                }
                mtd_response = client.post(
                    path=f"/subscriptions/{sub_id}/providers/Microsoft.CostManagement/query",
                    api_version=API_VERSIONS["cost_management"],
                    body=mtd_body,
                )

                # Last 30 days actual cost
                now = datetime.utcnow()
                thirty_days_ago = now - timedelta(days=30)
                l30d_body = {
                    "type": "ActualCost",
                    "timeframe": "Custom",
                    "timePeriod": {
                        "from": thirty_days_ago.strftime("%Y-%m-%dT00:00:00Z"),
                        "to": now.strftime("%Y-%m-%dT23:59:59Z"),
                    },
                    "dataset": {
                        "granularity": "None",
                        "aggregation": {"totalCost": {"name": "Cost", "function": "Sum"}},
                        "filter": {
                            "dimensions": {
                                "name": "ResourceType",
                                "operator": "In",
                                "values": ["Microsoft.Compute/hostGroups/hosts"],
                            }
                        },
                        "grouping": [{"type": "Dimension", "name": "ResourceId"}],
                    },
                }
                l30d_response = client.post(
                    path=f"/subscriptions/{sub_id}/providers/Microsoft.CostManagement/query",
                    api_version=API_VERSIONS["cost_management"],
                    body=l30d_body,
                )

                # Parse cost responses — columns: [Cost, ResourceId]
                # Find column indices
                sub_costs = {}
                mtd_columns = mtd_response.get("properties", {}).get("columns", [])
                mtd_rows = mtd_response.get("properties", {}).get("rows", [])
                cost_idx = next((i for i, c in enumerate(mtd_columns)
                                 if c.get("name", "").lower() == "cost"), 0)
                rid_idx = next((i for i, c in enumerate(mtd_columns)
                                if c.get("name", "").lower() == "resourceid"), 1)
                currency_idx = next((i for i, c in enumerate(mtd_columns)
                                     if c.get("name", "").lower() == "currency"), None)

                for row in mtd_rows:
                    res_id = str(row[rid_idx]).lower()
                    cost_val = float(row[cost_idx]) if row[cost_idx] is not None else 0.0
                    currency = str(row[currency_idx]) if currency_idx is not None and currency_idx < len(row) else "USD"
                    sub_costs[res_id] = {
                        "cost_month_to_date": cost_val,
                        "cost_currency": currency,
                    }

                # Parse last 30 days
                l30d_columns = l30d_response.get("properties", {}).get("columns", [])
                l30d_rows = l30d_response.get("properties", {}).get("rows", [])
                l30d_cost_idx = next((i for i, c in enumerate(l30d_columns)
                                      if c.get("name", "").lower() == "cost"), 0)
                l30d_rid_idx = next((i for i, c in enumerate(l30d_columns)
                                     if c.get("name", "").lower() == "resourceid"), 1)

                for row in l30d_rows:
                    res_id = str(row[l30d_rid_idx]).lower()
                    cost_val = float(row[l30d_cost_idx]) if row[l30d_cost_idx] is not None else 0.0
                    if res_id in sub_costs:
                        sub_costs[res_id]["cost_last_30_days"] = cost_val
                    else:
                        sub_costs[res_id] = {
                            "cost_month_to_date": 0.0,
                            "cost_currency": "USD",
                            "cost_last_30_days": cost_val,
                        }

                cost_cache[sub_id] = sub_costs
                logger.info("Cached cost data for %d dedicated hosts in subscription %s",
                            len(sub_costs), sub_id)
            except Exception as e:
                logger.warning("Cost Management query failed for subscription %s: %s",
                               sub_id, e)
                cost_cache[sub_id] = {}

        # --- Subscription-level: Advisor Recommendations (API 4) ---
        if sub_id not in advisor_cache:
            try:
                recommendations = client.get_all(
                    path=f"/subscriptions/{sub_id}/providers/Microsoft.Advisor/recommendations",
                    api_version=API_VERSIONS["advisor"],
                    params={"$filter": "ResourceType eq 'Microsoft.Compute/hostGroups/hosts'"},
                )

                sub_advisor = {}
                impact_order = {"High": 3, "Medium": 2, "Low": 1}
                for rec in recommendations:
                    rec_props = rec.get("properties", {})
                    affected_id = rec_props.get("resourceMetadata", {}).get(
                        "resourceId", "").lower()
                    if not affected_id:
                        # Fall back to the recommendation's own resource path
                        affected_id = rec.get("id", "").lower()
                        # Extract the host resource ID from the recommendation ID
                        # Format: .../hostGroups/{group}/hosts/{host}/providers/Microsoft.Advisor/...
                        parts = affected_id.split("/providers/microsoft.advisor/")
                        if parts:
                            affected_id = parts[0]

                    if affected_id not in sub_advisor:
                        sub_advisor[affected_id] = {
                            "count": 0,
                            "descriptions": [],
                            "impact": "",
                            "categories": set(),
                        }

                    entry = sub_advisor[affected_id]
                    entry["count"] += 1
                    short_desc = rec_props.get("shortDescription", {}).get(
                        "solution", rec_props.get("shortDescription", {}).get(
                            "problem", ""))
                    if short_desc:
                        entry["descriptions"].append(short_desc)
                    impact = rec_props.get("impact", "")
                    if impact_order.get(impact, 0) > impact_order.get(entry["impact"], 0):
                        entry["impact"] = impact
                    category = rec_props.get("category", "")
                    if category:
                        entry["categories"].add(category)

                advisor_cache[sub_id] = sub_advisor
                logger.info("Cached %d advisor-affected hosts in subscription %s",
                            len(sub_advisor), sub_id)
            except Exception as e:
                logger.warning("Advisor query failed for subscription %s: %s",
                               sub_id, e)
                advisor_cache[sub_id] = {}

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
                    safe_property(group_obj, f"summary|tags|{key}", value)

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
                        safe_property(host_obj, f"summary|tags|{key}", value)

                # =============================================================
                # Enrichment APIs — each in its own try/except
                # =============================================================

                # --- API 1: Cost Management (from subscription-level cache) ---
                try:
                    host_costs = cost_cache.get(sub_id, {}).get(
                        host_resource_id.lower(), {})
                    safe_property(host_obj, "cost_month_to_date",
                                  host_costs.get("cost_month_to_date", 0.0))
                    safe_property(host_obj, "cost_currency",
                                  host_costs.get("cost_currency", ""))
                    safe_property(host_obj, "cost_last_30_days",
                                  host_costs.get("cost_last_30_days", 0.0))
                except Exception as e:
                    logger.warning("Cost enrichment failed for host %s: %s",
                                   host_name, e)

                # --- API 2: Resource Health (per host) ---
                try:
                    health_statuses = client.get_all(
                        path=f"{host_resource_id}/providers/Microsoft.ResourceHealth/availabilityStatuses",
                        api_version=API_VERSIONS["resource_health"],
                    )
                    if health_statuses:
                        latest = health_statuses[0]
                        h_props = latest.get("properties", {})
                        safe_property(host_obj, "health_availability_state",
                                      h_props.get("availabilityState", "Unknown"))
                        safe_property(host_obj, "health_detailed_status",
                                      h_props.get("detailedStatus", ""))
                        safe_property(host_obj, "health_reason_type",
                                      h_props.get("reasonType", ""))
                        safe_property(host_obj, "health_occurred_time",
                                      h_props.get("occuredTime",
                                                   h_props.get("occurredTime", "")))
                        safe_property(host_obj, "health_summary",
                                      h_props.get("summary", ""))
                    else:
                        safe_property(host_obj, "health_availability_state", "Unknown")
                        safe_property(host_obj, "health_detailed_status", "")
                        safe_property(host_obj, "health_reason_type", "")
                        safe_property(host_obj, "health_occurred_time", "")
                        safe_property(host_obj, "health_summary", "")
                except Exception as e:
                    logger.warning("Resource Health query failed for host %s: %s",
                                   host_name, e)

                # --- API 3: Maintenance (per host) ---
                try:
                    maintenance_updates = client.get_all(
                        path=f"{host_resource_id}/providers/Microsoft.Maintenance/updates",
                        api_version=API_VERSIONS["maintenance"],
                    )
                    if maintenance_updates:
                        safe_property(host_obj, "maintenance_pending", True)
                        # Use the first (most relevant) update
                        m_props = maintenance_updates[0].get("properties", {})
                        safe_property(host_obj, "maintenance_impact_type",
                                      m_props.get("impactType", "None"))
                        safe_property(host_obj, "maintenance_status",
                                      m_props.get("status", ""))
                        safe_property(host_obj, "maintenance_not_before",
                                      m_props.get("notBefore", ""))
                        safe_property(host_obj, "maintenance_not_after",
                                      m_props.get("notAfter", ""))
                    else:
                        safe_property(host_obj, "maintenance_pending", False)
                        safe_property(host_obj, "maintenance_impact_type", "None")
                        safe_property(host_obj, "maintenance_status", "")
                        safe_property(host_obj, "maintenance_not_before", "")
                        safe_property(host_obj, "maintenance_not_after", "")
                except Exception as e:
                    logger.warning("Maintenance query failed for host %s: %s",
                                   host_name, e)

                # --- API 4: Advisor (from subscription-level cache) ---
                try:
                    host_advisor = advisor_cache.get(sub_id, {}).get(
                        host_resource_id.lower(), {})
                    safe_property(host_obj, "advisor_recommendation_count",
                                  host_advisor.get("count", 0))
                    descs = host_advisor.get("descriptions", [])
                    safe_property(host_obj, "advisor_recommendations",
                                  ", ".join(descs) if descs else "")
                    safe_property(host_obj, "advisor_impact",
                                  host_advisor.get("impact", ""))
                    cats = host_advisor.get("categories", set())
                    safe_property(host_obj, "advisor_category",
                                  ", ".join(sorted(cats)) if cats else "")
                except Exception as e:
                    logger.warning("Advisor enrichment failed for host %s: %s",
                                   host_name, e)

                # --- API 5: Activity Log (per host — last 7 days) ---
                try:
                    activity_start = (datetime.utcnow() - timedelta(days=7)).strftime(
                        "%Y-%m-%dT%H:%M:%SZ")
                    activity_events = client.get_all(
                        path=(f"/subscriptions/{sub_id}/providers"
                              f"/Microsoft.Insights/eventtypes/management/values"),
                        api_version=API_VERSIONS["activity_log"],
                        params={
                            "$filter": (f"eventTimestamp ge '{activity_start}'"
                                        f" and resourceUri eq '{host_resource_id}'"),
                        },
                    )
                    safe_property(host_obj, "recent_operations_count",
                                  len(activity_events))
                    if activity_events:
                        # Events are returned newest-first
                        latest_event = activity_events[0]
                        evt_auth = latest_event.get("authorization", {})
                        safe_property(host_obj, "last_operation",
                                      latest_event.get("operationName", {}).get(
                                          "localizedValue",
                                          latest_event.get("operationName", {}).get(
                                              "value", "")))
                        safe_property(host_obj, "last_operation_time",
                                      latest_event.get("eventTimestamp", ""))
                        safe_property(host_obj, "last_operation_status",
                                      latest_event.get("status", {}).get(
                                          "localizedValue",
                                          latest_event.get("status", {}).get(
                                              "value", "")))
                        safe_property(host_obj, "last_operation_caller",
                                      latest_event.get("caller", ""))
                    else:
                        safe_property(host_obj, "last_operation", "")
                        safe_property(host_obj, "last_operation_time", "")
                        safe_property(host_obj, "last_operation_status", "")
                        safe_property(host_obj, "last_operation_caller", "")
                except Exception as e:
                    logger.warning("Activity Log query failed for host %s: %s",
                                   host_name, e)

                # =============================================================
                # Sources 6-10: Computed metrics & additional enrichment
                # =============================================================

                # --- Source 10: Missing ARM properties ---
                safe_property(host_obj, "time_created",
                              host_props.get("timeCreated", ""))
                safe_property(host_obj, "sku_tier",
                              host_sku.get("tier", ""))
                safe_property(host_obj, "sku_capacity",
                              host_sku.get("capacity", ""))
                # Health status time and message from instanceView statuses
                health_status_time = ""
                health_status_message = ""
                for status in statuses:
                    s_time = status.get("time", "")
                    s_msg = status.get("message", "")
                    if s_time:
                        health_status_time = s_time
                    if s_msg:
                        health_status_message = s_msg
                safe_property(host_obj, "health_status_time",
                              health_status_time)
                safe_property(host_obj, "health_status_message",
                              health_status_message)

                # --- Sources 6-9: Computed metrics enrichment ---
                try:
                    _enrich_host_with_computed_metrics(
                        host_obj=host_obj,
                        host_resource_id=host_resource_id,
                        vm_lookup=vm_lookup,
                        vm_ids=vm_ids,
                        client=client,
                        sub_id=sub_id,
                        sku_memory=sku_memory,
                        host_sku_name=host_sku_name,
                        host_location=host_location,
                    )
                except Exception as e:
                    logger.warning("Sources 6-9 enrichment failed for host %s: %s",
                                   host_name, e)

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


# ---------------------------------------------------------------------------
# Source 6-10 enrichment helpers — separate from the main collector to avoid
# conflicts with the other agent editing the main function.
# ---------------------------------------------------------------------------

def _build_vcpu_caches(client, sub_id, host_location):
    """Build separate vCPU caches for VM SKUs and dedicated host SKUs.

    Uses a separate cache from the main collector's _sku_cache to avoid
    conflicts.  Fetches the compute/skus API and extracts vCPU counts
    for both virtualMachines (capability: "vCPUs") and dedicatedHosts
    (capability: "Cores").

    Returns:
        (vm_vcpu_map, host_vcpu_map): Dicts mapping SKU name to vCPU count.
    """
    if not hasattr(_build_vcpu_caches, '_vm_vcpu_cache'):
        _build_vcpu_caches._vm_vcpu_cache = {}
    if not hasattr(_build_vcpu_caches, '_host_vcpu_cache'):
        _build_vcpu_caches._host_vcpu_cache = {}

    cache_key = f"{sub_id}_{host_location}"
    if cache_key not in _build_vcpu_caches._vm_vcpu_cache:
        vm_vcpu = {}
        host_vcpu = {}
        try:
            skus = client.get_all(
                path=f"/subscriptions/{sub_id}/providers/Microsoft.Compute/skus",
                api_version="2021-07-01",
                params={"$filter": f"location eq '{host_location}'"},
            )
            for sku in skus:
                sku_name_val = sku.get("name", "")
                if sku.get("resourceType") == "virtualMachines":
                    for cap in sku.get("capabilities", []):
                        if cap.get("name") == "vCPUs":
                            try:
                                vm_vcpu[sku_name_val] = int(cap["value"])
                            except (ValueError, KeyError):
                                pass
                elif sku.get("resourceType") == "dedicatedHosts":
                    for cap in sku.get("capabilities", []):
                        if cap.get("name") == "Cores":
                            try:
                                host_vcpu[sku_name_val] = int(cap["value"])
                            except (ValueError, KeyError):
                                pass
            logger.info("Cached vCPU data: %d VM SKUs, %d host SKUs for %s",
                        len(vm_vcpu), len(host_vcpu), host_location)
        except Exception as e:
            logger.warning("Failed to fetch vCPU SKU data for %s: %s",
                           host_location, e)
        _build_vcpu_caches._vm_vcpu_cache[cache_key] = vm_vcpu
        _build_vcpu_caches._host_vcpu_cache[cache_key] = host_vcpu

    return (
        _build_vcpu_caches._vm_vcpu_cache.get(cache_key, {}),
        _build_vcpu_caches._host_vcpu_cache.get(cache_key, {}),
    )


def _collect_host_aggregated_metrics(host_obj, vm_ids, vm_lookup, client):
    """Aggregate VM-level Azure Monitor metrics to create host-level view.

    For each VM placed on this host, fetches CPU, memory, network, and disk
    metrics from Azure Monitor and aggregates them into host-level values.

    Performance note: This makes one API call per VM.  The main adapter
    already collects VM metrics in the VM collector, but those result objects
    are not easily accessible here, so we make dedicated calls and log
    the count for performance monitoring.
    """
    cpu_values = []
    memory_values = []
    net_in_total = 0.0
    net_out_total = 0.0
    disk_read_total = 0.0
    disk_write_total = 0.0

    # Collect the set of VM IDs that exist in our lookup
    vm_ids_to_fetch = [
        vm_id for vm_id in vm_ids
        if vm_lookup.get(vm_id.lower())
    ]

    if not vm_ids_to_fetch:
        return

    logger.info("Fetching metrics for %d VMs across dedicated hosts",
                len(vm_ids_to_fetch))

    for vm_id in vm_ids_to_fetch:
        try:
            metrics = client.get_metrics(
                resource_id=vm_id,
                metric_names=[
                    "Percentage CPU",
                    "Available Memory Bytes",
                    "Network In Total",
                    "Network Out Total",
                    "Disk Read Bytes",
                    "Disk Write Bytes",
                ],
                aggregation="Average",
                timespan="PT1H",
            )
            cpu = metrics.get("Percentage CPU")
            if cpu is not None:
                cpu_values.append(cpu)
            mem = metrics.get("Available Memory Bytes")
            if mem is not None:
                memory_values.append(mem)
            net_in = metrics.get("Network In Total")
            if net_in is not None:
                net_in_total += net_in
            net_out = metrics.get("Network Out Total")
            if net_out is not None:
                net_out_total += net_out
            disk_read = metrics.get("Disk Read Bytes")
            if disk_read is not None:
                disk_read_total += disk_read
            disk_write = metrics.get("Disk Write Bytes")
            if disk_write is not None:
                disk_write_total += disk_write
        except Exception as e:
            logger.debug("Metrics fetch failed for VM %s: %s",
                         vm_id.split("/")[-1], e)

    # Set aggregated metrics on the host object
    if cpu_values:
        host_obj.with_property("host_cpu_avg",
                               round(sum(cpu_values) / len(cpu_values), 2))
        host_obj.with_property("host_cpu_max", round(max(cpu_values), 2))
        host_obj.with_property("host_cpu_min", round(min(cpu_values), 2))
    host_obj.with_property("host_network_in_total", net_in_total)
    host_obj.with_property("host_network_out_total", net_out_total)
    host_obj.with_property("host_disk_read_total", disk_read_total)
    host_obj.with_property("host_disk_write_total", disk_write_total)


def _enrich_host_with_computed_metrics(host_obj, host_resource_id, vm_lookup,
                                       vm_ids, client, sub_id, sku_memory,
                                       host_sku_name, host_location):
    """Enrich a dedicated host with Sources 6-9 data.

    Source 6:  vCPU capacity from expanded SKU API
    Source 7:  Aggregated VM metrics (CPU, network, disk)
    Source 8:  Policy compliance state
    Source 9:  Reservations lookup

    Note: Source 10 (missing ARM properties) is handled inline in the main
    collector since those values come directly from the host dict.

    Args:
        host_obj: The Aria Ops result object for this host.
        host_resource_id: Full ARM resource ID of the host.
        vm_lookup: Dict mapping lowered VM ID to VM dict.
        vm_ids: List of VM resource IDs placed on this host.
        client: AzureClient instance.
        sub_id: Subscription ID.
        sku_memory: Dict mapping VM size to memory in GB (from main collector).
        host_sku_name: The dedicated host SKU name (e.g. "DSv3-Type1").
        host_location: Azure region of the host.
    """

    # ------------------------------------------------------------------
    # Source 6: Expand SKU API for vCPU capacity
    # ------------------------------------------------------------------
    try:
        vm_vcpu_map, host_vcpu_map = _build_vcpu_caches(
            client, sub_id, host_location)

        # Host vCPU capacity (from dedicated host SKU "Cores" capability)
        host_vcpu_capacity = host_vcpu_map.get(host_sku_name, 0)
        safe_property(host_obj, "host_vcpu_capacity", host_vcpu_capacity)

        # Total VM vCPUs allocated (sum across all VMs on host)
        total_vm_vcpus = 0
        for vm_id in vm_ids:
            vm_data = vm_lookup.get(vm_id.lower())
            if vm_data:
                vm_size = vm_data.get("properties", {}).get(
                    "hardwareProfile", {}).get("vmSize", "")
                total_vm_vcpus += vm_vcpu_map.get(vm_size, 0)
        safe_property(host_obj, "total_vm_vcpus_allocated", total_vm_vcpus)

        # vCPU utilization percentage
        if host_vcpu_capacity > 0:
            vcpu_util = round(
                (total_vm_vcpus / host_vcpu_capacity) * 100, 1)
            safe_property(host_obj, "vcpu_utilization_pct", vcpu_util)
    except Exception as e:
        logger.debug("vCPU enrichment failed for %s: %s",
                     host_resource_id.split("/")[-1], e)

    # ------------------------------------------------------------------
    # Source 7: Aggregated VM metrics
    # ------------------------------------------------------------------
    try:
        _collect_host_aggregated_metrics(
            host_obj, vm_ids, vm_lookup, client)
    except Exception as e:
        logger.debug("Host aggregated metrics failed for %s: %s",
                     host_resource_id.split("/")[-1], e)

    # ------------------------------------------------------------------
    # Source 8: Policy compliance
    # ------------------------------------------------------------------
    try:
        compliance_records = client.get_all(
            path=(f"{host_resource_id}/providers"
                  "/Microsoft.PolicyInsights/policyStates/latest"),
            api_version=API_VERSIONS.get("policy_insights", "2019-10-01"),
        )
        non_compliant = 0
        overall_state = "Compliant"
        for rec in compliance_records:
            comp_state = rec.get("properties", {}).get(
                "complianceState",
                rec.get("complianceState", ""))
            if comp_state == "NonCompliant":
                non_compliant += 1
                overall_state = "NonCompliant"
        safe_property(host_obj, "policy_compliance_state", overall_state)
        safe_property(host_obj, "policy_non_compliant_count", non_compliant)
    except Exception as e:
        logger.debug("Policy compliance fetch failed for %s: %s",
                     host_resource_id.split("/")[-1], e)
        safe_property(host_obj, "policy_compliance_state", "Unknown")
        safe_property(host_obj, "policy_non_compliant_count", 0)

    # ------------------------------------------------------------------
    # Source 9: Reservations lookup
    # ------------------------------------------------------------------
    try:
        if not hasattr(_enrich_host_with_computed_metrics,
                       '_reservations_cache'):
            _enrich_host_with_computed_metrics._reservations_cache = {}

        if sub_id not in _enrich_host_with_computed_metrics._reservations_cache:
            try:
                reservations = client.get_all(
                    path="/providers/Microsoft.Capacity/reservationOrders",
                    api_version=API_VERSIONS.get(
                        "reservations", "2022-11-01"),
                )
                _enrich_host_with_computed_metrics._reservations_cache[
                    sub_id] = reservations
            except Exception:
                _enrich_host_with_computed_metrics._reservations_cache[
                    sub_id] = []

        reservations = (
            _enrich_host_with_computed_metrics._reservations_cache
            .get(sub_id, []))

        reservation_status = "PayAsYouGo"
        reservation_id = ""
        reservation_expiry = ""

        for order in reservations:
            order_props = order.get("properties", {})
            res_items = order_props.get("reservations", [])
            for item in res_items:
                item_props = item.get("properties", {})
                # Check if reservation applies to dedicated hosts
                reserved_type = item_props.get(
                    "reservedResourceType", "")
                if reserved_type == "DedicatedHost":
                    display_name = item_props.get("displayName", "")
                    if (host_sku_name
                            and host_sku_name.lower()
                            in display_name.lower()):
                        reservation_status = "Reserved"
                        reservation_id = order.get("name", "")
                        reservation_expiry = str(
                            order_props.get("expiryDate", ""))
                        break
            if reservation_status == "Reserved":
                break

        safe_property(host_obj, "reservation_status", reservation_status)
        safe_property(host_obj, "reservation_id", reservation_id)
        safe_property(host_obj, "reservation_expiry", reservation_expiry)
    except Exception as e:
        logger.debug("Reservations lookup failed for %s: %s",
                     host_resource_id.split("/")[-1], e)
        safe_property(host_obj, "reservation_status", "")
        safe_property(host_obj, "reservation_id", "")
        safe_property(host_obj, "reservation_expiry", "")
