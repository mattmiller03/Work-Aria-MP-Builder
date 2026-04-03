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
