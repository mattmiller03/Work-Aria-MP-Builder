#!/usr/bin/env python3
"""Post-build script to patch the generated describe.xml.

The Python SDK's ObjectType class doesn't support all the XML attributes
needed for Aria Ops UI integration (type, subType, worldObjectName, showTag).
This script patches the generated describe.xml after mp-build to add them.

Each attribute patch REPLACES any existing same-named attribute rather than
appending, so we don't end up with duplicate `type="..."` attributes (which
produce malformed XML and cause Suite-API to reject the pak synchronously
during APPLY_ADAPTER).

Usage:
    python patch-describe-xml.py [path/to/describe.xml]

If no path is given, looks in the default location:
    ../Azure-Native-Build/conf/describe.xml

Run this AFTER mp-build but BEFORE mp-build finishes packaging the .pak.
Or better: integrate into the build process via a wrapper script.
"""

import re
import sys
import os


# ---------------------------------------------------------------------------
# Attribute patches — per-ResourceKind attribute overrides
#
# Each entry maps a ResourceKind `key` to a dict of attributes that should be
# present (overwriting any existing attribute of the same name emitted by the
# SDK).
# ---------------------------------------------------------------------------

ATTR_PATCHES = {
    "AZURE_WORLD": {
        "showTag": "false",
        "type": "8",
        "subType": "6",
        "worldObjectName": "Azure World",
    },
    "AZURE_REGION": {
        "showTag": "false",
    },
    "AZURE_REGION_PER_SUB": {
        "showTag": "false",
    },
    "AZURE_RESOURCE_GROUP": {
        "type": "8",
    },
    "AZURE_SERVICES_FROM_XML": {
        "showTag": "false",
    },
    # SDK emits "<adapter-name>_adapter_instance" for the adapter-instance
    # ResourceKind. Native pak uses "MicrosoftAzureAdapter Instance" (with a
    # space), and all our bundled content (traversal specs, dashboards) points
    # at that exact name. We rename the key below. monitoringInterval matches
    # the native pak's 10-minute cycle.
    "MicrosoftAzureAdapter_adapter_instance": {
        "monitoringInterval": "10",
    },
}

# ResourceKind keys that must be renamed after attribute patching. Map of
# old_key -> new_key. Keep in sync with OBJ_ADAPTER_INSTANCE in
# Azure-Native-Build/app/constants.py.
RENAME_KINDS = {
    "MicrosoftAzureAdapter_adapter_instance": "MicrosoftAzureAdapter Instance",
}

# ResourceIdentifier attribute overrides. Keyed by the identifier's `key`
# attribute; only applied to the first matching occurrence (typically inside
# the adapter-instance ResourceKind).
#
# Background: the SDK emits identType="1" (part of unique key) for all
# identifiers, but the native pak marks enum selectors like ACCOUNT_TYPE and
# SERVICES as identType="2" (descriptive, not part of uniqueness). On upgrade,
# Aria Ops matches existing adapter instances against our new schema by the
# identType="1" fields; if we claim ACCOUNT_TYPE is part of the key when
# existing instances were created with it as descriptive, the match fails and
# APPLY_ADAPTER rejects the pak.
IDENTIFIER_ATTR_PATCHES = {
    "ACCOUNT_TYPE": {
        "identType": "2",
    },
}

# ---------------------------------------------------------------------------
# Child-element patches — injected as children of the named ResourceKind.
# These are added once per kind; re-runs are a no-op because we check for the
# child's presence first.
# ---------------------------------------------------------------------------

POWER_STATE_BLOCK = """
         <PowerState alias="summary|runtime|powerState">
            <PowerStateValue key="ON" value="Powered On" />
            <PowerStateValue key="OFF" value="Powered Off" />
            <PowerStateValue key="UNKNOWN" value="Unknown" />
         </PowerState>"""

# PowerState injection for VM moved into AZURE_VIRTUAL_MACHINE_BLOCK below.
# Keep POWER_STATE_BLOCK defined — future kinds may reuse it via CHILD_PATCHES.
CHILD_PATCHES = []


# ---------------------------------------------------------------------------
# Whole-ResourceKind substitutions — replace the entire
# `<ResourceKind key="KIND">...</ResourceKind>` span with a hand-authored
# native-identical literal. Applied FIRST (step 0) so subsequent transforms
# on the same kind are either no-ops or safely target the already-native XML.
#
# Used for kinds whose native shape the Python SDK can't reproduce: nested
# <ResourceGroup>, <PowerState> sibling, identType asymmetry, nameKey integer
# attrs, and `validation=""`. Copy the span verbatim from the native pak's
# describe.xml so diff output against native is zero-line.
#
# Source: sdk_packages/MicrosoftAzureAdapter-818024067771/AzureAdapter/
#         MicrosoftAzureAdapter/conf/describe.xml
# ---------------------------------------------------------------------------

