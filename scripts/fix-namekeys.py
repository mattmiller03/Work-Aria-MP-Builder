#!/usr/bin/env python3
"""
fix-namekeys.py — repair kind display names on native-substituted kinds.
 
Fixes the "label impostor" defect (2026-07-10): ResourceKind spans copied
verbatim from the native pak carry the NATIVE pak's nameKey numbering, but
our pak ships the SDK-generated resources.properties, which numbers its
entries completely differently. Result: native-substituted kinds whose
nameKey collides with an SDK entry display a WRONG label everywhere the UI
groups by type (inventory tree, search dropdowns, relationship clusters):
 
    AZURE_STORAGE_DISK   nameKey=31  -> "Network In"
    AZURE_NW_INTERFACE   nameKey=18  -> "Tenant ID"
    AZURE_RESOURCE_GROUP nameKey=12  -> "AZURE_STANDARD_ACCOUNT"
    ... (~25 kinds, per the 2026-07-10 nameKey audit)
 
Kinds whose native nameKey has NO SDK entry ("NO ENTRY" in the audit) fall
back to an Aria-derived name and display acceptably — wrong entries are the
problem, not missing ones. This script therefore:
 
  1. For every kind in KIND_LABELS found in describe.xml, allocates a fresh
     nameKey in the 30000+ range (guaranteed collision-free vs both SDK and
     native numbering), rewrites the kind's nameKey attribute, and appends
     "NNNNN = <label>" to the pak's resources.properties.
  2. Leaves kinds not in the table untouched.
 
Idempotent: if a kind already points at a 30000-range key whose entry equals
the desired label, it is skipped on re-runs.
 
Runs AFTER merge-custom-attrs.py and BEFORE cleanup-describe-xml.py
(cleanup's --validate gate then proves the result).
 
Usage:
    python3.12 scripts/fix-namekeys.py <describe.xml> [<resources.properties>]
 
If the properties path is omitted it is derived as
<describe_dir>/resources/resources.properties.
"""
 
import os
import re
import sys
from lxml import etree
 
NS = "http://schemas.vmware.com/vcops/schema"
BASE_KEY = 30000  # allocation floor for our label keys
 
# ---------------------------------------------------------------------------
# Curated display names. Sourced from the production native pak's inventory
# tree (2026-07-10) where visible; sensible expansions elsewhere. Only kinds
# with COLLIDING nameKeys strictly need entries, but harmless to include
# more — NO-ENTRY kinds gain a stable label instead of a derived fallback.
# Add/adjust freely; the script only touches kinds present in describe.xml.
# ---------------------------------------------------------------------------
KIND_LABELS = {
    # --- colliding-nameKey kinds (the impostors; from the audit table) ---
    "AZURE_RESOURCE_GROUP": "Azure Resource Group",
    "AZURE_STORAGE_DISK": "Azure Disk",
    "AZURE_NW_INTERFACE": "Azure Network Interface",
    "AZURE_VIRTUAL_NETWORK": "Azure Virtual Network",
    "AZURE_STORAGE_ACCOUNT": "Azure Storage Account",
    "AZURE_LB": "Azure Load Balancer",
    "AZURE_SQL_SERVER": "Azure SQL Server",
    "AZURE_SQL_DATABASE": "Azure SQL Database",
    "AZURE_APP_SERVICE": "Azure App Service",
    "AZURE_DB_ACCOUNT": "Azure Cosmos DB Account",
    "AZURE_POSTGRESQL_SERVER": "Azure PostgreSQL Server",
    "AZURE_MYSQL_SERVER": "Azure MySQL Server",
    "AZURE_VIRTUAL_SCALESET": "Azure VM Scale Set",
    "AZURE_VIRTUAL_SCALESET_INSTANCE": "Azure VM Scale Set Instance",
    "AZURE_APPLICATION_GATEWAY": "Azure Application Gateway",
    "AZURE_VIRTUAL_NETWORK_GATEWAY": "Azure Virtual Network Gateway",
    "AZURE_KUBERNATE_CLUSTER": "Azure Kubernetes Cluster",
    "AZURE_SERVICE_BUS": "Azure Service Bus",
    "AZURE_HDINSIGHT": "Azure HDInsight",
    "AZURE_DATA_EXPLORER_CLUSTER": "Azure Data Explorer Cluster",
    "AZURE_DATA_EXPLORER_DATABASE": "Azure Data Explorer Database",
    "AZURE_DATA_FACTORY": "Azure Data Factory",
    "AZURE_DATA_LAKE_ANALYTICS": "Azure Data Lake Analytics",
    "AZURE_SYNAPSE_ANALYTICS_WORKSPACE": "Azure Synapse Analytics Workspace",
    "AZURE_SYNAPSE_ANALYTICS_SQL_POOL": "Azure Synapse SQL Pool",
    "AZURE_SYNAPSE_ANALYTICS_BIGDATA_POOL": "Azure Synapse Big Data Pool",
 
    # --- NO-ENTRY kinds worth pinning to stable labels (optional set) ---
    "AZURE_COMPUTE_HOSTGROUPS": "Azure Dedicated Host Group",
    "AZURE_DEDICATE_HOST": "Azure Dedicated Host",
    "AZURE_PUBLIC_IPADDRESSES": "Azure Public IP Address",
    "AZURE_EXPRESSROUTE_CIRCUITS": "Azure ExpressRoute Circuit",
    "AZURE_KEY_VAULTS": "Azure Key Vault",
    "AZURE_FUNCTIONS_APP": "Azure Function",
    "AZURE_APP_SERVICE_PLAN": "Azure App Service Plan",
    "AZURE_NETWORK_SECURITY_GROUP": "Azure Network Security Group",
    "AZURE_ROUTE_TABLES": "Azure Route Table",
    "AZURE_DNS_ZONES": "Azure DNS Zone",
    "AZURE_PRIVATE_DNSZONES": "Azure Private DNS Zone",
    "AZURE_NETWORK_WATCHERS": "Azure Network Watcher",
    "AZURE_CONTAINER_REGISTRIES": "Azure Container Registry",
    "AZURE_AVAILABILITY_SETS": "Azure Availability Set",
    "AZURE_AUTOMATION": "Azure Automation Account",
    "AZURE_CACHE_REDIS": "Azure Cache for Redis",
    "AZURE_EVENTHUBS_NAMESPACES": "Azure Event Hubs Namespace",
    "AZURE_COGNITIVE_SERVICES_ACCOUNTS": "Azure Cognitive Services Account",
    "AZURE_SEARCH_SERVICES": "Azure AI Search Service",
    "AZURE_SQL_MANAGEDINSTANCES": "Azure SQL Managed Instance",
    "AZURE_SQL_MANAGEDINSTANCES_DATABASE": "Azure SQL Managed Instance Database",
    "AZURE_REGION": "Azure Region",
    "AZURE_REGION_PER_SUB": "Azure Region Per Subscription",
    "AZURE_WORLD": "Azure World",
    "AZURE_VIRTUAL_HUBS": "Azure Virtual Hub",
}
 
 
def q(tag: str) -> str:
    return f"{{{NS}}}{tag}"
 
 
