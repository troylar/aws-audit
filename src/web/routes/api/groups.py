"""Resource groups API endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator

from ...dependencies import get_group_store

router = APIRouter(prefix="/groups")


class GroupMemberRequest(BaseModel):
    """Request model for adding a group member."""

    resource_name: str
    resource_type: str
    original_arn: Optional[str] = None


class AddMembersFromArnsRequest(BaseModel):
    """Request model for adding members from ARNs."""

    arns: List[Dict[str, str]]  # List of {"arn": "...", "resource_type": "..."}


class CreateGroupRequest(BaseModel):
    """Request model for creating a group."""

    name: str
    description: Optional[str] = ""
    from_snapshot: Optional[str] = None
    type_filter: Optional[str] = None
    region_filter: Optional[str] = None

    @field_validator("from_snapshot", "type_filter", "region_filter", mode="before")
    @classmethod
    def empty_string_to_none(cls, v):
        """Convert empty strings to None for optional fields."""
        if v == "":
            return None
        return v


class GroupResponse(BaseModel):
    """Response model for a group."""

    id: int
    name: str
    description: str
    source_snapshot: Optional[str]
    resource_count: int
    is_favorite: bool
    created_at: str
    last_updated: str


class GroupCompareResponse(BaseModel):
    """Response model for group comparison."""

    group_name: str
    snapshot_name: str
    total_in_group: int
    total_in_snapshot: int
    matched: int
    missing_from_snapshot: int
    not_in_group: int
    resources: Dict[str, List[Any]]


@router.get("")
async def list_groups(
    favorites_only: bool = Query(False, description="Only show favorites"),
):
    """List all resource groups."""
    store = get_group_store()
    groups = store.list_all()
    return {"groups": groups, "count": len(groups)}


@router.post("")
async def create_group(request: CreateGroupRequest):
    """Create a new resource group.

    If from_snapshot is provided, the group will be populated with resources
    from that snapshot. Otherwise, an empty group is created.
    """
    store = get_group_store()

    if store.exists(request.name):
        raise HTTPException(status_code=400, detail=f"Group '{request.name}' already exists")

    try:
        if request.from_snapshot:
            count = store.create_from_snapshot(
                group_name=request.name,
                snapshot_name=request.from_snapshot,
                description=request.description or "",
                type_filter=request.type_filter,
                region_filter=request.region_filter,
            )
            return {
                "message": f"Group '{request.name}' created with {count} resources",
                "name": request.name,
                "resource_count": count,
            }
        else:
            from ....models.group import ResourceGroup

            group = ResourceGroup(
                name=request.name,
                description=request.description or "",
            )
            group_id = store.save(group)
            return {
                "message": f"Empty group '{request.name}' created",
                "name": request.name,
                "id": group_id,
                "resource_count": 0,
            }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{name}")
async def get_group(name: str):
    """Get group details."""
    store = get_group_store()
    group = store.load(name)

    if not group:
        raise HTTPException(status_code=404, detail=f"Group '{name}' not found")

    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "source_snapshot": group.source_snapshot,
        "resource_count": group.resource_count,
        "is_favorite": group.is_favorite,
        "created_at": group.created_at.isoformat() if group.created_at else None,
        "last_updated": group.last_updated.isoformat() if group.last_updated else None,
    }


@router.delete("/{name}")
async def delete_group(name: str):
    """Delete a resource group."""
    store = get_group_store()

    if not store.exists(name):
        raise HTTPException(status_code=404, detail=f"Group '{name}' not found")

    store.delete(name)
    return {"message": f"Group '{name}' deleted"}


@router.post("/{name}/favorite")
async def toggle_group_favorite(name: str):
    """Toggle the favorite status of a group."""
    store = get_group_store()

    new_favorite = store.toggle_favorite(name)
    if new_favorite is None:
        raise HTTPException(status_code=404, detail=f"Group '{name}' not found")

    return {"message": "Favorite toggled", "is_favorite": new_favorite}


# Members endpoints


@router.get("/{name}/members")
async def get_group_members(
    name: str,
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
):
    """Get members of a group with pagination."""
    store = get_group_store()

    if not store.exists(name):
        raise HTTPException(status_code=404, detail=f"Group '{name}' not found")

    members = store.get_members(name, limit=limit, offset=offset)

    return {
        "members": [
            {
                "resource_name": m.resource_name,
                "resource_type": m.resource_type,
                "original_arn": m.original_arn,
            }
            for m in members
        ],
        "count": len(members),
        "limit": limit,
        "offset": offset,
    }


@router.post("/{name}/members")
async def add_group_members(name: str, request: AddMembersFromArnsRequest):
    """Add members to a group from ARNs.

    Each item in 'arns' should have 'arn' and 'resource_type' keys.
    The resource name will be extracted from the ARN.
    """
    store = get_group_store()

    if not store.exists(name):
        raise HTTPException(status_code=404, detail=f"Group '{name}' not found")

    try:
        added = store.add_members_from_arns(name, request.arns)
        return {"message": f"Added {added} members to group '{name}'", "added": added}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{name}/members")
async def remove_group_member(
    name: str,
    resource_name: str = Query(..., description="Resource name to remove"),
    resource_type: str = Query(..., description="Resource type"),
):
    """Remove a member from a group."""
    store = get_group_store()

    if not store.exists(name):
        raise HTTPException(status_code=404, detail=f"Group '{name}' not found")

    removed = store.remove_member(name, resource_name, resource_type)

    if removed:
        return {"message": f"Removed '{resource_name}' from group '{name}'"}
    else:
        return {"message": "Member not found in group", "removed": False}


# Comparison endpoints


@router.get("/{name}/compare/{snapshot}")
async def compare_group_to_snapshot(name: str, snapshot: str):
    """Compare a snapshot against a group.

    Returns resources that are:
    - matched: in both group and snapshot
    - missing: in group but not in snapshot
    - extra: in snapshot but not in group
    """
    store = get_group_store()

    try:
        result = store.compare_snapshot(name, snapshot)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{name}/resources/in")
async def get_resources_in_group(
    name: str,
    snapshot: str = Query(..., description="Snapshot name"),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
):
    """Get resources from a snapshot that ARE in the group."""
    store = get_group_store()

    try:
        resources = store.get_resources_in_group(name, snapshot, limit=limit, offset=offset)
        return {
            "resources": resources,
            "count": len(resources),
            "limit": limit,
            "offset": offset,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{name}/resources/not-in")
async def get_resources_not_in_group(
    name: str,
    snapshot: str = Query(..., description="Snapshot name"),
    limit: int = Query(100, le=1000),
    offset: int = Query(0, ge=0),
):
    """Get resources from a snapshot that are NOT in the group."""
    store = get_group_store()

    try:
        resources = store.get_resources_not_in_group(name, snapshot, limit=limit, offset=offset)
        return {
            "resources": resources,
            "count": len(resources),
            "limit": limit,
            "offset": offset,
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
