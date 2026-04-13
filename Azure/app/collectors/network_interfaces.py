"""Collector for Azure Network Interfaces."""

import logging

from azure_client import AzureClient
from constants import API_VERSIONS, OBJ_NETWORK_INTERFACE, OBJ_RESOURCE_GROUP
from helpers import make_identifiers, extract_resource_group, safe_property
from collectors.metrics import collect_metrics_for_objects

logger = logging.getLogger(__name__)


def collect_network_interfaces(client: AzureClient, result, adapter_kind: str,
                               subscriptions: list):
    """Collect network interfaces across all subscriptions."""
    logger.info("Collecting network interfaces")
    total = 0
    nic_objects = {}  # resource_id -> aria obj

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]
        nics = client.get_all(
            path=f"/subscriptions/{sub_id}/providers/Microsoft.Network/networkInterfaces",
            api_version=API_VERSIONS["network_interfaces"],
        )

        for nic in nics:
            nic_name = nic["name"]
            rg_name = extract_resource_group(nic.get("id", ""))
            props = nic.get("properties", {})

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_NETWORK_INTERFACE,
                name=nic_name,
                identifiers=make_identifiers([
                    ("subscription_id", sub_id),
                    ("resource_group", rg_name),
                    ("nic_name", nic_name),
                ]),
            )

            safe_property(obj, "nic_name", nic_name)
            safe_property(obj, "resource_id", nic.get("id", ""))
            safe_property(obj, "location", nic.get("location", ""))
            safe_property(obj, "subscription_id", sub_id)
            safe_property(obj, "resource_group", rg_name)
            safe_property(obj, "mac_address", props.get("macAddress", ""))
            safe_property(obj, "is_primary", str(props.get("primary", "")))
            safe_property(obj, "enable_ip_forwarding",
                          str(props.get("enableIPForwarding", "")))
            safe_property(obj, "provisioning_state",
                          props.get("provisioningState", ""))

            # NSG
            nsg = props.get("networkSecurityGroup", {})
            safe_property(obj, "nsg_id", nsg.get("id", ""))

            # Associated VM
            vm_ref = props.get("virtualMachine", {})
            safe_property(obj, "attached_vm_id", vm_ref.get("id", ""))

            # IP configurations
            ip_configs = props.get("ipConfigurations", [])
            private_ips = []
            subnet_ids = []
            public_ip_ids = []

            for ip_cfg in ip_configs:
                ip_props = ip_cfg.get("properties", {})
                private_ip = ip_props.get("privateIPAddress", "")
                if private_ip:
                    private_ips.append(private_ip)

                subnet = ip_props.get("subnet", {})
                if subnet.get("id"):
                    subnet_ids.append(subnet["id"])

                public_ip = ip_props.get("publicIPAddress", {})
                if public_ip.get("id"):
                    public_ip_ids.append(public_ip["id"])

                safe_property(obj, "private_ip_allocation_method",
                              ip_props.get("privateIPAllocationMethod", ""))

            safe_property(obj, "private_ip_addresses", ", ".join(private_ips))
            safe_property(obj, "subnet_ids", ", ".join(subnet_ids))
            safe_property(obj, "public_ip_ids", ", ".join(public_ip_ids))
            safe_property(obj, "ip_config_count", len(ip_configs))

            # DNS
            dns = props.get("dnsSettings", {})
            safe_property(obj, "dns_servers",
                          ", ".join(dns.get("dnsServers", [])))
            safe_property(obj, "applied_dns_servers",
                          ", ".join(dns.get("appliedDnsServers", [])))

            # Tags
            tags = nic.get("tags", {})
            if tags:
                for key, value in tags.items():
                    safe_property(obj, f"tag_{key}", value)

            # Relationship: NIC -> Resource Group
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

            resource_id = nic.get("id", "")
            if resource_id:
                nic_objects[resource_id] = obj

        total += len(nics)

    logger.info("Collected %d network interfaces", total)

    if nic_objects:
        collect_metrics_for_objects(client, nic_objects, "network_interfaces")
