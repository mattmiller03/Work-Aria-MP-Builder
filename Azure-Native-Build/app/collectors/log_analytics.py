"""Collector for Azure Log Analytics Workspaces."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_LOG_ANALYTICS, OBJ_RESOURCE_GROUP,
    RES_IDENT_SUB, RES_IDENT_RG, RES_IDENT_REGION, RES_IDENT_ID,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE, AZURE_SERVICE_NAMES,
)
from helpers import make_identifiers, extract_resource_group, safe_property, sanitize_tag_key

logger = logging.getLogger(__name__)


def collect_log_analytics_workspaces(client: AzureClient, result, adapter_kind: str,
                                     subscriptions: list):
    """Collect Log Analytics workspaces across all subscriptions."""
    logger.info("Collecting Log Analytics workspaces")
    total = 0

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]
        workspaces = client.get_all(
            path=f"/subscriptions/{sub_id}/providers/Microsoft.OperationalInsights/workspaces",
            api_version=API_VERSIONS["log_analytics"],
        )

        for ws in workspaces:
            ws_name = ws["name"]
            resource_id = ws.get("id", "")
            rg_name = extract_resource_group(resource_id)
            location = ws.get("location", "")
            props = ws.get("properties", {})

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_LOG_ANALYTICS,
                name=ws_name,
                identifiers=make_identifiers([
                    (RES_IDENT_SUB, sub_id),
                    (RES_IDENT_RG, rg_name),
                    (RES_IDENT_REGION, location),
                    (RES_IDENT_ID, resource_id),
                ]),
            )

            # SERVICE_DESCRIPTORS
            safe_property(obj, SD_SUBSCRIPTION, sub_id)
            safe_property(obj, SD_RESOURCE_GROUP, rg_name)
            safe_property(obj, SD_REGION, location)
            safe_property(obj, SD_SERVICE, AZURE_SERVICE_NAMES.get(OBJ_LOG_ANALYTICS, ""))

            safe_property(obj, "workspace_name", ws_name)
            safe_property(obj, "resource_id", resource_id)
            safe_property(obj, "location", location)
            safe_property(obj, "subscription_id", sub_id)
            safe_property(obj, "resource_group", rg_name)
            safe_property(obj, "workspace_id",
                          props.get("customerId", ""))
            safe_property(obj, "provisioning_state",
                          props.get("provisioningState", ""))
            safe_property(obj, "sku_name",
                          props.get("sku", {}).get("name", ""))
            safe_property(obj, "retention_in_days",
                          props.get("retentionInDays", ""))
            safe_property(obj, "daily_quota_gb",
                          props.get("workspaceCapping", {}).get("dailyQuotaGb", ""))
            safe_property(obj, "created_date",
                          props.get("createdDate", ""))
            safe_property(obj, "modified_date",
                          props.get("modifiedDate", ""))
            safe_property(obj, "public_network_access_for_ingestion",
                          props.get("publicNetworkAccessForIngestion", ""))
            safe_property(obj, "public_network_access_for_query",
                          props.get("publicNetworkAccessForQuery", ""))

            # Tags
            tags = ws.get("tags", {})
            if tags:
                for key, value in tags.items():
                    safe_property(obj, f"summary|tags|{key}", value)

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
                obj.add_parent(rg_obj)

        total += len(workspaces)

    logger.info("Collected %d Log Analytics workspaces", total)
