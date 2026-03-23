"""Azure resource collectors for Aria Operations management pack."""

from collectors.subscriptions import collect_subscriptions
from collectors.resource_groups import collect_resource_groups
from collectors.virtual_machines import collect_virtual_machines
from collectors.disks import collect_disks
from collectors.network_interfaces import collect_network_interfaces
from collectors.virtual_networks import collect_virtual_networks
from collectors.storage_accounts import collect_storage_accounts
from collectors.load_balancers import collect_load_balancers
from collectors.key_vaults import collect_key_vaults
from collectors.sql_databases import collect_sql_servers_and_databases
from collectors.app_services import collect_app_services

__all__ = [
    "collect_subscriptions",
    "collect_resource_groups",
    "collect_virtual_machines",
    "collect_disks",
    "collect_network_interfaces",
    "collect_virtual_networks",
    "collect_storage_accounts",
    "collect_load_balancers",
    "collect_key_vaults",
    "collect_sql_servers_and_databases",
    "collect_app_services",
]
