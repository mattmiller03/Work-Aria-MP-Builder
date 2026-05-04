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


def _vmss_props(obj, resource, props):
    """Virtual Machine Scale Set extra properties."""
    sku = resource.get("sku", {})
    safe_property(obj, "sku_name", sku.get("name", ""))
    safe_property(obj, "sku_tier", sku.get("tier", ""))
    safe_property(obj, "sku_capacity", sku.get("capacity", 0))
    safe_property(obj, "upgrade_mode",
                  props.get("upgradePolicy", {}).get("mode", ""))
    safe_property(obj, "overprovision",
                  str(props.get("overprovision", "")))
    safe_property(obj, "single_placement_group",
                  str(props.get("singlePlacementGroup", "")))
    safe_property(obj, "zone_balance",
                  str(props.get("zoneBalance", "")))
    zones = resource.get("zones", [])
    safe_property(obj, "zones", ", ".join(zones) if zones else "")
    vm_profile = props.get("virtualMachineProfile", {})
    os_profile = vm_profile.get("osProfile", {})
    if os_profile.get("windowsConfiguration") is not None:
        os_type = "Windows"
    elif os_profile.get("linuxConfiguration") is not None:
        os_type = "Linux"
    else:
        os_type = ""
    safe_property(obj, "os_type", os_type)
    storage = vm_profile.get("storageProfile", {})
    image_ref = storage.get("imageReference", {})
    safe_property(obj, "image_offer", image_ref.get("offer", ""))
    safe_property(obj, "image_sku", image_ref.get("sku", ""))
    safe_property(obj, "image_publisher", image_ref.get("publisher", ""))


def _availability_set_props(obj, resource, props):
    """Availability Set extra properties."""
    safe_property(obj, "fault_domain_count",
                  props.get("platformFaultDomainCount", 0))
    safe_property(obj, "update_domain_count",
                  props.get("platformUpdateDomainCount", 0))
    vms = props.get("virtualMachines", [])
    safe_property(obj, "vm_count", len(vms))
    sku = resource.get("sku", {})
    safe_property(obj, "managed",
                  str(sku.get("name", "") == "Aligned"))


def _network_watcher_props(obj, resource, props):
    """Network Watcher extra properties."""
    safe_property(obj, "provisioning_state",
                  props.get("provisioningState", ""))
    flow_analytics = props.get("flowAnalyticsConfiguration", {})
    safe_property(obj, "flow_analytics_enabled",
                  str(bool(flow_analytics)))


def _eventhub_ns_props(obj, resource, props):
    """Event Hub Namespace extra properties."""
    sku = resource.get("sku", {})
    safe_property(obj, "sku_name", sku.get("name", ""))
    safe_property(obj, "sku_tier", sku.get("tier", ""))
    safe_property(obj, "sku_capacity", sku.get("capacity", 0))
    safe_property(obj, "status", props.get("status", ""))
    safe_property(obj, "kafka_enabled",
                  str(props.get("kafkaEnabled", "")))
    safe_property(obj, "zone_redundant",
                  str(props.get("zoneRedundant", "")))
    safe_property(obj, "service_bus_endpoint",
                  props.get("serviceBusEndpoint", ""))
    safe_property(obj, "metric_id", props.get("metricId", ""))
    safe_property(obj, "disable_local_auth",
                  str(props.get("disableLocalAuth", "")))
    safe_property(obj, "maximum_throughput_units",
                  props.get("maximumThroughputUnits", 0))
    safe_property(obj, "is_auto_inflate_enabled",
                  str(props.get("isAutoInflateEnabled", "")))


def _cognitive_services_props(obj, resource, props):
    """Cognitive Services account extra properties."""
    sku = resource.get("sku", {})
    safe_property(obj, "sku_name", sku.get("name", ""))
    safe_property(obj, "kind", resource.get("kind", ""))
    safe_property(obj, "endpoint", props.get("endpoint", ""))
    safe_property(obj, "public_network_access",
                  props.get("publicNetworkAccess", ""))
    safe_property(obj, "custom_subdomain_name",
                  props.get("customSubDomainName", ""))
    network_acls = props.get("networkAcls", {})
    safe_property(obj, "network_rule_default_action",
                  network_acls.get("defaultAction", ""))
    safe_property(obj, "restore_allowed",
                  str(props.get("restore", "")))
    safe_property(obj, "disable_local_auth",
                  str(props.get("disableLocalAuth", "")))


