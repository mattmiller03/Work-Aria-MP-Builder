"""Collector for Azure Storage Accounts."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_STORAGE_ACCOUNT, OBJ_RESOURCE_GROUP,
    RES_IDENT_SUB, RES_IDENT_RG, RES_IDENT_REGION, RES_IDENT_ID,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE, AZURE_SERVICE_NAMES,
    MONITOR_METRICS,
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
                    safe_property(obj, f"summary|tags|{key}", value)

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

        # Collect sub-service metrics (blob, queue, file, table).
        # These use a sub-resource path and a different metric namespace.
        _SUB_SERVICES = [
            ("blobServices/default", "Microsoft.Storage/storageAccounts/blobServices", "storage_accounts_blob"),
            ("queueServices/default", "Microsoft.Storage/storageAccounts/queueServices", "storage_accounts_queue"),
            ("fileServices/default", "Microsoft.Storage/storageAccounts/fileServices", "storage_accounts_file"),
            ("tableServices/default", "Microsoft.Storage/storageAccounts/tableServices", "storage_accounts_table"),
        ]

        for sub_path, namespace, metrics_key in _SUB_SERVICES:
            metric_defs = MONITOR_METRICS.get(metrics_key, [])
            if not metric_defs:
                continue

            # Group by aggregation type to batch API calls
            by_aggregation = {}
            for azure_name, aria_key, aggregation in metric_defs:
                if aggregation not in by_aggregation:
                    by_aggregation[aggregation] = []
                by_aggregation[aggregation].append((azure_name, aria_key))

            errors = 0
            for resource_id, obj in sa_objects.items():
                sub_resource_id = f"{resource_id}/{sub_path}"
                for aggregation, metrics in by_aggregation.items():
                    azure_names = [m[0] for m in metrics]
                    aria_keys = {m[0]: m[1] for m in metrics}
                    try:
                        values = client.get_metrics(
                            resource_id=sub_resource_id,
                            metric_names=azure_names,
                            aggregation=aggregation,
                            metricnamespace=namespace,
                        )
                        for azure_name, value in values.items():
                            aria_key = aria_keys.get(azure_name)
                            if aria_key and value is not None:
                                obj.with_metric(aria_key, value)
                    except Exception as e:
                        errors += 1
                        if errors <= 3:
                            logger.warning("Sub-service metrics error (%s) for %s: %s",
                                           metrics_key, resource_id.split("/")[-1], e)

            logger.info("Sub-service metrics [%s]: processed %d storage accounts, %d errors",
                        metrics_key, len(sa_objects), errors)
