"""Collector for Azure Database for PostgreSQL Servers."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_POSTGRESQL, OBJ_RESOURCE_GROUP,
    RES_IDENT_SUB, RES_IDENT_RG, RES_IDENT_REGION, RES_IDENT_ID,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE, AZURE_SERVICE_NAMES,
)
from helpers import make_identifiers, extract_resource_group, safe_property, sanitize_tag_key
from collectors.metrics import collect_metrics_for_objects

logger = logging.getLogger(__name__)


def collect_postgresql_servers(client: AzureClient, result,
                               adapter_kind: str, subscriptions: list):
    """Collect PostgreSQL servers across all subscriptions.

    Tries flexible servers first, falls back to single servers.
    """
    logger.info("Collecting PostgreSQL servers")
    total = 0
    srv_objects = {}  # resource_id -> aria obj

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]

        # Try flexible servers first
        servers = client.get_all(
            path=(f"/subscriptions/{sub_id}/providers"
                  f"/Microsoft.DBforPostgreSQL/flexibleServers"),
            api_version=API_VERSIONS["postgresql_servers"],
        )

        # Fall back to single servers if no flexible servers found
        if not servers:
            servers = client.get_all(
                path=(f"/subscriptions/{sub_id}/providers"
                      f"/Microsoft.DBforPostgreSQL/servers"),
                api_version="2017-12-01",
            )

        for server in servers:
            srv_name = server["name"]
            rg_name = extract_resource_group(server.get("id", ""))
            resource_id = server.get("id", "")
            location = server.get("location", "")
            props = server.get("properties", {})
            sku = server.get("sku", {})

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_POSTGRESQL,
                name=srv_name,
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
            safe_property(obj, SD_SERVICE, AZURE_SERVICE_NAMES.get(OBJ_POSTGRESQL, ""))

            safe_property(obj, "server_name", srv_name)
            safe_property(obj, "resource_id", resource_id)
            safe_property(obj, "location", location)
            safe_property(obj, "subscription_id", sub_id)
            safe_property(obj, "resource_group", rg_name)

            # PostgreSQL properties
            safe_property(obj, "version", props.get("version", ""))
            safe_property(obj, "sku_name", sku.get("name", ""))
            safe_property(obj, "sku_tier", sku.get("tier", ""))
            safe_property(obj, "sku_capacity",
                          str(sku.get("capacity", "")))

            # Storage
            storage = props.get("storage", props.get("storageProfile", {}))
            safe_property(obj, "storage_mb",
                          str(storage.get("storageMB",
                              storage.get("storageSizeGB", ""))))

            # Security
            safe_property(obj, "ssl_enforcement",
                          props.get("sslEnforcement", ""))
            safe_property(obj, "minimal_tls_version",
                          props.get("minimalTlsVersion", ""))
            safe_property(obj, "infrastructure_encryption",
                          props.get("infrastructureEncryption", ""))
            safe_property(obj, "public_network_access",
                          props.get("publicNetworkAccess", ""))

            # Server info
            safe_property(obj, "fqdn",
                          props.get("fullyQualifiedDomainName", ""))
            safe_property(obj, "admin_login",
                          props.get("administratorLogin", ""))
            safe_property(obj, "user_visible_state",
                          props.get("userVisibleState",
                              props.get("state", "")))

            # Backup
            backup = props.get("backup", props.get("storageProfile", {}))
            safe_property(obj, "backup_retention_days",
                          str(backup.get("backupRetentionDays",
                              backup.get("retentionDays", ""))))
            safe_property(obj, "geo_redundant_backup",
                          backup.get("geoRedundantBackup", ""))

            # High availability
            ha = props.get("highAvailability", {})
            safe_property(obj, "ha_enabled",
                          ha.get("state", ""))
            safe_property(obj, "ha_mode",
                          ha.get("mode", ""))

            # Availability zone
            safe_property(obj, "availability_zone",
                          props.get("availabilityZone", ""))

            # Replication
            safe_property(obj, "replication_role",
                          props.get("replicationRole", ""))

            # Tags
            tags = server.get("tags", {})
            if tags:
                for key, value in tags.items():
                    safe_property(obj, f"tag_{sanitize_tag_key(key)}", value)

            # Relationship: PostgreSQL Server -> Resource Group
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

            if resource_id:
                srv_objects[resource_id] = obj

        total += len(servers)

    logger.info("Collected %d PostgreSQL servers", total)

    if srv_objects:
        collect_metrics_for_objects(client, srv_objects, "postgresql_servers")
