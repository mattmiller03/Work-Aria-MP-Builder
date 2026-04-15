"""Collector for Azure ExpressRoute Circuits."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_EXPRESSROUTE, OBJ_RESOURCE_GROUP,
    RES_IDENT_SUB, RES_IDENT_RG, RES_IDENT_REGION, RES_IDENT_ID,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE, AZURE_SERVICE_NAMES,
)
from helpers import make_identifiers, extract_resource_group, safe_property, sanitize_tag_key

logger = logging.getLogger(__name__)


def collect_expressroute_circuits(client: AzureClient, result, adapter_kind: str,
                                  subscriptions: list):
    """Collect ExpressRoute circuits across all subscriptions."""
    logger.info("Collecting ExpressRoute circuits")
    total = 0

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]
        circuits = client.get_all(
            path=f"/subscriptions/{sub_id}/providers/Microsoft.Network/expressRouteCircuits",
            api_version=API_VERSIONS["expressroute"],
        )

        for circuit in circuits:
            name = circuit["name"]
            resource_id = circuit.get("id", "")
            rg_name = extract_resource_group(resource_id)
            location = circuit.get("location", "")
            props = circuit.get("properties", {})
            sku = circuit.get("sku", {})

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_EXPRESSROUTE,
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
            safe_property(obj, SD_SERVICE, AZURE_SERVICE_NAMES.get(OBJ_EXPRESSROUTE, ""))

            safe_property(obj, "circuit_name", name)
            safe_property(obj, "resource_id", resource_id)
            safe_property(obj, "location", location)
            safe_property(obj, "subscription_id", sub_id)
            safe_property(obj, "resource_group", rg_name)
            safe_property(obj, "sku_name", sku.get("name", ""))
            safe_property(obj, "sku_tier", sku.get("tier", ""))
            safe_property(obj, "sku_family", sku.get("family", ""))
            safe_property(obj, "circuit_provisioning_state",
                          props.get("circuitProvisioningState", ""))
            safe_property(obj, "service_provider_provisioning_state",
                          props.get("serviceProviderProvisioningState", ""))
            safe_property(obj, "service_key", props.get("serviceKey", ""))
            safe_property(obj, "bandwidth_in_mbps",
                          props.get("serviceProviderProperties", {}).get("bandwidthInMbps", ""))
            safe_property(obj, "peering_location",
                          props.get("serviceProviderProperties", {}).get("peeringLocation", ""))
            safe_property(obj, "service_provider_name",
                          props.get("serviceProviderProperties", {}).get("serviceProviderName", ""))
            safe_property(obj, "provisioning_state",
                          props.get("provisioningState", ""))
            safe_property(obj, "allow_classic_operations",
                          str(props.get("allowClassicOperations", "")))
            safe_property(obj, "global_reach_enabled",
                          str(props.get("globalReachEnabled", "")))

            # Peerings
            peerings = props.get("peerings", [])
            safe_property(obj, "peering_count", len(peerings))
            peering_names = [p.get("name", "") for p in peerings]
            safe_property(obj, "peering_names", ", ".join(peering_names))

            # Tags
            tags = circuit.get("tags", {})
            if tags:
                for key, value in tags.items():
                    safe_property(obj, f"tag_{sanitize_tag_key(key)}", value)

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

        total += len(circuits)

    logger.info("Collected %d ExpressRoute circuits", total)