AZURE_VIRTUAL_MACHINE_BLOCK = """<ResourceKind key="AZURE_VIRTUAL_MACHINE" nameKey="14" type="4">
         <ResourceIdentifier dispOrder="1" enum="false" identType="1" key="AZURE_SUBSCRIPTION_ID" length="" nameKey="5" required="true" type="string" />
         <ResourceIdentifier dispOrder="2" enum="false" identType="2" key="AZURE_RESOURCE_GROUP" length="" nameKey="12" required="true" type="string" />
         <ResourceIdentifier dispOrder="3" enum="false" identType="2" key="AZURE_REGION" length="" nameKey="13" required="true" type="string" />
         <ResourceIdentifier dispOrder="4" enum="false" identType="1" key="ID" length="" nameKey="19" required="true" type="string" />
         <PowerState alias="summary|runtime|powerState">
            <PowerStateValue key="ON" value="Powered On" />
            <PowerStateValue key="OFF" value="Powered Off" />
            <PowerStateValue key="UNKNOWN" value="Unknown" />
         </PowerState>
         <ResourceGroup instanced="false" key="CPU" nameKey="100" validation="">
            <ResourceAttribute key="CPU_USAGE" nameKey="101" dashboardOrder="1" dataType="double" defaultMonitored="true" isDiscrete="false" isProperty="false" unit="percent" />
            <ResourceAttribute key="CPU_CRED_REMAINING" nameKey="102" dashboardOrder="2" dataType="double" defaultMonitored="true" isDiscrete="false" isProperty="false" />
            <ResourceAttribute key="CPU_CRED_CONSUMED" nameKey="103" dashboardOrder="3" dataType="double" defaultMonitored="true" isDiscrete="false" isProperty="false" />
         </ResourceGroup>
         <ResourceGroup instanced="false" key="STORAGE" nameKey="104" validation="">
            <ResourceAttribute key="DATA_WRITE_DISK" nameKey="105" dashboardOrder="1" dataType="double" defaultMonitored="true" isDiscrete="false" isProperty="false" unit="bytes" />
            <ResourceAttribute key="DATA_READ_DISK" nameKey="106" dashboardOrder="2" dataType="double" defaultMonitored="true" isDiscrete="false" isProperty="false" unit="bytes" />
            <ResourceAttribute key="DISK_READ_OPERATION" nameKey="107" dashboardOrder="3" dataType="double" defaultMonitored="true" isDiscrete="false" isProperty="false" />
            <ResourceAttribute key="DISK_WRITE_OPERATION" nameKey="108" dashboardOrder="4" dataType="double" defaultMonitored="true" isDiscrete="false" isProperty="false" />
         </ResourceGroup>
         <ResourceGroup instanced="false" key="NETWORK" nameKey="109" validation="">
            <ResourceAttribute key="NETWORK_IN" nameKey="110" dashboardOrder="1" dataType="double" defaultMonitored="true" isDiscrete="false" isProperty="false" unit="bytes" />
            <ResourceAttribute key="NETWORK_OUT" nameKey="111" dashboardOrder="2" dataType="double" defaultMonitored="true" isDiscrete="false" isProperty="false" unit="bytes" />
         </ResourceGroup>
          <ResourceGroup instanced="false" key="general" nameKey="6000" validation="">
            <ResourceAttribute key="FQDN" nameKey="115" dashboardOrder="4" dataType="string" isDiscrete="false" isProperty="true" />
            <ResourceAttribute key="running" nameKey="116" dataType="float" defaultMonitored="true" isDiscrete="false" isRate="false" isProperty="false" />
         </ResourceGroup>
         <ResourceGroup instanced="false" key="summary" nameKey="1100" validation="">
            <ResourceAttribute key="OS_TYPE" nameKey="112" dashboardOrder="1" dataType="string" isDiscrete="false" isProperty="true" />
            <ResourceAttribute key="OS_VHD_URI" nameKey="113" dashboardOrder="2" dataType="string" isDiscrete="false" isProperty="true" />
            <ResourceAttribute key="SIZING_TIER" nameKey="114" dashboardOrder="3" dataType="string" isDiscrete="false" isProperty="true" />
            <ResourceAttribute key="availabilityZones" nameKey="117" dashboardOrder="3" dataType="string" isDiscrete="false" isProperty="true" />
            <ResourceGroup instanced="false" key="runtime" nameKey="160" validation="">
               <ResourceAttribute key="powerState" nameKey="161" dataType="string" defaultMonitored="true" isDiscrete="false" isRate="false" maxVal="" minVal="" isProperty="true" keyAttribute="true" />
            </ResourceGroup>
         </ResourceGroup>
         <!-- Default Service Descriptors -->
         <ResourceGroup instanced="false" key="SERVICE_DESCRIPTORS" nameKey="950" validation="">
            <ResourceAttribute key="AZURE_SUBSCRIPTION_ID" nameKey="5" dashboardOrder="1" dataType="string" isDiscrete="false" isProperty="true" />
            <ResourceAttribute key="AZURE_RESOURCE_GROUP" nameKey="12" dashboardOrder="2" dataType="string" isDiscrete="false" isProperty="true" />
            <ResourceAttribute key="AZURE_REGION" nameKey="13" dashboardOrder="3" dataType="string" isDiscrete="false" isProperty="true" />
            <ResourceAttribute key="AZURE_SERVICE" nameKey="951" dashboardOrder="4" dataType="string" isDiscrete="false" isProperty="true" />
         </ResourceGroup>
      </ResourceKind>"""

