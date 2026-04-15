"""Collector for Azure Key Vaults."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_KEY_VAULT, OBJ_RESOURCE_GROUP,
    RES_IDENT_SUB, RES_IDENT_RG, RES_IDENT_REGION, RES_IDENT_ID,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE, AZURE_SERVICE_NAMES,
)
from helpers import make_identifiers, safe_property, sanitize_tag_key

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
                resource_id = vault.get("id", "")
                location = vault.get("location", "")
                props = vault.get("properties", {})
                sku = props.get("sku", {})

                obj = result.object(
                    adapter_kind=adapter_kind,
                    object_kind=OBJ_KEY_VAULT,
                    name=vault_name,
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
                safe_property(obj, SD_SERVICE, AZURE_SERVICE_NAMES.get(OBJ_KEY_VAULT, ""))

                # Native pak summary properties
                safe_property(obj, "summary|name", vault_name)
                safe_property(obj, "summary|id", resource_id)
                safe_property(obj, "summary|vaultUri", props.get("vaultUri", ""))
                safe_property(obj, "summary|tenantId", props.get("tenantId", ""))
                safe_property(obj, "summary|softDeleteEnabled",
                              str(props.get("enableSoftDelete", "")))
                safe_property(obj, "summary|purgeProtectionEnabled",
                              str(props.get("enablePurgeProtection", "")))
                safe_property(obj, "summary|regionName", location)
                safe_property(obj, "summary|type", vault.get("type", ""))
                safe_property(obj, "summary|tags", str(vault.get("tags", {})))
                safe_property(obj, "summary|createMode", props.get("createMode", ""))
                safe_property(obj, "summary|enabledForDeployment",
                              str(props.get("enabledForDeployment", "")))
                safe_property(obj, "summary|enabledForDiskEncryption",
                              str(props.get("enabledForDiskEncryption", "")))
                safe_property(obj, "summary|enabledForTemplateDeployment",
                              str(props.get("enabledForTemplateDeployment", "")))
                safe_property(obj, "summary|client", "")

                # Generic summary properties
                safe_property(obj, "genericsummary|Name", vault_name)
                safe_property(obj, "genericsummary|Location", location)
                safe_property(obj, "genericsummary|Id", resource_id)
                safe_property(obj, "genericsummary|Sku", sku.get("name", ""))
                safe_property(obj, "genericsummary|Type", vault.get("type", ""))

                # Additive custom properties
                safe_property(obj, "subscription_id", sub_id)
                safe_property(obj, "resource_group", rg_name)
                safe_property(obj, "sku_family", sku.get("family", ""))
                safe_property(obj, "sku_name", sku.get("name", ""))
                safe_property(obj, "rbac_authorization_enabled",
                              str(props.get("enableRbacAuthorization", "")))
                safe_property(obj, "soft_delete_retention_days",
                              str(props.get("softDeleteRetentionInDays", "")))

                # Network ACLs
                net_acls = props.get("networkAcls", {})
                safe_property(obj, "network_default_action",
                              net_acls.get("defaultAction", ""))

                # Tags
                tags = vault.get("tags", {})
                if tags:
                    for key, value in tags.items():
                        safe_property(obj, f"tag_{sanitize_tag_key(key)}", value)

                # Relationship: Key Vault -> Resource Group
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

                total += 1

    logger.info("Collected %d key vaults", total)
