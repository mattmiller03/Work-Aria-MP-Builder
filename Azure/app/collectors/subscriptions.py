"""Collector for Azure Subscriptions."""

import logging

from azure_client import AzureClient
from constants import API_VERSIONS, OBJ_SUBSCRIPTION

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
            identifiers=[("subscription_id", sub_id)],
        )

        obj.with_property("subscription_id", sub_id)
        obj.with_property("display_name", sub.get("displayName", ""))
        obj.with_property("state", sub.get("state", ""))
        obj.with_property("tenant_id", sub.get("tenantId", ""))

        policies = sub.get("subscriptionPolicies", {})
        obj.with_property("location_placement_id",
                          policies.get("locationPlacementId", ""))
        obj.with_property("quota_id", policies.get("quotaId", ""))
        obj.with_property("spending_limit", policies.get("spendingLimit", ""))

        tags = sub.get("tags", {})
        if tags:
            for key, value in tags.items():
                obj.with_property(f"tag_{key}", value)

    logger.info("Collected %d subscriptions", len(subscriptions))
    return subscriptions