BLOCK_SUBSTITUTIONS = {
    "AZURE_VIRTUAL_MACHINE": AZURE_VIRTUAL_MACHINE_BLOCK,
}


# ---------------------------------------------------------------------------
# Dynamic native-describe.xml loader.
#
# Most native-pak-equivalent ResourceKinds have a nested <ResourceGroup> shape
# that the SDK doesn't reproduce (flat <ResourceAttribute> instead). Rather
# than hand-paste ~40 verbatim blocks into BLOCK_SUBSTITUTIONS, we read the
# native describe.xml at patch time and substitute every kind that has a
# native equivalent.
#
# Kinds in BLOCK_SUBSTITUTIONS win — those are manual overrides we hand-tuned.
# Kinds in CUSTOM_KIND_SKIPS have no native equivalent and stay SDK-shaped.
# ---------------------------------------------------------------------------

# Path to native describe.xml (sdk_packages bundles VMware's pak). Override
# with NATIVE_DESCRIBE_XML env var for testing.
DEFAULT_NATIVE_DESCRIBE_XML = os.path.normpath(
    os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "sdk_packages",
        "MicrosoftAzureAdapter-818024067771",
        "AzureAdapter",
        "MicrosoftAzureAdapter",
        "conf",
        "describe.xml",
    )
)

# ResourceKind keys that have NO native equivalent — keep the SDK-emitted
# shape for these. The adapter-instance kind is excluded too because it's
# patched by attribute overrides + rename, not block substitution.
CUSTOM_KIND_SKIPS = {
    "azure_subscription",
    "azure_subnet",
    "azure_recovery_services_vault",
    "azure_log_analytics_workspace",
    # New custom kinds — no native equivalent in the VMware pak
    "azure_logic_workflow",
    "azure_arc_machine",
    "azure_bastion_host",
    "azure_private_endpoint",
    "azure_nat_gateway",
    "azure_compute_snapshot",
    "azure_disk_encryption_set",
    "azure_managed_identity",
    "azure_dns_resolver",
    "azure_backup_vault",
    "azure_sql_virtual_machine",
    "azure_app_service_environment",
    "azure_storage_sync",
    "MicrosoftAzureAdapter_adapter_instance",  # adapter-instance, pre-rename
    "MicrosoftAzureAdapter Instance",          # adapter-instance, post-rename
}


# ---------------------------------------------------------------------------
# ResourceIdentifier blocks to APPEND to the adapter-instance ResourceKind.
# These replicate identifiers the native pak has that our SDK doesn't emit.
# They're purely for upgrade compatibility — Aria Ops's existing adapter
# instances have values for SERVICES/REGIONS in the DB, and dropping those
# identifiers from the schema can make the upgrade reject.
#
# Blocks are idempotent: inject happens only if the identifier key isn't
# already present in the adapter-instance kind.
# ---------------------------------------------------------------------------

