"""Collector for Azure Functions Apps."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_FUNCTIONS_APP, OBJ_RESOURCE_GROUP, OBJ_APP_SERVICE_PLAN,
    RES_IDENT_SUB, RES_IDENT_RG, RES_IDENT_REGION, RES_IDENT_ID,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE, AZURE_SERVICE_NAMES,
)
from helpers import make_identifiers, extract_resource_group, safe_property, sanitize_tag_key

logger = logging.getLogger(__name__)


def collect_functions_apps(client: AzureClient, result, adapter_kind: str,
                           subscriptions: list):
    """Collect function apps across all subscriptions.

    Function Apps are Web Sites with kind containing 'functionapp'.
    Uses the same Microsoft.Web/sites API as app services, filtered by kind.
    """
    logger.info("Collecting function apps")
    total = 0

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]
        sites = client.get_all(
            path=f"/subscriptions/{sub_id}/providers/Microsoft.Web/sites",
            api_version=API_VERSIONS["web_apps"],
        )

        for site in sites:
            kind = site.get("kind", "")
            if "functionapp" not in kind.lower():
                continue

            app_name = site["name"]
            rg_name = extract_resource_group(site.get("id", ""))
            resource_id = site.get("id", "")
            location = site.get("location", "")
            props = site.get("properties", {})
            site_config = props.get("siteConfig", {})
            identity = site.get("identity", {})

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_FUNCTIONS_APP,
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
            safe_property(obj, SD_SERVICE, AZURE_SERVICE_NAMES.get(OBJ_FUNCTIONS_APP, ""))

            # Native pak summary properties
            safe_property(obj, "summary|name", app_name)
            safe_property(obj, "summary|id", resource_id)
            safe_property(obj, "summary|type", site.get("type", ""))
            safe_property(obj, "summary|tags", str(site.get("tags", {})))
            safe_property(obj, "summary|appServicePlanId",
                          props.get("serverFarmId", ""))
            safe_property(obj, "summary|defaultHostName",
                          props.get("defaultHostName", ""))
            safe_property(obj, "summary|state", props.get("state", ""))
            safe_property(obj, "summary|containerSize",
                          str(props.get("containerSize", "")))
            safe_property(obj, "summary|availabilityState",
                          props.get("availabilityState", ""))
            safe_property(obj, "summary|alwaysOn",
                          str(site_config.get("alwaysOn", "")))
            safe_property(obj, "summary|clientAffinityEnabled",
                          str(props.get("clientAffinityEnabled", "")))
            safe_property(obj, "summary|linuxFxVersion",
                          site_config.get("linuxFxVersion", ""))
            safe_property(obj, "summary|nodeVersion",
                          site_config.get("nodeVersion", ""))
            safe_property(obj, "summary|regionName", location)
            safe_property(obj, "summary|repositorySiteName",
                          props.get("repositorySiteName", ""))

            # Generic summary properties
            safe_property(obj, "genericsummary|Name", app_name)
            safe_property(obj, "genericsummary|Location", location)
            safe_property(obj, "genericsummary|Id", resource_id)
            safe_property(obj, "genericsummary|Sku", "")
            safe_property(obj, "genericsummary|Type", site.get("type", ""))

            # Deep properties (beyond native pak)
            linux_fx = site_config.get("linuxFxVersion", "")
            net_fw = site_config.get("netFrameworkVersion", "")
            safe_property(obj, "runtime_stack", linux_fx if linux_fx else net_fw)

            # App settings — extract FUNCTIONS_WORKER_RUNTIME and FUNCTIONS_EXTENSION_VERSION
            app_settings = site_config.get("appSettings", [])
            worker_runtime = ""
            extension_version = ""
            if isinstance(app_settings, list):
                for setting in app_settings:
                    name = setting.get("name", "")
                    if name == "FUNCTIONS_WORKER_RUNTIME":
                        worker_runtime = setting.get("value", "")
                    elif name == "FUNCTIONS_EXTENSION_VERSION":
                        extension_version = setting.get("value", "")
            safe_property(obj, "function_app_runtime", worker_runtime)
            safe_property(obj, "function_extension_version", extension_version)

            # Managed identity
            identity_type = identity.get("type", "")
            managed_identity = str("SystemAssigned" in identity_type) if identity_type else "False"
            safe_property(obj, "managed_identity_enabled", managed_identity)

            safe_property(obj, "https_only",
                          str(props.get("httpsOnly", "")))
            safe_property(obj, "enabled", str(props.get("enabled", "")))
            safe_property(obj, "outbound_ip_addresses",
                          props.get("outboundIpAddresses", ""))

            # Standard properties
            safe_property(obj, "resource_id", resource_id)
            safe_property(obj, "subscription_id", sub_id)
            safe_property(obj, "resource_group", rg_name)
            safe_property(obj, "kind", kind)

            # Tags
            tags = site.get("tags", {})
            if tags:
                for key, value in tags.items():
                    safe_property(obj, f"tag_{sanitize_tag_key(key)}", value)

            # Relationship: Function App -> Resource Group
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

            # Relationship: Function App -> App Service Plan
            server_farm_id = props.get("serverFarmId", "")
            if server_farm_id:
                plan_name = server_farm_id.split("/")[-1] if "/" in server_farm_id else ""
                if plan_name:
                    plan_rg = extract_resource_group(server_farm_id)
                    plan_obj = result.object(
                        adapter_kind=adapter_kind,
                        object_kind=OBJ_APP_SERVICE_PLAN,
                        name=plan_name,
                        identifiers=make_identifiers([
                            (RES_IDENT_SUB, sub_id),
                            (RES_IDENT_RG, plan_rg),
                            (RES_IDENT_REGION, location),
                            (RES_IDENT_ID, server_farm_id),
                        ]),
                    )
                    obj.add_parent(plan_obj)

            total += 1

    logger.info("Collected %d function apps", total)
