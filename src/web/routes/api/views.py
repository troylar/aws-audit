"""Saved views API endpoints."""

from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...dependencies import get_database

router = APIRouter(prefix="/views")


class ColumnConfig(BaseModel):
    """Column configuration model."""

    field: str
    label: str
    visible: bool = True
    width: Optional[int] = None


class ViewConfig(BaseModel):
    """View configuration model."""

    columns: List[ColumnConfig]
    sort_by: Optional[str] = None
    sort_order: str = "asc"
    filters: Optional[dict] = None


class SavedView(BaseModel):
    """Saved view model."""

    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    view_config: ViewConfig
    is_default: bool = False
    is_favorite: bool = False


# Define available columns for resources
AVAILABLE_COLUMNS = [
    {"field": "name", "label": "Name", "default": True},
    {"field": "arn", "label": "ARN", "default": True},
    {"field": "resource_type", "label": "Type", "default": True},
    {"field": "region", "label": "Region", "default": True},
    {"field": "snapshot_name", "label": "Snapshot", "default": True},
    {"field": "tags", "label": "Tags", "default": False},
    {"field": "created_at", "label": "Created", "default": False},
    {"field": "config_hash", "label": "Config Hash", "default": False},
]


@router.get("/columns")
async def get_available_columns():
    """Get list of available columns for customization."""
    return {"columns": AVAILABLE_COLUMNS}


@router.get("")
async def list_saved_views(favorites_only: bool = False):
    """List saved views."""
    db = get_database()

    sql = "SELECT * FROM saved_views WHERE 1=1"
    params: List = []

    if favorites_only:
        sql += " AND is_favorite = 1"

    sql += " ORDER BY is_default DESC, is_favorite DESC, last_used_at DESC NULLS LAST, name"

    rows = db.fetchall(sql, tuple(params))

    views = []
    for row in rows:
        row_dict = dict(row)
        if row_dict.get("view_config"):
            row_dict["view_config"] = json.loads(row_dict["view_config"])
        views.append(row_dict)

    return {"views": views}


@router.get("/default")
async def get_default_view():
    """Get the default view configuration."""
    db = get_database()

    row = db.fetchone("SELECT * FROM saved_views WHERE is_default = 1")

    if row:
        row_dict = dict(row)
        if row_dict.get("view_config"):
            row_dict["view_config"] = json.loads(row_dict["view_config"])
        return row_dict

    # Return a default configuration if none is set
    return {
        "id": None,
        "name": "Default View",
        "view_config": {
            "columns": [{"field": c["field"], "label": c["label"], "visible": c["default"]} for c in AVAILABLE_COLUMNS],
            "sort_by": "name",
            "sort_order": "asc",
        },
    }


@router.post("")
async def create_saved_view(view: SavedView):
    """Save a new view."""
    db = get_database()

    try:
        # If this is set as default, unset other defaults
        if view.is_default:
            db.execute("UPDATE saved_views SET is_default = 0 WHERE is_default = 1")

        config_json = json.dumps(view.view_config.model_dump())
        cursor = db.execute(
            """
            INSERT INTO saved_views (name, description, view_config, is_default, is_favorite, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                view.name,
                view.description,
                config_json,
                view.is_default,
                view.is_favorite,
                datetime.utcnow().isoformat(),
            ),
        )
        db.commit()
        return {"id": cursor.lastrowid, "message": "View saved"}
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(status_code=400, detail=f"View with name '{view.name}' already exists")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{view_id}")
async def get_saved_view(view_id: int):
    """Get a saved view by ID."""
    db = get_database()
    row = db.fetchone("SELECT * FROM saved_views WHERE id = ?", (view_id,))

    if not row:
        raise HTTPException(status_code=404, detail="View not found")

    row_dict = dict(row)
    if row_dict.get("view_config"):
        row_dict["view_config"] = json.loads(row_dict["view_config"])
    return row_dict


@router.put("/{view_id}")
async def update_saved_view(view_id: int, view: SavedView):
    """Update a saved view."""
    db = get_database()

    existing = db.fetchone("SELECT id FROM saved_views WHERE id = ?", (view_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="View not found")

    # If this is set as default, unset other defaults
    if view.is_default:
        db.execute("UPDATE saved_views SET is_default = 0 WHERE is_default = 1 AND id != ?", (view_id,))

    config_json = json.dumps(view.view_config.model_dump())
    db.execute(
        """
        UPDATE saved_views
        SET name = ?, description = ?, view_config = ?, is_default = ?, is_favorite = ?
        WHERE id = ?
        """,
        (view.name, view.description, config_json, view.is_default, view.is_favorite, view_id),
    )
    db.commit()
    return {"message": "View updated"}


@router.delete("/{view_id}")
async def delete_saved_view(view_id: int):
    """Delete a saved view."""
    db = get_database()

    existing = db.fetchone("SELECT id FROM saved_views WHERE id = ?", (view_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="View not found")

    db.execute("DELETE FROM saved_views WHERE id = ?", (view_id,))
    db.commit()
    return {"message": "View deleted"}


@router.post("/{view_id}/use")
async def mark_view_used(view_id: int):
    """Mark a view as used (updates last_used_at and use_count)."""
    db = get_database()

    existing = db.fetchone("SELECT id FROM saved_views WHERE id = ?", (view_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="View not found")

    db.execute(
        """
        UPDATE saved_views
        SET last_used_at = ?, use_count = use_count + 1
        WHERE id = ?
        """,
        (datetime.utcnow().isoformat(), view_id),
    )
    db.commit()
    return {"message": "View marked as used"}


@router.post("/{view_id}/set-default")
async def set_default_view(view_id: int):
    """Set a view as the default."""
    db = get_database()

    existing = db.fetchone("SELECT id FROM saved_views WHERE id = ?", (view_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="View not found")

    # Unset current default
    db.execute("UPDATE saved_views SET is_default = 0 WHERE is_default = 1")

    # Set new default
    db.execute("UPDATE saved_views SET is_default = 1 WHERE id = ?", (view_id,))
    db.commit()
    return {"message": "View set as default"}


@router.post("/{view_id}/favorite")
async def toggle_view_favorite(view_id: int):
    """Toggle the favorite status of a view."""
    db = get_database()

    existing = db.fetchone("SELECT id, is_favorite FROM saved_views WHERE id = ?", (view_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="View not found")

    new_favorite = not existing["is_favorite"]
    db.execute(
        "UPDATE saved_views SET is_favorite = ? WHERE id = ?",
        (new_favorite, view_id),
    )
    db.commit()
    return {"message": "Favorite toggled", "is_favorite": new_favorite}
