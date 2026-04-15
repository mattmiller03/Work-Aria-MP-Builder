"""Collector for Azure Cosmos DB Accounts."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_COSMOS_DB, OBJ_RESOURCE_GROUP,
    RES_IDENT_SUB, RES_IDENT_RG, RES_IDENT_REGION, RES_IDENT_ID,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE, AZURE_SERVICE_NAMES,
)
from helpers import make_identifiers, extract_resource_group, safe_property, sanitize_tag_key
from collectors.metrics import collect_metrics_for_objects

logger = logging.getLogger(__name__)


def collect_cosmos_db_accounts(client: AzureClient, result, adapter_kind: str,
                               subscriptions: list):
    """Collect Cosmos DB accounts across all subscriptions."""
    logger.info("Collecting Cosmos DB accounts")
    total = 0
    cosmos_objects = {}  # resource_id -> aria obj

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]
        accounts = client.get_all(
            path=f"/subscriptions/{sub_id}/providers/Microsoft.DocumentDB/databaseAccounts",
            api_version=API_VERSIONS["cosmos_db"],
        )

        for acct in accounts:
            acct_name = acct["name"]
            rg_name = extract_resource_group(acct.get("id", ""))
            resource_id = acct.get("id", "")
            location = acct.get("location", "")
            props = acct.get("properties", {})
            kind = acct.get("kind", "")

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_COSMOS_DB,
                name=acct_name,
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
            safe_property(obj, SD_SERVICE, AZURE_SERVICE_NAMES.get(OBJ_COSMOS_DB, ""))

            # Generic summary properties
            safe_property(obj, "genericsummary|Name", acct_name)
            safe_property(obj, "genericsummary|Location", location)
            safe_property(obj, "genericsummary|Id", resource_id)
            safe_property(obj, "genericsummary|Sku", "")
            safe_property(obj, "genericsummary|Type", acct.get("type", ""))

            # Deep properties
            safe_property(obj, "database_account_offer_type",
                          props.get("databaseAccountOfferType", ""))

            consistency_policy = props.get("consistencyPolicy", {})
            safe_property(obj, "consistency_level",
                          consistency_policy.get("defaultConsistencyLevel", ""))

            safe_property(obj, "enable_automatic_failover",
                          str(props.get("enableAutomaticFailover", "")))
            safe_property(obj, "enable_multiple_write_locations",
                          str(props.get("enableMultipleWriteLocations", "")))
            safe_property(obj, "is_virtual_network_filter_enabled",
                          str(props.get("isVirtualNetworkFilterEnabled", "")))
            safe_property(obj, "public_network_access",
                          props.get("publicNetworkAccess", ""))

            # Backup policy
            backup_policy = props.get("backupPolicy", {})
            safe_property(obj, "backup_policy_type",
                          backup_policy.get("type", ""))

            safe_property(obj, "total_throughput_limit",
                          str(props.get("capacity", {}).get("totalThroughputLimit", "")))

            # API kind — GlobalDocumentDB (SQL), MongoDB, etc.
            safe_property(obj, "api_kind", kind if kind else "GlobalDocumentDB")

            safe_property(obj, "document_endpoint",
                          props.get("documentEndpoint", ""))

            # Locations
            locations = props.get("locations", [])
            location_names = [loc.get("locationName", "") for loc in locations]
            safe_property(obj, "locations", ", ".join(location_names))

            read_locations = props.get("readLocations", [])
            read_names = [loc.get("locationName", "") for loc in read_locations]
            safe_property(obj, "read_locations", ", ".join(read_names))

            write_locations = props.get("writeLocations", [])
            write_names = [loc.get("locationName", "") for loc in write_locations]
            safe_property(obj, "write_locations", ", ".join(write_names))

            # IP rules
            ip_rules = props.get("ipRules", [])
            ip_list = [rule.get("ipAddressOrRange", "") for rule in ip_rules]
            safe_property(obj, "ip_rules", ", ".join(ip_list))

            # Capabilities
            capabilities = props.get("capabilities", [])
            cap_names = [cap.get("name", "") for cap in capabilities]
            safe_property(obj, "capabilities", ", ".join(cap_names))

            # Standard properties
            safe_property(obj, "resource_id", resource_id)
            safe_property(obj, "subscription_id", sub_id)
            safe_property(obj, "resource_group", rg_name)

            # Tags
            tags = acct.get("tags", {})
            if tags:
                for key, value in tags.items():
                    safe_property(obj, f"tag_{sanitize_tag_key(key)}", value)

            # Relationship: Cosmos DB Account -> Resource Group
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
                cosmos_objects[resource_id] = obj

            total += 1

    logger.info("Collected %d Cosmos DB accounts", total)

    if cosmos_objects:
        collect_metrics_for_objects(client, cosmos_objects, "cosmos_db")
