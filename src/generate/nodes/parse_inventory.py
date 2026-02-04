"""Parse inventory node for LangGraph workflow."""

import json
from pathlib import Path
from typing import Any, Dict, List

import yaml

from ...models.generation import TrackedResource
from ...snapshot.storage import SnapshotStorage
from ..state import GenerationState, emit_progress


def _load_from_file(filepath: str) -> List[Dict[str, Any]]:
    """Load resources from a JSON or YAML export file.

    Supports multiple formats:
    - JSON with 'resources' array (from snapshot report export)
    - JSON array of resources directly
    - YAML with 'resources' array
    - YAML array of resources directly

    Args:
        filepath: Path to JSON or YAML file

    Returns:
        List of resource dictionaries

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is invalid or unsupported
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {filepath}")

    suffix = path.suffix.lower()
    content = path.read_text(encoding="utf-8")

    if suffix == ".json":
        data = json.loads(content)
    elif suffix in (".yaml", ".yml"):
        data = yaml.safe_load(content)
    else:
        raise ValueError(
            f"Unsupported file format: {suffix}. Use .json, .yaml, or .yml"
        )

    # Handle different data structures
    if isinstance(data, list):
        # Direct array of resources
        return data
    elif isinstance(data, dict):
        # Look for resources array in common locations
        if "resources" in data:
            return data["resources"]
        elif "inventory" in data:
            return data["inventory"]
        else:
            raise ValueError(
                "File must contain 'resources' or 'inventory' array, or be a direct array of resources"
            )
    else:
        raise ValueError("Invalid file format: expected array or object with resources")


def parse_inventory(state: GenerationState) -> Dict[str, Any]:
    """Load resources from snapshot or export file.

    Args:
        state: Current generation state with snapshot_name or input_file

    Returns:
        Dict with:
        - resources: List[TrackedResource] - All resources
        - snapshot: The loaded snapshot object (None if from file)
        - errors: List[str] - Any loading errors
    """
    input_file = state.get("input_file")
    snapshot_name = state.get("snapshot_name")

    # Load from file if provided
    if input_file:
        emit_progress(
            "activity",
            {
                "message": f"Loading resources from {Path(input_file).name}",
                "step": "parse_inventory",
            },
        )
        try:
            resource_dicts = _load_from_file(input_file)
        except (FileNotFoundError, ValueError) as e:
            return {
                "resources": [],
                "snapshot": None,
                "errors": [str(e)],
            }

        emit_progress(
            "activity",
            {
                "message": f"Converting {len(resource_dicts)} resources",
                "step": "parse_inventory",
                "count": len(resource_dicts),
            },
        )

        # Convert to TrackedResource objects
        resources: List[TrackedResource] = []
        for i, res in enumerate(resource_dicts):
            tracked = TrackedResource.from_inventory(res)
            resources.append(tracked)
            # Emit progress every 10 resources
            if (i + 1) % 10 == 0:
                emit_progress(
                    "activity",
                    {
                        "message": f"Processed {i + 1}/{len(resource_dicts)} resources",
                        "step": "parse_inventory",
                        "processed": i + 1,
                        "total": len(resource_dicts),
                    },
                )

        # Count resource types
        type_counts: Dict[str, int] = {}
        for r in resources:
            rtype = (
                r.resource_type.split(":")[0]
                if ":" in r.resource_type
                else r.resource_type
            )
            type_counts[rtype] = type_counts.get(rtype, 0) + 1

        emit_progress(
            "activity",
            {
                "message": f"Loaded {len(resources)} resources ({len(type_counts)} types)",
                "step": "parse_inventory",
                "total": len(resources),
                "types": type_counts,
            },
        )

        return {
            "resources": resources,
            "snapshot": None,
            "errors": [],
        }

    # Fall back to snapshot loading
    if not snapshot_name:
        return {
            "resources": [],
            "snapshot": None,
            "errors": ["No snapshot_name or input_file provided"],
        }

    emit_progress(
        "activity",
        {
            "message": f"Loading snapshot '{snapshot_name}'",
            "step": "parse_inventory",
        },
    )

    storage = SnapshotStorage()
    try:
        snapshot = storage.load_snapshot(snapshot_name)
    except FileNotFoundError:
        return {
            "resources": [],
            "snapshot": None,
            "errors": [f"Snapshot '{snapshot_name}' not found"],
        }

    emit_progress(
        "activity",
        {
            "message": f"Converting {len(snapshot.resources)} resources",
            "step": "parse_inventory",
            "count": len(snapshot.resources),
        },
    )

    # Convert to TrackedResource objects
    resources = []
    for i, resource in enumerate(snapshot.resources):
        tracked = TrackedResource(
            resource_type=resource.resource_type,
            name=resource.name,
            arn=resource.arn,
            region=resource.region,
            raw_config=resource.raw_config or {},
            tags=resource.tags or {},
        )
        resources.append(tracked)
        # Emit progress every 10 resources
        if (i + 1) % 10 == 0:
            emit_progress(
                "activity",
                {
                    "message": f"Processed {i + 1}/{len(snapshot.resources)} resources",
                    "step": "parse_inventory",
                    "processed": i + 1,
                    "total": len(snapshot.resources),
                },
            )

    # Count resource types
    type_counts: Dict[str, int] = {}
    for r in resources:
        rtype = (
            r.resource_type.split(":")[0] if ":" in r.resource_type else r.resource_type
        )
        type_counts[rtype] = type_counts.get(rtype, 0) + 1

    emit_progress(
        "activity",
        {
            "message": f"Loaded {len(resources)} resources ({len(type_counts)} types)",
            "step": "parse_inventory",
            "total": len(resources),
            "types": type_counts,
        },
    )

    return {
        "resources": resources,
        "snapshot": snapshot,
        "errors": [],
    }
