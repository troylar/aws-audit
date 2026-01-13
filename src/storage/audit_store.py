"""Audit storage operations for SQLite backend."""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..models.deletion_operation import DeletionOperation, OperationMode, OperationStatus
from ..models.deletion_record import DeletionRecord, DeletionStatus
from .database import Database, json_deserialize, json_serialize

logger = logging.getLogger(__name__)


class AuditStore:
    """CRUD operations for audit logs in SQLite database."""

    def __init__(self, db: Database):
        """Initialize audit store.

        Args:
            db: Database connection manager
        """
        self.db = db

    def save_operation(self, operation: DeletionOperation) -> str:
        """Save or update deletion operation.

        Args:
            operation: DeletionOperation to save

        Returns:
            Operation ID
        """
        with self.db.transaction() as cursor:
            # Check if operation exists
            existing = self.db.fetchone(
                "SELECT operation_id FROM audit_operations WHERE operation_id = ?",
                (operation.operation_id,),
            )

            if existing:
                # Update existing
                cursor.execute(
                    """
                    UPDATE audit_operations SET
                        status = ?,
                        succeeded_count = ?,
                        failed_count = ?,
                        skipped_count = ?,
                        duration_seconds = ?
                    WHERE operation_id = ?
                    """,
                    (
                        operation.status.value,
                        operation.succeeded_count,
                        operation.failed_count,
                        operation.skipped_count,
                        operation.duration_seconds,
                        operation.operation_id,
                    ),
                )
                logger.debug(f"Updated audit operation '{operation.operation_id}'")
            else:
                # Insert new
                cursor.execute(
                    """
                    INSERT INTO audit_operations (
                        operation_id, baseline_snapshot, timestamp, aws_profile,
                        account_id, mode, status, total_resources, succeeded_count,
                        failed_count, skipped_count, duration_seconds, filters
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        operation.operation_id,
                        operation.baseline_snapshot,
                        operation.timestamp.isoformat(),
                        operation.aws_profile,
                        operation.account_id,
                        operation.mode.value,
                        operation.status.value,
                        operation.total_resources,
                        operation.succeeded_count,
                        operation.failed_count,
                        operation.skipped_count,
                        operation.duration_seconds,
                        json_serialize(operation.filters),
                    ),
                )
                logger.debug(f"Saved audit operation '{operation.operation_id}'")

        return operation.operation_id

    def save_record(self, record: DeletionRecord) -> str:
        """Save deletion record.

        Args:
            record: DeletionRecord to save

        Returns:
            Record ID
        """
        with self.db.transaction() as cursor:
            cursor.execute(
                """
                INSERT INTO audit_records (
                    operation_id, resource_arn, resource_id, resource_type,
                    region, status, error_code, error_message, protection_reason,
                    deletion_tier, tags, estimated_monthly_cost
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.operation_id,
                    record.resource_arn,
                    record.resource_id,
                    record.resource_type,
                    record.region,
                    record.status.value,
                    record.error_code,
                    record.error_message,
                    record.protection_reason,
                    record.deletion_tier,
                    json_serialize(record.tags),
                    record.estimated_monthly_cost,
                ),
            )

        logger.debug(f"Saved audit record for '{record.resource_arn}'")
        return record.record_id

    def save_records_batch(self, records: List[DeletionRecord]) -> int:
        """Save multiple deletion records efficiently.

        Args:
            records: List of DeletionRecord objects

        Returns:
            Number of records saved
        """
        if not records:
            return 0

        with self.db.transaction() as cursor:
            data = [
                (
                    r.operation_id,
                    r.resource_arn,
                    r.resource_id,
                    r.resource_type,
                    r.region,
                    r.status.value,
                    r.error_code,
                    r.error_message,
                    r.protection_reason,
                    r.deletion_tier,
                    json_serialize(r.tags),
                    r.estimated_monthly_cost,
                )
                for r in records
            ]
            cursor.executemany(
                """
                INSERT INTO audit_records (
                    operation_id, resource_arn, resource_id, resource_type,
                    region, status, error_code, error_message, protection_reason,
                    deletion_tier, tags, estimated_monthly_cost
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                data,
            )

        logger.debug(f"Saved {len(records)} audit records")
        return len(records)

    def load_operation(self, operation_id: str) -> Optional[DeletionOperation]:
        """Load deletion operation by ID.

        Args:
            operation_id: Operation ID

        Returns:
            DeletionOperation or None if not found
        """
        row = self.db.fetchone(
            "SELECT * FROM audit_operations WHERE operation_id = ?",
            (operation_id,),
        )
        if not row:
            return None

        return self._row_to_operation(row)

    def _row_to_operation(self, row: Dict[str, Any]) -> DeletionOperation:
        """Convert database row to DeletionOperation.

        Args:
            row: Database row dict

        Returns:
            DeletionOperation object
        """
        timestamp = datetime.fromisoformat(row["timestamp"])
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        return DeletionOperation(
            operation_id=row["operation_id"],
            baseline_snapshot=row["baseline_snapshot"],
            timestamp=timestamp,
            aws_profile=row["aws_profile"],
            account_id=row["account_id"],
            mode=OperationMode(row["mode"]),
            status=OperationStatus(row["status"]),
            total_resources=row["total_resources"],
            succeeded_count=row["succeeded_count"] or 0,
            failed_count=row["failed_count"] or 0,
            skipped_count=row["skipped_count"] or 0,
            duration_seconds=row["duration_seconds"],
            filters=json_deserialize(row["filters"]),
        )

    def load_records(self, operation_id: str) -> List[DeletionRecord]:
        """Load all records for an operation.

        Args:
            operation_id: Operation ID

        Returns:
            List of DeletionRecord objects
        """
        rows = self.db.fetchall(
            "SELECT * FROM audit_records WHERE operation_id = ? ORDER BY id",
            (operation_id,),
        )
        return [self._row_to_record(row) for row in rows]

    def _row_to_record(self, row: Dict[str, Any]) -> DeletionRecord:
        """Convert database row to DeletionRecord.

        Args:
            row: Database row dict

        Returns:
            DeletionRecord object
        """
        return DeletionRecord(
            record_id=str(row["id"]),
            operation_id=row["operation_id"],
            resource_arn=row["resource_arn"],
            resource_id=row["resource_id"] or "",
            resource_type=row["resource_type"],
            region=row["region"],
            timestamp=datetime.now(timezone.utc),  # Not stored in DB, use current time
            status=DeletionStatus(row["status"]),
            error_code=row["error_code"],
            error_message=row["error_message"],
            protection_reason=row["protection_reason"],
            deletion_tier=row["deletion_tier"],
            tags=json_deserialize(row["tags"]),
            estimated_monthly_cost=row["estimated_monthly_cost"],
        )

    def list_operations(
        self,
        account_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[DeletionOperation]:
        """List audit operations.

        Args:
            account_id: Filter by account ID (optional)
            limit: Maximum results

        Returns:
            List of DeletionOperation objects
        """
        if account_id:
            rows = self.db.fetchall(
                "SELECT * FROM audit_operations WHERE account_id = ? ORDER BY timestamp DESC LIMIT ?",
                (account_id, limit),
            )
        else:
            rows = self.db.fetchall(
                "SELECT * FROM audit_operations ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            )

        return [self._row_to_operation(row) for row in rows]

    def delete_operation(self, operation_id: str) -> bool:
        """Delete operation and all its records.

        Args:
            operation_id: Operation ID

        Returns:
            True if deleted, False if not found
        """
        with self.db.transaction() as cursor:
            # Records are deleted by CASCADE
            cursor.execute(
                "DELETE FROM audit_operations WHERE operation_id = ?",
                (operation_id,),
            )
            deleted = cursor.rowcount > 0

        if deleted:
            logger.debug(f"Deleted audit operation '{operation_id}'")
        return deleted

    def get_operation_stats(self, operation_id: str) -> Dict[str, Any]:
        """Get statistics for an operation.

        Args:
            operation_id: Operation ID

        Returns:
            Dictionary with statistics
        """
        operation = self.load_operation(operation_id)
        if not operation:
            return {}

        # Get record counts by status
        status_counts = self.db.fetchall(
            """
            SELECT status, COUNT(*) as count
            FROM audit_records
            WHERE operation_id = ?
            GROUP BY status
            """,
            (operation_id,),
        )

        # Get counts by resource type
        type_counts = self.db.fetchall(
            """
            SELECT resource_type, COUNT(*) as count
            FROM audit_records
            WHERE operation_id = ?
            GROUP BY resource_type
            ORDER BY count DESC
            """,
            (operation_id,),
        )

        # Get total estimated cost
        cost_row = self.db.fetchone(
            """
            SELECT SUM(estimated_monthly_cost) as total_cost
            FROM audit_records
            WHERE operation_id = ?
            """,
            (operation_id,),
        )

        return {
            "operation_id": operation_id,
            "baseline_snapshot": operation.baseline_snapshot,
            "mode": operation.mode.value,
            "status": operation.status.value,
            "total_resources": operation.total_resources,
            "succeeded_count": operation.succeeded_count,
            "failed_count": operation.failed_count,
            "skipped_count": operation.skipped_count,
            "duration_seconds": operation.duration_seconds,
            "status_breakdown": {row["status"]: row["count"] for row in status_counts},
            "type_breakdown": {row["resource_type"]: row["count"] for row in type_counts},
            "total_estimated_monthly_cost": cost_row["total_cost"] if cost_row else 0,
        }

    def get_recent_deletions(
        self,
        resource_arn: Optional[str] = None,
        resource_type: Optional[str] = None,
        region: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get recent deletion records with filters.

        Args:
            resource_arn: Filter by ARN pattern (optional)
            resource_type: Filter by resource type (optional)
            region: Filter by region (optional)
            limit: Maximum results

        Returns:
            List of deletion records with operation info
        """
        conditions = []
        params: List[Any] = []

        if resource_arn:
            conditions.append("r.resource_arn LIKE ?")
            params.append(f"%{resource_arn}%")

        if resource_type:
            conditions.append("r.resource_type LIKE ?")
            params.append(f"%{resource_type}%")

        if region:
            conditions.append("r.region = ?")
            params.append(region)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)

        rows = self.db.fetchall(
            f"""
            SELECT r.*, o.timestamp as operation_timestamp, o.mode, o.baseline_snapshot
            FROM audit_records r
            JOIN audit_operations o ON r.operation_id = o.operation_id
            WHERE {where_clause}
            ORDER BY o.timestamp DESC
            LIMIT ?
            """,
            tuple(params),
        )

        return [dict(row) for row in rows]
