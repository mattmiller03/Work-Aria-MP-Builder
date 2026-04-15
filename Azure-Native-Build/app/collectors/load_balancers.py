"""Collector for Azure Load Balancers."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_LOAD_BALANCER, OBJ_RESOURCE_GROUP,
    RES_IDENT_SUB, RES_IDENT_RG, RES_IDENT_REGION, RES_IDENT_ID,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE, AZURE_SERVICE_NAMES,
)
from helpers import make_identifiers, extract_resource_group, safe_property, sanitize_tag_key
from collectors.metrics import collect_metrics_for_objects

logger = logging.getLogger(__name__)


def collect_load_balancers(client: AzureClient, result, adapter_kind: str,
                           subscriptions: list):
    """Collect load balancers across all subscriptions."""
    logger.info("Collecting load balancers")
    total = 0
    lb_objects = {}  # resource_id -> aria obj

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]
        lbs = client.get_all(
            path=f"/subscriptions/{sub_id}/providers/Microsoft.Network/loadBalancers",
            api_version=API_VERSIONS["load_balancers"],
        )

        for lb in lbs:
            lb_name = lb["name"]
            rg_name = extract_resource_group(lb.get("id", ""))
            resource_id = lb.get("id", "")
            location = lb.get("location", "")
            props = lb.get("properties", {})
            sku = lb.get("sku", {})

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_LOAD_BALANCER,
                name=lb_name,
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
            safe_property(obj, SD_SERVICE, AZURE_SERVICE_NAMES.get(OBJ_LOAD_BALANCER, ""))

            safe_property(obj, "lb_name", lb_name)
            safe_property(obj, "resource_id", resource_id)
            safe_property(obj, "location", location)
            safe_property(obj, "subscription_id", sub_id)
            safe_property(obj, "resource_group", rg_name)
            safe_property(obj, "sku_name", sku.get("name", ""))
            safe_property(obj, "sku_tier", sku.get("tier", ""))
            safe_property(obj, "provisioning_state",
                          props.get("provisioningState", ""))

            # Frontend IP configs
            frontends = props.get("frontendIPConfigurations", [])
            safe_property(obj, "frontend_ip_count", len(frontends))
            frontend_names = [f.get("name", "") for f in frontends]
            safe_property(obj, "frontend_names", ", ".join(frontend_names))

            # Backend pools
            backends = props.get("backendAddressPools", [])
            safe_property(obj, "backend_pool_count", len(backends))
            backend_names = [b.get("name", "") for b in backends]
            safe_property(obj, "backend_pool_names", ", ".join(backend_names))

            # Load balancing rules
            rules = props.get("loadBalancingRules", [])
            safe_property(obj, "rule_count", len(rules))

            # Probes
            probes = props.get("probes", [])
            safe_property(obj, "probe_count", len(probes))

            # Inbound NAT rules
            nat_rules = props.get("inboundNatRules", [])
            safe_property(obj, "inbound_nat_rule_count", len(nat_rules))

            # Tags
            tags = lb.get("tags", {})
            if tags:
                for key, value in tags.items():
                    safe_property(obj, f"tag_{sanitize_tag_key(key)}", value)

            # Relationship: LB -> Resource Group
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
                lb_objects[resource_id] = obj

        total += len(lbs)

    logger.info("Collected %d load balancers", total)

    if lb_objects:
        collect_metrics_for_objects(client, lb_objects, "load_balancers")
