"""Collector for Azure App Services and Function Apps."""

import logging

from azure_client import AzureClient
from constants import API_VERSIONS, OBJ_APP_SERVICE, OBJ_RESOURCE_GROUP

logger = logging.getLogger(__name__)


def collect_app_services(client: AzureClient, result, adapter_kind: str,
                         subscriptions: list):
    """Collect web apps and function apps across all subscriptions."""
    logger.info("Collecting app services")
    total = 0

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]
        apps = client.get_all(
            path=f"/subscriptions/{sub_id}/providers/Microsoft.Web/sites",
            api_version=API_VERSIONS["web_apps"],
        )

        for app in apps:
            app_name = app["name"]
            rg_name = _extract_rg(app.get("id", ""))
            props = app.get("properties", {})

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_APP_SERVICE,
                name=app_name,
                identifiers=[
                    ("subscription_id", sub_id),
                    ("resource_group", rg_name),
                    ("app_name", app_name),
                ],
            )

            obj.with_property("app_name", app_name)
            obj.with_property("resource_id", app.get("id", ""))
            obj.with_property("location", app.get("location", ""))
            obj.with_property("subscription_id", sub_id)
            obj.with_property("resource_group", rg_name)

            # Kind: "app", "functionapp", "functionapp,linux", etc.
            kind = app.get("kind", "")
            obj.with_property("kind", kind)
            obj.with_property("is_function_app",
                              str("functionapp" in kind.lower()))

            obj.with_property("state", props.get("state", ""))
            obj.with_property("default_host_name",
                              props.get("defaultHostName", ""))
            obj.with_property("https_only",
                              str(props.get("httpsOnly", "")))
            obj.with_property("enabled", str(props.get("enabled", "")))

            # Host names
            host_names = props.get("hostNames", [])
            obj.with_property("host_names", ", ".join(host_names))

            # App Service Plan
            obj.with_property("server_farm_id",
                              props.get("serverFarmId", ""))

            # Availability state
            obj.with_property("availability_state",
                              props.get("availabilityState", ""))

            # Last modified
            obj.with_property("last_modified_time",
                              props.get("lastModifiedTimeUtc", ""))

            # Outbound IPs
            obj.with_property("outbound_ip_addresses",
                              props.get("outboundIpAddresses", ""))

            # Tags
            tags = app.get("tags", {})
            if tags:
                for key, value in tags.items():
                    obj.with_property(f"tag_{key}", value)

            # Relationship: App -> Resource Group
            if rg_name:
                result.add_relationship(
                    parent=result.object(
                        adapter_kind=adapter_kind,
                        object_kind=OBJ_RESOURCE_GROUP,
                        name=rg_name,
                        identifiers=[
                            ("subscription_id", sub_id),
                            ("resource_group_name", rg_name),
                        ],
                    ),
                    child=obj,
                )

        total += len(apps)

    logger.info("Collected %d app services", total)


def _extract_rg(resource_id: str) -> str:
    parts = resource_id.split("/")
    for i, part in enumerate(parts):
        if part.lower() == "resourcegroups" and i + 1 < len(parts):
            return parts[i + 1]
    return ""
