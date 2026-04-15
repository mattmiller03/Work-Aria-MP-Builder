"""Collector for Azure Virtual Networks and Subnets."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_VIRTUAL_NETWORK, OBJ_SUBNET, OBJ_RESOURCE_GROUP,
    RES_IDENT_SUB, RES_IDENT_RG, RES_IDENT_REGION, RES_IDENT_ID,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE, AZURE_SERVICE_NAMES,
)
from helpers import make_identifiers, extract_resource_group, safe_property, sanitize_tag_key

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
            resource_id = vnet.get("id", "")
            rg_name = extract_resource_group(resource_id)
            location = vnet.get("location", "")
            props = vnet.get("properties", {})

            vnet_obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_VIRTUAL_NETWORK,
                name=vnet_name,
                identifiers=make_identifiers([
                    (RES_IDENT_SUB, sub_id),
                    (RES_IDENT_RG, rg_name),
                    (RES_IDENT_REGION, location),
                    (RES_IDENT_ID, resource_id),
                ]),
            )

            # SERVICE_DESCRIPTORS
            safe_property(vnet_obj, SD_SUBSCRIPTION, sub_id)
            safe_property(vnet_obj, SD_RESOURCE_GROUP, rg_name)
            safe_property(vnet_obj, SD_REGION, location)
            safe_property(vnet_obj, SD_SERVICE, AZURE_SERVICE_NAMES.get(OBJ_VIRTUAL_NETWORK, ""))

            safe_property(vnet_obj, "vnet_name", vnet_name)
            safe_property(vnet_obj, "resource_id", resource_id)
            safe_property(vnet_obj, "location", location)
            safe_property(vnet_obj, "subscription_id", sub_id)
            safe_property(vnet_obj, "resource_group", rg_name)
            safe_property(vnet_obj, "provisioning_state",
                          props.get("provisioningState", ""))

            # Address space
            addr_space = props.get("addressSpace", {})
            prefixes = addr_space.get("addressPrefixes", [])
            safe_property(vnet_obj, "address_prefixes", ", ".join(prefixes))

            # DHCP options / DNS
            dhcp = props.get("dhcpOptions", {})
            dns = dhcp.get("dnsServers", [])
            safe_property(vnet_obj, "dns_servers", ", ".join(dns))

            # Enable DDoS protection
            safe_property(vnet_obj, "ddos_protection_enabled",
                          str(props.get("enableDdosProtection", "")))

            # Tags
            tags = vnet.get("tags", {})
            if tags:
                for key, value in tags.items():
                    safe_property(vnet_obj, f"summary|tags|{key}", value)

            # Relationship: VNet -> Resource Group
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
                vnet_obj.add_parent(rg_obj)

            # Subnets
            subnets = props.get("subnets", [])
            for subnet in subnets:
                subnet_name = subnet["name"]
                subnet_props = subnet.get("properties", {})

                subnet_obj = result.object(
                    adapter_kind=adapter_kind,
                    object_kind=OBJ_SUBNET,
                    name=subnet_name,
                    identifiers=make_identifiers([
                        ("subscription_id", sub_id),
                        ("vnet_id", vnet.get("id", "")),
                        ("subnet_name", subnet_name),
                    ]),
                )

                safe_property(subnet_obj, "subnet_name", subnet_name)
                safe_property(subnet_obj, "resource_id", subnet.get("id", ""))
                safe_property(subnet_obj, "address_prefix",
                              subnet_props.get("addressPrefix", ""))
                safe_property(subnet_obj, "provisioning_state",
                              subnet_props.get("provisioningState", ""))

                # NSG
                nsg = subnet_props.get("networkSecurityGroup", {})
                safe_property(subnet_obj, "nsg_id", nsg.get("id", ""))

                # Route table
                rt = subnet_props.get("routeTable", {})
                safe_property(subnet_obj, "route_table_id", rt.get("id", ""))

                # Service endpoints
                svc_eps = subnet_props.get("serviceEndpoints", [])
                svc_names = [ep.get("service", "") for ep in svc_eps]
                safe_property(subnet_obj, "service_endpoints",
                              ", ".join(svc_names))

                # Relationship: Subnet -> VNet (parent)
                subnet_obj.add_parent(vnet_obj)

                total_subnets += 1

        total_vnets += len(vnets)

    logger.info("Collected %d virtual networks, %d subnets",
                total_vnets, total_subnets)
