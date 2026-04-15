"""Bulk collector for all remaining Azure resource types.

Uses the generic ARM collector to collect resources that follow the standard
ARM list pattern. Each entry defines the resource kind, ARM provider path,
API version, and optional type-specific property extractor.
"""

import logging

from azure_client import AzureClient
from collectors.generic_arm import collect_generic_arm_resources
from helpers import safe_property

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Type-specific property extractors
# ---------------------------------------------------------------------------

def _nsg_props(obj, resource, props):
    """Network Security Group extra properties."""
    rules = props.get("securityRules", [])
    safe_property(obj, "security_rule_count", len(rules))
    default_rules = props.get("defaultSecurityRules", [])
    safe_property(obj, "default_rule_count", len(default_rules))
    nics = props.get("networkInterfaces", [])
    safe_property(obj, "attached_nic_count", len(nics))
    subnets = props.get("subnets", [])
    safe_property(obj, "attached_subnet_count", len(subnets))


def _route_table_props(obj, resource, props):
    """Route Table extra properties."""
    routes = props.get("routes", [])
    safe_property(obj, "route_count", len(routes))
    safe_property(obj, "disable_bgp_route_propagation",
                  str(props.get("disableBgpRoutePropagation", "")))


def _dns_zone_props(obj, resource, props):
    """DNS Zone extra properties."""
    safe_property(obj, "zone_type", props.get("zoneType", ""))
    safe_property(obj, "number_of_record_sets",
                  props.get("numberOfRecordSets", 0))
    safe_property(obj, "max_number_of_record_sets",
                  props.get("maxNumberOfRecordSets", 0))
    name_servers = props.get("nameServers", [])
    safe_property(obj, "name_servers", ", ".join(name_servers))


def _firewall_props(obj, resource, props):
    """Azure Firewall extra properties."""
    safe_property(obj, "threat_intel_mode",
                  props.get("threatIntelMode", ""))
    safe_property(obj, "sku_name",
                  props.get("sku", {}).get("name", ""))
    safe_property(obj, "sku_tier",
                  props.get("sku", {}).get("tier", ""))
    ip_configs = props.get("ipConfigurations", [])
    safe_property(obj, "ip_configuration_count", len(ip_configs))
    nat_rules = props.get("natRuleCollections", [])
    safe_property(obj, "nat_rule_collection_count", len(nat_rules))
    net_rules = props.get("networkRuleCollections", [])
    safe_property(obj, "network_rule_collection_count", len(net_rules))
    app_rules = props.get("applicationRuleCollections", [])
    safe_property(obj, "application_rule_collection_count", len(app_rules))


def _vnet_gateway_props(obj, resource, props):
    """Virtual Network Gateway extra properties."""
    safe_property(obj, "gateway_type", props.get("gatewayType", ""))
    safe_property(obj, "vpn_type", props.get("vpnType", ""))
    safe_property(obj, "active_active",
                  str(props.get("activeActive", "")))
    safe_property(obj, "enable_bgp",
                  str(props.get("enableBgp", "")))
    sku = props.get("sku", {})
    safe_property(obj, "gateway_sku_name", sku.get("name", ""))
    safe_property(obj, "gateway_sku_tier", sku.get("tier", ""))
    safe_property(obj, "gateway_sku_capacity", sku.get("capacity", ""))
    ip_configs = props.get("ipConfigurations", [])
    safe_property(obj, "ip_configuration_count", len(ip_configs))
    safe_property(obj, "vpn_gateway_generation",
                  props.get("vpnGatewayGeneration", ""))