SERVICES_BLOCK = """
      <ResourceIdentifier dispOrder="2" key="SERVICES" length="" nameKey="870" required="false" type="string" identType="2" enum="true" enumMultiSelect="true" advanced="false">
         <enumUnselected displayName="All" nameKey="865"/>
         <enum value="virtualMachines" nameKey="871" />
         <enum value="sqlServers" nameKey="872" />
         <enum value="cosmosDb" nameKey="873" />
         <enum value="loadBalancer" nameKey="874" />
         <enum value="networkInterfaces" nameKey="875" />
         <enum value="postgres" nameKey="876" />
         <enum value="mysql" nameKey="877" />
         <enum value="kubernetes" nameKey="878" />
         <enum value="vmScaleSets" nameKey="879" />
         <enum value="virtualNetwork" nameKey="880" />
         <enum value="vpnGateway" nameKey="881" />
         <enum value="appGateway" nameKey="882" />
         <enum value="webApps" nameKey="883" />
         <enum value="diskStorage" nameKey="884" />
         <enum value="storageAccounts" nameKey="886" />
         <enum value="serviceBus" nameKey="885" />
         <enum value="dataLakeAnalytics" nameKey="890" />
         <enum value="synapseAnalyticsWorkspace" nameKey="891" />
         <enum value="synapseAnalyticsSQLPool" nameKey="892" />
         <enum value="synapseAnalyticsBigDataPool" nameKey="893" />
         <enum value="hdInsight" nameKey="894" />
         <enum value="kustoClusters" nameKey="895" />
         <enum value="dataFactory" nameKey="896" />
         <enum value="kustoDatabases" nameKey="897" />
         <enum value="purviewAccounts" nameKey="2037" />
         <enum value="botServices" nameKey="2038" />
         <enum value="searchServices" nameKey="2039" />
         <enum value="analysisServices" nameKey="2040" />
         <enum value="cognitiveServicesAccounts" nameKey="2041" />
         <enum value="powerBIEmbedded" nameKey="2042" />
         <enum value="machineLearning" nameKey="2043" />
         <enum value="streamAnalyticsJobs" nameKey="2045" />
         <enum value="streamAnalyticsClusters" nameKey="2046" />
         <enum value="dataBox" nameKey="2047" />
         <enum value="digitalTwins" nameKey="2048" />
         <enum value="iotCentral" nameKey="2049" />
         <enum value="apiManagement" nameKey="2050" />
         <enum value="spatialAnchors" nameKey="2052" />
         <enum value="ddosProtectionPlan" nameKey="2053" />
         <enum value="iotHub" nameKey="2054" />
         <enum value="automation" nameKey="2055" />
         <enum value="timeSeriesInsights" nameKey="2056" />
         <enum value="eventGridDomain" nameKey="2057" />
         <enum value="eventGridTopic" nameKey="2058" />
         <enum value="eventGridSubscription" nameKey="2059" />
         <enum value="publicIpAddresses" nameKey="2200" />
         <enum value="functionApp" nameKey="2201" />
         <enum value="networkWatchers" nameKey="2202" />
         <enum value="cacheRedis" nameKey="2203" />
         <enum value="sqlManagedInstances" nameKey="2204" />
         <enum value="mariaDbServer" nameKey="2205" />
         <enum value="computeDomains" nameKey="2206" />
         <enum value="batchAccount" nameKey="2207" />
         <enum value="computeHostGroups" nameKey="2208" />
         <enum value="containerGroups" nameKey="2209" />
         <enum value="containerRegisteries" nameKey="2210" />
         <enum value="dataLakeStore" nameKey="2211" />
         <enum value="appConfiguration" nameKey="2212" />
         <enum value="openshiftClusters" nameKey="2213" />
         <enum value="routeTable" nameKey="2214" />
         <enum value="dnsZones" nameKey="2215" />
         <enum value="privateDnsZones" nameKey="2216" />
         <enum value="expressRouteCirtuits" nameKey="2217" />
         <enum value="trafficManagerProfiles" nameKey="2218" />
         <enum value="singnalrServices" nameKey="2219" />
         <enum value="firewalls" nameKey="2220" />
         <enum value="frontDoors" nameKey="2221" />
         <enum value="cdnProfile" nameKey="2222" />
         <enum value="cdnProfileEndpoints" nameKey="2223" />
         <enum value="virtualWan" nameKey="2224" />
         <enum value="keyVaults" nameKey="2225" />
         <enum value="natAppAccount" nameKey="2226" />
         <enum value="natAppAccountCapacityPools" nameKey="2227" />
         <enum value="natAppAccountCapacityPoolVolumn" nameKey="2228" />
         <enum value="mediaServices" nameKey="2229" />
         <enum value="mediaServicesLiveEvents" nameKey="2230" />
         <enum value="mediaServicesStreamingGep" nameKey="2231" />
         <enum value="notificationHubs" nameKey="2232" />
         <enum value="notificationHubsNamespaces" nameKey="2233" />
         <enum value="eventHubsNamespaces" nameKey="2234" />
         <enum value="networkSecurityGroup" nameKey="2243" />
         <enum value="appServicePlan" nameKey="2244" />
         <enum value="availabilitysets" nameKey="2245" />
         <enum value="proximityPlacementGroups" nameKey="2246" />
      </ResourceIdentifier>"""

REGIONS_BLOCK = """
      <ResourceIdentifier dispOrder="3" key="REGIONS" length="" nameKey="802" required="false" type="string" identType="2" enum="true" enumMultiSelect="true" advanced="false">
         <enumUnselected displayName="All" nameKey="866"/>
         <enum value="westus" nameKey="803" />
         <enum value="westus2" nameKey="804" />
         <enum value="centralus" nameKey="805" />
         <enum value="eastus" nameKey="806" />
         <enum value="eastus2" nameKey="807" />
         <enum value="northcentralus" nameKey="808" />
         <enum value="southcentralus" nameKey="809" />
         <enum value="westcentralus" nameKey="810" />
         <enum value="canadacentral" nameKey="811" />
         <enum value="canadaeast" nameKey="812" />
         <enum value="brazilsouth" nameKey="813" />
         <enum value="northeurope" nameKey="814" />
         <enum value="westeurope" nameKey="815" />
         <enum value="uksouth" nameKey="816" />
         <enum value="ukwest" nameKey="817" />
         <enum value="francecentral" nameKey="818" />
         <enum value="francesouth" nameKey="819" />
         <enum value="eastasia" nameKey="820" />
         <enum value="southeastasia" nameKey="821" />
         <enum value="japaneast" nameKey="822" />
         <enum value="japanwest" nameKey="823" />
         <enum value="australiaeast" nameKey="824" />
         <enum value="australiasoutheast" nameKey="825" />
         <enum value="australiacentral" nameKey="826" />
         <enum value="australiacentral2" nameKey="827" />
         <enum value="centralindia" nameKey="828" />
         <enum value="southindia" nameKey="829" />
         <enum value="westindia" nameKey="830" />
         <enum value="koreacentral" nameKey="831" />
         <enum value="koreasouth" nameKey="832" />
         <enum value="southafricanorth" nameKey="833" />
         <enum value="germanywestcentral" nameKey="834" />
         <enum value="norwayeast" nameKey="835" />
         <enum value="switzerlandnorth" nameKey="836" />
         <enum value="uaenorth" nameKey="837" />
         <enum value="eastus2euap" nameKey="858" />
         <enum value="southafricawest" nameKey="859" />
         <enum value="germanynorth" nameKey="860" />
         <enum value="norwaywest" nameKey="861" />
         <enum value="switzerlandwest" nameKey="862" />
         <enum value="uaecentral" nameKey="863" />
         <enum value="brazilsoutheast" nameKey="864" />
         <enum value="westus3" nameKey="867" />
         <enum value="southcentralindia" nameKey="868" />
         <enum value="swedencentral" nameKey="869" />
         <enum value="jioindiawest" nameKey="901" />
         <enum value="jioindiacentral" nameKey="902" />
         <enum value="swedensouth" nameKey="903" />
         <enum value="centraluseuap" nameKey="904" />
      </ResourceIdentifier>"""

