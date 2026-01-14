"""Snapshot API endpoints."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ...dependencies import get_resource_store, get_snapshot_store

router = APIRouter(prefix="/snapshots")


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
