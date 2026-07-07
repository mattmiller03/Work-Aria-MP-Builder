# HANDOFF — Aria Azure Management Pack (resume brief)

**Last updated:** 2026-07-07
**Purpose:** Load this into a fresh Claude session (desktop / dispatch) to continue the Aria/Azure MP work with full context. Self-contained — read it top to bottom before acting.

---

## 1. What this project is

A custom **VMware Aria Operations 8.18.6** management pack that collects **Azure Government Cloud** resource attributes (via the VCF Operations Integration SDK, Python) and renders them in Aria Ops. Deployed **air-gapped**, container-based adapter running on a Cloud Proxy. ~16K objects across ~18 resource types, plus dedicated-host costing and parent-child relationships.

Repo root: `Work Projects/Aria/MP Builder` (this is the git repo; the `Aria/` parent is not).

## 2. Two build variants (important)

| Dir | What it is | Status |
|---|---|---|
| **`Azure/`** | Original *fully-custom* pak with custom `AzureGovCloud` object kinds. | Known-good; installed + collected ~16K objects at v1.x. Safe fallback. |
| **`Azure-Native-Build/`** | **"Phase D"** — reuses VMware's *native* `MicrosoftAzureAdapter` `describe.xml` + dashboards and substitutes Azure Gov data into the native ResourceKinds so the polished native dashboards render. | **This is the one failing install. All current work is here.** |

The native-substitution magic is `scripts/patch-describe-xml.py` (a "dynamic native loader") — at build time it splices verbatim native XML for equivalent kinds into the pak's `describe.xml`. `scripts/build-pak.sh` runs `mp-build -i --no-ttl`, then patches the `describe.xml` **inside** the built `.pak` and repacks. Output: `Azure-Native-Build/build/*.pak`.

Native reference describe.xml: `sdk_packages/MicrosoftAzureAdapter-818024067771/AzureAdapter/MicrosoftAzureAdapter/conf/describe.xml`.

## 3. The blocker

The `Azure-Native-Build` pak **fails to install**: upload reaches Aria Ops **step 16/20 `APPLY_ADAPTER` → `ERROR after 0.0 seconds` with an empty errorMessages array** = Suite-API rejecting the patched `describe.xml` synchronously (the real error is not shown in the UI).

Defects chased in late April 2026: pipe (`|`) chars in `ResourceAttribute` keys; a **duplicate `AZURE_PUBLIC_IPADDRESSES` ResourceKind**; `type`/`identType` mismatches; missing root `xsi:schemaLocation`; adapter-instance kind renamed to `MicrosoftAzureAdapter Instance` + `monitoringInterval="10"`. Whether these are all resolved in the current pak is **exactly what the Stage A diagnostic below re-establishes.**

**Separate, non-code failure to know about:** an intermittent build-time 500 (`adapterDefinition endpoint returned 500`) is **`/tmp` full** on the Photon server (`OSError Errno 28` in swagger_server's `tempfile.mkdtemp()`), from accumulated zombie `microsoftazureadapter-test` containers. The diagnostic + `build-pak.sh` both reap zombies to prevent it.

## 4. Current code state (as of this handoff)

`Azure-Native-Build/app/adapter.py` is at the **full ~50-kind configuration**: the old `if False:` phase gates are gone; the geo trio (World / Region / Region-Per-Sub) and the `ALL_NATIVE_STUB_KINDS` loop are active. The `regions.py` collector bug (`'CollectResult' object has no attribute get_objects`) is **already fixed** (uses `result.objects.values()`). Working tree is clean; last commit before resuming was `roll back commit` (touched only `debug/build.log`).

## 5. Air-gapped workflow (division of labor)

- **Claude / dev box (Windows):** edits code, commits/pushes to `origin/main`. **Cannot** build or install — no SDK base image, no Aria Ops here.
- **User / Photon "MP Builder" server** (`/opt/aria/Aria-MP-Builder`): pulls (or hand-copies) code, runs `bash scripts/build-pak.sh`, pushes image to local registry `214.73.76.134:5000`, uploads `.pak` via Aria Ops UI.

Each cycle: **edit + push → pull/build/install on server → paste logs back → diagnose.** Server transfers use `git fetch origin && git reset --hard origin/main` (reset preferred over pull). The live env is **not** network-reachable from the dev box.

## 6. IMMEDIATE NEXT STEP — re-diagnose (decided approach)

We are **re-establishing the exact reject from a real signal** rather than editing blind after a 2-month gap. On the MP Builder server:

```bash
cd /opt/aria/Aria-MP-Builder
git fetch origin && git reset --hard origin/main    # or hand-copy scripts/diagnose-install.sh
bash scripts/diagnose-install.sh 2>&1 | tee /tmp/aria-diag.out
```

Then read the **`XMLLINT SCHEMA VALIDATION`** block in the output:

- **Schema errors printed** (`describe.xml:NNN: element ... is not a valid value ...`) → *structural* reject. Fix precisely in `scripts/patch-describe-xml.py` (or the adapter definition) at the named line/element.
- **`describe.xml validates`** → structurally clean; reject is *semantic*. Upload the `.pak` in the Aria Ops UI, let it fail, then:
  ```bash
  bash scripts/diagnose-install.sh analytics
  ```
  which greps `/storage/log/vcops/log/analytics-*.log*` for the real reject.

Paste the diagnostic output back to Claude to pick the fix.

## 7. Key files

- `scripts/diagnose-install.sh` — the diagnostic runbook (Stage A build+validate, `analytics` = Stage B).
- `scripts/build-pak.sh` — build + patch + repack wrapper.
- `scripts/patch-describe-xml.py` — the describe.xml patcher / dynamic native loader (largest, most-edited file; most likely fix site).
- `Azure-Native-Build/app/adapter.py` — `get_adapter_definition()` (kind registrations) + `collect()`.
- `Azure-Native-Build/app/constants.py` — `ALL_NATIVE_STUB_KINDS`, object-type keys.
- `docs/diagnose-apply-adapter-failure.md` — full xmllint diagnosis playbook + error→fix table.
- `docs/phase-d-rollout.md` — phased rollout runbook (D.2 24 kinds → D.3 27 → D.4 ~50).

## 8. Environment specifics

- Server path: `/opt/aria/Aria-MP-Builder`
- Adapter kind (manifest.txt `adapter_kinds[0]`): `MicrosoftAzureAdapter`
- Local registry: `214.73.76.134:5000/azuregovcloud-adapter` — **OPEN QUESTION: confirm this IP/registry host still matches the environment; it does not affect the xmllint diagnosis but is needed for the push + install step.**
- Base image: `base-adapter:python-1.2.0` (cannot be re-pulled air-gapped — do not aggressively `docker prune -a`).
- manifest.txt platform MUST be `["Linux Non-VA", "Linux VA"]`; API_PORT 8080/HTTP via `-i` build flag; Azure Gov API versions use 2023-xx.

## 9. Open decisions / forks

- Confirm registry IP (§8).
- If native-substitution stays blocked after this diagnostic round, the fallback is to ship/refresh the known-good custom `Azure/` pak and treat native dashboards as a stretch goal.
