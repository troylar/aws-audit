"""Chart data API endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from ...dependencies import get_resource_store, get_snapshot_store

router = APIRouter(prefix="/charts")

# Chart.js color palette
CHART_COLORS = [
    "#3B82F6",  # Blue
    "#10B981",  # Green
    "#F59E0B",  # Amber
    "#EF4444",  # Red
    "#8B5CF6",  # Purple
    "#EC4899",  # Pink
    "#06B6D4",  # Cyan
    "#84CC16",  # Lime
    "#F97316",  # Orange
    "#6366F1",  # Indigo
]


@router.get("/resources-by-type")
async def chart_resources_by_type(
    snapshot: Optional[str] = Query(None, description="Limit to specific snapshot"),
    limit: int = Query(10, le=20),
):
    """Get Chart.js data for resources by type."""
    store = get_resource_store()
    stats = store.get_stats(snapshot_name=snapshot, group_by="type")[:limit]

    labels = [s["group_key"] for s in stats]
    data = [s["count"] for s in stats]

    return {
        "labels": labels,
        "datasets": [
            {
                "data": data,
                "backgroundColor": CHART_COLORS[: len(data)],
            }
        ],
    }


@router.get("/resources-by-region")
async def chart_resources_by_region(
    snapshot: Optional[str] = Query(None, description="Limit to specific snapshot"),
):
    """Get Chart.js data for resources by region."""
    store = get_resource_store()
    stats = store.get_stats(snapshot_name=snapshot, group_by="region")

    labels = [s["group_key"] for s in stats]
    data = [s["count"] for s in stats]

    return {
        "labels": labels,
        "datasets": [
            {
                "label": "Resources",
                "data": data,
                "backgroundColor": "#3B82F6",
            }
        ],
    }


@router.get("/resources-by-service")
async def chart_resources_by_service(
    snapshot: Optional[str] = Query(None, description="Limit to specific snapshot"),
    limit: int = Query(10, le=20),
):
    """Get Chart.js data for resources by service."""
    store = get_resource_store()
    stats = store.get_stats(snapshot_name=snapshot, group_by="service")[:limit]

    labels = [s["group_key"] for s in stats]
    data = [s["count"] for s in stats]

    return {
        "labels": labels,
        "datasets": [
            {
                "data": data,
                "backgroundColor": CHART_COLORS[: len(data)],
            }
        ],
    }


@router.get("/snapshot-trend")
async def chart_snapshot_trend():
    """Get Chart.js data for snapshot resource count over time."""
    store = get_snapshot_store()
    snapshots = store.list_all()

    # Sort by created_at
    sorted_snapshots = sorted(snapshots, key=lambda s: s.get("created_at", ""))

    # Take last 10 snapshots for trend
    recent = sorted_snapshots[-10:] if len(sorted_snapshots) > 10 else sorted_snapshots

    labels = [s["name"][:20] for s in recent]  # Truncate long names
    data = [s.get("resource_count", 0) for s in recent]

    return {
        "labels": labels,
        "datasets": [
            {
                "label": "Resource Count",
                "data": data,
                "borderColor": "#3B82F6",
                "backgroundColor": "rgba(59, 130, 246, 0.1)",
                "fill": True,
                "tension": 0.3,
            }
        ],
    }


@router.get("/tag-coverage")
async def chart_tag_coverage(
    snapshot: Optional[str] = Query(None, description="Limit to specific snapshot"),
):
    """Get Chart.js data for tag coverage analysis."""
    resource_store = get_resource_store()

    # Get all resources
    resources = resource_store.search(snapshot_name=snapshot, limit=10000)

    # Count tagged vs untagged
    tagged = 0
    untagged = 0

    for r in resources:
        tags = r.get("tags", {})
        if tags and len(tags) > 0:
            tagged += 1
        else:
            untagged += 1

    return {
        "labels": ["Tagged", "Untagged"],
        "datasets": [
            {
                "data": [tagged, untagged],
                "backgroundColor": ["#10B981", "#EF4444"],
            }
        ],
    }
