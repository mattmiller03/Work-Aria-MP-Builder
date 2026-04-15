"""Constants for the Azure Management Pack — Native Pak Compatible.

All keys match the VMware native MicrosoftAzureAdapter v8.18.0 describe.xml
so that existing dashboards and traversal specs continue to work.
"""

# ---------------------------------------------------------------------------
# Adapter identity — must match native pak adapter kind
# ---------------------------------------------------------------------------
ADAPTER_KIND = "MicrosoftAzureAdapter"
ADAPTER_NAME = "Management Pack for Microsoft Azure"

# ---------------------------------------------------------------------------
# Azure Gov endpoints
# ---------------------------------------------------------------------------
AZURE_GOV_ARM_ENDPOINT = "https://management.usgovcloudapi.net"
AZURE_GOV_AUTH_ENDPOINT = "https://login.microsoftonline.us"
AZURE_GOV_TOKEN_SCOPE = "https://management.usgovcloudapi.net/.default"

# Azure Commercial endpoints
AZURE_COM_ARM_ENDPOINT = "https://management.azure.com"
AZURE_COM_AUTH_ENDPOINT = "https://login.microsoftonline.com"
AZURE_COM_TOKEN_SCOPE = "https://management.azure.com/.default"

# Account type enum values — match native pak ACCOUNT_TYPE identifier
ACCOUNT_TYPE_GOV = "AZURE_GOV_CLOUD_ACCOUNT"
ACCOUNT_TYPE_STANDARD = "AZURE_STANDARD_ACCOUNT"

# Legacy compat aliases used by auth.py / azure_client.py
CLOUD_ENV_GOV = "government"
CLOUD_ENV_COMMERCIAL = "commercial"

# ---------------------------------------------------------------------------
# Credential kind and field keys — match native pak AZURE_CLIENT_CREDENTIALS
# ---------------------------------------------------------------------------
CREDENTIAL_TYPE = "AZURE_CLIENT_CREDENTIALS"
CREDENTIAL_CLIENT_ID = "AZURE_CLIENT_ID"
CREDENTIAL_CLIENT_SECRET = "CLIENT_SECRET"
CREDENTIAL_PROXY_HOST = "PROXY_HOST"
CREDENTIAL_PROXY_PORT = "PROXY_PORT"
CREDENTIAL_PROXY_USERNAME = "PROXY_USERNAME"
CREDENTIAL_PROXY_PASSWORD = "PROXY_PASSWORD"

# ---------------------------------------------------------------------------
# Adapter instance identifier keys — match native pak
# ---------------------------------------------------------------------------
IDENT_SUBSCRIPTION_ID = "AZURE_SUBSCRIPTION_ID"
IDENT_TENANT_ID = "AZURE_TENANT_ID"
IDENT_ACCOUNT_TYPE = "ACCOUNT_TYPE"
IDENT_SERVICES = "SERVICES"
IDENT_REGIONS = "REGIONS"
IDENT_GOV_SERVICES = "GOV_CLOUD_SERVICES"

# ---------------------------------------------------------------------------
# Resource identifier keys — every resource kind uses these 4
# ---------------------------------------------------------------------------
RES_IDENT_SUB = "AZURE_SUBSCRIPTION_ID"       # identType=1
RES_IDENT_RG = "AZURE_RESOURCE_GROUP"          # identType=2
RES_IDENT_REGION = "AZURE_REGION"              # identType=2
RES_IDENT_ID = "ID"                            # identType=1

