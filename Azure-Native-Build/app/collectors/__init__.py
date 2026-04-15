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
from collectors.functions_apps import collect_functions_apps
from collectors.app_service_plans import collect_app_service_plans
from collectors.cosmos_db import collect_cosmos_db_accounts
from collectors.dedicated_hosts import collect_dedicated_hosts
from collectors.public_ips import collect_public_ips
from collectors.expressroute import collect_expressroute_circuits
from collectors.recovery_vaults import collect_recovery_vaults
from collectors.log_analytics import collect_log_analytics_workspaces
from collectors.postgresql_servers import collect_postgresql_servers
from collectors.mysql_servers import collect_mysql_servers
from collectors.regions import collect_regions_and_world
from collectors.bulk_resources import collect_all_generic_resources

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
    "collect_functions_apps",
    "collect_app_service_plans",
    "collect_cosmos_db_accounts",
    "collect_dedicated_hosts",
    "collect_public_ips",
    "collect_expressroute_circuits",
    "collect_recovery_vaults",
    "collect_log_analytics_workspaces",
    "collect_postgresql_servers",
    "collect_mysql_servers",
    "collect_regions_and_world",
    "collect_all_generic_resources",
]
