"""AUTO-GENERATED from native MicrosoftAzureAdapter describe.xml.
Maps each ResourceKind -> {identifier_key: is_part_of_uniqueness}.
identType="1" -> True (part of uniqueness); identType="2" -> False.
Regenerate with scripts/gen-identifier-uniqueness.py when the native
describe.xml changes. Do NOT hand-edit.
"""

KIND_IDENTIFIER_UNIQUENESS = {
    "AZURE_ANALYSIS_SERVICES": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_API_MANAGEMENT": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_APPLICATION_GATEWAY": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_APP_CONFIGURATION": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_APP_SERVICE": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_APP_SERVICE_PLAN": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_AUTOMATION": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_AVAILABILITY_SETS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_BATCH_ACCOUNT": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_BOT_SERVICES": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_CACHE_REDIS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_CDN_PROFILES": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_CDN_PROFILES_ENDPOINTS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True,
        "cdnProfileId": False
    },
    "AZURE_COGNITIVE_SERVICES_ACCOUNTS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_COMPUTE_DOMAINNAMES": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_COMPUTE_HOSTGROUPS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_CONTAINER": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True,
        "containerGroupId": True
    },
    "AZURE_CONTAINER_REGISTRIES": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_CONTIANER_CONTAINERGROUPS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_DATALAKE_STORE": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_DATA_BOX": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_DATA_EXPLORER_CLUSTER": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_DATA_EXPLORER_DATABASE": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_DATA_FACTORY": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_DATA_LAKE_ANALYTICS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_DB_ACCOUNT": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_DDOS_PROTECTION_PLAN": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_DEDICATE_HOST": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True,
        "hostGroupName": True
    },
    "AZURE_DIGITAL_TWINS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_DNS_ZONES": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_EVENTHUBS_NAMESPACES": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_EVENT_GRID_DOMAIN": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_EVENT_GRID_SUBSCRIPTION": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_EVENT_GRID_TOPIC": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_EVENT_HUBS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True,
        "eventHubsNameId": True
    },
    "AZURE_EXPRESSROUTE_CIRCUITS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_FIREWALLS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_FRONT_DOORS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_FUNCTIONS_APP": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_HDINSIGHT": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_IOT_CENTRAL": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_IOT_HUB": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_KEY_VAULTS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_KUBERNATE_CLUSTER": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_LB": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_MACHINE_LEARNING": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_MARIADB_SERVER": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_MARIA_DBSERVER_DATABASE": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True,
        "mariaServerDB": True
    },
    "AZURE_MEDIASERVICES_LIVEEVENTS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_MEDIASERVICES_STREAMINGEP": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_MEDIA_SERVICES": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_MYSQL_SERVER": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_NETAPPACCOUNT": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_NETAPPACCOUNT_CAPACITYPOOLS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True,
        "netAppAccountId": True
    },
    "AZURE_NETAPPACCOUNT_CAPACITYPOOLS_VOLUMES": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True,
        "netAppAccountId": True,
        "poolName": True
    },
    "AZURE_NETWORK_SECURITY_GROUP": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_NETWORK_WATCHERS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_NH_NAMESPACES_NOTIFICATIONHUBS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_NOTIFICATIONHUBS_NAMESPACES": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_NW_INTERFACE": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_OPENSHIFT_CLUSTERS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_POSTGRESQL_SERVER": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_POWER_BI_EMBEDDED": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_PRIVATE_DNSZONES": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_PROXIMITY_PLACEMENT_GROUP": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_PUBLIC_IPADDRESSES": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_PURVIEW_ACCOUNTS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_RESOURCE_GROUP": {
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_ROUTE_TABLES": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_SEARCH_SERVICES": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_SERVICE_BUS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_SIGNALR_SERVICES": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_SPATIAL_ANCHORS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_SQL_DATABASE": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True,
        "SERVER_ID": True
    },
    "AZURE_SQL_MANAGEDINSTANCES": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_SQL_MANAGEDINSTANCES_DATABASE": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True,
        "managedInstanceId": True
    },
    "AZURE_SQL_SERVER": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_STORAGE_ACCOUNT": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_STORAGE_DISK": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_STREAM_ANALYTICS_CLUSTERS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_STREAM_ANALYTICS_JOBS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_SYNAPSE_ANALYTICS_BIGDATA_POOL": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_SYNAPSE_ANALYTICS_SQL_POOL": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_SYNAPSE_ANALYTICS_WORKSPACE": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_TIME_SERIES_INSIGHTS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_TRAFFIC_MANAGER_PROFILES": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_VIRTUAL_HUBS": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True,
        "virtualWanId": True
    },
    "AZURE_VIRTUAL_MACHINE": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_VIRTUAL_NETWORK": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_VIRTUAL_NETWORK_GATEWAY": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_VIRTUAL_SCALESET": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_VIRTUAL_SCALESET_INSTANCE": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "AZURE_VIRTUAL_WAN": {
        "AZURE_REGION": False,
        "AZURE_RESOURCE_GROUP": True,
        "AZURE_SUBSCRIPTION_ID": True,
        "ID": True
    },
    "MicrosoftAzureAdapter Instance": {
        "ACCOUNT_TYPE": False,
        "ACTION": False,
        "AZURE_SUBSCRIPTION_ID": True,
        "AZURE_TENANT_ID": True,
        "COLLECT_CUSTOM_METRICS": False,
        "GOV_CLOUD_REGIONS": False,
        "GOV_CLOUD_SERVICES": False,
        "REGIONS": False,
        "SERVICES": False
    }
}
