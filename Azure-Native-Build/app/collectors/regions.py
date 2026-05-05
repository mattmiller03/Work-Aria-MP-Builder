"""Collector for Azure Region, Region-per-Subscription, and World objects.

Creates the three aggregation object types used by native pak dashboards:
- AZURE_REGION — one per unique region across all subscriptions
- AZURE_REGION_PER_SUB — one per (subscription, region) pair
- AZURE_WORLD — single root object with total_number_* count metrics

Must run AFTER all other collectors so it can scan the result for objects
to build region mappings, attach REGION_PER_SUB parents, and roll up counts.

Native traversal expectations (content/traversalspecs/MicrosoftAzureTraversalSpecs.xml):
  - Azure Resources By Region:
        AZURE_REGION -> AZURE_REGION_PER_SUB -> resources (VM, Disk, ...)
  - Azure Resources By Subscription:
        Adapter Instance -> AZURE_RESOURCE_GROUP -> resources

For "By Region" to work, every collected resource must be a child of its
REGION_PER_SUB; for the dashboards' Subscription drill-down to find
regions, REGION_PER_SUB must be a child of azure_subscription too.
"""

import logging
from collections import defaultdict

from helpers import safe_property
from constants import (
    OBJ_REGION, OBJ_REGION_PER_SUB, OBJ_WORLD, OBJ_SUBSCRIPTION,
    OBJ_VIRTUAL_MACHINE, OBJ_STORAGE_ACCOUNT, OBJ_SQL_SERVER,
    OBJ_LOAD_BALANCER, OBJ_NETWORK_INTERFACE, OBJ_VIRTUAL_NETWORK,
    OBJ_APP_SERVICE, OBJ_DISK, OBJ_HOST_GROUP, OBJ_DEDICATED_HOST,
    OBJ_PUBLIC_IP, OBJ_EXPRESSROUTE, OBJ_KEY_VAULT,
    OBJ_POSTGRESQL, OBJ_MYSQL, OBJ_FUNCTIONS_APP,
    RES_IDENT_REGION, RES_IDENT_SUB,
)

logger = logging.getLogger(__name__)


# Map Azure Gov ARM region codes to the display names used in
# content/regions/azureregions.json. The Aria Ops home-tab globe widget
# joins AZURE_REGION objects to that file by name, so the region object's
# `name` MUST match a `name` entry in the JSON for the geo coords to
# attach. lat/lon are duplicated as object properties so widgets that
# read coords directly (rather than via name join) also work.
_GOV_REGION_GEO = {
    "usgovvirginia":  ("Azure GovCloud (US Gov Virginia)", 37.623159, -78.39411),
    "usgovtexas":     ("Azure GovCloud (US Gov Texas)",     31.56443,  -99.208076),
    "usgovarizona":   ("Azure GovCloud (US Gov Arizona)",   34.42527,  -111.7046),
    "usdodcentral":   ("Azure GovCloud (US DoD Central)",   42.41475,  -92.561731),
    "usdodeast":      ("Azure GovCloud (US DoD East)",      37.70926,  -77.84588),
}


def _resolve_region_display(region_code):
    """Map an Azure region code to (display_name, latitude, longitude).

    Falls back to "Azure {code}" with no geo when the code isn't in the
    Gov mapping, so non-Gov collectors still produce sane region objects.
    """
    entry = _GOV_REGION_GEO.get(region_code.lower())
    if entry:
        return entry
    return (f"Azure {region_code}", None, None)


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


# Aggregation kinds — never become children of REGION_PER_SUB.
_AGGREGATION_KINDS = {
    OBJ_REGION, OBJ_REGION_PER_SUB, OBJ_WORLD, OBJ_SUBSCRIPTION,
}


