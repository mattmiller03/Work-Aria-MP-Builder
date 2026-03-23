# Aria Operations Management Pack — Azure Government Cloud

A custom VMware Aria Operations management pack that collects resource attributes from Azure Government Cloud. This guide covers **both** implementation paths:

- **Path A** — [MP Builder GUI](#path-a-management-pack-builder-gui) (no-code, visual designer appliance)
- **Path B** — [Integration SDK](#path-b-integration-sdk-code-based) (Python code in this repository)

> **Which path should I choose?**
> The MP Builder GUI is great for simple REST APIs with offset/page-based pagination. Azure ARM APIs use cursor-based `nextLink` pagination which the GUI does **not** natively support — meaning you may only retrieve the first page of results for large environments. The SDK approach in this repo handles `nextLink` pagination, token refresh, rate-limiting, and multi-subscription enumeration automatically. **For production Azure Gov deployments, the SDK path is recommended.**

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Azure Gov App Registration Setup](#azure-gov-app-registration-setup)
- [Path A: Management Pack Builder GUI](#path-a-management-pack-builder-gui)
  - [Step 1 — Deploy the MP Builder Appliance](#step-1--deploy-the-mp-builder-appliance)
  - [Step 2 — Log In and Create a Design](#step-2--log-in-and-create-a-design)
  - [Step 3 — Configure the Source](#step-3--configure-the-source)
  - [Step 4 — Configure Authentication](#step-4--configure-authentication)
  - [Step 5 — Configure Session Authentication (OAuth2)](#step-5--configure-session-authentication-oauth2)
  - [Step 6 — Set Global Request Headers](#step-6--set-global-request-headers)
  - [Step 7 — Test the Connection](#step-7--test-the-connection)
  - [Step 8 — Define API Requests](#step-8--define-api-requests)
  - [Step 9 — Define Objects](#step-9--define-objects)
  - [Step 10 — Define Relationships](#step-10--define-relationships)
  - [Step 11 — Run a Test Collection](#step-11--run-a-test-collection)
  - [Step 12 — Build the .pak File](#step-12--build-the-pak-file)
  - [Step 13 — Deploy to Aria Operations](#step-13--deploy-to-aria-operations)
- [Path B: Integration SDK (Code-Based)](#path-b-integration-sdk-code-based)
  - [Step 1 — Install Prerequisites](#step-1--install-prerequisites)
  - [Step 2 — Clone the Repository](#step-2--clone-the-repository)
  - [Step 3 — Install Python Dependencies](#step-3--install-python-dependencies)
  - [Step 4 — Configure Credentials](#step-4--configure-credentials)
  - [Step 5 — Understand the Project Structure](#step-5--understand-the-project-structure)
  - [Step 6 — Customize What Gets Collected](#step-6--customize-what-gets-collected-optional)
  - [Step 7 — Test Locally](#step-7--test-locally)
  - [Step 8 — Build the .pak File](#step-8--build-the-pak-file)
  - [Step 9 — Deploy to Aria Operations](#step-9--deploy-to-aria-operations)
  - [Step 10 — Configure the Adapter Instance](#step-10--configure-the-adapter-instance)
  - [Step 11 — Verify Collection](#step-11--verify-collection)
  - [Step 12 — Iterate and Redeploy](#step-12--iterate-and-redeploy)
- [Azure Gov Endpoint Reference](#azure-gov-endpoint-reference)
- [Collected Resource Types](#collected-resource-types)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

| Requirement | Details |
|-------------|---------|
| **Aria Operations** | On-premises v8.10+ (MP Builder does not support SaaS) |
| **vSphere** | For deploying the MP Builder OVA (Path A only) |
| **Azure Gov Tenant** | An Entra ID (Azure AD) tenant in Azure Government |
| **App Registration** | Service principal with Reader role on target subscriptions |
| **Network Access** | Firewall rules allowing outbound HTTPS to `login.microsoftonline.us` and `management.usgovcloudapi.net` |
| **Python 3.8+** | Path B (SDK) only |

---

## Azure Gov App Registration Setup

Before either path, you need an Azure Gov service principal:

1. **Sign in** to the Azure Gov Portal at `https://portal.azure.us`
2. Navigate to **Microsoft Entra ID > App registrations > New registration**
   - Name: `aria-operations-mp` (or any descriptive name)
   - Supported account types: Single tenant
   - Click **Register**
3. **Note the values** from the Overview page:
   - **Application (client) ID** — this is your `client_id`
   - **Directory (tenant) ID** — this is your `tenant_id`
4. **Create a client secret**:
   - Go to **Certificates & secrets > New client secret**
   - Set an expiration (recommend 12-24 months)
   - **Copy the secret value immediately** — it won't be shown again. This is your `client_secret`
5. **Assign RBAC role**:
   - Navigate to the target **Subscription > Access control (IAM) > Add role assignment**
   - Role: **Reader**
   - Assign to: the app registration you just created
   - Repeat for each subscription you want to monitor
6. **Note your Subscription ID(s)** from the Subscriptions blade

You should now have four values:
```
tenant_id:       xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
client_id:       xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
client_secret:   your-secret-value
subscription_id: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

---

## Path A: Management Pack Builder GUI

### Step 1 — Deploy the MP Builder Appliance

1. **Download** the MP Builder OVA from the [VMware Marketplace](https://marketplace.cloud.vmware.com) (search for "Management Pack Builder"). The file is ~2 GB. If the download has a `.tar` extension, rename it to `.ova`.

2. **Deploy the OVA** in vSphere Client:
   - Right-click your cluster > **Deploy OVF Template**
   - Upload the OVA file
   - Name the VM (alphanumeric and hyphens only — no underscores)
   - Select compute, storage, and network resources
   - **Customize template** (DHCP is NOT supported):
     - Set the root password
     - Enter: Gateway, Domain, DNS server(s), static IP address, Netmask
   - Finish and wait for deployment

3. **Power on** the VM and wait ~10 minutes for services to initialize.

### Step 2 — Log In and Create a Design

1. Browse to `https://<MP-Builder-IP>`
2. Log in with `admin` / `admin`
3. **Change the password** on first login (8+ chars, must include a number and special character)
4. Click the **Designs** tab
5. Click **Create > New**
6. Enter:
   - **Management Pack Name**: `Azure Government Cloud`
   - **Description**: `Collects resource attributes from Azure Gov Cloud instances`

The design editor opens with a left navigation: Source, Requests, Objects, Relationships, Events, Alerts, Content, Configuration, Build.

### Step 3 — Configure the Source

Navigate to **Source** and fill in:

| Field | Value |
|-------|-------|
| **Hostname** | `login.microsoftonline.us` |
| **Port** | `443` |
| **SSL Configuration** | **Unverified** (or Verified if you import the Microsoft cert) |
| **Base API Path** | *(leave blank)* |

> **Note:** The Hostname here is used for the authentication session request. Individual data collection requests will use the full Azure ARM URL via request configuration.

### Step 4 — Configure Authentication

1. Select **Custom** authentication type
2. Add the following credential fields by clicking **Add Field** for each:

| Label | Sample Value | Sensitive? |
|-------|-------------|------------|
| `tenant_id` | `your-tenant-guid` | No |
| `client_id` | `your-client-id-guid` | No |
| `client_secret` | `your-secret-value` | **Yes** |
| `subscription_id` | `your-subscription-guid` | No |

These generate substitution variables:
- `${authentication.credentials.tenant_id}`
- `${authentication.credentials.client_id}`
- `${authentication.credentials.client_secret}`
- `${authentication.credentials.subscription_id}`

### Step 5 — Configure Session Authentication (OAuth2)

1. Toggle **"Will session authentication be used?"** to **Yes**

2. **Get Session — Request tab:**

| Field | Value |
|-------|-------|
| **HTTP Method** | `POST` |
| **API Path** | `/${authentication.credentials.tenant_id}/oauth2/v2.0/token` |

3. **Get Session — Advanced tab:**
   - **Headers**: Add `Content-Type` = `application/x-www-form-urlencoded`
   - **Body**:
     ```
     grant_type=client_credentials&client_id=${authentication.credentials.client_id}&client_secret=${authentication.credentials.client_secret}&scope=https%3A%2F%2Fmanagement.usgovcloudapi.net%2F.default
     ```

4. Click **Request** to test the session call. You should receive a 200 response with JSON containing `access_token`, `token_type`, and `expires_in`.

5. **Session Fields tab:**
   - In the Variables section, check the box next to **`access_token`**
   - Click the copy icon to get the substitution variable: `${authentication.session.access_token}`

6. **Release Session** — Toggle **off** (Azure OAuth2 tokens are self-expiring; there is no revoke endpoint needed).

### Step 6 — Set Global Request Headers

In the **Global Request Settings** tab:

| Header Name | Header Value |
|-------------|-------------|
| `Authorization` | `Bearer ${authentication.session.access_token}` |

This header is automatically included in **every** subsequent API request.

### Step 7 — Test the Connection

1. In the **Test Connection** tab:
   - **API Path**: `https://management.usgovcloudapi.net/subscriptions/${authentication.credentials.subscription_id}?api-version=2022-12-01`
2. Click **Request**
3. Verify you receive HTTP 200 with your subscription details in the response body

### Step 8 — Define API Requests

Navigate to **Requests** and create the following API requests. For each, click **Add Request**:

#### Request: List Subscriptions
| Field | Value |
|-------|-------|
| **Name** | `List Subscriptions` |
| **Method** | `GET` |
| **API Path** | `https://management.usgovcloudapi.net/subscriptions?api-version=2022-12-01` |

#### Request: List Resource Groups
| Field | Value |
|-------|-------|
| **Name** | `List Resource Groups` |
| **Method** | `GET` |
| **API Path** | `https://management.usgovcloudapi.net/subscriptions/${authentication.credentials.subscription_id}/resourcegroups?api-version=2024-03-01` |

#### Request: List Virtual Machines
| Field | Value |
|-------|-------|
| **Name** | `List Virtual Machines` |
| **Method** | `GET` |
| **API Path** | `https://management.usgovcloudapi.net/subscriptions/${authentication.credentials.subscription_id}/providers/Microsoft.Compute/virtualMachines?api-version=2024-07-01&$expand=instanceView` |

#### Request: List Disks
| Field | Value |
|-------|-------|
| **Name** | `List Disks` |
| **Method** | `GET` |
| **API Path** | `https://management.usgovcloudapi.net/subscriptions/${authentication.credentials.subscription_id}/providers/Microsoft.Compute/disks?api-version=2024-03-02` |

#### Request: List Network Interfaces
| Field | Value |
|-------|-------|
| **Name** | `List Network Interfaces` |
| **Method** | `GET` |
| **API Path** | `https://management.usgovcloudapi.net/subscriptions/${authentication.credentials.subscription_id}/providers/Microsoft.Network/networkInterfaces?api-version=2024-05-01` |

#### Request: List Virtual Networks
| Field | Value |
|-------|-------|
| **Name** | `List Virtual Networks` |
| **Method** | `GET` |
| **API Path** | `https://management.usgovcloudapi.net/subscriptions/${authentication.credentials.subscription_id}/providers/Microsoft.Network/virtualNetworks?api-version=2024-05-01` |

#### Request: List Storage Accounts
| Field | Value |
|-------|-------|
| **Name** | `List Storage Accounts` |
| **Method** | `GET` |
| **API Path** | `https://management.usgovcloudapi.net/subscriptions/${authentication.credentials.subscription_id}/providers/Microsoft.Storage/storageAccounts?api-version=2023-05-01` |

#### Request: List Load Balancers
| Field | Value |
|-------|-------|
| **Name** | `List Load Balancers` |
| **Method** | `GET` |
| **API Path** | `https://management.usgovcloudapi.net/subscriptions/${authentication.credentials.subscription_id}/providers/Microsoft.Network/loadBalancers?api-version=2024-05-01` |

#### Request: List SQL Servers
| Field | Value |
|-------|-------|
| **Name** | `List SQL Servers` |
| **Method** | `GET` |
| **API Path** | `https://management.usgovcloudapi.net/subscriptions/${authentication.credentials.subscription_id}/providers/Microsoft.Sql/servers?api-version=2023-08-01` |

#### Request: List Web Apps
| Field | Value |
|-------|-------|
| **Name** | `List Web Apps` |
| **Method** | `GET` |
| **API Path** | `https://management.usgovcloudapi.net/subscriptions/${authentication.credentials.subscription_id}/providers/Microsoft.Web/sites?api-version=2023-12-01` |

> **Pagination Note:** Azure ARM APIs use cursor-based `nextLink` pagination. The MP Builder GUI only supports offset-based and page-based pagination natively. For small environments (< 1000 resources per type), the first page response typically contains all results. For large environments, consider using the SDK approach (Path B) which handles `nextLink` automatically.

After creating each request, click the **play/test** button to verify it returns data. The response panel will show the JSON response — expand `value[]` to see the resource array.

### Step 9 — Define Objects

Navigate to **Objects** and create object types by mapping API responses to Aria Operations resources.

#### Example: Azure Virtual Machine

1. Click **Add New Object**
2. **Object Type Name**: `Azure Virtual Machine`
3. Select an icon
4. Expand the **List Virtual Machines** request response
5. Check the boxes for these attributes from the `value[]` array:

| Response Path | Aria Ops Label | Data Type | Property? | KPI? |
|---------------|---------------|-----------|-----------|------|
| `name` | VM Name | String | Yes | No |
| `location` | Location | String | Yes | No |
| `properties.hardwareProfile.vmSize` | VM Size | String | Yes | Yes |
| `properties.provisioningState` | Provisioning State | String | Yes | No |
| `properties.vmId` | VM ID | String | Yes | No |
| `properties.osProfile.computerName` | Computer Name | String | Yes | No |
| `properties.storageProfile.osDisk.osType` | OS Type | String | Yes | Yes |
| `properties.storageProfile.osDisk.diskSizeGB` | OS Disk Size GB | Decimal | Yes | No |
| `properties.storageProfile.imageReference.publisher` | Image Publisher | String | Yes | No |
| `properties.storageProfile.imageReference.offer` | Image Offer | String | Yes | No |
| `properties.storageProfile.imageReference.sku` | Image SKU | String | Yes | No |
| `properties.instanceView.statuses[].code` | Power State | String | Yes | Yes |
| `tags` | Tags | String | Yes | No |
| `zones[]` | Availability Zone | String | Yes | No |

6. **Object Instance Name**: Select `name` (the VM name)
7. **Object Identifiers**: Select `properties.vmId` (uniquely identifies each VM)

#### Repeat for Other Resource Types

Create similar object mappings for each request:

| Object Type | Key Attributes to Select |
|-------------|------------------------|
| **Azure Subscription** | subscriptionId, displayName, state, tenantId |
| **Azure Resource Group** | name, location, properties.provisioningState, tags |
| **Azure Disk** | name, location, sku.name, properties.diskSizeGB, properties.diskState, properties.diskIOPSReadWrite |
| **Azure Network Interface** | name, location, properties.macAddress, properties.ipConfigurations[].properties.privateIPAddress |
| **Azure Virtual Network** | name, location, properties.addressSpace.addressPrefixes[], properties.subnets[].name |
| **Azure Storage Account** | name, location, kind, sku.name, properties.accessTier, properties.primaryEndpoints.blob |
| **Azure Load Balancer** | name, location, sku.name, properties.frontendIPConfigurations[], properties.backendAddressPools[] |
| **Azure SQL Server** | name, location, properties.fullyQualifiedDomainName, properties.state, properties.version |
| **Azure App Service** | name, location, kind, properties.state, properties.defaultHostName, properties.httpsOnly |

For each object type, set appropriate identifiers (the minimum set of properties that uniquely identify each instance).

### Step 10 — Define Relationships

Navigate to **Relationships** and define the parent-child hierarchy:

| Parent | Child | Matching Property |
|--------|-------|-------------------|
| Azure Subscription | Azure Resource Group | `subscription_id` on both |
| Azure Resource Group | Azure Virtual Machine | Extract resource group from VM's `id` field |
| Azure Resource Group | Azure Disk | Extract resource group from disk's `id` field |
| Azure Resource Group | Azure Network Interface | Extract resource group from NIC's `id` field |
| Azure Resource Group | Azure Virtual Network | Extract resource group from VNet's `id` field |
| Azure Resource Group | Azure Storage Account | Extract resource group from storage account's `id` field |
| Azure Resource Group | Azure Load Balancer | Extract resource group from LB's `id` field |
| Azure Resource Group | Azure SQL Server | Extract resource group from server's `id` field |
| Azure Resource Group | Azure App Service | Extract resource group from app's `id` field |
| Azure Virtual Network | Azure Subnet | Match VNet `id` to subnet's parent path |
| Azure SQL Server | Azure SQL Database | Match server `name` |

For each relationship:
1. Select the **Parent** and **Child** object types
2. Choose matching properties on each side
3. Set case sensitivity to **Insensitive** (Azure resource names are case-insensitive)

### Step 11 — Run a Test Collection

1. Navigate to **Build > Perform Collection**
2. Click **Run Collection**
3. Review the summary:
   - **Objects discovered** — should show counts for each resource type
   - **Properties collected** — total attributes gathered
   - **Relationships established** — parent-child links created
4. Click on any object type to inspect individual instances and verify the correct properties were collected
5. If issues appear, check the **Logs** (set to DEBUG for verbose output)

### Step 12 — Build the .pak File

1. Navigate to **Build**
2. Click **Build**
3. The system packages everything into a `.pak` file
4. **Download** the `.pak` when the build completes
5. The file is saved as `AzureGovernmentCloud-1.0.0.pak` (or similar)

### Step 13 — Deploy to Aria Operations

1. Log in to your **Aria Operations** instance
2. Navigate to **Administration > Integrations** (or **Administration > Solutions** in older versions)
3. Click **Add** and upload the `.pak` file
4. **Check "Ignore the PAK file signature checking"** (MP Builder packs are unsigned)
5. Accept the EULA and wait for the installation to complete

**Configure the Adapter Instance:**

6. Go to **Administration > Integrations > Accounts > Add Account**
7. Select **Azure Government Cloud** from the adapter type list
8. Fill in the connection details:

| Field | Value |
|-------|-------|
| **Display Name** | `Azure Gov - Production` (or descriptive name) |
| **Tenant ID** | Your Azure Gov tenant GUID |
| **Client ID** | Your app registration client ID |
| **Client Secret** | Your app registration secret |
| **Subscription ID** | Target subscription (or leave blank for all) |

9. Click **Validate Connection** — you should see a success message with subscription count
10. Set the **Collection Interval** (default 5 minutes)
11. Click **Save**

**Verify:**

12. Wait ~5-15 minutes for the first collection cycles
13. Navigate to **Inventory** and look for your Azure resources under the new integration
14. Check **Administration > Integrations** to confirm the collector status shows green

---

## Path B: Integration SDK (Code-Based)

This is the **recommended path** for production Azure Gov environments. The Python code in this repository handles `nextLink` cursor pagination, OAuth2 token refresh, rate-limit retry with exponential backoff, and multi-subscription enumeration — none of which the MP Builder GUI supports natively.

### Step 1 — Install Prerequisites

**Python 3.8+** and **Docker** are required. Docker is used by `mp-test` to simulate the Aria Operations collector environment locally.

```bash
# Install the VCF Operations Integration SDK
pip install vmware-aria-operations-integration-sdk

# Verify installation
mp-build --version
```

### Step 2 — Clone the Repository

```bash
git clone https://github.com/mattmiller03/Aria-MP-Builder.git
cd Aria-MP-Builder
```

### Step 3 — Install Python Dependencies

```bash
pip install -r Azure/app/requirements.txt
```

This installs the `requests` library used by the adapter for all Azure REST API calls.

### Step 4 — Configure Credentials

Create (or edit) `Azure/connections.json` with your Azure Gov service principal:

```json
{
  "connections": [
    {
      "name": "Azure Gov Test",
      "credential": {
        "type": "azure_gov_credential",
        "tenant_id": "YOUR_TENANT_ID",
        "client_id": "YOUR_CLIENT_ID",
        "client_secret": "YOUR_CLIENT_SECRET",
        "subscription_id": "YOUR_SUBSCRIPTION_ID"
      },
      "configuration": {
        "cloud_environment": "government"
      }
    }
  ]
}
```

| Field | Description |
|-------|-------------|
| `tenant_id` | Directory (tenant) ID from your Azure Gov Entra ID |
| `client_id` | Application (client) ID from the app registration |
| `client_secret` | Client secret value (not the secret ID) |
| `subscription_id` | Target subscription GUID, or leave blank `""` to collect from all accessible subscriptions |
| `cloud_environment` | `"government"` for Azure Gov, `"commercial"` for standard Azure |

> **Security:** `connections.json` is listed in `.gitignore` and will never be committed to the repository. Do not remove it from `.gitignore`.

### Step 5 — Understand the Project Structure

```
Azure/
├── app/
│   ├── adapter.py              ← Main entry point (collect, test, get_adapter_definition)
│   ├── constants.py            ← Adapter keys, Azure Gov endpoints, API versions, object type keys
│   ├── auth.py                 ← OAuth2 client credentials flow (login.microsoftonline.us)
│   ├── azure_client.py         ← REST client with nextLink pagination + rate-limit retry
│   ├── collectors/
│   │   ├── __init__.py         ← Re-exports all collector functions
│   │   ├── subscriptions.py    ← Enumerates Azure subscriptions
│   │   ├── resource_groups.py  ← Resource groups per subscription
│   │   ├── virtual_machines.py ← VMs with instance view (power state)
│   │   ├── disks.py            ← Managed disks (IOPS, size, SKU)
│   │   ├── network_interfaces.py ← NICs (IPs, MAC, NSG, subnet)
│   │   ├── virtual_networks.py ← VNets and subnets
│   │   ├── storage_accounts.py ← Storage accounts (endpoints, tier)
│   │   ├── load_balancers.py   ← Load balancers (frontends, backends)
│   │   ├── key_vaults.py       ← Key Vaults (soft delete, purge protection)
│   │   ├── sql_databases.py    ← SQL servers + databases
│   │   └── app_services.py     ← Web apps and function apps
│   └── requirements.txt
├── conf/
│   └── describe.xml            ← Adapter object model (auto-generated by mp-build)
├── resources/
│   └── resources.properties    ← Localization keys
├── manifest.txt                ← Pack metadata (name, version, adapter_kinds)
├── eula.txt                    ← License agreement
└── connections.json            ← Local test credentials (git-ignored)
```

**How the collection flow works:**

```
adapter.py collect()
  │
  ├─ auth.py ── POST login.microsoftonline.us/{tenant}/oauth2/v2.0/token
  │              └─ Returns Bearer access_token (cached, auto-refreshed)
  │
  ├─ azure_client.py ── GET management.usgovcloudapi.net/...
  │                      ├─ Follows nextLink pagination automatically
  │                      ├─ Retries on HTTP 429 (respects Retry-After)
  │                      └─ Retries on 5xx with exponential backoff
  │
  └─ collectors/* ── Each collector:
       ├─ Calls azure_client.get_all() for its resource type
       ├─ Creates Aria Operations objects with properties
       └─ Defines parent→child relationships
```

### Step 6 — Customize What Gets Collected (Optional)

#### Add or Remove Resource Types

Each collector is a standalone module. To disable a resource type, comment it out in `adapter.py`:

```python
# In the collect() function, comment out any collector you don't need:
# collect_sql_servers_and_databases(client, result, ADAPTER_KIND, subscriptions)
# collect_app_services(client, result, ADAPTER_KIND, subscriptions)
```

Also remove the corresponding object type definition from `get_adapter_definition()` in the same file.

#### Add New Properties to an Existing Collector

To collect additional attributes from a resource (e.g., add `priority` to load balancer rules):

1. Open the collector file (e.g., `Azure/app/collectors/load_balancers.py`)
2. Add `obj.with_property("your_new_property", props.get("yourField", ""))` in the collection loop
3. Open `Azure/app/adapter.py` and add the matching definition:
   ```python
   lb.define_string_property("your_new_property", "Your New Property")
   ```
4. Rebuild — the SDK auto-generates `describe.xml` from `get_adapter_definition()`

#### Add a New Resource Type

To add a completely new Azure resource (e.g., Azure Cosmos DB):

1. Create `Azure/app/collectors/cosmos_db.py` following the pattern of existing collectors
2. Add the object type key in `constants.py`:
   ```python
   OBJ_COSMOS_DB = "azure_cosmos_db"
   ```
3. Add the API version in `constants.py`:
   ```python
   "cosmos_db": "2024-05-15",
   ```
4. Define the object type in `get_adapter_definition()` in `adapter.py`
5. Import and call the collector in the `collect()` function in `adapter.py`
6. Export it from `collectors/__init__.py`

#### Switch to Commercial Azure

Change `cloud_environment` to `"commercial"` in `connections.json`. The adapter automatically switches endpoints:

| Setting | Government | Commercial |
|---------|-----------|------------|
| ARM endpoint | `management.usgovcloudapi.net` | `management.azure.com` |
| Auth endpoint | `login.microsoftonline.us` | `login.microsoftonline.com` |
| Token scope | `management.usgovcloudapi.net/.default` | `management.azure.com/.default` |

#### Change API Versions

If an API version isn't available in Azure Gov yet, edit `Azure/app/constants.py`:

```python
API_VERSIONS = {
    "virtual_machines": "2024-07-01",   # Lower this if Azure Gov returns 400
    "disks": "2024-03-02",
    # ...
}
```

Azure Gov API versions may lag 1-2 releases behind commercial Azure. If you get a `400 Bad Request` or `NoRegisteredProviderFound`, try the previous stable version.

### Step 7 — Test Locally

```bash
cd Azure
mp-test
```

This command:
1. Spins up a Docker container simulating the Aria Operations collector
2. Reads credentials from `connections.json`
3. Calls `test()` to validate connectivity
4. Calls `collect()` to run a full collection cycle
5. Displays all discovered objects, properties, metrics, and relationships

**Expected output** (example):

```
Testing connection...
  ✓ Successfully connected. Found 2 subscription(s).

Running collection...
  Collecting subscriptions...         2 found
  Collecting resource groups...       8 found
  Collecting virtual machines...     15 found
  Collecting disks...                23 found
  Collecting network interfaces...   18 found
  Collecting virtual networks...      4 found
  Collecting storage accounts...      6 found
  Collecting load balancers...        2 found
  Collecting key vaults...            3 found
  Collecting SQL servers...           1 found (2 databases)
  Collecting app services...          4 found

Collection complete: 86 objects, 1,240 properties, 78 relationships
```

**If the test fails:**

| Error | Fix |
|-------|-----|
| `Connection refused` | Check Docker is running |
| `401 Unauthorized` | Verify tenant_id, client_id, client_secret in connections.json |
| `403 Forbidden` | Service principal needs Reader role on the subscription |
| `Module not found` | Run `pip install -r Azure/app/requirements.txt` |

### Step 8 — Build the .pak File

```bash
cd Azure
mp-build
```

This command:
1. Reads `get_adapter_definition()` from `adapter.py`
2. Auto-generates `conf/describe.xml` from the definition (overwriting the manual version)
3. Packages all files into a `.pak` archive (ZIP with deflate compression)
4. Outputs the file (e.g., `AzureGovAdapter-1.0.0.pak`)

> **Tip:** To inspect the `.pak` contents, rename it to `.zip` and extract.

### Step 9 — Deploy to Aria Operations

1. Log in to your **Aria Operations** instance
2. Navigate to **Administration > Integrations** (or **Administration > Solutions**)
3. Click **Add** and upload the `.pak` file
4. **Check "Ignore the PAK file signature checking"** — SDK-built packs are unsigned
5. Accept the EULA and wait for installation

### Step 10 — Configure the Adapter Instance

1. Go to **Administration > Integrations > Accounts > Add Account**
2. Select **Azure Government Cloud** from the adapter type dropdown
3. Fill in:

| Field | Value |
|-------|-------|
| **Display Name** | `Azure Gov - Production` |
| **Cloud Environment** | `government` (dropdown) |
| **Credential Type** | `Azure Credentials` |
| **Tenant ID** | Your Azure Gov tenant GUID |
| **Client ID** | Your app registration client ID |
| **Client Secret** | Your app registration client secret |
| **Subscription ID** | Target subscription GUID (or leave blank for all) |

4. Click **Validate Connection**
   - Expected: `"Successfully connected. Found X subscription(s)."`
5. Set **Collection Interval** (default 5 minutes; 10 minutes recommended for large environments)
6. Select the **Collector/Group** to run the adapter on
7. Click **Save**

### Step 11 — Verify Collection

1. **Wait 5-15 minutes** for the first collection cycles to complete
2. Check the adapter status:
   - **Administration > Integrations** — collector indicator should turn **green**
   - If yellow/red, click the adapter and check the **Collection Status** tab for errors
3. Navigate to **Inventory > Other Objects** or search for "Azure" to find your resources
4. Click any object to see its collected properties:
   - VM example: vm_size, power_state, os_type, image_sku, location, tags, etc.
5. Check **Relationships** tab on any object to verify parent-child hierarchy:
   ```
   Subscription
     └─ Resource Group
          ├─ Virtual Machine
          ├─ Disk
          ├─ Network Interface
          ├─ Virtual Network
          │    └─ Subnet
          ├─ Storage Account
          ├─ Load Balancer
          ├─ Key Vault
          ├─ SQL Server
          │    └─ SQL Database
          └─ App Service
   ```

### Step 12 — Iterate and Redeploy

When you modify collectors or add resource types:

```bash
# Make code changes
# Test locally
cd Azure && mp-test

# Build new .pak
mp-build

# Upload new .pak to Aria Operations (same process as Step 9)
# The existing adapter instance picks up the new version automatically
```

> **Version bumping:** Update the `"version"` field in `Azure/manifest.txt` before each redeploy (e.g., `1.0.0` → `1.1.0`). Aria Operations uses this to track pack versions.

---

## Azure Gov Endpoint Reference

All Azure Government Cloud endpoints differ from commercial Azure:

| Service | Commercial Azure | Azure Government |
|---------|-----------------|------------------|
| **Resource Manager (ARM)** | `management.azure.com` | `management.usgovcloudapi.net` |
| **Authentication (Entra ID)** | `login.microsoftonline.com` | `login.microsoftonline.us` |
| **Portal** | `portal.azure.com` | `portal.azure.us` |
| **Key Vault** | `vault.azure.net` | `vault.usgovcloudapi.net` |
| **Blob Storage** | `blob.core.windows.net` | `blob.core.usgovcloudapi.net` |
| **SQL Database** | `database.windows.net` | `database.usgovcloudapi.net` |
| **App Service** | `azurewebsites.net` | `azurewebsites.us` |
| **Container Registry** | `azurecr.io` | `azurecr.us` |
| **Redis Cache** | `redis.cache.windows.net` | `redis.cache.usgovcloudapi.net` |
| **Service Bus / Event Hubs** | `servicebus.windows.net` | `servicebus.usgovcloudapi.net` |
| **Cosmos DB** | `documents.azure.com` | `documents.azure.us` |

Azure Gov regions: **US Gov Virginia**, **US Gov Arizona**, **US Gov Texas**, **US DoD Central**, **US DoD East**

---

## Collected Resource Types

This management pack collects attributes from 13 Azure resource types:

| Resource Type | Key Attributes |
|---------------|---------------|
| **Subscriptions** | ID, display name, state, tenant, quota, spending limit |
| **Resource Groups** | Name, location, provisioning state, tags |
| **Virtual Machines** | VM size, power state, OS type, image (publisher/offer/SKU), computer name, disk info, NIC count, security profile, availability zone, tags |
| **Managed Disks** | SKU (Premium/Standard/Ultra), size GB, IOPS, throughput MBps, disk state, encryption type, zones |
| **Network Interfaces** | Private/public IPs, MAC address, NSG, subnet, DNS servers, IP forwarding, attached VM |
| **Virtual Networks** | Address prefixes, DNS servers, DDoS protection, subnets |
| **Subnets** | Address prefix, NSG, route table, service endpoints |
| **Storage Accounts** | Kind, SKU/tier, access tier, TLS version, endpoints, encryption, network rules |
| **Load Balancers** | SKU, frontend IPs, backend pools, rules, probes, NAT rules |
| **Key Vaults** | URI, SKU, soft delete, purge protection, RBAC auth, retention days |
| **SQL Servers** | FQDN, version, state, TLS version, public network access |
| **SQL Databases** | SKU/tier/capacity, max size, collation, service objective, zone redundancy |
| **App Services** | Kind (web/function), state, host names, HTTPS-only, outbound IPs, availability |

All resource types also collect **tags** as dynamic properties (each tag becomes `tag_<key>` = `<value>`).

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|---------|
| **Authentication fails with 401** | Wrong tenant/client/secret or expired secret | Verify credentials in Azure Gov portal; regenerate secret if expired |
| **"AADSTS700016: Application not found"** | Client ID doesn't exist in the specified tenant | Confirm tenant_id and client_id are from the same Azure Gov Entra ID tenant |
| **Empty VM list (0 objects)** | Service principal lacks Reader role | Assign Reader role on the subscription via IAM |
| **HTTP 403 on specific resources** | Insufficient RBAC permissions | Grant Reader role at subscription scope (not resource group) to cover all resource types |
| **HTTP 429 Too Many Requests** | Rate limit exceeded | SDK handles this automatically with retry. For MP Builder, reduce collection frequency |
| **"nextLink" data missing** | MP Builder doesn't follow cursor pagination | Use the SDK approach (Path B) for environments with >1000 resources per type |
| **Collector stays red in Aria Ops** | Network/firewall blocking outbound HTTPS | Ensure the Aria Operations collector node can reach `login.microsoftonline.us:443` and `management.usgovcloudapi.net:443` |
| **API version not supported** | Azure Gov lags behind commercial Azure | Lower the `api-version` parameter (e.g., from `2024-07-01` to `2024-03-01`) |
| **SSL certificate errors** | Self-signed or untrusted certs on proxy | Set SSL to "Unverified" in MP Builder, or import the cert to the truststore |
| **Objects appear but no properties** | Attributes not selected in Object definition | Re-open the Object in MP Builder, ensure attribute checkboxes are ticked |
