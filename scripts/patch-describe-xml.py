#!/usr/bin/env python3
"""Post-build script to patch the generated describe.xml.

The Python SDK's ObjectType class doesn't support all the XML attributes
needed for Aria Ops UI integration (type, subType, worldObjectName, showTag).
This script patches the generated describe.xml after mp-build to add them.

Each attribute patch REPLACES any existing same-named attribute rather than
appending, so we don't end up with duplicate `type="..."` attributes (which
produce malformed XML and cause Suite-API to reject the pak synchronously
during APPLY_ADAPTER).

Usage:
    python patch-describe-xml.py [path/to/describe.xml]

If no path is given, looks in the default location:
    ../Azure-Native-Build/conf/describe.xml

Run this AFTER mp-build but BEFORE mp-build finishes packaging the .pak.
Or better: integrate into the build process via a wrapper script.
"""

import re
import sys
import os


# ---------------------------------------------------------------------------
# Attribute patches — per-ResourceKind attribute overrides
#
# Each entry maps a ResourceKind `key` to a dict of attributes that should be
# present (overwriting any existing attribute of the same name emitted by the
# SDK).
# ---------------------------------------------------------------------------

ATTR_PATCHES = {
    "AZURE_WORLD": {
        "showTag": "false",
        "type": "8",
        "subType": "6",
        "worldObjectName": "Azure World",
    },
    "AZURE_REGION": {
        "showTag": "false",
    },
    "AZURE_REGION_PER_SUB": {
        "showTag": "false",
    },
    "AZURE_RESOURCE_GROUP": {
        "type": "8",
    },
    "AZURE_SERVICES_FROM_XML": {
        "showTag": "false",
    },
    # SDK emits "<adapter-name>_adapter_instance" for the adapter-instance
    # ResourceKind. Native pak uses "MicrosoftAzureAdapter Instance" (with a
    # space), and all our bundled content (traversal specs, dashboards) points
    # at that exact name. We rename the key below. monitoringInterval matches
    # the native pak's 10-minute cycle.
    "MicrosoftAzureAdapter_adapter_instance": {
        "monitoringInterval": "10",
    },
}

# ResourceKind keys that must be renamed after attribute patching. Map of
# old_key -> new_key. Keep in sync with OBJ_ADAPTER_INSTANCE in
# Azure-Native-Build/app/constants.py.
RENAME_KINDS = {
    "MicrosoftAzureAdapter_adapter_instance": "MicrosoftAzureAdapter Instance",
}

# ---------------------------------------------------------------------------
# Child-element patches — injected as children of the named ResourceKind.
# These are added once per kind; re-runs are a no-op because we check for the
# child's presence first.
# ---------------------------------------------------------------------------

POWER_STATE_BLOCK = """
         <PowerState alias="summary|runtime|powerState">
            <PowerStateValue key="ON" value="Powered On" />
            <PowerStateValue key="OFF" value="Powered Off" />
            <PowerStateValue key="UNKNOWN" value="Unknown" />
         </PowerState>"""

CHILD_PATCHES = [
    {
        "kind": "AZURE_VIRTUAL_MACHINE",
        "child_tag": "PowerState",
        "block": POWER_STATE_BLOCK,
        "description": "AZURE_VIRTUAL_MACHINE: add PowerState for health integration",
    },
]


# ---------------------------------------------------------------------------
# Core patching helpers
# ---------------------------------------------------------------------------

_ATTR_RE = re.compile(r'(\w+)="([^"]*)"')


