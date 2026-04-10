# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Custom VMware Aria Operations management pack that collects resource attributes from **Azure Government Cloud** using the VCF Operations Integration SDK 1.3.1 (Python). Deployed on Aria Ops 8.18.6 Enterprise (air-gapped) with a container-based adapter running on a Cloud Proxy.

**Current version:** 1.4.0 with 18 resource types collecting ~17,000 objects. Includes dedicated host costing (hourly/monthly rates from Azure Retail Prices API with air-gapped fallback) and full parent-child relationships (Host > VM > Disk).

## Architecture

```
Azure/
├── Dockerfile                  # FROM base-adapter:python-1.2.0
├── commands.cfg                # Maps HTTP endpoints to adapter subprocess commands
├── manifest.txt                # Pack metadata — platform MUST be ["Linux Non-VA", "Linux VA"]
├── config.json                 # Container registry config (git-ignored)
├── connections.json.example    # Credential template
├── app/
│   ├── adapter.py              # Main entry point (collect, test, get_adapter_definition, main dispatcher)
│   ├── constants.py            # Adapter keys, Azure Gov endpoints, API versions, object type keys
│   ├── auth.py                 # OAuth2 client credentials flow (login.microsoftonline.us)
│   ├── azure_client.py         # REST client with nextLink pagination + rate-limit retry
│   ├── helpers.py              # SDK compat: make_identifiers(), safe_property(), extract_resource_group()
│   ├── pricing.py              # Azure Retail Prices API client with air-gapped fallback table
│   ├── collectors/             # 18 per-resource-type modules
│   └── wheels/                 # Bundled Python wheels for air-gapped Docker builds
├── fetch_pricing.py            # Standalone script to update fallback pricing from internet-connected PC
├── conf/describeSchema.xsd     # VMware validation schema (do not modify)
└── content/                    # Dashboards (built in Aria Ops UI, see docs/)
```

## SDK Compatibility Notes (CRITICAL)

The SDK lib is v1.1.0. These patterns differ from newer SDK versions:

- **Identifiers:** Use `define_string_identifier()`, NOT `define_string_property(is_part_of_uniqueness=True)`
- **Credentials:** Use `adapter_instance.get_credential_value(key)` directly, NOT `get_credential(type).get_credential_value(key)`
- **Properties:** Use `safe_property(obj, key, value)` from helpers.py to prevent None values
- **Relationships:** Use `child.add_parent(parent)`, NOT `result.add_relationship(parent, child)`
- **TestResult:** Has no `with_message()` method — a successful test just returns without calling `with_error()`
- **Entry point:** adapter.py uses pipe-based dispatch via `main(sys.argv[1:])`, not `start_adapter()`
- **Identifiers must be `Identifier` objects**, not tuples — use `make_identifiers()` from helpers.py

## Build Commands (Air-Gapped)

```bash
# On MP Builder server (Photon 4.0 OVA)
cd /opt/aria/Aria-MP-Builder/Azure

# Test locally
sudo mp-test --port 8181

# Build .pak — MUST use -i flag for insecure collector communication
sudo mp-build -i --no-ttl --registry-tag "<REGISTRY-IP>:5000/azuregovcloud-adapter" -P 8181

# Push image to local registry
sudo docker tag azuregovcloud-test:<VERSION> <REGISTRY-IP>:5000/azuregovcloud-adapter:latest
sudo docker push <REGISTRY-IP>:5000/azuregovcloud-adapter:latest
```

See `docs/rebuild-steps.md` for full step-by-step rebuild process.

## Dedicated Host Costing

Pricing is fetched from the Azure Retail Prices API (`prices.azure.com`) at collection time. In air-gapped environments where the Cloud Proxy can't reach the API, it falls back to a hardcoded table in `app/pricing.py`.

To update the fallback table from an internet-connected PC:
```bash
python fetch_pricing.py --no-verify --update app/pricing.py
```

### Relationship Hierarchy

```text
Host Group > Dedicated Host > VM > Disk
```

- VMs link to hosts via `properties.host.id` from the Azure VM API
- Disks link to VMs via the `managedBy` field from the Azure Disk API
- Dedicated hosts show: `hourly_rate`, `monthly_rate_estimate`, `vm_size_summary`, `vm_disk_skus`, `allocatable_vm_summary`

### Dashboard

Built in Aria Ops UI (not in the pak). See `docs/dashboard-dedicated-host-detail.md` for step-by-step build guide.

## Deployment Gotchas (Air-Gapped Aria Ops 8.18.6)

- **manifest.txt platform:** MUST be `["Linux Non-VA", "Linux VA"]` — bare `["Linux"]` crashes pak manager
- **manifest.txt fields:** Must include `display_name`, `disk_space_required`, `adapters`, `license_type`
- **API_PORT:** Container adapter uses 8080/HTTP (set via `-i` build flag). Port 443 conflicts with Cloud Proxy's config-modules container
- **REGISTRY in .conf:** Must be explicitly set — without it, Cloud Proxy tries `harbor-repo.vmware.com`
- **Cloud Proxy Docker certs:** Must copy registry cert to `/etc/docker/certs.d/<IP>:5000/ca.crt`
- **Azure Gov API versions:** Use 2023-xx — newer versions return 502 Bad Gateway
- **Unsigned pak STIG:** No way to self-sign; document exception with security team

## Azure Gov Endpoints

| Service | Endpoint |
|---------|----------|
| ARM | `management.usgovcloudapi.net` |
| Auth | `login.microsoftonline.us` |
| Token scope | `https://management.usgovcloudapi.net/.default` |
| Key Vault | `vault.usgovcloudapi.net` |
| Storage | `*.core.usgovcloudapi.net` |
| SQL | `database.usgovcloudapi.net` |
