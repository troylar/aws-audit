"""Integration tests for restore workflow.

End-to-end tests for resource cleanup/restoration functionality.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from src.models.deletion_operation import OperationMode, OperationStatus
from src.restore.audit import AuditStorage
from src.restore.cleaner import ResourceCleaner
from src.restore.safety import SafetyChecker
from src.snapshot.storage import SnapshotStorage


class TestRestoreWorkflowIntegration:
    """Integration tests for restore workflow (US1 - Preview)."""

    @pytest.fixture
    def temp_storage_dir(self, tmp_path: Path) -> Path:
        """Create temporary storage directory."""
        storage_dir = tmp_path / ".snapshots"
        storage_dir.mkdir(parents=True)
        return storage_dir

    @pytest.fixture
    def snapshot_storage(self, temp_storage_dir: Path) -> SnapshotStorage:
        """Create snapshot storage with test data."""
        from src.models.resource import Resource
        from src.models.snapshot import Snapshot

        storage = SnapshotStorage(storage_dir=str(temp_storage_dir))

        # Create baseline snapshot with Resource objects
        resources = [
            Resource(
                arn="arn:aws:ec2:us-east-1:123456789012:vpc/vpc-baseline",
                resource_type="AWS::EC2::VPC",
                name="vpc-baseline",
                region="us-east-1",
                config_hash="baseline_config_hash",
                tags={},
            )
        ]

        baseline_snapshot = Snapshot(
            name="baseline-test",
            created_at=datetime(2025, 11, 1, 10, 0, 0),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=resources,
            resource_count=1,
        )

        # Save baseline snapshot using storage
        storage.save_snapshot(baseline_snapshot)

        return storage

    @pytest.fixture
    def audit_storage(self, temp_storage_dir: Path) -> AuditStorage:
        """Create audit storage."""
        return AuditStorage(storage_dir=str(temp_storage_dir / "audit-logs"))

    @pytest.fixture
    def safety_checker(self) -> SafetyChecker:
        """Create safety checker with no rules."""
        return SafetyChecker(rules=[])

    def test_preview_workflow_end_to_end(
        self,
        snapshot_storage: SnapshotStorage,
        audit_storage: AuditStorage,
        safety_checker: SafetyChecker,
    ) -> None:
        """Test complete preview workflow from snapshot to operation result."""
        cleaner = ResourceCleaner(
            snapshot_storage=snapshot_storage,
            safety_checker=safety_checker,
            audit_storage=audit_storage,
        )

        # Mock current resources (baseline + new resources)
        current_resources = [
            {
                "resource_id": "vpc-baseline",
                "resource_type": "AWS::EC2::VPC",
                "region": "us-east-1",
                "arn": "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-baseline",
                "tags": {},
            },
            {
                "resource_id": "i-new-001",
                "resource_type": "AWS::EC2::Instance",
                "region": "us-east-1",
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-new-001",
                "tags": {"Environment": "test", "CreatedBy": "integration-test"},
            },
            {
                "resource_id": "i-new-002",
                "resource_type": "AWS::EC2::Instance",
                "region": "us-east-1",
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-new-002",
                "tags": {"Environment": "dev"},
            },
        ]

        # Mock resource collection
        with patch.object(cleaner, "_collect_current_resources", return_value=current_resources):
            operation = cleaner.preview(
                baseline_snapshot="baseline-test",
                account_id="123456789012",
            )

        # Verify operation structure
        assert operation.mode == OperationMode.DRY_RUN
        assert operation.status == OperationStatus.PLANNED
        assert operation.baseline_snapshot == "baseline-test"
        assert operation.account_id == "123456789012"

        # Verify new resources identified
        assert operation.total_resources == 2
        assert operation.succeeded_count == 0  # Dry-run, no deletions
        assert operation.failed_count == 0
        assert operation.skipped_count == 0

    def test_preview_with_filters_integration(
        self,
        snapshot_storage: SnapshotStorage,
        audit_storage: AuditStorage,
        safety_checker: SafetyChecker,
    ) -> None:
        """Test preview with resource type and region filters."""
        cleaner = ResourceCleaner(
            snapshot_storage=snapshot_storage,
            safety_checker=safety_checker,
            audit_storage=audit_storage,
        )

        current_resources = [
            {
                "resource_id": "vpc-baseline",
                "resource_type": "AWS::EC2::VPC",
                "region": "us-east-1",
                "arn": "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-baseline",
            },
            {
                "resource_id": "i-001",
                "resource_type": "AWS::EC2::Instance",
                "region": "us-east-1",
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-001",
            },
            {
                "resource_id": "bucket-001",
                "resource_type": "AWS::S3::Bucket",
                "region": "us-east-1",
                "arn": "arn:aws:s3:::bucket-001",
            },
        ]

        with patch.object(cleaner, "_collect_current_resources", return_value=current_resources):
            operation = cleaner.preview(
                baseline_snapshot="baseline-test",
                account_id="123456789012",
                resource_types=["AWS::EC2::Instance"],
                regions=["us-east-1"],
            )

        # Should only include EC2 instances in us-east-1
        assert operation.total_resources == 1
        assert operation.filters == {
            "resource_types": ["AWS::EC2::Instance"],
            "regions": ["us-east-1"],
        }

    def test_preview_with_protection_rules_integration(
        self,
        snapshot_storage: SnapshotStorage,
        audit_storage: AuditStorage,
        temp_storage_dir: Path,
    ) -> None:
        """Test preview with protection rules applied."""
        from src.models.protection_rule import ProtectionRule, RuleType

        # Create safety checker with protection rule
        rules = [
            ProtectionRule(
                rule_id="rule_001",
                rule_type=RuleType.TAG,
                enabled=True,
                priority=1,
                patterns={
                    "tag_key": "Protection",
                    "tag_values": ["true", "critical"],
                },
                description="Protect tagged resources",
            )
        ]

        safety_checker = SafetyChecker(rules=rules)

        cleaner = ResourceCleaner(
            snapshot_storage=snapshot_storage,
            safety_checker=safety_checker,
            audit_storage=audit_storage,
        )

        current_resources = [
            {
                "resource_id": "vpc-baseline",
                "resource_type": "AWS::EC2::VPC",
                "region": "us-east-1",
                "arn": "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-baseline",
                "tags": {},
            },
            {
                "resource_id": "i-protected",
                "resource_type": "AWS::EC2::Instance",
                "region": "us-east-1",
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-protected",
                "tags": {"Protection": "true"},  # Protected!
            },
            {
                "resource_id": "i-deletable",
                "resource_type": "AWS::EC2::Instance",
                "region": "us-east-1",
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-deletable",
                "tags": {"Environment": "test"},
            },
        ]

        with patch.object(cleaner, "_collect_current_resources", return_value=current_resources):
            operation = cleaner.preview(
                baseline_snapshot="baseline-test",
                account_id="123456789012",
            )

        # Should identify 2 new resources, 1 protected
        assert operation.total_resources == 2
        assert operation.skipped_count == 1

    def test_execute_workflow_end_to_end(
        self,
        snapshot_storage: SnapshotStorage,
        audit_storage: AuditStorage,
        safety_checker: SafetyChecker,
    ) -> None:
        """Test complete execute workflow from snapshot to deletion."""
        cleaner = ResourceCleaner(
            snapshot_storage=snapshot_storage,
            safety_checker=safety_checker,
            audit_storage=audit_storage,
        )

        # Mock current resources (baseline + new resources)
        current_resources = [
            {
                "resource_id": "vpc-baseline",
                "resource_type": "AWS::EC2::VPC",
                "region": "us-east-1",
                "arn": "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-baseline",
                "tags": {},
            },
            {
                "resource_id": "i-new-001",
                "resource_type": "AWS::EC2::Instance",
                "region": "us-east-1",
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-new-001",
                "tags": {"Environment": "test"},
            },
        ]

        # Mock resource collection and deletion
        with patch.object(cleaner, "_collect_current_resources", return_value=current_resources), patch.object(
            cleaner, "_delete_resource", return_value=(True, None)
        ) as mock_delete:
            operation, records = cleaner.execute(
                baseline_snapshot="baseline-test",
                account_id="123456789012",
                confirmed=True,
            )

        # Verify operation structure
        assert operation.mode == OperationMode.EXECUTE
        assert operation.status == OperationStatus.COMPLETED
        assert operation.baseline_snapshot == "baseline-test"
        assert operation.account_id == "123456789012"

        # Verify deletion occurred
        assert mock_delete.call_count == 1
        assert operation.total_resources == 1
        assert operation.succeeded_count == 1
        assert operation.failed_count == 0
        assert operation.skipped_count == 0

    def test_execute_without_confirmation_fails(
        self,
        snapshot_storage: SnapshotStorage,
        audit_storage: AuditStorage,
        safety_checker: SafetyChecker,
    ) -> None:
        """Test execute requires explicit confirmation."""
        cleaner = ResourceCleaner(
            snapshot_storage=snapshot_storage,
            safety_checker=safety_checker,
            audit_storage=audit_storage,
        )

        with pytest.raises(ValueError, match="confirmation"):
            cleaner.execute(
                baseline_snapshot="baseline-test",
                account_id="123456789012",
                confirmed=False,
            )
