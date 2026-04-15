"""Collector for Azure Region, Region-per-Subscription, and World objects.

Creates the three aggregation object types used by native pak dashboards:
- AZURE_REGION — one per unique region across all subscriptions
- AZURE_REGION_PER_SUB — one per region per subscription
- AZURE_WORLD — single root object with total_number_* count metrics

Must run AFTER all other collectors so it can scan the result for objects
to build region mappings and resource counts.
"""

import logging
from collections import defaultdict

from constants import (
    OBJ_REGION, OBJ_REGION_PER_SUB, OBJ_WORLD,
    OBJ_VIRTUAL_MACHINE, OBJ_STORAGE_ACCOUNT, OBJ_SQL_SERVER,
    OBJ_LOAD_BALANCER, OBJ_NETWORK_INTERFACE, OBJ_VIRTUAL_NETWORK,
    OBJ_APP_SERVICE, OBJ_DISK, OBJ_HOST_GROUP, OBJ_DEDICATED_HOST,
    OBJ_PUBLIC_IP, OBJ_EXPRESSROUTE, OBJ_KEY_VAULT,
    OBJ_POSTGRESQL, OBJ_MYSQL, OBJ_FUNCTIONS_APP,
    RES_IDENT_REGION,
)

logger = logging.getLogger(__name__)


# Mapping from object kind to AZURE_WORLD summary metric key.
# Keys match native pak describe.xml exactly (including typos).
_WORLD_COUNT_METRICS = {
    OBJ_VIRTUAL_MACHINE: "summary|total_number_vms",
    OBJ_STORAGE_ACCOUNT: "summary|total_number_storgeaccounts",   # native typo
    OBJ_SQL_SERVER: "summary|total_number_sqlserver",
    OBJ_LOAD_BALANCER: "summary|total_number_loadbalancers",
    OBJ_NETWORK_INTERFACE: "summary|total_number_nwInterface",
    OBJ_VIRTUAL_NETWORK: "summary|total_number_vNets",
    OBJ_APP_SERVICE: "summary|total_number_appServices",
    OBJ_DISK: "summary|total_number_storageDisks",
    OBJ_HOST_GROUP: "summary|total_number_hostGroups",
    OBJ_DEDICATED_HOST: "summary|total_number_dedicatedHosts",
    OBJ_PUBLIC_IP: "summary|total_number_publicIPAddresses",
    OBJ_EXPRESSROUTE: "summary|total_number_expressrouteCircuit",
    OBJ_KEY_VAULT: "summary|total_number_keyVaults",
    OBJ_POSTGRESQL: "summary|total_number_postgresqlserver",
    OBJ_MYSQL: "summary|total_number_mysqlserver",
    OBJ_FUNCTIONS_APP: "summary|total_number_functionApp",
}


def collect_regions_and_world(result, adapter_kind, subscriptions,
                              adapter_instance_name):
    """Create AZURE_REGION, AZURE_REGION_PER_SUB, and AZURE_WORLD objects.

    Scans all objects already in the result to:
    1. Build region-to-objects mapping from AZURE_REGION identifiers
    2. Create one AZURE_REGION per unique region
    3. Create one AZURE_REGION_PER_SUB per region (name includes instance)
    4. Create a single AZURE_WORLD with total_number_* count metrics

    Args:
        result: CollectResult populated by prior collectors.
        adapter_kind: Adapter kind string (MicrosoftAzureAdapter).
        subscriptions: List of subscription dicts.
        adapter_instance_name: Display name for the adapter instance.
    """
    logger.info("Collecting regions and world objects")

    # ------------------------------------------------------------------
    # 1. Scan all existing objects for region info and kind counts
    # ------------------------------------------------------------------
    regions = set()
    kind_counts = defaultdict(int)
    active_vms = 0

    for obj in result.get_objects():
        obj_kind = obj.get_key().object_kind

        # Count objects by kind
        kind_counts[obj_kind] += 1

        # Extract region from identifiers
        for ident in obj.get_key().identifiers:
            if ident.key == RES_IDENT_REGION and ident.value:
                regions.add(ident.value)

        # Count active VMs (general|running == 1.0)
        if obj_kind == OBJ_VIRTUAL_MACHINE:
            for metric_data in obj.get_metrics():
                if metric_data.key == "general|running":
                    try:
                        values = metric_data.get_values()
                        if values and values[-1] == 1.0:
                            active_vms += 1
                    except Exception:
                        pass

    logger.info("Found %d unique regions across all objects", len(regions))

    # ------------------------------------------------------------------
    # 2. Create AZURE_REGION objects (no identifiers, name-only)
    # ------------------------------------------------------------------
    region_objects = {}
    for region_name in sorted(regions):
        region_label = f"Azure {region_name}"
        region_obj = result.object(
            adapter_kind=adapter_kind,
            object_kind=OBJ_REGION,
            name=region_label,
            identifiers=[],
        )
        region_objects[region_name] = region_obj

    logger.info("Created %d AZURE_REGION objects", len(region_objects))

    # ------------------------------------------------------------------
    # 3. Create AZURE_REGION_PER_SUB objects (no identifiers, name-only)
    # ------------------------------------------------------------------
    region_per_sub_count = 0
    for region_name in sorted(regions):
        per_sub_label = f"{region_name} - {adapter_instance_name}"
        per_sub_obj = result.object(
            adapter_kind=adapter_kind,
            object_kind=OBJ_REGION_PER_SUB,
            name=per_sub_label,
            identifiers=[],
        )

        # Parent: AZURE_REGION
        region_obj = region_objects.get(region_name)
        if region_obj:
            per_sub_obj.add_parent(region_obj)

        region_per_sub_count += 1

    logger.info("Created %d AZURE_REGION_PER_SUB objects", region_per_sub_count)

    # ------------------------------------------------------------------
    # 4. Create AZURE_WORLD object with total_number_* metrics
    # ------------------------------------------------------------------
    world_obj = result.object(
        adapter_kind=adapter_kind,
        object_kind=OBJ_WORLD,
        name="Azure World",
        identifiers=[],
    )

    # Set count metrics for each resource kind we track
    for obj_kind, metric_key in _WORLD_COUNT_METRICS.items():
        world_obj.with_metric(metric_key, float(kind_counts.get(obj_kind, 0)))

    # Active VMs
    world_obj.with_metric("summary|active_number_vms", float(active_vms))

    # Region count (AZURE_REGION_PER_SUB objects)
    world_obj.with_metric("summary|total_number_regions",
                          float(region_per_sub_count))

    # Subscription count
    world_obj.with_metric("summary|total_number_subscriptions",
                          float(len(subscriptions)))

    logger.info(
        "Created AZURE_WORLD with %d resource kind counts, "
        "%d regions, %d subscriptions",
        len(_WORLD_COUNT_METRICS), len(regions), len(subscriptions),
    )
