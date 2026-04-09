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
}
