"""Generic ARM resource collector for simple resource types.

Most Azure resources follow the same pattern:
1. List via ARM API: GET /subscriptions/{sub}/providers/{namespace}
2. Extract standard properties (name, location, SKU, provisioning state, tags)
3. Set SERVICE_DESCRIPTORS
4. Parent to Resource Group

This module provides a factory function that generates collectors for any
resource type following this pattern, avoiding 70+ nearly-identical files.
"""

import logging

from azure_client import AzureClient
from constants import (
    OBJ_RESOURCE_GROUP,
    RES_IDENT_SUB, RES_IDENT_RG, RES_IDENT_REGION, RES_IDENT_ID,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE,
    AZURE_SERVICE_NAMES,
)
from helpers import make_identifiers, extract_resource_group, safe_property

logger = logging.getLogger(__name__)


def collect_generic_arm_resources(
    client: AzureClient,
    result,
    adapter_kind: str,
    subscriptions: list,
    resource_kind: str,
    arm_provider_path: str,
    api_version: str,
    extra_properties_fn=None,
):
    """Collect resources of a given type from the ARM API.

    Args:
        client: Azure REST client.
        result: CollectResult to populate.
        adapter_kind: Adapter kind string.
        subscriptions: List of subscription dicts.
        resource_kind: Aria Ops object type key (e.g., 'AZURE_FIREWALLS').
        arm_provider_path: ARM provider path (e.g., 'Microsoft.Network/azureFirewalls').
        api_version: Azure API version string.
        extra_properties_fn: Optional callable(obj, resource_dict, props_dict)
            to set additional type-specific properties beyond the generic ones.

    Returns:
        Total count of resources collected.
    """
    logger.info("Collecting %s resources", resource_kind)
    total = 0

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]

        try:
            resources = client.get_all(
                path=f"/subscriptions/{sub_id}/providers/{arm_provider_path}",
                api_version=api_version,
            )
        except Exception as e:
            logger.warning("Failed to list %s in subscription %s: %s",
                           resource_kind, sub_id, e)
            continue

        for resource in resources:
            name = resource.get("name", "")
            resource_id = resource.get("id", "")
            location = resource.get("location", "")
            rg_name = extract_resource_group(resource_id)
            props = resource.get("properties", {})
            sku = resource.get("sku", {})

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=resource_kind,
                name=name,
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
            safe_property(obj, SD_SERVICE,
                          AZURE_SERVICE_NAMES.get(resource_kind, ""))

            # Standard summary properties (native pak pattern)
            safe_property(obj, "summary|name", name)
            safe_property(obj, "summary|id", resource_id)
            safe_property(obj, "summary|type", resource.get("type", ""))
            safe_property(obj, "summary|provisioningState",
                          props.get("provisioningState", ""))
            safe_property(obj, "summary|regionName", location)

            # Tags — native pak format: summary|tags|{key}
            tags = resource.get("tags", {})
            if tags:
                safe_property(obj, "summary|tags",
                              str(tags))
                for key, value in tags.items():
                    safe_property(obj, f"summary|tags|{key}", value)

            # SKU if present
            if sku:
                safe_property(obj, "genericsummary|Sku",
                              sku.get("name", str(sku)))

            # Generic summary
            safe_property(obj, "genericsummary|Name", name)
            safe_property(obj, "genericsummary|Location", location)
            safe_property(obj, "genericsummary|Id", resource_id)
            safe_property(obj, "genericsummary|Type",
                          resource.get("type", ""))

            # Type-specific properties
            if extra_properties_fn:
                try:
                    extra_properties_fn(obj, resource, props)
                except Exception as e:
                    logger.debug("Extra properties failed for %s/%s: %s",
                                 resource_kind, name, e)

            # Parent: Resource Group
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

            total += 1

    logger.info("Collected %d %s resources", total, resource_kind)
    return total
