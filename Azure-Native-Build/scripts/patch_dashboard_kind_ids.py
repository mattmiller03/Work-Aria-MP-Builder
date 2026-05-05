#!/usr/bin/env python3
"""Rewrite resourceKind:id:N references in dashboard.json.

The dashboards shipped by the native MicrosoftAzureAdapter pak reference
resource kinds by *numeric ID* (e.g. resourceKind:id:3_::_), where the
number is the position of the ResourceKind block inside that pak's
describe.xml. Those positions are not portable across paks: when our
adapter.py defines kinds in a different order, every numeric reference
in the imported dashboard JSON points to the wrong kind.

This script runs as a build step. It reads our SDK-generated describe.xml,
builds a kindName -> our_id map, and rewrites dashboard.json so each
"resourceKind:id:N" reference uses *our* pak's id for the same logical
kind name (e.g. "Azure Virtual Machine"). Dashboard tiles for Regions,
Resource Groups, Subscriptions, etc. then bind to the correct objects
without manual UI fixes.

Usage:
    python patch_dashboard_kind_ids.py \
        --describe path/to/describe.xml \
        --dashboard path/to/dashboard.json \
        [--out path/to/dashboard.patched.json]

If --out is omitted, dashboard.json is overwritten in place.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger("patch_dashboard_kind_ids")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


# Map from the native dashboard's "resourceKindName" labels to the
# ResourceKind keys we use in describe.xml. The dashboards reference
# kinds by display name in the resourceKindName field; describe.xml
# stores them by `key` attribute. The map covers every name the
# native dashboards reference (extracted from
# "resourceKindId":"resourceKind:id:N_::_","resourceKindName":"..."
# pairs in the bundled dashboard.json).
NAME_TO_KEY = {
    "Microsoft Azure Adapter Instance": "MicrosoftAzureAdapter Instance",
    "Azure Application Gateway": "AZURE_APPLICATION_GATEWAY",
    "Azure Resource Group": "AZURE_RESOURCE_GROUP",
    "Azure Virtual Machine": "AZURE_VIRTUAL_MACHINE",
    "Azure SQL Database": "AZURE_SQL_DATABASE",
    "Azure Load Balancer": "AZURE_LB",
    "Azure Kubernetes Cluster": "AZURE_KUBERNATE_CLUSTER",
    "Azure Virtual Network": "AZURE_VIRTUAL_NETWORK",
    "Azure Virtual Network Gateway": "AZURE_VIRTUAL_NETWORK_GATEWAY",
    "Azure Storage Account": "AZURE_STORAGE_ACCOUNT",
    "Azure Region": "AZURE_REGION",
    "Azure Region Per Subscription": "AZURE_REGION_PER_SUB",
    "Azure World": "AZURE_WORLD",
}


# Native id -> name mapping, extracted from the bundled dashboard.json's
# resourceKindId+resourceKindName pairs. Used as the source side of the
# rewrite when only an id is present in the JSON (no nearby name to
# disambiguate). Keep this list in sync with NAME_TO_KEY.
NATIVE_ID_TO_NAME = {
    0:  "Microsoft Azure Adapter Instance",
    1:  "Azure Application Gateway",
    2:  "Azure Resource Group",
    3:  "Azure Virtual Machine",
    5:  "Azure SQL Database",
    8:  "Azure Load Balancer",
    11: "Azure Kubernetes Cluster",
    12: "Azure Virtual Network",
    13: "Azure Virtual Network Gateway",
    16: "Azure Storage Account",
    17: "Azure Region",
    18: "Azure Region Per Subscription",
    21: "Azure World",
}


def build_our_key_to_id(describe_xml_path: Path) -> dict[str, int]:
    """Parse our describe.xml and return ResourceKind key -> id index.

    The Adapter Instance is implicit at id:0; user-defined ResourceKinds
    follow in the order they appear inside <AdapterKind>. The id we
    return matches the numeric reference Aria Ops dashboards use
    (resourceKind:id:N).
    """
    tree = ET.parse(describe_xml_path)
    root = tree.getroot()

    # describe.xml uses a default namespace -- strip it for simpler
    # tag comparisons.
    def _localname(tag: str) -> str:
        return tag.split("}", 1)[1] if "}" in tag else tag

    adapter_kinds = [
        e for e in root.iter() if _localname(e.tag) == "AdapterKind"
    ]
    if not adapter_kinds:
        raise RuntimeError(
            "describe.xml has no <AdapterKind> -- is this the right file?"
        )

    key_to_id: dict[str, int] = {}
    # Aria Ops always reserves id 0 for the Adapter Instance kind whose
    # key is "<AdapterKind> Instance". Encode that explicitly so the
    # name->key map can target it.
    adapter_key = adapter_kinds[0].get("key", "")
    if adapter_key:
        key_to_id[f"{adapter_key} Instance"] = 0

    next_id = 1
    for ak in adapter_kinds:
        for rk in ak.iter():
            if _localname(rk.tag) != "ResourceKind":
                continue
            key = rk.get("key", "")
            if not key:
                continue
            # Skip the Adapter Instance ResourceKind we already inserted
            if key == f"{adapter_key} Instance":
                continue
            key_to_id.setdefault(key, next_id)
            next_id += 1

    return key_to_id


def build_native_id_to_our_id(
    our_key_to_id: dict[str, int],
) -> dict[int, int]:
    """Compose native_id -> kind_name -> kind_key -> our_id.

    Returns a dict that maps each native ID we know about to our pak's
    ID for the same logical kind. Native IDs whose target kind is
    missing from our describe.xml are skipped with a warning.
    """
    mapping: dict[int, int] = {}
    for native_id, name in NATIVE_ID_TO_NAME.items():
        key = NAME_TO_KEY.get(name)
        if not key:
            logger.warning(
                "No NAME_TO_KEY entry for native kind %r (id %d) -- skipping",
                name, native_id,
            )
            continue
        our_id = our_key_to_id.get(key)
        if our_id is None:
            logger.warning(
                "Kind key %r not found in describe.xml (native %r, id %d) -- skipping",
                key, name, native_id,
            )
            continue
        mapping[native_id] = our_id
        logger.info(
            "  %-40s native id:%-3d -> ours id:%d", name, native_id, our_id,
        )
    return mapping


# Match every "resourceKind:id:N_::_" reference. The trailing _::_ marker
# is part of Aria Ops's encoded ID and must be preserved in the
# replacement.
_REF_RE = re.compile(r"resourceKind:id:(\d+)_::_")


def patch_dashboard_text(text: str, native_to_ours: dict[int, int]) -> tuple[str, int]:
    """Rewrite resourceKind:id:N references in dashboard JSON text.

    Returns (patched_text, replacement_count). References whose native
    id is not in `native_to_ours` are left untouched and counted as
    skipped in the log.
    """
    replaced = 0
    skipped: dict[int, int] = {}

    def repl(match: re.Match) -> str:
        nonlocal replaced
        native_id = int(match.group(1))
        our_id = native_to_ours.get(native_id)
        if our_id is None:
            skipped[native_id] = skipped.get(native_id, 0) + 1
            return match.group(0)
        replaced += 1
        return f"resourceKind:id:{our_id}_::_"

    new_text = _REF_RE.sub(repl, text)

    if skipped:
        for nid, count in sorted(skipped.items()):
            logger.warning(
                "Left %d reference(s) to native id %d unchanged "
                "(kind not in our describe.xml)",
                count, nid,
            )
    return new_text, replaced


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--describe", required=True, type=Path,
        help="Path to our SDK-generated describe.xml.",
    )
    parser.add_argument(
        "--dashboard", required=True, type=Path,
        help="Path to dashboard.json to rewrite.",
    )
    parser.add_argument(
        "--out", type=Path, default=None,
        help="Output path. Defaults to overwriting --dashboard in place.",
    )
    args = parser.parse_args(argv)

    if not args.describe.exists():
        logger.error("describe.xml not found: %s", args.describe)
        return 2
    if not args.dashboard.exists():
        logger.error("dashboard.json not found: %s", args.dashboard)
        return 2

    logger.info("Building kind-key map from %s", args.describe)
    our_key_to_id = build_our_key_to_id(args.describe)
    logger.info("Found %d ResourceKinds in describe.xml", len(our_key_to_id))

    logger.info("Resolving native id -> our id mapping")
    native_to_ours = build_native_id_to_our_id(our_key_to_id)
    if not native_to_ours:
        logger.error(
            "No native ids could be remapped. "
            "describe.xml is likely missing the kinds the dashboards reference."
        )
        return 1

    logger.info("Reading %s", args.dashboard)
    text = args.dashboard.read_text(encoding="utf-8")

    # Validate JSON parses before AND after rewrite -- catches accidental
    # text changes that break dashboard import.
    json.loads(text)

    patched, count = patch_dashboard_text(text, native_to_ours)
    json.loads(patched)

    out_path = args.out or args.dashboard
    out_path.write_text(patched, encoding="utf-8")
    logger.info(
        "Rewrote %d resourceKind:id references and wrote %s",
        count, out_path,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
