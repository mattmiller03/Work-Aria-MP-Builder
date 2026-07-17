"""Collector for Azure App Services and Function Apps."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_APP_SERVICE, OBJ_RESOURCE_GROUP,
    RES_IDENT_SUB, RES_IDENT_RG, RES_IDENT_REGION, RES_IDENT_ID,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE, AZURE_SERVICE_NAMES,
)
from helpers import (make_identifiers, extract_resource_group,
                     reference_resource_group, safe_property, sanitize_tag_key)
from collectors.metrics import collect_metrics_for_objects

logger = logging.getLogger(__name__)


def collect_app_services(client: AzureClient, result, adapter_kind: str,
                         subscriptions: list, rg_lookup: dict = None):
    """Collect web apps and function apps across all subscriptions.

    Args:
        rg_lookup: Canonical RG lookup from resource_groups.py (see
            helpers.build_rg_lookup). Used to resolve RG parent edges with
            original-cased IDs; without it, RG edges are skipped.
    """
    logger.info("Collecting app services")
    total = 0
    app_objects = {}  # resource_id -> aria obj

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]
        apps = client.get_all(
            path=f"/subscriptions/{sub_id}/providers/Microsoft.Web/sites",
            api_version=API_VERSIONS["web_apps"],
        )

        for app in apps:
            app_name = app["name"]
            rg_name = extract_resource_group(app.get("id", ""))
            resource_id = app.get("id", "")
            location = app.get("location", "")
            props = app.get("properties", {})
            site_config = props.get("siteConfig", {})

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_APP_SERVICE,
                name=app_name,
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
            safe_property(obj, SD_SERVICE, AZURE_SERVICE_NAMES.get(OBJ_APP_SERVICE, ""))

            # Native pak summary properties
            safe_property(obj, "summary|name", app_name)
            safe_property(obj, "summary|state", props.get("state", ""))
            safe_property(obj, "summary|defaultHostName",
                          props.get("defaultHostName", ""))
            safe_property(obj, "summary|httpsOnly",
                          str(props.get("httpsOnly", "")))
            host_names = props.get("hostNames", [])
            safe_property(obj, "summary|hostNames", ", ".join(host_names))
            safe_property(obj, "summary|appServicePlanId",
                          props.get("serverFarmId", ""))
            safe_property(obj, "summary|containerSize",
                          str(props.get("containerSize", "")))
            safe_property(obj, "summary|hostNamesDisabled",
                          str(props.get("hostNamesDisabled", "")))

            # siteConfig properties
            safe_property(obj, "summary|alwaysOn",
                          str(site_config.get("alwaysOn", "")))
            safe_property(obj, "summary|http20Enabled",
                          str(site_config.get("http20Enabled", "")))
            safe_property(obj, "summary|javaContainer",
                          site_config.get("javaContainer", ""))
            safe_property(obj, "summary|javaContainerVersion",
                          site_config.get("javaContainerVersion", ""))
            safe_property(obj, "summary|linuxFxVersion",
                          site_config.get("linuxFxVersion", ""))

            # Additional non-native properties retained for compatibility
            safe_property(obj, "resource_id", resource_id)
            safe_property(obj, "location", location)
            safe_property(obj, "subscription_id", sub_id)
            safe_property(obj, "resource_group", rg_name)

            # Kind: "app", "functionapp", "functionapp,linux", etc.
            kind = app.get("kind", "")
            safe_property(obj, "kind", kind)
            safe_property(obj, "is_function_app",
                          str("functionapp" in kind.lower()))

            safe_property(obj, "enabled", str(props.get("enabled", "")))

            # Availability state
            safe_property(obj, "availability_state",
                          props.get("availabilityState", ""))

            # Last modified
            safe_property(obj, "last_modified_time",
                          props.get("lastModifiedTimeUtc", ""))

            # Outbound IPs
            safe_property(obj, "outbound_ip_addresses",
                          props.get("outboundIpAddresses", ""))

            # Tags
            tags = app.get("tags", {})
            if tags:
                for key, value in tags.items():
                    safe_property(obj, f"summary|tags|{key}", value)

            # Relationship: App -> Resource Group (parent).
            # 2026-07-16 fix: previously built an f-string rg_id with
            # .lower(), which could never resolve against the original-cased
            # RG objects in Aria Ops (the "zero relationships" defect). Now
            # resolves through the canonical rg_lookup; on a miss the edge
            # is skipped — never fabricate an RG identifier.
            if rg_name:
                rg_obj = reference_resource_group(
                    result, adapter_kind, sub_id, rg_name, rg_lookup)
                if rg_obj is not None:
                    obj.add_parent(rg_obj)

            if resource_id:
                app_objects[resource_id] = obj

        total += len(apps)

    logger.info("Collected %d app services", total)

    if app_objects:
        collect_metrics_for_objects(client, app_objects, "app_services")