def _sql_managed_instance_props(obj, resource, props):
    """SQL Managed Instance extra properties."""
    sku = resource.get("sku", {})
    safe_property(obj, "sku_name", sku.get("name", ""))
    safe_property(obj, "sku_tier", sku.get("tier", ""))
    safe_property(obj, "v_cores", props.get("vCores", 0))
    safe_property(obj, "storage_size_in_gb",
                  props.get("storageSizeInGB", 0))
    safe_property(obj, "state", props.get("state", ""))
    safe_property(obj, "fully_qualified_domain_name",
                  props.get("fullyQualifiedDomainName", ""))
    safe_property(obj, "administrator_login",
                  props.get("administratorLogin", ""))
    safe_property(obj, "license_type", props.get("licenseType", ""))
    safe_property(obj, "collation", props.get("collation", ""))
    safe_property(obj, "public_data_endpoint_enabled",
                  str(props.get("publicDataEndpointEnabled", "")))
    safe_property(obj, "proxy_override", props.get("proxyOverride", ""))
    safe_property(obj, "timezone_id", props.get("timezoneId", ""))
    safe_property(obj, "zone_redundant",
                  str(props.get("zoneRedundant", "")))
    safe_property(obj, "minimal_tls_version",
                  props.get("minimalTlsVersion", ""))


def _data_explorer_props(obj, resource, props):
    """Azure Data Explorer (Kusto) cluster extra properties."""
    sku = resource.get("sku", {})
    safe_property(obj, "sku_name", sku.get("name", ""))
    safe_property(obj, "sku_tier", sku.get("tier", ""))
    safe_property(obj, "sku_capacity", sku.get("capacity", 0))
    safe_property(obj, "state", props.get("state", ""))
    safe_property(obj, "uri", props.get("uri", ""))
    safe_property(obj, "data_ingestion_uri",
                  props.get("dataIngestionUri", ""))
    safe_property(obj, "enable_streaming_ingest",
                  str(props.get("enableStreamingIngest", "")))
    safe_property(obj, "enable_purge",
                  str(props.get("enablePurge", "")))
    safe_property(obj, "enable_disk_encryption",
                  str(props.get("enableDiskEncryption", "")))
    trusted = props.get("trustedExternalTenants", [])
    safe_property(obj, "trusted_external_tenant_count", len(trusted))
    safe_property(obj, "engine_type", props.get("engineType", ""))
    zones = resource.get("zones", [])
    safe_property(obj, "zones", ", ".join(zones) if zones else "")


# ---------------------------------------------------------------------------
# Extractors for new custom kinds (no native pak equivalent)
# ---------------------------------------------------------------------------

def _logic_workflow_props(obj, resource, props):
    """Logic App Workflow extra properties."""
    safe_property(obj, "state", props.get("state", ""))
    safe_property(obj, "created_time", props.get("createdTime", ""))
    safe_property(obj, "changed_time", props.get("changedTime", ""))
    safe_property(obj, "version", props.get("version", ""))
    safe_property(obj, "sku_name",
                  props.get("sku", {}).get("name", ""))
    definition = props.get("definition", {})
    actions = definition.get("actions", {})
    safe_property(obj, "action_count", len(actions))
    triggers = definition.get("triggers", {})
    safe_property(obj, "trigger_count", len(triggers))
    safe_property(obj, "integration_account_id",
                  props.get("integrationAccount", {}).get("id", ""))


def _arc_machine_props(obj, resource, props):
    """Azure Arc (HybridCompute) machine extra properties."""
    safe_property(obj, "os_type", props.get("osType", ""))
    safe_property(obj, "os_name", props.get("osName", ""))
    safe_property(obj, "os_version", props.get("osVersion", ""))
    safe_property(obj, "agent_version", props.get("agentVersion", ""))
    safe_property(obj, "status", props.get("status", ""))
    safe_property(obj, "dns_fqdn", props.get("dnsFqdn", ""))
    safe_property(obj, "machine_fqdn", props.get("machineFqdn", ""))
    safe_property(obj, "vm_uuid", props.get("vmUuid", ""))
    safe_property(obj, "cloud_metadata_provider",
                  props.get("cloudMetadata", {}).get("provider", ""))
    safe_property(obj, "license_profile_esu_status",
                  props.get("licenseProfile", {}).get(
                      "esuProfile", {}).get("assignedLicense", ""))
    extensions = props.get("extensions", [])
    safe_property(obj, "extension_count", len(extensions))


