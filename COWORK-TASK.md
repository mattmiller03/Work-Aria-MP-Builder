# RG-Casing Fix — Collector Sweep Task (for Claude Cowork)

**Context:** The "zero relationships" defect in the Aria Azure MP was root-caused
on 2026-07-16 to Resource Group ID casing: ~20 collectors emitted
`rg_id = f"/subscriptions/{sub_id}/resourceGroups/{rg_name}".lower()` while the
RG objects ingested in Aria Ops are keyed with original Azure casing. `ID` is a
uniqueness-bearing identifier, so lowercased edge references silently fail to
resolve node-side. The fix is a canonical `rg_lookup` pattern (already
implemented in `helpers.py`): **lowercase for dict lookups, NEVER for emitted
identifier values.**

## Step 1 — Replace these 9 files with the completed versions

The completed versions sit in `_completed/` next to this file. Copy them over
the existing files in `Azure-Native-Build/app/` (collector files go in
`app/collectors/`):

| Completed file | Destination |
|---|---|
| helpers.py | app/helpers.py |
| adapter.py | app/adapter.py |
| resource_groups.py | app/collectors/resource_groups.py |
| virtual_machines.py | app/collectors/virtual_machines.py |
| dedicated_hosts.py | app/collectors/dedicated_hosts.py |
| disks.py | app/collectors/disks.py |
| app_service_plans.py | app/collectors/app_service_plans.py |
| app_services.py | app/collectors/app_services.py |
| bulk_resources.py | app/collectors/bulk_resources.py |

`disks.py` is the **reference implementation** of the sweep pattern below.

## Step 2 — Apply the 3-edit pattern to each remaining collector

Every collector in `app/collectors/` that still contains
`resourceGroups/{rg_name}".lower()` gets exactly three edits:

1. **Import** — add `reference_resource_group` to the `from helpers import (...)` list.
2. **Signature** — add `rg_lookup: dict = None` as the last parameter of the
   `collect_*` function (adapter.py already passes it by keyword).
3. **Replace the RG-edge block** — the old form:
   ```python
   rg_id = f"/subscriptions/{sub_id}/resourceGroups/{rg_name}".lower()
   rg_obj = result.object(
       adapter_kind=adapter_kind,
       object_kind=OBJ_RESOURCE_GROUP,
       name=rg_name,
       identifiers=make_identifiers([
           (RES_IDENT_SUB, sub_id),
           (RES_IDENT_ID, rg_id),
       ]),
   )
   obj.add_parent(rg_obj)
   ```
   becomes:
   ```python
   rg_obj = reference_resource_group(
       result, adapter_kind, sub_id, rg_name, rg_lookup)
   if rg_obj is not None:
       obj.add_parent(rg_obj)
   ```
   Keep the surrounding `if rg_name:` guard if present. Add a short comment
   noting the 2026-07-16 casing fix (see disks.py for wording).

**Files to sweep:** network_interfaces.py, virtual_networks.py,
storage_accounts.py, load_balancers.py, key_vaults.py, sql_databases.py,
functions_apps.py, cosmos_db.py, postgresql_servers.py, mysql_servers.py,
public_ips.py, expressroute.py, recovery_vaults.py, log_analytics.py,
generic_arm.py.

**Special cases:**
- **generic_arm.py** — also add `rg_lookup: dict = None` to the
  `collect_generic_arm_resources` signature (bulk_resources.py already passes
  it as a keyword arg). The `.lower()` site is ~line 134.
- **key_vaults.py** — nonstandard: its signature takes `rgs_by_sub`. Apply the
  pattern but review the whole file manually; its RG handling may differ.

## Step 3 — DO NOT TOUCH

- `dedicated_hosts.py` DH identifier tuples (`RES_IDENT_RG, rg_name.lower()`
  etc.) and the matching VM->DH stub in `virtual_machines.py` — deliberate
  lowercase convention, byte-matched on both sides, already correct.
- Any `.lower()` used for dict lookups (`vm_lookup.get(x.lower())`,
  `power_lookup`, cost/advisor caches) or string comparisons
  (`"functionapp" in kind.lower()`).
- `regions.py`, `pricing.py`, `subscriptions.py`, subnet handling.

## Step 4 — Gates before commit

1. **constants.py verification** — confirm these values (if any differ, fix
   helpers.py to match and report the difference):
   - `RES_IDENT_SUB == "AZURE_SUBSCRIPTION_ID"`
   - `RES_IDENT_RG == "AZURE_RESOURCE_GROUP"`
   - `RES_IDENT_REGION == "AZURE_REGION"`
   - `RES_IDENT_ID == "ID"`
   - `OBJ_RESOURCE_GROUP == "AZURE_RESOURCE_GROUP"`
2. **Zero remaining hits:**
   ```
   grep -rn 'resourceGroups/{rg_name}".lower()' Azure-Native-Build/app/
   ```
   must return nothing.
3. **Survivor audit:** `grep -rn '\.lower()' Azure-Native-Build/app/collectors/`
   — every remaining hit must be a dict lookup, comparison, or a documented
   DH-convention tuple.
4. **Single commit** — adapter.py passes `rg_lookup=` by keyword to every
   collector, so a partially-migrated tree fails at collect time with
   TypeError (by design). All files land together.
5. Bump `manifest.txt` version to **>= 8.19.232**.

## After commit (handled outside Cowork)

Transfer to the air-gapped MP Builder server, then: mp-test payload check
(`grep -c 'resourcegroups/' logs/test.log` — expect 0) -> build -> push
versioned tag AND latest -> pull + restart all 9 containers on Cloud Proxy
(verify single image sha via docker inspect) -> re-run PARENT/CHILD Suite API
query on test VM 198b9e46-e830-4cc0-8226-db81b0e7e0a0 -> then (Phase 5) run
the lowercase-RG orphan cleanup script.
