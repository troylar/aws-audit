"""Tests for CLI delta commands."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.main import app
from src.models.delta_report import DeltaReport
from src.models.resource import Resource
from src.models.snapshot import Snapshot

runner = CliRunner()

MOCK_IDENTITY = {
    "account_id": "123456789012",
    "arn": "arn:aws:iam::123456789012:user/test",
}

# Patch both import sites so the mock takes effect regardless of import order
PATCHES = [
    "src.cli.main.validate_credentials",
    "src.aws.credentials.validate_credentials",
]


def _invoke_delta(args):
    """Invoke delta command with both validate_credentials locations patched."""
    with patch(PATCHES[0], return_value=MOCK_IDENTITY), patch(PATCHES[1], return_value=MOCK_IDENTITY):
        return runner.invoke(app, ["delta"] + args)


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
    ]
    return Snapshot(
        name="baseline-snap",
        created_at=datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
        account_id="123456789012",
        regions=["us-east-1"],
        resources=resources,
    )


@pytest.fixture
def sample_delta_report():
    """Create a sample delta report with changes."""
    return DeltaReport(
        generated_at=datetime(2025, 1, 20, 12, 0, 0, tzinfo=timezone.utc),
        baseline_snapshot_name="baseline-snap",
        current_snapshot_name="current-snap",
        added_resources=[
            Resource(
                arn="arn:aws:ec2:us-east-1:123456789012:instance/i-new456",
                resource_type="AWS::EC2::Instance",
                name="new-server",
                region="us-east-1",
                config_hash="c" * 64,
            ),
        ],
        deleted_resources=[],
        modified_resources=[],
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

    def test_delta_help_text(self):
        result = runner.invoke(app, ["delta", "--help"])
        assert result.exit_code == 0
        assert "snapshot" in result.stdout.lower()

    @patch("src.delta.calculator.compare_to_current_state")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    def test_delta_with_valid_snapshot(
        self,
        mock_storage_cls,
        mock_coll_storage_cls,
        mock_compare,
        sample_snapshot,
        sample_delta_report,
        mock_collection,
    ):
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_cls.return_value = mock_storage
        mock_coll_storage_cls.return_value.get_or_create_default.return_value = mock_collection
        mock_compare.return_value = sample_delta_report

        result = _invoke_delta(["--snapshot", "baseline-snap"])
        assert result.exit_code == 0, f"Unexpected output: {result.output}"

    @patch("src.delta.calculator.compare_to_current_state")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    def test_delta_no_changes(
        self,
        mock_storage_cls,
        mock_coll_storage_cls,
        mock_compare,
        sample_snapshot,
        no_changes_delta_report,
        mock_collection,
    ):
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_cls.return_value = mock_storage
        mock_coll_storage_cls.return_value.get_or_create_default.return_value = mock_collection
        mock_compare.return_value = no_changes_delta_report

        result = _invoke_delta(["--snapshot", "baseline-snap"])
        assert result.exit_code == 0, f"Unexpected output: {result.output}"
        assert "No changes" in result.stdout

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    def test_delta_with_nonexistent_snapshot(self, mock_storage_cls, mock_coll_storage_cls, mock_collection):
        mock_storage = MagicMock()
        mock_storage.load_snapshot.side_effect = FileNotFoundError("Snapshot 'nonexistent' not found")
        mock_storage_cls.return_value = mock_storage
        mock_coll_storage_cls.return_value.get_or_create_default.return_value = mock_collection

        result = _invoke_delta(["--snapshot", "nonexistent"])
        assert result.exit_code == 1, f"Unexpected output: {result.output}"
        assert "not found" in result.stdout.lower()

    @patch("src.delta.calculator.compare_to_current_state")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    def test_delta_with_show_diff(
        self,
        mock_storage_cls,
        mock_coll_storage_cls,
        mock_compare,
        sample_snapshot,
        sample_delta_report,
        mock_collection,
    ):
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_cls.return_value = mock_storage
        mock_coll_storage_cls.return_value.get_or_create_default.return_value = mock_collection
        mock_compare.return_value = sample_delta_report

        result = _invoke_delta(["--snapshot", "baseline-snap", "--show-diff"])
        assert result.exit_code == 0, f"Unexpected output: {result.output}"
        mock_compare.assert_called_once()
        assert mock_compare.call_args[1]["include_drift_details"] is True

    @patch("src.delta.calculator.compare_to_current_state")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    def test_delta_with_type_filter(
        self,
        mock_storage_cls,
        mock_coll_storage_cls,
        mock_compare,
        sample_snapshot,
        no_changes_delta_report,
        mock_collection,
    ):
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_cls.return_value = mock_storage
        mock_coll_storage_cls.return_value.get_or_create_default.return_value = mock_collection
        mock_compare.return_value = no_changes_delta_report

        result = _invoke_delta(["--snapshot", "baseline-snap", "--type", "AWS::EC2::Instance"])
        assert result.exit_code == 0, f"Unexpected output: {result.output}"
        assert mock_compare.call_args[1]["resource_type_filter"] == ["AWS::EC2::Instance"]

    @patch("src.delta.calculator.compare_to_current_state")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    def test_delta_with_region_filter(
        self,
        mock_storage_cls,
        mock_coll_storage_cls,
        mock_compare,
        sample_snapshot,
        no_changes_delta_report,
        mock_collection,
    ):
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_cls.return_value = mock_storage
        mock_coll_storage_cls.return_value.get_or_create_default.return_value = mock_collection
        mock_compare.return_value = no_changes_delta_report

        result = _invoke_delta(["--snapshot", "baseline-snap", "--region", "us-west-2"])
        assert result.exit_code == 0, f"Unexpected output: {result.output}"
        assert mock_compare.call_args[1]["region_filter"] == ["us-west-2"]

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    def test_delta_with_nonexistent_collection(self, mock_storage_cls, mock_coll_storage_cls):
        mock_coll_storage_cls.return_value.get_by_name.side_effect = Exception("Collection not found")

        result = _invoke_delta(["--collection", "nonexistent-collection"])
        assert result.exit_code == 1, f"Unexpected output: {result.output}"
        assert "not found" in result.stdout.lower()

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    def test_delta_collection_no_snapshots(self, mock_storage_cls, mock_coll_storage_cls):
        empty_collection = MagicMock()
        empty_collection.snapshots = []
        empty_collection.active_snapshot = None
        mock_coll_storage_cls.return_value.get_or_create_default.return_value = empty_collection

        result = _invoke_delta([])
        assert result.exit_code == 1, f"Unexpected output: {result.output}"
        assert "no snapshots" in result.stdout.lower()