def _bastion_host_props(obj, resource, props):
    """Azure Bastion Host extra properties."""
    safe_property(obj, "dns_name", props.get("dnsName", ""))
    safe_property(obj, "scale_units", props.get("scaleUnits", 0))
    safe_property(obj, "sku_name",
                  resource.get("sku", {}).get("name", ""))
    safe_property(obj, "disable_copy_paste",
                  str(props.get("disableCopyPaste", "")))
    safe_property(obj, "enable_tunneling",
                  str(props.get("enableTunneling", "")))
    safe_property(obj, "enable_ip_connect",
                  str(props.get("enableIpConnect", "")))
    safe_property(obj, "enable_shareable_link",
                  str(props.get("enableShareableLink", "")))
    safe_property(obj, "enable_kerberos",
                  str(props.get("enableKerberos", "")))
    ip_configs = props.get("ipConfigurations", [])
    safe_property(obj, "ip_configuration_count", len(ip_configs))


def _private_endpoint_props(obj, resource, props):
    """Private Endpoint extra properties."""
    connections = props.get("privateLinkServiceConnections", [])
    if connections:
        conn = connections[0]
        conn_props = conn.get("properties", {})
        state = conn_props.get("privateLinkServiceConnectionState", {})
        safe_property(obj, "connection_status", state.get("status", ""))
        safe_property(obj, "connection_description",
                      state.get("description", ""))
        group_ids = conn_props.get("groupIds", [])
        safe_property(obj, "group_ids", ", ".join(group_ids))
        safe_property(obj, "linked_resource_id",
                      conn_props.get("privateLinkServiceId", ""))
    else:
        safe_property(obj, "connection_status", "")
        safe_property(obj, "linked_resource_id", "")
        safe_property(obj, "group_ids", "")
    subnet = props.get("subnet", {})
    safe_property(obj, "subnet_id", subnet.get("id", ""))
    nics = props.get("networkInterfaces", [])
    safe_property(obj, "network_interface_count", len(nics))
    configs = props.get("customDnsConfigs", [])
    ip_list = [c.get("ipAddresses", []) for c in configs]
    flat_ips = [ip for sublist in ip_list for ip in sublist]
    safe_property(obj, "ip_addresses", ", ".join(flat_ips) if flat_ips else "")


def _nat_gateway_props(obj, resource, props):
    """NAT Gateway extra properties."""
    sku = resource.get("sku", {})
    safe_property(obj, "sku_name", sku.get("name", ""))
    safe_property(obj, "idle_timeout_minutes",
                  props.get("idleTimeoutInMinutes", 0))
    pub_ips = props.get("publicIpAddresses", [])
    safe_property(obj, "public_ip_count", len(pub_ips))
    pub_prefixes = props.get("publicIpPrefixes", [])
    safe_property(obj, "public_ip_prefix_count", len(pub_prefixes))
    subnets = props.get("subnets", [])
    safe_property(obj, "subnet_count", len(subnets))
    zones = resource.get("zones", [])
    safe_property(obj, "zones", ", ".join(zones) if zones else "")


def _snapshot_props(obj, resource, props):
    """Compute Snapshot extra properties."""
    safe_property(obj, "disk_size_gb", props.get("diskSizeGB", 0))
    safe_property(obj, "os_type", props.get("osType", ""))
    safe_property(obj, "disk_state", props.get("diskState", ""))
    safe_property(obj, "incremental",
                  str(props.get("incremental", "")))
    safe_property(obj, "network_access_policy",
                  props.get("networkAccessPolicy", ""))
    safe_property(obj, "public_network_access",
                  props.get("publicNetworkAccess", ""))
    safe_property(obj, "hyper_v_generation",
                  props.get("hyperVGeneration", ""))
    safe_property(obj, "disk_access_id",
                  props.get("diskAccessId", ""))
    creation_data = props.get("creationData", {})
    safe_property(obj, "create_option",
                  creation_data.get("createOption", ""))
    safe_property(obj, "source_resource_id",
                  creation_data.get("sourceResourceId", ""))
    sku = resource.get("sku", {})
    safe_property(obj, "sku_name", sku.get("name", ""))


