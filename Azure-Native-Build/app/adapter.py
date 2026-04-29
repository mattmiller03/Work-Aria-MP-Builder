"""Main adapter for Azure Management Pack — Native Pak Compatible.

Implements the three entry points required by the Aria Operations Integration SDK:
- get_adapter_definition() — defines the object model (matches native pak describe.xml)
- collect() — collects data from Azure Gov/Commercial
- test() — validates connectivity

All adapter kind, object type, property, and metric keys match the VMware native
MicrosoftAzureAdapter v8.18.0 so existing dashboards and traversal specs are preserved.
"""

import logging
import sys

from constants import (
    ADAPTER_KIND, ADAPTER_NAME,
    CREDENTIAL_TYPE, CREDENTIAL_CLIENT_ID, CREDENTIAL_CLIENT_SECRET,
    CREDENTIAL_PROXY_HOST, CREDENTIAL_PROXY_PORT,
    CREDENTIAL_PROXY_USERNAME, CREDENTIAL_PROXY_PASSWORD,
    IDENT_SUBSCRIPTION_ID, IDENT_TENANT_ID, IDENT_ACCOUNT_TYPE,
    ACCOUNT_TYPE_GOV, ACCOUNT_TYPE_STANDARD,
    CLOUD_ENV_GOV, API_VERSIONS,
    RES_IDENT_SUB, RES_IDENT_RG, RES_IDENT_REGION, RES_IDENT_ID,
    OBJ_SUBSCRIPTION, OBJ_RESOURCE_GROUP, OBJ_VIRTUAL_MACHINE,
    OBJ_DISK, OBJ_NETWORK_INTERFACE, OBJ_VIRTUAL_NETWORK, OBJ_SUBNET,
    OBJ_STORAGE_ACCOUNT, OBJ_LOAD_BALANCER, OBJ_KEY_VAULT,
    OBJ_SQL_SERVER, OBJ_SQL_DATABASE, OBJ_APP_SERVICE,
    OBJ_HOST_GROUP, OBJ_DEDICATED_HOST,
    OBJ_PUBLIC_IP, OBJ_EXPRESSROUTE, OBJ_RECOVERY_VAULT, OBJ_LOG_ANALYTICS,
    OBJ_FUNCTIONS_APP, OBJ_APP_SERVICE_PLAN, OBJ_COSMOS_DB,
    OBJ_POSTGRESQL, OBJ_MYSQL,
    OBJ_REGION, OBJ_REGION_PER_SUB, OBJ_WORLD,
    ALL_NATIVE_STUB_KINDS,
    SD_SUBSCRIPTION, SD_RESOURCE_GROUP, SD_REGION, SD_SERVICE,
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
    collect_functions_apps,
    collect_app_service_plans,
    collect_cosmos_db_accounts,
    collect_postgresql_servers,
    collect_mysql_servers,
    collect_dedicated_hosts,
    collect_public_ips,
    collect_expressroute_circuits,
    collect_recovery_vaults,
    collect_log_analytics_workspaces,
    collect_regions_and_world,
    collect_all_generic_resources,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)


# ---------------------------------------------------------------------------
# Helper: add standard identifiers and SERVICE_DESCRIPTORS to a resource kind
# ---------------------------------------------------------------------------

def _add_standard_identifiers(obj_type):
    """Add the 4 standard identifiers that every native pak resource uses."""
    obj_type.define_string_identifier(RES_IDENT_SUB, "Subscription ID")
    obj_type.define_string_identifier(RES_IDENT_RG, "Resource Group")
    obj_type.define_string_identifier(RES_IDENT_REGION, "Region")
    obj_type.define_string_identifier(RES_IDENT_ID, "Resource ID")


def _add_service_descriptors(obj_type):
    """Add SERVICE_DESCRIPTORS property group matching native pak."""
    obj_type.define_string_property(SD_SUBSCRIPTION, "Subscription ID")
    obj_type.define_string_property(SD_RESOURCE_GROUP, "Resource Group")
    obj_type.define_string_property(SD_REGION, "Region")
    obj_type.define_string_property(SD_SERVICE, "Service")


def _add_generic_summary(obj_type):
    """Add genericsummary property group matching native pak."""
    obj_type.define_string_property("genericsummary|Name", "Name")
    obj_type.define_string_property("genericsummary|Location", "Location")
    obj_type.define_string_property("genericsummary|Id", "Resource ID")
    obj_type.define_string_property("genericsummary|Plan", "Plan")
    obj_type.define_string_property("genericsummary|PlanVersion", "Plan Version")
    obj_type.define_string_property("genericsummary|ManagedBy", "Managed By")
    obj_type.define_string_property("genericsummary|Sku", "SKU")
    obj_type.define_string_property("genericsummary|Type", "Type")


# ---------------------------------------------------------------------------
# Adapter Definition
# ---------------------------------------------------------------------------

