"""Unit tests for delta report models."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from src.models.delta_report import DeltaReport, ResourceChange
from src.models.resource import Resource


class TestResourceChange:
    """Tests for ResourceChange dataclass."""

    @pytest.fixture
    def sample_resource(self):
        """Create a sample resource for testing."""
        return Resource(
            arn="arn:aws:s3:::test-bucket",
            resource_type="AWS::S3::Bucket",
            name="test-bucket",
            region="us-east-1",
            config_hash="a" * 64,
            raw_config={"BucketName": "test-bucket"},
            tags={"Environment": "test"},
        )

    @pytest.fixture
    def baseline_resource(self):
        """Create a baseline resource for testing."""
        return Resource(
            arn="arn:aws:s3:::test-bucket",
            resource_type="AWS::S3::Bucket",
            name="test-bucket",
            region="us-east-1",
            config_hash="b" * 64,
            raw_config={"BucketName": "test-bucket"},
            tags={"Environment": "prod"},
        )

    def test_resource_change_creation(self, sample_resource, baseline_resource):
        """Test creating a ResourceChange instance."""
        change = ResourceChange(
            resource=sample_resource,
            baseline_resource=baseline_resource,
            change_type="modified",
            old_config_hash="b" * 64,
            new_config_hash="a" * 64,
            changes_summary="Tags changed",
        )

        assert change.resource == sample_resource
        assert change.baseline_resource == baseline_resource
        assert change.change_type == "modified"
        assert change.old_config_hash == "b" * 64
        assert change.new_config_hash == "a" * 64
        assert change.changes_summary == "Tags changed"

    def test_resource_change_to_dict(self, sample_resource, baseline_resource):
        """Test ResourceChange.to_dict() serialization."""
        change = ResourceChange(
            resource=sample_resource,
            baseline_resource=baseline_resource,
            change_type="modified",
            old_config_hash="b" * 64,
            new_config_hash="a" * 64,
            changes_summary="Configuration updated",
        )

        result = change.to_dict()

        assert result["arn"] == "arn:aws:s3:::test-bucket"
        assert result["resource_type"] == "AWS::S3::Bucket"
        assert result["name"] == "test-bucket"
        assert result["region"] == "us-east-1"
        assert result["change_type"] == "modified"
        assert result["tags"] == {"Environment": "test"}
        assert result["old_config_hash"] == "b" * 64
        assert result["new_config_hash"] == "a" * 64
        assert result["changes_summary"] == "Configuration updated"

    def test_resource_change_to_dict_no_summary(self, sample_resource, baseline_resource):
        """Test ResourceChange.to_dict() with no changes_summary."""
        change = ResourceChange(
            resource=sample_resource,
            baseline_resource=baseline_resource,
            change_type="modified",
            old_config_hash="b" * 64,
            new_config_hash="a" * 64,
        )

        result = change.to_dict()

        assert result["changes_summary"] is None


class TestDeltaReport:
    """Tests for DeltaReport dataclass."""

    @pytest.fixture
    def sample_resources(self):
        """Create sample resources for testing."""
        return [
            Resource(
                arn="arn:aws:s3:::bucket-1",
                resource_type="AWS::S3::Bucket",
                name="bucket-1",
                region="us-east-1",
                config_hash="a" * 64,
                raw_config={},
            ),
            Resource(
                arn="arn:aws:ec2:us-east-1:123456789012:instance/i-abc123",
                resource_type="AWS::EC2::Instance",
                name="i-abc123",
                region="us-east-1",
                config_hash="b" * 64,
                raw_config={},
            ),
            Resource(
                arn="arn:aws:lambda:us-east-1:123456789012:function:my-func",
                resource_type="AWS::Lambda::Function",
                name="my-func",
                region="us-east-1",
                config_hash="c" * 64,
                raw_config={},
            ),
        ]

    @pytest.fixture
    def empty_delta_report(self):
        """Create an empty delta report."""
        return DeltaReport(
            generated_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            baseline_snapshot_name="baseline-snapshot",
            current_snapshot_name="current-snapshot",
            baseline_resource_count=10,
            current_resource_count=10,
        )

    @pytest.fixture
    def delta_report_with_changes(self, sample_resources):
        """Create a delta report with changes."""
        added = [sample_resources[0]]  # S3 bucket added
        deleted = [sample_resources[1]]  # EC2 instance deleted

        # Create a modified resource
        modified_resource = sample_resources[2]
        baseline_resource = Resource(
            arn=modified_resource.arn,
            resource_type=modified_resource.resource_type,
            name=modified_resource.name,
            region=modified_resource.region,
            config_hash="d" * 64,
            raw_config={},
        )
        modified = [
            ResourceChange(
                resource=modified_resource,
                baseline_resource=baseline_resource,
                change_type="modified",
                old_config_hash="d" * 64,
                new_config_hash="c" * 64,
                changes_summary="Runtime updated",
            )
        ]

        return DeltaReport(
            generated_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            baseline_snapshot_name="baseline-snapshot",
            current_snapshot_name="current-snapshot",
            added_resources=added,
            deleted_resources=deleted,
            modified_resources=modified,
            baseline_resource_count=10,
            current_resource_count=10,
        )

    def test_delta_report_creation(self, empty_delta_report):
        """Test creating an empty DeltaReport."""
        report = empty_delta_report

        assert report.baseline_snapshot_name == "baseline-snapshot"
        assert report.current_snapshot_name == "current-snapshot"
        assert report.added_resources == []
        assert report.deleted_resources == []
        assert report.modified_resources == []
        assert report.baseline_resource_count == 10
        assert report.current_resource_count == 10

    def test_total_changes_empty(self, empty_delta_report):
        """Test total_changes property with no changes."""
        assert empty_delta_report.total_changes == 0

    def test_total_changes_with_changes(self, delta_report_with_changes):
        """Test total_changes property with changes."""
        # 1 added + 1 deleted + 1 modified = 3
        assert delta_report_with_changes.total_changes == 3

    def test_unchanged_count(self, empty_delta_report):
        """Test unchanged_count property with no changes."""
        # All 10 resources unchanged
        assert empty_delta_report.unchanged_count == 10

    def test_unchanged_count_with_changes(self, delta_report_with_changes):
        """Test unchanged_count property with changes."""
        # 10 baseline - 1 deleted - 1 modified = 8 unchanged
        assert delta_report_with_changes.unchanged_count == 8

    def test_has_changes_false(self, empty_delta_report):
        """Test has_changes property when no changes."""
        assert empty_delta_report.has_changes is False

    def test_has_changes_true(self, delta_report_with_changes):
        """Test has_changes property when changes exist."""
        assert delta_report_with_changes.has_changes is True

    def test_to_dict_empty_report(self, empty_delta_report):
        """Test to_dict() on empty delta report."""
        result = empty_delta_report.to_dict()

        assert result["generated_at"] == "2024-01-15T10:30:00+00:00"
        assert result["baseline_snapshot_name"] == "baseline-snapshot"
        assert result["current_snapshot_name"] == "current-snapshot"
        assert result["added_resources"] == []
        assert result["deleted_resources"] == []
        assert result["modified_resources"] == []
        assert result["baseline_resource_count"] == 10
        assert result["current_resource_count"] == 10
        assert result["summary"]["added"] == 0
        assert result["summary"]["deleted"] == 0
        assert result["summary"]["modified"] == 0
        assert result["summary"]["unchanged"] == 10
        assert result["summary"]["total_changes"] == 0
        assert "drift_details" not in result

    def test_to_dict_with_changes(self, delta_report_with_changes):
        """Test to_dict() on delta report with changes."""
        result = delta_report_with_changes.to_dict()

        assert len(result["added_resources"]) == 1
        assert result["added_resources"][0]["name"] == "bucket-1"

        assert len(result["deleted_resources"]) == 1
        assert result["deleted_resources"][0]["name"] == "i-abc123"

        assert len(result["modified_resources"]) == 1
        assert result["modified_resources"][0]["name"] == "my-func"
        assert result["modified_resources"][0]["changes_summary"] == "Runtime updated"

        assert result["summary"]["added"] == 1
        assert result["summary"]["deleted"] == 1
        assert result["summary"]["modified"] == 1
        assert result["summary"]["unchanged"] == 8
        assert result["summary"]["total_changes"] == 3

    def test_to_dict_with_drift_report(self, empty_delta_report):
        """Test to_dict() includes drift_report when present."""
        # Create a mock drift report
        mock_drift_report = MagicMock()
        mock_drift_report.to_dict.return_value = {
            "changes": [{"field": "Runtime", "old": "python3.8", "new": "python3.9"}]
        }

        empty_delta_report.drift_report = mock_drift_report
        result = empty_delta_report.to_dict()

        assert "drift_details" in result
        assert result["drift_details"]["changes"][0]["field"] == "Runtime"

    def test_group_by_service_empty(self, empty_delta_report):
        """Test group_by_service() with no changes."""
        result = empty_delta_report.group_by_service()
        assert result == {}

    def test_group_by_service_with_changes(self, delta_report_with_changes):
        """Test group_by_service() groups changes correctly."""
        result = delta_report_with_changes.group_by_service()

        # S3 bucket was added
        assert "AWS::S3::Bucket" in result
        assert len(result["AWS::S3::Bucket"]["added"]) == 1
        assert len(result["AWS::S3::Bucket"]["deleted"]) == 0
        assert len(result["AWS::S3::Bucket"]["modified"]) == 0

        # EC2 instance was deleted
        assert "AWS::EC2::Instance" in result
        assert len(result["AWS::EC2::Instance"]["added"]) == 0
        assert len(result["AWS::EC2::Instance"]["deleted"]) == 1
        assert len(result["AWS::EC2::Instance"]["modified"]) == 0

        # Lambda function was modified
        assert "AWS::Lambda::Function" in result
        assert len(result["AWS::Lambda::Function"]["added"]) == 0
        assert len(result["AWS::Lambda::Function"]["deleted"]) == 0
        assert len(result["AWS::Lambda::Function"]["modified"]) == 1

    def test_group_by_service_multiple_same_type(self, sample_resources):
        """Test group_by_service() with multiple resources of same type."""
        # Create another S3 bucket
        bucket2 = Resource(
            arn="arn:aws:s3:::bucket-2",
            resource_type="AWS::S3::Bucket",
            name="bucket-2",
            region="us-west-2",
            config_hash="e" * 64,
            raw_config={},
        )

        report = DeltaReport(
            generated_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            baseline_snapshot_name="baseline",
            current_snapshot_name="current",
            added_resources=[sample_resources[0], bucket2],  # Two S3 buckets added
            baseline_resource_count=5,
            current_resource_count=7,
        )

        result = report.group_by_service()

        assert "AWS::S3::Bucket" in result
        assert len(result["AWS::S3::Bucket"]["added"]) == 2
        assert result["AWS::S3::Bucket"]["added"][0].name == "bucket-1"
        assert result["AWS::S3::Bucket"]["added"][1].name == "bucket-2"