def _disk_encryption_set_props(obj, resource, props):
    """Disk Encryption Set extra properties."""
    safe_property(obj, "encryption_type",
                  props.get("encryptionType", ""))
    safe_property(obj, "auto_key_rotation_enabled",
                  str(props.get("autoKeyRotationError", {}) == {}
                      and props.get("rotationToLatestKeyVersionEnabled", False)))
    safe_property(obj, "rotation_to_latest_key_version_enabled",
                  str(props.get("rotationToLatestKeyVersionEnabled", "")))
    active_key = props.get("activeKey", {})
    key_url = active_key.get("keyUrl", "")
    safe_property(obj, "key_url", key_url)
    source_vault = active_key.get("sourceVault", {})
    safe_property(obj, "key_vault_id", source_vault.get("id", ""))
    safe_property(obj, "federated_client_id",
                  props.get("federatedClientId", ""))
    prev_keys = props.get("previousKeys", [])
    safe_property(obj, "previous_key_count", len(prev_keys))


def _managed_identity_props(obj, resource, props):
    """User-Assigned Managed Identity extra properties."""
    safe_property(obj, "client_id", props.get("clientId", ""))
    safe_property(obj, "principal_id", props.get("principalId", ""))
    safe_property(obj, "tenant_id", props.get("tenantId", ""))


def _dns_resolver_props(obj, resource, props):
    """Azure DNS Resolver extra properties."""
    safe_property(obj, "dns_resolver_state",
                  props.get("dnsResolverState", ""))
    vnet = props.get("virtualNetwork", {})
    safe_property(obj, "virtual_network_id", vnet.get("id", ""))


def _backup_vault_props(obj, resource, props):
    """Azure Backup Vault (DataProtection) extra properties."""
    storage_settings = props.get("storageSettings", [])
    if storage_settings:
        ss = storage_settings[0]
        safe_property(obj, "storage_redundancy",
                      ss.get("storageDataStoreType", ""))
        safe_property(obj, "datastore_type",
                      ss.get("datastoreType", ""))
    else:
        safe_property(obj, "storage_redundancy", "")
        safe_property(obj, "datastore_type", "")
    safe_property(obj, "immutability_state",
                  props.get("securitySettings", {}).get(
                      "immutabilitySettings", {}).get("state", ""))
    safe_property(obj, "soft_delete_state",
                  props.get("securitySettings", {}).get(
                      "softDeleteSettings", {}).get("softDeleteState", ""))
    sku = resource.get("sku", {})
    safe_property(obj, "sku_name", sku.get("name", ""))
    safe_property(obj, "sku_tier", sku.get("tier", ""))


def _sql_vm_props(obj, resource, props):
    """SQL Virtual Machine extra properties."""
    safe_property(obj, "sql_image_sku", props.get("sqlImageSku", ""))
    safe_property(obj, "sql_management", props.get("sqlManagement", ""))
    safe_property(obj, "sql_server_license_type",
                  props.get("sqlServerLicenseType", ""))
    safe_property(obj, "virtual_machine_id",
                  props.get("virtualMachineResourceId", ""))
    safe_property(obj, "sql_image_offer", props.get("sqlImageOffer", ""))
    conn_settings = props.get("serverConfigurationsManagementSettings", {})
    sql_conn = conn_settings.get("sqlConnectivityUpdateSettings", {})
    safe_property(obj, "sql_connectivity_type",
                  sql_conn.get("connectivityType", ""))
    safe_property(obj, "sql_workload_type",
                  props.get("sqlVirtualMachineGroupResourceId", ""))
    wl_settings = props.get("sqlWorkloadTypeUpdateSettings", {})
    safe_property(obj, "workload_type",
                  wl_settings.get("sqlWorkloadType", ""))


def _app_service_env_props(obj, resource, props):
    """App Service Environment (ASE) extra properties."""
    safe_property(obj, "status", props.get("status", ""))
    safe_property(obj, "kind", resource.get("kind", ""))
    safe_property(obj, "internal_load_balancing_mode",
                  props.get("internalLoadBalancingMode", ""))
    safe_property(obj, "multi_size", props.get("multiSize", ""))
    vnet = props.get("virtualNetwork", {})
    safe_property(obj, "virtual_network_id", vnet.get("id", ""))
    safe_property(obj, "subnet_id", vnet.get("subnet", ""))
    worker_pools = props.get("workerPools", [])
    safe_property(obj, "worker_pool_count", len(worker_pools))
    safe_property(obj, "maximum_number_of_machines",
                  props.get("maximumNumberOfMachines", 0))
    safe_property(obj, "front_end_scale_factor",
                  props.get("frontEndScaleFactor", 0))
    safe_property(obj, "upgrade_preference",
                  props.get("upgradePreference", ""))


