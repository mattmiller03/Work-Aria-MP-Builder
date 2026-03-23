"""Collector for Azure Network Interfaces."""

import logging

from azure_client import AzureClient
from constants import API_VERSIONS, OBJ_NETWORK_INTERFACE, OBJ_RESOURCE_GROUP

logger = logging.getLogger(__name__)


def collect_network_interfaces(client: AzureClient, result, adapter_kind: str,
                               subscriptions: list):
    """Collect network interfaces across all subscriptions."""
    logger.info("Collecting network interfaces")
    total = 0

    for sub in subscriptions:
        sub_id = sub["subscriptionId"]
        nics = client.get_all(
            path=f"/subscriptions/{sub_id}/providers/Microsoft.Network/networkInterfaces",
            api_version=API_VERSIONS["network_interfaces"],
        )

        for nic in nics:
            nic_name = nic["name"]
            rg_name = _extract_rg(nic.get("id", ""))
            props = nic.get("properties", {})

            obj = result.object(
                adapter_kind=adapter_kind,
                object_kind=OBJ_NETWORK_INTERFACE,
                name=nic_name,
                identifiers=[
                    ("subscription_id", sub_id),
                    ("resource_group", rg_name),
                    ("nic_name", nic_name),
                ],
            )

            obj.with_property("nic_name", nic_name)
            obj.with_property("resource_id", nic.get("id", ""))
            obj.with_property("location", nic.get("location", ""))
            obj.with_property("subscription_id", sub_id)
            obj.with_property("resource_group", rg_name)
            obj.with_property("mac_address", props.get("macAddress", ""))
            obj.with_property("is_primary", str(props.get("primary", "")))
            obj.with_property("enable_ip_forwarding",
                              str(props.get("enableIPForwarding", "")))
            obj.with_property("provisioning_state",
                              props.get("provisioningState", ""))

            # NSG
            nsg = props.get("networkSecurityGroup", {})
            obj.with_property("nsg_id", nsg.get("id", ""))

            # Associated VM
            vm_ref = props.get("virtualMachine", {})
            obj.with_property("attached_vm_id", vm_ref.get("id", ""))

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

                obj.with_property("private_ip_allocation_method",
                                  ip_props.get("privateIPAllocationMethod", ""))

            obj.with_property("private_ip_addresses", ", ".join(private_ips))
            obj.with_property("subnet_ids", ", ".join(subnet_ids))
            obj.with_property("public_ip_ids", ", ".join(public_ip_ids))
            obj.with_property("ip_config_count", len(ip_configs))

            # DNS
            dns = props.get("dnsSettings", {})
            obj.with_property("dns_servers",
                              ", ".join(dns.get("dnsServers", [])))
            obj.with_property("applied_dns_servers",
                              ", ".join(dns.get("appliedDnsServers", [])))

            # Tags
            tags = nic.get("tags", {})
            if tags:
                for key, value in tags.items():
                    obj.with_property(f"tag_{key}", value)

            # Relationship: NIC -> Resource Group
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

        total += len(nics)

    logger.info("Collected %d network interfaces", total)


def _extract_rg(resource_id: str) -> str:
    parts = resource_id.split("/")
    for i, part in enumerate(parts):
        if part.lower() == "resourcegroups" and i + 1 < len(parts):
            return parts[i + 1]
    return ""