def load_resources(path: str) -> dict:
    entries = {}
    if os.path.exists(path):
        for line in open(path, encoding="utf-8", errors="replace"):
            m = re.match(r"^(\d+)\s*=\s*(.*)$", line.strip())
            if m:
                entries[int(m.group(1))] = m.group(2)
    return entries
 
 
def main(describe_path: str, resources_path: str) -> None:
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(describe_path, parser)
    root = tree.getroot()
 
    resources = load_resources(resources_path)
    next_key = max([BASE_KEY - 1] + [k for k in resources if k >= BASE_KEY]) + 1
 
    remapped = 0
    skipped = 0
    appended = []  # (key, label) pairs to add to resources.properties
 
    for rk in root.iter(q("ResourceKind")):
        kind = rk.get("key")
        label = KIND_LABELS.get(kind)
        if label is None:
            continue
 
        current = rk.get("nameKey", "")
        # Idempotency: already pointing at one of our keys with the right label
        if current.isdigit() and int(current) >= BASE_KEY \
                and resources.get(int(current)) == label:
            skipped += 1
            continue
 
        # Reuse an existing 30000-range entry with this exact label if present
        existing = next((k for k, v in resources.items()
                         if k >= BASE_KEY and v == label), None)
        if existing is not None:
            new_key = existing
        else:
            new_key = next_key
            next_key += 1
            resources[new_key] = label
            appended.append((new_key, label))
 
        rk.set("nameKey", str(new_key))
        remapped += 1
 
    if remapped:
        tree.write(describe_path, encoding="UTF-8", xml_declaration=True)
 
    if appended:
        with open(resources_path, "a", encoding="utf-8") as f:
            f.write("\n# --- Kind display names (added by fix-namekeys.py) ---\n")
            for k, v in appended:
                f.write(f"{k} = {v}\n")
 
    print(
        f"[NAMEKEYS] {describe_path}\n"
        f"  kinds remapped          : {remapped}\n"
        f"  kinds already correct   : {skipped}\n"
        f"  resource entries added  : {len(appended)}\n"
        f"  resources file          : {resources_path}"
    )
 
 
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    describe = sys.argv[1]
    if len(sys.argv) >= 3:
        resources = sys.argv[2]
    else:
        resources = os.path.join(os.path.dirname(describe),
                                 "resources", "resources.properties")
    if not os.path.exists(resources):
        print(f"ERROR: resources.properties not found at {resources}")
        sys.exit(1)
    main(describe, resources)
 