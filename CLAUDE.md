# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Custom VMware Aria Operations management pack that collects resource attributes from **Azure Government Cloud** using the VCF Operations Integration SDK (Python). The pack authenticates via OAuth2 client credentials to Azure Gov ARM APIs and discovers/monitors VMs, Disks, NICs, VNets, Storage Accounts, Key Vaults, SQL Databases, Load Balancers, App Services, and more.

## Architecture

```
Azure/
├── app/
│   ├── adapter.py          # Main adapter — defines collect(), test(), get_adapter_definition()
│   ├── constants.py         # Adapter kind key, object type keys, API versions
│   ├── auth.py              # OAuth2 client credentials flow against Azure Gov Entra ID
│   ├── azure_client.py      # REST client with pagination (nextLink), rate-limit handling
│   ├── collectors/          # Per-resource-type collection modules
│   │   ├── virtual_machines.py
│   │   ├── disks.py
│   │   ├── network_interfaces.py
│   │   ├── virtual_networks.py
│   │   ├── storage_accounts.py
│   │   ├── key_vaults.py
│   │   ├── sql_databases.py
│   │   ├── load_balancers.py
│   │   ├── app_services.py
│   │   ├── resource_groups.py
│   │   └── subscriptions.py
│   └── requirements.txt     # requests, etc.
├── conf/
│   └── describe.xml         # Adapter object model (resource kinds, metrics, properties, credentials)
├── resources/
│   └── resources.properties # Localization keys
├── manifest.txt             # MP metadata (name, version, adapter_kinds)
├── eula.txt                 # License agreement
└── connections.json         # Test connection config (not shipped in .pak)
```

### Key Design Decisions

- **SDK approach over MP Builder GUI**: The code-based SDK gives full control over Azure Gov's OAuth2 token lifecycle, nextLink pagination, retry/rate-limiting, and multi-subscription enumeration.
- **Azure Gov endpoints**: All API calls target `management.usgovcloudapi.net` (ARM) and `login.microsoftonline.us` (auth). These differ from commercial Azure.
- **Token scope**: `https://management.usgovcloudapi.net/.default`
- **Pagination**: Azure ARM uses cursor-based pagination via `nextLink` in response bodies. Always follow the full nextLink URL as-is.

## Build & Development Commands

```bash
# Install the SDK
pip install vmware-aria-operations-integration-sdk

# Scaffold a new project (interactive)
mp-init

# Test adapter locally against a target environment
mp-test

# Build the .pak file for deployment to Aria Operations
mp-build
```

### Deploy to Aria Operations

1. Upload `.pak` via **Administration > Solutions/Integrations**
2. Disable signature checking for unsigned packs
3. Configure adapter instance with Azure Gov credentials (tenant_id, client_id, client_secret, subscription_id)
4. Validate connection, then collection starts within ~5 minutes

## Azure Gov Authentication Flow

```
POST https://login.microsoftonline.us/{tenant_id}/oauth2/v2.0/token
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
&client_id={client_id}
&client_secret={client_secret}
&scope=https://management.usgovcloudapi.net/.default
```

The returned `access_token` (Bearer) is used in `Authorization` header for all ARM calls.

## Azure Gov Endpoint Quick Reference

| Service | Endpoint |
|---------|----------|
| ARM | `management.usgovcloudapi.net` |
| Auth | `login.microsoftonline.us` |
| Key Vault | `vault.usgovcloudapi.net` |
| Storage | `*.core.usgovcloudapi.net` |
| SQL | `database.usgovcloudapi.net` |

## Adapter Entry Points

The SDK expects three functions in `adapter.py`:

- **`get_adapter_definition()`** — Returns `AdapterDefinition` with all credential types, object types, metrics, and properties. The SDK auto-generates `describe.xml` from this.
- **`collect(adapter_instance)`** — Called each collection cycle. Authenticates to Azure Gov, enumerates subscriptions/resource groups, calls each collector, returns `CollectResult` with objects, metrics, properties, and relationships.
- **`test(adapter_instance)`** — Validates credentials and connectivity. Called when user clicks "Test Connection" in Aria Operations.

## Rate Limiting

Azure Gov currently uses legacy hourly limits: 12,000 reads/hour per service principal per subscription. Monitor `x-ms-ratelimit-remaining-subscription-reads` response header. On HTTP 429, respect `Retry-After` header.
