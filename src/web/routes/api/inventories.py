"""Inventory API endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...dependencies import get_inventory_store

router = APIRouter(prefix="/inventories")


class InventorySummary(BaseModel):
    """Inventory summary for list view."""

    name: str
    account_id: str
    description: str
    snapshot_count: int
    include_tags: dict
    exclude_tags: dict


@router.get("")
async def list_inventories():
    """List all inventories."""
    store = get_inventory_store()
    inventories = store.list_all()

    return {
        "inventories": [
            {
                "name": inv.name,
                "account_id": inv.account_id,
                "description": inv.description or "",
                "snapshot_count": len(inv.snapshots) if inv.snapshots else 0,
                "include_tags": inv.include_tags or {},
                "exclude_tags": inv.exclude_tags or {},
                "created_at": (
                    inv.created_at.isoformat() if hasattr(inv.created_at, "isoformat") else str(inv.created_at)
                ),
            }
            for inv in inventories
        ],
        "count": len(inventories),
    }


@router.get("/{name}")
async def get_inventory(name: str, account_id: Optional[str] = None):
    """Get inventory details."""
    store = get_inventory_store()

    try:
        # If account_id not provided, search all inventories
        inventory = None
        if account_id:
            inventory = store.load(name, account_id)
        else:
            # Find first matching inventory by name
            all_invs = store.list_all()
            inventory = next((inv for inv in all_invs if inv.name == name), None)

        if not inventory:
            raise HTTPException(status_code=404, detail=f"Inventory '{name}' not found")

        return {
            "name": inventory.name,
            "account_id": inventory.account_id,
            "description": inventory.description or "",
            "include_tags": inventory.include_tags or {},
            "exclude_tags": inventory.exclude_tags or {},
            "snapshots": inventory.snapshots or [],
            "active_snapshot": inventory.active_snapshot,
            "created_at": (
                inventory.created_at.isoformat()
                if hasattr(inventory.created_at, "isoformat")
                else str(inventory.created_at)
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