# List of (identifier_key, block) pairs to append to the adapter-instance kind.
# Uses the SDK-emitted adapter kind name (pre-rename).
ADAPTER_INSTANCE_APPEND = [
    ("SERVICES", SERVICES_BLOCK),
    ("REGIONS", REGIONS_BLOCK),
]

# The adapter-instance ResourceKind key at the time these appends run
# (before rename). Keep in sync with the first key in RENAME_KINDS.
ADAPTER_INSTANCE_KIND = "MicrosoftAzureAdapter_adapter_instance"

# Attributes to inject onto the root <AdapterKind> element. Matches native pak.
ROOT_ATTRS = {
    "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "xsi:schemaLocation": "http://schemas.vmware.com/vcops/schema describeSchema.xsd",
}


# ---------------------------------------------------------------------------
# Core patching helpers
# ---------------------------------------------------------------------------

# Matches XML attributes including namespace-prefixed ones (e.g., xmlns:xsi).
# Without the colon, we'd mis-parse xmlns:xsi="..." as xsi="..." and break
# idempotency on root-element patches.
_ATTR_RE = re.compile(r'([\w:]+)="([^"]*)"')


def _substitute_resource_kind(content: str, kind: str, block: str) -> tuple[str, int]:
    """Replace the entire `<ResourceKind key="KIND">...</ResourceKind>` span
    with `block`. Idempotent: if the literal block is already a substring of
    `content`, returns unchanged.
    """
    if block in content:
        return content, 0

    open_re = re.compile(
        r'<ResourceKind\s+key="' + re.escape(kind) + r'"[^>]*>'
    )
    match = open_re.search(content)
    if not match:
        return content, 0

    close_tag = "</ResourceKind>"
    close_start = content.find(close_tag, match.end())
    if close_start == -1:
        return content, 0
    full_end = close_start + len(close_tag)

    return content[:match.start()] + block + content[full_end:], 1


def _extract_custom_flat_attrs(sdk_content: str, kind: str, native_span: str) -> list:
    """Find ResourceAttribute children in the SDK-emitted block for `kind`
    that are flat (no pipe in key) AND not present in the native span.

    Returned list is the raw XML elements (with whitespace). They represent
    extensions we've added to a native-equivalent kind that the dynamic
    loader's substitution would otherwise erase.

    Pipe-keyed attrs are intentionally skipped — those are SDK-emulated
    nested-group fields that the native span already provides via real
    nested ResourceGroup elements.
    """
    open_re = re.compile(
        r'<ResourceKind\s+key="' + re.escape(kind) + r'"[^>]*>'
    )
    sdk_match = open_re.search(sdk_content)
    if not sdk_match:
        return []
    sdk_close = sdk_content.find("</ResourceKind>", sdk_match.end())
    if sdk_close == -1:
        return []
    sdk_body = sdk_content[sdk_match.end():sdk_close]

    # Keys that already exist in the native span — skip duplicates.
    native_keys = set(re.findall(
        r'<ResourceAttribute\b[^>]*?\bkey="([^"]+)"', native_span
    ))

    custom = []
    for m in re.finditer(r'<ResourceAttribute\b[^>]*/>', sdk_body):
        elem = m.group(0)
        key_match = re.search(r'\bkey="([^"]+)"', elem)
        if not key_match:
            continue
        key = key_match.group(1)
        if "|" in key:
            continue
        if key in native_keys:
            continue
        custom.append(elem)
    return custom