def _app_gateway_props(obj, resource, props):
    """Application Gateway extra properties."""
    sku = props.get("sku", {})
    safe_property(obj, "app_gw_sku_name", sku.get("name", ""))
    safe_property(obj, "app_gw_sku_tier", sku.get("tier", ""))
    safe_property(obj, "app_gw_sku_capacity", sku.get("capacity", ""))
    safe_property(obj, "operational_state",
                  props.get("operationalState", ""))
    backend_pools = props.get("backendAddressPools", [])
    safe_property(obj, "backend_pool_count", len(backend_pools))
    http_listeners = props.get("httpListeners", [])
    safe_property(obj, "http_listener_count", len(http_listeners))
    rules = props.get("requestRoutingRules", [])
    safe_property(obj, "routing_rule_count", len(rules))
    probes = props.get("probes", [])
    safe_property(obj, "probe_count", len(probes))
    safe_property(obj, "enable_http2",
                  str(props.get("enableHttp2", "")))
    waf = props.get("webApplicationFirewallConfiguration", {})
    if waf:
        safe_property(obj, "waf_enabled", str(waf.get("enabled", "")))
        safe_property(obj, "waf_mode", waf.get("firewallMode", ""))


def _k8s_props(obj, resource, props):
    """Kubernetes (AKS) cluster extra properties."""
    safe_property(obj, "kubernetes_version",
                  props.get("kubernetesVersion", ""))
    safe_property(obj, "dns_prefix", props.get("dnsPrefix", ""))
    safe_property(obj, "fqdn", props.get("fqdn", ""))
    safe_property(obj, "enable_rbac",
                  str(props.get("enableRBAC", "")))
    safe_property(obj, "power_state",
                  props.get("powerState", {}).get("code", ""))
    agent_pools = props.get("agentPoolProfiles", [])
    safe_property(obj, "agent_pool_count", len(agent_pools))
    total_nodes = sum(p.get("count", 0) for p in agent_pools)
    safe_property(obj, "total_node_count", total_nodes)
    pool_names = [p.get("name", "") for p in agent_pools]
    safe_property(obj, "agent_pool_names", ", ".join(pool_names))
    network_profile = props.get("networkProfile", {})
    safe_property(obj, "network_plugin",
                  network_profile.get("networkPlugin", ""))
    safe_property(obj, "service_cidr",
                  network_profile.get("serviceCidr", ""))
    safe_property(obj, "dns_service_ip",
                  network_profile.get("dnsServiceIP", ""))


def _container_registry_props(obj, resource, props):
    """Container Registry extra properties."""
    safe_property(obj, "login_server", props.get("loginServer", ""))
    safe_property(obj, "admin_user_enabled",
                  str(props.get("adminUserEnabled", "")))
    safe_property(obj, "creation_date", props.get("creationDate", ""))
    safe_property(obj, "status",
                  props.get("status", {}).get("displayStatus", ""))
    safe_property(obj, "data_endpoint_enabled",
                  str(props.get("dataEndpointEnabled", "")))
    safe_property(obj, "public_network_access",
                  props.get("publicNetworkAccess", ""))
    safe_property(obj, "zone_redundancy",
                  props.get("zoneRedundancy", ""))
    policies = props.get("policies", {})
    safe_property(obj, "quarantine_policy",
                  str(policies.get("quarantinePolicy", {}).get("status", "")))
    safe_property(obj, "retention_days",
                  policies.get("retentionPolicy", {}).get("days", ""))


def _redis_props(obj, resource, props):
    """Redis Cache extra properties."""
    safe_property(obj, "redis_version", props.get("redisVersion", ""))
    safe_property(obj, "host_name", props.get("hostName", ""))
    safe_property(obj, "port", props.get("port", ""))
    safe_property(obj, "ssl_port", props.get("sslPort", ""))
    safe_property(obj, "linked_servers_count",
                  len(props.get("linkedServers", [])))
    safe_property(obj, "max_memory_policy",
                  props.get("redisConfiguration", {}).get(
                      "maxmemory-policy", ""))
    safe_property(obj, "enable_non_ssl_port",
                  str(props.get("enableNonSslPort", "")))
    safe_property(obj, "minimum_tls_version",
                  props.get("minimumTlsVersion", ""))
    safe_property(obj, "public_network_access",
                  props.get("publicNetworkAccess", ""))
    safe_property(obj, "replicas_per_master",
                  props.get("replicasPerMaster", ""))


