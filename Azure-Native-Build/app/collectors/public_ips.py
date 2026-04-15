"""Collector for Azure Public IP Addresses."""

import logging

from azure_client import AzureClient
from constants import (
    API_VERSIONS, OBJ_PUBLIC_IP, OBJ_RESOURCE_GROUP,
    RES_IDENT_SUB, RES_IDENT_RG, RES_IDENT_REGION, RES_IDENT_ID,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE, AZURE_SERVICE_NAMES,
)
from helpers import make_identifiers, extract_resource_group, safe_property, sanitize_tag_key

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
            resource_id = ip.get("id", "")
            rg_name = extract_resource_group(resource_id)
            location = ip.get("location", "")
            props = ip.get("properties", {})
            sku = ip.get("sku", {})

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_PUBLIC_IP,
                name=ip_name,
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
            safe_property(obj, SD_SERVICE, AZURE_SERVICE_NAMES.get(OBJ_PUBLIC_IP, ""))

            safe_property(obj, "public_ip_name", ip_name)
            safe_property(obj, "resource_id", resource_id)
            safe_property(obj, "location", location)
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
                    safe_property(obj, f"summary|tags|{key}", value)

            # Zones
            zones = ip.get("zones", [])
            if zones:
                safe_property(obj, "availability_zone", ", ".join(zones))

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

        total += len(ips)

    logger.info("Collected %d public IP addresses", total)
