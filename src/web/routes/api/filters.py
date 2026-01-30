"""Saved filters API endpoints."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...dependencies import get_database

router = APIRouter(prefix="/filters")


# Available filter operators
FILTER_OPERATORS = [
    {"value": "equals", "label": "equals"},
    {"value": "not_equals", "label": "does not equal"},
    {"value": "contains", "label": "contains"},
    {"value": "not_contains", "label": "does not contain"},
    {"value": "starts_with", "label": "starts with"},
    {"value": "not_starts_with", "label": "does not start with"},
    {"value": "ends_with", "label": "ends with"},
    {"value": "not_ends_with", "label": "does not end with"},
    {"value": "is_empty", "label": "is empty"},
    {"value": "is_not_empty", "label": "is not empty"},
]

# Available filter fields
FILTER_FIELDS = [
    {"value": "name", "label": "Name"},
    {"value": "arn", "label": "ARN"},
    {"value": "resource_type", "label": "Type"},
    {"value": "region", "label": "Region"},
    {"value": "snapshot_name", "label": "Snapshot"},
    {"value": "config_hash", "label": "Config Hash"},
    {"value": "tag_key", "label": "Tag Key"},
    {"value": "tag_value", "label": "Tag Value"},
]


class FilterCondition(BaseModel):
    """A single filter condition."""

    field: str
    operator: str
    value: Optional[str] = None


class FilterConfig(BaseModel):
    """Filter configuration model - supports both simple and advanced modes."""

    # Simple mode fields (legacy support)
    resource_type: Optional[str] = None
    region: Optional[str] = None
    snapshot: Optional[str] = None
    search: Optional[str] = None
    tags: Optional[dict] = None

    # Advanced mode fields
    logic: Optional[str] = "AND"  # "AND" or "OR"
    conditions: Optional[List[FilterCondition]] = None


class SavedFilter(BaseModel):
    """Saved filter model."""

    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    filter_config: Any  # Accept both FilterConfig and raw dict
    is_favorite: bool = False


class SavedFilterResponse(BaseModel):
    """Saved filter response model."""

    id: int
    name: str
    description: Optional[str]
    filter_config: dict
    is_favorite: bool
    created_at: str
    last_used_at: Optional[str]
    use_count: int


@router.get("/schema")
async def get_filter_schema():
    """Get available filter fields and operators."""
    return {
        "fields": FILTER_FIELDS,
        "operators": FILTER_OPERATORS,
        "logic_options": ["AND", "OR"],
    }


@router.get("")
async def list_saved_filters(favorites_only: bool = False):
    """List saved filters."""
    db = get_database()

    sql = "SELECT * FROM saved_filters WHERE 1=1"
    params: List = []

    if favorites_only:
        sql += " AND is_favorite = 1"

    sql += " ORDER BY is_favorite DESC, last_used_at DESC NULLS LAST, name"

    rows = db.fetchall(sql, tuple(params))

    filters = []
    for row in rows:
        row_dict = dict(row)
        # Parse the JSON filter_config
        if row_dict.get("filter_config"):
            row_dict["filter_config"] = json.loads(row_dict["filter_config"])
        filters.append(row_dict)

    return {"filters": filters}


@router.post("")
async def create_saved_filter(filter_data: SavedFilter):
    """Save a new filter."""
    db = get_database()

    try:
        # Handle both Pydantic model and raw dict
        if hasattr(filter_data.filter_config, "model_dump"):
            config_json = json.dumps(filter_data.filter_config.model_dump())
        else:
            config_json = json.dumps(filter_data.filter_config)

        cursor = db.execute(
            """
            INSERT INTO saved_filters (name, description, filter_config, is_favorite, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                filter_data.name,
                filter_data.description,
                config_json,
                filter_data.is_favorite,
                datetime.utcnow().isoformat(),
            ),
        )
        db.commit()
        return {"id": cursor.lastrowid, "message": "Filter saved"}
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(status_code=400, detail=f"Filter with name '{filter_data.name}' already exists")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{filter_id}")
async def get_saved_filter(filter_id: int):
    """Get a saved filter by ID."""
    db = get_database()
    row = db.fetchone("SELECT * FROM saved_filters WHERE id = ?", (filter_id,))

    if not row:
        raise HTTPException(status_code=404, detail="Filter not found")

    row_dict = dict(row)
    if row_dict.get("filter_config"):
        row_dict["filter_config"] = json.loads(row_dict["filter_config"])
    return row_dict


@router.put("/{filter_id}")
async def update_saved_filter(filter_id: int, filter_data: SavedFilter):
    """Update a saved filter."""
    db = get_database()

    existing = db.fetchone("SELECT id FROM saved_filters WHERE id = ?", (filter_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Filter not found")

    # Handle both Pydantic model and raw dict
    if hasattr(filter_data.filter_config, "model_dump"):
        config_json = json.dumps(filter_data.filter_config.model_dump())
    else:
        config_json = json.dumps(filter_data.filter_config)

    db.execute(
        """
        UPDATE saved_filters
        SET name = ?, description = ?, filter_config = ?, is_favorite = ?
        WHERE id = ?
        """,
        (filter_data.name, filter_data.description, config_json, filter_data.is_favorite, filter_id),
    )
    db.commit()
    return {"message": "Filter updated"}


@router.delete("/{filter_id}")
async def delete_saved_filter(filter_id: int):
    """Delete a saved filter."""
    db = get_database()

    existing = db.fetchone("SELECT id FROM saved_filters WHERE id = ?", (filter_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Filter not found")

    db.execute("DELETE FROM saved_filters WHERE id = ?", (filter_id,))
    db.commit()
    return {"message": "Filter deleted"}


@router.post("/{filter_id}/use")
async def mark_filter_used(filter_id: int):
    """Mark a filter as used (updates last_used_at and use_count)."""
    db = get_database()

    existing = db.fetchone("SELECT id FROM saved_filters WHERE id = ?", (filter_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Filter not found")

    db.execute(
        """
        UPDATE saved_filters
        SET last_used_at = ?, use_count = use_count + 1
        WHERE id = ?
        """,
        (datetime.utcnow().isoformat(), filter_id),
    )
    db.commit()
    return {"message": "Filter marked as used"}


@router.post("/{filter_id}/favorite")
async def toggle_filter_favorite(filter_id: int):
    """Toggle the favorite status of a filter."""
    db = get_database()

    existing = db.fetchone("SELECT id, is_favorite FROM saved_filters WHERE id = ?", (filter_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Filter not found")

    new_favorite = not existing["is_favorite"]
    db.execute(
        "UPDATE saved_filters SET is_favorite = ? WHERE id = ?",
        (new_favorite, filter_id),
    )
    db.commit()
    return {"message": "Favorite toggled", "is_favorite": new_favorite}
