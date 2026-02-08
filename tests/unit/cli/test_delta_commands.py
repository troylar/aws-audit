"""Tests for CLI delta commands."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.main import app
from src.models.delta_report import DeltaReport, ResourceChange
from src.models.resource import Resource
from src.models.snapshot import Snapshot


@pytest.fixture
def cli_runner():
    """Create a Typer CLI runner."""
    return CliRunner()


@pytest.fixture
def sample_snapshot():
    """Create a sample snapshot for testing."""
    resources = [
        Resource(
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-abc123",
            resource_type="AWS::EC2::Instance",
            name="web-server",
            region="us-east-1",
            config_hash="a" * 64,
        ),
        Resource(
            arn="arn:aws:s3:::my-bucket",
            resource_type="AWS::S3::Bucket",
            name="my-bucket",
            region="us-east-1",
            config_hash="b" * 64,
        ),
    ]
    return Snapshot(
        name="baseline-snap",
        created_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        account_id="123456789012",
        regions=["us-east-1"],
        resources=resources,
    )


@pytest.fixture
def sample_delta_report(sample_snapshot):
    """Create a sample delta report with changes."""
    added = [
        Resource(
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-new456",
            resource_type="AWS::EC2::Instance",
            name="new-server",
            region="us-east-1",
            config_hash="c" * 64,
        ),
    ]
    deleted = [
        Resource(
            arn="arn:aws:s3:::old-bucket",
            resource_type="AWS::S3::Bucket",
            name="old-bucket",
            region="us-east-1",
            config_hash="d" * 64,
        ),
    ]
    modified = [
        ResourceChange(
            resource=Resource(
                arn="arn:aws:ec2:us-east-1:123456789012:instance/i-abc123",
                resource_type="AWS::EC2::Instance",
                name="web-server",
                region="us-east-1",
                config_hash="e" * 64,
            ),
            baseline_resource=Resource(
                arn="arn:aws:ec2:us-east-1:123456789012:instance/i-abc123",
                resource_type="AWS::EC2::Instance",
                name="web-server",
                region="us-east-1",
                config_hash="a" * 64,
            ),
            change_type="modified",
            old_config_hash="a" * 64,
            new_config_hash="e" * 64,
        ),
    ]
    return DeltaReport(
        generated_at=datetime(2025, 1, 20, 12, 0, 0, tzinfo=timezone.utc),
        baseline_snapshot_name="baseline-snap",
        current_snapshot_name="current-snap",
        added_resources=added,
        deleted_resources=deleted,
        modified_resources=modified,
        baseline_resource_count=3,
        current_resource_count=3,
    )


@pytest.fixture
def no_changes_delta_report():
    """Create a delta report with no changes."""
    return DeltaReport(
        generated_at=datetime(2025, 1, 20, 12, 0, 0, tzinfo=timezone.utc),
        baseline_snapshot_name="baseline-snap",
        current_snapshot_name="current-snap",
        added_resources=[],
        deleted_resources=[],
        modified_resources=[],
        baseline_resource_count=5,
        current_resource_count=5,
    )


@pytest.fixture
def mock_collection():
    """Create a mock collection with an active snapshot."""
    collection = MagicMock()
    collection.snapshots = ["baseline-snap.yaml"]
    collection.active_snapshot = "baseline-snap.yaml"
    return collection


class TestDeltaCommand:
    """Tests for awsinv delta command."""

    @patch("src.cli.main.SnapshotStorage")
    @patch("src.cli.main.delta")
    def test_delta_help_text(self, mock_delta_fn, mock_storage_cls, cli_runner):
        """Test that delta command has help text."""
        result = cli_runner.invoke(app, ["delta", "--help"])
        assert result.exit_code == 0
        assert "snapshot" in result.stdout.lower()

    @patch("src.delta.calculator.compare_to_current_state")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    @patch("src.cli.main.validate_credentials")
    def test_delta_with_valid_snapshot(
        self,
        mock_validate,
        mock_storage_cls,
        mock_coll_storage_cls,
        mock_compare,
        cli_runner,
        sample_snapshot,
        sample_delta_report,
        mock_collection,
    ):
        """Test delta with a valid snapshot returns changes."""
        mock_validate.return_value = {
            "account_id": "123456789012",
            "arn": "arn:aws:iam::123456789012:user/test",
        }
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_cls.return_value = mock_storage

        mock_coll_storage = MagicMock()
        mock_coll_storage.get_or_create_default.return_value = mock_collection
        mock_coll_storage_cls.return_value = mock_coll_storage

        mock_compare.return_value = sample_delta_report

        result = cli_runner.invoke(app, ["delta", "--snapshot", "baseline-snap"])

        assert result.exit_code == 0

    @patch("src.delta.calculator.compare_to_current_state")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    @patch("src.cli.main.validate_credentials")
    def test_delta_no_changes(
        self,
        mock_validate,
        mock_storage_cls,
        mock_coll_storage_cls,
        mock_compare,
        cli_runner,
        sample_snapshot,
        no_changes_delta_report,
        mock_collection,
    ):
        """Test delta when no changes are detected."""
        mock_validate.return_value = {
            "account_id": "123456789012",
            "arn": "arn:aws:iam::123456789012:user/test",
        }
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_cls.return_value = mock_storage

        mock_coll_storage = MagicMock()
        mock_coll_storage.get_or_create_default.return_value = mock_collection
        mock_coll_storage_cls.return_value = mock_coll_storage

        mock_compare.return_value = no_changes_delta_report

        result = cli_runner.invoke(app, ["delta", "--snapshot", "baseline-snap"])

        assert result.exit_code == 0
        assert "No changes" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    @patch("src.cli.main.validate_credentials")
    def test_delta_with_nonexistent_snapshot(
        self,
        mock_validate,
        mock_storage_cls,
        cli_runner,
        mock_collection,
    ):
        """Test delta with a snapshot that does not exist."""
        mock_validate.return_value = {
            "account_id": "123456789012",
            "arn": "arn:aws:iam::123456789012:user/test",
        }
        mock_storage = MagicMock()
        mock_storage.load_snapshot.side_effect = FileNotFoundError("Snapshot 'nonexistent' not found")
        mock_storage_cls.return_value = mock_storage

        mock_coll_storage = MagicMock()
        mock_coll_storage.get_or_create_default.return_value = mock_collection

        with patch("src.snapshot.collection_storage.CollectionStorage", return_value=mock_coll_storage):
            result = cli_runner.invoke(app, ["delta", "--snapshot", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    @patch("src.delta.calculator.compare_to_current_state")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    @patch("src.cli.main.validate_credentials")
    def test_delta_with_show_diff(
        self,
        mock_validate,
        mock_storage_cls,
        mock_coll_storage_cls,
        mock_compare,
        cli_runner,
        sample_snapshot,
        sample_delta_report,
        mock_collection,
    ):
        """Test delta with --show-diff flag enables drift details."""
        mock_validate.return_value = {
            "account_id": "123456789012",
            "arn": "arn:aws:iam::123456789012:user/test",
        }
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_cls.return_value = mock_storage

        mock_coll_storage = MagicMock()
        mock_coll_storage.get_or_create_default.return_value = mock_collection
        mock_coll_storage_cls.return_value = mock_coll_storage

        mock_compare.return_value = sample_delta_report

        result = cli_runner.invoke(app, ["delta", "--snapshot", "baseline-snap", "--show-diff"])

        assert result.exit_code == 0
        mock_compare.assert_called_once()
        call_kwargs = mock_compare.call_args
        assert call_kwargs[1]["include_drift_details"] is True

    @patch("src.delta.calculator.compare_to_current_state")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    @patch("src.cli.main.validate_credentials")
    def test_delta_with_type_filter(
        self,
        mock_validate,
        mock_storage_cls,
        mock_coll_storage_cls,
        mock_compare,
        cli_runner,
        sample_snapshot,
        no_changes_delta_report,
        mock_collection,
    ):
        """Test delta with --type filter passes resource_type_filter."""
        mock_validate.return_value = {
            "account_id": "123456789012",
            "arn": "arn:aws:iam::123456789012:user/test",
        }
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_cls.return_value = mock_storage

        mock_coll_storage = MagicMock()
        mock_coll_storage.get_or_create_default.return_value = mock_collection
        mock_coll_storage_cls.return_value = mock_coll_storage

        mock_compare.return_value = no_changes_delta_report

        result = cli_runner.invoke(app, ["delta", "--snapshot", "baseline-snap", "--type", "AWS::EC2::Instance"])

        assert result.exit_code == 0
        mock_compare.assert_called_once()
        call_kwargs = mock_compare.call_args
        assert call_kwargs[1]["resource_type_filter"] == ["AWS::EC2::Instance"]

    @patch("src.delta.calculator.compare_to_current_state")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    @patch("src.cli.main.validate_credentials")
    def test_delta_with_region_filter(
        self,
        mock_validate,
        mock_storage_cls,
        mock_coll_storage_cls,
        mock_compare,
        cli_runner,
        sample_snapshot,
        no_changes_delta_report,
        mock_collection,
    ):
        """Test delta with --region filter passes region_filter."""
        mock_validate.return_value = {
            "account_id": "123456789012",
            "arn": "arn:aws:iam::123456789012:user/test",
        }
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_cls.return_value = mock_storage

        mock_coll_storage = MagicMock()
        mock_coll_storage.get_or_create_default.return_value = mock_collection
        mock_coll_storage_cls.return_value = mock_coll_storage

        mock_compare.return_value = no_changes_delta_report

        result = cli_runner.invoke(app, ["delta", "--snapshot", "baseline-snap", "--region", "us-west-2"])

        assert result.exit_code == 0
        mock_compare.assert_called_once()
        call_kwargs = mock_compare.call_args
        assert call_kwargs[1]["region_filter"] == ["us-west-2"]

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    @patch("src.cli.main.validate_credentials")
    def test_delta_with_nonexistent_collection(
        self,
        mock_validate,
        mock_storage_cls,
        mock_coll_storage_cls,
        cli_runner,
    ):
        """Test delta with a collection that does not exist."""
        mock_validate.return_value = {
            "account_id": "123456789012",
            "arn": "arn:aws:iam::123456789012:user/test",
        }
        mock_coll_storage = MagicMock()
        mock_coll_storage.get_by_name.side_effect = Exception("Collection not found")
        mock_coll_storage_cls.return_value = mock_coll_storage

        result = cli_runner.invoke(app, ["delta", "--collection", "nonexistent-collection"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower()

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    @patch("src.cli.main.validate_credentials")
    def test_delta_collection_no_snapshots(
        self,
        mock_validate,
        mock_storage_cls,
        mock_coll_storage_cls,
        cli_runner,
    ):
        """Test delta when collection has no snapshots."""
        mock_validate.return_value = {
            "account_id": "123456789012",
            "arn": "arn:aws:iam::123456789012:user/test",
        }
        empty_collection = MagicMock()
        empty_collection.snapshots = []
        empty_collection.active_snapshot = None

        mock_coll_storage = MagicMock()
        mock_coll_storage.get_or_create_default.return_value = empty_collection
        mock_coll_storage_cls.return_value = mock_coll_storage

        result = cli_runner.invoke(app, ["delta"])

        assert result.exit_code == 1
        assert "No snapshots" in result.stdout or "no snapshots" in result.stdout.lower()
