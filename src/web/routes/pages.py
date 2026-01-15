"""HTML page routes for the web UI."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..dependencies import get_audit_store, get_group_store, get_resource_store, get_snapshot_store

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render the main dashboard page."""
    templates = request.app.state.templates

    # Get dashboard data
    snapshot_store = get_snapshot_store()
    resource_store = get_resource_store()

    snapshots = snapshot_store.list_all()
    total_snapshots = len(snapshots)
    total_resources = snapshot_store.get_resource_count()
    active_snapshot = snapshot_store.get_active()

    # Get stats for charts
    stats_by_type = resource_store.get_stats(group_by="type")[:10]
    stats_by_region = resource_store.get_stats(group_by="region")

    return templates.TemplateResponse(
        "pages/dashboard.html",
        {
            "request": request,
            "total_snapshots": total_snapshots,
            "total_resources": total_resources,
            "active_snapshot": active_snapshot,
            "recent_snapshots": snapshots[:5],
            "stats_by_type": stats_by_type,
            "stats_by_region": stats_by_region,
        },
    )


@router.get("/snapshots", response_class=HTMLResponse)
async def snapshots_list(request: Request):
    """Render the snapshots list page."""
    templates = request.app.state.templates
    snapshot_store = get_snapshot_store()

    snapshots = snapshot_store.list_all()
    active_snapshot = snapshot_store.get_active()

    return templates.TemplateResponse(
        "pages/snapshots.html",
        {
            "request": request,
            "snapshots": snapshots,
            "active_snapshot": active_snapshot,
        },
    )


@router.get("/snapshots/{name}", response_class=HTMLResponse)
async def snapshot_detail(request: Request, name: str):
    """Render snapshot detail page."""
    templates = request.app.state.templates
    snapshot_store = get_snapshot_store()
    resource_store = get_resource_store()

    snapshot = snapshot_store.load(name)
    if not snapshot:
        return templates.TemplateResponse(
            "pages/error.html",
            {"request": request, "error": f"Snapshot '{name}' not found"},
            status_code=404,
        )

    # Get stats for this snapshot
    stats_by_type = resource_store.get_stats(snapshot_name=name, group_by="type")
    stats_by_region = resource_store.get_stats(snapshot_name=name, group_by="region")

    return templates.TemplateResponse(
        "pages/snapshot_detail.html",
        {
            "request": request,
            "snapshot": snapshot,
            "stats_by_type": stats_by_type,
            "stats_by_region": stats_by_region,
        },
    )


@router.get("/resources", response_class=HTMLResponse)
async def resources_list(request: Request):
    """Render the resource explorer page."""
    templates = request.app.state.templates
    resource_store = get_resource_store()
    snapshot_store = get_snapshot_store()

    # Get filter options
    resource_types = resource_store.get_unique_resource_types()
    regions = resource_store.get_unique_regions()
    snapshots = snapshot_store.list_all()

    return templates.TemplateResponse(
        "pages/resources.html",
        {
            "request": request,
            "resource_types": resource_types,
            "regions": regions,
            "snapshots": snapshots,
        },
    )


@router.get("/diff", response_class=HTMLResponse)
async def diff_page(request: Request):
    """Render the diff viewer page."""
    templates = request.app.state.templates
    snapshot_store = get_snapshot_store()

    snapshots = snapshot_store.list_all()

    return templates.TemplateResponse(
        "pages/diff.html",
        {
            "request": request,
            "snapshots": snapshots,
        },
    )


@router.get("/queries", response_class=HTMLResponse)
async def queries_page(request: Request):
    """Render the SQL query editor page."""
    templates = request.app.state.templates

    return templates.TemplateResponse(
        "pages/queries.html",
        {
            "request": request,
        },
    )


@router.get("/cleanup", response_class=HTMLResponse)
async def cleanup_page(request: Request):
    """Render the cleanup operations page."""
    templates = request.app.state.templates
    snapshot_store = get_snapshot_store()

    snapshots = snapshot_store.list_all()

    return templates.TemplateResponse(
        "pages/cleanup.html",
        {
            "request": request,
            "snapshots": snapshots,
        },
    )


@router.get("/audit", response_class=HTMLResponse)
async def audit_logs_page(request: Request):
    """Render the audit logs page."""
    templates = request.app.state.templates
    audit_store = get_audit_store()

    operations = audit_store.list_operations(limit=50)

    return templates.TemplateResponse(
        "pages/audit_logs.html",
        {
            "request": request,
            "operations": operations,
        },
    )


@router.get("/groups", response_class=HTMLResponse)
async def groups_page(request: Request):
    """Render the resource groups page."""
    templates = request.app.state.templates
    group_store = get_group_store()
    snapshot_store = get_snapshot_store()

    groups = group_store.list_all()
    snapshots = snapshot_store.list_all()

    return templates.TemplateResponse(
        "pages/groups.html",
        {
            "request": request,
            "groups": groups,
            "snapshots": snapshots,
        },
    )
