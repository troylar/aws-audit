"""Collection API endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...dependencies import get_collection_store

router = APIRouter(prefix="/collections")


class CollectionSummary(BaseModel):
    """Collection summary for list view."""

    name: str
    account_id: str
    description: str
    snapshot_count: int
    include_tags: dict
    exclude_tags: dict


@router.get("")
async def list_collections():
    """List all collections."""
    store = get_collection_store()
    collections = store.list_all()

    return {
        "collections": [
            {
                "name": coll.name,
                "account_id": coll.account_id,
                "description": coll.description or "",
                "snapshot_count": len(coll.snapshots) if coll.snapshots else 0,
                "include_tags": coll.include_tags or {},
                "exclude_tags": coll.exclude_tags or {},
                "created_at": (
                    coll.created_at.isoformat() if hasattr(coll.created_at, "isoformat") else str(coll.created_at)
                ),
            }
            for coll in collections
        ],
        "count": len(collections),
    }


@router.get("/{name}")
async def get_collection(name: str, account_id: Optional[str] = None):
    """Get collection details."""
    store = get_collection_store()

    try:
        # If account_id not provided, search all collections
        collection = None
        if account_id:
            collection = store.load(name, account_id)
        else:
            # Find first matching collection by name
            all_colls = store.list_all()
            collection = next((coll for coll in all_colls if coll.name == name), None)

        if not collection:
            raise HTTPException(status_code=404, detail=f"Collection '{name}' not found")

        return {
            "name": collection.name,
            "account_id": collection.account_id,
            "description": collection.description or "",
            "include_tags": collection.include_tags or {},
            "exclude_tags": collection.exclude_tags or {},
            "snapshots": collection.snapshots or [],
            "active_snapshot": collection.active_snapshot,
            "created_at": (
                collection.created_at.isoformat()
                if hasattr(collection.created_at, "isoformat")
                else str(collection.created_at)
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
