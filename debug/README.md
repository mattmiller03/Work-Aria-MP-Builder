<!-- markdownlint-disable -->


# Debug Folder

Use this folder for transferring logs and scratch files between machines.
Files in this folder are git-ignored except this README.

Common files to put here:
- `terminal.log` — console output from the server
- `adapter.log` — adapter container logs
- `casa-log.txt` — Aria Ops CASA service logs
- `validation.log` — mp-test validation output




The simplest test — just curl it from the machine that runs the adapter:


curl -s "https://prices.azure.com/api/retail/prices?\$filter=serviceName%20eq%20'Virtual%20Machines%20Dedicated%20Host'%20and%20armRegionName%20eq%20'usgovvirginia'%20and%20priceType%20eq%20'Consumption'" | python3 -m json.tool | head -30
That tells you two things at once:

Can the machine reach prices.azure.com
Does the region name format (usgovvirginia vs usgov virginia) return results
If you get results back, check the armSkuName values match what your hosts report as sku_name. If you get an empty Items array, try the spaced version:


curl -s "https://prices.azure.com/api/retail/prices?\$filter=serviceName%20eq%20'Virtual%20Machines%20Dedicated%20Host'%20and%20armRegionName%20eq%20'usgov%20virginia'%20and%20priceType%20eq%20'Consumption'" | python3 -m json.tool | head -30
If neither returns results, try dropping the region filter entirely to confirm the API is reachable:


curl -s "https://prices.azure.com/api/retail/prices?\$filter=serviceName%20eq%20'Virtual%20Machines%20Dedicated%20Host'" | python3 -m json.tool | head -30
If the machine can't reach prices.azure.com at all (timeout/connection refused), the air-gap is blocking it and we'll need to switch to a hardcoded pricing table instead.

curl -s -H "Authorization: Bearer <TOKEN>" "https://management.usgovcloudapi.net/subscriptions/<SUB_ID>/providers/Microsoft.Compute/hostGroups?api-version=2023-03-01&\$expand=instanceView" | python3 -m json.tool | grep -i skuName



You already have both in your adapter's credentials:

Sub ID — it's in your connections.json (or visible in the Azure portal under Subscriptions)
Bearer token — your adapter's auth.py handles this. You can grab one quickly with a Python one-liner from the MP Builder server:

cd /opt/aria/Aria-MP-Builder/Azure/app
python3 -c "
from auth import AzureAuthenticator
auth = AzureAuthenticator('<TENANT_ID>', '<CLIENT_ID>', '<CLIENT_SECRET>', 'government')
print(auth.get_token())
"
Replace the three values from your connections.json. That prints a bearer token you can paste into the curl.

Alternatively, skip all that and just check what SKUs you have from the mp-test output. When you run a collect, the adapter logs should show the host groups and hosts it found. Or check the Aria Ops UI — go to your Azure adapter objects, find the Dedicated Host objects, and look at the sku_name property.

If none of those are convenient, you can also check the Azure Gov portal at portal.azure.us > Dedicated Hosts — the SKU is listed on each host.

cd /opt/aria/Aria-MP-Builder/Azure/app
python3 -c "
from auth import AzureAuthenticator
from azure_client import AzureClient
auth = AzureAuthenticator('<TENANT_ID>', '<CLIENT_ID>', '<CLIENT_SECRET>', 'government')
client = AzureClient(auth, 'government')
subs = client.get_all('/subscriptions', '2022-12-01')
print(f'Service principal can see {len(subs)} subscriptions:')
for s in subs:
    print(f'  {s[\"displayName\"]} ({s[\"subscriptionId\"]})')
"

The suite-api auth can be tricky. Try this format instead:


# Use basic auth directly with the suite-api
curl -k -u 'admin:YOUR_PASSWORD' -X DELETE \
  "https://localhost/suite-api/api/solutions/AzureGovCloud" \
  -H "Accept: application/json"
If that's still unauthorized, the solution ID might not match. Find the exact ID first:


curl -k -u 'admin:YOUR_PASSWORD' \
  "https://localhost/suite-api/api/solutions" \
  -H "Accept: application/json"
Look for the Azure entry and note the exact id field — it might be something like AzureGovCloud-141 rather than just AzureGovCloud.

