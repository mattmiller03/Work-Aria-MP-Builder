"""Collector for Azure Storage Accounts."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_STORAGE_ACCOUNT, OBJ_RESOURCE_GROUP,
    RES_IDENT_SUB, RES_IDENT_RG, RES_IDENT_REGION, RES_IDENT_ID,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE, AZURE_SERVICE_NAMES,
)
from helpers import make_identifiers, extract_resource_group, safe_property, sanitize_tag_key
from collectors.metrics import collect_metrics_for_objects

logger = logging.getLogger(__name__)


def collect_storage_accounts(client: AzureClient, result, adapter_kind: str,
                             subscriptions: list):
    """Collect storage accounts across all subscriptions."""
    logger.info("Collecting storage accounts")
    total = 0
    sa_objects = {}  # resource_id -> aria obj

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]
        accounts = client.get_all(
            path=f"/subscriptions/{sub_id}/providers/Microsoft.Storage/storageAccounts",
            api_version=API_VERSIONS["storage_accounts"],
        )

        for acct in accounts:
            acct_name = acct["name"]
            rg_name = extract_resource_group(acct.get("id", ""))
            resource_id = acct.get("id", "")
            location = acct.get("location", "")
            props = acct.get("properties", {})
            sku = acct.get("sku", {})

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_STORAGE_ACCOUNT,
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
            safe_property(obj, SD_SERVICE, AZURE_SERVICE_NAMES.get(OBJ_STORAGE_ACCOUNT, ""))

            safe_property(obj, "summary|name", acct_name)
            safe_property(obj, "summary|creationTime", props.get("creationTime", ""))
            safe_property(obj, "summary|primaryLocation", location)
            safe_property(obj, "summary|enableHttpsTrafficOnly",
                          str(props.get("supportsHttpsTrafficOnly", "")))
            safe_property(obj, "summary|provisioningState",
                          props.get("provisioningState", ""))
            safe_property(obj, "resource_id", resource_id)
            safe_property(obj, "subscription_id", sub_id)
            safe_property(obj, "resource_group", rg_name)
            safe_property(obj, "kind", acct.get("kind", ""))
            safe_property(obj, "sku_name", sku.get("name", ""))
            safe_property(obj, "sku_tier", sku.get("tier", ""))
            safe_property(obj, "access_tier", props.get("accessTier", ""))
            safe_property(obj, "minimum_tls_version",
                          props.get("minimumTlsVersion", ""))
            safe_property(obj, "allow_blob_public_access",
                          str(props.get("allowBlobPublicAccess", "")))

            # Primary endpoints
            endpoints = props.get("primaryEndpoints", {})
            safe_property(obj, "endpoint_blob", endpoints.get("blob", ""))
            safe_property(obj, "endpoint_queue", endpoints.get("queue", ""))
            safe_property(obj, "endpoint_table", endpoints.get("table", ""))
            safe_property(obj, "endpoint_file", endpoints.get("file", ""))

            # Encryption
            enc = props.get("encryption", {})
            safe_property(obj, "encryption_key_source",
                          enc.get("keySource", ""))

            # Network rules
            net_rules = props.get("networkAcls", {})
            safe_property(obj, "network_default_action",
                          net_rules.get("defaultAction", ""))

            # Tags
            tags = acct.get("tags", {})
            if tags:
                for key, value in tags.items():
                    safe_property(obj, f"tag_{sanitize_tag_key(key)}", value)

            # Relationship: Storage Account -> Resource Group
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
                sa_objects[resource_id] = obj

        total += len(accounts)

    logger.info("Collected %d storage accounts", total)

    if sa_objects:
        collect_metrics_for_objects(client, sa_objects, "storage_accounts")
