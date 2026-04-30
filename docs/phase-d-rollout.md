# Phase D Rollout — Build, Push, Install Commands

Copy-paste runbook for each Phase D cycle. Each cycle adds more ResourceKinds and re-installs the pak. Goal: APPLY_ADAPTER (step 16/20) reaches SUCCESS each cycle.

Plan reference: [`C:\Users\mille\.claude\plans\resume-previous-work-on-reflective-conway.md`](.) (local — Claude's plan file).

## Pre-flight (do once on the MP Builder server)

```bash
cd /opt/aria/Aria-MP-Builder

# Pull the latest committed changes from this repo
git fetch origin
git reset --hard origin/main         # safer than pull — see memory note about filter-repo + pull
```

## Cycle D.2 — 24 ResourceKinds (3 → 24)

State after this cycle: Subscription + RG + VM + 21 more first-class kinds. The dynamic native-loader in `scripts/patch-describe-xml.py` substitutes 20 native-equivalents with verbatim native XML; 4 customs (`azure_subscription`, `azure_subnet`, `azure_recovery_services_vault`, `azure_log_analytics_workspace`) keep SDK-emitted shape.

```bash
# 1. Purge stale azure adapter images (mp-build's cache lies — see memory)
sudo docker images | grep -iE 'azure|microsoft' | awk '{print $3}' | xargs -r sudo docker rmi --force

# 2. Build the pak
mkdir -p debug
bash scripts/build-pak.sh 2>&1 | tee debug/build.log

# 3. Verify the pak has 24 kinds and the dynamic loader fired
PAK=$(ls -t Azure-Native-Build/build/*.pak | head -1)
echo "Pak: $PAK"
rm -rf /tmp/pak-inspect && mkdir /tmp/pak-inspect && cd /tmp/pak-inspect
unzip -q "$PAK" && unzip -q adapter.zip
echo "ResourceKind count: $(grep -c '<ResourceKind ' MicrosoftAzureAdapter/conf/describe.xml)"
echo "(expected: 24)"
grep '\[PATCHED\] dynamic native loader' /opt/aria/Aria-MP-Builder/debug/build.log

# 4. Spot-check a few kinds got the native shape
for kind in AZURE_STORAGE_DISK AZURE_DEDICATE_HOST AZURE_APP_SERVICE; do
  echo "=== $kind: diff vs native ==="
  diff <(sed -n "/ResourceKind key=\"$kind\"/,/<\\/ResourceKind>/p" MicrosoftAzureAdapter/conf/describe.xml) \
       <(sed -n "/ResourceKind key=\"$kind\"/,/<\\/ResourceKind>/p" \
         /opt/aria/Aria-MP-Builder/sdk_packages/MicrosoftAzureAdapter-818024067771/AzureAdapter/MicrosoftAzureAdapter/conf/describe.xml) \
    | head -3
  # Expect: empty (or whitespace-only) diff
done

# 5. Tag and push the container image (find the version mp-build assigned first)
sudo docker images | grep microsoftazureadapter
# Pick the right tag from the output (e.g. "8.19.0"), then:
VERSION=8.19.7
sudo docker tag microsoftazureadapter-test:$VERSION 214.73.76.134:5000/azuregovcloud-adapter:latest
sudo docker push 214.73.76.134:5000/azuregovcloud-adapter:latest

# 6. Install via Aria Ops UI
#    Administration > Repository > Add Pak > select the .pak from $PAK above
#    Watch the install task in Administration > Support > Logs > Task History
#    Step 16/20 (APPLY_ADAPTER) must reach SUCCESS, not ERROR
```

### If the build itself 500s (`adapterDefinition endpoint returned 500`)

**Most common cause: `/tmp` is full on the host.** Confirmed via in-container diagnosis on 2026-04-30 — the actual exception is `OSError: [Errno 28] No space left on device` from `tempfile.mkdtemp()` in `swagger_server/controllers/controller.py:168`. swagger_server can't create the FIFO pipes it needs to talk to our adapter subprocess, so it returns 500 before our `adapter.py` ever runs. (That's why `adapter.log` is empty after a failed build.)

#### Recovery — disk-space cleanup (run these in order)