# ---------------------------------------------------------------------------
# Object type keys — match native pak exactly (including typos)
# ---------------------------------------------------------------------------
OBJ_ADAPTER_INSTANCE = "MicrosoftAzureAdapter Instance"
OBJ_RESOURCE_GROUP = "AZURE_RESOURCE_GROUP"
OBJ_VIRTUAL_MACHINE = "AZURE_VIRTUAL_MACHINE"
OBJ_DISK = "AZURE_STORAGE_DISK"
OBJ_NETWORK_INTERFACE = "AZURE_NW_INTERFACE"
OBJ_VIRTUAL_NETWORK = "AZURE_VIRTUAL_NETWORK"
OBJ_SUBNET = "azure_subnet"  # no native equivalent — custom addition
OBJ_STORAGE_ACCOUNT = "AZURE_STORAGE_ACCOUNT"
OBJ_LOAD_BALANCER = "AZURE_LB"
OBJ_KEY_VAULT = "AZURE_KEY_VAULTS"
OBJ_SQL_SERVER = "AZURE_SQL_SERVER"
OBJ_SQL_DATABASE = "AZURE_SQL_DATABASE"
OBJ_APP_SERVICE = "AZURE_APP_SERVICE"
OBJ_HOST_GROUP = "AZURE_COMPUTE_HOSTGROUPS"
OBJ_DEDICATED_HOST = "AZURE_DEDICATE_HOST"            # native pak typo
OBJ_PUBLIC_IP = "AZURE_PUBLIC_IPADDRESSES"
OBJ_EXPRESSROUTE = "AZURE_EXPRESSROUTE_CIRCUITS"
OBJ_RECOVERY_VAULT = "azure_recovery_services_vault"   # no native equivalent
OBJ_LOG_ANALYTICS = "azure_log_analytics_workspace"     # no native equivalent
OBJ_SUBSCRIPTION = "azure_subscription"                 # no native equivalent

OBJ_POSTGRESQL = "AZURE_POSTGRESQL_SERVER"
OBJ_MYSQL = "AZURE_MYSQL_SERVER"

