"""Collector for Azure Recovery Services Vaults."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_RECOVERY_VAULT, OBJ_RESOURCE_GROUP,
    RES_IDENT_SUB, RES_IDENT_RG, RES_IDENT_REGION, RES_IDENT_ID,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE, AZURE_SERVICE_NAMES,
)
from helpers import make_identifiers, extract_resource_group, safe_property, sanitize_tag_key

logger = logging.getLogger(__name__)


def collect_recovery_vaults(client: AzureClient, result, adapter_kind: str,
                            subscriptions: list):
    """Collect Recovery Services vaults across all subscriptions."""
    logger.info("Collecting Recovery Services vaults")
    total = 0

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]
        vaults = client.get_all(
            path=f"/subscriptions/{sub_id}/providers/Microsoft.RecoveryServices/vaults",
            api_version=API_VERSIONS["recovery_vaults"],
        )

        for vault in vaults:
            vault_name = vault["name"]
            resource_id = vault.get("id", "")
            rg_name = extract_resource_group(resource_id)
            location = vault.get("location", "")
            props = vault.get("properties", {})
            sku = vault.get("sku", {})

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_RECOVERY_VAULT,
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
            safe_property(obj, SD_SERVICE, AZURE_SERVICE_NAMES.get(OBJ_RECOVERY_VAULT, ""))

            safe_property(obj, "vault_name", vault_name)
            safe_property(obj, "resource_id", resource_id)
            safe_property(obj, "location", location)
            safe_property(obj, "subscription_id", sub_id)
            safe_property(obj, "resource_group", rg_name)
            safe_property(obj, "sku_name", sku.get("name", ""))
            safe_property(obj, "sku_tier", sku.get("tier", ""))
            safe_property(obj, "provisioning_state",
                          props.get("provisioningState", ""))
            safe_property(obj, "private_endpoint_state_for_backup",
                          props.get("privateEndpointStateForBackup", ""))
            safe_property(obj, "private_endpoint_state_for_site_recovery",
                          props.get("privateEndpointStateForSiteRecovery", ""))

            # Redundancy settings
            safe_property(obj, "storage_type",
                          props.get("redundancySettings", {}).get("standardTierStorageRedundancy", ""))
            safe_property(obj, "cross_region_restore",
                          str(props.get("redundancySettings", {}).get("crossRegionRestore", "")))

            # Security
            safe_property(obj, "immutability_state",
                          props.get("securitySettings", {}).get("immutabilitySettings", {}).get("state", ""))
            safe_property(obj, "soft_delete_state",
                          props.get("securitySettings", {}).get("softDeleteSettings", {}).get("softDeleteState", ""))

            # Tags
            tags = vault.get("tags", {})
            if tags:
                for key, value in tags.items():
                    safe_property(obj, f"summary|tags|{key}", value)

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

        total += len(vaults)

    logger.info("Collected %d Recovery Services vaults", total)
