"""Snapshot API endpoints."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from ...dependencies import get_resource_store, get_snapshot_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/snapshots")

# In-memory store for snapshot creation jobs
_snapshot_jobs: Dict[str, dict] = {}


class SnapshotSummary(BaseModel):
    """Snapshot summary for list view."""

    name: str
    created_at: str
    account_id: str
    regions: List[str]
    resource_count: int
    is_active: bool


class SnapshotDetail(BaseModel):
    """Full snapshot details."""

    name: str
    created_at: str
    account_id: str
    regions: List[str]
    resource_count: int
    service_counts: dict
    is_active: bool
    metadata: Optional[dict] = None


@router.get("", response_model=List[SnapshotSummary])
async def list_snapshots():
    """List all snapshots."""
    store = get_snapshot_store()
    snapshots = store.list_all()

    return [
        SnapshotSummary(
            name=s["name"],
            created_at=s["created_at"].isoformat() if hasattr(s["created_at"], "isoformat") else str(s["created_at"]),
            account_id=s["account_id"],
            regions=s.get("regions", []),
            resource_count=s.get("resource_count", 0),
            is_active=s.get("is_active", False),
        )
        for s in snapshots
    ]


class CreateSnapshotRequest(BaseModel):
    """Request model for creating a snapshot."""

    name: Optional[str] = None  # Auto-generated if not provided
    regions: Optional[List[str]] = None  # Defaults to us-east-1
    inventory: Optional[str] = None  # Inventory name to use
    set_active: bool = True
    use_config: bool = True  # Use AWS Config for collection


class SnapshotJobStatus(BaseModel):
    """Status of a snapshot creation job."""

    job_id: str
    status: str  # pending, running, completed, failed
    snapshot_name: Optional[str] = None
    message: Optional[str] = None
    progress: Optional[int] = None
    created_at: str


def _create_snapshot_sync(
    job_id: str, name: str, regions: List[str], inventory: Optional[str], set_active: bool, use_config: bool
):
    """Synchronous snapshot creation function to run in background."""
    import os
    import sys

    import boto3

    # Add project root to path for imports in thread
    project_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    )
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from src.config import config
    from src.snapshot.collector import SnapshotCollector
    from src.snapshot.inventory_storage import InventoryStorage
    from src.snapshot.storage import SnapshotStorage

    try:
        _snapshot_jobs[job_id]["status"] = "running"
        _snapshot_jobs[job_id]["message"] = "Validating AWS credentials..."

        # Get AWS identity
        sts = boto3.client("sts")
        identity = sts.get_caller_identity()
        account_id = identity["Account"]

        _snapshot_jobs[job_id]["message"] = f"Authenticated as account {account_id}"

        # Load inventory if specified
        inventory_storage = InventoryStorage(config.storage_path)
        active_inventory = None
        include_tags = {}
        exclude_tags = {}

        if inventory:
            try:
                active_inventory = inventory_storage.get_by_name(inventory, account_id)
                include_tags = active_inventory.include_tags or {}
                exclude_tags = active_inventory.exclude_tags or {}
                _snapshot_jobs[job_id]["message"] = f"Using inventory: {inventory}"
            except Exception:
                _snapshot_jobs[job_id]["status"] = "failed"
                _snapshot_jobs[job_id]["message"] = f"Inventory '{inventory}' not found"
                return

        _snapshot_jobs[job_id]["message"] = f"Collecting resources from {', '.join(regions)}..."
        _snapshot_jobs[job_id]["progress"] = 10

        # Create collector and collect resources
        collector = SnapshotCollector(
            regions=regions,
            include_tags=include_tags,
            exclude_tags=exclude_tags,
            use_config=use_config,
        )

        snapshot = collector.collect(snapshot_name=name)
        _snapshot_jobs[job_id]["progress"] = 80

        # Save snapshot
        _snapshot_jobs[job_id]["message"] = f"Saving snapshot with {snapshot.resource_count} resources..."
        storage = SnapshotStorage(config.storage_path)
        snapshot.is_active = set_active
        storage.save_snapshot(snapshot)

        _snapshot_jobs[job_id]["progress"] = 100
        _snapshot_jobs[job_id]["status"] = "completed"
        _snapshot_jobs[job_id]["snapshot_name"] = snapshot.name
        _snapshot_jobs[job_id]["message"] = (
            f"Created snapshot '{snapshot.name}' with {snapshot.resource_count} resources"
        )

    except Exception as e:
        logger.exception(f"Snapshot creation failed: {e}")
        _snapshot_jobs[job_id]["status"] = "failed"
        _snapshot_jobs[job_id]["message"] = str(e)


@router.post("")
async def create_snapshot(request: CreateSnapshotRequest, background_tasks: BackgroundTasks):
    """Create a new snapshot (runs in background)."""

    # Generate snapshot name if not provided
    name = request.name
    if not name:
        name = f"snapshot-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    # Default regions
    regions = request.regions or ["us-east-1"]

    # Create job ID
    job_id = str(uuid.uuid4())[:8]

    # Initialize job status
    _snapshot_jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "snapshot_name": name,
        "message": "Starting snapshot creation...",
        "progress": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Run in background thread (not async since boto3 is sync)
    import threading

    thread = threading.Thread(
        target=_create_snapshot_sync,
        args=(job_id, name, regions, request.inventory, request.set_active, request.use_config),
        daemon=True,
    )
    thread.start()

    return {
        "job_id": job_id,
        "message": f"Snapshot creation started for '{name}'",
        "status_url": f"/api/snapshots/jobs/{job_id}",
    }


@router.get("/jobs/{job_id}")
async def get_snapshot_job_status(job_id: str):
    """Get status of a snapshot creation job."""
    if job_id not in _snapshot_jobs:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    return _snapshot_jobs[job_id]


@router.get("/{name}")
async def get_snapshot(name: str):
    """Get snapshot details."""
    store = get_snapshot_store()
    snapshot = store.load(name)

    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Snapshot '{name}' not found")

    return {
        "name": snapshot.name,
        "created_at": snapshot.created_at.isoformat(),
        "account_id": snapshot.account_id,
        "regions": snapshot.regions,
        "resource_count": snapshot.resource_count,
        "service_counts": snapshot.service_counts,
        "is_active": snapshot.is_active,
        "metadata": snapshot.metadata,
    }


@router.delete("/{name}")
async def delete_snapshot(name: str):
    """Delete a snapshot."""
    store = get_snapshot_store()

    if not store.exists(name):
        raise HTTPException(status_code=404, detail=f"Snapshot '{name}' not found")

    success = store.delete(name)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to delete snapshot")

    return {"message": f"Snapshot '{name}' deleted"}


@router.post("/{name}/activate")
async def activate_snapshot(name: str):
    """Set snapshot as active baseline."""
    store = get_snapshot_store()

    if not store.exists(name):
        raise HTTPException(status_code=404, detail=f"Snapshot '{name}' not found")

    store.set_active(name)
    return {"message": f"Snapshot '{name}' is now active"}


class RenameRequest(BaseModel):
    """Request model for renaming."""

    new_name: str


@router.post("/{name}/rename")
async def rename_snapshot(name: str, request: RenameRequest):
    """Rename a snapshot."""
    store = get_snapshot_store()

    if not store.exists(name):
        raise HTTPException(status_code=404, detail=f"Snapshot '{name}' not found")

    try:
        success = store.rename(name, request.new_name)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to rename snapshot")

        return {"message": f"Snapshot renamed from '{name}' to '{request.new_name}'", "new_name": request.new_name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{name}/resources")
async def get_snapshot_resources(
    name: str,
    type: Optional[str] = Query(None, description="Filter by resource type"),
    region: Optional[str] = Query(None, description="Filter by region"),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
):
    """Get resources in a snapshot."""
    snapshot_store = get_snapshot_store()

    if not snapshot_store.exists(name):
        raise HTTPException(status_code=404, detail=f"Snapshot '{name}' not found")

    resource_store = get_resource_store()
    resources = resource_store.search(
        snapshot_name=name,
        resource_type=type,
        region=region,
        limit=limit,
        offset=offset,
    )

    return {
        "snapshot": name,
        "count": len(resources),
        "limit": limit,
        "offset": offset,
        "resources": resources,
    }