If basic auth doesn't work at all, try through the Aria Ops UI instead:

Administration > Solutions
Right-click the Azure Gov pack
Look for Reset or Uninstall option
Does basic auth with -u 'admin:password' work, or is that also unauthorized?


1. Use the maintenanceAdmin account instead (built-in system account):


curl -k -u 'maintenanceAdmin:YOUR_PASSWORD' \
  "https://localhost/suite-api/api/solutions" \
  -H "Accept: application/json"
2. Try specifying the auth source explicitly:


curl -k -X POST "https://localhost/suite-api/api/auth/token/acquire" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"YOUR_PASSWORD","authSource":"LOCAL"}'
Note LOCAL in caps — some versions are case-sensitive.

3. Skip the API entirely — use the $VMWARE_PYTHON_BIN CLI on the node:


# SSH into the Aria Ops master node
sudo su -
cd /usr/lib/vmware-vcops/
./vcopsConfigureRoles.sh --


# Or try the pak manager directly
/usr/lib/vmware-vcops/tools/opscli/admin-cli.sh solution list
4. Simplest option — just uninstall from the UI:

In the Aria Ops web UI, go to Administration > Repository > Management Packs (not Solutions). The failed pak might show there with an option to delete it.




On the Cloud Proxy:


# Stop and remove all Azure adapter containers
sudo docker ps -a | grep azure
sudo docker stop $(sudo docker ps -a | grep azure | awk '{print $1}')
sudo docker rm $(sudo docker ps -a | grep azure | awk '{print $1}')

# Remove all Azure adapter images
sudo docker rmi $(sudo docker images | grep azure | awk '{print $3}') --force

# Verify clean
sudo docker images | grep azure
sudo docker ps -a | grep azure
On the Aria Ops node:


# Restart CASA to clear any cached state
sudo systemctl restart vmware-casa

# Wait a couple minutes, then verify the solution is gone
# Check the UI: Administration > Solutions — Azure Gov should not appear
On the MP Builder server:


# Clean old builds and images
sudo docker rmi $(sudo docker images | grep azure | awk '{print $3}') --force

# Fresh build
cd /opt/aria/Aria-MP-Builder/Azure
sudo mp-build -i --no-ttl --registry-tag "mp-builder-Ip:5000/azuregovcloud-adapter" -P 8181

# Push to registry
sudo docker push mp-builder-Ip:5000/azuregovcloud-adapter:latest
Then on Aria Ops UI:

Administration > Repository > Add Pak
Fresh install of the new .pak file



The key finding: the suite-api's SOLUTION_INSTALL task goes to ERROR in 87 milliseconds with empty errorMessages. That's an instant rejection — the suite-api already has a stale adapter kind registered.

We need the suite-api logs. Try these locations:


sudo find /storage/log /usr/lib/vmware-vcops -name "*.log" 2>/dev/null | xargs grep -l "SOLUTION_INSTALL\|AzureGov" 2>/dev/null
Or look specifically for the analytics web service logs:


sudo ls /storage/log/vcops/log/
sudo ls /usr/lib/vmware-vcops/user/log/
Also — let's try to get the task detail directly:


curl -k -u 'admin:YOUR_PASSWORD' \
  "https://localhost/suite-api/api/tasks/d98d88ef-1daf-47b7-84f5-4763f85a42e7" \
  -H "Accept: application/json"
And check if the adapter kind is still registered even after uninstall:


curl -k -u 'admin:YOUR_PASSWORD' \
  "https://localhost/suite-api/api/adapterkinds" \
  -H "Accept: application/json" 2>/dev/null | grep -i azure
If it shows AzureGovAdapter still registered, that's the blocker. We'd need to delete the stale adapter kind before reinstalling.