def _storage_sync_props(obj, resource, props):
    """Storage Sync Service extra properties."""
    safe_property(obj, "incoming_traffic_policy",
                  props.get("incomingTrafficPolicy", ""))
    safe_property(obj, "storage_sync_service_status",
                  str(props.get("storageSyncServiceStatus", "")))
    safe_property(obj, "use_private_link_enabled",
                  str(props.get("usePrivateLinkEnabled", "")))


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
     "2023-05-01", _network_watcher_props),

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
     "2023-03-01", _vmss_props),
    ("AZURE_AVAILABILITY_SETS", "Microsoft.Compute/availabilitySets",
     "2023-03-01", _availability_set_props),
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
     "2023-05-01-preview", _sql_managed_instance_props),
    ("AZURE_MARIADB_SERVER", "Microsoft.DBforMariaDB/servers",
     "2018-06-01", None),
    # AZURE_SQL_MANAGEDINSTANCES_DATABASE and AZURE_MARIA_DBSERVER_DATABASE
    # are children — would need per-parent enumeration

    # --- Messaging (6) ---
    ("AZURE_SERVICE_BUS", "Microsoft.ServiceBus/namespaces",
     "2022-10-01-preview", _service_bus_props),
    ("AZURE_EVENTHUBS_NAMESPACES", "Microsoft.EventHub/namespaces",
     "2022-10-01-preview", _eventhub_ns_props),
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
     "2023-05-02", _data_explorer_props),
    ("AZURE_STREAM_ANALYTICS_JOBS", "Microsoft.StreamAnalytics/streamingjobs",
     "2021-10-01-preview", None),
    ("AZURE_STREAM_ANALYTICS_CLUSTERS", "Microsoft.StreamAnalytics/clusters",
     "2020-03-01-preview", None),

    # --- AI/ML & Cognitive (7) ---
    ("AZURE_COGNITIVE_SERVICES_ACCOUNTS", "Microsoft.CognitiveServices/accounts",
     "2023-05-01", _cognitive_services_props),
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

    # --- Custom kinds — no native pak equivalent (13) ---
    ("azure_logic_workflow", "Microsoft.Logic/workflows",
     "2019-05-01", _logic_workflow_props),
    ("azure_arc_machine", "Microsoft.HybridCompute/machines",
     "2023-03-15-preview", _arc_machine_props),
    ("azure_bastion_host", "Microsoft.Network/bastionHosts",
     "2023-05-01", _bastion_host_props),
    ("azure_private_endpoint", "Microsoft.Network/privateEndpoints",
     "2023-05-01", _private_endpoint_props),
    ("azure_nat_gateway", "Microsoft.Network/natGateways",
     "2023-05-01", _nat_gateway_props),
    ("azure_compute_snapshot", "Microsoft.Compute/snapshots",
     "2023-04-02", _snapshot_props),
    ("azure_disk_encryption_set", "Microsoft.Compute/diskEncryptionSets",
     "2023-04-02", _disk_encryption_set_props),
    ("azure_managed_identity", "Microsoft.ManagedIdentity/userAssignedIdentities",
     "2023-01-31", _managed_identity_props),
    ("azure_dns_resolver", "Microsoft.Network/dnsResolvers",
     "2022-07-01", _dns_resolver_props),
    ("azure_backup_vault", "Microsoft.DataProtection/backupVaults",
     "2023-05-01", _backup_vault_props),
    ("azure_sql_virtual_machine", "Microsoft.SqlVirtualMachine/sqlVirtualMachines",
     "2023-01-01-preview", _sql_vm_props),
    ("azure_app_service_environment", "Microsoft.Web/hostingEnvironments",
     "2023-01-01", _app_service_env_props),
    ("azure_storage_sync", "Microsoft.StorageSync/storageSyncServices",
     "2022-06-01", _storage_sync_props),
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
