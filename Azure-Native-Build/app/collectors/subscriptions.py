"""Collector for Azure Subscriptions."""

import logging

from azure_client import AzureClient
from constants import API_VERSIONS, OBJ_SUBSCRIPTION
from helpers import make_identifiers, safe_property, sanitize_tag_key

logger = logging.getLogger(__name__)


def collect_subscriptions(client: AzureClient, result, adapter_kind: str):
    """Collect all accessible Azure subscriptions.

    Returns:
        List of subscription dicts for use by downstream collectors.
    """
    logger.info("Collecting subscriptions")
    subscriptions = client.get_all(
        path="/subscriptions",
        api_version=API_VERSIONS["subscriptions"],
    )

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]
        obj = result.object(
            adapter_kind=adapter_kind,
            object_kind=OBJ_SUBSCRIPTION,
            name=sub.get("displayName", sub_id),
            identifiers=make_identifiers([("subscription_id", sub_id)]),
        )

        safe_property(obj, "subscription_id", sub_id)
        safe_property(obj, "display_name", sub.get("displayName", ""))
        safe_property(obj, "state", sub.get("state", ""))
        safe_property(obj, "tenant_id", sub.get("tenantId", ""))

        policies = sub.get("subscriptionPolicies", {})
        safe_property(obj, "location_placement_id",
                      policies.get("locationPlacementId", ""))
        safe_property(obj, "quota_id", policies.get("quotaId", ""))
        safe_property(obj, "spending_limit", policies.get("spendingLimit", ""))

        tags = sub.get("tags", {})
        if tags:
            for key, value in tags.items():
                safe_property(obj, f"summary|tags|{key}", value)

    logger.info("Collected %d subscriptions", len(subscriptions))
    return subscriptions
