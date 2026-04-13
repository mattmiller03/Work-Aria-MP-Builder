"""Main adapter for Azure Government Cloud Management Pack.

Implements the three entry points required by the Aria Operations Integration SDK:
- get_adapter_definition() — defines the object model
- collect() — collects data from Azure Gov
- test() — validates connectivity
"""

import logging
import sys

from constants import (
    ADAPTER_KIND, ADAPTER_NAME,
    CREDENTIAL_TYPE, CREDENTIAL_TENANT_ID, CREDENTIAL_CLIENT_ID,
    CREDENTIAL_CLIENT_SECRET, CREDENTIAL_SUBSCRIPTION_ID,
    CONFIG_CLOUD_ENVIRONMENT, CLOUD_ENV_GOV, API_VERSIONS,
    OBJ_SUBSCRIPTION, OBJ_RESOURCE_GROUP, OBJ_VIRTUAL_MACHINE,
    OBJ_DISK, OBJ_NETWORK_INTERFACE, OBJ_VIRTUAL_NETWORK, OBJ_SUBNET,
    OBJ_STORAGE_ACCOUNT, OBJ_LOAD_BALANCER, OBJ_KEY_VAULT,
    OBJ_SQL_SERVER, OBJ_SQL_DATABASE, OBJ_APP_SERVICE,
    OBJ_HOST_GROUP, OBJ_DEDICATED_HOST,
    OBJ_PUBLIC_IP, OBJ_EXPRESSROUTE, OBJ_RECOVERY_VAULT, OBJ_LOG_ANALYTICS,
)
from auth import AzureAuthenticator
from azure_client import AzureClient
from collectors import (
    collect_subscriptions,
    collect_resource_groups,
    collect_virtual_machines,
    collect_disks,
    collect_network_interfaces,
    collect_virtual_networks,
    collect_storage_accounts,
    collect_load_balancers,
    collect_key_vaults,
    collect_sql_servers_and_databases,
    collect_app_services,
    collect_dedicated_hosts,
    collect_public_ips,
    collect_expressroute_circuits,
    collect_recovery_vaults,
    collect_log_analytics_workspaces,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)


# ---------------------------------------------------------------------------
# Adapter Definition
# ---------------------------------------------------------------------------

