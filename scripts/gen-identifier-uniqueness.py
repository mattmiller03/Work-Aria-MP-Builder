#!/usr/bin/env python3
"""Generate app/identifier_uniqueness.py from the native describe.xml.

Parses the native MicrosoftAzureAdapter describe.xml and emits, per
ResourceKind, {identifier_key: is_part_of_uniqueness} where identType="1"
maps to True and identType="2" maps to False. The runtime adapter MUST emit
identifiers with these exact uniqueness flags or Aria silently drops every
relationship whose endpoint identity doesn't resolve against the stored
(describe-keyed) objects.

Usage:
  python3 scripts/gen-identifier-uniqueness.py \
      sdk_packages/MicrosoftAzureAdapter-*/AzureAdapter/MicrosoftAzureAdapter/conf/describe.xml \
      > Azure-Native-Build/app/identifier_uniqueness.py
"""
import sys, re, json

def main(path):
    xml = open(path, encoding="utf-8", errors="replace").read()
    blocks = re.split(r'(?=<ResourceKind key=")', xml)
    kindmap = {}
    for b in blocks:
        m = re.match(r'<ResourceKind key="([^"]+)"', b)
        if not m:
            continue
        head = b.split("<ResourceGroup", 1)[0]
        idents = {}
        for mm in re.finditer(r"<ResourceIdentifier\b[^>]*>", head):
            tag = mm.group(0)
            k = re.search(r'key="([^"]+)"', tag)
            t = re.search(r'identType="(\d)"', tag)
            if k and t:
                idents[k.group(1)] = (t.group(1) == "1")
        if idents:
            kindmap[m.group(1)] = idents
    out = json.dumps(kindmap, indent=4, sort_keys=True).replace(": true", ": True").replace(": false", ": False")
    print('"""AUTO-GENERATED from native MicrosoftAzureAdapter describe.xml.')
    print("Maps each ResourceKind -> {identifier_key: is_part_of_uniqueness}.")
    print('identType="1" -> True (part of uniqueness); identType="2" -> False.')
    print("Regenerate with scripts/gen-identifier-uniqueness.py; do NOT hand-edit.")
    print('"""')
    print()
    print("KIND_IDENTIFIER_UNIQUENESS = " + out)

if __name__ == "__main__":
    main(sys.argv[1])