def _inject_custom_attrs(content: str, kind: str, attrs: list) -> str:
    """Insert `attrs` (list of <ResourceAttribute .../> XML elements) just
    before </ResourceKind> in the block for `kind`. Idempotent: skips if all
    keys are already present in the block.
    """
    if not attrs:
        return content
    open_re = re.compile(
        r'<ResourceKind\s+key="' + re.escape(kind) + r'"[^>]*>'
    )
    match = open_re.search(content)
    if not match:
        return content
    close_start = content.find("</ResourceKind>", match.end())
    if close_start == -1:
        return content

    body = content[match.end():close_start]
    # Filter out attrs whose keys already appear in the body (idempotent re-runs).
    fresh = []
    for attr in attrs:
        key_match = re.search(r'\bkey="([^"]+)"', attr)
        if not key_match:
            continue
        if f'key="{key_match.group(1)}"' in body:
            continue
        fresh.append(attr)
    if not fresh:
        return content

    injection = (
        "\n         <!-- Custom extensions (preserved across native substitution) -->\n         "
        + "\n         ".join(fresh)
        + "\n      "
    )
    return content[:close_start] + injection + content[close_start:]


def _load_native_resourcekinds(native_xml_path: str) -> dict:
    """Read the native pak's describe.xml and return a dict mapping each
    ResourceKind key to its raw `<ResourceKind ...>...</ResourceKind>` span
    (or, for self-closing kinds, the `<ResourceKind ... />` element itself).

    Uses regex (not ET) so we preserve the exact whitespace from the source —
    important because Aria Ops parses describe.xml byte-for-byte and any
    SDK-vs-native diff has bitten us before.

    Critical: self-closing tags (`<ResourceKind .../>`) MUST be detected
    explicitly. Without that, the regex would happily match the self-closer
    as an "open" tag and then look for the next `</ResourceKind>` — which
    belongs to a LATER kind in the file. That overlong span, substituted
    into our pak, creates a duplicate of the next kind. (Symptom hit on
    AZURE_SERVICES_FROM_XML which is self-closing in the native pak; the
    bogus span dragged AZURE_PUBLIC_IPADDRESSES along with it.)
    """
    with open(native_xml_path, "r", encoding="utf-8") as f:
        native_content = f.read()

    kinds = {}
    open_re = re.compile(
        r'<ResourceKind\s+key="([^"]+)"[^>]*>'
    )
    for match in open_re.finditer(native_content):
        key = match.group(1)
        # The matched text includes the closing `>`. If the char before `>`
        # is `/`, this is a self-closing element with no body or close tag.
        is_self_closing = match.group(0).rstrip(">").endswith("/")
        if is_self_closing:
            kinds[key] = native_content[match.start():match.end()]
        else:
            close_start = native_content.find("</ResourceKind>", match.end())
            if close_start == -1:
                continue
            full_end = close_start + len("</ResourceKind>")
            kinds[key] = native_content[match.start():full_end]

    return kinds


def _apply_attr_patch(content: str, kind: str, new_attrs: dict) -> tuple[str, int]:
    """Replace or add attributes on `<ResourceKind key="KIND" ...>` opening tag.

    Removes any SDK-emitted attribute whose name matches one of new_attrs.keys(),
    then prepends the new attributes right after the `key="..."` attribute.
    """
    pattern = re.compile(
        r'(<ResourceKind\s+key="' + re.escape(kind) + r'")([^>]*?)(/?>)'
    )

    def substitute(match):
        head = match.group(1)           # <ResourceKind key="KIND"
        rest = match.group(2)           # everything else before >
        close = match.group(3)          # > or />

        # Parse existing attributes and strip the ones we're overriding.
        preserved = []
        for attr_match in _ATTR_RE.finditer(rest):
            name = attr_match.group(1)
            if name in new_attrs:
                continue
            preserved.append(attr_match.group(0))

        # Build the new attribute block: our overrides first (in insertion
        # order), then whatever the SDK emitted that we didn't override.
        our_attrs = " ".join(f'{k}="{v}"' for k, v in new_attrs.items())
        preserved_attrs = " ".join(preserved)

        parts = [head]
        if our_attrs:
            parts.append(" " + our_attrs)
        if preserved_attrs:
            parts.append(" " + preserved_attrs)
        parts.append(close)
        return "".join(parts)

    new_content, count = pattern.subn(substitute, content)
    return new_content, count


def _apply_child_patch(content: str, kind: str, child_tag: str, block: str) -> tuple[str, int]:
    """Insert `block` as the first child of `<ResourceKind key="KIND">`, unless
    a child with `child_tag` is already present inside it."""
    open_re = re.compile(
        r'(<ResourceKind\s+key="' + re.escape(kind) + r'"[^>]*>)'
    )
    match = open_re.search(content)
    if not match:
        return content, 0

    open_end = match.end()
    # Look for the matching </ResourceKind> to get the body
    close_start = content.find("</ResourceKind>", open_end)
    if close_start == -1:
        return content, 0

    body = content[open_end:close_start]
    if f"<{child_tag}" in body:
        # Already present — idempotent, skip
        return content, 0

    injected = content[:open_end] + block + content[open_end:]
    return injected, 1