# Stub-only object types (native pak resource kinds we don't collect)
OBJ_COSMOS_DB = "AZURE_DB_ACCOUNT"
OBJ_KUBERNETES = "AZURE_KUBERNATE_CLUSTER"             # native pak typo
OBJ_VMSS = "AZURE_VIRTUAL_SCALESET"
OBJ_VMSS_INSTANCE = "AZURE_VIRTUAL_SCALESET_INSTANCE"
OBJ_VNET_GATEWAY = "AZURE_VIRTUAL_NETWORK_GATEWAY"
OBJ_APP_GATEWAY = "AZURE_APPLICATION_GATEWAY"
OBJ_DATA_LAKE_ANALYTICS = "AZURE_DATA_LAKE_ANALYTICS"
OBJ_COGNITIVE_SERVICES = "AZURE_COGNITIVE_SERVICES_ACCOUNTS"
OBJ_HDINSIGHT = "AZURE_HDINSIGHT"
OBJ_SYNAPSE_WORKSPACE = "AZURE_SYNAPSE_ANALYTICS_WORKSPACE"
OBJ_SYNAPSE_SQL_POOL = "AZURE_SYNAPSE_ANALYTICS_SQL_POOL"
OBJ_SYNAPSE_BIGDATA_POOL = "AZURE_SYNAPSE_ANALYTICS_BIGDATA_POOL"
OBJ_SERVICE_BUS = "AZURE_SERVICE_BUS"
OBJ_SERVICES_FROM_XML = "AZURE_SERVICES_FROM_XML"
OBJ_FUNCTIONS_APP = "AZURE_FUNCTIONS_APP"
OBJ_NETWORK_WATCHERS = "AZURE_NETWORK_WATCHERS"
OBJ_CACHE_REDIS = "AZURE_CACHE_REDIS"
OBJ_SQL_MANAGED_INSTANCE = "AZURE_SQL_MANAGEDINSTANCES"
OBJ_SQL_MANAGED_DB = "AZURE_SQL_MANAGEDINSTANCES_DATABASE"
OBJ_MARIADB = "AZURE_MARIADB_SERVER"
OBJ_MARIADB_DB = "AZURE_MARIA_DBSERVER_DATABASE"
OBJ_COMPUTE_DOMAINS = "AZURE_COMPUTE_DOMAINNAMES"
OBJ_BATCH_ACCOUNT = "AZURE_BATCH_ACCOUNT"
OBJ_CONTAINER_GROUPS = "AZURE_CONTIANER_CONTAINERGROUPS"  # native pak typo
OBJ_CONTAINER = "AZURE_CONTAINER"
OBJ_CONTAINER_REGISTRIES = "AZURE_CONTAINER_REGISTRIES"
OBJ_DATALAKE_STORE = "AZURE_DATALAKE_STORE"
OBJ_APP_CONFIGURATION = "AZURE_APP_CONFIGURATION"
OBJ_OPENSHIFT = "AZURE_OPENSHIFT_CLUSTERS"
OBJ_ROUTE_TABLES = "AZURE_ROUTE_TABLES"
OBJ_PRIVATE_DNS = "AZURE_PRIVATE_DNSZONES"
OBJ_DNS_ZONES = "AZURE_DNS_ZONES"
OBJ_TRAFFIC_MANAGER = "AZURE_TRAFFIC_MANAGER_PROFILES"
OBJ_SIGNALR = "AZURE_SIGNALR_SERVICES"
OBJ_FIREWALLS = "AZURE_FIREWALLS"
OBJ_FRONT_DOORS = "AZURE_FRONT_DOORS"
OBJ_CDN_PROFILES = "AZURE_CDN_PROFILES"
OBJ_CDN_ENDPOINTS = "AZURE_CDN_PROFILES_ENDPOINTS"
OBJ_VIRTUAL_WAN = "AZURE_VIRTUAL_WAN"
OBJ_VIRTUAL_HUBS = "AZURE_VIRTUAL_HUBS"
OBJ_NETAPP_ACCOUNT = "AZURE_NETAPPACCOUNT"
OBJ_NETAPP_POOLS = "AZURE_NETAPPACCOUNT_CAPACITYPOOLS"
OBJ_NETAPP_VOLUMES = "AZURE_NETAPPACCOUNT_CAPACITYPOOLS_VOLUMES"
OBJ_MEDIA_SERVICES = "AZURE_MEDIA_SERVICES"
OBJ_MEDIA_LIVE_EVENTS = "AZURE_MEDIASERVICES_LIVEEVENTS"
OBJ_MEDIA_STREAMING = "AZURE_MEDIASERVICES_STREAMINGEP"
OBJ_NOTIFICATION_HUBS = "AZURE_NH_NAMESPACES_NOTIFICATIONHUBS"
OBJ_NOTIFICATION_NS = "AZURE_NOTIFICATIONHUBS_NAMESPACES"
OBJ_EVENTHUBS_NS = "AZURE_EVENTHUBS_NAMESPACES"
OBJ_EVENT_HUBS = "AZURE_EVENT_HUBS"
OBJ_DATA_EXPLORER_CLUSTER = "AZURE_DATA_EXPLORER_CLUSTER"
OBJ_DATA_EXPLORER_DB = "AZURE_DATA_EXPLORER_DATABASE"
OBJ_DATA_FACTORY = "AZURE_DATA_FACTORY"
OBJ_SEARCH_SERVICES = "AZURE_SEARCH_SERVICES"
OBJ_MACHINE_LEARNING = "AZURE_MACHINE_LEARNING"
OBJ_STREAM_ANALYTICS_JOBS = "AZURE_STREAM_ANALYTICS_JOBS"
OBJ_STREAM_ANALYTICS_CLUSTERS = "AZURE_STREAM_ANALYTICS_CLUSTERS"
OBJ_PURVIEW = "AZURE_PURVIEW_ACCOUNTS"
OBJ_BOT_SERVICES = "AZURE_BOT_SERVICES"
OBJ_ANALYSIS_SERVICES = "AZURE_ANALYSIS_SERVICES"
OBJ_POWER_BI = "AZURE_POWER_BI_EMBEDDED"
OBJ_NSG = "AZURE_NETWORK_SECURITY_GROUP"
OBJ_APP_SERVICE_PLAN = "AZURE_APP_SERVICE_PLAN"
OBJ_AVAILABILITY_SETS = "AZURE_AVAILABILITY_SETS"
OBJ_PROXIMITY_GROUP = "AZURE_PROXIMITY_PLACEMENT_GROUP"
OBJ_DIGITAL_TWINS = "AZURE_DIGITAL_TWINS"
OBJ_API_MANAGEMENT = "AZURE_API_MANAGEMENT"
OBJ_DDOS_PROTECTION = "AZURE_DDOS_PROTECTION_PLAN"
OBJ_IOT_CENTRAL = "AZURE_IOT_CENTRAL"
OBJ_IOT_HUB = "AZURE_IOT_HUB"
OBJ_TIME_SERIES = "AZURE_TIME_SERIES_INSIGHTS"
OBJ_EVENT_GRID_DOMAIN = "AZURE_EVENT_GRID_DOMAIN"
OBJ_EVENT_GRID_TOPIC = "AZURE_EVENT_GRID_TOPIC"
OBJ_EVENT_GRID_SUB = "AZURE_EVENT_GRID_SUBSCRIPTION"
OBJ_DATA_BOX = "AZURE_DATA_BOX"
OBJ_SPATIAL_ANCHORS = "AZURE_SPATIAL_ANCHORS"
OBJ_AUTOMATION = "AZURE_AUTOMATION"
OBJ_REGION_PER_SUB = "AZURE_REGION_PER_SUB"
OBJ_REGION = "AZURE_REGION"
OBJ_WORLD = "AZURE_WORLD"

