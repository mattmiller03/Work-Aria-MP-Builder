"""Collector for Azure Storage Accounts."""

import logging

from azure_client import AzureClient
from constants import API_VERSIONS, OBJ_STORAGE_ACCOUNT, OBJ_RESOURCE_GROUP
from helpers import make_identifiers, extract_resource_group

logger = logging.getLogger(__name__)


def collect_storage_accounts(client: AzureClient, result, adapter_kind: str,
                             subscriptions: list):
    """Collect storage accounts across all subscriptions."""
    logger.info("Collecting storage accounts")
    total = 0

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]
        accounts = client.get_all(
            path=f"/subscriptions/{sub_id}/providers/Microsoft.Storage/storageAccounts",
            api_version=API_VERSIONS["storage_accounts"],
        )

        for acct in accounts:
            acct_name = acct["name"]
            rg_name = extract_resource_group(acct.get("id", ""))
            props = acct.get("properties", {})
            sku = acct.get("sku", {})

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_STORAGE_ACCOUNT,
                name=acct_name,
                identifiers=make_identifiers([
                    ("subscription_id", sub_id),
                    ("resource_group", rg_name),
                    ("account_name", acct_name),
                ]),
            )

            obj.with_property("account_name", acct_name)
            obj.with_property("resource_id", acct.get("id", ""))
            obj.with_property("location", acct.get("location", ""))
            obj.with_property("subscription_id", sub_id)
            obj.with_property("resource_group", rg_name)
            obj.with_property("kind", acct.get("kind", ""))
            obj.with_property("sku_name", sku.get("name", ""))
            obj.with_property("sku_tier", sku.get("tier", ""))
            obj.with_property("provisioning_state",
                              props.get("provisioningState", ""))
            obj.with_property("creation_time", props.get("creationTime", ""))
            obj.with_property("access_tier", props.get("accessTier", ""))
            obj.with_property("https_only",
                              str(props.get("supportsHttpsTrafficOnly", "")))
            obj.with_property("minimum_tls_version",
                              props.get("minimumTlsVersion", ""))
            obj.with_property("allow_blob_public_access",
                              str(props.get("allowBlobPublicAccess", "")))

            # Primary endpoints
            endpoints = props.get("primaryEndpoints", {})
            obj.with_property("endpoint_blob", endpoints.get("blob", ""))
            obj.with_property("endpoint_queue", endpoints.get("queue", ""))
            obj.with_property("endpoint_table", endpoints.get("table", ""))
            obj.with_property("endpoint_file", endpoints.get("file", ""))

            # Encryption
            enc = props.get("encryption", {})
            obj.with_property("encryption_key_source",
                              enc.get("keySource", ""))

            # Network rules
            net_rules = props.get("networkAcls", {})
            obj.with_property("network_default_action",
                              net_rules.get("defaultAction", ""))

            # Tags
            tags = acct.get("tags", {})
            if tags:
                for key, value in tags.items():
                    obj.with_property(f"tag_{key}", value)

            # Relationship: Storage Account -> Resource Group
            if rg_name:
                rg_obj = result.object(
                    adapter_kind=adapter_kind,
                    object_kind=OBJ_RESOURCE_GROUP,
                    name=rg_name,
                    identifiers=make_identifiers([
                        ("subscription_id", sub_id),
                        ("resource_group_name", rg_name),
                    ]),
                )
                obj.add_parent(rg_obj)

        total += len(accounts)

    logger.info("Collected %d storage accounts", total)