def _apply_identifier_attr_patch(content: str, ident_key: str, new_attrs: dict) -> tuple[str, int]:
    """Replace/add attributes on the first `<ResourceIdentifier ... key="KEY" ...>` match.

    The SDK emits attributes in a fixed order; we don't care about order —
    we strip any existing attribute whose name we're overriding and insert
    our values. The `key=` attribute itself is left untouched.
    """
    pattern = re.compile(
        r'(<ResourceIdentifier\b)([^>]*?\bkey="' + re.escape(ident_key) + r'"[^>]*?)(/?>)'
    )

    def substitute(match):
        head = match.group(1)         # <ResourceIdentifier
        rest = match.group(2)         # all attrs including key="..."
        close = match.group(3)        # /> or >

        kept = []
        for attr_match in _ATTR_RE.finditer(rest):
            name = attr_match.group(1)
            if name in new_attrs:
                continue
            kept.append(attr_match.group(0))

        our_attrs = " ".join(f'{k}="{v}"' for k, v in new_attrs.items())
        kept_attrs = " ".join(kept)

        parts = [head]
        if kept_attrs:
            parts.append(" " + kept_attrs)
        if our_attrs:
            parts.append(" " + our_attrs)
        parts.append(close)
        return "".join(parts)

    # Replace only the first match (scoped to the adapter-instance ResourceKind)
    new_content, count = pattern.subn(substitute, content, count=1)
    return new_content, count


def _append_identifier_block(content: str, parent_kind: str, ident_key: str, block: str) -> tuple[str, int]:
    """Insert `block` just before the closing `</ResourceKind>` of the named
    kind. Idempotent: skipped if a ResourceIdentifier with key=ident_key
    already lives inside that ResourceKind.
    """
    open_re = re.compile(
        r'(<ResourceKind\s+key="' + re.escape(parent_kind) + r'"[^>]*>)'
    )
    match = open_re.search(content)
    if not match:
        return content, 0

    open_end = match.end()
    close_start = content.find("</ResourceKind>", open_end)
    if close_start == -1:
        return content, 0

    body = content[open_end:close_start]
    if f'key="{ident_key}"' in body:
        return content, 0  # already present

    injected = content[:close_start] + block + "\n   " + content[close_start:]
    return injected, 1


def _patch_root_attrs(content: str, new_attrs: dict) -> tuple[str, int]:
    """Inject/override attributes on the root <AdapterKind ...> opening tag."""
    pattern = re.compile(r'(<AdapterKind\b)([^>]*?)(>)')
    match = pattern.search(content)
    if not match:
        return content, 0

    head = match.group(1)   # <AdapterKind
    rest = match.group(2)   # existing attrs
    close = match.group(3)  # >

    kept = []
    for attr_match in _ATTR_RE.finditer(rest):
        name = attr_match.group(1)
        if name in new_attrs:
            continue
        kept.append(attr_match.group(0))

    our_attrs = " ".join(f'{k}="{v}"' for k, v in new_attrs.items())
    kept_attrs = " ".join(kept)

    parts = [head]
    if kept_attrs:
        parts.append(" " + kept_attrs)
    if our_attrs:
        parts.append(" " + our_attrs)
    parts.append(close)
    new_tag = "".join(parts)

    # Did the root tag actually change? (skip no-op writes for idempotency)
    if new_tag == match.group(0):
        return content, 0
    return content[:match.start()] + new_tag + content[match.end():], 1


def _rename_kind(content: str, old_key: str, new_key: str) -> tuple[str, int]:
    """Rename every `<ResourceKind key="old_key">` occurrence to new_key.
    Does NOT touch other XML (the adapter instance kind doesn't appear as a
    child/parent reference inside describe.xml itself).
    """
    pattern = re.compile(
        r'(<ResourceKind\s+key=")' + re.escape(old_key) + r'(")'
    )
    return pattern.subn(r'\1' + new_key + r'\2', content)