def get_adapter_definition():
    """Define the adapter's object model, credentials, and configuration.

    The SDK uses this to auto-generate describe.xml at build time.
    """
    from aria.ops.definition.adapter_definition import AdapterDefinition
    from aria.ops.definition.units import Unit

    # Unit constants — the SDK's @skip-decorated enum classes (Ratio, DataSize,
    # etc.) become NonMember objects under aenum 3.1.11, breaking attribute
    # access.  The SDK also expects enum-style access (unit.value.key), so we
    # wrap each Unit in a simple object whose .value returns the Unit itself.
    class _UnitWrapper:
        def __init__(self, unit):
            self.value = unit

    PERCENT = _UnitWrapper(Unit("percent", "%", 1, 1))
    BYTE = _UnitWrapper(Unit("byte", "B", 1, 1, "bytes_base_10"))
    MILLISECONDS = _UnitWrapper(Unit("milliseconds", "ms", 4, 1000))
    PACKETS = _UnitWrapper(Unit("packets", "packets", 1, 1, "Packets"))
    OPERATIONS_PER_SECOND = _UnitWrapper(Unit("operations_per_sec", "ops/s", 1, 1, is_rate=True))

    definition = AdapterDefinition(ADAPTER_KIND, ADAPTER_NAME)

    # -- Configuration parameter: cloud environment --
    definition.define_enum_parameter(
        CONFIG_CLOUD_ENVIRONMENT,
        values=[CLOUD_ENV_GOV, "commercial"],
        label="Cloud Environment",
        default=CLOUD_ENV_GOV,
        description="Azure cloud environment (government or commercial)",
    )

    # -- Credential type --
    credential = definition.define_credential_type(CREDENTIAL_TYPE,
                                                   "Azure Credentials")
    credential.define_string_parameter(CREDENTIAL_TENANT_ID,
                                       "Tenant ID (Directory ID)")
    credential.define_string_parameter(CREDENTIAL_CLIENT_ID,
                                       "Client ID (Application ID)")
    credential.define_password_parameter(CREDENTIAL_CLIENT_SECRET,
                                         "Client Secret")
    credential.define_string_parameter(CREDENTIAL_SUBSCRIPTION_ID,
                                       "Subscription ID (leave blank for all)",
                                       required=False)

    # -- Object Types --

    # Subscription
    sub = definition.define_object_type(OBJ_SUBSCRIPTION, "Azure Subscription")
    sub.define_string_identifier("subscription_id", "Subscription ID")
    sub.define_string_property("display_name", "Display Name")
    sub.define_string_property("state", "State")
    sub.define_string_property("tenant_id", "Tenant ID")
    sub.define_string_property("location_placement_id", "Location Placement ID")
    sub.define_string_property("quota_id", "Quota ID")
    sub.define_string_property("spending_limit", "Spending Limit")

    # Resource Group
    rg = definition.define_object_type(OBJ_RESOURCE_GROUP,
                                       "Azure Resource Group")
    rg.define_string_property("name", "Name")
    rg.define_string_identifier("subscription_id", "Subscription ID")
    rg.define_string_identifier("resource_group_name", "Resource Group Name")
    rg.define_string_property("location", "Location")
    rg.define_string_property("provisioning_state", "Provisioning State")
    rg.define_string_property("resource_id", "Resource ID")

    # Virtual Machine
    vm = definition.define_object_type(OBJ_VIRTUAL_MACHINE,
                                       "Azure Virtual Machine")
    vm.define_string_identifier("subscription_id", "Subscription ID")
    vm.define_string_identifier("resource_group", "Resource Group")
    vm.define_string_identifier("vm_name", "VM Name")
    vm.define_string_property("resource_id", "Resource ID")
    vm.define_string_property("location", "Location")
    vm.define_string_property("vm_id", "VM ID")
    vm.define_string_property("vm_size", "VM Size")
    vm.define_string_property("provisioning_state", "Provisioning State")
    vm.define_string_property("power_state", "Power State")
    vm.define_string_property("computer_name", "Computer Name")
    vm.define_string_property("admin_username", "Admin Username")
    vm.define_string_property("os_type", "OS Type")
    vm.define_string_property("image_publisher", "Image Publisher")
    vm.define_string_property("image_offer", "Image Offer")
    vm.define_string_property("image_sku", "Image SKU")
    vm.define_string_property("image_version", "Image Version")
    vm.define_string_property("os_disk_name", "OS Disk Name")
    vm.define_string_property("os_disk_size_gb", "OS Disk Size (GB)")
    vm.define_string_property("os_disk_caching", "OS Disk Caching")
    vm.define_string_property("os_disk_storage_type", "OS Disk Storage Type")
    vm.define_numeric_property("data_disk_count", "Data Disk Count")
    vm.define_string_property("network_interface_ids", "Network Interface IDs")
    vm.define_numeric_property("nic_count", "NIC Count")
    vm.define_string_property("secure_boot_enabled", "Secure Boot Enabled")
    vm.define_string_property("vtpm_enabled", "vTPM Enabled")
    vm.define_string_property("boot_diagnostics_enabled",
                              "Boot Diagnostics Enabled")
    vm.define_string_property("availability_zone", "Availability Zone")
    vm.define_string_property("dedicated_host_id", "Dedicated Host ID")
    vm.define_string_property("dedicated_host_name", "Dedicated Host Name")
    vm.define_string_property("dedicated_host_group", "Dedicated Host Group")
    # VM Metrics (Azure Monitor)
    vm.define_metric("CPU|cpu_usage", "CPU Usage",
                     unit=PERCENT, is_key_attribute=True)
    vm.define_metric("Disk|disk_read_bytes", "Disk Read Bytes",
                     unit=BYTE)
    vm.define_metric("Disk|disk_write_bytes", "Disk Write Bytes",
                     unit=BYTE)
    vm.define_metric("Disk|disk_read_operations", "Disk Read Operations",
                     unit=OPERATIONS_PER_SECOND, is_rate=True)
    vm.define_metric("Disk|disk_write_operations", "Disk Write Operations",
                     unit=OPERATIONS_PER_SECOND, is_rate=True)
    vm.define_metric("Network|network_in", "Network In",
                     unit=BYTE)
    vm.define_metric("Network|network_out", "Network Out",
                     unit=BYTE)
    vm.define_metric("CPU|capacity", "CPU Capacity Reference",
                     unit=PERCENT)

    # Disk
    disk = definition.define_object_type(OBJ_DISK, "Azure Disk")
    disk.define_string_identifier("subscription_id", "Subscription ID")
    disk.define_string_identifier("resource_group", "Resource Group")
    disk.define_string_identifier("disk_name", "Disk Name")
    disk.define_string_property("resource_id", "Resource ID")
    disk.define_string_property("location", "Location")
    disk.define_string_property("sku_name", "SKU Name")
    disk.define_string_property("sku_tier", "SKU Tier")
    disk.define_string_property("disk_size_gb", "Disk Size (GB)")
    disk.define_string_property("disk_iops_read_write", "Disk IOPS Read/Write")
    disk.define_string_property("disk_mbps_read_write",
                                "Disk MBps Read/Write")
    disk.define_string_property("disk_state", "Disk State")
    disk.define_string_property("os_type", "OS Type")
    disk.define_string_property("time_created", "Time Created")
    disk.define_string_property("provisioning_state", "Provisioning State")
    disk.define_string_property("encryption_type", "Encryption Type")
    disk.define_string_property("network_access_policy",
                                "Network Access Policy")
    disk.define_string_property("availability_zone", "Availability Zone")
    disk.define_string_property("attached_vm_id", "Attached VM ID")
    disk.define_string_property("attached_vm_name", "Attached VM Name")

    # Network Interface
    nic = definition.define_object_type(OBJ_NETWORK_INTERFACE,
                                        "Azure Network Interface")
    nic.define_string_identifier("subscription_id", "Subscription ID")
    nic.define_string_identifier("resource_group", "Resource Group")
    nic.define_string_identifier("nic_name", "NIC Name")
    nic.define_string_property("resource_id", "Resource ID")
    nic.define_string_property("location", "Location")
    nic.define_string_property("mac_address", "MAC Address")
    nic.define_string_property("is_primary", "Is Primary")
    nic.define_string_property("enable_ip_forwarding", "IP Forwarding Enabled")
    nic.define_string_property("provisioning_state", "Provisioning State")
    nic.define_string_property("nsg_id", "NSG ID")
    nic.define_string_property("attached_vm_id", "Attached VM ID")
    nic.define_string_property("private_ip_addresses", "Private IP Addresses")
    nic.define_string_property("private_ip_allocation_method",
                               "IP Allocation Method")
    nic.define_string_property("subnet_ids", "Subnet IDs")
    nic.define_string_property("public_ip_ids", "Public IP IDs")
    nic.define_numeric_property("ip_config_count", "IP Config Count")
    nic.define_string_property("dns_servers", "DNS Servers")
    nic.define_string_property("applied_dns_servers", "Applied DNS Servers")
    # NIC Metrics (Azure Monitor)
    nic.define_metric("Network|bytes_sent", "Bytes Sent",
                      unit=BYTE)
    nic.define_metric("Network|bytes_received", "Bytes Received",
                      unit=BYTE)
    nic.define_metric("Network|packets_sent", "Packets Sent",
                      unit=PACKETS)
    nic.define_metric("Network|packets_received", "Packets Received",
                      unit=PACKETS)

    # Virtual Network
    vnet = definition.define_object_type(OBJ_VIRTUAL_NETWORK,
                                         "Azure Virtual Network")
    vnet.define_string_identifier("subscription_id", "Subscription ID")
    vnet.define_string_identifier("resource_group", "Resource Group")
    vnet.define_string_identifier("vnet_name", "VNet Name")
    vnet.define_string_property("resource_id", "Resource ID")
    vnet.define_string_property("location", "Location")
    vnet.define_string_property("provisioning_state", "Provisioning State")
    vnet.define_string_property("address_prefixes", "Address Prefixes")
    vnet.define_string_property("dns_servers", "DNS Servers")
    vnet.define_string_property("ddos_protection_enabled",
                                "DDoS Protection Enabled")

    # Subnet
    subnet = definition.define_object_type(OBJ_SUBNET, "Azure Subnet")
    subnet.define_string_identifier("subscription_id", "Subscription ID")
    subnet.define_string_identifier("vnet_id", "VNet ID")
    subnet.define_string_identifier("subnet_name", "Subnet Name")
    subnet.define_string_property("resource_id", "Resource ID")
    subnet.define_string_property("address_prefix", "Address Prefix")
    subnet.define_string_property("provisioning_state", "Provisioning State")
    subnet.define_string_property("nsg_id", "NSG ID")
    subnet.define_string_property("route_table_id", "Route Table ID")
    subnet.define_string_property("service_endpoints", "Service Endpoints")

    # Storage Account
    sa = definition.define_object_type(OBJ_STORAGE_ACCOUNT,
                                       "Azure Storage Account")
    sa.define_string_identifier("subscription_id", "Subscription ID")
    sa.define_string_identifier("resource_group", "Resource Group")
    sa.define_string_identifier("account_name", "Account Name")
    sa.define_string_property("resource_id", "Resource ID")
    sa.define_string_property("location", "Location")
    sa.define_string_property("kind", "Kind")
    sa.define_string_property("sku_name", "SKU Name")
    sa.define_string_property("sku_tier", "SKU Tier")
    sa.define_string_property("provisioning_state", "Provisioning State")
    sa.define_string_property("creation_time", "Creation Time")
    sa.define_string_property("access_tier", "Access Tier")
    sa.define_string_property("https_only", "HTTPS Only")
    sa.define_string_property("minimum_tls_version", "Minimum TLS Version")
    sa.define_string_property("allow_blob_public_access",
                              "Allow Blob Public Access")
    sa.define_string_property("endpoint_blob", "Blob Endpoint")
    sa.define_string_property("endpoint_queue", "Queue Endpoint")
    sa.define_string_property("endpoint_table", "Table Endpoint")
    sa.define_string_property("endpoint_file", "File Endpoint")
    sa.define_string_property("encryption_key_source", "Encryption Key Source")
    sa.define_string_property("network_default_action",
                              "Network Default Action")
    # Storage Account Metrics (Azure Monitor)
    sa.define_metric("Storage|used_capacity", "Used Capacity",
                     unit=BYTE)
    sa.define_metric("Storage|transactions", "Transactions")
    sa.define_metric("Network|ingress", "Ingress",
                     unit=BYTE)
    sa.define_metric("Network|egress", "Egress",
                     unit=BYTE)
    sa.define_metric("Availability|availability", "Availability",
                     unit=PERCENT)
    sa.define_metric("Latency|e2e_latency", "E2E Latency",
                     unit=MILLISECONDS)
    sa.define_metric("Latency|server_latency", "Server Latency",
                     unit=MILLISECONDS)

    # Load Balancer
    lb = definition.define_object_type(OBJ_LOAD_BALANCER,
                                       "Azure Load Balancer")
    lb.define_string_identifier("subscription_id", "Subscription ID")
    lb.define_string_identifier("resource_group", "Resource Group")
    lb.define_string_identifier("lb_name", "Load Balancer Name")
    lb.define_string_property("resource_id", "Resource ID")
    lb.define_string_property("location", "Location")
    lb.define_string_property("sku_name", "SKU Name")
    lb.define_string_property("sku_tier", "SKU Tier")
    lb.define_string_property("provisioning_state", "Provisioning State")
    lb.define_numeric_property("frontend_ip_count", "Frontend IP Count")
    lb.define_string_property("frontend_names", "Frontend Names")
    lb.define_numeric_property("backend_pool_count", "Backend Pool Count")
    lb.define_string_property("backend_pool_names", "Backend Pool Names")
    lb.define_numeric_property("rule_count", "Rule Count")
    lb.define_numeric_property("probe_count", "Probe Count")
    lb.define_numeric_property("inbound_nat_rule_count",
                               "Inbound NAT Rule Count")
    # Load Balancer Metrics (Azure Monitor)
    lb.define_metric("Availability|data_path_availability",
                     "Data Path Availability", unit=PERCENT)
    lb.define_metric("Availability|health_probe_status",
                     "Health Probe Status", unit=PERCENT)
    lb.define_metric("Network|byte_count", "Byte Count",
                     unit=BYTE)
    lb.define_metric("Network|packet_count", "Packet Count",
                     unit=PACKETS)

    # Key Vault
    kv = definition.define_object_type(OBJ_KEY_VAULT, "Azure Key Vault")
    kv.define_string_identifier("subscription_id", "Subscription ID")
    kv.define_string_identifier("resource_group", "Resource Group")
    kv.define_string_identifier("vault_name", "Vault Name")
    kv.define_string_property("resource_id", "Resource ID")
    kv.define_string_property("location", "Location")
    kv.define_string_property("vault_uri", "Vault URI")
    kv.define_string_property("tenant_id", "Tenant ID")
    kv.define_string_property("sku_family", "SKU Family")
    kv.define_string_property("sku_name", "SKU Name")
    kv.define_string_property("soft_delete_enabled", "Soft Delete Enabled")
    kv.define_string_property("purge_protection_enabled",
                              "Purge Protection Enabled")
    kv.define_string_property("rbac_authorization_enabled",
                              "RBAC Authorization Enabled")
    kv.define_string_property("soft_delete_retention_days",
                              "Soft Delete Retention Days")
    kv.define_string_property("network_default_action",
                              "Network Default Action")

    # SQL Server
    sql_srv = definition.define_object_type(OBJ_SQL_SERVER,
                                            "Azure SQL Server")
    sql_srv.define_string_identifier("subscription_id", "Subscription ID")
    sql_srv.define_string_identifier("resource_group", "Resource Group")
    sql_srv.define_string_identifier("server_name", "Server Name")
    sql_srv.define_string_property("resource_id", "Resource ID")
    sql_srv.define_string_property("location", "Location")
    sql_srv.define_string_property("fqdn", "Fully Qualified Domain Name")
    sql_srv.define_string_property("state", "State")
    sql_srv.define_string_property("version", "Version")
    sql_srv.define_string_property("admin_login", "Admin Login")
    sql_srv.define_string_property("public_network_access",
                                   "Public Network Access")
    sql_srv.define_string_property("minimal_tls_version",
                                   "Minimal TLS Version")
    # SQL Server Metrics (Azure Monitor — aggregated from child databases)
    sql_srv.define_metric("CPU|cpu_usage", "Avg CPU Usage",
                          unit=PERCENT)
    sql_srv.define_metric("Storage|data_io", "Avg Data I/O",
                          unit=PERCENT)
    sql_srv.define_metric("Storage|xtp_storage", "XTP Storage",
                          unit=PERCENT)
    sql_srv.define_metric("Workload|dtu_used", "DTU Used")
    sql_srv.define_metric("Workload|workers", "Workers",
                          unit=PERCENT)
    sql_srv.define_metric("Workload|sessions", "Sessions",
                          unit=PERCENT)

    # SQL Database
    sql_db = definition.define_object_type(OBJ_SQL_DATABASE,
                                           "Azure SQL Database")
    sql_db.define_string_identifier("subscription_id", "Subscription ID")
    sql_db.define_string_identifier("server_name", "Server Name")
    sql_db.define_string_identifier("database_name", "Database Name")
    sql_db.define_string_property("resource_id", "Resource ID")
    sql_db.define_string_property("location", "Location")
    sql_db.define_string_property("status", "Status")
    sql_db.define_string_property("database_id", "Database ID")
    sql_db.define_string_property("sku_name", "SKU Name")
    sql_db.define_string_property("sku_tier", "SKU Tier")
    sql_db.define_string_property("sku_capacity", "SKU Capacity")
    sql_db.define_string_property("max_size_bytes", "Max Size (Bytes)")
    sql_db.define_string_property("collation", "Collation")
    sql_db.define_string_property("creation_date", "Creation Date")
    sql_db.define_string_property("current_service_objective",
                                  "Current Service Objective")
    sql_db.define_string_property("zone_redundant", "Zone Redundant")
    # SQL Database Metrics (Azure Monitor)
    sql_db.define_metric("CPU|cpu_usage", "CPU Usage",
                         unit=PERCENT, is_key_attribute=True)
    sql_db.define_metric("Workload|dtu_consumption", "DTU Consumption",
                         unit=PERCENT)
    sql_db.define_metric("Workload|dtu_limit", "DTU Limit")
    sql_db.define_metric("Workload|dtu_used", "DTU Used")
    sql_db.define_metric("Storage|data_io", "Data I/O",
                         unit=PERCENT)
    sql_db.define_metric("Storage|log_io", "Log I/O",
                         unit=PERCENT)
    sql_db.define_metric("Storage|storage_usage", "Storage Usage",
                         unit=PERCENT)
    sql_db.define_metric("Storage|database_size", "Database Size",
                         unit=BYTE)
    sql_db.define_metric("Storage|xtp_storage", "XTP Storage",
                         unit=PERCENT)
    sql_db.define_metric("Network|successful_connections",
                         "Successful Connections")
    sql_db.define_metric("Network|failed_connections",
                         "Failed Connections")
    sql_db.define_metric("Network|blocked_by_firewall",
                         "Blocked by Firewall")
    sql_db.define_metric("Network|deadlocks", "Deadlocks")
    sql_db.define_metric("Workload|workers", "Workers",
                         unit=PERCENT)
    sql_db.define_metric("Workload|sessions", "Sessions",
                         unit=PERCENT)

    # App Service
    app = definition.define_object_type(OBJ_APP_SERVICE,
                                        "Azure App Service")
    app.define_string_identifier("subscription_id", "Subscription ID")
    app.define_string_identifier("resource_group", "Resource Group")
    app.define_string_identifier("app_name", "App Name")
    app.define_string_property("resource_id", "Resource ID")
    app.define_string_property("location", "Location")
    app.define_string_property("kind", "Kind")
    app.define_string_property("is_function_app", "Is Function App")
    app.define_string_property("state", "State")
    app.define_string_property("default_host_name", "Default Host Name")
    app.define_string_property("https_only", "HTTPS Only")
    app.define_string_property("enabled", "Enabled")
    app.define_string_property("host_names", "Host Names")
    app.define_string_property("server_farm_id", "App Service Plan ID")
    app.define_string_property("availability_state", "Availability State")
    app.define_string_property("last_modified_time", "Last Modified Time")
    app.define_string_property("outbound_ip_addresses",
                               "Outbound IP Addresses")

    # Host Group
    hg = definition.define_object_type(OBJ_HOST_GROUP,
                                       "Azure Dedicated Host Group")
    hg.define_string_identifier("subscription_id", "Subscription ID")
    hg.define_string_identifier("resource_group", "Resource Group")
    hg.define_string_identifier("host_group_name", "Host Group Name")
    hg.define_string_property("resource_id", "Resource ID")
    hg.define_string_property("location", "Location")
    hg.define_string_property("platform_fault_domain_count",
                              "Platform Fault Domain Count")
    hg.define_string_property("support_automatic_placement",
                              "Support Automatic Placement")
    hg.define_string_property("provisioning_state", "Provisioning State")

    # Dedicated Host
    dh = definition.define_object_type(OBJ_DEDICATED_HOST,
                                       "Azure Dedicated Host")
    dh.define_string_identifier("subscription_id", "Subscription ID")
    dh.define_string_identifier("host_group_name", "Host Group Name")
    dh.define_string_identifier("host_name", "Host Name")
    dh.define_string_property("resource_id", "Resource ID")
    dh.define_string_property("location", "Location")
    dh.define_string_property("resource_group", "Resource Group")
    dh.define_string_property("sku_name", "SKU Name")
    dh.define_string_property("platform_fault_domain", "Platform Fault Domain")
    dh.define_string_property("auto_replace_on_failure",
                              "Auto Replace on Failure")
    dh.define_string_property("host_id", "Host ID")
    dh.define_string_property("provisioning_state", "Provisioning State")
    dh.define_string_property("provisioning_time", "Provisioning Time")
    dh.define_numeric_property("vm_count", "VM Count")
    dh.define_string_property("vm_ids", "VM Resource IDs")
    dh.define_string_property("vm_names", "VM Names")
    dh.define_string_property("health_state", "Health State")
    dh.define_numeric_property("max_available_slots", "Max Available VM Slots")
    dh.define_string_property("smallest_vm_size", "Smallest VM Size")
    dh.define_numeric_property("smallest_vm_available",
                               "Smallest VM Size Available Count")
    dh.define_string_property("allocatable_vm_summary",
                              "Allocatable VM Capacity Summary")
    dh.define_string_property("vm_size_summary", "VM Size Breakdown")
    dh.define_numeric_property("vm_size_distinct_count",
                               "Distinct VM Size Count")
    dh.define_string_property("vm_disk_skus", "Disk SKUs In Use")
    dh.define_numeric_property("hourly_rate", "Hourly Compute Rate (USD)")
    dh.define_numeric_property("monthly_rate_estimate",
                               "Monthly Rate Estimate (USD)")

    # Public IP Address
    pip = definition.define_object_type(OBJ_PUBLIC_IP,
                                        "Azure Public IP Address")
    pip.define_string_identifier("subscription_id", "Subscription ID")
    pip.define_string_identifier("resource_group", "Resource Group")
    pip.define_string_identifier("public_ip_name", "Public IP Name")
    pip.define_string_property("resource_id", "Resource ID")
    pip.define_string_property("location", "Location")
    pip.define_string_property("sku_name", "SKU Name")
    pip.define_string_property("sku_tier", "SKU Tier")
    pip.define_string_property("ip_address", "IP Address")
    pip.define_string_property("public_ip_allocation_method", "Allocation Method")
    pip.define_string_property("public_ip_address_version", "IP Version")
    pip.define_string_property("idle_timeout_in_minutes", "Idle Timeout (min)")
    pip.define_string_property("provisioning_state", "Provisioning State")
    pip.define_string_property("dns_fqdn", "DNS FQDN")
    pip.define_string_property("dns_domain_name_label", "DNS Domain Label")
    pip.define_string_property("associated_resource_id", "Associated Resource ID")
    pip.define_string_property("availability_zone", "Availability Zone")

    # ExpressRoute Circuit
    er = definition.define_object_type(OBJ_EXPRESSROUTE,
                                       "Azure ExpressRoute Circuit")
    er.define_string_identifier("subscription_id", "Subscription ID")
    er.define_string_identifier("resource_group", "Resource Group")
    er.define_string_identifier("circuit_name", "Circuit Name")
    er.define_string_property("resource_id", "Resource ID")
    er.define_string_property("location", "Location")
    er.define_string_property("sku_name", "SKU Name")
    er.define_string_property("sku_tier", "SKU Tier")
    er.define_string_property("sku_family", "SKU Family")
    er.define_string_property("circuit_provisioning_state", "Circuit Provisioning State")
    er.define_string_property("service_provider_provisioning_state", "Provider State")
    er.define_string_property("bandwidth_in_mbps", "Bandwidth (Mbps)")
    er.define_string_property("peering_location", "Peering Location")
    er.define_string_property("service_provider_name", "Service Provider")
    er.define_string_property("provisioning_state", "Provisioning State")
    er.define_string_property("allow_classic_operations", "Allow Classic Operations")
    er.define_string_property("global_reach_enabled", "Global Reach Enabled")
    er.define_numeric_property("peering_count", "Peering Count")
    er.define_string_property("peering_names", "Peering Names")

    # Recovery Services Vault
    rv = definition.define_object_type(OBJ_RECOVERY_VAULT,
                                       "Azure Recovery Services Vault")
    rv.define_string_identifier("subscription_id", "Subscription ID")
    rv.define_string_identifier("resource_group", "Resource Group")
    rv.define_string_identifier("vault_name", "Vault Name")
    rv.define_string_property("resource_id", "Resource ID")
    rv.define_string_property("location", "Location")
    rv.define_string_property("sku_name", "SKU Name")
    rv.define_string_property("sku_tier", "SKU Tier")
    rv.define_string_property("provisioning_state", "Provisioning State")
    rv.define_string_property("private_endpoint_state_for_backup", "Private Endpoint Backup")
    rv.define_string_property("private_endpoint_state_for_site_recovery", "Private Endpoint Site Recovery")
    rv.define_string_property("storage_type", "Storage Redundancy Type")
    rv.define_string_property("cross_region_restore", "Cross Region Restore")
    rv.define_string_property("immutability_state", "Immutability State")
    rv.define_string_property("soft_delete_state", "Soft Delete State")

    # Log Analytics Workspace
    la = definition.define_object_type(OBJ_LOG_ANALYTICS,
                                       "Azure Log Analytics Workspace")
    la.define_string_identifier("subscription_id", "Subscription ID")
    la.define_string_identifier("resource_group", "Resource Group")
    la.define_string_identifier("workspace_name", "Workspace Name")
    la.define_string_property("resource_id", "Resource ID")
    la.define_string_property("location", "Location")
    la.define_string_property("workspace_id", "Workspace ID")
    la.define_string_property("provisioning_state", "Provisioning State")
    la.define_string_property("sku_name", "SKU Name")
    la.define_string_property("retention_in_days", "Retention (Days)")
    la.define_string_property("daily_quota_gb", "Daily Quota (GB)")
    la.define_string_property("created_date", "Created Date")
    la.define_string_property("modified_date", "Modified Date")
    la.define_string_property("public_network_access_for_ingestion", "Public Ingestion Access")
    la.define_string_property("public_network_access_for_query", "Public Query Access")

    return definition


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

