"""Helper utilities for SDK compatibility."""
 
import logging
 
from aria.ops.object import Identifier
 
_logger = logging.getLogger(__name__)
# Track unique resource_id patterns we couldn't extract an RG from. Avoids
# log spam when many resources share the same non-standard ID shape.
_extract_rg_misses: set[str] = set()
 
 
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
            ("subscription_id", sub_id),
            ("resource_group", extract_resource_group(resource_id)),
            ("region", vm.get("location", "")),
            ("resource_id", resource_id),
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