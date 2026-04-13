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




500 Internal Server Error
No result from adapter. Captured stdout:
  2026-04-13 16:59:00,858 [INFO] __main__: Running adapter code with arguments: ['adapter_definition', '/tmp/tmprnwnr6zu/input_pipe', '/tmp/tmprnwnr6zu/output_pipe']
2026-04-13 16:59:00,882 [ERROR] __main__: Error in adapter_definition: 'Unit' object has no attribute 'value'
Traceback (most recent call last):
  File "/home/aria-ops-adapter-user/src/app/app/adapter.py", line 748, in main
    result = get_adapter_definition()
             ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/aria-ops-adapter-user/src/app/app/adapter.py", line 155, in get_adapter_definition
    vm.define_metric("CPU|cpu_usage", "CPU Usage",
  File "/usr/local/lib/python3.11/site-packages/aria/ops/definition/group.py", line 113, in define_metric
    metric = MetricAttribute(
             ^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.11/site-packages/aria/ops/definition/attribute.py", line 98, in __init__
    super().__init__(
  File "/usr/local/lib/python3.11/site-packages/aria/ops/definition/attribute.py", line 45, in __init__
    self.unit = unit.value.key if unit else None
                ^^^^^^^^^^
AttributeError: 'Unit' object has no attribute 'value'
2026-04-13 16:59:00,883 [INFO] __main__: Timing Graph: 
━━━━━━━━━┯━━━━━━━━┯━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Operation│Time    │t=0s                                                t=-1776099540.88s
━━━━━━━━━┿━━━━━━━━┿━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
━━━━━━━━━┷━━━━━━━━┷━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

adapterDefinition endpoint returned 500.
Unable to build pak file



sudo docker images | grep azure
mp-builder-Ip:5000/azuregovcloud-adapter                            <none>       f994e72787c2   2 days ago     281MB
mp-builder-Ip:5000/azuregovcloud-adapter                            <none>       66f9a35890b1   3 days ago     281MB
mp-builder-Ip:5000/azuregovcloud-adapter                            latest       9eb8cf6a0866   3 days ago     281MB
mp-builder-Ip:5000/azuregovcloud-adapter                            <none>       63dd5869a726   3 days ago     281MB
mp-builder-Ip:5000/azuregovcloud-adapter                            <none>       786e9f3b4ac2   3 days ago     281MB
azuregovcloud-test                                                  1.0.0        ae3623788d7a   7 days ago     281MB
mp-builder-Ip:5000/azuregovcloud-adapter                            <none>       ae3623788d7a   7 days ago     281MB



Unexpected exception occurred while trying to build pak file
[Errno 2] No such file or directory: '/opt/aria/Aria-MP-Builder/Azure/echo 0'
  File "/opt/python312/lib/python3.12/site-packages/vmware_aria_operations_integration_sdk/mp_build.py", line 713, in main
    pak_file = asyncio.run(
               ^^^^^^^^^^^^
  File "/opt/python312/lib/python3.12/asyncio/runners.py", line 195, in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
  File "/opt/python312/lib/python3.12/asyncio/runners.py", line 118, in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/python312/lib/python3.12/asyncio/base_events.py", line 691, in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
  File "/opt/python312/lib/python3.12/site-packages/vmware_aria_operations_integration_sdk/mp_build.py", line 547, in build_pak_file
    shutil.copy(
  File "/opt/python312/lib/python3.12/shutil.py", line 435, in copy
    copyfile(src, dst, follow_symlinks=follow_symlinks)
  File "/opt/python312/lib/python3.12/shutil.py", line 260, in copyfile
    with open(src, 'rb') as fsrc: