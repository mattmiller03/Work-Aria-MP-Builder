"""Helper utilities for SDK compatibility."""
 
import logging
 
from aria.ops.object import Identifier
 
_logger = logging.getLogger(__name__)
# Track unique resource_id patterns we couldn't extract an RG from. Avoids
# log spam when many resources share the same non-standard ID shape.
_extract_rg_misses: set[str] = set()
# Track RG references that missed the rg_lookup (deleted RGs, or RGs from
# subscriptions outside the enumerated set). One log line per unique miss.
_rg_lookup_misses: set[str] = set()
 
 
def make_identifiers(pairs):
    """Convert a list of (key, value) tuples to Identifier objects.
 
    Args:
        pairs: List of (key, value) tuples
 
    Returns:
        List of Identifier objects
    """
    return [Identifier(key, value) for key, value in pairs]
 
 
def extract_resource_group(resource_id):
    """Extract resource group name from an Azure resource ID.
 
    Returns "" if the ID doesn't contain a /resourceGroups/X/ segment
    (e.g., subscription-level resources, Arc-managed resources with
    non-standard IDs). Logs a warning once per unique ID shape so the
    caller can decide whether to skip parent linking or fall back.
 
    NOTE (casing): the returned name carries whatever casing the *child*
    resource's ID path used, which Azure does not keep consistent across
    resources in the same RG. Never emit this value into identifiers
    directly — resolve through rg_lookup / canonical_rg_* first.
    """
    parts = resource_id.split("/")
    for i, part in enumerate(parts):
        if part.lower() == "resourcegroups" and i + 1 < len(parts):
            return parts[i + 1]
    # Not found — log once per unique pattern (collapse the variable
    # parts so we don't fill the log with one entry per resource).
    if resource_id:
        # Collapse GUIDs and trailing names so the pattern is reusable
        import re
        pattern = re.sub(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", "<guid>", resource_id)
        # Truncate trailing path component to <name>
        head = "/".join(pattern.split("/")[:-1])
        if head and head not in _extract_rg_misses:
            _extract_rg_misses.add(head)
            _logger.warning(
                "extract_resource_group: no /resourceGroups/ segment in pattern %s/<name>",
                head,
            )
    return ""
 
 
# ---------------------------------------------------------------------------
# Canonical Resource Group resolution
# ---------------------------------------------------------------------------
#
# Fixes the "RG casing fork" defect (2026-07-16): ~20 collectors built RG
# parent references with
#     rg_id = f"/subscriptions/{sub_id}/resourceGroups/{rg_name}".lower()
# while the RG objects already ingested in Aria Ops are keyed with Azure's
# original casing. ID is a uniqueness-bearing identifier, so lowercased edge
# references can never resolve against original-cased RG objects — the node
# silently skips every such edge (confirmed via Suite API: 341 camelCase RGs
# vs 184 lowercase duplicates minted by the lowercasing code; a lowercase RG
# showed CHILD:2 proving edges attach when keys byte-match).
#
# THE RULE (same as the phantom-VM fix): lowercase is for dict LOOKUP KEYS
# only. Emitted identifier values always carry Azure's original casing,
# byte-identical between the declaring collector and every referencing
# collector.
#
# Pattern:
#   1. resource_groups.py runs first, declares each RG using the RG list
#      API's own `id`/`name` fields VERBATIM (no .lower()), and populates
#      rg_lookup via build_rg_lookup().
#   2. adapter.py passes rg_lookup to every child collector (same plumbing
#      as vm_lookup).
#   3. Child collectors call canonical_rg_id() / reference_resource_group()
#      instead of f-stringing their own rg_id.
#   4. On a lookup miss, callers SKIP the parent link — never construct a
#      fallback RG identifier, or the duplicate population comes back.
 
 
def build_rg_lookup(raw_rgs, rg_lookup=None):
    """Build/extend the canonical RG lookup from Azure RG list API results.
 
    The RG list API (GET /subscriptions/{sub}/resourcegroups) returns each
    RG's `id` and `name` in the true casing the RG was created with — this
    is the canonical recipe every emitted identifier must match.
 
    Args:
        raw_rgs: Iterable of RG dicts from the Azure API (must have "id",
            "name"; "location" used if present).
        rg_lookup: Optional existing dict to extend (multi-subscription
            collects call this once per subscription).
 
    Returns:
        Dict mapping LOWERCASED RG resource ID -> {"id": <original-cased
        ARM ID>, "name": <original-cased name>, "location": <region>}.
    """
    if rg_lookup is None:
        rg_lookup = {}
    for rg in raw_rgs:
        rg_id = rg.get("id", "")
        rg_name = rg.get("name", "")
        if not rg_id or not rg_name:
            continue
        rg_lookup[rg_id.lower()] = {
            "id": rg_id,                      # original casing — canonical
            "name": rg_name,                  # original casing — canonical
            "location": rg.get("location", ""),
        }
    return rg_lookup
 
 
def canonical_rg_id(sub_id, rg_name, rg_lookup):
    """Resolve the canonical (original-cased) RG resource ID, or None.
 
    Args:
        sub_id: Subscription ID the resource belongs to.
        rg_name: RG name in ANY casing (typically parsed out of a child
            resource's ID path via extract_resource_group()).
        rg_lookup: Dict from build_rg_lookup().
 
    Returns:
        The RG's canonical ARM resource ID exactly as the RG list API
        reported it, or None if the RG isn't in the lookup (deleted RG, or
        subscription outside the enumerated set). Callers must SKIP the
        parent link on None — never fabricate an ID.
    """
    if not sub_id or not rg_name or not rg_lookup:
        return None
    key = f"/subscriptions/{sub_id}/resourcegroups/{rg_name}".lower()
    entry = rg_lookup.get(key)
    if entry is None:
        miss = f"{sub_id}/{rg_name}".lower()
        if miss not in _rg_lookup_misses:
            _rg_lookup_misses.add(miss)
            _logger.warning(
                "canonical_rg_id: RG %r (sub %s) not in rg_lookup — "
                "skipping parent link", rg_name, sub_id,
            )
        return None
    return entry["id"]
 
 
def reference_resource_group(result, adapter_kind, sub_id, rg_name, rg_lookup):
    """Return the canonical RG object for a parent/child link, or None.
 
    Sibling of reference_vm(): resolves any-cased RG names through
    rg_lookup and builds name + identifiers from the RG list API's OWN
    field values — byte-identical to the declaration recipe in
    resource_groups.py. Keep the two recipes in lockstep: if the
    identifier list there ever changes, change it here too.
 
    Returns None when the RG isn't in the lookup. Callers should SKIP the
    relationship in that case — never create a fallback object.
 
    Args:
        result: CollectResult being populated.
        adapter_kind: Adapter kind string.
        sub_id: Subscription ID the referencing resource belongs to.
        rg_name: RG name in any casing (e.g., from
            extract_resource_group(child_resource_id)).
        rg_lookup: Dict from build_rg_lookup().
 
    Returns:
        The canonical RG object, or None if the RG is not in inventory.
    """
    # Local import to avoid a circular import at module load time.
    from constants import OBJ_RESOURCE_GROUP, RES_IDENT_SUB, RES_IDENT_ID
 
    if not sub_id or not rg_name or not rg_lookup:
        return None
    entry = rg_lookup.get(
        f"/subscriptions/{sub_id}/resourcegroups/{rg_name}".lower())
    if entry is None:
        # canonical_rg_id handles the one-shot warning; reuse it.
        canonical_rg_id(sub_id, rg_name, rg_lookup)
        return None
 
    return result.object(
        adapter_kind=adapter_kind,
        object_kind=OBJ_RESOURCE_GROUP,
        name=entry["name"],
        identifiers=make_identifiers([
            (RES_IDENT_SUB, sub_id),
            (RES_IDENT_ID, entry["id"]),
        ]),
    )
 
 
def reference_vm(result, adapter_kind, sub_id, vm_resource_id, vm_lookup):
    """Return the canonical VM object for a resource ID, or None.
 
    Fixes the "phantom VM" defect (2026-07-09): collectors that reference
    VMs from *other* APIs' resource IDs (e.g., a disk's `managedBy` field)
    were constructing identifiers from those raw IDs. Azure APIs disagree
    on resource-ID casing between endpoints, so the constructed identifiers
    didn't byte-match the objects created by virtual_machines.py — and the
    SDK minted a second, property-less VM object instead of linking to the
    real one. (Observed: 684 VM objects collected vs 332 real VMs; the 352
    phantoms carried the Disk->VM relationships while the real VMs sat
    childless — exactly the "no properties / no relationships" UI symptom.)
 
    This helper resolves the reference through `vm_lookup` (keyed on
    lowercased resource IDs, populated by virtual_machines.py) and builds
    name + identifiers from the VM API's OWN field values — byte-identical
    to the canonical creation recipe in virtual_machines.py. Keep the two
    recipes in lockstep: if the identifier list there ever changes, change
    it here too.
 
    FIX (2026-07-16): the identifier list below previously used literal
    lowercase keys ("subscription_id", "resource_group", "region",
    "resource_id") while importing — but never using — the RES_IDENT_*
    constants. The ingested VM objects are keyed with the constants'
    AZURE_* identifier names, so references built with the literals could
    never resolve. Now uses the constants, matching virtual_machines.py.
 
    Returns None when the VM isn't in the lookup (deleted VM with a stale
    managedBy, or a VM outside the enumerated subscriptions). Callers
    should SKIP the relationship in that case — never create a fallback
    object, or the phantoms come back.
 
    Args:
        result: CollectResult being populated.
        adapter_kind: Adapter kind string.
        sub_id: Subscription ID the referencing resource belongs to.
        vm_resource_id: The VM's ARM resource ID as reported by the
            referencing API (any casing).
        vm_lookup: Dict mapping lowercased VM resource IDs to the VM
            dicts returned by the Azure VM API.
 
    Returns:
        The canonical VM object, or None if the VM is not in inventory.
    """
    # Local import to avoid a circular import at module load time
    # (constants does not import helpers, but keep this defensive).
    from constants import (OBJ_VIRTUAL_MACHINE, RES_IDENT_SUB, RES_IDENT_RG,
                           RES_IDENT_REGION, RES_IDENT_ID)
 
    if not vm_resource_id or not vm_lookup:
        return None
    vm = vm_lookup.get(vm_resource_id.lower())
    if vm is None:
        return None
 
    resource_id = vm.get("id", "")
    vm_name = vm.get("name", "")
    if not resource_id or not vm_name:
        return None
 
    return result.object(
        adapter_kind=adapter_kind,
        object_kind=OBJ_VIRTUAL_MACHINE,
        name=vm_name,
        identifiers=make_identifiers([
            (RES_IDENT_SUB, sub_id),
            (RES_IDENT_RG, extract_resource_group(resource_id)),
            (RES_IDENT_REGION, vm.get("location", "")),
            (RES_IDENT_ID, resource_id),
        ]),
    )
 
 
def safe_property(obj, key, value):
    """Set a property on an object, converting None to empty string.
 
    The SDK schema requires non-null values for all properties.
    Azure APIs sometimes return null for optional fields.
    Numeric values (int, float) are preserved as-is for numeric properties.
    """
    if value is None:
        value = ""
    elif isinstance(value, (int, float)):
        obj.with_property(key, value)
        return
    obj.with_property(key, str(value))
 
 
def sanitize_tag_key(key):
    """Sanitize an Azure tag key for use as an Aria Ops property key.
 
    Replaces spaces and special characters with underscores, converts
    to lowercase for consistency.
    """
    sanitized = key.replace(" ", "_").replace("-", "_").replace(".", "_")
    sanitized = sanitized.replace("/", "_").replace("\\", "_")
    # Remove any remaining non-alphanumeric chars except underscore
    sanitized = "".join(c if c.isalnum() or c == "_" else "_" for c in sanitized)
    return sanitized.lower()