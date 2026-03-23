"""Collector for Azure SQL Servers and Databases."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_SQL_SERVER, OBJ_SQL_DATABASE, OBJ_RESOURCE_GROUP,
)

logger = logging.getLogger(__name__)


def collect_sql_servers_and_databases(client: AzureClient, result,
                                     adapter_kind: str, subscriptions: list):
    """Collect SQL servers and their databases across all subscriptions."""
    logger.info("Collecting SQL servers and databases")
    total_servers = 0
    total_dbs = 0

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]

        # List SQL servers in subscription
        servers = client.get_all(
            path=f"/subscriptions/{sub_id}/providers/Microsoft.Sql/servers",
            api_version=API_VERSIONS["sql_servers"],
        )

        for server in servers:
            srv_name = server["name"]
            rg_name = _extract_rg(server.get("id", ""))
            srv_props = server.get("properties", {})

            srv_obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_SQL_SERVER,
                name=srv_name,
                identifiers=[
                    ("subscription_id", sub_id),
                    ("resource_group", rg_name),
                    ("server_name", srv_name),
                ],
            )

            srv_obj.with_property("server_name", srv_name)
            srv_obj.with_property("resource_id", server.get("id", ""))
            srv_obj.with_property("location", server.get("location", ""))
            srv_obj.with_property("subscription_id", sub_id)
            srv_obj.with_property("resource_group", rg_name)
            srv_obj.with_property("fqdn",
                                  srv_props.get("fullyQualifiedDomainName", ""))
            srv_obj.with_property("state", srv_props.get("state", ""))
            srv_obj.with_property("version", srv_props.get("version", ""))
            srv_obj.with_property("admin_login",
                                  srv_props.get("administratorLogin", ""))
            srv_obj.with_property("public_network_access",
                                  srv_props.get("publicNetworkAccess", ""))
            srv_obj.with_property("minimal_tls_version",
                                  srv_props.get("minimalTlsVersion", ""))

            # Tags
            tags = server.get("tags", {})
            if tags:
                for key, value in tags.items():
                    srv_obj.with_property(f"tag_{key}", value)

            # Relationship: SQL Server -> Resource Group
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
                    child=srv_obj,
                )

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

                db_obj = result.object(
                    adapter_kind=adapter_kind,
                    object_kind=OBJ_SQL_DATABASE,
                    name=db_name,
                    identifiers=[
                        ("subscription_id", sub_id),
                        ("server_name", srv_name),
                        ("database_name", db_name),
                    ],
                )

                db_obj.with_property("database_name", db_name)
                db_obj.with_property("resource_id", db.get("id", ""))
                db_obj.with_property("location", db.get("location", ""))
                db_obj.with_property("subscription_id", sub_id)
                db_obj.with_property("server_name", srv_name)
                db_obj.with_property("status", db_props.get("status", ""))
                db_obj.with_property("database_id",
                                     db_props.get("databaseId", ""))
                db_obj.with_property("sku_name", db_sku.get("name", ""))
                db_obj.with_property("sku_tier", db_sku.get("tier", ""))
                db_obj.with_property("sku_capacity",
                                     str(db_sku.get("capacity", "")))
                db_obj.with_property("max_size_bytes",
                                     str(db_props.get("maxSizeBytes", "")))
                db_obj.with_property("collation",
                                     db_props.get("collation", ""))
                db_obj.with_property("creation_date",
                                     db_props.get("creationDate", ""))
                db_obj.with_property("current_service_objective",
                                     db_props.get("currentServiceObjectiveName", ""))
                db_obj.with_property("zone_redundant",
                                     str(db_props.get("zoneRedundant", "")))

                # Tags
                db_tags = db.get("tags", {})
                if db_tags:
                    for key, value in db_tags.items():
                        db_obj.with_property(f"tag_{key}", value)

                # Relationship: Database -> SQL Server (parent)
                result.add_relationship(parent=srv_obj, child=db_obj)
                total_dbs += 1

        total_servers += len(servers)

    logger.info("Collected %d SQL servers, %d databases",
                total_servers, total_dbs)


def _extract_rg(resource_id: str) -> str:
    parts = resource_id.split("/")
    for i, part in enumerate(parts):
        if part.lower() == "resourcegroups" and i + 1 < len(parts):
            return parts[i + 1]
    return ""
