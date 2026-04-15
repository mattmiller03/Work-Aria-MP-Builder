"""Helper utilities for SDK compatibility."""

from aria.ops.object import Identifier


def make_identifiers(pairs):
    """Convert a list of (key, value) tuples to Identifier objects.

    Args:
        pairs: List of (key, value) tuples

    Returns:
        List of Identifier objects
    """
    return [Identifier(key, value) for key, value in pairs]


def extract_resource_group(resource_id):
    """Extract resource group name from an Azure resource ID."""
    parts = resource_id.split("/")
    for i, part in enumerate(parts):
        if part.lower() == "resourcegroups" and i + 1 < len(parts):
            return parts[i + 1]
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
