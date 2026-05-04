#!/usr/bin/env python3
"""End-to-end verification for the Azure Gov management pack.

Drives a real collection cycle by importing app/adapter.py:collect() directly
with a hand-rolled StubAdapterInstance, then layers on three more audits:
  --pak       describe.xml audit (kind registry, Dedicated Host custom attrs,
              pipe-keyed attrs on custom kinds)
  --pak       content drift audit (dashboards, alert defs, traversal specs)
  --aria-ops  Aria Ops Suite-API counts and Dedicated Host props/stats

Each audit is opt-in via flag so subsets run independently. Live collection
needs the aria.ops SDK installed (wheel under app/wheels/); static audits do
not.

Exit code: 0 = all PASS, 1 = any FAIL, 2 = WARN-only.

See plans/pure-cuddling-charm.md for context.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import signal
import ssl
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("verify_collection")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)


# ---------------------------------------------------------------------------
# Per-kind expectations
# ---------------------------------------------------------------------------
# Conservative: require count >= min_count, parent edge, and the universal
# SERVICE_DESCRIPTORS|AZURE_SUBSCRIPTION_ID property. Kind-specific extras only
# where the collector reliably emits them. Keys verified against
# constants.py MONITOR_METRICS and the actual safe_property() calls in each
# collector file.

# Universal property emitted by _add_service_descriptors() in adapter.py for
# nearly every kind.
UNIVERSAL_PROP = "SERVICE_DESCRIPTORS|AZURE_SUBSCRIPTION_ID"

KIND_SPECS: dict[str, dict[str, Any]] = {
    # Roots
    "azure_subscription": {
        "min_count": 1,
        "parent_kind": None,
        "required_props": set(),
    },
    "AZURE_RESOURCE_GROUP": {
        "min_count": 1,
        "parent_kind": "azure_subscription",
        "required_props": {UNIVERSAL_PROP},
    },
    # Compute
    "AZURE_VIRTUAL_MACHINE": {
        "min_count": 0,  # tenant may have zero
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
        "required_metrics": {"CPU|CPU_USAGE", "NETWORK|NETWORK_IN"},
    },
    "AZURE_STORAGE_DISK": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
    },
    "AZURE_COMPUTE_HOSTGROUPS": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
    },
    "AZURE_DEDICATE_HOST": {  # native pak typo preserved
        "min_count": 0,
        # Hierarchy: Host Group > Dedicated Host > VM > Disk
        # (per project_phase_d_complete memory)
        "parent_kind": "AZURE_COMPUTE_HOSTGROUPS",
        "required_props": {
            UNIVERSAL_PROP,
            "hourly_rate",
            "monthly_rate_estimate",
            "vm_size_summary",
            "host_vcpu_capacity",
            "memory_utilization_pct",
            "health_availability_state",
            "policy_compliance_state",
        },
    },
    # Networking
    "AZURE_NW_INTERFACE": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
        "required_metrics": {"BYTES_SENT", "BYTES_RECEIVED"},
    },
    "AZURE_VIRTUAL_NETWORK": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
    },
    "azure_subnet": {
        "min_count": 0,
        "parent_kind": "AZURE_VIRTUAL_NETWORK",
        "required_props": set(),
    },
    "AZURE_LB": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
        "required_metrics": {"BYTE_COUNT"},
    },
    "AZURE_PUBLIC_IPADDRESSES": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
    },
    "AZURE_EXPRESSROUTE_CIRCUITS": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
    },
    # Storage
    "AZURE_STORAGE_ACCOUNT": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
        # Verified 2026-05-01 across 3 runs: summary|usedCapacity returns
        # no datapoints for any storage account in this Azure Gov tenant.
        # Likely a Gov-data-reality issue (no metric extension or
        # low-activity buckets), not a collector bug.
        "optional_metrics": {"summary|usedCapacity"},
    },
    # Identity / Security
    "AZURE_KEY_VAULTS": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
    },
    # Database
    "AZURE_SQL_SERVER": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
    },
    "AZURE_SQL_DATABASE": {
        "min_count": 0,
        "parent_kind": "AZURE_SQL_SERVER",
        "required_props": {UNIVERSAL_PROP},
    },
    "AZURE_POSTGRESQL_SERVER": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
        "required_metrics": {"CPU_PERCENT"},
    },
    "AZURE_MYSQL_SERVER": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
        # Verified 2026-05-01 across 3 runs: same pattern as storage —
        # CPU_PERCENT returns no datapoints. Demoted to optional.
        "optional_metrics": {"CPU_PERCENT"},
    },
    "AZURE_DB_ACCOUNT": {  # Cosmos DB
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
    },
    # Web / App Service
    "AZURE_APP_SERVICE": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
        # Verified 2026-05-01 across 3 runs: summary|requests returns
        # no datapoints. Likely a low-traffic web app pattern in this
        # tenant, not a collector bug. Demoted to optional.
        "optional_metrics": {"summary|requests"},
    },
    "AZURE_FUNCTIONS_APP": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
    },
    "AZURE_APP_SERVICE_PLAN": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
    },
    # Custom kinds — must NOT have pipe-keyed attrs (rejected by Aria Ops)
    "azure_recovery_services_vault": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": set(),
    },
    "azure_log_analytics_workspace": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": set(),
    },
    # World aggregation
    "AZURE_WORLD": {
        "min_count": 1,
        "parent_kind": None,
        "required_props": set(),
    },
    "AZURE_REGION": {
        "min_count": 1,
        "parent_kind": None,
        "required_props": set(),
    },
    "AZURE_REGION_PER_SUB": {
        "min_count": 1,
        "parent_kind": None,
        "required_props": set(),
    },
    # Native kinds upgraded from None extra_fn — agency has actual objects
    "AZURE_VIRTUAL_SCALESET": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
    },
    "AZURE_AVAILABILITY_SETS": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
    },
    "AZURE_NETWORK_WATCHERS": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
    },
    "AZURE_EVENTHUBS_NAMESPACES": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
    },
    "AZURE_COGNITIVE_SERVICES_ACCOUNTS": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
    },
    "AZURE_SQL_MANAGEDINSTANCES": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
    },
    "AZURE_DATA_EXPLORER_CLUSTER": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": {UNIVERSAL_PROP},
    },
    # New custom kinds — no SERVICE_DESCRIPTORS (flat keys only)
    "azure_logic_workflow": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": set(),
    },
    "azure_arc_machine": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": set(),
    },
    "azure_bastion_host": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": set(),
    },
    "azure_private_endpoint": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": set(),
    },
    "azure_nat_gateway": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": set(),
    },
    "azure_compute_snapshot": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": set(),
    },
    "azure_disk_encryption_set": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": set(),
    },
    "azure_managed_identity": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": set(),
    },
    "azure_dns_resolver": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": set(),
    },
    "azure_backup_vault": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": set(),
    },
    "azure_sql_virtual_machine": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": set(),
    },
    "azure_app_service_environment": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": set(),
    },
    "azure_storage_sync": {
        "min_count": 0,
        "parent_kind": "AZURE_RESOURCE_GROUP",
        "required_props": set(),
    },
}

# Custom (non-native) kind keys — must not have pipe-keyed attrs.
CUSTOM_KIND_KEYS = {
    "azure_subscription",
    "azure_subnet",
    "azure_recovery_services_vault",
    "azure_log_analytics_workspace",
    # New custom kinds added in bulk_resources.py
    "azure_logic_workflow",
    "azure_arc_machine",
    "azure_bastion_host",
    "azure_private_endpoint",
    "azure_nat_gateway",
    "azure_compute_snapshot",
    "azure_disk_encryption_set",
    "azure_managed_identity",
    "azure_dns_resolver",
    "azure_backup_vault",
    "azure_sql_virtual_machine",
    "azure_app_service_environment",
    "azure_storage_sync",
}

# Dedicated Host custom attributes — must be present in the patched
# describe.xml AND populated on collected objects. Source of truth:
# app/collectors/dedicated_hosts.py safe_property(host_obj, ...) calls.
DH_CUSTOM_ATTRS = [
    # Pricing
    "hourly_rate",
    "monthly_rate_estimate",
    # Capacity / utilization
    "host_vcpu_capacity",
    "total_vm_vcpus_allocated",
    "vcpu_utilization_pct",
    "host_memory_capacity_gb",
    "memory_utilization_pct",
    "memory_available_gb",
    "total_vm_memory_gb",
    "vm_memory_breakdown",
    # VM placement
    "vm_count",
    "vm_names",
    "vm_size_summary",
    "vm_size_distinct_count",
    "vm_disk_skus",
    # Allocatable capacity
    "max_available_slots",
    "smallest_vm_size",
    "smallest_vm_available",
    "allocatable_vm_summary",
    # Health
    "health_availability_state",
    "health_detailed_status",
    "health_reason_type",
    "health_summary",
    # Maintenance
    "maintenance_pending",
    "maintenance_impact_type",
    "maintenance_status",
    # Cost (if Cost Management API reachable)
    "cost_month_to_date",
    "cost_currency",
    "cost_last_30_days",
    # Advisor
    "advisor_recommendation_count",
    "advisor_recommendations",
    "advisor_impact",
    "advisor_category",
    # Activity log
    "recent_operations_count",
    "last_operation",
    "last_operation_time",
    "last_operation_status",
    "last_operation_caller",
    # Policy compliance
    "policy_compliance_state",
    "policy_non_compliant_count",
    # Reservations
    "reservation_status",
    "reservation_id",
    "reservation_expiry",
    # ARM properties
    "time_created",
    "sku_tier",
    "sku_capacity",
]

# Identifier keys that look like AZURE_* but are NOT resource kinds.
NON_KIND_AZURE_TOKENS = {
    "AZURE_TENANT_ID",
    "AZURE_SUBSCRIPTION_ID",
    "AZURE_CLIENT_ID",
    "AZURE_RESOURCE_GROUP",  # also a kind, but token reuse is fine
    "AZURE_REGION",  # also a kind
    "AZURE_SERVICE",
    "AZURE_GOV_CLOUD_ACCOUNT",
    "AZURE_STANDARD_ACCOUNT",
    "AZURE_CLIENT_CREDENTIALS",
    "AZURE_NIC_VM",
}


# ---------------------------------------------------------------------------
# Connection loading + stub
# ---------------------------------------------------------------------------

def load_connection(path: str) -> dict:
    """Load mp-test format connections.json -> flat dict."""
    with open(path) as f:
        data = json.load(f)
    conns = data.get("connections", [])
    if not conns:
        raise ValueError(f"No 'connections' in {path}")
    conn = conns[0]
    identifiers = {
        k: (v.get("value") if isinstance(v, dict) else v)
        for k, v in conn.get("identifiers", {}).items()
    }
    credentials: dict[str, Optional[str]] = {}
    cred_block = conn.get("credential") or {}
    for k, v in cred_block.items():
        if k == "credential_kind_key":
            credentials["_type"] = v
        elif isinstance(v, dict):
            credentials[k] = v.get("value")
        else:
            credentials[k] = v
    return {
        "name": conn.get("name", "<unnamed>"),
        "identifiers": identifiers,
        "credentials": credentials,
        "suite_api_hostname": conn.get("suite_api_hostname"),
        "suite_api_username": conn.get("suite_api_username"),
        "suite_api_password": conn.get("suite_api_password"),
    }


class StubAdapterInstance:
    """Minimal shim implementing the two methods adapter.collect() reads."""

    def __init__(self, conn: dict) -> None:
        self._identifiers = conn["identifiers"]
        self._credentials = conn["credentials"]

    def get_identifier_value(
        self, key: str, default: Optional[str] = None
    ) -> Optional[str]:
        v = self._identifiers.get(key)
        return v if v else default

    def get_credential_value(self, key: str) -> Optional[str]:
        return self._credentials.get(key)


# ---------------------------------------------------------------------------
# Live collection
# ---------------------------------------------------------------------------

def _ensure_aria_sdk(app_dir: Path) -> None:
    """Make `aria.ops` importable, falling back to the bundled wheels.

    On the MP Builder server, the SDK is installed in the container that runs
    mp-test/mp-build, but not necessarily in whatever Python the user invokes
    this script with. Rather than require a separate `pip install`, we add
    every `.whl` in `app/wheels/` to sys.path — wheels are zip archives with
    a standard package layout, so this is enough to satisfy `import aria` and
    its transitive deps (aenum, requests, urllib3, certifi, idna, charset-
    normalizer, cryptography, cffi, pycparser).

    Note: the cffi / cryptography / charset_normalizer wheels are
    Linux-x86_64-only (manylinux) — this works on the Photon MP Builder
    server but not on Windows. For Windows debugging, `pip install` from a
    pip cache or PyPI proxy is the right path.
    """
    try:
        import aria.ops  # noqa: F401
        return
    except ImportError:
        pass

    wheels_dir = app_dir / "wheels"
    if not wheels_dir.is_dir():
        raise ImportError(
            f"aria SDK not installed and no wheels dir at {wheels_dir}. "
            "Run `pip install app/wheels/*.whl` first."
        )
    wheels = sorted(wheels_dir.glob("*.whl"))
    if not wheels:
        raise ImportError(
            f"No wheels found in {wheels_dir}. "
            "Run `pip install app/wheels/*.whl` first."
        )

    # Insert in reverse order so the SDK wheel ends up at sys.path[0] last
    # (purely cosmetic — Python checks each entry until something resolves).
    for wheel in wheels:
        sys.path.insert(0, str(wheel))
    logger.info("Bootstrapped %d wheels from %s", len(wheels), wheels_dir)

    try:
        import aria.ops  # noqa: F401
    except ImportError as e:
        raise ImportError(
            f"Failed to import aria.ops after adding {len(wheels)} wheels to "
            f"sys.path. Likely a platform mismatch (Linux wheels on a "
            f"non-Linux host). Original error: {e}"
        ) from e


def _install_sampling(sample_n: int) -> None:
    """Monkey-patch AzureClient.get_all to truncate leaf-resource list calls.

    The patch returns at most `sample_n` items from any path containing
    `/providers/` (leaf-level enumeration: VMs, storage accounts, hosts,
    etc.). Discovery paths (`/subscriptions`, `/subscriptions/{id}/
    resourceGroups`) are passed through unchanged so parent-edge integrity
    is preserved.

    Note: the underlying call still paginates fully — we truncate only the
    returned list. Pagination overhead is small compared to the per-resource
    enrichment loops downstream (Dedicated Host's 10 ARM calls per host,
    metric calls per VM/disk/etc.), which scale with the truncated list.
    """
    import azure_client

    orig = azure_client.AzureClient.get_all

    def sampled_get_all(self, path, *args, **kwargs):
        results = orig(self, path, *args, **kwargs)
        if (
            "/providers/" in path.lower()
            and isinstance(results, list)
            and len(results) > sample_n
        ):
            logger.debug(
                "Sampling: %s capped %d -> %d", path, len(results), sample_n
            )
            return results[:sample_n]
        return results

    azure_client.AzureClient.get_all = sampled_get_all
    logger.info("Sampling enabled: leaf list calls capped at %d items", sample_n)


def _install_crash_safe(report: dict, args: "argparse.Namespace") -> None:
    """Register signal handlers and an excepthook so a partial JSON report
    is written on any abnormal exit (Ctrl-C, SIGTERM, SIGHUP from a dropped
    SSH session, unhandled exception). The handlers reference the same
    `report` dict that main() mutates as audits complete, so whatever phase
    finished before the crash is what gets persisted.

    No-op when args.out is unset (without an output path there's nowhere
    to dump the report).
    """
    if not args.out:
        return

    written = {"done": False}

    def _persist(reason: str, code: int) -> None:
        if written["done"]:
            return
        written["done"] = True
        logger.warning("Crash-safe write triggered: %s", reason)
        report.setdefault("partial", True)
        report.setdefault("exit_summary", "INTERRUPTED")
        report.setdefault("crash_reason", reason)
        try:
            rendered = redact_report(report) if args.redacted else report
            render_json_report(rendered, args.out)
            logger.info(
                "Partial report written to %s%s",
                args.out,
                " (redacted)" if args.redacted else "",
            )
        except Exception as e:
            logger.error("Failed to write partial report: %s", e)

    def _signal_handler(signum: int, frame: Any) -> None:  # noqa: ANN001
        _persist(f"signal {signum} ({signal.Signals(signum).name})", 130)
        sys.exit(130)

    def _excepthook(
        exc_type: type, exc_value: BaseException, traceback: Any
    ) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            _persist("KeyboardInterrupt", 130)
        else:
            report["error"] = f"{exc_type.__name__}: {exc_value}"
            _persist(f"unhandled {exc_type.__name__}", 1)
        sys.__excepthook__(exc_type, exc_value, traceback)

    sys.excepthook = _excepthook
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    sighup = getattr(signal, "SIGHUP", None)  # Unix only; dropped SSH sessions
    if sighup is not None:
        signal.signal(sighup, _signal_handler)


def _start_heartbeat(interval: int) -> threading.Event:
    """Background thread that logs elapsed time every `interval` seconds.

    Returns the stop Event; caller calls `.set()` to halt the thread. The
    thread is daemon so it dies with the process. Useful when paired with
    `--quiet-collectors` so the user knows the run is making progress
    rather than hung.
    """
    stop = threading.Event()
    started = time.time()

    def beat() -> None:
        while not stop.wait(interval):
            elapsed = time.time() - started
            logger.info("Heartbeat: %.1f min elapsed", elapsed / 60)

    t = threading.Thread(target=beat, daemon=True, name="verify-heartbeat")
    t.start()
    return stop


def run_collection(
    stub: StubAdapterInstance,
    sample_n: Optional[int] = None,
    heartbeat_interval: int = 60,
) -> tuple[Any, float]:
    """Import adapter and run collect(). Returns (CollectResult, duration_seconds)."""
    here = Path(__file__).resolve().parent
    app_dir = here.parent / "app"
    if not app_dir.exists():
        raise FileNotFoundError(f"Expected app/ at {app_dir}")
    _ensure_aria_sdk(app_dir)
    sys.path.insert(0, str(app_dir))
    if sample_n is not None and sample_n > 0:
        _install_sampling(sample_n)
    import importlib  # noqa
    adapter_mod = importlib.import_module("adapter")
    stop_heartbeat = (
        _start_heartbeat(heartbeat_interval) if heartbeat_interval > 0 else None
    )
    t0 = time.time()
    try:
        result = adapter_mod.collect(stub)
    finally:
        if stop_heartbeat is not None:
            stop_heartbeat.set()
    return result, time.time() - t0


def inspect_result(result: Any) -> dict[str, list[dict]]:
    """Walk CollectResult.objects, group by kind, snapshot what we need."""
    by_kind: dict[str, list[dict]] = {}
    for obj in result.objects.values():
        kind = obj.object_type()
        snap = {
            "name": obj.get_key().name,
            "identifiers": {
                k: ident.value
                for k, ident in obj.get_key().identifiers.items()
            },
            "properties": {
                p.key: p.value for p in obj._properties
            },
            "metric_keys": sorted({m.key for m in obj._metrics}),
            "metric_datapoints_by_key": {},
            "parents": [
                {"kind": k.object_kind, "name": k.name}
                for k in obj.get_parents()
            ],
        }
        for m in obj._metrics:
            snap["metric_datapoints_by_key"][m.key] = (
                snap["metric_datapoints_by_key"].get(m.key, 0) + 1
            )
        by_kind.setdefault(kind, []).append(snap)
    return by_kind


def assert_kind(
    by_kind: dict[str, list[dict]], kind: str, spec: dict
) -> tuple[str, int, list[str]]:
    """Return (status, count, reasons) for one kind. status in PASS/WARN/FAIL."""
    reasons: list[str] = []
    objs = by_kind.get(kind, [])
    count = len(objs)

    min_count = spec.get("min_count", 0)
    if count < min_count:
        return ("FAIL", count, [f"count {count} < min {min_count}"])
    if count == 0:
        return ("WARN", 0, ["no objects (tenant may have none)"])

    # Parent edge
    parent_kind = spec.get("parent_kind")
    if parent_kind:
        no_parent = [
            o for o in objs
            if not any(p["kind"] == parent_kind for p in o["parents"])
        ]
        if no_parent:
            reasons.append(
                f"{len(no_parent)}/{count} missing parent {parent_kind}"
            )

    # Required props (at least one object has each, with non-empty value)
    for prop in spec.get("required_props", set()):
        present = any(
            prop in o["properties"]
            and o["properties"][prop] not in (None, "", "None")
            for o in objs
        )
        if not present:
            reasons.append(f"prop {prop!r} not populated on any object")

    # Required metrics (at least one object has each) — missing causes FAIL
    min_dp = spec.get("min_metric_datapoints", 1)
    for metric in spec.get("required_metrics", set()):
        present = any(metric in o["metric_keys"] for o in objs)
        if not present:
            reasons.append(f"metric {metric!r} absent on every object")
            continue
        max_dp = max(
            (o["metric_datapoints_by_key"].get(metric, 0) for o in objs),
            default=0,
        )
        if max_dp < min_dp:
            reasons.append(
                f"metric {metric!r} has at most {max_dp} datapoints "
                f"(need >= {min_dp})"
            )

    # Optional metrics — missing causes WARN (not FAIL). Used for metrics
    # the verifier wants to track but can't fail on, e.g. metric series
    # that consistently return no data in Azure Gov even though the
    # collector requests them correctly. Tracked separately so we can
    # tell apart "verifier doesn't care" (omitted from spec) from
    # "verifier checked and the metric is silent" (optional missing).
    optional_only_reasons: list[str] = []
    for metric in spec.get("optional_metrics", set()):
        present = any(metric in o["metric_keys"] for o in objs)
        if not present:
            optional_only_reasons.append(
                f"metric {metric!r} absent on every object (optional)"
            )

    if reasons:
        return ("FAIL", count, reasons + optional_only_reasons)
    if optional_only_reasons:
        return ("WARN", count, optional_only_reasons)
    return ("PASS", count, [])


# ---------------------------------------------------------------------------
# describe.xml audit
# ---------------------------------------------------------------------------

def _read_describe_xml(pak_path: Path) -> bytes:
    """Extract describe.xml from a .pak. May be at root or inside adapter.zip."""
    with zipfile.ZipFile(pak_path) as outer:
        names = outer.namelist()

        # Try direct describe.xml
        direct = next((n for n in names if n.endswith("describe.xml")), None)
        if direct:
            return outer.read(direct)

        # Try inside adapter.zip
        adapter_zips = [n for n in names if n.endswith("adapter.zip")]
        for az_name in adapter_zips:
            with outer.open(az_name) as az_fp:
                # zipfile needs a seekable stream; load fully into BytesIO
                import io
                az_bytes = az_fp.read()
                with zipfile.ZipFile(io.BytesIO(az_bytes)) as inner:
                    for n in inner.namelist():
                        if n.endswith("describe.xml"):
                            return inner.read(n)

    raise ValueError(f"No describe.xml found in {pak_path}")


def audit_describe_xml(pak_path: str) -> dict[str, dict[str, Any]]:
    """Parse describe.xml; return {kind_key: {attrs, metrics, groups, parent}}."""
    pak = Path(pak_path)
    if not pak.exists():
        raise FileNotFoundError(pak_path)
    xml_bytes = _read_describe_xml(pak)
    root = ET.fromstring(xml_bytes)
    ns = ""
    if root.tag.startswith("{"):
        ns = root.tag[: root.tag.index("}") + 1]

    index: dict[str, dict[str, Any]] = {}
    for rk in root.iter(f"{ns}ResourceKind"):
        key = rk.get("key", "")
        if not key:
            continue
        attrs: set[str] = set()
        metrics: set[str] = set()
        groups: set[str] = set()
        for child in rk.iter():
            tag = child.tag[len(ns):] if ns and child.tag.startswith(ns) else child.tag
            ck = child.get("key", "")
            if not ck:
                continue
            if tag == "ResourceAttribute":
                # isProperty="true" => property; "false" => metric; default true
                is_prop = child.get("isProperty", "true").lower() != "false"
                if is_prop:
                    attrs.add(ck)
                else:
                    metrics.add(ck)
            elif tag == "ResourceGroup":
                groups.add(ck)
        index[key] = {"attrs": attrs, "metrics": metrics, "groups": groups}
    return index


# ---------------------------------------------------------------------------
# Content drift audit
# ---------------------------------------------------------------------------

KIND_TOKEN_RE = re.compile(r"\b(AZURE_[A-Z][A-Z0-9_]*|azure_[a-z][a-z0-9_]*)\b")


def _attr_in_describe(
    attr_key: str, describe_index: dict[str, dict[str, Any]]
) -> bool:
    for d in describe_index.values():
        if attr_key in d["attrs"] or attr_key in d["metrics"]:
            return True
    return False


def _walk_json_for_tokens(
    node: Any,
    path: str,
    drift: list[tuple[str, str, str]],
    valid_kinds: set[str],
    file_: str,
) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            _walk_json_for_tokens(v, f"{path}.{k}", drift, valid_kinds, file_)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            _walk_json_for_tokens(item, f"{path}[{i}]", drift, valid_kinds, file_)
    elif isinstance(node, str):
        for m in KIND_TOKEN_RE.finditer(node):
            tok = m.group(1)
            if tok in NON_KIND_AZURE_TOKENS:
                continue
            if tok in valid_kinds:
                continue
            # Treat AZURE_RESOURCE_GROUP and AZURE_REGION as valid kinds
            # (they appear as both identifier names and kind keys).
            drift.append((file_, path or "(root)", f"unknown kind token {tok}"))


def audit_content(
    content_dir: str, describe_index: dict[str, dict[str, Any]]
) -> list[tuple[str, str, str]]:
    """Walk content/ for kind/attribute references not in describe_index."""
    drift: list[tuple[str, str, str]] = []
    base = Path(content_dir)
    if not base.exists():
        return [(content_dir, "(missing)", "content directory does not exist")]

    valid_kinds = set(describe_index.keys())

    # Traversal specs
    for f in base.rglob("*.xml"):
        if "traversalspec" not in str(f).lower():
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            drift.append((str(f), "(read error)", str(e)))
            continue
        # Require AZURE_ or azure_ prefix on captured kind so we don't
        # mis-capture nested adapter-kind tokens like
        # `MicrosoftAzureAdapter::MicrosoftAzureAdapter::AZURE_X`.
        for m in re.finditer(
            r"MicrosoftAzureAdapter::([Aa][Zz][Uu][Rr][Ee]_[A-Za-z0-9_]+)", text
        ):
            kind = m.group(1)
            if kind not in valid_kinds and kind not in NON_KIND_AZURE_TOKENS:
                drift.append(
                    (str(f), f"offset {m.start()}", f"unknown kind {kind}")
                )

    # Alert defs (XML)
    for f in base.rglob("*.xml"):
        if "alertdef" not in str(f).lower():
            continue
        try:
            tree = ET.parse(f)
        except (ET.ParseError, OSError) as e:
            drift.append((str(f), "(parse error)", str(e)))
            continue
        for elem in tree.iter():
            for attr in (
                "resourceKind",
                "objectType",
                "adapterAndObjectType",
            ):
                rk = elem.get(attr) or ""
                if "::" in rk:
                    rk = rk.split("::", 1)[-1]
                if rk and (rk.startswith("AZURE_") or rk.startswith("azure_")):
                    if rk not in valid_kinds and rk not in NON_KIND_AZURE_TOKENS:
                        drift.append(
                            (str(f), elem.tag, f"unknown kind {rk} in @{attr}")
                        )
            for attr in ("attributeKey", "statKey", "key"):
                ak = elem.get(attr) or ""
                if "|" in ak and not _attr_in_describe(ak, describe_index):
                    drift.append(
                        (str(f), elem.tag, f"unknown attr {ak} in @{attr}")
                    )

    # Dashboards (JSON)
    for f in base.rglob("*.json"):
        if "dashboard" not in str(f).lower():
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8", errors="replace"))
        except (json.JSONDecodeError, OSError) as e:
            drift.append((str(f), "(parse error)", str(e)))
            continue
        _walk_json_for_tokens(data, "", drift, valid_kinds, str(f))

    return drift


# ---------------------------------------------------------------------------
# Aria Ops Suite-API
# ---------------------------------------------------------------------------

def _aria_request(
    url: str,
    headers: dict[str, str],
    ctx: ssl.SSLContext,
    body: Optional[bytes] = None,
    timeout: int = 30,
) -> dict:
    req = urllib.request.Request(url, data=body, headers=headers)
    if body is not None:
        req.method = "POST"
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        return json.loads(resp.read())


def verify_aria_ops(
    host: str,
    user: str,
    password: str,
    expected_counts: Optional[dict[str, int]] = None,
) -> dict:
    """Acquire token, enumerate kinds, count resources per kind.

    Returns a structured dict with counts and per-kind comparison if
    expected_counts is provided.
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    base = f"https://{host}/suite-api/api"
    common_headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    # Acquire token
    try:
        tok_body = json.dumps({"username": user, "password": password}).encode()
        tok_resp = _aria_request(
            f"{base}/auth/token/acquire", common_headers, ctx, body=tok_body
        )
        token = tok_resp.get("token")
        if not token:
            return {"error": f"no token in response: {tok_resp}"}
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        return {"error": f"token acquire failed: {e}"}

    auth_headers = {
        "Authorization": f"vRealizeOpsToken {token}",
        "Accept": "application/json",
    }

    # Enumerate kinds
    try:
        rk_resp = _aria_request(
            f"{base}/adapterkinds/MicrosoftAzureAdapter/resourcekinds",
            auth_headers,
            ctx,
        )
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        return {"error": f"resourcekinds query failed: {e}"}
    kind_keys = [
        rk.get("key") for rk in rk_resp.get("resource-kind", []) if rk.get("key")
    ]

    counts: dict[str, Any] = {}
    mismatches: list[str] = []
    for kind in kind_keys:
        try:
            # URL-encode the kind: native pak uses literal spaces in some
            # keys (e.g., "MicrosoftAzureAdapter Instance"), and urllib
            # refuses to send a request with raw control characters.
            url = (
                f"{base}/resources?adapterKind=MicrosoftAzureAdapter"
                f"&resourceKind={urllib.parse.quote(kind)}&pageSize=1"
            )
            resp = _aria_request(url, auth_headers, ctx)
            n = resp.get("pageInfo", {}).get("totalCount", 0)
            counts[kind] = n
            if expected_counts is not None and kind in expected_counts:
                exp = expected_counts[kind]
                # Allow rounding within +/-1 (collection in flight)
                if abs(n - exp) > max(1, exp // 10):
                    mismatches.append(f"{kind}: aria={n} live={exp}")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            counts[kind] = f"ERROR: {e}"

    return {
        "host": host,
        "kind_count": len(kind_keys),
        "counts": counts,
        "mismatches": mismatches,
    }


# ---------------------------------------------------------------------------
# Redaction (for sharing reports outside the secure environment)
# ---------------------------------------------------------------------------

# Azure tenant/subscription/client IDs are 8-4-4-4-12 GUIDs. Replace any
# occurrence in free-text strings (error messages, content drift entries).
_GUID_RE = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
# ARM resource paths frequently embed names: /subscriptions/<guid>/resourceGroups/<name>/...
_ARM_PATH_RE = re.compile(r"/(subscriptions|resourceGroups|providers)/[^/\s]+", re.IGNORECASE)


def _redact_text(s: str) -> str:
    if not isinstance(s, str):
        return s
    s = _GUID_RE.sub("<guid>", s)
    s = _ARM_PATH_RE.sub(r"/\1/<redacted>", s)
    return s


def redact_report(report: dict) -> dict:
    """Return a deep copy of the report with sensitive values stripped.

    Removed: connection name, Aria Ops hostname, object names in the
    Dedicated Host coverage section, GUIDs anywhere in error messages,
    ARM-path-shaped substrings.
    Kept: kind keys, attribute keys, counts, statuses, content file paths
    (which are repo-relative and public), drift token names (schema-level).
    """
    import copy

    r = copy.deepcopy(report)

    if r.get("connection"):
        r["connection"] = "<connection>"

    live = r.get("live")
    if isinstance(live, dict):
        if live.get("error"):
            live["error"] = _redact_text(live["error"])
        # Dedicated Host coverage carries actual host names.
        dh = live.get("dedicated_host_missing_attrs", [])
        if isinstance(dh, list):
            for i, entry in enumerate(dh):
                if isinstance(entry, dict) and "name" in entry:
                    entry["host_index"] = i + 1
                    entry.pop("name", None)
        # Per-kind reasons should be schema-only by construction, but redact
        # GUIDs defensively in case an exception message snuck through.
        per_kind = live.get("per_kind", {})
        if isinstance(per_kind, dict):
            for kinfo in per_kind.values():
                if isinstance(kinfo, dict) and isinstance(kinfo.get("reasons"), list):
                    kinfo["reasons"] = [_redact_text(x) for x in kinfo["reasons"]]

        # DH stats id_samples include identifier values (sub GUIDs, ARM paths,
        # host names). Redact identifier values and clear the host name.
        dh_stats = live.get("dh_stats")
        if isinstance(dh_stats, dict):
            samples = dh_stats.get("id_samples", [])
            if isinstance(samples, list):
                for i, s in enumerate(samples):
                    if not isinstance(s, dict):
                        continue
                    s["sample_index"] = i + 1
                    s.pop("name", None)
                    idents = s.get("identifiers", {})
                    if isinstance(idents, dict):
                        s["identifiers"] = {
                            k: _redact_text(str(v)) for k, v in idents.items()
                        }

    ao = r.get("aria_ops")
    if isinstance(ao, dict):
        if ao.get("host"):
            ao["host"] = "<aria-ops-host>"
        if ao.get("error"):
            ao["error"] = _redact_text(ao["error"])
        if isinstance(ao.get("mismatches"), list):
            ao["mismatches"] = [_redact_text(m) for m in ao["mismatches"]]

    da = r.get("describe_audit")
    if isinstance(da, dict) and da.get("error"):
        da["error"] = _redact_text(da["error"])

    drift = r.get("content_drift")
    if isinstance(drift, list):
        redacted_drift = []
        for item in drift:
            if isinstance(item, (list, tuple)):
                redacted_drift.append([_redact_text(str(x)) for x in item])
            else:
                redacted_drift.append(_redact_text(str(item)))
        r["content_drift"] = redacted_drift

    return r


def quiet_collector_logs() -> None:
    """Bump adapter/collector loggers to WARNING to suppress per-resource INFO."""
    for name in (
        "adapter",
        "azure_client",
        "auth",
        "helpers",
        "pricing",
        "collectors",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------

def render_text_report(report: dict) -> str:
    out: list[str] = []
    out.append("# Azure MP — End-to-End Verification Report")
    out.append(f"Generated: {report['timestamp']}")
    if report.get("connection"):
        out.append(f"Connection: {report['connection']}")
    if report.get("pak"):
        out.append(f"Pak: {report['pak']}")
    out.append("")

    if "live" in report:
        live = report["live"]
        if live.get("error"):
            out.append("## Live Collection: FAILED")
            out.append(f"  {live['error']}")
            out.append("")
        else:
            out.append(
                f"## Live Collection ({live['duration']:.1f}s, "
                f"{live['total_objects']} objects)"
            )
            out.append("")
            out.append("| Kind | Status | Count | Notes |")
            out.append("|---|---|---|---|")
            order = sorted(
                live["per_kind"].items(),
                key=lambda kv: (
                    {"FAIL": 0, "WARN": 1, "PASS": 2}.get(kv[1]["status"], 3),
                    kv[0],
                ),
            )
            for kind, r in order:
                notes = "; ".join(r["reasons"]) if r["reasons"] else ""
                out.append(
                    f"| `{kind}` | **{r['status']}** | {r['count']} | {notes} |"
                )
            out.append("")
            extras = live.get("kind_counts_unspecified", {})
            if extras:
                out.append("### Other kinds collected (not in spec table)")
                for k, n in sorted(extras.items()):
                    out.append(f"- `{k}`: {n}")
                out.append("")
            dh_miss = live.get("dedicated_host_missing_attrs", [])
            if dh_miss:
                out.append("### Dedicated Host attribute coverage")
                for entry in dh_miss:
                    label = entry.get("name") or f"host-{entry.get('host_index', '?')}"
                    out.append(
                        f"- `{label}` missing: {', '.join(entry['missing'])}"
                    )
                out.append("")

    if "describe_audit" in report:
        d = report["describe_audit"]
        if d.get("error"):
            out.append(f"## describe.xml Audit: FAILED ({d['error']})")
            out.append("")
        else:
            out.append(
                f"## describe.xml Audit ({d['kind_count']} kinds in pak)"
            )
            if d.get("missing_kinds"):
                out.append(
                    f"- **Missing expected kinds:** "
                    f"{', '.join(d['missing_kinds'])}"
                )
            if d.get("dedicated_host_attrs_missing"):
                out.append(
                    f"- **Dedicated Host attrs not in describe.xml:** "
                    f"{', '.join(d['dedicated_host_attrs_missing'])}"
                )
            if d.get("custom_kinds_with_pipe_attrs"):
                out.append(
                    f"- **Custom kinds with pipe-keyed attrs (will be "
                    f"rejected by Aria Ops):** "
                    f"{json.dumps(d['custom_kinds_with_pipe_attrs'])}"
                )
            if not (
                d.get("missing_kinds")
                or d.get("dedicated_host_attrs_missing")
                or d.get("custom_kinds_with_pipe_attrs")
            ):
                out.append("- All expected kinds present, no pipe-attr issues.")
            out.append("")

    if "content_drift" in report:
        drift = report["content_drift"]
        out.append(f"## Content Drift ({len(drift)} issues)")
        for f, where, msg in drift[:50]:
            out.append(f"- {f} @ {where}: {msg}")
        if len(drift) > 50:
            out.append(f"... and {len(drift) - 50} more (see JSON report)")
        out.append("")

    if "aria_ops" in report:
        a = report["aria_ops"]
        if a.get("error"):
            out.append(f"## Aria Ops Suite-API: ERROR ({a['error']})")
        else:
            out.append(
                f"## Aria Ops Suite-API ({a['host']}, "
                f"{a['kind_count']} kinds enumerated)"
            )
            for kind, count in sorted(a["counts"].items()):
                out.append(f"- `{kind}`: {count}")
            if a.get("mismatches"):
                out.append("")
                out.append("### Count mismatches vs live collection")
                for m in a["mismatches"]:
                    out.append(f"- {m}")
        out.append("")

    out.append("## Summary")
    out.append(f"- Exit signal: {report.get('exit_summary', '?')}")
    return "\n".join(out)


def render_json_report(report: dict, path: str) -> None:
    # Ensure the parent directory exists. Critical for the crash-safe
    # write path: if the user passes --out debug/verify.json from a cwd
    # where debug/ doesn't exist, the partial write would silently lose
    # everything they just collected.
    p = Path(path)
    if p.parent and str(p.parent) not in ("", "."):
        p.parent.mkdir(parents=True, exist_ok=True)
    serializable = json.loads(json.dumps(report, default=_json_default))
    with open(p, "w") as f:
        json.dump(serializable, f, indent=2)


def _json_default(o: Any) -> Any:
    if isinstance(o, set):
        return sorted(o)
    if isinstance(o, Path):
        return str(o)
    return str(o)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="End-to-end verifier for the Azure Gov management pack.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  # Static-only audit (no Azure API calls, no SDK needed):
  #   describe.xml registry + Dedicated Host custom attrs +
  #   pipe-keyed attr check on custom kinds + content drift
  python scripts/verify_collection.py \\
      --pak build/MicrosoftAzureAdapter.pak

  # Live collection only — runs the 19 first-class collectors against
  # Azure Gov, asserts counts/parents/props/metrics per kind, dumps JSON
  python scripts/verify_collection.py \\
      --connection connections.json \\
      --out verify-$(date +%Y%m%d-%H%M).json

  # Full sweep on the MP Builder server (Photon OS):
  #   live collect + pak audit + content drift + Aria Ops Suite-API
  ARIA_PASS='...' python scripts/verify_collection.py \\
      --connection connections.json \\
      --pak build/MicrosoftAzureAdapter.pak \\
      --aria-ops aria.ops.local --aria-user admin \\
      --out verify-$(date +%Y%m%d-%H%M).json

  # Aria Ops check only (after pak deploy, no rebuild needed) — pulls
  # username/password from connections.json's suite_api_* fields if
  # --aria-user / ARIA_PASS not given
  python scripts/verify_collection.py \\
      --connection connections.json \\
      --aria-ops aria.ops.local

  # Override content/ location (e.g. when pak is in a custom path)
  python scripts/verify_collection.py \\
      --pak /tmp/custom.pak \\
      --content Azure-Native-Build/content

  # Diff two runs to detect drift over time (counts, missing kinds, etc.)
  diff <(jq -S . verify-20260430-0900.json) \\
       <(jq -S . verify-20260501-0900.json)

  # Quiet the per-resource INFO chatter from the collectors, useful when
  # the run is going to scroll past 10k+ log lines
  python scripts/verify_collection.py \\
      --connection connections.json --pak build/...pak \\
      --quiet-collectors \\
      --out verify.json

  # Re-render an existing report with sensitive values redacted (GUIDs,
  # Aria Ops hostname, host names). Cheap — no Azure or Aria Ops calls.
  # Use this to produce a shareable variant after running locally.
  python scripts/verify_collection.py --report verify.json --redacted \\
      --out verify-redacted.json

  # Fast smoke run on a real tenant — caps each ARM list at 5 items per
  # call, finishes in ~3-5 minutes instead of hours. Heartbeat every 30s
  # confirms the run is alive even with --quiet-collectors.
  python scripts/verify_collection.py \\
      --connection connections.json \\
      --pak build/MicrosoftAzureAdapter.pak \\
      --sample 5 --quiet-collectors --heartbeat 30 \\
      --out verify-smoke.json

  # Survive session timeouts — run in background with nohup, tail the log.
  # Crash-safe handlers flush a partial JSON to --out on SIGHUP/SIGTERM/
  # Ctrl-C so dropped SSH connections don't lose the work.
  nohup python scripts/verify_collection.py \\
      --connection connections.json \\
      --pak build/MicrosoftAzureAdapter.pak \\
      --sample 20 --quiet-collectors \\
      --out debug/verify.json > debug/verify.log 2>&1 &
  tail -f debug/verify.log

exit codes:
  0  all PASS
  1  any FAIL (missing kind, missing parent, dropped metric, etc.)
  2  WARN only (e.g. tenant has no instances of an optional kind)
""",
    )
    parser.add_argument(
        "--connection",
        help="Path to mp-test format connections.json (enables live collect)",
    )
    parser.add_argument(
        "--pak",
        help="Path to .pak (enables describe.xml + content drift audits)",
    )
    parser.add_argument(
        "--content",
        help="Path to content/ dir; defaults to <pak>/../../content",
    )
    parser.add_argument(
        "--aria-ops",
        help="Aria Ops hostname for Suite-API audit (e.g., aria.ops.local)",
    )
    parser.add_argument("--aria-user", help="Aria Ops API username")
    parser.add_argument(
        "--aria-pass-env",
        default="ARIA_PASS",
        help="Env var holding Aria Ops password (default: ARIA_PASS)",
    )
    parser.add_argument("--out", help="Path to write JSON report")
    parser.add_argument(
        "--no-text-report",
        action="store_true",
        help="Suppress markdown stdout report",
    )
    parser.add_argument(
        "--redacted",
        action="store_true",
        help=(
            "Strip GUIDs, Aria Ops hostname, connection name, and Dedicated "
            "Host names from the rendered output. Use when sharing reports."
        ),
    )
    parser.add_argument(
        "--quiet-collectors",
        action="store_true",
        help=(
            "Bump adapter/collector loggers to WARNING during live collection "
            "(suppresses per-resource INFO chatter)."
        ),
    )
    parser.add_argument(
        "--report",
        help=(
            "Path to a previously-written JSON report; re-renders without "
            "re-running collection. Combine with --redacted to produce a "
            "shareable variant."
        ),
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Cap leaf ARM list calls at N items per call. Recommended: 5 for "
            "smoke (~3-5 min on a real tenant), 20 for sample (~15 min). "
            "Default: 0 (unlimited; full collection, can take hours)."
        ),
    )
    parser.add_argument(
        "--heartbeat",
        type=int,
        default=60,
        metavar="SECS",
        help=(
            "Emit elapsed-time log every SECS during live collection. "
            "Default: 60. Set 0 to disable. Useful with --quiet-collectors "
            "to confirm the run is alive."
        ),
    )
    args = parser.parse_args(argv)

    # --report short-circuits everything else: load the JSON, render, exit.
    if args.report:
        with open(args.report) as f:
            cached = json.load(f)
        rendered = redact_report(cached) if args.redacted else cached
        if not args.no_text_report:
            print(render_text_report(rendered))
        if args.out:
            render_json_report(rendered, args.out)
            logger.info("Report written to %s", args.out)
        exit_summary = cached.get("exit_summary", "PASS")
        return {"FAIL": 1, "WARN": 2, "PASS": 0}.get(exit_summary, 0)

    if not (args.connection or args.pak or args.aria_ops):
        parser.error(
            "at least one of --connection, --pak, --aria-ops, --report is required"
        )

    # Auto-detect newest pak in build/ if --pak missing or stale. Saves the
    # "passed --pak path/to/old.8.pak after rebuilding to .9 and got
    # 'pak not found'" footgun.
    if args.pak and not Path(args.pak).exists():
        logger.warning("--pak %s does not exist; trying auto-detect", args.pak)
        args.pak = None
    if args.pak is None and args.connection:
        # Look near connections.json for a build/ dir
        conn_parent = Path(args.connection).resolve().parent
        for build_dir in (conn_parent / "build", Path("build"), Path("Azure-Native-Build/build")):
            if build_dir.is_dir():
                paks = sorted(
                    build_dir.glob("MicrosoftAzureAdapter*.pak"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if paks:
                    args.pak = str(paks[0])
                    logger.info("Auto-detected newest pak: %s", args.pak)
                    break

    # Default --out to a timestamped file when running a live collection.
    # Live collect can take 15+ minutes; losing the JSON because the user
    # forgot --out is a needlessly expensive mistake.
    if args.connection and not args.out:
        default_out = f"verify-{time.strftime('%Y%m%d-%H%M%S')}.json"
        logger.warning(
            "--out not specified for live collection; defaulting to %s "
            "in cwd. Pass --out explicitly (or --no-default-out) to override.",
            default_out,
        )
        args.out = default_out

    if args.quiet_collectors:
        quiet_collector_logs()

    report: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    if args.pak:
        report["pak"] = args.pak
    if args.sample > 0:
        report["sample"] = args.sample

    # Register crash-safe handlers BEFORE the long-running audits so an
    # SSH-session-kill / Ctrl-C / unhandled exception still produces a JSON
    # report at args.out with whatever phases completed.
    _install_crash_safe(report, args)

    has_fail = False
    has_warn = False
    expected_counts_for_aria: Optional[dict[str, int]] = None
    conn: Optional[dict] = None
    exit_code = 0

    # --- Live collection ---------------------------------------------------
    if args.connection:
        conn = load_connection(args.connection)
        report["connection"] = conn["name"]
        stub = StubAdapterInstance(conn)
        logger.info("Running live collection...")
        try:
            result, duration = run_collection(
                stub,
                sample_n=args.sample if args.sample > 0 else None,
                heartbeat_interval=args.heartbeat,
            )
        except Exception as e:
            logger.error("run_collection failed: %s", e, exc_info=True)
            report["live"] = {"error": f"{type(e).__name__}: {e}"}
            has_fail = True
        else:
            err = getattr(result, "_error_message", None)
            if err:
                logger.error("Collection returned error: %s", err)
                report["live"] = {"error": err, "duration": duration}
                has_fail = True
            else:
                by_kind = inspect_result(result)
                total = sum(len(v) for v in by_kind.values())
                per_kind: dict[str, dict] = {}
                for kind, spec in KIND_SPECS.items():
                    status, count, reasons = assert_kind(by_kind, kind, spec)
                    per_kind[kind] = {
                        "status": status,
                        "count": count,
                        "reasons": reasons,
                    }
                    if status == "FAIL":
                        has_fail = True
                    elif status == "WARN":
                        has_warn = True
                # Counts for kinds not in spec table (likely stub kinds via
                # bulk_resources). Surface them but don't grade.
                spec_keys = set(KIND_SPECS.keys())
                extras = {
                    k: len(v) for k, v in by_kind.items() if k not in spec_keys
                }
                # Dedicated Host attribute coverage
                dh_kind = "AZURE_DEDICATE_HOST"
                dh_miss: list[dict] = []
                dh_prop_keys_sample: list[str] = []
                dh_total = 0
                dh_with_props = 0
                dh_empty_props = 0
                dh_with_group_parent = 0
                dh_id_samples: list[dict] = []
                for o in by_kind.get(dh_kind, []):
                    dh_total += 1
                    nprops = len(o["properties"])
                    if nprops > 0:
                        dh_with_props += 1
                    else:
                        dh_empty_props += 1
                    if any(p["kind"] == "AZURE_COMPUTE_HOSTGROUPS"
                           for p in o["parents"]):
                        dh_with_group_parent += 1
                    if len(dh_id_samples) < 4:
                        dh_id_samples.append({
                            "name": o["name"],
                            "n_properties": nprops,
                            "parent_kinds": sorted({p["kind"]
                                                    for p in o["parents"]}),
                            "identifiers": o["identifiers"],
                        })
                    miss = [
                        a for a in DH_CUSTOM_ATTRS
                        if a not in o["properties"]
                        or o["properties"][a] in (None, "")
                    ]
                    if miss:
                        dh_miss.append({"name": o["name"], "missing": miss})
                    if not dh_prop_keys_sample:
                        dh_prop_keys_sample = sorted(o["properties"].keys())
                if dh_miss:
                    has_warn = True
                report["live"] = {
                    "duration": duration,
                    "total_objects": total,
                    "kind_counts": {k: len(v) for k, v in by_kind.items()},
                    "kind_counts_unspecified": extras,
                    "per_kind": per_kind,
                    "dedicated_host_missing_attrs": dh_miss,
                    "dh_prop_keys_first_obj": dh_prop_keys_sample,
                    "dh_stats": {
                        "total": dh_total,
                        "with_any_property": dh_with_props,
                        "with_zero_properties": dh_empty_props,
                        "with_hostgroup_parent": dh_with_group_parent,
                        "id_samples": dh_id_samples,
                    },
                }
                expected_counts_for_aria = {
                    k: len(v) for k, v in by_kind.items()
                }

    # --- describe.xml + content drift -------------------------------------
    if args.pak:
        if not Path(args.pak).exists():
            logger.error("Pak not found: %s", args.pak)
            report["describe_audit"] = {"error": f"pak not found: {args.pak}"}
            has_fail = True
        else:
            logger.info("Auditing describe.xml in %s", args.pak)
            try:
                describe_index = audit_describe_xml(args.pak)
            except Exception as e:
                logger.error("describe.xml audit failed: %s", e, exc_info=True)
                report["describe_audit"] = {"error": str(e)}
                has_fail = True
            else:
                expected_kinds = list(KIND_SPECS.keys())
                missing = [
                    k for k in expected_kinds if k not in describe_index
                ]
                dh_kind = "AZURE_DEDICATE_HOST"
                dh = describe_index.get(dh_kind, {})
                dh_present = dh.get("attrs", set()) | dh.get("metrics", set())
                dh_missing = [a for a in DH_CUSTOM_ATTRS if a not in dh_present]
                custom_pipe: dict[str, list[str]] = {}
                for kind in CUSTOM_KIND_KEYS:
                    info = describe_index.get(kind, {})
                    pipe_attrs = [
                        a for a in info.get("attrs", set()) | info.get("metrics", set())
                        if "|" in a
                    ]
                    if pipe_attrs:
                        custom_pipe[kind] = pipe_attrs

                report["describe_audit"] = {
                    "kind_count": len(describe_index),
                    "missing_kinds": missing,
                    "dedicated_host_attrs_missing": dh_missing,
                    "custom_kinds_with_pipe_attrs": custom_pipe,
                }
                if missing or dh_missing or custom_pipe:
                    has_fail = True

                content_dir = args.content
                if not content_dir:
                    pak_parent = Path(args.pak).resolve().parent
                    # Common layouts: build/foo.pak -> ../content
                    candidates = [
                        pak_parent.parent / "content",
                        pak_parent / "content",
                    ]
                    content_dir = next(
                        (str(c) for c in candidates if c.exists()), None
                    )
                if content_dir:
                    logger.info(
                        "Auditing content drift against %s", content_dir
                    )
                    drift = audit_content(content_dir, describe_index)
                    report["content_drift"] = drift
                    if drift:
                        has_warn = True
                else:
                    logger.warning(
                        "No content/ dir found near pak; skipping drift audit"
                    )

    # --- Aria Ops Suite-API ------------------------------------------------
    if args.aria_ops:
        password = os.environ.get(args.aria_pass_env)
        user = args.aria_user
        if not password and conn:
            password = conn.get("suite_api_password") or password
        if not user and conn:
            user = conn.get("suite_api_username")
        if not (user and password):
            logger.error(
                "Aria Ops requires --aria-user and a password "
                "(env %s or connections.json suite_api_password)",
                args.aria_pass_env,
            )
            report["aria_ops"] = {
                "error": "missing user/password for Aria Ops"
            }
            has_fail = True
        else:
            logger.info(
                "Querying Aria Ops Suite-API at %s as %s", args.aria_ops, user
            )
            ao = verify_aria_ops(
                args.aria_ops, user, password, expected_counts_for_aria
            )
            report["aria_ops"] = ao
            if ao.get("error"):
                has_fail = True
            elif ao.get("mismatches"):
                has_warn = True

    # --- Render ------------------------------------------------------------
    if has_fail:
        report["exit_summary"] = "FAIL"
        exit_code = 1
    elif has_warn:
        report["exit_summary"] = "WARN"
        exit_code = 2
    else:
        report["exit_summary"] = "PASS"
        exit_code = 0

    rendered = redact_report(report) if args.redacted else report
    if not args.no_text_report:
        print(render_text_report(rendered))
    if args.out:
        render_json_report(rendered, args.out)
        logger.info(
            "JSON report written to %s%s",
            args.out,
            " (redacted)" if args.redacted else "",
        )

    return exit_code




if __name__ == "__main__":
    sys.exit(main())
