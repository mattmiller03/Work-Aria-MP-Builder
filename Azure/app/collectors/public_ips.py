"""Collector for Azure Public IP Addresses."""

import logging

from azure_client import AzureClient
from constants import API_VERSIONS, OBJ_PUBLIC_IP, OBJ_RESOURCE_GROUP
from helpers import make_identifiers, extract_resource_group, safe_property

logger = logging.getLogger(__name__)


def collect_public_ips(client: AzureClient, result, adapter_kind: str,
                       subscriptions: list):
    """Collect public IP addresses across all subscriptions."""
    logger.info("Collecting public IP addresses")
    total = 0

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]
        ips = client.get_all(
            path=f"/subscriptions/{sub_id}/providers/Microsoft.Network/publicIPAddresses",
            api_version=API_VERSIONS["public_ips"],
        )

        for ip in ips:
            ip_name = ip["name"]
            rg_name = extract_resource_group(ip.get("id", ""))
            props = ip.get("properties", {})
            sku = ip.get("sku", {})

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_PUBLIC_IP,
                name=ip_name,
                identifiers=make_identifiers([
                    ("subscription_id", sub_id),
                    ("resource_group", rg_name),
                    ("public_ip_name", ip_name),
                ]),
            )

            safe_property(obj, "public_ip_name", ip_name)
            safe_property(obj, "resource_id", ip.get("id", ""))
            safe_property(obj, "location", ip.get("location", ""))
            safe_property(obj, "subscription_id", sub_id)
            safe_property(obj, "resource_group", rg_name)
            safe_property(obj, "sku_name", sku.get("name", ""))
            safe_property(obj, "sku_tier", sku.get("tier", ""))
            safe_property(obj, "ip_address", props.get("ipAddress", ""))
            safe_property(obj, "public_ip_allocation_method",
                          props.get("publicIPAllocationMethod", ""))
            safe_property(obj, "public_ip_address_version",
                          props.get("publicIPAddressVersion", ""))
            safe_property(obj, "idle_timeout_in_minutes",
                          props.get("idleTimeoutInMinutes", ""))
            safe_property(obj, "provisioning_state",
                          props.get("provisioningState", ""))
            safe_property(obj, "dns_fqdn",
                          props.get("dnsSettings", {}).get("fqdn", ""))
            safe_property(obj, "dns_domain_name_label",
                          props.get("dnsSettings", {}).get("domainNameLabel", ""))

            # Associated resource
            ip_config = props.get("ipConfiguration", {})
            safe_property(obj, "associated_resource_id", ip_config.get("id", ""))

            # Tags
            tags = ip.get("tags", {})
            if tags:
                for key, value in tags.items():
                    safe_property(obj, f"tag_{key}", value)

            # Zones
            zones = ip.get("zones", [])
            if zones:
                safe_property(obj, "availability_zone", ", ".join(zones))

            if rg_name:
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

        total += len(ips)

    logger.info("Collected %d public IP addresses", total)