def collect(adapter_instance):
    """Collect resources from Azure Government Cloud.

    Called by Aria Operations on each collection cycle.
    """
    from aria.ops.result import CollectResult

    result = CollectResult()

    try:
        # Extract credentials and config
        tenant_id = adapter_instance.get_credential_value(CREDENTIAL_TENANT_ID)
        client_id = adapter_instance.get_credential_value(CREDENTIAL_CLIENT_ID)
        client_secret = adapter_instance.get_credential_value(CREDENTIAL_CLIENT_SECRET)
        target_sub = adapter_instance.get_credential_value(CREDENTIAL_SUBSCRIPTION_ID)

        cloud_env = adapter_instance.get_identifier_value(
            CONFIG_CLOUD_ENVIRONMENT, CLOUD_ENV_GOV
        )

        # Authenticate
        auth = AzureAuthenticator(tenant_id, client_id, client_secret,
                                  cloud_env)
        client = AzureClient(auth, cloud_env)

        # 1. Subscriptions
        subscriptions = collect_subscriptions(client, result, ADAPTER_KIND)

        # Filter to specific subscription if configured
        if target_sub:
            subscriptions = [
                s for s in subscriptions
                if s["subscriptionId"] == target_sub
            ]
            if not subscriptions:
                logger.warning("Configured subscription %s not found",
                               target_sub)

        # 2. Resource Groups
        rgs_by_sub = collect_resource_groups(client, result, ADAPTER_KIND,
                                             subscriptions)

        # 3. Collect VMs first and build lookup for dedicated host enrichment
        vm_lookup = {}  # VM resource ID (lowered) -> VM API dict
        try:
            for sub in subscriptions:
                sub_id = sub["subscriptionId"]
                try:
                    vms_raw = client.get_all(
                        path=f"/subscriptions/{sub_id}/providers/Microsoft.Compute/virtualMachines",
                        api_version=API_VERSIONS["virtual_machines"],
                        params={"$expand": "instanceView"},
                    )
                except Exception:
                    vms_raw = client.get_all(
                        path=f"/subscriptions/{sub_id}/providers/Microsoft.Compute/virtualMachines",
                        api_version=API_VERSIONS["virtual_machines"],
                    )
                for vm_raw in vms_raw:
                    vm_id = vm_raw.get("id", "")
                    if vm_id:
                        vm_lookup[vm_id.lower()] = vm_raw
            logger.info("Built VM lookup with %d entries", len(vm_lookup))
        except Exception as e:
            logger.warning("Failed to build VM lookup: %s", e)

        # 4. All resource collectors — each wrapped independently
        #    so one failure doesn't prevent other resource types from collecting
        collectors = [
            ("Virtual Machines", lambda: collect_virtual_machines(client, result, ADAPTER_KIND, subscriptions, vm_lookup)),
            ("Disks", lambda: collect_disks(client, result, ADAPTER_KIND, subscriptions)),
            ("Network Interfaces", lambda: collect_network_interfaces(client, result, ADAPTER_KIND, subscriptions)),
            ("Virtual Networks", lambda: collect_virtual_networks(client, result, ADAPTER_KIND, subscriptions)),
            ("Storage Accounts", lambda: collect_storage_accounts(client, result, ADAPTER_KIND, subscriptions)),
            ("Load Balancers", lambda: collect_load_balancers(client, result, ADAPTER_KIND, subscriptions)),
            ("Key Vaults", lambda: collect_key_vaults(client, result, ADAPTER_KIND, subscriptions, rgs_by_sub)),
            ("SQL Databases", lambda: collect_sql_servers_and_databases(client, result, ADAPTER_KIND, subscriptions)),
            ("App Services", lambda: collect_app_services(client, result, ADAPTER_KIND, subscriptions)),
            ("Dedicated Hosts", lambda: collect_dedicated_hosts(client, result, ADAPTER_KIND, subscriptions, vm_lookup)),
            ("Public IPs", lambda: collect_public_ips(client, result, ADAPTER_KIND, subscriptions)),
            ("ExpressRoute", lambda: collect_expressroute_circuits(client, result, ADAPTER_KIND, subscriptions)),
            ("Recovery Vaults", lambda: collect_recovery_vaults(client, result, ADAPTER_KIND, subscriptions)),
            ("Log Analytics", lambda: collect_log_analytics_workspaces(client, result, ADAPTER_KIND, subscriptions)),
        ]

        for name, collector_fn in collectors:
            try:
                collector_fn()
            except Exception as e:
                logger.error("Collector %s failed: %s", name, e, exc_info=True)

    except Exception as e:
        logger.error("Collection failed: %s", e, exc_info=True)
        result.with_error(f"Collection failed: {e}")

    return result


