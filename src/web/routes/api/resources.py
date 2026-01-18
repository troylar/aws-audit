"""Resource API endpoints."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import unquote

import yaml
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from ...dependencies import get_database, get_resource_store, get_snapshot_store

router = APIRouter(prefix="/resources")


@router.get("")
async def search_resources(
    q: Optional[str] = Query(None, description="Search query (ARN pattern)"),
    type: Optional[str] = Query(None, description="Filter by resource type"),
    region: Optional[str] = Query(None, description="Filter by region"),
    snapshot: Optional[str] = Query(None, description="Limit to specific snapshot"),
    tag_key: Optional[str] = Query(None, description="Filter by tag key"),
    tag_value: Optional[str] = Query(None, description="Filter by tag value"),
    include_tags: bool = Query(False, description="Include tags in response"),
    limit: int = Query(50, le=500),
    offset: int = Query(0, ge=0),
):
    """Search resources across snapshots."""
    store = get_resource_store()

    resources = store.search(
        arn_pattern=q,
        resource_type=type,
        region=region,
        snapshot_name=snapshot,
        tag_key=tag_key,
        tag_value=tag_value,
        limit=limit,
        offset=offset,
    )

    # Optionally include tags for each resource
    if include_tags:
        enriched_resources = []
        for resource in resources:
            r = dict(resource)
            tags = store.get_tags_for_resource(
                resource["arn"],
                snapshot_name=resource.get("snapshot_name"),
            )
            r["tags"] = tags
            enriched_resources.append(r)
        resources = enriched_resources

    return {
        "count": len(resources),
        "limit": limit,
        "offset": offset,
        "resources": resources,
    }


@router.get("/types")
async def get_resource_types(
    snapshot: Optional[str] = Query(None, description="Limit to specific snapshot"),
):
    """Get unique resource types."""
    store = get_resource_store()
    types = store.get_unique_resource_types(snapshot_name=snapshot)
    return {"types": types}


@router.get("/regions")
async def get_regions(
    snapshot: Optional[str] = Query(None, description="Limit to specific snapshot"),
):
    """Get unique regions."""
    store = get_resource_store()
    regions = store.get_unique_regions(snapshot_name=snapshot)
    return {"regions": regions}


@router.get("/tags/keys")
async def get_tag_keys(
    snapshot: Optional[str] = Query(None, description="Limit to specific snapshot"),
):
    """Get unique tag keys."""
    db = get_database()

    if snapshot:
        query = """
            SELECT DISTINCT t.key
            FROM resource_tags t
            JOIN resources r ON t.resource_id = r.id
            JOIN snapshots s ON r.snapshot_id = s.id
            WHERE s.name = ?
            ORDER BY t.key
        """
        rows = db.fetchall(query, (snapshot,))
    else:
        query = """
            SELECT DISTINCT key FROM resource_tags ORDER BY key
        """
        rows = db.fetchall(query)

    return {"keys": [row["key"] for row in rows]}


@router.get("/tags/values")
async def get_tag_values(
    key: str = Query(..., description="Tag key to get values for"),
    snapshot: Optional[str] = Query(None, description="Limit to specific snapshot"),
):
    """Get unique values for a tag key."""
    db = get_database()

    if snapshot:
        query = """
            SELECT DISTINCT t.value
            FROM resource_tags t
            JOIN resources r ON t.resource_id = r.id
            JOIN snapshots s ON r.snapshot_id = s.id
            WHERE t.key = ? AND s.name = ?
            ORDER BY t.value
        """
        rows = db.fetchall(query, (key, snapshot))
    else:
        query = """
            SELECT DISTINCT value FROM resource_tags WHERE key = ? ORDER BY value
        """
        rows = db.fetchall(query, (key,))

    return {"key": key, "values": [row["value"] for row in rows]}


@router.get("/stats")
async def get_stats(
    snapshot: Optional[str] = Query(None, description="Limit to specific snapshot"),
    group_by: str = Query("type", description="Group by: type, region, service"),
):
    """Get resource statistics."""
    store = get_resource_store()
    stats = store.get_stats(snapshot_name=snapshot, group_by=group_by)
    return {"group_by": group_by, "stats": stats}


@router.get("/by-arn/{arn:path}")
async def get_resource_by_arn(arn: str):
    """Get resource details by ARN."""
    # URL decode the ARN
    decoded_arn = unquote(arn)

    store = get_resource_store()
    resources = store.search(arn_pattern=decoded_arn, limit=1)

    if not resources:
        raise HTTPException(status_code=404, detail=f"Resource not found: {decoded_arn}")

    return resources[0]


@router.get("/history/{arn:path}")
async def get_resource_history(arn: str):
    """Get resource history across snapshots."""
    decoded_arn = unquote(arn)

    store = get_resource_store()
    history = store.get_history(decoded_arn)

    if not history:
        raise HTTPException(status_code=404, detail=f"No history found for: {decoded_arn}")

    return {"arn": decoded_arn, "snapshots": history}


@router.get("/diff")
async def compare_snapshots(
    snapshot1: str = Query(..., description="First snapshot name"),
    snapshot2: str = Query(..., description="Second snapshot name"),
    type: Optional[str] = Query(None, description="Filter by resource type"),
):
    """Compare resources between two snapshots."""
    snapshot_store = get_snapshot_store()

    # Validate snapshots exist
    if not snapshot_store.exists(snapshot1):
        raise HTTPException(status_code=404, detail=f"Snapshot '{snapshot1}' not found")
    if not snapshot_store.exists(snapshot2):
        raise HTTPException(status_code=404, detail=f"Snapshot '{snapshot2}' not found")

    resource_store = get_resource_store()
    diff = resource_store.compare_snapshots(snapshot1, snapshot2)

    # Filter by type if specified
    if type:
        diff["added"] = [r for r in diff["added"] if r.get("resource_type") == type]
        diff["removed"] = [r for r in diff["removed"] if r.get("resource_type") == type]
        diff["modified"] = [r for r in diff["modified"] if r.get("resource_type") == type]

    return diff


@router.get("/export/csv")
async def export_resources_csv(
    q: Optional[str] = Query(None, description="Search query (ARN pattern)"),
    type: Optional[str] = Query(None, description="Filter by resource type"),
    region: Optional[str] = Query(None, description="Filter by region"),
    snapshot: Optional[str] = Query(None, description="Limit to specific snapshot"),
    tag_key: Optional[str] = Query(None, description="Filter by tag key"),
    tag_value: Optional[str] = Query(None, description="Filter by tag value"),
    columns: Optional[str] = Query(None, description="Comma-separated column names to include"),
    sort_by: Optional[str] = Query(None, description="Column to sort by"),
    sort_order: str = Query("asc", description="Sort order: asc or desc"),
):
    """Export resources to CSV file."""
    store = get_resource_store()

    # Define base columns
    base_columns = ["name", "arn", "resource_type", "region", "snapshot_name", "tags", "created_at", "config_hash"]

    # Parse requested columns
    requested_columns = [c.strip() for c in columns.split(",")] if columns else base_columns

    # Check if we need tags (either "tags" column or any "tag:KEY" column)
    include_tags = any(c == "tags" or c.startswith("tag:") for c in requested_columns)

    # Get all matching resources (no limit for export)
    resources = store.search(
        arn_pattern=q,
        resource_type=type,
        region=region,
        snapshot_name=snapshot,
        tag_key=tag_key,
        tag_value=tag_value,
        limit=10000,  # Reasonable limit for export
        offset=0,
    )

    if not resources:
        raise HTTPException(status_code=404, detail="No resources found matching criteria")

    # Enrich resources with tags if needed
    enriched_resources = []
    for resource in resources:
        r = dict(resource)
        if include_tags:
            tags = store.get_tags_for_resource(
                resource["arn"],
                snapshot_name=resource.get("snapshot_name"),
            )
            # "tags" column: all tags as string
            r["tags"] = "; ".join(f"{k}={v}" for k, v in tags.items()) if tags else ""
            # Individual tag columns (tag:KEY)
            for col in requested_columns:
                if col.startswith("tag:"):
                    tag_key_name = col[4:]  # Remove "tag:" prefix
                    r[col] = tags.get(tag_key_name, "")
        enriched_resources.append(r)
    resources = enriched_resources

    # Filter columns to only those requested (allow tag:KEY columns)
    selected_columns = [c for c in requested_columns if c in base_columns or c.startswith("tag:")]
    if not selected_columns:
        selected_columns = base_columns

    # Sort if requested
    if sort_by and (sort_by in base_columns or sort_by.startswith("tag:")):
        reverse = sort_order.lower() == "desc"
        resources = sorted(
            resources,
            key=lambda r: (r.get(sort_by) or "") if isinstance(r.get(sort_by), str) else r.get(sort_by, 0),
            reverse=reverse,
        )

    # Generate CSV
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=selected_columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(resources)

    # Create response
    csv_content = output.getvalue()
    output.close()

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"resources_export_{timestamp}.csv"

    return StreamingResponse(
        iter([csv_content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/yaml")
async def export_resources_yaml(
    q: Optional[str] = Query(None, description="Search query (ARN pattern)"),
    type: Optional[str] = Query(None, description="Filter by resource type (comma-separated for multiple)"),
    region: Optional[str] = Query(None, description="Filter by region (comma-separated for multiple)"),
    snapshot: Optional[str] = Query(None, description="Limit to specific snapshot"),
    tag_key: Optional[str] = Query(None, description="Filter by tag key"),
    tag_value: Optional[str] = Query(None, description="Filter by tag value"),
    include_config: bool = Query(True, description="Include raw configuration"),
    include_tags: bool = Query(True, description="Include resource tags"),
):
    """Export resources to YAML file with all properties."""
    store = get_resource_store()
    db = get_database()

    # Parse comma-separated types and regions
    types_list = [t.strip() for t in type.split(",")] if type else []
    regions_list = [r.strip() for r in region.split(",")] if region else []

    # For single value, use API filter; for multiple, we'll post-filter
    api_type = types_list[0] if len(types_list) == 1 else None
    api_region = regions_list[0] if len(regions_list) == 1 else None

    # Get all matching resources
    resources = store.search(
        arn_pattern=q,
        resource_type=api_type,
        region=api_region,
        snapshot_name=snapshot,
        tag_key=tag_key,
        tag_value=tag_value,
        limit=10000,
        offset=0,
    )

    # Post-filter for multiple types/regions
    if len(types_list) > 1:
        resources = [r for r in resources if r.get("resource_type") in types_list]
    if len(regions_list) > 1:
        resources = [r for r in resources if r.get("region") in regions_list]

    if not resources:
        raise HTTPException(status_code=404, detail="No resources found matching criteria")

    # Enrich resources with full data
    enriched_resources: List[Dict[str, Any]] = []

    for resource in resources:
        enriched = dict(resource)

        # Get tags if requested
        if include_tags:
            tags = store.get_tags_for_resource(
                resource["arn"],
                snapshot_name=resource.get("snapshot_name"),
            )
            enriched["tags"] = tags

        # Get raw config if requested
        if include_config:
            # Fetch raw_config from database
            row = db.fetchone(
                """
                SELECT r.raw_config
                FROM resources r
                JOIN snapshots s ON r.snapshot_id = s.id
                WHERE r.arn = ? AND s.name = ?
                """,
                (resource["arn"], resource.get("snapshot_name")),
            )
            if row and row["raw_config"]:
                try:
                    enriched["config"] = json.loads(row["raw_config"])
                except json.JSONDecodeError:
                    enriched["config"] = row["raw_config"]

        enriched_resources.append(enriched)

    # Generate YAML
    yaml_content = yaml.dump(
        {"resources": enriched_resources, "count": len(enriched_resources)},
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"resources_export_{timestamp}.yaml"

    return StreamingResponse(
        iter([yaml_content]),
        media_type="application/x-yaml",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/export/yaml")
async def export_resources_yaml_by_arns(
    request_body: Dict[str, Any],
    include_config: bool = Query(True, description="Include raw configuration"),
    include_tags: bool = Query(True, description="Include resource tags"),
):
    """Export specific resources by ARN to YAML file with all properties.

    Request body should contain:
    - arns: List of ARN strings to export
    - snapshot: Optional snapshot name to scope the lookup
    """
    db = get_database()
    store = get_resource_store()

    arns = request_body.get("arns", [])
    snapshot_name = request_body.get("snapshot")

    if not arns:
        raise HTTPException(status_code=400, detail="No ARNs provided")

    if len(arns) > 10000:
        raise HTTPException(status_code=400, detail="Too many ARNs (max 10000)")

    enriched_resources: List[Dict[str, Any]] = []

    for arn in arns:
        # Build query for this ARN
        if snapshot_name:
            row = db.fetchone(
                """
                SELECT r.*, s.name as snapshot_name, s.created_at as snapshot_created_at,
                       s.account_id
                FROM resources r
                JOIN snapshots s ON r.snapshot_id = s.id
                WHERE r.arn = ? AND s.name = ?
                """,
                (arn, snapshot_name),
            )
        else:
            # Get most recent snapshot for this ARN
            row = db.fetchone(
                """
                SELECT r.*, s.name as snapshot_name, s.created_at as snapshot_created_at,
                       s.account_id
                FROM resources r
                JOIN snapshots s ON r.snapshot_id = s.id
                WHERE r.arn = ?
                ORDER BY s.created_at DESC
                LIMIT 1
                """,
                (arn,),
            )

        if not row:
            continue

        enriched = dict(row)

        # Get tags if requested
        if include_tags:
            tags = store.get_tags_for_resource(arn, snapshot_name=enriched.get("snapshot_name"))
            enriched["tags"] = tags

        # Parse raw config if requested
        if include_config and enriched.get("raw_config"):
            try:
                enriched["config"] = json.loads(enriched["raw_config"])
            except json.JSONDecodeError:
                enriched["config"] = enriched["raw_config"]

        # Remove internal fields
        enriched.pop("raw_config", None)
        enriched.pop("id", None)
        enriched.pop("snapshot_id", None)

        enriched_resources.append(enriched)

    if not enriched_resources:
        raise HTTPException(status_code=404, detail="No resources found for provided ARNs")

    # Generate YAML
    yaml_content = yaml.dump(
        {"resources": enriched_resources, "count": len(enriched_resources)},
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"resources_export_{timestamp}.yaml"

    return StreamingResponse(
        iter([yaml_content]),
        media_type="application/x-yaml",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
