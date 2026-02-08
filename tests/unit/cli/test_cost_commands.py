"""Tests for CLI cost commands."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.main import app
from src.models.cost_report import CostBreakdown, CostReport
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


def _invoke_cost(args):
    """Invoke cost command with both validate_credentials locations patched."""
    with patch(PATCHES[0], return_value=MOCK_IDENTITY), patch(PATCHES[1], return_value=MOCK_IDENTITY):
        return runner.invoke(app, ["cost"] + args)


@pytest.fixture
def sample_snapshot():
    """Create a sample snapshot for cost analysis."""
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
        Resource(
            arn="arn:aws:rds:us-east-1:123456789012:db:mydb",
            resource_type="AWS::RDS::DBInstance",
            name="mydb",
            region="us-east-1",
            config_hash="c" * 64,
        ),
    ]
    return Snapshot(
        name="cost-test-snap",
        created_at=datetime(2025, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
        account_id="123456789012",
        regions=["us-east-1"],
        resources=resources,
    )


@pytest.fixture
def sample_cost_report():
    """Create a sample cost report."""
    return CostReport(
        generated_at=datetime(2025, 1, 31, 12, 0, 0),
        baseline_snapshot_name="cost-test-snap",
        period_start=datetime(2025, 1, 1),
        period_end=datetime(2025, 1, 31),
        baseline_costs=CostBreakdown(
            total=1250.50,
            by_service={
                "Amazon Elastic Compute Cloud - Compute": 800.00,
                "Amazon Simple Storage Service": 50.50,
                "Amazon Relational Database Service": 400.00,
            },
            percentage=100.0,
        ),
        non_baseline_costs=CostBreakdown(
            total=0.0,
            by_service={},
            percentage=0.0,
        ),
        total_cost=1250.50,
        data_complete=True,
        data_through=datetime(2025, 1, 30),
        lag_days=1,
    )


@pytest.fixture
def no_changes_delta_report():
    """Create a delta report with no changes."""
    return DeltaReport(
        generated_at=datetime(2025, 1, 31, 12, 0, 0, tzinfo=timezone.utc),
        baseline_snapshot_name="cost-test-snap",
        current_snapshot_name="current-snap",
        added_resources=[],
        deleted_resources=[],
        modified_resources=[],
        baseline_resource_count=3,
        current_resource_count=3,
    )


@pytest.fixture
def mock_collection():
    """Create a mock collection with an active snapshot."""
    collection = MagicMock()
    collection.snapshots = ["cost-test-snap.yaml"]
    collection.active_snapshot = "cost-test-snap.yaml"
    return collection


class TestCostCommand:
    """Tests for awsinv cost command."""

    def test_cost_help_text(self):
        """Test that cost command has help text."""
        result = runner.invoke(app, ["cost", "--help"])
        assert result.exit_code == 0
        assert "snapshot" in result.stdout.lower()
        assert "granularity" in result.stdout.lower()

    @patch("src.cost.explorer.CostExplorerClient")
    @patch("src.cost.analyzer.CostAnalyzer")
    @patch("src.delta.calculator.compare_to_current_state")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    def test_cost_with_valid_snapshot(
        self,
        mock_storage_cls,
        mock_coll_storage_cls,
        mock_compare,
        mock_analyzer_cls,
        mock_explorer_cls,
        sample_snapshot,
        sample_cost_report,
        no_changes_delta_report,
        mock_collection,
    ):
        """Test cost analysis with a valid snapshot."""
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_cls.return_value = mock_storage

        mock_coll_storage = MagicMock()
        mock_coll_storage.get_or_create_default.return_value = mock_collection
        mock_coll_storage_cls.return_value = mock_coll_storage

        mock_compare.return_value = no_changes_delta_report

        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = sample_cost_report
        mock_analyzer_cls.return_value = mock_analyzer

        result = _invoke_cost(["--snapshot", "cost-test-snap"])

        assert result.exit_code == 0, f"Unexpected output: {result.output}"

    @patch("src.cli.main.SnapshotStorage")
    def test_cost_with_nonexistent_snapshot(
        self,
        mock_storage_cls,
        mock_collection,
    ):
        """Test cost analysis with a snapshot that does not exist."""
        mock_storage = MagicMock()
        mock_storage.load_snapshot.side_effect = FileNotFoundError("Snapshot not found")
        mock_storage_cls.return_value = mock_storage

        mock_coll_storage = MagicMock()
        mock_coll_storage.get_or_create_default.return_value = mock_collection

        with patch("src.snapshot.collection_storage.CollectionStorage", return_value=mock_coll_storage):
            result = _invoke_cost(["--snapshot", "nonexistent"])

        assert result.exit_code == 1, f"Unexpected output: {result.output}"
        assert "not found" in result.stdout.lower()

    @patch("src.cost.explorer.CostExplorerClient")
    @patch("src.cost.analyzer.CostAnalyzer")
    @patch("src.delta.calculator.compare_to_current_state")
    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    def test_cost_with_date_range(
        self,
        mock_storage_cls,
        mock_coll_storage_cls,
        mock_compare,
        mock_analyzer_cls,
        mock_explorer_cls,
        sample_snapshot,
        sample_cost_report,
        no_changes_delta_report,
        mock_collection,
    ):
        """Test cost analysis with --start-date and --end-date."""
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_cls.return_value = mock_storage

        mock_coll_storage = MagicMock()
        mock_coll_storage.get_or_create_default.return_value = mock_collection
        mock_coll_storage_cls.return_value = mock_coll_storage

        mock_compare.return_value = no_changes_delta_report

        mock_analyzer = MagicMock()
        mock_analyzer.analyze.return_value = sample_cost_report
        mock_analyzer_cls.return_value = mock_analyzer

        result = _invoke_cost(
            [
                "--snapshot",
                "cost-test-snap",
                "--start-date",
                "2025-01-01",
                "--end-date",
                "2025-01-31",
            ],
        )

        assert result.exit_code == 0, f"Unexpected output: {result.output}"

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    def test_cost_with_invalid_start_date(
        self,
        mock_storage_cls,
        mock_coll_storage_cls,
        sample_snapshot,
        mock_collection,
    ):
        """Test cost analysis with an invalid start date format."""
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_cls.return_value = mock_storage

        mock_coll_storage = MagicMock()
        mock_coll_storage.get_or_create_default.return_value = mock_collection
        mock_coll_storage_cls.return_value = mock_coll_storage

        result = _invoke_cost(
            ["--snapshot", "cost-test-snap", "--start-date", "not-a-date"],
        )

        assert result.exit_code == 1, f"Unexpected output: {result.output}"
        assert "Invalid" in result.stdout

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    def test_cost_with_invalid_granularity(
        self,
        mock_storage_cls,
        mock_coll_storage_cls,
        sample_snapshot,
        mock_collection,
    ):
        """Test cost analysis with an invalid granularity value."""
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_cls.return_value = mock_storage

        mock_coll_storage = MagicMock()
        mock_coll_storage.get_or_create_default.return_value = mock_collection
        mock_coll_storage_cls.return_value = mock_coll_storage

        result = _invoke_cost(
            ["--snapshot", "cost-test-snap", "--granularity", "HOURLY"],
        )

        assert result.exit_code == 1, f"Unexpected output: {result.output}"
        assert "Invalid granularity" in result.stdout

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    def test_cost_with_nonexistent_collection(
        self,
        mock_storage_cls,
        mock_coll_storage_cls,
    ):
        """Test cost analysis with a collection that does not exist."""
        mock_coll_storage = MagicMock()
        mock_coll_storage.get_by_name.side_effect = Exception("Collection not found")
        mock_coll_storage_cls.return_value = mock_coll_storage

        result = _invoke_cost(["--collection", "nonexistent-collection"])

        assert result.exit_code == 1, f"Unexpected output: {result.output}"
        assert "not found" in result.stdout.lower()

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    def test_cost_collection_no_snapshots(
        self,
        mock_storage_cls,
        mock_coll_storage_cls,
    ):
        """Test cost analysis when collection has no snapshots."""
        empty_collection = MagicMock()
        empty_collection.snapshots = []
        empty_collection.active_snapshot = None

        mock_coll_storage = MagicMock()
        mock_coll_storage.get_or_create_default.return_value = empty_collection
        mock_coll_storage_cls.return_value = mock_coll_storage

        result = _invoke_cost([])

        assert result.exit_code == 1, f"Unexpected output: {result.output}"
        assert "No snapshots" in result.stdout or "no snapshots" in result.stdout.lower()

    @patch("src.snapshot.collection_storage.CollectionStorage")
    @patch("src.cli.main.SnapshotStorage")
    def test_cost_with_invalid_end_date(
        self,
        mock_storage_cls,
        mock_coll_storage_cls,
        sample_snapshot,
        mock_collection,
    ):
        """Test cost analysis with an invalid end date format."""
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_cls.return_value = mock_storage

        mock_coll_storage = MagicMock()
        mock_coll_storage.get_or_create_default.return_value = mock_collection
        mock_coll_storage_cls.return_value = mock_coll_storage

        result = _invoke_cost(
            [
                "--snapshot",
                "cost-test-snap",
                "--start-date",
                "2025-01-01",
                "--end-date",
                "bad-date",
            ],
        )

        assert result.exit_code == 1, f"Unexpected output: {result.output}"
        assert "Invalid" in result.stdout