# Get auth token
TOKEN=$(curl -k -s -X POST "https://localhost/suite-api/api/auth/token/acquire" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"***REDACTED-PASSWORD***","authSource":"LOCAL"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")


  curl -k -X POST "https://localhost/suite-api/api/auth/token/acquire" \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"***REDACTED-PASSWORD***","authSource":"LOCAL"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")


# Check if AzureGovAdapter is still registered
curl -k -s "https://localhost/suite-api/api/adapterkinds" \
  -H "Authorization: vRealizeOpsToken ***REDACTED-TOKEN***" \
  -H "Accept: application/json" | grep -i -o '"key":"[^"]*[Aa]zure[^"]*"'
import sys,json
data = json.load(sys.stdin)
for ak in data.get('adapter-kind',[]):
    if 'azure' in ak.get('key','').lower():
        print(ak['key'], ak.get('name',''))
"

# If it shows AzureGovAdapter, delete it
curl -k -s -X DELETE "https://localhost/suite-api/api/adapterkinds/AzureGovAdapter" \
  -H "Authorization: vRealizeOpsToken $TOKEN"









  root@ariaops-node [ /home/svcaccount ]# $VMWARE_PYTHON_BIN /usr/lib/vmware-vcopssuite/utilities/sliceConfiguration/bin/vcopsClusterManager.py init-cluster
ERROR:root:Failed to get CaSA token pair: '503' error code: HTTP Error 503: Service Unavailable
2026-04-14T19:03:41 ERROR [2933] - root - Failed to get CaSA token pair: '503' error code: HTTP Error 503: Service Unavailable
2026-04-14T19:03:42 ERROR [2933] - root - Failed to initialize the cluster. Casa returned status code 503.
2026-04-14T19:03:42 ERROR [2933] - root - 
Operation failed.  Failed to initialize the cluster.  See log for details.
2026-04-14T19:03:42 ERROR [2933] - root - Failed to initialize the cluster.
Traceback (most recent call last):
  File "/usr/lib/vmware-vcopssuite/utilities/sliceConfiguration/bin/vcopsClusterManager.py", line 146, in <module>
    ClusterManager().initializeCluster()
  File "/usr/lib/vmware-vcopssuite/utilities/sliceConfiguration/bin/vcopsClusterManager.py", line 81, in initializeCluster
    raise Exception('Failed to initialize the cluster.')
Exception: Failed to initialize the cluster.








root@ariaops-node [ ~ ]# sudo systemctl status vmware-casa.service
● vmware-casa.service - LSB: vRealize Operations Cluster and Slice Administration
     Loaded: loaded (/usr/lib/vmware-casa/bin/vmware-casa.sh; enabled; preset: enabled)
     Active: activating (start) since Tue 2026-04-14 19:34:52 UTC; 835ms ago
       Docs: man:systemd-sysv-generator(8)
    Process: 3640 ExecStartPre=/usr/lib/vmware-vcopssuite/utilities/bin/restore_check_instance_id.sh (code=exited, status=0/SUCCESS)
  Cntrl PID: 3643 (vmware-casa.sh)
      Tasks: 4
     Memory: 1.6M
        CPU: 87ms
     CGroup: /system.slice/vmware-casa.service
             ├─3643 /bin/bash /usr/lib/vmware-casa/bin/vmware-casa.sh start
             ├─3649 /bin/sh /usr/lib/vmware-casa/casa-webapp/bin/init.d.sh start
             ├─3652 /bin/sh /usr/share/tomcat/instance/bin/tomcat-instance-control.sh casa-webapp start
             └─3671 sleep 2

Apr 14 19:34:52 ariaops-node.INTERNAL-DOMAIN systemd[1]: Starting LSB: vRealize Operations Cluster and Sl…on...
Apr 14 19:34:52 ariaops-node.INTERNAL-DOMAIN vmware-casa.sh[3649]: init.d.sh  admin
Apr 14 19:34:52 ariaops-node.INTERNAL-DOMAIN vmware-casa.sh[3649]: starting tomcat instance
Apr 14 19:34:52 ariaops-node.INTERNAL-DOMAIN vmware-casa.sh[3649]: su_tomcat /usr/lib/vmware-casa/casa-web…tart
Apr 14 19:34:52 ariaops-node.INTERNAL-DOMAIN vmware-casa.sh[3670]: touch: cannot touch '/storage/log/vcops…tory
Apr 14 19:34:52 ariaops-node.INTERNAL-DOMAIN vmware-casa.sh[3666]: /usr/share/tomcat/bin/catalina.sh: line…tory




sudo mkdir -p /storage/log/vcops/log/casa
sudo mkdir -p /storage/log/vcops/log/pakManager
sudo chown -R admin:admin /storage/log/vcops/log/casa
sudo chown -R admin:admin /storage/log/vcops/log/pakManager