# Complete list of all native pak resource kinds (for stub generation)
ALL_NATIVE_STUB_KINDS = [
    OBJ_KUBERNETES,
    OBJ_VMSS, OBJ_VMSS_INSTANCE, OBJ_VNET_GATEWAY, OBJ_APP_GATEWAY,
    OBJ_DATA_LAKE_ANALYTICS, OBJ_COGNITIVE_SERVICES, OBJ_HDINSIGHT,
    OBJ_SYNAPSE_WORKSPACE, OBJ_SYNAPSE_SQL_POOL, OBJ_SYNAPSE_BIGDATA_POOL,
    OBJ_SERVICE_BUS, OBJ_NETWORK_WATCHERS,
    OBJ_CACHE_REDIS, OBJ_SQL_MANAGED_INSTANCE, OBJ_SQL_MANAGED_DB,
    OBJ_MARIADB, OBJ_MARIADB_DB, OBJ_COMPUTE_DOMAINS, OBJ_BATCH_ACCOUNT,
    OBJ_CONTAINER_GROUPS, OBJ_CONTAINER, OBJ_CONTAINER_REGISTRIES,
    OBJ_DATALAKE_STORE, OBJ_APP_CONFIGURATION, OBJ_OPENSHIFT,
    OBJ_ROUTE_TABLES, OBJ_PRIVATE_DNS, OBJ_DNS_ZONES,
    OBJ_TRAFFIC_MANAGER, OBJ_SIGNALR, OBJ_FIREWALLS, OBJ_FRONT_DOORS,
    OBJ_CDN_PROFILES, OBJ_CDN_ENDPOINTS, OBJ_VIRTUAL_WAN, OBJ_VIRTUAL_HUBS,
    OBJ_NETAPP_ACCOUNT, OBJ_NETAPP_POOLS, OBJ_NETAPP_VOLUMES,
    OBJ_MEDIA_SERVICES, OBJ_MEDIA_LIVE_EVENTS, OBJ_MEDIA_STREAMING,
    OBJ_NOTIFICATION_HUBS, OBJ_NOTIFICATION_NS, OBJ_EVENTHUBS_NS,
    OBJ_EVENT_HUBS, OBJ_DATA_EXPLORER_CLUSTER, OBJ_DATA_EXPLORER_DB,
    OBJ_DATA_FACTORY, OBJ_SEARCH_SERVICES, OBJ_MACHINE_LEARNING,
    OBJ_STREAM_ANALYTICS_JOBS, OBJ_STREAM_ANALYTICS_CLUSTERS,
    OBJ_PURVIEW, OBJ_BOT_SERVICES, OBJ_ANALYSIS_SERVICES, OBJ_POWER_BI,
    OBJ_NSG, OBJ_AVAILABILITY_SETS,
    OBJ_PROXIMITY_GROUP, OBJ_DIGITAL_TWINS, OBJ_API_MANAGEMENT,
    OBJ_DDOS_PROTECTION, OBJ_IOT_CENTRAL, OBJ_IOT_HUB, OBJ_TIME_SERIES,
    OBJ_EVENT_GRID_DOMAIN, OBJ_EVENT_GRID_TOPIC, OBJ_EVENT_GRID_SUB,
    OBJ_DATA_BOX, OBJ_SPATIAL_ANCHORS, OBJ_AUTOMATION,
]