```bash
# 1. Diagnose
df -h
df -h /var/lib/docker /tmp
sudo docker system df

# 2. Clean host /tmp (leftover dirs from build-pak.sh's mktemp -d that didn't cleanup on crash)
sudo rm -rf /tmp/pak-inspect /tmp/test_def.py
sudo find /tmp -maxdepth 1 -type d -name 'tmp*' -mtime +1 -exec rm -rf {} +

# 3. Docker prune (keeps tagged images like base-adapter:python-1.2.0)
sudo docker system prune -f
sudo docker system df    # confirm space recovered

# 4. AGGRESSIVE prune — only if step 3 didn't free enough.
#    WARNING: -a removes all unused images including base-adapter:python-1.2.0,
#    which in this air-gapped env you cannot re-pull. Confirm base-adapter
#    survives via `docker images | grep base-adapter` after.
# sudo docker system prune -a --volumes -f

# 5. Verify free space
df -h /var/lib/docker /tmp
sudo docker run --rm microsoftazureadapter-test:8.19.2 df -h /tmp

# 6. Rebuild
mkdir -p debug
bash scripts/build-pak.sh 2>&1 | tee debug/build.log
ls -la Azure-Native-Build/build/*.pak
```

#### Other possible causes (check after disk-space is ruled out)

- **Stale Docker image cache** — see [memory note](.). Purge with `sudo docker images | grep -iE 'azure|microsoft' | awk '{print $3}' | xargs -r sudo docker rmi --force`.
- **A specific kind's definition crashing the SDK serializer** — only relevant if `adapter.log` exists inside the running container with a Python traceback (see "Capture container logs" below).

```bash
cd /opt/aria/Aria-MP-Builder

# 1. Confirm the server has the latest commit (otherwise nothing changed)
git log --oneline -3
# expect e70b157 "Phase D.1+D.2..." (or later) at HEAD

# 2. Hard-purge ALL azure adapter images (including any "<none>" dangling ones)
sudo docker images -a | grep -iE 'azure|microsoft' | awk '{print $3}' | sort -u | xargs -r sudo docker rmi --force
sudo docker system prune -f

# 3. Rebuild and capture the full output
mkdir -p debug
bash scripts/build-pak.sh 2>&1 | tee debug/build.log

# 4. As soon as it 500s, in another terminal grab the container logs
#    (mp-build tears the container down fast — don't wait)
sudo docker ps -a --format '{{.ID}} {{.Image}} {{.Status}}' | grep -iE 'azure|microsoft'
# Note the container ID and run:
sudo docker logs <CONTAINER_ID> 2>&1 | tail -100 | tee debug/container.log
```

If the container is gone before you can `docker logs` it, run the adapter manually instead so its stdout stays visible:

```bash
cd /opt/aria/Aria-MP-Builder/Azure-Native-Build
sudo mp-test --port 8181 2>&1 | tail -50
# In another shell:
curl -s http://localhost:8181/adapterDefinition | head -50
```

The Python traceback in either output names the exact line/kind that's crashing.

### If APPLY_ADAPTER fails on D.2 (build succeeded, install rejected the pak)

| Symptom | Likely cause | Fix |
|---|---|---|
| `ERROR after 0.0 seconds, empty errorMessages` | A custom kind's SDK shape isn't acceptable to Aria Ops | Bisect — temporarily put one of `azure_subnet` / `azure_recovery_services_vault` / `azure_log_analytics_workspace` back in `if False:` to find the culprit |
| `ERROR` with text mentioning a specific kind | That kind's native span has a value Aria Ops rejects on this server | Add a hand-tuned entry to `BLOCK_SUBSTITUTIONS` (manual override wins over loader) |

## Cycle D.3 — Add Geo Trio (24 → 27 kinds)

Enable World / Region / Region-Per-Sub. Edit [`Azure-Native-Build/app/adapter.py`](../Azure-Native-Build/app/adapter.py) — find the `if False:` near line 713 and remove it (unindent the 3 kind blocks). Then run cycle D.2's commands; expected ResourceKind count is now **27**.

## Cycle D.4 — Add Native Stub Kinds (27 → ~50 kinds)

Enable the `ALL_NATIVE_STUB_KINDS` loop. Edit [`Azure-Native-Build/app/adapter.py`](../Azure-Native-Build/app/adapter.py) — find the `if False:` near line 734 (or whatever line it is post-D.3 cleanup) and remove it. Run cycle D.2's commands; expected count is **~50**.

## End-to-end collection check (after D.4)

```bash
# On Aria Ops:
# - Administration > Cloud Accounts > New > MicrosoftAzureAdapter
# - Fill tenant_id, subscription_id, client_id, client_secret, account_type=Gov
# - Save and Test — expect "Test Success"
# - Wait one collection interval (~10 min) and check Inventory:
#   - Subscription, Resource Group, VM should populate
#   - Disk, NIC, Storage Account, Dedicated Host should populate
#   - Geo trio (World > Region > Region-Per-Sub) should appear
#   - Host Group > Dedicated Host > VM > Disk relationships should render in dashboards
```



services in use list

