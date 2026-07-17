#!/usr/bin/env python3
"""
merge-custom-attrs.py — graft SDK-defined custom attributes into the
native-substituted describe.xml.

Fixes "Defect A" (2026-07-09): ~87K mp-test warnings of the form
  Property 'X' is not defined in describe.xml. Could not find ResourceGroup/
  ResourceAttribute ...
Root cause: the SDK emits ALL attribute definitions as flat
<ResourceAttribute> elements, encoding groups as pipes in the key
(e.g. key="summary|virtualMachineId", key="SERVICE_DESCRIPTORS|AZURE_REGION").
The native pak's describe.xml instead uses real nested <ResourceGroup>
elements. When patch-describe-xml.py substitutes a kind with the native
literal, every SDK-defined pipe-keyed attribute that native doesn't also
define is silently dropped (the flat-attr preservation pass deliberately
skipped pipe keys). Collected properties then have no declared slot and
Aria warns / hides them.

This script runs AFTER patch-describe-xml.py and BEFORE
cleanup-describe-xml.py. For every ResourceKind present in the SDK
pre-patch snapshot AND the patched file, it:

  1. Reads the SDK's flat ResourceAttribute definitions for that kind.
  2. Flat (no-pipe) keys: ensures they exist directly under the kind
     (belt-and-suspenders next to the patcher's own flat preservation;
     skips anything already present).
  3. Pipe keys "g1|g2|...|attr": walks/creates the nested ResourceGroup
     chain g1 > g2 > ... in the patched kind and adds a ResourceAttribute
     with key="attr" (copying dataType/isProperty/unit/etc. from the SDK
     element) if not already declared there.

Notes:
  - Dynamic runtime-only properties (e.g. summary|tags|<tagname> set via
    safe_property without a define_* call) are NOT in the SDK describe and
    therefore cannot be declared here; their warnings are expected and
    harmless (Aria stores undeclared properties).
  - New ResourceGroups need a nameKey; we reuse the first child attribute's
    nameKey so the UI shows *a* label rather than failing. Cosmetic only.
  - lxml rewriting of this file is proven safe: cleanup-describe-xml.py has
    rewritten it with lxml since 8.19.19-hotfix1, which installed cleanly.
  - Idempotent: re-runs skip everything already present. The cleanup pass
    afterwards de-dupes any residual overlap and --validate gates the build.

Usage:
    python3.12 scripts/merge-custom-attrs.py <patched-describe.xml> <sdk-prepatch-describe.xml>
"""

import sys
from lxml import etree

NS = "http://schemas.vmware.com/vcops/schema"


def q(tag: str) -> str:
    return f"{{{NS}}}{tag}"


def _kinds_by_key(root):
    out = {}
    for rk in root.iter(q("ResourceKind")):
        key = rk.get("key")
        if key:
            out[key] = rk
    return out


def _find_child_group(parent, group_key):
    for rg in parent.findall(q("ResourceGroup")):
        if rg.get("key") == group_key:
            return rg
    return None


def _find_child_attr(parent, attr_key):
    for ra in parent.findall(q("ResourceAttribute")):
        if ra.get("key") == attr_key:
            return ra
    return None


def _make_attr_element(sdk_attr, new_key):
    """Copy an SDK ResourceAttribute element, replacing its key."""
    el = etree.Element(q("ResourceAttribute"))
    for k, v in sdk_attr.attrib.items():
        el.set(k, v)
    el.set("key", new_key)
    return el


def merge(patched_path: str, sdk_path: str) -> None:
    parser = etree.XMLParser(remove_blank_text=False)
    patched_tree = etree.parse(patched_path, parser)
    sdk_tree = etree.parse(sdk_path, parser)

    patched_kinds = _kinds_by_key(patched_tree.getroot())
    sdk_kinds = _kinds_by_key(sdk_tree.getroot())

    kinds_touched = 0
    flat_added = 0
    grouped_added = 0
    groups_created = 0

    for kind_key, sdk_kind in sdk_kinds.items():
        target_kind = patched_kinds.get(kind_key)
        if target_kind is None:
            continue  # kind not in final pak (renamed adapter instance etc.)

        touched_this_kind = False

        # SDK attrs are all DIRECT children of the kind (flat emission).
        for sdk_attr in sdk_kind.findall(q("ResourceAttribute")):
            key = sdk_attr.get("key", "")
            if not key:
                continue

            if "|" not in key:
                # Flat custom attr — ensure present directly under the kind.
                if _find_child_attr(target_kind, key) is None:
                    target_kind.append(_make_attr_element(sdk_attr, key))
                    flat_added += 1
                    touched_this_kind = True
                continue

            # Pipe key: walk/create the nested ResourceGroup chain.
            segments = key.split("|")
            group_chain, attr_name = segments[:-1], segments[-1]
            if not attr_name:
                continue

            container = target_kind
            for gseg in group_chain:
                grp = _find_child_group(container, gseg)
                if grp is None:
                    grp = etree.SubElement(container, q("ResourceGroup"))
                    grp.set("key", gseg)
                    # nameKey is required by the schema; reuse the source
                    # attribute's nameKey so the UI has *a* label.
                    grp.set("nameKey", sdk_attr.get("nameKey", "1"))
                    grp.set("instanced", "false")
                    groups_created += 1
                    touched_this_kind = True
                container = grp

            if _find_child_attr(container, attr_name) is None:
                container.append(_make_attr_element(sdk_attr, attr_name))
                grouped_added += 1
                touched_this_kind = True

        if touched_this_kind:
            kinds_touched += 1

    patched_tree.write(patched_path, encoding="UTF-8", xml_declaration=True)

    print(
        f"[MERGE] {patched_path}\n"
        f"  kinds updated            : {kinds_touched}\n"
        f"  flat attrs added         : {flat_added}\n"
        f"  grouped attrs added      : {grouped_added}\n"
        f"  ResourceGroups created   : {groups_created}"
    )


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    merge(sys.argv[1], sys.argv[2])