def _apply_attr_patch(content: str, kind: str, new_attrs: dict) -> tuple[str, int]:
    """Replace or add attributes on `<ResourceKind key="KIND" ...>` opening tag.

    Removes any SDK-emitted attribute whose name matches one of new_attrs.keys(),
    then prepends the new attributes right after the `key="..."` attribute.
    """
    pattern = re.compile(
        r'(<ResourceKind\s+key="' + re.escape(kind) + r'")([^>]*?)(/?>)'
    )

    def substitute(match):
        head = match.group(1)           # <ResourceKind key="KIND"
        rest = match.group(2)           # everything else before >
        close = match.group(3)          # > or />

        # Parse existing attributes and strip the ones we're overriding.
        preserved = []
        for attr_match in _ATTR_RE.finditer(rest):
            name = attr_match.group(1)
            if name in new_attrs:
                continue
            preserved.append(attr_match.group(0))

        # Build the new attribute block: our overrides first (in insertion
        # order), then whatever the SDK emitted that we didn't override.
        our_attrs = " ".join(f'{k}="{v}"' for k, v in new_attrs.items())
        preserved_attrs = " ".join(preserved)

        parts = [head]
        if our_attrs:
            parts.append(" " + our_attrs)
        if preserved_attrs:
            parts.append(" " + preserved_attrs)
        parts.append(close)
        return "".join(parts)

    new_content, count = pattern.subn(substitute, content)
    return new_content, count


def _apply_child_patch(content: str, kind: str, child_tag: str, block: str) -> tuple[str, int]:
    """Insert `block` as the first child of `<ResourceKind key="KIND">`, unless
    a child with `child_tag` is already present inside it."""
    open_re = re.compile(
        r'(<ResourceKind\s+key="' + re.escape(kind) + r'"[^>]*>)'
    )
    match = open_re.search(content)
    if not match:
        return content, 0

    open_end = match.end()
    # Look for the matching </ResourceKind> to get the body
    close_start = content.find("</ResourceKind>", open_end)
    if close_start == -1:
        return content, 0

    body = content[open_end:close_start]
    if f"<{child_tag}" in body:
        # Already present — idempotent, skip
        return content, 0

    injected = content[:open_end] + block + content[open_end:]
    return injected, 1


def _rename_kind(content: str, old_key: str, new_key: str) -> tuple[str, int]:
    """Rename every `<ResourceKind key="old_key">` occurrence to new_key.
    Does NOT touch other XML (the adapter instance kind doesn't appear as a
    child/parent reference inside describe.xml itself).
    """
    pattern = re.compile(
        r'(<ResourceKind\s+key=")' + re.escape(old_key) + r'(")'
    )
    return pattern.subn(r'\1' + new_key + r'\2', content)


def patch_describe_xml(filepath: str) -> int:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    original = content
    applied = 0

    # 1. Attribute patches (strip any conflicting existing attrs, then inject)
    for kind, attrs in ATTR_PATCHES.items():
        content, count = _apply_attr_patch(content, kind, attrs)
        attr_preview = ", ".join(f"{k}={v}" for k, v in attrs.items())
        if count > 0:
            applied += count
            print(f"  [PATCHED] {kind}: set {attr_preview}")
        else:
            print(f"  [SKIP]    {kind}: ResourceKind not found")

    # 2. Child-element injections (PowerState, etc.)
    for patch in CHILD_PATCHES:
        content, count = _apply_child_patch(
            content, patch["kind"], patch["child_tag"], patch["block"]
        )
        if count > 0:
            applied += count
            print(f"  [PATCHED] {patch['description']}")
        else:
            print(f"  [SKIP]    {patch['description']} (already present or ResourceKind missing)")

    # 3. ResourceKind renames (applied last so attribute patches can target
    # the SDK's original key). Each rename is idempotent via check before sub.
    for old_key, new_key in RENAME_KINDS.items():
        content, count = _rename_kind(content, old_key, new_key)
        if count > 0:
            applied += count
            print(f"  [PATCHED] rename ResourceKind: {old_key} -> {new_key}")
        else:
            print(f"  [SKIP]    rename {old_key} (not found — already renamed?)")

    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\n{applied} patches applied to {filepath}")
    else:
        print(f"\nNo patches needed for {filepath}")

    return applied


def main():
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(script_dir, "..", "Azure-Native-Build", "conf", "describe.xml"),
            os.path.join(script_dir, "..", "conf", "describe.xml"),
            "conf/describe.xml",
        ]
        filepath = None
        for c in candidates:
            if os.path.exists(c):
                filepath = c
                break
        if filepath is None:
            print("Could not find describe.xml. Pass the path as an argument:")
            print(f"  python {sys.argv[0]} path/to/describe.xml")
            sys.exit(1)

    print(f"Patching: {os.path.abspath(filepath)}")
    print()
    patch_describe_xml(filepath)


if __name__ == "__main__":
    main()