# ---------------------------------------------------------------------------
# API versions — use versions confirmed available in Azure Gov
# ---------------------------------------------------------------------------
API_VERSIONS = {
    "subscriptions": "2022-12-01",
    "resource_groups": "2021-04-01",
    "virtual_machines": "2023-03-01",
    "disks": "2023-04-02",
    "network_interfaces": "2023-05-01",
    "virtual_networks": "2023-05-01",
    "storage_accounts": "2023-01-01",
    "load_balancers": "2023-05-01",
    "key_vaults": "2023-02-01",
    "sql_servers": "2023-05-01-preview",
    "sql_databases": "2023-05-01-preview",
    "web_apps": "2023-01-01",
    "app_service_plans": "2023-01-01",
    "cosmos_db": "2023-04-15",
    "host_groups": "2023-03-01",
    "dedicated_hosts": "2023-03-01",
    "public_ips": "2023-05-01",
    "expressroute": "2023-05-01",
    "recovery_vaults": "2023-01-01",
    "log_analytics": "2023-09-01",
    "cost_management": "2023-03-01",
    "monitor_metrics": "2023-10-01",
    "postgresql_servers": "2022-12-01",
    "mysql_servers": "2023-06-30",
}

# ---------------------------------------------------------------------------
# Azure Monitor metric definitions — keys match native pak describe.xml
# ---------------------------------------------------------------------------
MONITOR_METRICS = {
    "virtual_machines": [
        # Native pak: CPU group
        ("Percentage CPU", "CPU|CPU_USAGE", "Average"),
        ("CPU Credits Remaining", "CPU|CPU_CRED_REMAINING", "Average"),
        ("CPU Credits Consumed", "CPU|CPU_CRED_CONSUMED", "Average"),
        # Native pak: STORAGE group
        ("Disk Read Bytes", "STORAGE|DATA_READ_DISK", "Total"),
        ("Disk Write Bytes", "STORAGE|DATA_WRITE_DISK", "Total"),
        ("Disk Read Operations/Sec", "STORAGE|DISK_READ_OPERATION", "Average"),
        ("Disk Write Operations/Sec", "STORAGE|DISK_WRITE_OPERATION", "Average"),
        # Native pak: NETWORK group
        ("Network In Total", "NETWORK|NETWORK_IN", "Total"),
        ("Network Out Total", "NETWORK|NETWORK_OUT", "Total"),
        # Custom: Memory metrics (requires Azure Monitor Agent or diagnostics extension)
        ("Available Memory Bytes", "MEMORY|AVAILABLE_MEMORY_BYTES", "Average"),
    ],
    "network_interfaces": [
        # Native pak: flat metrics (no group prefix)
        ("BytesSentRate", "BYTES_SENT", "Total"),
        ("BytesReceivedRate", "BYTES_RECEIVED", "Total"),
        ("PacketsSentRate", "PACK_SENT", "Total"),
        ("PacketsReceivedRate", "PACK_RECEIVED", "Total"),
    ],
    "load_balancers": [
        # Native pak: flat metrics (no group prefix)
        ("VipAvailability", "DATA_PATH_AVAILABLITY", "Average"),
        ("DipAvailability", "HEALTH_PROBE_STATUS", "Average"),
        ("ByteCount", "BYTE_COUNT", "Total"),
        ("PacketCount", "PACKET_COUNT", "Total"),
    ],
    "sql_databases": [
        # Native pak: CPU group
        ("cpu_percent", "CPU|CPU_USAGE", "Average"),
        # Native pak: STORAGE group
        ("physical_data_read_percent", "STORAGE|DATA_IO", "Average"),
        ("storage", "STORAGE|DATABASE_SIZE", "Maximum"),
        ("xtp_storage_percent", "STORAGE|IN_MEM_OLTP_STORAGE", "Average"),
        # Native pak: WORKLOAD group
        ("log_write_percent", "WORKLOAD|LOG_IO", "Average"),
        ("sessions_percent", "WORKLOAD|CON_SESSION", "Average"),
        ("workers_percent", "WORKLOAD|CON_WORKER", "Average"),
        ("dtu_used", "WORKLOAD|DTU_USED", "Average"),
        # Native pak: flat metrics
        ("dtu_consumption_percent", "DTU_PERCENTAGE", "Average"),
        ("connection_successful", "SUCCESSFUL_CONNECTIONS", "Total"),
        ("connection_failed", "FAILED_CONNECTIONS", "Total"),
        ("blocked_by_firewall", "BLOCKED_BY_FIREWALL", "Total"),
        ("deadlock", "DEADLOCKS", "Total"),
        ("storage_percent", "DATA_SPACE_USED_PERCENT", "Average"),
        ("dtu_limit", "DTU_LIMIT", "Average"),
        ("cpu_limit", "CPU_LIMIT", "Average"),
        ("cpu_used", "CPU_USED", "Average"),
        ("dwu_limit", "DWU_LIMIT", "Average"),
        ("dwu_consumption_percent", "DWU_PERCENTAGE", "Average"),
        ("dwu_used", "DWU_USED", "Average"),
    ],
    "sql_servers": [
        ("cpu_percent", "CPU|CPU_USAGE", "Average"),
        ("physical_data_read_percent", "STORAGE|DATA_IO", "Average"),
        ("storage", "STORAGE|DATABASE_SIZE", "Maximum"),
        ("xtp_storage_percent", "STORAGE|IN_MEM_OLTP_STORAGE", "Average"),
        ("log_write_percent", "WORKLOAD|LOG_IO", "Average"),
        ("sessions_percent", "WORKLOAD|CON_SESSION", "Average"),
        ("workers_percent", "WORKLOAD|CON_WORKER", "Average"),
        ("dtu_used", "WORKLOAD|DTU_USED", "Average"),
    ],
    "storage_accounts": [
        # Native pak: summary group
        ("UsedCapacity", "summary|usedCapacity", "Average"),
        ("Transactions", "summary|transactions", "Total"),
        ("Ingress", "summary|ingress", "Total"),
        ("Egress", "summary|egress", "Total"),
        ("SuccessServerLatency", "summary|successServerLatency", "Average"),
        ("SuccessE2ELatency", "summary|successE2ELatency", "Average"),
        ("Availability", "summary|availability", "Average"),
    ],
    "postgresql_servers": [
        # Native pak: flat metrics (no group prefix)
        ("cpu_percent", "CPU_PERCENT", "Average"),
        ("memory_percent", "MEMORY_PERCENT", "Average"),
        ("io_consumption_percent", "IO_PERCENT", "Average"),
        ("storage_percent", "STORAGE_PERCENT", "Average"),
        ("storage_used", "STORAGE_USED", "Average"),
        ("storage_limit", "STORAGE_LIMIT", "Maximum"),
        ("serverlog_storage_percent", "SERVER_LOG_STORAGE_PERCENT", "Average"),
        ("serverlog_storage_usage", "SERVER_LOG_STORAGE_USED", "Average"),
        ("serverlog_storage_limit", "SERVER_LOG_STORAGE_LIMIT", "Maximum"),
        ("active_connections", "ACTIVE_CONNECTIONS", "Average"),
        ("connections_failed", "FAILED_CONNECTIONS", "Total"),
        ("backup_storage_used", "BACKUP_STORAGE_USED", "Average"),
        ("network_bytes_egress", "NETWORK_OUT", "Total"),
        ("network_bytes_ingress", "NETWORK_IN", "Total"),
        ("pg_replica_log_delay_in_seconds", "REPLICA_LAG", "Maximum"),
        ("pg_replica_log_delay_in_bytes", "MAX_LAG_ACROSS_REPLICAS", "Maximum"),
    ],
    "mysql_servers": [
        # Native pak: flat metrics (no group prefix)
        ("cpu_percent", "CPU_PERCENT", "Average"),
        ("memory_percent", "MEMORY_PERCENT", "Average"),
        ("io_consumption_percent", "IO_PERCENT", "Average"),
        ("storage_percent", "STORAGE_PERCENT", "Average"),
        ("storage_used", "STORAGE_USED", "Average"),
        ("storage_limit", "STORAGE_LIMIT", "Maximum"),
        ("serverlog_storage_percent", "SERVER_LOG_STORAGE_PERCENT", "Average"),
        ("serverlog_storage_usage", "SERVER_LOG_STORAGE_USED", "Average"),
        ("serverlog_storage_limit", "SERVER_LOG_STORAGE_LIMIT", "Maximum"),
        ("active_connections", "ACTIVE_CONNECTIONS", "Average"),
        ("connections_failed", "FAILED_CONNECTIONS", "Total"),
        ("seconds_behind_master", "REPLICATION_LAG_IN_SECONDS", "Maximum"),
        ("backup_storage_used", "BACKUP_STORAGE_USED", "Average"),
        ("network_bytes_egress", "NETWORK_OUT", "Total"),
        ("network_bytes_ingress", "NETWORK_IN", "Total"),
    ],
    "cosmos_db": [
        # Native pak: flat metrics (no group prefix)
        ("AvailableStorage", "AVAIL_STORAGE", "Total"),
        ("DataUsage", "DATA_USAGE", "Total"),
        ("IndexUsage", "INDEX_USAGE", "Total"),
        ("DocumentQuota", "DOC_QUOTA", "Maximum"),
        ("DocumentCount", "DOC_COUNT", "Total"),
    ],
}

