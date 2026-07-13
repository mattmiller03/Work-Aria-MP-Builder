#!/usr/bin/env python3
"""
cleanup-describe-xml.py — final sanitization pass for describe.xml
 
Encodes the fixes that unblocked APPLY_ADAPTER (step 16/20) on 2026-07-08
after the 8.19.19 hotfix installed successfully on Aria Ops 8.18.6.
 
Suite-API rejects describe.xml synchronously (ERROR after 0.0s, empty
errorMessages) when it violates the SDK-bundled describeSchema.xsd. The
native-XML splicing in patch-describe-xml.py imports constructs that are
legal against the *native* pak's (older) schema but not against ours:
 
  1. <enumUnselected .../> children on ResourceIdentifier  -> removed
  2. advanced="..." attributes on ResourceIdentifier       -> removed
  3. empty length="" attributes (383 of them!)             -> removed
  4. duplicate ResourceAttribute keys within one ResourceGroup
     (native pak has 7 of these bugs; our schema's Xsd11Unique
     constraint rejects them)                              -> keep first, drop rest
  5. dispOrder collisions on adapter-instance identifiers
     (injected SERVICES reused dispOrder=2 = AZURE_TENANT_ID)
                                                           -> renumber sequentially
 
Usage:
    python3.12 scripts/cleanup-describe-xml.py <path-to-describe.xml>
 
Called by build-pak.sh AFTER patch-describe-xml.py, BEFORE repacking.
Idempotent — safe to run multiple times.
 
Optional self-check (validates result against the schema sitting next to
describe.xml, requires the xmlschema package):
    python3.12 scripts/cleanup-describe-xml.py <describe.xml> --validate
"""
 
import sys
from lxml import etree
 
NS = "http://schemas.vmware.com/vcops/schema"
 
 
def q(tag: str) -> str:
    return f"{{{NS}}}{tag}"
 
 
def cleanup(path: str) -> None:
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(path, parser)
    root = tree.getroot()
 
    # --- 1. Remove <enumUnselected> children (not in SDK schema) ---
    n_enum_unselected = 0
    for el in root.iter(q("enumUnselected")):
        el.getparent().remove(el)
        n_enum_unselected += 1
    # Also catch un-namespaced occurrences from raw-text splices
    for el in root.iter("enumUnselected"):
        el.getparent().remove(el)
        n_enum_unselected += 1
 
    # --- 2 + 3. Strip advanced= and empty length= attributes everywhere ---
    n_advanced = 0
    n_empty_length = 0
    for el in root.iter():
        if "advanced" in el.attrib:
            del el.attrib["advanced"]
            n_advanced += 1
        if el.attrib.get("length") == "":
            del el.attrib["length"]
            n_empty_length += 1
 
    # --- 4. De-dupe ResourceAttribute keys within each ResourceGroup ---
    n_dup_attrs = 0
    for rg in root.iter(q("ResourceGroup")):
        seen = set()
        for ra in list(rg.findall(q("ResourceAttribute"))):
            key = ra.get("key")
            if key in seen:
                rg.remove(ra)
                n_dup_attrs += 1
            else:
                seen.add(key)
 
    # --- 5. Renumber dispOrder on adapter-instance ResourceIdentifiers ---
    # Sequential by document order; display-only, does not affect identity
    # (identType governs identity, not dispOrder).
    n_renumbered = 0
    for rk in root.iter(q("ResourceKind")):
        if rk.get("type") == "7":  # adapter instance kind
            for i, ri in enumerate(rk.findall(q("ResourceIdentifier"))):
                if ri.get("dispOrder") != str(i):
                    ri.set("dispOrder", str(i))
                    n_renumbered += 1
 
    tree.write(path, encoding="UTF-8", xml_declaration=True)
 
    print(
        f"[CLEANUP] {path}\n"
        f"  removed enumUnselected elements : {n_enum_unselected}\n"
        f"  removed advanced= attributes    : {n_advanced}\n"
        f"  removed empty length= attributes: {n_empty_length}\n"
        f"  removed duplicate attributes    : {n_dup_attrs}\n"
        f"  renumbered dispOrder values     : {n_renumbered}"
    )
 
 
def validate(describe_path: str) -> int:
    """Validate against the describeSchema.xsd next to describe.xml."""
    import os
 
    schema_path = os.path.join(os.path.dirname(describe_path), "describeSchema.xsd")
    if not os.path.exists(schema_path):
        print(f"[VALIDATE] skipped — no schema at {schema_path}")
        return 0
    try:
        import xmlschema
    except ImportError:
        print("[VALIDATE] skipped — xmlschema package not installed")
        return 0
 
    schema = xmlschema.XMLSchema11(schema_path)
    errors = list(schema.iter_errors(describe_path))
    print(f"[VALIDATE] {len(errors)} validation error(s)")
    for e in errors[:15]:
        print(f"  {e.path}: {e.reason}")
    return 1 if errors else 0
 
 
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    target = sys.argv[1]
    cleanup(target)
    if "--validate" in sys.argv[2:]:
        sys.exit(validate(target))
 