# ---------------------------------------------------------------------------
# Connection Test
# ---------------------------------------------------------------------------

def test(adapter_instance):
    """Test connectivity to Azure Government Cloud.

    Validates credentials by acquiring a token and listing subscriptions.
    """
    from aria.ops.result import TestResult

    result = TestResult()

    try:
        tenant_id = adapter_instance.get_credential_value(CREDENTIAL_TENANT_ID)
        client_id = adapter_instance.get_credential_value(CREDENTIAL_CLIENT_ID)
        client_secret = adapter_instance.get_credential_value(CREDENTIAL_CLIENT_SECRET)

        cloud_env = adapter_instance.get_identifier_value(
            CONFIG_CLOUD_ENVIRONMENT, CLOUD_ENV_GOV
        )

        # Test authentication
        auth = AzureAuthenticator(tenant_id, client_id, client_secret,
                                  cloud_env)
        auth.test_connection()

        # Test API access by listing subscriptions
        client = AzureClient(auth, cloud_env)
        subs = client.get_all(
            path="/subscriptions",
            api_version="2022-12-01",
        )

        logger.info(f"Successfully connected. Found {len(subs)} subscription(s).")

    except Exception as e:
        logger.error("Connection test failed: %s", e, exc_info=True)
        result.with_error(f"Connection test failed: {e}")

    return result