# ---------------------------------------------------------------------------
# SERVICE_DESCRIPTORS property keys — included on every resource
# ---------------------------------------------------------------------------
SD_SUBSCRIPTION = "SERVICE_DESCRIPTORS|AZURE_SUBSCRIPTION_ID"
SD_RESOURCE_GROUP = "SERVICE_DESCRIPTORS|AZURE_RESOURCE_GROUP"
SD_REGION = "SERVICE_DESCRIPTORS|AZURE_REGION"
SD_SERVICE = "SERVICE_DESCRIPTORS|AZURE_SERVICE"

# Azure service name mapping for SERVICE_DESCRIPTORS|AZURE_SERVICE
AZURE_SERVICE_NAMES = {
    OBJ_VIRTUAL_MACHINE: "Microsoft.Compute/virtualMachines",
    OBJ_DISK: "Microsoft.Compute/disks",
    OBJ_NETWORK_INTERFACE: "Microsoft.Network/networkInterfaces",
    OBJ_VIRTUAL_NETWORK: "Microsoft.Network/virtualNetworks",
    OBJ_STORAGE_ACCOUNT: "Microsoft.Storage/storageAccounts",
    OBJ_LOAD_BALANCER: "Microsoft.Network/loadBalancers",
    OBJ_KEY_VAULT: "Microsoft.KeyVault/vaults",
    OBJ_SQL_SERVER: "Microsoft.Sql/servers",
    OBJ_SQL_DATABASE: "Microsoft.Sql/servers/databases",
    OBJ_APP_SERVICE: "Microsoft.Web/sites",
    OBJ_HOST_GROUP: "Microsoft.Compute/hostGroups",
    OBJ_DEDICATED_HOST: "Microsoft.Compute/hostGroups/hosts",
    OBJ_PUBLIC_IP: "Microsoft.Network/publicIPAddresses",
    OBJ_EXPRESSROUTE: "Microsoft.Network/expressRouteCircuits",
    OBJ_RESOURCE_GROUP: "Microsoft.Resources/resourceGroups",
    OBJ_POSTGRESQL: "Microsoft.DBforPostgreSQL/servers",
    OBJ_MYSQL: "Microsoft.DBforMySQL/servers",
    OBJ_COSMOS_DB: "Microsoft.DocumentDB/databaseAccounts",
    OBJ_FUNCTIONS_APP: "Microsoft.Web/sites",
    OBJ_APP_SERVICE_PLAN: "Microsoft.Web/serverfarms",
}