def collect_regions_and_world(result, adapter_kind, subscriptions,
                              adapter_instance_name):
    """Create AZURE_REGION, AZURE_REGION_PER_SUB, and AZURE_WORLD objects
    and wire up the topology that native pak dashboards expect.

    1. Build a (sub_id, region) index from existing object identifiers.
    2. Create one AZURE_REGION per unique region.
    3. Create one AZURE_REGION_PER_SUB per (sub, region) pair, with
       parents = [AZURE_REGION, azure_subscription].
    4. Add REGION_PER_SUB as a parent of every collected resource so the
       "By Region" traversal returns objects.
    5. Create one AZURE_WORLD with total_number_* count metrics.

    Args:
        result: CollectResult populated by prior collectors.
        adapter_kind: Adapter kind string (MicrosoftAzureAdapter).
        subscriptions: List of subscription dicts.
        adapter_instance_name: Display name for the adapter instance,
            used as a fallback when a sub display name is not available.
    """
    logger.info("Collecting regions and world objects")

    # ------------------------------------------------------------------
    # 1. Build lookups by scanning existing objects
    # ------------------------------------------------------------------
    # subscription_id -> azure_subscription Object
    sub_lookup = {}
    # set of (sub_id, region) pairs found on collected resources
    sub_region_pairs = set()
    # list of (resource_obj, sub_id, region) for the link-back step
    resources_to_link = []
    # per-kind counts for AZURE_WORLD
    kind_counts = defaultdict(int)
    active_vms = 0

    # Snapshot the values list — we'll be calling add_parent below which
    # mutates parent sets but not the result.objects dict, so this is
    # purely defensive.
    all_objects = list(result.objects.values())

    for obj in all_objects:
        obj_kind = obj.get_key().object_kind
        kind_counts[obj_kind] += 1

        # Build subscription lookup
        if obj_kind == OBJ_SUBSCRIPTION:
            for ident in obj.get_key().identifiers.values():
                if ident.key == "subscription_id" and ident.value:
                    sub_lookup[ident.value] = obj
                    break
            continue

        # Skip aggregation kinds for region indexing + linking
        if obj_kind in _AGGREGATION_KINDS:
            continue

        # Pull (sub_id, region) from this resource's identifiers
        sub_id = ""
        region = ""
        for ident in obj.get_key().identifiers.values():
            if ident.key == RES_IDENT_SUB and ident.value:
                sub_id = ident.value
            elif ident.key == RES_IDENT_REGION and ident.value:
                region = ident.value

        if sub_id and region:
            sub_region_pairs.add((sub_id, region))
            resources_to_link.append((obj, sub_id, region))

        # Count active VMs (general|running == 1.0)
        if obj_kind == OBJ_VIRTUAL_MACHINE:
            try:
                if obj.get_last_metric_value("general|running") == 1.0:
                    active_vms += 1
            except Exception:
                pass

    unique_regions = sorted({r for _, r in sub_region_pairs})
    logger.info(
        "Region scan: %d unique regions, %d (sub, region) pairs, "
        "%d resources eligible for region linking, %d subscriptions",
        len(unique_regions), len(sub_region_pairs),
        len(resources_to_link), len(sub_lookup),
    )

    # ------------------------------------------------------------------
    # 2. Create AZURE_REGION objects (one per unique region)
    #    Names match content/regions/azureregions.json exactly so the
    #    Aria Ops home-tab globe joins by name. Lat/lon are also stamped
    #    as properties so widgets that read coords directly work too.
    # ------------------------------------------------------------------
    region_objects = {}
    for region_name in unique_regions:
        display_name, lat, lon = _resolve_region_display(region_name)
        region_obj = result.object(
            adapter_kind=adapter_kind,
            object_kind=OBJ_REGION,
            name=display_name,
            identifiers=[],
        )
        safe_property(region_obj, "azure_region_code", region_name)
        if lat is not None and lon is not None:
            safe_property(region_obj, "latitude", lat)
            safe_property(region_obj, "longitude", lon)
            safe_property(region_obj, "geolocation|latitude", lat)
            safe_property(region_obj, "geolocation|longitude", lon)
        region_objects[region_name] = region_obj

    logger.info(
        "Created %d AZURE_REGION objects (geo coords applied to %d)",
        len(region_objects),
        sum(1 for r in unique_regions if _resolve_region_display(r)[1] is not None),
    )

    # ------------------------------------------------------------------
    # 3. Create AZURE_REGION_PER_SUB per (sub_id, region) pair, parented
    #    to BOTH the AZURE_REGION and the azure_subscription so that:
    #      - By-Region traversal walks REGION -> REGION_PER_SUB -> resources
    #      - Subscription-rooted dashboards find regions as children
    # ------------------------------------------------------------------
    per_sub_objects = {}  # (sub_id, region) -> AZURE_REGION_PER_SUB obj
    for sub_id, region_name in sorted(sub_region_pairs):
        sub_obj = sub_lookup.get(sub_id)
        # Prefer the subscription's display name in the per-sub label so
        # multi-sub deployments produce distinct, human-readable names.
        sub_display = (
            sub_obj.get_key().name if sub_obj else adapter_instance_name
        )
        per_sub_label = f"{region_name} - {sub_display}"
        per_sub_obj = result.object(
            adapter_kind=adapter_kind,
            object_kind=OBJ_REGION_PER_SUB,
            name=per_sub_label,
            identifiers=[],
        )
        region_obj = region_objects.get(region_name)
        if region_obj:
            per_sub_obj.add_parent(region_obj)
        if sub_obj:
            per_sub_obj.add_parent(sub_obj)
        per_sub_objects[(sub_id, region_name)] = per_sub_obj

    logger.info(
        "Created %d AZURE_REGION_PER_SUB objects "
        "(linked to %d subs and %d regions)",
        len(per_sub_objects), len(sub_lookup), len(region_objects),
    )

    # ------------------------------------------------------------------
    # 4. Add REGION_PER_SUB as a parent of every collected resource so
    #    the "By Region" traversal can reach them. Resources already have
    #    AZURE_RESOURCE_GROUP as a parent for the "By Subscription" view;
    #    multiple parents are allowed and expected.
    # ------------------------------------------------------------------
    linked_count = 0
    for obj, sub_id, region in resources_to_link:
        per_sub_obj = per_sub_objects.get((sub_id, region))
        if per_sub_obj is not None:
            obj.add_parent(per_sub_obj)
            linked_count += 1

    logger.info(
        "Linked %d resources as children of their AZURE_REGION_PER_SUB",
        linked_count,
    )

    # ------------------------------------------------------------------
    # 5. AZURE_WORLD with total_number_* metrics
    # ------------------------------------------------------------------
    world_obj = result.object(
        adapter_kind=adapter_kind,
        object_kind=OBJ_WORLD,
        name="Azure World",
        identifiers=[],
    )

    for obj_kind, metric_key in _WORLD_COUNT_METRICS.items():
        world_obj.with_metric(metric_key, float(kind_counts.get(obj_kind, 0)))

    world_obj.with_metric("summary|active_number_vms", float(active_vms))
    world_obj.with_metric("summary|total_number_regions",
                          float(len(per_sub_objects)))
    world_obj.with_metric("summary|total_number_subscriptions",
                          float(len(subscriptions)))

    logger.info(
        "Created AZURE_WORLD with %d resource kind counts, "
        "%d region-per-sub, %d subscriptions",
        len(_WORLD_COUNT_METRICS), len(per_sub_objects), len(subscriptions),
    )
