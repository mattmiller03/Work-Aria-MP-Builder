"""Collector for Azure Virtual Networks and Subnets."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_VIRTUAL_NETWORK, OBJ_SUBNET, OBJ_RESOURCE_GROUP,
)

logger = logging.getLogger(__name__)


def collect_virtual_networks(client: AzureClient, result, adapter_kind: str,
                             subscriptions: list):
    """Collect virtual networks and subnets across all subscriptions."""
    logger.info("Collecting virtual networks")
    total_vnets = 0
    total_subnets = 0

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]
        vnets = client.get_all(
            path=f"/subscriptions/{sub_id}/providers/Microsoft.Network/virtualNetworks",
            api_version=API_VERSIONS["virtual_networks"],
        )

        for vnet in vnets:
            vnet_name = vnet["name"]
            rg_name = _extract_rg(vnet.get("id", ""))
            props = vnet.get("properties", {})

            vnet_obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_VIRTUAL_NETWORK,
                name=vnet_name,
                identifiers=[
                    ("subscription_id", sub_id),
                    ("resource_group", rg_name),
                    ("vnet_name", vnet_name),
                ],
            )

            vnet_obj.with_property("vnet_name", vnet_name)
            vnet_obj.with_property("resource_id", vnet.get("id", ""))
            vnet_obj.with_property("location", vnet.get("location", ""))
            vnet_obj.with_property("subscription_id", sub_id)
            vnet_obj.with_property("resource_group", rg_name)
            vnet_obj.with_property("provisioning_state",
                                   props.get("provisioningState", ""))

            # Address space
            addr_space = props.get("addressSpace", {})
            prefixes = addr_space.get("addressPrefixes", [])
            vnet_obj.with_property("address_prefixes", ", ".join(prefixes))

            # DHCP options / DNS
            dhcp = props.get("dhcpOptions", {})
            dns = dhcp.get("dnsServers", [])
            vnet_obj.with_property("dns_servers", ", ".join(dns))

            # Enable DDoS protection
            vnet_obj.with_property("ddos_protection_enabled",
                                   str(props.get("enableDdosProtection", "")))

            # Tags
            tags = vnet.get("tags", {})
            if tags:
                for key, value in tags.items():
                    vnet_obj.with_property(f"tag_{key}", value)

            # Relationship: VNet -> Resource Group
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
                    child=vnet_obj,
                )

            # Subnets
            subnets = props.get("subnets", [])
            for subnet in subnets:
                subnet_name = subnet["name"]
                subnet_props = subnet.get("properties", {})

                subnet_obj = result.object(
                    adapter_kind=adapter_kind,
                    object_kind=OBJ_SUBNET,
                    name=subnet_name,
                    identifiers=[
                        ("subscription_id", sub_id),
                        ("vnet_id", vnet.get("id", "")),
                        ("subnet_name", subnet_name),
                    ],
                )

                subnet_obj.with_property("subnet_name", subnet_name)
                subnet_obj.with_property("resource_id", subnet.get("id", ""))
                subnet_obj.with_property("address_prefix",
                                         subnet_props.get("addressPrefix", ""))
                subnet_obj.with_property("provisioning_state",
                                         subnet_props.get("provisioningState", ""))

                # NSG
                nsg = subnet_props.get("networkSecurityGroup", {})
                subnet_obj.with_property("nsg_id", nsg.get("id", ""))

                # Route table
                rt = subnet_props.get("routeTable", {})
                subnet_obj.with_property("route_table_id", rt.get("id", ""))

                # Service endpoints
                svc_eps = subnet_props.get("serviceEndpoints", [])
                svc_names = [ep.get("service", "") for ep in svc_eps]
                subnet_obj.with_property("service_endpoints",
                                         ", ".join(svc_names))

                # Relationship: Subnet -> VNet (parent)
                result.add_relationship(parent=vnet_obj, child=subnet_obj)

                total_subnets += 1

        total_vnets += len(vnets)

    logger.info("Collected %d virtual networks, %d subnets",
                total_vnets, total_subnets)


def _extract_rg(resource_id: str) -> str:
    parts = resource_id.split("/")
    for i, part in enumerate(parts):
        if part.lower() == "resourcegroups" and i + 1 < len(parts):
            return parts[i + 1]
    return ""
