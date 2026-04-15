#!/usr/bin/env python3
"""Post-build script to patch the generated describe.xml.

The Python SDK's ObjectType class doesn't support all the XML attributes
needed for Aria Ops UI integration (type, subType, worldObjectName, showTag).
This script patches the generated describe.xml after mp-build to add them.

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
# Patches to apply
# ---------------------------------------------------------------------------

PATCHES = [
    # AZURE_WORLD: add type="8" subType="6" worldObjectName="Azure World" showTag="false"
    {
        "find": r'<ResourceKind key="AZURE_WORLD"([^>]*)>',
        "replace": '<ResourceKind key="AZURE_WORLD" showTag="false" type="8" subType="6" worldObjectName="Azure World"\\1>',
        "description": "AZURE_WORLD: set as world object (Home Overview)",
    },

    # AZURE_REGION: add type="4" showTag="false"
    {
        "find": r'<ResourceKind key="AZURE_REGION"([^>]*)>',
        "replace": '<ResourceKind key="AZURE_REGION" showTag="false"\\1>',
        "description": "AZURE_REGION: hide from tag navigation",
    },

    # AZURE_REGION_PER_SUB: add type="4" showTag="false"
    {
        "find": r'<ResourceKind key="AZURE_REGION_PER_SUB"([^>]*)>',
        "replace": '<ResourceKind key="AZURE_REGION_PER_SUB" showTag="false"\\1>',
        "description": "AZURE_REGION_PER_SUB: hide from tag navigation",
    },

    # AZURE_RESOURCE_GROUP: set type="8" (container, not leaf)
    {
        "find": r'<ResourceKind key="AZURE_RESOURCE_GROUP"([^>]*)>',
        "replace": '<ResourceKind key="AZURE_RESOURCE_GROUP" type="8"\\1>',
        "description": "AZURE_RESOURCE_GROUP: set as container type",
    },

    # AZURE_VIRTUAL_MACHINE: add PowerState alias
    {
        "find": r'(<ResourceKind key="AZURE_VIRTUAL_MACHINE"[^>]*>)',
        "replace": '\\1\n         <PowerState alias="summary|runtime|powerState">\n            <PowerStateValue key="ON" value="Powered On" />\n            <PowerStateValue key="OFF" value="Powered Off" />\n            <PowerStateValue key="UNKNOWN" value="Unknown" />\n         </PowerState>',
        "description": "AZURE_VIRTUAL_MACHINE: add PowerState for health integration",
    },

    # AZURE_SERVICES_FROM_XML: add showTag="false"
    {
        "find": r'<ResourceKind key="AZURE_SERVICES_FROM_XML"([^>]*)>',
        "replace": '<ResourceKind key="AZURE_SERVICES_FROM_XML" showTag="false"\\1>',
        "description": "AZURE_SERVICES_FROM_XML: hide from tag navigation",
    },
]


def patch_describe_xml(filepath: str) -> int:
    """Apply patches to the describe.xml file.

    Returns:
        Number of patches applied.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    original = content
    applied = 0

    for patch in PATCHES:
        pattern = patch["find"]
        replacement = patch["replace"]
        desc = patch["description"]

        new_content, count = re.subn(pattern, replacement, content)
        if count > 0:
            content = new_content
            applied += count
            print(f"  [PATCHED] {desc}")
        else:
            print(f"  [SKIP]    {desc} (pattern not found)")

    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\n{applied} patches applied to {filepath}")
    else:
        print(f"\nNo patches needed for {filepath}")

    return applied


def main():
    # Find describe.xml
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        # Default: look relative to this script's location
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
