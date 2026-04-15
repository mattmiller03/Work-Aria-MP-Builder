"""Collector for Azure SQL Servers and Databases."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_SQL_SERVER, OBJ_SQL_DATABASE, OBJ_RESOURCE_GROUP,
    RES_IDENT_SUB, RES_IDENT_RG, RES_IDENT_REGION, RES_IDENT_ID,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE, AZURE_SERVICE_NAMES,
)
from helpers import make_identifiers, extract_resource_group, safe_property, sanitize_tag_key
from collectors.metrics import collect_metrics_for_objects

logger = logging.getLogger(__name__)


def collect_sql_servers_and_databases(client: AzureClient, result,
                                     adapter_kind: str, subscriptions: list):
    """Collect SQL servers and their databases across all subscriptions."""
    logger.info("Collecting SQL servers and databases")
    total_servers = 0
    total_dbs = 0
    srv_objects = {}  # resource_id -> aria obj (servers)
    db_objects = {}  # resource_id -> aria obj (databases)

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]

        # List SQL servers in subscription
        servers = client.get_all(
            path=f"/subscriptions/{sub_id}/providers/Microsoft.Sql/servers",
            api_version=API_VERSIONS["sql_servers"],
        )

        for server in servers:
            srv_name = server["name"]
            rg_name = extract_resource_group(server.get("id", ""))
            srv_resource_id = server.get("id", "")
            srv_location = server.get("location", "")
            srv_props = server.get("properties", {})

            srv_obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_SQL_SERVER,
                name=srv_name,
                identifiers=make_identifiers([
                    (RES_IDENT_SUB, sub_id),
                    (RES_IDENT_RG, rg_name),
                    (RES_IDENT_REGION, srv_location),
                    (RES_IDENT_ID, srv_resource_id),
                ]),
            )

            # SERVICE_DESCRIPTORS
            safe_property(srv_obj, SD_SUBSCRIPTION, sub_id)
            safe_property(srv_obj, SD_RESOURCE_GROUP, rg_name)
            safe_property(srv_obj, SD_REGION, srv_location)
            safe_property(srv_obj, SD_SERVICE, AZURE_SERVICE_NAMES.get(OBJ_SQL_SERVER, ""))

            safe_property(srv_obj, "server_name", srv_name)
            safe_property(srv_obj, "resource_id", srv_resource_id)
            safe_property(srv_obj, "location", srv_location)
            safe_property(srv_obj, "subscription_id", sub_id)
            safe_property(srv_obj, "resource_group", rg_name)
            safe_property(srv_obj, "fqdn",
                          srv_props.get("fullyQualifiedDomainName", ""))
            safe_property(srv_obj, "state", srv_props.get("state", ""))
            safe_property(srv_obj, "version", srv_props.get("version", ""))
            safe_property(srv_obj, "admin_login",
                          srv_props.get("administratorLogin", ""))
            safe_property(srv_obj, "public_network_access",
                          srv_props.get("publicNetworkAccess", ""))
            safe_property(srv_obj, "minimal_tls_version",
                          srv_props.get("minimalTlsVersion", ""))

            # Tags
            tags = server.get("tags", {})
            if tags:
                for key, value in tags.items():
                    safe_property(srv_obj, f"tag_{sanitize_tag_key(key)}", value)

            # Relationship: SQL Server -> Resource Group
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
                srv_obj.add_parent(rg_obj)

            if srv_resource_id:
                srv_objects[srv_resource_id] = srv_obj

            # List databases on this server
            databases = client.get_all(
                path=(f"/subscriptions/{sub_id}/resourceGroups/{rg_name}"
                      f"/providers/Microsoft.Sql/servers/{srv_name}/databases"),
                api_version=API_VERSIONS["sql_databases"],
            )

            for db in databases:
                db_name = db["name"]
                # Skip the system 'master' database
                if db_name.lower() == "master":
                    continue

                db_props = db.get("properties", {})
                db_sku = db.get("sku", {})
                db_resource_id = db.get("id", "")
                db_location = db.get("location", "")

                db_obj = result.object(
                    adapter_kind=adapter_kind,
                    object_kind=OBJ_SQL_DATABASE,
                    name=db_name,
                    identifiers=make_identifiers([
                        (RES_IDENT_SUB, sub_id),
                        (RES_IDENT_RG, rg_name),
                        (RES_IDENT_REGION, db_location),
                        (RES_IDENT_ID, db_resource_id),
                        ("SERVER_ID", srv_resource_id),
                    ]),
                )

                # SERVICE_DESCRIPTORS
                safe_property(db_obj, SD_SUBSCRIPTION, sub_id)
                safe_property(db_obj, SD_RESOURCE_GROUP, rg_name)
                safe_property(db_obj, SD_REGION, db_location)
                safe_property(db_obj, SD_SERVICE, AZURE_SERVICE_NAMES.get(OBJ_SQL_DATABASE, ""))

                safe_property(db_obj, "database_name", db_name)
                safe_property(db_obj, "resource_id", db_resource_id)
                safe_property(db_obj, "location", db_location)
                safe_property(db_obj, "subscription_id", sub_id)
                safe_property(db_obj, "server_name", srv_name)
                safe_property(db_obj, "status", db_props.get("status", ""))
                safe_property(db_obj, "database_id",
                              db_props.get("databaseId", ""))
                safe_property(db_obj, "sku_name", db_sku.get("name", ""))
                safe_property(db_obj, "sku_tier", db_sku.get("tier", ""))
                safe_property(db_obj, "sku_capacity",
                              str(db_sku.get("capacity", "")))
                safe_property(db_obj, "max_size_bytes",
                              str(db_props.get("maxSizeBytes", "")))
                safe_property(db_obj, "collation",
                              db_props.get("collation", ""))
                safe_property(db_obj, "creation_date",
                              db_props.get("creationDate", ""))
                safe_property(db_obj, "current_service_objective",
                              db_props.get("currentServiceObjectiveName", ""))
                safe_property(db_obj, "zone_redundant",
                              str(db_props.get("zoneRedundant", "")))

                # Tags
                db_tags = db.get("tags", {})
                if db_tags:
                    for key, value in db_tags.items():
                        safe_property(db_obj, f"tag_{sanitize_tag_key(key)}", value)

                # Relationship: Database -> SQL Server (parent)
                db_obj.add_parent(srv_obj)
                total_dbs += 1

                if db_resource_id:
                    db_objects[db_resource_id] = db_obj

        total_servers += len(servers)

    logger.info("Collected %d SQL servers, %d databases",
                total_servers, total_dbs)

    if srv_objects:
        collect_metrics_for_objects(client, srv_objects, "sql_servers")
    if db_objects:
        collect_metrics_for_objects(client, db_objects, "sql_databases")
