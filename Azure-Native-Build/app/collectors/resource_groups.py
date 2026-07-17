"""Collector for Azure Resource Groups."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_RESOURCE_GROUP, OBJ_SUBSCRIPTION,
    RES_IDENT_SUB, RES_IDENT_ID,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE,
    AZURE_SERVICE_NAMES,
)
from helpers import (build_rg_lookup, make_identifiers, safe_property,
                     sanitize_tag_key)

logger = logging.getLogger(__name__)


def collect_resource_groups(client: AzureClient, result, adapter_kind: str,
                            subscriptions: list, rg_lookup: dict = None):
    """Collect resource groups across all subscriptions.

    Also populates `rg_lookup` (see helpers.build_rg_lookup) — the
    canonical RG resolution table every child collector must use when
    building RG parent references. Pass a shared dict in from adapter.py
    so downstream collectors see it; a fresh dict is created if omitted.

    Returns:
        Tuple of (all_rgs, rg_lookup):
          all_rgs   — dict mapping subscription_id -> list of RG dicts
          rg_lookup — dict mapping lowercased canonical RG ID ->
                      {"id", "name", "location"} (original casing)
    """
    logger.info("Collecting resource groups")
    all_rgs = {}
    if rg_lookup is None:
        rg_lookup = {}

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]
        rgs = client.get_all(
            path=f"/subscriptions/{sub_id}/resourcegroups",
            api_version=API_VERSIONS["resource_groups"],
        )
        all_rgs[sub_id] = rgs
        build_rg_lookup(sub_id, rgs, rg_lookup)

        for rg in rgs:
            rg_name = rg["name"]
            # CANONICAL RECIPE (2026-07-16, replaces the .lower() form):
            # camelCase /resourceGroups/ segment + name in created casing.
            # This byte-matches (a) the RG population already ingested in
            # Aria Ops, and (b) every reference built by child collectors
            # via helpers.canonical_rg_id()/reference_resource_group(),
            # which resolve through rg_lookup to this exact string.
            #
            # Do NOT use rg["id"] verbatim here — ARM echoes the request
            # path's casing (/resourcegroups lowercase) in the id field.
            # Do NOT reintroduce .lower() — ID is uniqueness-bearing, and
            # lowercased declarations orphan every edge referencing the
            # original-cased objects (the 2026-07 "zero relationships"
            # defect) while forking a duplicate RG population.
            rg_id = rg_lookup[
                f"/subscriptions/{sub_id}/resourcegroups/{rg_name}".lower()
            ]["id"]
            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_RESOURCE_GROUP,
                name=rg_name,
                identifiers=make_identifiers([
                    (RES_IDENT_SUB, sub_id),
                    (RES_IDENT_ID, rg_id),
                ]),
            )

            # SERVICE_DESCRIPTORS — required for native-pak compatibility.
            # Without these, downstream dashboards and traversal specs that
            # filter by SD properties find no resource groups.
            rg_location = rg.get("location", "")
            safe_property(obj, SD_SUBSCRIPTION, sub_id)
            safe_property(obj, SD_RESOURCE_GROUP, rg_name)
            safe_property(obj, SD_REGION, rg_location)
            safe_property(obj, SD_SERVICE,
                          AZURE_SERVICE_NAMES.get(OBJ_RESOURCE_GROUP, ""))

            safe_property(obj, "name", rg_name)
            safe_property(obj, "location", rg_location)
            safe_property(obj, "provisioning_state",
                          rg.get("properties", {}).get("provisioningState", ""))
            safe_property(obj, "subscription_id", sub_id)
            safe_property(obj, "resource_id", rg_id)

            tags = rg.get("tags", {})
            if tags:
                for key, value in tags.items():
                    safe_property(obj, f"summary|tags|{key}", value)

            # Relationship: Resource Group -> Subscription (parent)
            sub_obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_SUBSCRIPTION,
                name=sub.get("displayName", sub_id),
                identifiers=make_identifiers([("subscription_id", sub_id)]),
            )
            obj.add_parent(sub_obj)

    total = sum(len(rgs) for rgs in all_rgs.values())
    logger.info("Collected %d resource groups across %d subscriptions "
                "(rg_lookup: %d entries)",
                total, len(subscriptions), len(rg_lookup))
    return all_rgs, rg_lookup