Microsoft.AlertsManagement/actionRules
Microsoft.AlertsManagement/prometheusRuleGroups
microsoft.alertsmanagement/smartDetectorAlertRules
Microsoft.Automation/automationAccounts
Microsoft.Automation/automationAccounts/runbooks
Microsoft.Cache/Redis
Microsoft.CognitiveServices/accounts
Microsoft.Compute/availabilitySets
Microsoft.Compute/diskEncryptionSets
Microsoft.Compute/disks
Microsoft.Compute/galleries
Microsoft.Compute/galleries/images
Microsoft.Compute/galleries/images/versions
Microsoft.Compute/hostGroups
Microsoft.Compute/hostGroups/hosts
Microsoft.Compute/images
Microsoft.Compute/restorePointCollections
Microsoft.Compute/snapshots
Microsoft.Compute/sshPublicKeys
Microsoft.Compute/virtualMachines
Microsoft.Compute/virtualMachines/extensions
Microsoft.Compute/virtualMachineScaleSets
Microsoft.ContainerRegistry/registries
Microsoft.ContainerRegistry/registries/agentPools
Microsoft.ContainerRegistry/registries/replications
Microsoft.ContainerRegistry/registries/tasks
Microsoft.ContainerService/managedClusters
microsoft.dashboard/grafana
Microsoft.DataFactory/factories
Microsoft.DataMigration/SqlMigrationServices
Microsoft.DataProtection/BackupVaults
Microsoft.DBforMySQL/flexibleServers
Microsoft.EventGrid/systemTopics
Microsoft.EventHub/namespaces
Microsoft.HybridCompute/machines
Microsoft.HybridCompute/machines/extensions
Microsoft.HybridCompute/machines/licenseProfiles
Microsoft.HybridCompute/privateLinkScopes
microsoft.insights/actiongroups
microsoft.insights/activityLogAlerts
Microsoft.Insights/autoscalesettings
microsoft.insights/components
Microsoft.Insights/dataCollectionEndpoints
Microsoft.Insights/dataCollectionRules
microsoft.insights/metricalerts
microsoft.insights/privateLinkScopes
microsoft.insights/scheduledqueryrules
microsoft.insights/workbooks
Microsoft.KeyVault/vaults
Microsoft.KubernetesConfiguration/privateLinkScopes
Microsoft.Kusto/clusters
Microsoft.Logic/workflows
Microsoft.ManagedIdentity/userAssignedIdentities
Microsoft.Maps/accounts
Microsoft.Migrate/migrateprojects
Microsoft.Migrate/moveCollections
microsoft.monitor/accounts
Microsoft.Network/applicationGateways
Microsoft.Network/applicationGatewayWebApplicationFirewallPolicies
Microsoft.Network/azureFirewalls
Microsoft.Network/bastionHosts
Microsoft.Network/connections
Microsoft.Network/dnsForwardingRulesets
Microsoft.Network/dnsResolvers
Microsoft.Network/dnsResolvers/inboundEndpoints
Microsoft.Network/dnsResolvers/outboundEndpoints
Microsoft.Network/dnszones
Microsoft.Network/expressRouteCircuits
Microsoft.Network/loadBalancers
Microsoft.Network/natGateways
Microsoft.Network/networkIntentPolicies
Microsoft.Network/networkInterfaces
Microsoft.Network/networkSecurityGroups
Microsoft.Network/networkWatchers
Microsoft.Network/networkWatchers/connectionMonitors
Microsoft.Network/networkWatchers/flowLogs
Microsoft.Network/privateDnsZones
Microsoft.Network/privateDnsZones/virtualNetworkLinks
Microsoft.Network/privateEndpoints
Microsoft.Network/publicIPAddresses
Microsoft.Network/routeTables
Microsoft.Network/virtualHubs
Microsoft.Network/virtualNetworkGateways
Microsoft.Network/virtualNetworks
microsoft.operationalInsights/querypacks
Microsoft.OperationalInsights/workspaces
Microsoft.OperationsManagement/solutions
Microsoft.Portal/dashboards
Microsoft.RecoveryServices/vaults
Microsoft.Relay/namespaces
Microsoft.Resources/templateSpecs
Microsoft.Resources/templateSpecs/versions
Microsoft.Security/automations
Microsoft.Sql/managedInstances
Microsoft.Sql/managedInstances/databases
Microsoft.Sql/servers
Microsoft.Sql/servers/databases
Microsoft.Sql/servers/elasticpools
Microsoft.Sql/virtualClusters
Microsoft.SqlVirtualMachine/SqlVirtualMachines
Microsoft.Storage/storageAccounts
Microsoft.StorageSync/storageSyncServices
Microsoft.Web/certificates
Microsoft.Web/connections
Microsoft.Web/hostingEnvironments
Microsoft.Web/serverFarms
Microsoft.Web/sites