def _service_bus_props(obj, resource, props):
    """Service Bus Namespace extra properties."""
    safe_property(obj, "status", props.get("status", ""))
    safe_property(obj, "metric_id", props.get("metricId", ""))
    safe_property(obj, "service_bus_endpoint",
                  props.get("serviceBusEndpoint", ""))
    safe_property(obj, "zone_redundant",
                  str(props.get("zoneRedundant", "")))
    safe_property(obj, "disable_local_auth",
                  str(props.get("disableLocalAuth", "")))


def _automation_props(obj, resource, props):
    """Automation Account extra properties."""
    safe_property(obj, "state", props.get("state", ""))
    safe_property(obj, "creation_time", props.get("creationTime", ""))
    safe_property(obj, "last_modified_time", props.get("lastModifiedTime", ""))
    safe_property(obj, "public_network_access",
                  str(props.get("publicNetworkAccess", "")))
    safe_property(obj, "disable_local_auth",
                  str(props.get("disableLocalAuth", "")))


def _api_management_props(obj, resource, props):
    """API Management extra properties."""
    safe_property(obj, "publisher_email", props.get("publisherEmail", ""))
    safe_property(obj, "publisher_name", props.get("publisherName", ""))
    safe_property(obj, "gateway_url", props.get("gatewayUrl", ""))
    safe_property(obj, "portal_url", props.get("portalUrl", ""))
    safe_property(obj, "management_api_url",
                  props.get("managementApiUrl", ""))
    safe_property(obj, "developer_portal_url",
                  props.get("developerPortalUrl", ""))
    safe_property(obj, "virtual_network_type",
                  props.get("virtualNetworkType", ""))
    safe_property(obj, "platform_version",
                  props.get("platformVersion", ""))


def _data_factory_props(obj, resource, props):
    """Data Factory extra properties."""
    safe_property(obj, "version", props.get("version", ""))
    safe_property(obj, "create_time", props.get("createTime", ""))
    safe_property(obj, "public_network_access",
                  props.get("publicNetworkAccess", ""))
    repo = props.get("repoConfiguration", {})
    if repo:
        safe_property(obj, "repo_type", repo.get("type", ""))
        safe_property(obj, "repo_account_name",
                      repo.get("accountName", ""))


# ---------------------------------------------------------------------------
# Resource type definitions: (resource_kind, arm_path, api_version, extra_fn)
# ---------------------------------------------------------------------------

