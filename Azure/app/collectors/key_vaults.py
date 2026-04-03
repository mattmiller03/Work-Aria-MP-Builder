"""Collector for Azure Key Vaults."""

import logging

from azure_client import AzureClient
from constants import API_VERSIONS, OBJ_KEY_VAULT, OBJ_RESOURCE_GROUP
from helpers import make_identifiers

logger = logging.getLogger(__name__)


def collect_key_vaults(client: AzureClient, result, adapter_kind: str,
                       subscriptions: list, rgs_by_sub: dict):
    """Collect key vaults across all subscriptions.

    Key Vaults require per-resource-group listing since there is no
    subscription-wide list endpoint in the management plane.
    """
    logger.info("Collecting key vaults")
    total = 0

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]
        rgs = rgs_by_sub.get(sub_id, [])

        for rg in rgs:
            rg_name = rg["name"]
            vaults = client.get_all(
                path=(f"/subscriptions/{sub_id}/resourceGroups/{rg_name}"
                      f"/providers/Microsoft.KeyVault/vaults"),
                api_version=API_VERSIONS["key_vaults"],
            )

            for vault in vaults:
                vault_name = vault["name"]
                props = vault.get("properties", {})

                obj = result.object(
                    adapter_kind=adapter_kind,
                    object_kind=OBJ_KEY_VAULT,
                    name=vault_name,
                    identifiers=make_identifiers([
                        ("subscription_id", sub_id),
                        ("resource_group", rg_name),
                        ("vault_name", vault_name),
                    ]),
                )

                obj.with_property("vault_name", vault_name)
                obj.with_property("resource_id", vault.get("id", ""))
                obj.with_property("location", vault.get("location", ""))
                obj.with_property("subscription_id", sub_id)
                obj.with_property("resource_group", rg_name)
                obj.with_property("vault_uri", props.get("vaultUri", ""))
                obj.with_property("tenant_id", props.get("tenantId", ""))

                sku = props.get("sku", {})
                obj.with_property("sku_family", sku.get("family", ""))
                obj.with_property("sku_name", sku.get("name", ""))

                obj.with_property("soft_delete_enabled",
                                  str(props.get("enableSoftDelete", "")))
                obj.with_property("purge_protection_enabled",
                                  str(props.get("enablePurgeProtection", "")))
                obj.with_property("rbac_authorization_enabled",
                                  str(props.get("enableRbacAuthorization", "")))
                obj.with_property("soft_delete_retention_days",
                                  str(props.get("softDeleteRetentionInDays", "")))

                # Network ACLs
                net_acls = props.get("networkAcls", {})
                obj.with_property("network_default_action",
                                  net_acls.get("defaultAction", ""))

                # Tags
                tags = vault.get("tags", {})
                if tags:
                    for key, value in tags.items():
                        obj.with_property(f"tag_{key}", value)

                # Relationship: Key Vault -> Resource Group
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

                total += 1

    logger.info("Collected %d key vaults", total)
