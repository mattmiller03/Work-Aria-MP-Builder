"""Collector for Azure Load Balancers."""

import logging

from azure_client import AzureClient
from constants import API_VERSIONS, OBJ_LOAD_BALANCER, OBJ_RESOURCE_GROUP

logger = logging.getLogger(__name__)


def collect_load_balancers(client: AzureClient, result, adapter_kind: str,
                           subscriptions: list):
    """Collect load balancers across all subscriptions."""
    logger.info("Collecting load balancers")
    total = 0

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]
        lbs = client.get_all(
            path=f"/subscriptions/{sub_id}/providers/Microsoft.Network/loadBalancers",
            api_version=API_VERSIONS["load_balancers"],
        )

        for lb in lbs:
            lb_name = lb["name"]
            rg_name = _extract_rg(lb.get("id", ""))
            props = lb.get("properties", {})
            sku = lb.get("sku", {})

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_LOAD_BALANCER,
                name=lb_name,
                identifiers=[
                    ("subscription_id", sub_id),
                    ("resource_group", rg_name),
                    ("lb_name", lb_name),
                ],
            )

            obj.with_property("lb_name", lb_name)
            obj.with_property("resource_id", lb.get("id", ""))
            obj.with_property("location", lb.get("location", ""))
            obj.with_property("subscription_id", sub_id)
            obj.with_property("resource_group", rg_name)
            obj.with_property("sku_name", sku.get("name", ""))
            obj.with_property("sku_tier", sku.get("tier", ""))
            obj.with_property("provisioning_state",
                              props.get("provisioningState", ""))

            # Frontend IP configs
            frontends = props.get("frontendIPConfigurations", [])
            obj.with_property("frontend_ip_count", len(frontends))
            frontend_names = [f.get("name", "") for f in frontends]
            obj.with_property("frontend_names", ", ".join(frontend_names))

            # Backend pools
            backends = props.get("backendAddressPools", [])
            obj.with_property("backend_pool_count", len(backends))
            backend_names = [b.get("name", "") for b in backends]
            obj.with_property("backend_pool_names", ", ".join(backend_names))

            # Load balancing rules
            rules = props.get("loadBalancingRules", [])
            obj.with_property("rule_count", len(rules))

            # Probes
            probes = props.get("probes", [])
            obj.with_property("probe_count", len(probes))

            # Inbound NAT rules
            nat_rules = props.get("inboundNatRules", [])
            obj.with_property("inbound_nat_rule_count", len(nat_rules))

            # Tags
            tags = lb.get("tags", {})
            if tags:
                for key, value in tags.items():
                    obj.with_property(f"tag_{key}", value)

            # Relationship: LB -> Resource Group
            if rg_name:
                result.add_relationship(
                    parent=result.object(
                        adapter_kind=adapter_kind,
                        object_kind=OBJ_RESOURCE_GROUP,
                        name=rg_name,
                        identifiers=[
                            ("subscription_id", sub_id),
                            ("resource_group_name", rg_name),
                        ],
                    ),
                    child=obj,
                )

        total += len(lbs)

    logger.info("Collected %d load balancers", total)


def _extract_rg(resource_id: str) -> str:
    parts = resource_id.split("/")
    for i, part in enumerate(parts):
        if part.lower() == "resourcegroups" and i + 1 < len(parts):
            return parts[i + 1]
    return ""
