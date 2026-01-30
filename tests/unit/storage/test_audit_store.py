"""Unit tests for AuditStore."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.models.deletion_operation import DeletionOperation, OperationMode, OperationStatus
from src.models.deletion_record import DeletionRecord, DeletionStatus
from src.storage.audit_store import AuditStore
from src.storage.database import Database


@pytest.fixture
def db(tmp_path: Path) -> Database:
    """Create a test database."""
    database = Database(storage_path=tmp_path)
    database.ensure_schema()
    return database


@pytest.fixture
def store(db: Database) -> AuditStore:
    """Create an audit store."""
    return AuditStore(db)


@pytest.fixture
def sample_operation() -> DeletionOperation:
    """Create a sample deletion operation."""
    return DeletionOperation(
        operation_id="op-123",
        baseline_snapshot="baseline-snap",
        timestamp=datetime(2025, 1, 10, 12, 0, 0, tzinfo=timezone.utc),
        aws_profile="default",
        account_id="123456789012",
        mode=OperationMode.DRY_RUN,
        status=OperationStatus.COMPLETED,
        total_resources=10,
        succeeded_count=8,
        failed_count=1,
        skipped_count=1,
        duration_seconds=120.5,
        filters={"resource_type": "s3:bucket"},
    )


@pytest.fixture
def sample_record() -> DeletionRecord:
    """Create a sample deletion record."""
    return DeletionRecord(
        record_id="rec-1",
        operation_id="op-123",
        resource_arn="arn:aws:s3:::test-bucket",
        resource_id="test-bucket",
        resource_type="s3:bucket",
        region="us-east-1",
        timestamp=datetime(2025, 1, 10, 12, 0, 0, tzinfo=timezone.utc),
        status=DeletionStatus.SUCCEEDED,
        tags={"Environment": "test"},
        estimated_monthly_cost=10.50,
    )


class TestAuditStore:
    """Test cases for AuditStore."""

    def test_save_operation(self, store: AuditStore, sample_operation: DeletionOperation) -> None:
        """Test saving a deletion operation."""
        operation_id = store.save_operation(sample_operation)

        assert operation_id == "op-123"

    def test_save_and_load_operation(self, store: AuditStore, sample_operation: DeletionOperation) -> None:
        """Test saving and loading a deletion operation."""
        store.save_operation(sample_operation)

        loaded = store.load_operation("op-123")

        assert loaded is not None
        assert loaded.operation_id == "op-123"
        assert loaded.baseline_snapshot == "baseline-snap"
        assert loaded.account_id == "123456789012"
        assert loaded.mode == OperationMode.DRY_RUN
        assert loaded.status == OperationStatus.COMPLETED

    def test_load_operation_counts(self, store: AuditStore, sample_operation: DeletionOperation) -> None:
        """Test that operation counts are loaded correctly."""
        store.save_operation(sample_operation)

        loaded = store.load_operation("op-123")

        assert loaded.total_resources == 10
        assert loaded.succeeded_count == 8
        assert loaded.failed_count == 1
        assert loaded.skipped_count == 1
        assert loaded.duration_seconds == 120.5

    def test_load_operation_filters(self, store: AuditStore, sample_operation: DeletionOperation) -> None:
        """Test that operation filters are loaded correctly."""
        store.save_operation(sample_operation)

        loaded = store.load_operation("op-123")

        assert loaded.filters == {"resource_type": "s3:bucket"}

    def test_load_nonexistent_operation(self, store: AuditStore) -> None:
        """Test loading an operation that doesn't exist."""
        loaded = store.load_operation("nonexistent")

        assert loaded is None

    def test_save_record(
        self, store: AuditStore, sample_operation: DeletionOperation, sample_record: DeletionRecord
    ) -> None:
        """Test saving a deletion record."""
        store.save_operation(sample_operation)
        record_id = store.save_record(sample_record)

        assert record_id is not None

    def test_load_records(
        self, store: AuditStore, sample_operation: DeletionOperation, sample_record: DeletionRecord
    ) -> None:
        """Test loading records for an operation."""
        store.save_operation(sample_operation)
        store.save_record(sample_record)

        records = store.load_records("op-123")

        assert len(records) == 1
        assert records[0].resource_arn == "arn:aws:s3:::test-bucket"
        assert records[0].status == DeletionStatus.SUCCEEDED

    def test_load_records_with_tags(
        self, store: AuditStore, sample_operation: DeletionOperation, sample_record: DeletionRecord
    ) -> None:
        """Test that record tags are loaded correctly."""
        store.save_operation(sample_operation)
        store.save_record(sample_record)

        records = store.load_records("op-123")

        assert records[0].tags == {"Environment": "test"}

    def test_save_records_batch(self, store: AuditStore, sample_operation: DeletionOperation) -> None:
        """Test batch saving multiple records."""
        store.save_operation(sample_operation)

        records = [
            DeletionRecord(
                record_id=f"rec-{i}",
                operation_id="op-123",
                resource_arn=f"arn:aws:s3:::bucket-{i}",
                resource_id=f"bucket-{i}",
                resource_type="s3:bucket",
                region="us-east-1",
                timestamp=datetime.now(timezone.utc),
                status=DeletionStatus.SUCCEEDED,
            )
            for i in range(5)
        ]

        count = store.save_records_batch(records)

        assert count == 5
        loaded_records = store.load_records("op-123")
        assert len(loaded_records) == 5

    def test_save_records_batch_empty(self, store: AuditStore) -> None:
        """Test batch saving empty list."""
        count = store.save_records_batch([])

        assert count == 0

    def test_update_operation(self, store: AuditStore, sample_operation: DeletionOperation) -> None:
        """Test updating an existing operation."""
        store.save_operation(sample_operation)

        # Update operation
        sample_operation.status = OperationStatus.FAILED
        sample_operation.failed_count = 5
        store.save_operation(sample_operation)

        # Verify update
        loaded = store.load_operation("op-123")
        assert loaded.status == OperationStatus.FAILED
        assert loaded.failed_count == 5

    def test_list_operations_empty(self, store: AuditStore) -> None:
        """Test listing operations when none exist."""
        operations = store.list_operations()

        assert operations == []

    def test_list_operations(self, store: AuditStore) -> None:
        """Test listing multiple operations."""
        op1 = DeletionOperation(
            operation_id="op-1",
            baseline_snapshot="snap1",
            timestamp=datetime(2025, 1, 10, tzinfo=timezone.utc),
            account_id="123456789012",
            mode=OperationMode.DRY_RUN,
            status=OperationStatus.COMPLETED,
            total_resources=5,
        )
        op2 = DeletionOperation(
            operation_id="op-2",
            baseline_snapshot="snap2",
            timestamp=datetime(2025, 1, 11, tzinfo=timezone.utc),
            account_id="123456789012",
            mode=OperationMode.EXECUTE,
            status=OperationStatus.EXECUTING,
            total_resources=10,
        )

        store.save_operation(op1)
        store.save_operation(op2)

        operations = store.list_operations()

        assert len(operations) == 2

    def test_list_operations_by_account(self, store: AuditStore) -> None:
        """Test listing operations filtered by account."""
        op1 = DeletionOperation(
            operation_id="op-1",
            baseline_snapshot="snap1",
            timestamp=datetime.now(timezone.utc),
            account_id="111111111111",
            mode=OperationMode.DRY_RUN,
            status=OperationStatus.COMPLETED,
            total_resources=5,
        )
        op2 = DeletionOperation(
            operation_id="op-2",
            baseline_snapshot="snap2",
            timestamp=datetime.now(timezone.utc),
            account_id="222222222222",
            mode=OperationMode.DRY_RUN,
            status=OperationStatus.COMPLETED,
            total_resources=5,
        )

        store.save_operation(op1)
        store.save_operation(op2)

        account1_ops = store.list_operations(account_id="111111111111")
        account2_ops = store.list_operations(account_id="222222222222")

        assert len(account1_ops) == 1
        assert len(account2_ops) == 1
        assert account1_ops[0].account_id == "111111111111"

    def test_list_operations_with_limit(self, store: AuditStore) -> None:
        """Test listing operations with limit."""
        for i in range(10):
            op = DeletionOperation(
                operation_id=f"op-{i}",
                baseline_snapshot="snap",
                timestamp=datetime.now(timezone.utc),
                account_id="123456789012",
                mode=OperationMode.DRY_RUN,
                status=OperationStatus.COMPLETED,
                total_resources=5,
            )
            store.save_operation(op)

        operations = store.list_operations(limit=5)

        assert len(operations) == 5

    def test_delete_operation(
        self, store: AuditStore, sample_operation: DeletionOperation, sample_record: DeletionRecord
    ) -> None:
        """Test deleting an operation."""
        store.save_operation(sample_operation)
        store.save_record(sample_record)

        result = store.delete_operation("op-123")

        assert result is True
        assert store.load_operation("op-123") is None

    def test_delete_operation_cascades_to_records(
        self, store: AuditStore, sample_operation: DeletionOperation, sample_record: DeletionRecord, db: Database
    ) -> None:
        """Test that deleting operation cascades to records."""
        store.save_operation(sample_operation)
        store.save_record(sample_record)

        # Verify records exist
        records = db.fetchall("SELECT * FROM audit_records WHERE operation_id = ?", ("op-123",))
        assert len(records) == 1

        store.delete_operation("op-123")

        # Verify records were deleted
        records = db.fetchall("SELECT * FROM audit_records WHERE operation_id = ?", ("op-123",))
        assert len(records) == 0

    def test_delete_nonexistent_operation(self, store: AuditStore) -> None:
        """Test deleting an operation that doesn't exist."""
        result = store.delete_operation("nonexistent")

        assert result is False

    def test_get_operation_stats(self, store: AuditStore, sample_operation: DeletionOperation) -> None:
        """Test getting operation statistics."""
        store.save_operation(sample_operation)

        # Add some records
        records = [
            DeletionRecord(
                record_id="rec-1",
                operation_id="op-123",
                resource_arn="arn:aws:s3:::bucket-1",
                resource_id="bucket-1",
                resource_type="s3:bucket",
                region="us-east-1",
                timestamp=datetime.now(timezone.utc),
                status=DeletionStatus.SUCCEEDED,
                estimated_monthly_cost=5.0,
            ),
            DeletionRecord(
                record_id="rec-2",
                operation_id="op-123",
                resource_arn="arn:aws:s3:::bucket-2",
                resource_id="bucket-2",
                resource_type="s3:bucket",
                region="us-east-1",
                timestamp=datetime.now(timezone.utc),
                status=DeletionStatus.SUCCEEDED,
                estimated_monthly_cost=3.0,
            ),
            DeletionRecord(
                record_id="rec-3",
                operation_id="op-123",
                resource_arn="arn:aws:ec2:us-east-1:123:instance/i-1",
                resource_id="i-1",
                resource_type="ec2:instance",
                region="us-east-1",
                timestamp=datetime.now(timezone.utc),
                status=DeletionStatus.FAILED,
                error_code="AccessDenied",
                estimated_monthly_cost=10.0,
            ),
        ]
        store.save_records_batch(records)

        stats = store.get_operation_stats("op-123")

        assert stats["operation_id"] == "op-123"
        assert stats["baseline_snapshot"] == "baseline-snap"
        assert stats["mode"] == "dry-run"
        assert stats["status_breakdown"]["succeeded"] == 2
        assert stats["status_breakdown"]["failed"] == 1
        assert stats["type_breakdown"]["s3:bucket"] == 2
        assert stats["type_breakdown"]["ec2:instance"] == 1
        assert stats["total_estimated_monthly_cost"] == 18.0

    def test_get_operation_stats_nonexistent(self, store: AuditStore) -> None:
        """Test getting stats for nonexistent operation."""
        stats = store.get_operation_stats("nonexistent")

        assert stats == {}

    def test_get_recent_deletions(self, store: AuditStore, sample_operation: DeletionOperation) -> None:
        """Test getting recent deletion records."""
        store.save_operation(sample_operation)

        records = [
            DeletionRecord(
                record_id="rec-1",
                operation_id="op-123",
                resource_arn="arn:aws:s3:::bucket-1",
                resource_id="bucket-1",
                resource_type="s3:bucket",
                region="us-east-1",
                timestamp=datetime.now(timezone.utc),
                status=DeletionStatus.SUCCEEDED,
            ),
            DeletionRecord(
                record_id="rec-2",
                operation_id="op-123",
                resource_arn="arn:aws:ec2:us-west-2:123:instance/i-1",
                resource_id="i-1",
                resource_type="ec2:instance",
                region="us-west-2",
                timestamp=datetime.now(timezone.utc),
                status=DeletionStatus.SUCCEEDED,
            ),
        ]
        store.save_records_batch(records)

        # Filter by region
        deletions = store.get_recent_deletions(region="us-east-1")
        assert len(deletions) == 1
        assert deletions[0]["region"] == "us-east-1"

        # Filter by resource type
        deletions = store.get_recent_deletions(resource_type="ec2")
        assert len(deletions) == 1
        assert "ec2" in deletions[0]["resource_type"]

    def test_record_statuses(self, store: AuditStore, sample_operation: DeletionOperation) -> None:
        """Test various deletion statuses."""
        store.save_operation(sample_operation)

        records = [
            DeletionRecord(
                record_id="rec-1",
                operation_id="op-123",
                resource_arn="arn:aws:s3:::succeeded",
                resource_id="succeeded",
                resource_type="s3:bucket",
                region="us-east-1",
                timestamp=datetime.now(timezone.utc),
                status=DeletionStatus.SUCCEEDED,
            ),
            DeletionRecord(
                record_id="rec-2",
                operation_id="op-123",
                resource_arn="arn:aws:s3:::failed",
                resource_id="failed",
                resource_type="s3:bucket",
                region="us-east-1",
                timestamp=datetime.now(timezone.utc),
                status=DeletionStatus.FAILED,
                error_code="AccessDenied",
                error_message="Access denied",
            ),
            DeletionRecord(
                record_id="rec-3",
                operation_id="op-123",
                resource_arn="arn:aws:s3:::skipped",
                resource_id="skipped",
                resource_type="s3:bucket",
                region="us-east-1",
                timestamp=datetime.now(timezone.utc),
                status=DeletionStatus.SKIPPED,
                protection_reason="Production resource",
            ),
        ]
        store.save_records_batch(records)

        loaded = store.load_records("op-123")

        statuses = {r.resource_arn.split(":")[-1]: r.status for r in loaded}
        assert statuses["succeeded"] == DeletionStatus.SUCCEEDED
        assert statuses["failed"] == DeletionStatus.FAILED
        assert statuses["skipped"] == DeletionStatus.SKIPPED
