"""Configuration hashing utility for change detection."""

import hashlib
import json
from typing import Any, Dict, Set

# Attributes to exclude from hashing (volatile data)
EXCLUDE_ATTRIBUTES: Set[str] = {
    "ResponseMetadata",
    "LastModifiedDate",
    "CreatedDate",
    "CreateDate",
    "State",
    "Status",
    "RequestId",
    "VersionId",
    "LastUpdateTime",
    "LastUpdatedTime",
    "ModifiedTime",
}


def compute_config_hash(resource_data: Dict[str, Any]) -> str:
    """Compute stable SHA256 hash of resource configuration.

    This hash is used for change detection. Volatile attributes
    (timestamps, states, etc.) are excluded to prevent false positives.

    Args:
        resource_data: Resource configuration dictionary

    Returns:
        64-character SHA256 hex string
    """
    # Deep copy and remove excluded attributes
    clean_data = _remove_volatile_attributes(resource_data, EXCLUDE_ATTRIBUTES)

    # Normalize: sort keys for deterministic JSON
    normalized = json.dumps(clean_data, sort_keys=True, default=str)

    # Hash
    return hashlib.sha256(normalized.encode()).hexdigest()


def _remove_volatile_attributes(data: Any, exclude_set: Set[str]) -> Any:
    """Recursively remove excluded attributes from nested dict/list.

    Args:
        data: Data structure to clean (dict, list, or primitive)
        exclude_set: Set of attribute names to exclude

    Returns:
        Cleaned data structure
    """
    if isinstance(data, dict):
        return {k: _remove_volatile_attributes(v, exclude_set) for k, v in data.items() if k not in exclude_set}
    elif isinstance(data, list):
        return [_remove_volatile_attributes(item, exclude_set) for item in data]
    else:
        return data
