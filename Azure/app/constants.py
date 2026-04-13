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
# Each entry maps a resource type key to a list of (azure_metric, aria_key, aggregation)
# aria_key uses "Group|metric" pattern matching native Azure management pack convention
# aggregation: Azure Monitor aggregation (Average, Total, Count, Maximum, Minimum)
MONITOR_METRICS = {
    "virtual_machines": [
        ("Percentage CPU", "CPU|cpu_usage", "Average"),
        ("Disk Read Bytes", "Disk|disk_read_bytes", "Total"),
        ("Disk Write Bytes", "Disk|disk_write_bytes", "Total"),
        ("Disk Read Operations/Sec", "Disk|disk_read_operations", "Average"),
        ("Disk Write Operations/Sec", "Disk|disk_write_operations", "Average"),
        ("Network In Total", "Network|network_in", "Total"),
        ("Network Out Total", "Network|network_out", "Total"),
    ],
    "network_interfaces": [
        ("BytesSentRate", "Network|bytes_sent", "Total"),
        ("BytesReceivedRate", "Network|bytes_received", "Total"),
        ("PacketsSentRate", "Network|packets_sent", "Total"),
        ("PacketsReceivedRate", "Network|packets_received", "Total"),
    ],
    "load_balancers": [
        ("VipAvailability", "Availability|data_path_availability", "Average"),
        ("DipAvailability", "Availability|health_probe_status", "Average"),
        ("Network|byte_count", "Network|byte_count", "Total"),
        ("PacketCount", "Network|packet_count", "Total"),
    ],
    "sql_databases": [
        ("cpu_percent", "CPU|cpu_usage", "Average"),
        ("dtu_consumption_percent", "Workload|dtu_consumption", "Average"),
        ("physical_data_read_percent", "Storage|data_io", "Average"),
        ("log_write_percent", "Storage|log_io", "Average"),
        ("storage_percent", "Storage|storage_usage", "Average"),
        ("storage", "Storage|database_size", "Maximum"),
        ("dtu_limit", "Workload|dtu_limit", "Average"),
        ("dtu_used", "Workload|dtu_used", "Average"),
        ("connection_successful", "Network|successful_connections", "Total"),
        ("connection_failed", "Network|failed_connections", "Total"),
        ("blocked_by_firewall", "Network|blocked_by_firewall", "Total"),
        ("deadlock", "Network|deadlocks", "Total"),
        ("workers_percent", "Workload|workers", "Average"),
        ("sessions_percent", "Workload|sessions", "Average"),
        ("xtp_storage_percent", "Storage|xtp_storage", "Average"),
    ],
    "sql_servers": [
        ("cpu_percent", "CPU|cpu_usage", "Average"),
        ("physical_data_read_percent", "Storage|data_io", "Average"),
        ("storage_percent", "Storage|xtp_storage", "Average"),
        ("dtu_used", "Workload|dtu_used", "Average"),
        ("workers_percent", "Workload|workers", "Average"),
        ("sessions_percent", "Workload|sessions", "Average"),
    ],
    "storage_accounts": [
        ("UsedCapacity", "Storage|used_capacity", "Average"),
        ("Transactions", "Storage|transactions", "Total"),
        ("Ingress", "Network|ingress", "Total"),
        ("Egress", "Network|egress", "Total"),
        ("Availability", "Availability|availability", "Average"),
        ("SuccessE2ELatency", "Latency|e2e_latency", "Average"),
        ("SuccessServerLatency", "Latency|server_latency", "Average"),
    ],
}
