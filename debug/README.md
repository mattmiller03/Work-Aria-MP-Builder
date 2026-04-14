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

Can you check both the Solutions page and the Repository page in the UI?