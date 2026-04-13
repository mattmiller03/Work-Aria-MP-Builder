"""Constants for the Azure Gov Management Pack."""

# Adapter identity
ADAPTER_KIND = "AzureGovAdapter"
ADAPTER_NAME = "Azure Government Cloud"

# Azure Gov endpoints
AZURE_GOV_ARM_ENDPOINT = "https://management.usgovcloudapi.net"
AZURE_GOV_AUTH_ENDPOINT = "https://login.microsoftonline.us"
AZURE_GOV_TOKEN_SCOPE = "https://management.usgovcloudapi.net/.default"

# Azure Commercial endpoints (for potential future use)
AZURE_COM_ARM_ENDPOINT = "https://management.azure.com"
AZURE_COM_AUTH_ENDPOINT = "https://login.microsoftonline.com"
AZURE_COM_TOKEN_SCOPE = "https://management.azure.com/.default"

# Credential keys
CREDENTIAL_TYPE = "azure_gov_credential"
CREDENTIAL_TENANT_ID = "tenant_id"
CREDENTIAL_CLIENT_ID = "client_id"
CREDENTIAL_CLIENT_SECRET = "client_secret"
CREDENTIAL_SUBSCRIPTION_ID = "subscription_id"

# Configuration keys
CONFIG_CLOUD_ENVIRONMENT = "cloud_environment"
CLOUD_ENV_GOV = "government"
CLOUD_ENV_COMMERCIAL = "commercial"

# Object type keys
OBJ_SUBSCRIPTION = "azure_subscription"
OBJ_RESOURCE_GROUP = "azure_resource_group"
OBJ_VIRTUAL_MACHINE = "azure_virtual_machine"
OBJ_DISK = "azure_disk"
OBJ_NETWORK_INTERFACE = "azure_network_interface"
OBJ_VIRTUAL_NETWORK = "azure_virtual_network"
OBJ_SUBNET = "azure_subnet"
OBJ_STORAGE_ACCOUNT = "azure_storage_account"
OBJ_LOAD_BALANCER = "azure_load_balancer"
OBJ_KEY_VAULT = "azure_key_vault"
OBJ_SQL_SERVER = "azure_sql_server"
OBJ_SQL_DATABASE = "azure_sql_database"
OBJ_APP_SERVICE = "azure_app_service"
OBJ_HOST_GROUP = "azure_host_group"
OBJ_DEDICATED_HOST = "azure_dedicated_host"
OBJ_PUBLIC_IP = "azure_public_ip"
OBJ_EXPRESSROUTE = "azure_expressroute_circuit"
OBJ_RECOVERY_VAULT = "azure_recovery_services_vault"
OBJ_LOG_ANALYTICS = "azure_log_analytics_workspace"

# API versions — use versions confirmed available in Azure Gov
# These may lag behind commercial Azure; fall back if needed
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
    "host_groups": "2023-03-01",
    "dedicated_hosts": "2023-03-01",
    "public_ips": "2023-05-01",
    "expressroute": "2023-05-01",
    "recovery_vaults": "2023-01-01",
    "log_analytics": "2023-09-01",
    "cost_management": "2023-03-01",
    "monitor_metrics": "2023-10-01",
}

# Azure Monitor metric definitions per resource type
# Each entry maps a resource type key to a list of (metric_name, aria_key, aggregation) tuples
# metric_name: Azure Monitor metric name
# aria_key: key used in Aria Ops (obj.with_metric)
# aggregation: Azure aggregation type (Average, Total, Count, Maximum, Minimum)
MONITOR_METRICS = {
    "virtual_machines": [
        ("Percentage CPU", "cpu_percent", "Average"),
        ("Disk Read Bytes", "disk_read_bytes", "Total"),
        ("Disk Write Bytes", "disk_write_bytes", "Total"),
        ("Disk Read Operations/Sec", "disk_read_ops_per_sec", "Average"),
        ("Disk Write Operations/Sec", "disk_write_ops_per_sec", "Average"),
        ("Network In Total", "network_in_bytes", "Total"),
        ("Network Out Total", "network_out_bytes", "Total"),
    ],
    "network_interfaces": [
        ("BytesSentRate", "bytes_sent", "Total"),
        ("BytesReceivedRate", "bytes_received", "Total"),
        ("PacketsSentRate", "packets_sent", "Total"),
        ("PacketsReceivedRate", "packets_received", "Total"),
    ],
    "load_balancers": [
        ("VipAvailability", "data_path_availability", "Average"),
        ("DipAvailability", "health_probe_status", "Average"),
        ("ByteCount", "byte_count", "Total"),
        ("PacketCount", "packet_count", "Total"),
    ],
    "sql_databases": [
        ("cpu_percent", "cpu_percent", "Average"),
        ("dtu_consumption_percent", "dtu_percent", "Average"),
        ("physical_data_read_percent", "data_io_percent", "Average"),
        ("log_write_percent", "log_io_percent", "Average"),
        ("storage_percent", "storage_percent", "Average"),
        ("connection_successful", "successful_connections", "Total"),
        ("connection_failed", "failed_connections", "Total"),
        ("deadlock", "deadlocks", "Total"),
        ("workers_percent", "workers_percent", "Average"),
        ("sessions_percent", "sessions_percent", "Average"),
    ],
    "storage_accounts": [
        ("UsedCapacity", "used_capacity_bytes", "Average"),
        ("Transactions", "transactions", "Total"),
        ("Ingress", "ingress_bytes", "Total"),
        ("Egress", "egress_bytes", "Total"),
        ("Availability", "availability_percent", "Average"),
        ("SuccessE2ELatency", "e2e_latency_ms", "Average"),
        ("SuccessServerLatency", "server_latency_ms", "Average"),
    ],
}
