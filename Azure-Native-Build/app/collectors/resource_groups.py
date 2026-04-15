"""Collector for Azure Resource Groups."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_RESOURCE_GROUP, OBJ_SUBSCRIPTION,
    RES_IDENT_SUB, RES_IDENT_ID,
)
from helpers import make_identifiers, safe_property, sanitize_tag_key

logger = logging.getLogger(__name__)


def collect_resource_groups(client: AzureClient, result, adapter_kind: str,
                            subscriptions: list):
    """Collect resource groups across all subscriptions.

    Returns:
        Dict mapping subscription_id -> list of resource group dicts.
    """
    logger.info("Collecting resource groups")
    all_rgs = {}

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]
        rgs = client.get_all(
            path=f"/subscriptions/{sub_id}/resourcegroups",
            api_version=API_VERSIONS["resource_groups"],
        )
        all_rgs[sub_id] = rgs

        for rg in rgs:
            rg_name = rg["name"]
            rg_id = rg.get("id", "")
            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_RESOURCE_GROUP,
                name=rg_name,
                identifiers=make_identifiers([
                    (RES_IDENT_SUB, sub_id),
                    (RES_IDENT_ID, rg_id),
                ]),
            )

            safe_property(obj, "name", rg_name)
            safe_property(obj, "location", rg.get("location", ""))
            safe_property(obj, "provisioning_state",
                          rg.get("properties", {}).get("provisioningState", ""))
            safe_property(obj, "subscription_id", sub_id)
            safe_property(obj, "resource_id", rg.get("id", ""))

            tags = rg.get("tags", {})
            if tags:
                for key, value in tags.items():
                    safe_property(obj, f"tag_{sanitize_tag_key(key)}", value)

            # Relationship: Resource Group -> Subscription (parent)
            sub_obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_SUBSCRIPTION,
                name=sub.get("displayName", sub_id),
                identifiers=make_identifiers([("subscription_id", sub_id)]),
            )
            obj.add_parent(sub_obj)

    total = sum(len(rgs) for rgs in all_rgs.values())
    logger.info("Collected %d resource groups across %d subscriptions",
                total, len(subscriptions))
    return all_rgs
