"""Cleanup operations API endpoints."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ...dependencies import get_audit_store, get_snapshot_store

router = APIRouter(prefix="/cleanup")


class CleanupPreviewRequest(BaseModel):
    """Request for cleanup preview."""

    baseline_snapshot: str
    resource_types: Optional[List[str]] = None
    regions: Optional[List[str]] = None
    protect_tags: Optional[List[str]] = None  # Format: "key=value"


class CleanupExecuteRequest(BaseModel):
    """Request for cleanup execution."""

    baseline_snapshot: str
    confirmation_token: str  # Must match expected token
    resource_types: Optional[List[str]] = None
    regions: Optional[List[str]] = None
    protect_tags: Optional[List[str]] = None


@router.post("/preview")
async def preview_cleanup(request: CleanupPreviewRequest):
    """Preview cleanup operation (dry-run).

    Note: This endpoint is a placeholder. Full implementation requires
    integrating with the ResourceCleaner and collecting current AWS resources.
    """
    snapshot_store = get_snapshot_store()

    if not snapshot_store.exists(request.baseline_snapshot):
        raise HTTPException(status_code=404, detail=f"Snapshot '{request.baseline_snapshot}' not found")

    # TODO: Implement full preview
    # This would need to:
    # 1. Load the baseline snapshot
    # 2. Collect current AWS resources (requires AWS credentials)
    # 3. Calculate the diff
    # 4. Apply protection rules

    return {
        "status": "preview",
        "message": "Preview endpoint - full implementation pending",
        "baseline_snapshot": request.baseline_snapshot,
        "filters": {
            "resource_types": request.resource_types,
            "regions": request.regions,
            "protect_tags": request.protect_tags,
        },
        "note": "This preview requires AWS credentials to collect current resources. "
        "Use the CLI 'awsinv cleanup preview' for full functionality.",
    }


@router.post("/execute")
async def execute_cleanup(request: CleanupExecuteRequest):
    """Execute cleanup operation.

    Note: This endpoint is a placeholder. Full implementation requires
    AWS credentials and careful safety checks.
    """
    snapshot_store = get_snapshot_store()

    if not snapshot_store.exists(request.baseline_snapshot):
        raise HTTPException(status_code=404, detail=f"Snapshot '{request.baseline_snapshot}' not found")

    # For safety, this is not implemented in the web UI
    # Users should use the CLI for destructive operations
    raise HTTPException(
        status_code=501,
        detail="Cleanup execution is not available in the web UI for safety. "
        "Please use the CLI: awsinv cleanup execute <snapshot> --confirm",
    )


@router.get("/operations")
async def list_operations(
    account_id: Optional[str] = Query(None, description="Filter by account"),
    limit: int = Query(50, le=200),
):
    """List cleanup operations from audit log."""
    audit_store = get_audit_store()
    operations = audit_store.list_operations(account_id=account_id, limit=limit)

    return {
        "count": len(operations),
        "operations": [
            {
                "operation_id": op.operation_id,
                "baseline_snapshot": op.baseline_snapshot,
                "timestamp": op.timestamp.isoformat() if hasattr(op.timestamp, "isoformat") else str(op.timestamp),
                "account_id": op.account_id,
                "mode": op.mode.value if hasattr(op.mode, "value") else str(op.mode),
                "status": op.status.value if hasattr(op.status, "value") else str(op.status),
                "total_resources": op.total_resources,
                "succeeded_count": op.succeeded_count,
                "failed_count": op.failed_count,
                "skipped_count": op.skipped_count,
                "duration_seconds": op.duration_seconds,
            }
            for op in operations
        ],
    }


@router.get("/operations/{operation_id}")
async def get_operation(operation_id: str):
    """Get details of a cleanup operation."""
    audit_store = get_audit_store()
    operation = audit_store.load_operation(operation_id)

    if not operation:
        raise HTTPException(status_code=404, detail="Operation not found")

    return {
        "operation_id": operation.operation_id,
        "baseline_snapshot": operation.baseline_snapshot,
        "timestamp": (
            operation.timestamp.isoformat() if hasattr(operation.timestamp, "isoformat") else str(operation.timestamp)
        ),
        "account_id": operation.account_id,
        "mode": operation.mode.value if hasattr(operation.mode, "value") else str(operation.mode),
        "status": operation.status.value if hasattr(operation.status, "value") else str(operation.status),
        "total_resources": operation.total_resources,
        "succeeded_count": operation.succeeded_count,
        "failed_count": operation.failed_count,
        "skipped_count": operation.skipped_count,
        "duration_seconds": operation.duration_seconds,
        "filters": operation.filters,
    }


@router.get("/operations/{operation_id}/records")
async def get_operation_records(
    operation_id: str,
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, le=500),
):
    """Get deletion records for a cleanup operation."""
    audit_store = get_audit_store()

    # First verify operation exists
    operation = audit_store.load_operation(operation_id)
    if not operation:
        raise HTTPException(status_code=404, detail="Operation not found")

    records = audit_store.load_records(operation_id)

    # Filter by status if specified
    if status:
        records = [r for r in records if str(r.status.value if hasattr(r.status, "value") else r.status) == status]

    # Apply limit
    records = records[:limit]

    return {
        "operation_id": operation_id,
        "count": len(records),
        "records": [
            {
                "record_id": r.record_id,
                "resource_arn": r.resource_arn,
                "resource_id": r.resource_id,
                "resource_type": r.resource_type,
                "region": r.region,
                "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                "error_code": r.error_code,
                "error_message": r.error_message,
                "protection_reason": r.protection_reason,
                "deletion_tier": r.deletion_tier,
            }
            for r in records
        ],
    }
