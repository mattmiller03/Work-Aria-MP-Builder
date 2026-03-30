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
    CONFIG_CLOUD_ENVIRONMENT, CLOUD_ENV_GOV,
    OBJ_SUBSCRIPTION, OBJ_RESOURCE_GROUP, OBJ_VIRTUAL_MACHINE,
    OBJ_DISK, OBJ_NETWORK_INTERFACE, OBJ_VIRTUAL_NETWORK, OBJ_SUBNET,
    OBJ_STORAGE_ACCOUNT, OBJ_LOAD_BALANCER, OBJ_KEY_VAULT,
    OBJ_SQL_SERVER, OBJ_SQL_DATABASE, OBJ_APP_SERVICE,
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
    sub.define_string_property("subscription_id", "Subscription ID",
                               is_part_of_uniqueness=True)
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
    rg.define_string_property("subscription_id", "Subscription ID",
                              is_part_of_uniqueness=True)
    rg.define_string_property("resource_group_name", "Resource Group Name",
                              is_part_of_uniqueness=True)
    rg.define_string_property("location", "Location")
    rg.define_string_property("provisioning_state", "Provisioning State")
    rg.define_string_property("resource_id", "Resource ID")

    # Virtual Machine
    vm = definition.define_object_type(OBJ_VIRTUAL_MACHINE,
                                       "Azure Virtual Machine")
    vm.define_string_property("subscription_id", "Subscription ID",
                              is_part_of_uniqueness=True)
    vm.define_string_property("resource_group", "Resource Group",
                              is_part_of_uniqueness=True)
    vm.define_string_property("vm_name", "VM Name",
                              is_part_of_uniqueness=True)
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

    # Disk
    disk = definition.define_object_type(OBJ_DISK, "Azure Disk")
    disk.define_string_property("subscription_id", "Subscription ID",
                                is_part_of_uniqueness=True)
    disk.define_string_property("resource_group", "Resource Group",
                                is_part_of_uniqueness=True)
    disk.define_string_property("disk_name", "Disk Name",
                                is_part_of_uniqueness=True)
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

    # Network Interface
    nic = definition.define_object_type(OBJ_NETWORK_INTERFACE,
                                        "Azure Network Interface")
    nic.define_string_property("subscription_id", "Subscription ID",
                               is_part_of_uniqueness=True)
    nic.define_string_property("resource_group", "Resource Group",
                               is_part_of_uniqueness=True)
    nic.define_string_property("nic_name", "NIC Name",
                               is_part_of_uniqueness=True)
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

    # Virtual Network
    vnet = definition.define_object_type(OBJ_VIRTUAL_NETWORK,
                                         "Azure Virtual Network")
    vnet.define_string_property("subscription_id", "Subscription ID",
                                is_part_of_uniqueness=True)
    vnet.define_string_property("resource_group", "Resource Group",
                                is_part_of_uniqueness=True)
    vnet.define_string_property("vnet_name", "VNet Name",
                                is_part_of_uniqueness=True)
    vnet.define_string_property("resource_id", "Resource ID")
    vnet.define_string_property("location", "Location")
    vnet.define_string_property("provisioning_state", "Provisioning State")
    vnet.define_string_property("address_prefixes", "Address Prefixes")
    vnet.define_string_property("dns_servers", "DNS Servers")
    vnet.define_string_property("ddos_protection_enabled",
                                "DDoS Protection Enabled")

    # Subnet
    subnet = definition.define_object_type(OBJ_SUBNET, "Azure Subnet")
    subnet.define_string_property("subscription_id", "Subscription ID",
                                  is_part_of_uniqueness=True)
    subnet.define_string_property("vnet_id", "VNet ID",
                                  is_part_of_uniqueness=True)
    subnet.define_string_property("subnet_name", "Subnet Name",
                                  is_part_of_uniqueness=True)
    subnet.define_string_property("resource_id", "Resource ID")
    subnet.define_string_property("address_prefix", "Address Prefix")
    subnet.define_string_property("provisioning_state", "Provisioning State")
    subnet.define_string_property("nsg_id", "NSG ID")
    subnet.define_string_property("route_table_id", "Route Table ID")
    subnet.define_string_property("service_endpoints", "Service Endpoints")

    # Storage Account
    sa = definition.define_object_type(OBJ_STORAGE_ACCOUNT,
                                       "Azure Storage Account")
    sa.define_string_property("subscription_id", "Subscription ID",
                              is_part_of_uniqueness=True)
    sa.define_string_property("resource_group", "Resource Group",
                              is_part_of_uniqueness=True)
    sa.define_string_property("account_name", "Account Name",
                              is_part_of_uniqueness=True)
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

    # Load Balancer
    lb = definition.define_object_type(OBJ_LOAD_BALANCER,
                                       "Azure Load Balancer")
    lb.define_string_property("subscription_id", "Subscription ID",
                              is_part_of_uniqueness=True)
    lb.define_string_property("resource_group", "Resource Group",
                              is_part_of_uniqueness=True)
    lb.define_string_property("lb_name", "Load Balancer Name",
                              is_part_of_uniqueness=True)
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

    # Key Vault
    kv = definition.define_object_type(OBJ_KEY_VAULT, "Azure Key Vault")
    kv.define_string_property("subscription_id", "Subscription ID",
                              is_part_of_uniqueness=True)
    kv.define_string_property("resource_group", "Resource Group",
                              is_part_of_uniqueness=True)
    kv.define_string_property("vault_name", "Vault Name",
                              is_part_of_uniqueness=True)
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
    sql_srv.define_string_property("subscription_id", "Subscription ID",
                                   is_part_of_uniqueness=True)
    sql_srv.define_string_property("resource_group", "Resource Group",
                                   is_part_of_uniqueness=True)
    sql_srv.define_string_property("server_name", "Server Name",
                                   is_part_of_uniqueness=True)
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

    # SQL Database
    sql_db = definition.define_object_type(OBJ_SQL_DATABASE,
                                           "Azure SQL Database")
    sql_db.define_string_property("subscription_id", "Subscription ID",
                                  is_part_of_uniqueness=True)
    sql_db.define_string_property("server_name", "Server Name",
                                  is_part_of_uniqueness=True)
    sql_db.define_string_property("database_name", "Database Name",
                                  is_part_of_uniqueness=True)
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

    # App Service
    app = definition.define_object_type(OBJ_APP_SERVICE,
                                        "Azure App Service")
    app.define_string_property("subscription_id", "Subscription ID",
                               is_part_of_uniqueness=True)
    app.define_string_property("resource_group", "Resource Group",
                               is_part_of_uniqueness=True)
    app.define_string_property("app_name", "App Name",
                               is_part_of_uniqueness=True)
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
        cred = adapter_instance.get_credential(CREDENTIAL_TYPE)
        tenant_id = cred.get_credential_value(CREDENTIAL_TENANT_ID)
        client_id = cred.get_credential_value(CREDENTIAL_CLIENT_ID)
        client_secret = cred.get_credential_value(CREDENTIAL_CLIENT_SECRET)
        target_sub = cred.get_credential_value(CREDENTIAL_SUBSCRIPTION_ID)

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

        # 3. All resource collectors
        collect_virtual_machines(client, result, ADAPTER_KIND, subscriptions)
        collect_disks(client, result, ADAPTER_KIND, subscriptions)
        collect_network_interfaces(client, result, ADAPTER_KIND, subscriptions)
        collect_virtual_networks(client, result, ADAPTER_KIND, subscriptions)
        collect_storage_accounts(client, result, ADAPTER_KIND, subscriptions)
        collect_load_balancers(client, result, ADAPTER_KIND, subscriptions)
        collect_key_vaults(client, result, ADAPTER_KIND, subscriptions,
                           rgs_by_sub)
        collect_sql_servers_and_databases(client, result, ADAPTER_KIND,
                                         subscriptions)
        collect_app_services(client, result, ADAPTER_KIND, subscriptions)

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
        cred = adapter_instance.get_credential(CREDENTIAL_TYPE)
        tenant_id = cred.get_credential_value(CREDENTIAL_TENANT_ID)
        client_id = cred.get_credential_value(CREDENTIAL_CLIENT_ID)
        client_secret = cred.get_credential_value(CREDENTIAL_CLIENT_SECRET)

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

        result.with_message(
            f"Successfully connected. Found {len(subs)} subscription(s)."
        )

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
    from aria.ops.definition.adapter_definition import AdapterDefinition
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
            if isinstance(result, AdapterDefinition):
                result.send_results()
            else:
                logger.error("get_adapter_definition did not return an AdapterDefinition")
                sys.exit(1)
        else:
            logger.error(f"Command {method} not found")
            sys.exit(1)
    finally:
        logger.info(Timer.graph())
        sys.exit(0)


if __name__ == "__main__":
    main(sys.argv[1:])
