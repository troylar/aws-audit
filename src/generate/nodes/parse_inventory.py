"""Parse inventory node for LangGraph workflow."""

from typing import Any, Dict, List

from ...models.generation import TrackedResource
from ...snapshot.storage import SnapshotStorage
from ..state import GenerationState


def parse_inventory(state: GenerationState) -> Dict[str, Any]:
    """Load snapshot and extract resources.

    Args:
        state: Current generation state with snapshot_name

    Returns:
        Dict with:
        - resources: List[TrackedResource] - All resources from snapshot
        - snapshot: The loaded snapshot object
        - errors: List[str] - Any loading errors
    """
    snapshot_name = state["snapshot_name"]

    # Load snapshot from storage
    storage = SnapshotStorage()
    try:
        snapshot = storage.load_snapshot(snapshot_name)
    except FileNotFoundError:
        return {
            "resources": [],
            "snapshot": None,
            "errors": [f"Snapshot '{snapshot_name}' not found"],
        }

    # Convert to TrackedResource objects
    resources: List[TrackedResource] = []
    for resource in snapshot.resources:
        tracked = TrackedResource(
            resource_type=resource.resource_type,
            name=resource.name,
            arn=resource.arn,
            region=resource.region,
            raw_config=resource.raw_config or {},
            tags=resource.tags or {},
        )
        resources.append(tracked)

    return {
        "resources": resources,
        "snapshot": snapshot,
        "errors": [],
    }