def patch_describe_xml(filepath: str) -> int:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    original = content
    applied = 0

    # 0a. Manual whole-ResourceKind substitutions (hand-tuned overrides).
    # Runs first so any kind we've explicitly hand-edited wins over the
    # dynamic native-loader below.
    for kind, block in BLOCK_SUBSTITUTIONS.items():
        content, count = _substitute_resource_kind(content, kind, block)
        if count > 0:
            applied += count
            print(f"  [PATCHED] substitute ResourceKind {kind} with native literal (manual)")
        else:
            print(f"  [SKIP]    substitute {kind} (already native or ResourceKind not found)")

    # 0b. Dynamic substitution from the native pak's describe.xml.
    # For every ResourceKind in our SDK-emitted XML that has a same-keyed
    # entry in the native describe.xml, replace it with the native span
    # verbatim. Skips kinds in BLOCK_SUBSTITUTIONS (manual overrides win)
    # and CUSTOM_KIND_SKIPS (no native equivalent).
    #
    # Critical: native substitution would discard any SDK-emitted custom
    # ResourceAttribute children we added via define_*_property/metric
    # (e.g., AZURE_DEDICATE_HOST has ~50 custom attrs like hourly_rate,
    # vm_size_summary, memory tracking, cost, health). We preserve these
    # by extracting them BEFORE substitution and re-injecting them
    # immediately after.
    native_xml_path = os.environ.get("NATIVE_DESCRIBE_XML", DEFAULT_NATIVE_DESCRIBE_XML)
    if os.path.exists(native_xml_path):
        native_kinds = _load_native_resourcekinds(native_xml_path)
        dynamic_skips = set(BLOCK_SUBSTITUTIONS.keys()) | CUSTOM_KIND_SKIPS
        substituted_dyn = 0
        preserved_total = 0
        for kind, native_span in native_kinds.items():
            if kind in dynamic_skips:
                continue
            # Capture our SDK's flat custom attrs for this kind BEFORE the substitution.
            custom_attrs = _extract_custom_flat_attrs(content, kind, native_span)
            content, count = _substitute_resource_kind(content, kind, native_span)
            if count > 0:
                applied += count
                substituted_dyn += 1
                if custom_attrs:
                    content = _inject_custom_attrs(content, kind, custom_attrs)
                    preserved_total += len(custom_attrs)
                    print(f"  [PATCHED] preserved {len(custom_attrs)} custom attr(s) "
                          f"on {kind} after native substitution")
        print(f"  [PATCHED] dynamic native loader: {substituted_dyn} kinds substituted, "
              f"{preserved_total} custom attrs preserved "
              f"(from {native_xml_path})")
    else:
        print(f"  [WARN]    native describe.xml not found at {native_xml_path}; "
              "dynamic loader skipped — only BLOCK_SUBSTITUTIONS will apply")

    # 1. Attribute patches (strip any conflicting existing attrs, then inject)
    for kind, attrs in ATTR_PATCHES.items():
        content, count = _apply_attr_patch(content, kind, attrs)
        attr_preview = ", ".join(f"{k}={v}" for k, v in attrs.items())
        if count > 0:
            applied += count
            print(f"  [PATCHED] {kind}: set {attr_preview}")
        else:
            print(f"  [SKIP]    {kind}: ResourceKind not found")

    # 2. Child-element injections (PowerState, etc.)
    for patch in CHILD_PATCHES:
        content, count = _apply_child_patch(
            content, patch["kind"], patch["child_tag"], patch["block"]
        )
        if count > 0:
            applied += count
            print(f"  [PATCHED] {patch['description']}")
        else:
            print(f"  [SKIP]    {patch['description']} (already present or ResourceKind missing)")

    # 3. ResourceIdentifier attribute overrides (identType fixes, etc.)
    for ident_key, attrs in IDENTIFIER_ATTR_PATCHES.items():
        content, count = _apply_identifier_attr_patch(content, ident_key, attrs)
        attr_preview = ", ".join(f"{k}={v}" for k, v in attrs.items())
        if count > 0:
            applied += count
            print(f"  [PATCHED] identifier {ident_key}: set {attr_preview}")
        else:
            print(f"  [SKIP]    identifier {ident_key}: not found")

    # 4. Append missing ResourceIdentifier blocks (SERVICES, REGIONS) to the
    # adapter-instance ResourceKind. Must run BEFORE the rename step below
    # because we target the SDK's original key.
    for ident_key, block in ADAPTER_INSTANCE_APPEND:
        content, count = _append_identifier_block(
            content, ADAPTER_INSTANCE_KIND, ident_key, block
        )
        if count > 0:
            applied += count
            print(f"  [PATCHED] append ResourceIdentifier {ident_key} to adapter-instance kind")
        else:
            print(f"  [SKIP]    append {ident_key} (already present or parent kind missing)")

    # 5. Root <AdapterKind> attribute injection (xsi:schemaLocation, xmlns:xsi)
    content, count = _patch_root_attrs(content, ROOT_ATTRS)
    if count > 0:
        applied += count
        print(f"  [PATCHED] root AdapterKind: {', '.join(ROOT_ATTRS)}")
    else:
        print(f"  [SKIP]    root AdapterKind attrs (already set)")

    # 6. ResourceKind renames (applied last so attribute patches can target
    # the SDK's original key). Each rename is idempotent via check before sub.
    for old_key, new_key in RENAME_KINDS.items():
        content, count = _rename_kind(content, old_key, new_key)
        if count > 0:
            applied += count
            print(f"  [PATCHED] rename ResourceKind: {old_key} -> {new_key}")
        else:
            print(f"  [SKIP]    rename {old_key} (not found — already renamed?)")

    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\n{applied} patches applied to {filepath}")
    else:
        print(f"\nNo patches needed for {filepath}")

    return applied


def main():
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(script_dir, "..", "Azure-Native-Build", "conf", "describe.xml"),
            os.path.join(script_dir, "..", "conf", "describe.xml"),
            "conf/describe.xml",
        ]
        filepath = None
        for c in candidates:
            if os.path.exists(c):
                filepath = c
                break
        if filepath is None:
            print("Could not find describe.xml. Pass the path as an argument:")
            print(f"  python {sys.argv[0]} path/to/describe.xml")
            sys.exit(1)

    print(f"Patching: {os.path.abspath(filepath)}")
    print()
    patch_describe_xml(filepath)


if __name__ == "__main__":
    main()