RESOURCE_TYPE_DEFINITIONS = [
    # --- Networking (13) ---
    ("AZURE_NETWORK_SECURITY_GROUP", "Microsoft.Network/networkSecurityGroups",
     "2023-05-01", _nsg_props),
    ("AZURE_ROUTE_TABLES", "Microsoft.Network/routeTables",
     "2023-05-01", _route_table_props),
    ("AZURE_DNS_ZONES", "Microsoft.Network/dnsZones",
     "2018-05-01", _dns_zone_props),
    ("AZURE_PRIVATE_DNSZONES", "Microsoft.Network/privateDnsZones",
     "2020-06-01", _dns_zone_props),
    ("AZURE_FIREWALLS", "Microsoft.Network/azureFirewalls",
     "2023-05-01", _firewall_props),
    ("AZURE_VIRTUAL_NETWORK_GATEWAY", "Microsoft.Network/virtualNetworkGateways",
     "2023-05-01", _vnet_gateway_props),
    ("AZURE_APPLICATION_GATEWAY", "Microsoft.Network/applicationGateways",
     "2023-05-01", _app_gateway_props),
    ("AZURE_TRAFFIC_MANAGER_PROFILES", "Microsoft.Network/trafficManagerProfiles",
     "2022-04-01", None),
    ("AZURE_FRONT_DOORS", "Microsoft.Network/frontDoors",
     "2021-06-01", None),
    ("AZURE_VIRTUAL_WAN", "Microsoft.Network/virtualWans",
     "2023-05-01", None),
    ("AZURE_VIRTUAL_HUBS", "Microsoft.Network/virtualHubs",
     "2023-05-01", None),
    ("AZURE_DDOS_PROTECTION_PLAN", "Microsoft.Network/ddosProtectionPlans",
     "2023-05-01", None),
    ("AZURE_NETWORK_WATCHERS", "Microsoft.Network/networkWatchers",
     "2023-05-01", None),

    # --- Containers (5) ---
    ("AZURE_KUBERNATE_CLUSTER", "Microsoft.ContainerService/managedClusters",
     "2023-05-01", _k8s_props),
    ("AZURE_CONTIANER_CONTAINERGROUPS", "Microsoft.ContainerInstance/containerGroups",
     "2023-05-01", None),
    ("AZURE_CONTAINER_REGISTRIES", "Microsoft.ContainerRegistry/registries",
     "2023-07-01", _container_registry_props),
    ("AZURE_OPENSHIFT_CLUSTERS", "Microsoft.RedHatOpenShift/openShiftClusters",
     "2023-04-01", None),
    # AZURE_CONTAINER is a child of container groups — handled inline if needed

    # --- Compute (7) ---
    ("AZURE_VIRTUAL_SCALESET", "Microsoft.Compute/virtualMachineScaleSets",
     "2023-03-01", None),
    ("AZURE_AVAILABILITY_SETS", "Microsoft.Compute/availabilitySets",
     "2023-03-01", None),
    ("AZURE_PROXIMITY_PLACEMENT_GROUP", "Microsoft.Compute/proximityPlacementGroups",
     "2023-03-01", None),
    ("AZURE_BATCH_ACCOUNT", "Microsoft.Batch/batchAccounts",
     "2023-05-01", None),
    ("AZURE_AUTOMATION", "Microsoft.Automation/automationAccounts",
     "2023-11-01", _automation_props),
    # AZURE_COMPUTE_DOMAINNAMES and AZURE_VIRTUAL_SCALESET_INSTANCE are special

    # --- Database (5) ---
    ("AZURE_CACHE_REDIS", "Microsoft.Cache/redis",
     "2023-04-01", _redis_props),
    ("AZURE_SQL_MANAGEDINSTANCES", "Microsoft.Sql/managedInstances",
     "2023-05-01-preview", None),
    ("AZURE_MARIADB_SERVER", "Microsoft.DBforMariaDB/servers",
     "2018-06-01", None),
    # AZURE_SQL_MANAGEDINSTANCES_DATABASE and AZURE_MARIA_DBSERVER_DATABASE
    # are children — would need per-parent enumeration

    # --- Messaging (6) ---
    ("AZURE_SERVICE_BUS", "Microsoft.ServiceBus/namespaces",
     "2022-10-01-preview", _service_bus_props),
    ("AZURE_EVENTHUBS_NAMESPACES", "Microsoft.EventHub/namespaces",
     "2022-10-01-preview", None),
    ("AZURE_EVENT_GRID_DOMAIN", "Microsoft.EventGrid/domains",
     "2022-06-15", None),
    ("AZURE_EVENT_GRID_TOPIC", "Microsoft.EventGrid/topics",
     "2022-06-15", None),
    # AZURE_EVENT_HUBS and AZURE_EVENT_GRID_SUBSCRIPTION are children

    # --- Analytics & Data (10) ---
    ("AZURE_DATA_FACTORY", "Microsoft.DataFactory/factories",
     "2018-06-01", _data_factory_props),
    ("AZURE_DATA_LAKE_ANALYTICS", "Microsoft.DataLakeAnalytics/accounts",
     "2016-11-01", None),
    ("AZURE_DATALAKE_STORE", "Microsoft.DataLakeStore/accounts",
     "2016-11-01", None),
    ("AZURE_SYNAPSE_ANALYTICS_WORKSPACE", "Microsoft.Synapse/workspaces",
     "2021-06-01", None),
    ("AZURE_HDINSIGHT", "Microsoft.HDInsight/clusters",
     "2023-06-01-preview", None),
    ("AZURE_DATA_EXPLORER_CLUSTER", "Microsoft.Kusto/clusters",
     "2023-05-02", None),
    ("AZURE_STREAM_ANALYTICS_JOBS", "Microsoft.StreamAnalytics/streamingjobs",
     "2021-10-01-preview", None),
    ("AZURE_STREAM_ANALYTICS_CLUSTERS", "Microsoft.StreamAnalytics/clusters",
     "2020-03-01-preview", None),

    # --- AI/ML & Cognitive (7) ---
    ("AZURE_COGNITIVE_SERVICES_ACCOUNTS", "Microsoft.CognitiveServices/accounts",
     "2023-05-01", None),
    ("AZURE_MACHINE_LEARNING", "Microsoft.MachineLearningServices/workspaces",
     "2023-04-01", None),
    ("AZURE_SEARCH_SERVICES", "Microsoft.Search/searchServices",
     "2023-11-01", None),
    ("AZURE_ANALYSIS_SERVICES", "Microsoft.AnalysisServices/servers",
     "2017-08-01", None),
    ("AZURE_POWER_BI_EMBEDDED", "Microsoft.PowerBIDedicated/capacities",
     "2021-01-01", None),
    ("AZURE_BOT_SERVICES", "Microsoft.BotService/botServices",
     "2022-09-15", None),
    ("AZURE_PURVIEW_ACCOUNTS", "Microsoft.Purview/accounts",
     "2021-12-01", None),

    # --- IoT & Digital (4) ---
    ("AZURE_IOT_HUB", "Microsoft.Devices/IotHubs",
     "2023-06-30", None),
    ("AZURE_IOT_CENTRAL", "Microsoft.IoTCentral/iotApps",
     "2021-06-01", None),
    ("AZURE_DIGITAL_TWINS", "Microsoft.DigitalTwins/digitalTwinsInstances",
     "2023-01-31", None),
    ("AZURE_TIME_SERIES_INSIGHTS", "Microsoft.TimeSeriesInsights/environments",
     "2020-05-15", None),

    # --- API & Integration (2) ---
    ("AZURE_API_MANAGEMENT", "Microsoft.ApiManagement/service",
     "2022-08-01", _api_management_props),
    ("AZURE_APP_CONFIGURATION", "Microsoft.AppConfiguration/configurationStores",
     "2023-03-01", None),

    # --- CDN (2) ---
    ("AZURE_CDN_PROFILES", "Microsoft.Cdn/profiles",
     "2023-05-01", None),
    # AZURE_CDN_PROFILES_ENDPOINTS is a child of CDN profiles

    # --- Media (1 — children handled separately) ---
    ("AZURE_MEDIA_SERVICES", "Microsoft.Media/mediaservices",
     "2023-01-01", None),

    # --- NetApp (1 — children handled separately) ---
    ("AZURE_NETAPPACCOUNT", "Microsoft.NetApp/netAppAccounts",
     "2023-05-01", None),

    # --- Notifications (1 — children handled separately) ---
    ("AZURE_NOTIFICATIONHUBS_NAMESPACES", "Microsoft.NotificationHubs/namespaces",
     "2023-01-01", None),

    # --- SignalR (1) ---
    ("AZURE_SIGNALR_SERVICES", "Microsoft.SignalRService/signalR",
     "2023-02-01", None),

    # --- Other (2) ---
    ("AZURE_SPATIAL_ANCHORS", "Microsoft.MixedReality/spatialAnchorsAccounts",
     "2021-01-01", None),
    ("AZURE_DATA_BOX", "Microsoft.DataBox/jobs",
     "2022-12-01", None),
]


def collect_all_generic_resources(client: AzureClient, result,
                                  adapter_kind: str, subscriptions: list):
    """Collect all generic ARM resource types.

    Each type is collected independently — failure in one doesn't affect others.
    """
    total_types = 0
    total_resources = 0

    for resource_kind, arm_path, api_version, extra_fn in RESOURCE_TYPE_DEFINITIONS:
        try:
            count = collect_generic_arm_resources(
                client=client,
                result=result,
                adapter_kind=adapter_kind,
                subscriptions=subscriptions,
                resource_kind=resource_kind,
                arm_provider_path=arm_path,
                api_version=api_version,
                extra_properties_fn=extra_fn,
            )
            total_types += 1
            total_resources += count
        except Exception as e:
            logger.error("Failed to collect %s: %s", resource_kind, e)

    logger.info("Bulk collection complete: %d types, %d total resources",
                total_types, total_resources)