# ---------------------------------------------------------------------------
# SDK Entry Point — dispatches based on method arg from mp-test
# ---------------------------------------------------------------------------

def get_endpoints(adapter_instance):
    """Return endpoint URLs for certificate validation."""
    from aria.ops.result import EndpointResult
    return EndpointResult()


def main(argv):
    import aria.ops.adapter_logging as adapter_logging
    from aria.ops.adapter_instance import AdapterInstance
    from aria.ops.timer import Timer

    adapter_logging.setup_logging("adapter.log")
    adapter_logging.rotate()
    logger.info(f"Running adapter code with arguments: {argv}")

    if len(argv) != 3:
        logger.error("Arguments must be <method> <inputfile> <outputfile>")
        sys.exit(1)

    method = argv[0]
    try:
        if method == "test":
            test(AdapterInstance.from_input()).send_results()
        elif method == "endpoint_urls":
            get_endpoints(AdapterInstance.from_input()).send_results()
        elif method == "collect":
            collect(AdapterInstance.from_input()).send_results()
        elif method == "adapter_definition":
            result = get_adapter_definition()
            logger.info(f"adapter_definition returned: {type(result)}")
            result.send_results()
            logger.info("send_results completed")
        else:
            logger.error(f"Command {method} not found")
            sys.exit(1)
    except Exception as e:
        logger.error(f"Error in {method}: {e}", exc_info=True)
    finally:
        logger.info(Timer.graph())
        sys.exit(0)


if __name__ == "__main__":
    main(sys.argv[1:])
