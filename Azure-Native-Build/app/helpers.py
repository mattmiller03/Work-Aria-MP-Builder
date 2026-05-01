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
