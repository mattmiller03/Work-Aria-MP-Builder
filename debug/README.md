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