def get_adapter_definition():
    """Define the adapter's object model, credentials, and configuration.

    The SDK uses this to auto-generate describe.xml at build time.
    All keys match the native MicrosoftAzureAdapter v8.18.0.
    """
    from aria.ops.definition.adapter_definition import AdapterDefinition
    from aria.ops.definition.units import Unit

    class _UnitWrapper:
        def __init__(self, unit):
            self.value = unit

    PERCENT = _UnitWrapper(Unit("percent", "%", 1, 1))
    BYTE = _UnitWrapper(Unit("byte", "B", 1, 1, "bytes_base_10"))
    MILLISECONDS = _UnitWrapper(Unit("milliseconds", "ms", 4, 1000))
    COUNT = _UnitWrapper(Unit("count", "", 1, 1))

    definition = AdapterDefinition(ADAPTER_KIND, ADAPTER_NAME)

    # -- Account Type (Gov vs Standard) --
    definition.define_enum_parameter(
        IDENT_ACCOUNT_TYPE,
        values=[ACCOUNT_TYPE_GOV, ACCOUNT_TYPE_STANDARD],
        label="Account Type",
        default=ACCOUNT_TYPE_GOV,
        description="Azure cloud environment",
    )

    # -- Subscription ID and Tenant ID as instance identifiers --
    definition.define_string_parameter(
        IDENT_SUBSCRIPTION_ID, label="Subscription ID",
        description="Azure Subscription ID",
    )
    definition.define_string_parameter(
        IDENT_TENANT_ID, label="Directory (Tenant) ID",
        description="Azure AD / Entra ID Tenant ID",
    )

    # -- Credential type: AZURE_CLIENT_CREDENTIALS --
    credential = definition.define_credential_type(
        CREDENTIAL_TYPE, "Azure Credentials"
    )
    credential.define_string_parameter(
        CREDENTIAL_CLIENT_ID, "Application (Client) ID"
    )
    credential.define_password_parameter(
        CREDENTIAL_CLIENT_SECRET, "Client Secret"
    )
    credential.define_string_parameter(
        CREDENTIAL_PROXY_HOST, "Proxy Host", required=False
    )
    credential.define_string_parameter(
        CREDENTIAL_PROXY_PORT, "Proxy Port", required=False
    )
    credential.define_string_parameter(
        CREDENTIAL_PROXY_USERNAME, "Proxy Username", required=False
    )
    credential.define_password_parameter(
        CREDENTIAL_PROXY_PASSWORD, "Proxy Password", required=False
    )

    # ===================================================================
    # Resource Kinds — 18 fully implemented
    # ===================================================================

    # -- Subscription (custom, no native equivalent) --
    sub = definition.define_object_type(OBJ_SUBSCRIPTION, "Azure Subscription")
    sub.define_string_identifier("subscription_id", "Subscription ID")
    sub.define_string_property("display_name", "Display Name")
    sub.define_string_property("state", "State")
    sub.define_string_property("tenant_id", "Tenant ID")

    # -- Resource Group --
    rg = definition.define_object_type(OBJ_RESOURCE_GROUP, "Azure Resource Group")
    rg.define_string_identifier(RES_IDENT_SUB, "Subscription ID")
    rg.define_string_identifier(RES_IDENT_ID, "Resource ID")

    # -- Virtual Machine --
    vm = definition.define_object_type(OBJ_VIRTUAL_MACHINE, "Azure Virtual Machine")
    _add_standard_identifiers(vm)
    # CPU group
    vm.define_metric("CPU|CPU_USAGE", "CPU Usage", unit=PERCENT, is_key_attribute=True)
    vm.define_metric("CPU|CPU_CRED_REMAINING", "CPU Credits Remaining")
    vm.define_metric("CPU|CPU_CRED_CONSUMED", "CPU Credits Consumed")
    # STORAGE group
    vm.define_metric("STORAGE|DATA_WRITE_DISK", "Disk Write Bytes", unit=BYTE)
    vm.define_metric("STORAGE|DATA_READ_DISK", "Disk Read Bytes", unit=BYTE)
    vm.define_metric("STORAGE|DISK_READ_OPERATION", "Disk Read Operations")
    vm.define_metric("STORAGE|DISK_WRITE_OPERATION", "Disk Write Operations")
    # NETWORK group
    vm.define_metric("NETWORK|NETWORK_IN", "Network In", unit=BYTE)
    vm.define_metric("NETWORK|NETWORK_OUT", "Network Out", unit=BYTE)
    # MEMORY group (custom — requires Azure Monitor Agent on VM)
    vm.define_metric("MEMORY|AVAILABLE_MEMORY_BYTES", "Available Memory Bytes", unit=BYTE)
    # general group
    vm.define_string_property("general|FQDN", "FQDN")
    vm.define_metric("general|running", "Running")
    # summary group
    vm.define_string_property("summary|OS_TYPE", "OS Type")
    vm.define_string_property("summary|OS_VHD_URI", "OS VHD URI")
    vm.define_string_property("summary|SIZING_TIER", "VM Size")
    vm.define_string_property("summary|availabilityZones", "Availability Zones")
    vm.define_string_property("summary|runtime|powerState", "Power State")
    _add_service_descriptors(vm)

    # -- Disk (AZURE_STORAGE_DISK) --
    disk = definition.define_object_type(OBJ_DISK, "Azure Managed Disk")
    _add_standard_identifiers(disk)
    disk.define_string_property("summary|name", "Name")
    disk.define_string_property("summary|type", "Disk Type")
    disk.define_string_property("summary|virtualMachineId", "Virtual Machine ID")
    disk.define_string_property("summary|sizeInGB", "Size (GB)")
    disk.define_string_property("summary|creationMethod", "Creation Method")
    disk.define_string_property("summary|isAttachedToVirtualMachine", "Attached to VM")
    disk.define_string_property("summary|osType", "OS Type")
    disk.define_string_property("summary|source", "Source")
    disk.define_string_property("summary|sku", "SKU")
    _add_service_descriptors(disk)

    # -- Network Interface (AZURE_NW_INTERFACE) --
    nic = definition.define_object_type(OBJ_NETWORK_INTERFACE, "Azure Network Interface")
    _add_standard_identifiers(nic)
    nic.define_metric("BYTES_SENT", "Bytes Sent", unit=BYTE)
    nic.define_metric("BYTES_RECEIVED", "Bytes Received", unit=BYTE)
    nic.define_metric("PACK_SENT", "Packets Sent")
    nic.define_metric("PACK_RECEIVED", "Packets Received")
    _add_service_descriptors(nic)

    # -- Virtual Network --
    vnet = definition.define_object_type(OBJ_VIRTUAL_NETWORK, "Azure Virtual Network")
    _add_standard_identifiers(vnet)
    _add_service_descriptors(vnet)

    # -- Subnet (custom, no native equivalent) --
    subnet = definition.define_object_type(OBJ_SUBNET, "Azure Subnet")
    subnet.define_string_identifier("subscription_id", "Subscription ID")
    subnet.define_string_identifier("vnet_id", "VNet ID")
    subnet.define_string_identifier("subnet_name", "Subnet Name")
    subnet.define_string_property("resource_id", "Resource ID")
    subnet.define_string_property("address_prefix", "Address Prefix")
    subnet.define_string_property("provisioning_state", "Provisioning State")

    # -- Storage Account --
    sa = definition.define_object_type(OBJ_STORAGE_ACCOUNT, "Azure Storage Account")
    _add_standard_identifiers(sa)
    # summary group — metrics
    sa.define_metric("summary|usedCapacity", "Used Capacity", unit=BYTE)
    sa.define_metric("summary|transactions", "Transactions", unit=COUNT)
    sa.define_metric("summary|ingress", "Ingress", unit=BYTE)
    sa.define_metric("summary|egress", "Egress", unit=BYTE)
    sa.define_metric("summary|successServerLatency", "Server Latency", unit=MILLISECONDS)
    sa.define_metric("summary|successE2ELatency", "E2E Latency", unit=MILLISECONDS)
    sa.define_metric("summary|availability", "Availability", unit=PERCENT)
    # blobService group — metrics
    sa.define_metric("blobService|blobCapacity", "Blob Capacity", unit=BYTE)
    sa.define_metric("blobService|blobCount", "Blob Count", unit=COUNT)
    sa.define_metric("blobService|containerCount", "Container Count", unit=COUNT)
    sa.define_metric("blobService|indexCapacity", "Index Capacity", unit=BYTE)
    sa.define_metric("blobService|transactions", "Blob Transactions", unit=COUNT)
    sa.define_metric("blobService|ingress", "Blob Ingress", unit=BYTE)
    sa.define_metric("blobService|egress", "Blob Egress", unit=BYTE)
    sa.define_metric("blobService|successServerLatency", "Blob Server Latency", unit=MILLISECONDS)
    sa.define_metric("blobService|successE2ELatency", "Blob E2E Latency", unit=MILLISECONDS)
    sa.define_metric("blobService|availability", "Blob Availability", unit=PERCENT)
    # queueService group — metrics
    sa.define_metric("queueService|queueCapacity", "Queue Capacity", unit=BYTE)
    sa.define_metric("queueService|queueCount", "Queue Count", unit=COUNT)
    sa.define_metric("queueService|queueMessageCount", "Queue Message Count", unit=COUNT)
    sa.define_metric("queueService|transactions", "Queue Transactions", unit=COUNT)
    sa.define_metric("queueService|ingress", "Queue Ingress", unit=BYTE)
    sa.define_metric("queueService|egress", "Queue Egress", unit=BYTE)
    sa.define_metric("queueService|successServerLatency", "Queue Server Latency", unit=MILLISECONDS)
    sa.define_metric("queueService|successE2ELatency", "Queue E2E Latency", unit=MILLISECONDS)
    sa.define_metric("queueService|availability", "Queue Availability", unit=PERCENT)
    # fileService group — metrics
    sa.define_metric("fileService|fileCapacity", "File Capacity", unit=BYTE)
    sa.define_metric("fileService|fileCount", "File Count", unit=COUNT)
    sa.define_metric("fileService|fileShareCount", "File Share Count", unit=COUNT)
    sa.define_metric("fileService|fileShareSnapshotCount", "File Share Snapshot Count", unit=COUNT)
    sa.define_metric("fileService|fileShareSnapshotSize", "File Share Snapshot Size", unit=BYTE)
    sa.define_metric("fileService|fileShareCapacityQuota", "File Share Capacity Quota", unit=BYTE)
    sa.define_metric("fileService|transactions", "File Transactions", unit=COUNT)
    sa.define_metric("fileService|ingress", "File Ingress", unit=BYTE)
    sa.define_metric("fileService|egress", "File Egress", unit=BYTE)
    sa.define_metric("fileService|successServerLatency", "File Server Latency", unit=MILLISECONDS)
    sa.define_metric("fileService|successE2ELatency", "File E2E Latency", unit=MILLISECONDS)
    sa.define_metric("fileService|availability", "File Availability", unit=PERCENT)
    # tableService group — metrics
    sa.define_metric("tableService|tableCapacity", "Table Capacity", unit=BYTE)
    sa.define_metric("tableService|tableCount", "Table Count", unit=COUNT)
    sa.define_metric("tableService|tableEntityCount", "Table Entity Count", unit=COUNT)
    sa.define_metric("tableService|transactions", "Table Transactions", unit=COUNT)
    sa.define_metric("tableService|ingress", "Table Ingress", unit=BYTE)
    sa.define_metric("tableService|egress", "Table Egress", unit=BYTE)
    sa.define_metric("tableService|successServerLatency", "Table Server Latency", unit=MILLISECONDS)
    sa.define_metric("tableService|successE2ELatency", "Table E2E Latency", unit=MILLISECONDS)
    sa.define_metric("tableService|availability", "Table Availability", unit=PERCENT)
    # summary group — properties
    sa.define_string_property("summary|name", "Name")
    sa.define_string_property("summary|creationTime", "Creation Time")
    sa.define_string_property("summary|primaryLocation", "Primary Location")
    sa.define_string_property("summary|enableHttpsTrafficOnly", "HTTPS Only")
    sa.define_string_property("summary|statusOfPrimary", "Status of Primary")
    sa.define_string_property("summary|provisioningState", "Provisioning State")
    _add_service_descriptors(sa)

    # -- Load Balancer (AZURE_LB) --
    lb = definition.define_object_type(OBJ_LOAD_BALANCER, "Azure Load Balancer")
    _add_standard_identifiers(lb)
    lb.define_metric("DATA_PATH_AVAILABLITY", "Data Path Availability")
    lb.define_metric("HEALTH_PROBE_STATUS", "Health Probe Status")
    lb.define_metric("BYTE_COUNT", "Byte Count")
    lb.define_metric("PACKET_COUNT", "Packet Count")
    _add_service_descriptors(lb)

    # -- Key Vault (AZURE_KEY_VAULTS) --
    kv = definition.define_object_type(OBJ_KEY_VAULT, "Azure Key Vault")
    _add_standard_identifiers(kv)
    kv.define_string_property("summary|name", "Name")
    kv.define_string_property("summary|id", "ID")
    kv.define_string_property("summary|type", "Type")
    kv.define_string_property("summary|tags", "Tags")
    kv.define_string_property("summary|regionName", "Region")
    kv.define_string_property("summary|tenantId", "Tenant ID")
    kv.define_string_property("summary|vaultUri", "Vault URI")
    kv.define_string_property("summary|createMode", "Create Mode")
    kv.define_string_property("summary|enabledForDeployment", "Enabled for Deployment")
    kv.define_string_property("summary|enabledForDiskEncryption", "Enabled for Disk Encryption")
    kv.define_string_property("summary|enabledForTemplateDeployment", "Enabled for Template Deployment")
    kv.define_string_property("summary|purgeProtectionEnabled", "Purge Protection Enabled")
    kv.define_string_property("summary|softDeleteEnabled", "Soft Delete Enabled")
    kv.define_string_property("summary|client", "Client")
    _add_generic_summary(kv)
    _add_service_descriptors(kv)

    # -- SQL Server --
    sql_srv = definition.define_object_type(OBJ_SQL_SERVER, "Azure SQL Server")
    _add_standard_identifiers(sql_srv)
    sql_srv.define_metric("CPU|CPU_USAGE", "CPU Usage", unit=PERCENT)
    sql_srv.define_metric("STORAGE|DATA_IO", "Data I/O", unit=PERCENT)
    sql_srv.define_metric("STORAGE|DATABASE_SIZE", "Database Size", unit=BYTE)
    sql_srv.define_metric("STORAGE|IN_MEM_OLTP_STORAGE", "In-Memory OLTP Storage", unit=PERCENT)
    sql_srv.define_metric("WORKLOAD|LOG_IO", "Log I/O", unit=PERCENT)
    sql_srv.define_metric("WORKLOAD|CON_SESSION", "Sessions", unit=PERCENT)
    sql_srv.define_metric("WORKLOAD|CON_WORKER", "Workers", unit=PERCENT)
    sql_srv.define_metric("WORKLOAD|DTU_USED", "DTU Used")
    sql_srv.define_string_property("SQL_VERSION", "SQL Version")
    _add_service_descriptors(sql_srv)

    # -- SQL Database --
    sql_db = definition.define_object_type(OBJ_SQL_DATABASE, "Azure SQL Database")
    _add_standard_identifiers(sql_db)
    sql_db.define_string_identifier("SERVER_ID", "Server ID")
    # CPU group
    sql_db.define_metric("CPU|CPU_USAGE", "CPU Usage", unit=PERCENT, is_key_attribute=True)
    # STORAGE group
    sql_db.define_metric("STORAGE|DATA_IO", "Data I/O", unit=PERCENT)
    sql_db.define_metric("STORAGE|DATABASE_SIZE", "Database Size", unit=BYTE)
    sql_db.define_metric("STORAGE|IN_MEM_OLTP_STORAGE", "In-Memory OLTP Storage", unit=PERCENT)
    # WORKLOAD group
    sql_db.define_metric("WORKLOAD|LOG_IO", "Log I/O", unit=PERCENT)
    sql_db.define_metric("WORKLOAD|CON_SESSION", "Sessions", unit=PERCENT)
    sql_db.define_metric("WORKLOAD|CON_WORKER", "Workers", unit=PERCENT)
    sql_db.define_metric("WORKLOAD|DTU_USED", "DTU Used")
    # Flat metrics
    sql_db.define_metric("DTU_PERCENTAGE", "DTU Percentage", unit=PERCENT)
    sql_db.define_metric("SUCCESSFUL_CONNECTIONS", "Successful Connections")
    sql_db.define_metric("FAILED_CONNECTIONS", "Failed Connections")
    sql_db.define_metric("BLOCKED_BY_FIREWALL", "Blocked by Firewall")
    sql_db.define_metric("DEADLOCKS", "Deadlocks")
    sql_db.define_metric("DATA_SPACE_USED_PERCENT", "Data Space Used", unit=PERCENT)
    sql_db.define_metric("DTU_LIMIT", "DTU Limit")
    sql_db.define_metric("CPU_LIMIT", "CPU Limit")
    sql_db.define_metric("CPU_USED", "CPU Used")
    sql_db.define_metric("DWU_LIMIT", "DWU Limit")
    sql_db.define_metric("DWU_PERCENTAGE", "DWU Percentage", unit=PERCENT)
    sql_db.define_metric("DWU_USED", "DWU Used")
    # Additional metrics from native pak decompiled source
    sql_db.define_metric("DW_NODE_LEVEL_CPU_PERCENTAGE", "DW Node CPU Percentage", unit=PERCENT)
    sql_db.define_metric("DW_NODE_LEVEL_DATA_IO_PERCENTAGE", "DW Node Data IO Percentage", unit=PERCENT)
    sql_db.define_metric("CACHE_HIT_PERCENTAGE", "Cache Hit Percentage", unit=PERCENT)
    sql_db.define_metric("CACHE_USED_PERCENTAGE", "Cache Used Percentage", unit=PERCENT)
    sql_db.define_metric("LOCAL_TEMPDB_PERCENTAGE", "Local TempDB Percentage", unit=PERCENT)
    sql_db.define_metric("APP_CPU_BILLED", "App CPU Billed")
    sql_db.define_metric("APP_CPU_PERCENTAGE", "App CPU Percentage", unit=PERCENT)
    sql_db.define_metric("APP_MEMORY_USED_PERCENTAGE", "App Memory Used Percentage", unit=PERCENT)
    sql_db.define_metric("DATA_SPACE_ALLOCATED", "Data Space Allocated", unit=BYTE)
    _add_service_descriptors(sql_db)

    # -- App Service --
    app = definition.define_object_type(OBJ_APP_SERVICE, "Azure App Service")
    _add_standard_identifiers(app)
    # CPU group
    app.define_metric("CPU|cpuTime", "CPU Time")
    # summary group — metrics
    app.define_metric("summary|requests", "Requests", unit=COUNT)
    app.define_metric("summary|bytesReceived", "Data In", unit=BYTE)
    app.define_metric("summary|bytesSent", "Data Out", unit=BYTE)
    app.define_metric("summary|http101", "Http 101", unit=COUNT)
    app.define_metric("summary|http2xx", "Http 2xx", unit=COUNT)
    app.define_metric("summary|http3xx", "Http 3xx", unit=COUNT)
    app.define_metric("summary|http401", "Http 401", unit=COUNT)
    app.define_metric("summary|http403", "Http 403", unit=COUNT)
    app.define_metric("summary|http404", "Http 404", unit=COUNT)
    app.define_metric("summary|http406", "Http 406", unit=COUNT)
    app.define_metric("summary|http4xx", "Http 4xx", unit=COUNT)
    app.define_metric("summary|http5xx", "Http Server Errors", unit=COUNT)
    app.define_metric("summary|memoryWorkingSet", "Memory Working Set", unit=BYTE)
    app.define_metric("summary|averageMemoryWorkingSet", "Average Memory Working Set", unit=BYTE)
    app.define_metric("summary|averageResponseTime", "Average Response Time")
    app.define_metric("summary|httpResponseTime", "Response Time")
    app.define_metric("summary|appConnections", "Connections", unit=COUNT)
    app.define_metric("summary|handles", "Handle Count", unit=COUNT)
    app.define_metric("summary|threads", "Thread Count", unit=COUNT)
    app.define_metric("summary|privateBytes", "Private Bytes", unit=BYTE)
    app.define_metric("summary|ioReadBytesPerSecond", "IO Read Bytes Per Second", unit=BYTE)
    app.define_metric("summary|ioWriteBytesPerSecond", "IO Write Bytes Per Second", unit=BYTE)
    app.define_metric("summary|ioOtherBytesPerSecond", "IO Other Bytes Per Second", unit=BYTE)
    app.define_metric("summary|ioReadOperationsPerSecond", "IO Read Operations Per Second")
    app.define_metric("summary|ioWriteOperationsPerSecond", "IO Write Operations Per Second")
    app.define_metric("summary|ioOtherOperationsPerSecond", "IO Other Operations Per Second")
    app.define_metric("summary|requestsInApplicationQueue", "Requests In Application Queue", unit=COUNT)
    app.define_metric("summary|currentAssemblies", "Current Assemblies", unit=COUNT)
    app.define_metric("summary|totalAppDomains", "Total App Domains", unit=COUNT)
    app.define_metric("summary|totalAppDomainsUnloaded", "Total App Domains Unloaded", unit=COUNT)
    app.define_metric("summary|gen0Collections", "Gen 0 Garbage Collections", unit=COUNT)
    app.define_metric("summary|gen1Collections", "Gen 1 Garbage Collections", unit=COUNT)
    app.define_metric("summary|gen2Collections", "Gen 2 Garbage Collections", unit=COUNT)
    app.define_metric("summary|healthCheckStatus", "Health Check Status")
    app.define_metric("summary|fileSystemUsage", "File System Usage", unit=BYTE)
    # summary group — properties
    app.define_string_property("summary|name", "Name")
    app.define_string_property("summary|appServicePlanId", "App Service Plan ID")
    app.define_string_property("summary|defaultHostName", "Default Host Name")
    app.define_string_property("summary|javaContainer", "Java Container")
    app.define_string_property("summary|javaContainerVersion", "Java Container Version")
    app.define_string_property("summary|linuxFxVersion", "Linux Fx Version")
    app.define_string_property("summary|state", "State")
    app.define_string_property("summary|containerSize", "Container Size")
    app.define_string_property("summary|alwaysOn", "Always On")
    app.define_string_property("summary|http20Enabled", "HTTP/2 Enabled")
    app.define_string_property("summary|httpsOnly", "HTTPS Only")
    app.define_string_property("summary|hostNamesDisabled", "Host Names Disabled")
    app.define_string_property("summary|hostNames", "Host Names")
    _add_service_descriptors(app)

    # -- Functions App (AZURE_FUNCTIONS_APP) --
    fa = definition.define_object_type(OBJ_FUNCTIONS_APP, "Azure Functions App")
    _add_standard_identifiers(fa)
    fa.define_string_property("summary|name", "Name")
    fa.define_string_property("summary|id", "ID")
    fa.define_string_property("summary|type", "Type")
    fa.define_string_property("summary|tags", "Tags")
    fa.define_string_property("summary|appServicePlanId", "App Service Plan ID")
    fa.define_string_property("summary|defaultHostName", "Default Host Name")
    fa.define_string_property("summary|state", "State")
    fa.define_string_property("summary|containerSize", "Container Size")
    fa.define_string_property("summary|availabilityState", "Availability State")
    fa.define_string_property("summary|alwaysOn", "Always On")
    fa.define_string_property("summary|clientAffinityEnabled", "Client Affinity Enabled")
    fa.define_string_property("summary|linuxFxVersion", "Linux Fx Version")
    fa.define_string_property("summary|nodeVersion", "Node Version")
    fa.define_string_property("summary|regionName", "Region")
    fa.define_string_property("summary|repositorySiteName", "Repository Site Name")
    _add_generic_summary(fa)
    _add_service_descriptors(fa)

    # -- App Service Plan (AZURE_APP_SERVICE_PLAN) --
    asp = definition.define_object_type(OBJ_APP_SERVICE_PLAN, "Azure App Service Plan")
    _add_standard_identifiers(asp)
    asp.define_string_property("summary|name", "Name")
    asp.define_string_property("summary|provisioningState", "Provisioning State")
    asp.define_string_property("summary|sku", "SKU")
    asp.define_string_property("summary|tags", "Tags")
    asp.define_string_property("summary|capacity", "Capacity")
    asp.define_string_property("summary|maxInstances", "Max Instances")
    asp.define_string_property("summary|numberOfWebApps", "Number of Web Apps")
    asp.define_string_property("summary|operatingSystem", "Operating System")
    asp.define_string_property("summary|pricingTier", "Pricing Tier")
    asp.define_string_property("summary|workerTierName", "Worker Tier Name")
    asp.define_string_property("summary|maximumElasticWorkerCount", "Max Elastic Worker Count")
    asp.define_string_property("summary|maximumNumberOfWorkers", "Max Number of Workers")
    asp.define_string_property("summary|numberOfSites", "Number of Sites")
    asp.define_string_property("summary|targetWorkerCount", "Target Worker Count")
    asp.define_string_property("summary|targetWorkerSizeId", "Target Worker Size ID")
    asp.define_string_property("summary|freeOfferExpirationTime", "Free Offer Expiration Time")
    asp.define_string_property("summary|hyperV", "Hyper-V")
    asp.define_string_property("summary|isSpot", "Is Spot")
    asp.define_string_property("summary|isXenon", "Is Xenon")
    asp.define_string_property("summary|hostingEnvironmentProfile", "Hosting Environment Profile")
    asp.define_string_property("summary|reserved", "Reserved")
    asp.define_string_property("summary|spotExpirationTime", "Spot Expiration Time")
    asp.define_string_property("summary|status", "Status")
    _add_generic_summary(asp)
    _add_service_descriptors(asp)

    # -- Cosmos DB Account (AZURE_DB_ACCOUNT) --
    cosmos = definition.define_object_type(OBJ_COSMOS_DB, "Azure Cosmos DB Account")
    _add_standard_identifiers(cosmos)
    # Native pak flat metrics
    cosmos.define_metric("AVAIL_STORAGE", "Available Storage", unit=BYTE)
    cosmos.define_metric("DATA_USAGE", "Data Usage", unit=BYTE)
    cosmos.define_metric("INDEX_USAGE", "Index Usage", unit=BYTE)
    cosmos.define_metric("DOC_QUOTA", "Document Quota", unit=BYTE)
    cosmos.define_metric("DOC_COUNT", "Document Count", unit=COUNT)
    _add_generic_summary(cosmos)
    _add_service_descriptors(cosmos)

    # -- PostgreSQL Server (AZURE_POSTGRESQL_SERVER) --
    pg = definition.define_object_type(OBJ_POSTGRESQL, "Azure PostgreSQL Server")
    _add_standard_identifiers(pg)
    pg.define_metric("CPU_PERCENT", "CPU Percent", unit=PERCENT)
    pg.define_metric("MEMORY_PERCENT", "Memory Percent", unit=PERCENT)
    pg.define_metric("IO_PERCENT", "IO Percent", unit=PERCENT)
    pg.define_metric("STORAGE_PERCENT", "Storage Percent", unit=PERCENT)
    pg.define_metric("STORAGE_USED", "Storage Used", unit=BYTE)
    pg.define_metric("STORAGE_LIMIT", "Storage Limit", unit=BYTE)
    pg.define_metric("SERVER_LOG_STORAGE_PERCENT", "Server Log Storage Percent", unit=PERCENT)
    pg.define_metric("SERVER_LOG_STORAGE_USED", "Server Log Storage Used", unit=BYTE)
    pg.define_metric("SERVER_LOG_STORAGE_LIMIT", "Server Log Storage Limit", unit=BYTE)
    pg.define_metric("ACTIVE_CONNECTIONS", "Active Connections")
    pg.define_metric("FAILED_CONNECTIONS", "Failed Connections")
    pg.define_metric("BACKUP_STORAGE_USED", "Backup Storage Used", unit=BYTE)
    pg.define_metric("NETWORK_OUT", "Network Out", unit=BYTE)
    pg.define_metric("NETWORK_IN", "Network In", unit=BYTE)
    pg.define_metric("REPLICA_LAG", "Replica Lag")
    pg.define_metric("MAX_LAG_ACROSS_REPLICAS", "Max Lag Across Replicas", unit=BYTE)
    _add_service_descriptors(pg)

    # -- MySQL Server (AZURE_MYSQL_SERVER) --
    my = definition.define_object_type(OBJ_MYSQL, "Azure MySQL Server")
    _add_standard_identifiers(my)
    my.define_metric("CPU_PERCENT", "CPU Percent", unit=PERCENT)
    my.define_metric("MEMORY_PERCENT", "Memory Percent", unit=PERCENT)
    my.define_metric("IO_PERCENT", "IO Percent", unit=PERCENT)
    my.define_metric("STORAGE_PERCENT", "Storage Percent", unit=PERCENT)
    my.define_metric("STORAGE_USED", "Storage Used", unit=BYTE)
    my.define_metric("STORAGE_LIMIT", "Storage Limit", unit=BYTE)
    my.define_metric("SERVER_LOG_STORAGE_PERCENT", "Server Log Storage Percent", unit=PERCENT)
    my.define_metric("SERVER_LOG_STORAGE_USED", "Server Log Storage Used", unit=BYTE)
    my.define_metric("SERVER_LOG_STORAGE_LIMIT", "Server Log Storage Limit", unit=BYTE)
    my.define_metric("ACTIVE_CONNECTIONS", "Active Connections")
    my.define_metric("FAILED_CONNECTIONS", "Failed Connections")
    my.define_metric("REPLICATION_LAG_IN_SECONDS", "Replication Lag")
    my.define_metric("BACKUP_STORAGE_USED", "Backup Storage Used", unit=BYTE)
    my.define_metric("NETWORK_OUT", "Network Out", unit=BYTE)
    my.define_metric("NETWORK_IN", "Network In", unit=BYTE)
    _add_service_descriptors(my)

    # -- Host Group (AZURE_COMPUTE_HOSTGROUPS) --
    hg = definition.define_object_type(OBJ_HOST_GROUP, "Azure Dedicated Host Group")
    _add_standard_identifiers(hg)
    hg.define_string_property("summary|name", "Name")
    hg.define_string_property("summary|id", "ID")
    hg.define_string_property("summary|type", "Type")
    hg.define_string_property("summary|tags", "Tags")
    hg.define_string_property("summary|platformFaultDomainCount", "Fault Domain Count")
    hg.define_string_property("summary|supportAutomaticPlacement", "Automatic Placement")
    hg.define_string_property("summary|zones", "Zones")
    _add_generic_summary(hg)
    _add_service_descriptors(hg)

    # -- Dedicated Host (AZURE_DEDICATE_HOST — native pak typo) --
    dh = definition.define_object_type(OBJ_DEDICATED_HOST, "Azure Dedicated Host")
    _add_standard_identifiers(dh)
    dh.define_string_identifier("hostGroupName", "Host Group Name")
    dh.define_string_property("summary|name", "Name")
    dh.define_string_property("summary|id", "ID")
    dh.define_string_property("summary|type", "Type")
    dh.define_string_property("summary|tags", "Tags")
    dh.define_string_property("summary|hostId", "Host ID")
    dh.define_string_property("summary|platformFaultDomain", "Fault Domain")
    dh.define_string_property("summary|autoReplaceOnFailure", "Auto Replace")
    dh.define_string_property("summary|provisioningState", "Provisioning State")
    dh.define_string_property("summary|regionName", "Region")
    dh.define_string_property("summary|provisioningTime", "Provisioning Time")
    dh.define_string_property("summary|instanceView", "Instance View")
    dh.define_string_property("summary|licenseTypes", "License Types")
    # Custom extensions (not in native pak — additive)
    dh.define_numeric_property("vm_count", "VM Count")
    dh.define_string_property("vm_names", "VM Names")
    dh.define_string_property("vm_size_summary", "VM Size Breakdown")
    dh.define_string_property("allocatable_vm_summary", "Allocatable VM Capacity")
    dh.define_numeric_property("hourly_rate", "Hourly Compute Rate (USD)")
    dh.define_numeric_property("monthly_rate_estimate", "Monthly Rate Estimate (USD)")
    # Memory tracking per dedicated host
    dh.define_numeric_property("total_vm_memory_gb", "Total VM Memory Allocated (GB)")
    dh.define_string_property("vm_memory_breakdown", "VM Memory Breakdown")
    dh.define_numeric_property("host_memory_capacity_gb", "Host Memory Capacity (GB)")
    dh.define_numeric_property("memory_utilization_pct", "Memory Utilization (%)")
    dh.define_numeric_property("memory_available_gb", "Memory Available (GB)")
    # Cost Management
    dh.define_numeric_property("cost_month_to_date", "Cost Month To Date")
    dh.define_string_property("cost_currency", "Cost Currency")
    dh.define_numeric_property("cost_last_30_days", "Cost Last 30 Days")
    # Resource Health
    dh.define_string_property("health_availability_state", "Health Availability State")
    dh.define_string_property("health_detailed_status", "Health Detailed Status")
    dh.define_string_property("health_reason_type", "Health Reason Type")
    dh.define_string_property("health_occurred_time", "Health Occurred Time")
    dh.define_string_property("health_summary", "Health Summary")
    # Maintenance
    dh.define_string_property("maintenance_pending", "Maintenance Pending")
    dh.define_string_property("maintenance_impact_type", "Maintenance Impact Type")
    dh.define_string_property("maintenance_status", "Maintenance Status")
    dh.define_string_property("maintenance_not_before", "Maintenance Not Before")
    dh.define_string_property("maintenance_not_after", "Maintenance Not After")
    # Advisor Recommendations
    dh.define_numeric_property("advisor_recommendation_count", "Advisor Recommendation Count")
    dh.define_string_property("advisor_recommendations", "Advisor Recommendations")
    dh.define_string_property("advisor_impact", "Advisor Impact")
    dh.define_string_property("advisor_category", "Advisor Category")
    # Activity Log
    dh.define_numeric_property("recent_operations_count", "Recent Operations Count (7d)")
    dh.define_string_property("last_operation", "Last Operation")
    dh.define_string_property("last_operation_time", "Last Operation Time")
    dh.define_string_property("last_operation_status", "Last Operation Status")
    dh.define_string_property("last_operation_caller", "Last Operation Caller")
    # vCPU capacity (Source 6 — expanded SKU API)
    dh.define_numeric_property("host_vcpu_capacity", "Host vCPU Capacity")
    dh.define_numeric_property("total_vm_vcpus_allocated", "Total VM vCPUs Allocated")
    dh.define_numeric_property("vcpu_utilization_pct", "vCPU Utilization (%)")
    # Computed host-level metrics — aggregated from VMs (Source 7)
    dh.define_metric("host_cpu_avg", "Host Avg CPU%", unit=PERCENT)
    dh.define_metric("host_cpu_max", "Host Peak CPU%", unit=PERCENT)
    dh.define_metric("host_cpu_min", "Host Min CPU%", unit=PERCENT)
    dh.define_metric("host_network_in_total", "Host Network In Total", unit=BYTE)
    dh.define_metric("host_network_out_total", "Host Network Out Total", unit=BYTE)
    dh.define_metric("host_disk_read_total", "Host Disk Read Total", unit=BYTE)
    dh.define_metric("host_disk_write_total", "Host Disk Write Total", unit=BYTE)
    # Policy Compliance (Source 8)
    dh.define_string_property("policy_compliance_state", "Policy Compliance State")
    dh.define_numeric_property("policy_non_compliant_count", "Policy Non-Compliant Count")
    # Reservations (Source 9)
    dh.define_string_property("reservation_status", "Reservation Status")
    dh.define_string_property("reservation_id", "Reservation Order ID")
    dh.define_string_property("reservation_expiry", "Reservation Expiry Date")
    # Missing ARM properties (Source 10)
    dh.define_string_property("time_created", "Time Created")
    dh.define_string_property("sku_tier", "SKU Tier")
    dh.define_string_property("sku_capacity", "SKU Capacity")
    dh.define_string_property("health_status_time", "Health Status Time")
    dh.define_string_property("health_status_message", "Health Status Message")
    _add_generic_summary(dh)
    _add_service_descriptors(dh)

    # -- Public IP (AZURE_PUBLIC_IPADDRESSES) --
    pip = definition.define_object_type(OBJ_PUBLIC_IP, "Azure Public IP Address")
    _add_standard_identifiers(pip)
    _add_service_descriptors(pip)

    # -- ExpressRoute Circuit --
    er = definition.define_object_type(OBJ_EXPRESSROUTE, "Azure ExpressRoute Circuit")
    _add_standard_identifiers(er)
    _add_service_descriptors(er)

    # -- Recovery Services Vault (custom, no native equivalent) --
    # NOTE: no _add_service_descriptors() — the SDK emits SERVICE_DESCRIPTORS as
    # flat pipe-separated attribute keys ("SERVICE_DESCRIPTORS|AZURE_SUBSCRIPTION_ID")
    # which Aria Ops's parser rejects as "Illegal symbols in attribute key". The
    # 19 native-equivalent kinds get away with it because the dynamic loader in
    # patch-describe-xml.py substitutes them with native nested-ResourceGroup XML.
    # Custom kinds with no native equivalent must avoid SERVICE_DESCRIPTORS.
    rv = definition.define_object_type(OBJ_RECOVERY_VAULT, "Azure Recovery Services Vault")
    _add_standard_identifiers(rv)

    # -- Log Analytics Workspace (custom, no native equivalent) --
    # See note above re: SERVICE_DESCRIPTORS exclusion for custom kinds.
    la = definition.define_object_type(OBJ_LOG_ANALYTICS, "Azure Log Analytics Workspace")
    _add_standard_identifiers(la)

    # ===================================================================
    # Region / World aggregation kinds — match native pak describe.xml
    # ===================================================================

    # Helper: define the full set of summary|total_number_* metrics shared
    # by AZURE_REGION_PER_SUB, AZURE_REGION, and AZURE_WORLD.
    def _add_summary_count_metrics(obj_type):
        """Add all summary|total_number_* metrics from native pak."""
        obj_type.define_metric("summary|total_number_vms", "Total VMs")
        obj_type.define_metric("summary|active_number_vms", "Active VMs")
        obj_type.define_metric("summary|total_number_storgeaccounts", "Total Storage Accounts")
        obj_type.define_metric("summary|total_number_sqlserver", "Total SQL Servers")
        obj_type.define_metric("summary|total_number_loadbalancers", "Total Load Balancers")
        obj_type.define_metric("summary|total_number_nwInterface", "Total Network Interfaces")
        obj_type.define_metric("summary|total_number_vNets", "Total Virtual Networks")
        obj_type.define_metric("summary|total_number_appServices", "Total App Services")
        obj_type.define_metric("summary|total_number_storageDisks", "Total Storage Disks")
        obj_type.define_metric("summary|total_number_hostGroups", "Total Host Groups")
        obj_type.define_metric("summary|total_number_dedicatedHosts", "Total Dedicated Hosts")
        obj_type.define_metric("summary|total_number_publicIPAddresses", "Total Public IPs")
        obj_type.define_metric("summary|total_number_expressrouteCircuit", "Total ExpressRoute Circuits")
        obj_type.define_metric("summary|total_number_keyVaults", "Total Key Vaults")
        obj_type.define_metric("summary|total_number_postgresqlserver", "Total PostgreSQL Servers")
        obj_type.define_metric("summary|total_number_mysqlserver", "Total MySQL Servers")
        obj_type.define_metric("summary|total_number_functionApp", "Total Function Apps")
        obj_type.define_metric("summary|total_number_subscriptions", "Total Subscriptions")

    # Geo aggregation kinds — no <ResourceIdentifier> children (display name is
    # the unique key). The SDK emits pipe-keyed `summary|total_number_*` metrics
    # which Aria Ops would reject, BUT the dynamic loader in
    # patch-describe-xml.py substitutes the entire ResourceKind block with
    # the native verbatim XML (which uses nested ResourceGroup) before pak
    # packaging.
    # -- AZURE_REGION_PER_SUB --
    rps = definition.define_object_type(OBJ_REGION_PER_SUB, "Azure Region Per Subscription")
    _add_summary_count_metrics(rps)

    # -- AZURE_REGION --
    reg = definition.define_object_type(OBJ_REGION, "Azure Region")
    _add_summary_count_metrics(reg)

    # -- AZURE_WORLD --
    world = definition.define_object_type(OBJ_WORLD, "Azure World")
    _add_summary_count_metrics(world)
    world.define_metric("summary|total_number_regions", "Total Regions")

    # ===================================================================
    # Stub Resource Kinds — 18 native pak types we don't actively collect
    # ===================================================================
    # TEMPORARILY DISABLED for install-failure bisection. If enabling the
    # stub loop is what blocks APPLY_ADAPTER, the generic 4-identifier
    # shape we're using must not match what Aria Ops expects for these
    # specific kinds. Remove the `False and` to re-enable.
    if False:
        for stub_key in ALL_NATIVE_STUB_KINDS:
            stub = definition.define_object_type(stub_key, stub_key)
            _add_standard_identifiers(stub)
            _add_service_descriptors(stub)

    return definition


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------

def collect(adapter_instance):
    """Collect resources from Azure Government or Commercial Cloud.

    Called by Aria Operations on each collection cycle.
    """
    from aria.ops.result import CollectResult

    result = CollectResult()

    try:
        # Extract instance identifiers
        tenant_id = adapter_instance.get_identifier_value(IDENT_TENANT_ID)
        target_sub = adapter_instance.get_identifier_value(IDENT_SUBSCRIPTION_ID)
        account_type = adapter_instance.get_identifier_value(
            IDENT_ACCOUNT_TYPE, ACCOUNT_TYPE_GOV
        )

        # Extract credentials
        client_id = adapter_instance.get_credential_value(CREDENTIAL_CLIENT_ID)
        client_secret = adapter_instance.get_credential_value(CREDENTIAL_CLIENT_SECRET)

        # Determine cloud environment from account type
        cloud_env = CLOUD_ENV_GOV if account_type == ACCOUNT_TYPE_GOV else "commercial"

        # Authenticate
        auth = AzureAuthenticator(tenant_id, client_id, client_secret, cloud_env)
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
                logger.warning("Configured subscription %s not found", target_sub)

        # 2. Resource Groups
        rgs_by_sub = collect_resource_groups(client, result, ADAPTER_KIND,
                                             subscriptions)

        # 3. Collect VMs first and build lookup for dedicated host enrichment
        vm_lookup = {}
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
            ("Function Apps", lambda: collect_functions_apps(client, result, ADAPTER_KIND, subscriptions)),
            ("App Service Plans", lambda: collect_app_service_plans(client, result, ADAPTER_KIND, subscriptions)),
            ("Cosmos DB", lambda: collect_cosmos_db_accounts(client, result, ADAPTER_KIND, subscriptions)),
            ("PostgreSQL Servers", lambda: collect_postgresql_servers(client, result, ADAPTER_KIND, subscriptions)),
            ("MySQL Servers", lambda: collect_mysql_servers(client, result, ADAPTER_KIND, subscriptions)),
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

        # 5. Bulk generic ARM resources (networking, containers, compute, etc.)
        try:
            collect_all_generic_resources(client, result, ADAPTER_KIND, subscriptions)
        except Exception as e:
            logger.error("Bulk resource collection failed: %s", e, exc_info=True)

        # 6. Region & World aggregation — must run AFTER all resource collectors
        try:
            adapter_instance_name = target_sub or "Azure"
            collect_regions_and_world(
                result, ADAPTER_KIND, subscriptions, adapter_instance_name,
            )
        except Exception as e:
            logger.error("Regions/World collector failed: %s", e, exc_info=True)

    except Exception as e:
        logger.error("Collection failed: %s", e, exc_info=True)
        result.with_error(f"Collection failed: {e}")

    return result


# ---------------------------------------------------------------------------
# Connection Test
# ---------------------------------------------------------------------------

def test(adapter_instance):
    """Test connectivity to Azure Government or Commercial Cloud.

    Validates credentials by acquiring a token and listing subscriptions.
    """
    from aria.ops.result import TestResult

    result = TestResult()

    try:
        # Extract instance identifiers
        tenant_id = adapter_instance.get_identifier_value(IDENT_TENANT_ID)
        account_type = adapter_instance.get_identifier_value(
            IDENT_ACCOUNT_TYPE, ACCOUNT_TYPE_GOV
        )

        # Extract credentials
        client_id = adapter_instance.get_credential_value(CREDENTIAL_CLIENT_ID)
        client_secret = adapter_instance.get_credential_value(CREDENTIAL_CLIENT_SECRET)

        cloud_env = CLOUD_ENV_GOV if account_type == ACCOUNT_TYPE_GOV else "commercial"

        # Test authentication
        auth = AzureAuthenticator(tenant_id, client_id, client_secret, cloud_env)
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
# SDK Entry Point
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
