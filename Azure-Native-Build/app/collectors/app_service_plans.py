"""Collector for Azure App Service Plans."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_APP_SERVICE_PLAN, OBJ_RESOURCE_GROUP,
    RES_IDENT_SUB, RES_IDENT_RG, RES_IDENT_REGION, RES_IDENT_ID,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE, AZURE_SERVICE_NAMES,
)
from helpers import make_identifiers, extract_resource_group, safe_property, sanitize_tag_key

logger = logging.getLogger(__name__)


def collect_app_service_plans(client: AzureClient, result, adapter_kind: str,
                              subscriptions: list):
    """Collect app service plans across all subscriptions."""
    logger.info("Collecting app service plans")
    total = 0

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]
        plans = client.get_all(
            path=f"/subscriptions/{sub_id}/providers/Microsoft.Web/serverfarms",
            api_version=API_VERSIONS["app_service_plans"],
        )

        for plan in plans:
            plan_name = plan["name"]
            rg_name = extract_resource_group(plan.get("id", ""))
            resource_id = plan.get("id", "")
            location = plan.get("location", "")
            props = plan.get("properties", {})
            sku = plan.get("sku", {})

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_APP_SERVICE_PLAN,
                name=plan_name,
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
            safe_property(obj, SD_SERVICE, AZURE_SERVICE_NAMES.get(OBJ_APP_SERVICE_PLAN, ""))

            # Native pak summary properties
            safe_property(obj, "summary|name", plan_name)
            safe_property(obj, "summary|provisioningState",
                          props.get("provisioningState", ""))
            safe_property(obj, "summary|sku", str(sku))
            safe_property(obj, "summary|tags", str(plan.get("tags", {})))
            safe_property(obj, "summary|capacity",
                          str(sku.get("capacity", "")))
            safe_property(obj, "summary|maxInstances",
                          str(props.get("maximumNumberOfWorkers", "")))
            safe_property(obj, "summary|numberOfWebApps",
                          str(props.get("numberOfSites", "")))
            safe_property(obj, "summary|operatingSystem",
                          "Linux" if props.get("reserved", False) else "Windows")
            safe_property(obj, "summary|pricingTier",
                          sku.get("tier", ""))
            safe_property(obj, "summary|workerTierName",
                          props.get("workerTierName", ""))
            safe_property(obj, "summary|maximumElasticWorkerCount",
                          str(props.get("maximumElasticWorkerCount", "")))
            safe_property(obj, "summary|maximumNumberOfWorkers",
                          str(props.get("maximumNumberOfWorkers", "")))
            safe_property(obj, "summary|numberOfSites",
                          str(props.get("numberOfSites", "")))
            safe_property(obj, "summary|targetWorkerCount",
                          str(props.get("targetWorkerCount", "")))
            safe_property(obj, "summary|targetWorkerSizeId",
                          str(props.get("targetWorkerSizeId", "")))
            safe_property(obj, "summary|freeOfferExpirationTime",
                          props.get("freeOfferExpirationTime", ""))
            safe_property(obj, "summary|hyperV",
                          str(props.get("hyperV", "")))
            safe_property(obj, "summary|isSpot",
                          str(props.get("isSpot", "")))
            safe_property(obj, "summary|isXenon",
                          str(props.get("isXenon", "")))
            safe_property(obj, "summary|hostingEnvironmentProfile",
                          str(props.get("hostingEnvironmentProfile", "")))
            safe_property(obj, "summary|reserved",
                          str(props.get("reserved", "")))
            safe_property(obj, "summary|spotExpirationTime",
                          props.get("spotExpirationTime", ""))
            safe_property(obj, "summary|status",
                          str(props.get("status", "")))

            # Generic summary properties
            safe_property(obj, "genericsummary|Name", plan_name)
            safe_property(obj, "genericsummary|Location", location)
            safe_property(obj, "genericsummary|Id", resource_id)
            safe_property(obj, "genericsummary|Sku", sku.get("name", ""))
            safe_property(obj, "genericsummary|Type", plan.get("type", ""))

            # Deep properties (beyond native pak)
            safe_property(obj, "current_number_of_workers",
                          str(props.get("currentNumberOfWorkers", "")))
            safe_property(obj, "per_site_scaling_enabled",
                          str(props.get("perSiteScaling", "")))
            safe_property(obj, "zone_redundant",
                          str(props.get("zoneRedundant", "")))
            safe_property(obj, "kind", plan.get("kind", ""))

            # Standard properties
            safe_property(obj, "resource_id", resource_id)
            safe_property(obj, "subscription_id", sub_id)
            safe_property(obj, "resource_group", rg_name)

            # Tags
            tags = plan.get("tags", {})
            if tags:
                for key, value in tags.items():
                    safe_property(obj, f"tag_{sanitize_tag_key(key)}", value)

            # Relationship: App Service Plan -> Resource Group
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

            total += 1

    logger.info("Collected %d app service plans", total)
