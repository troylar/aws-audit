"""
Integration tests for snapshot report CLI command.

Tests end-to-end CLI execution with test snapshots.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from src.cli.main import app
from src.models.resource import Resource
from src.models.snapshot import Snapshot


@pytest.fixture
def cli_runner():
    """Create a Typer CLI runner."""
    return CliRunner()


@pytest.fixture
def test_snapshot():
    """Create a test snapshot with sample resources."""
    resources = [
        Resource(
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-123",
            resource_type="AWS::EC2::Instance",
            name="test-instance",
            region="us-east-1",
            config_hash="a" * 64,
            raw_config={},
            tags={"Environment": "test"},
            created_at=datetime(2025, 1, 15, 10, 0, 0),
        ),
        Resource(
            arn="arn:aws:s3:::test-bucket",
            resource_type="AWS::S3::Bucket",
            name="test-bucket",
            region="us-east-1",
            config_hash="b" * 64,
            raw_config={},
            tags={},
            created_at=None,
        ),
    ]

    return Snapshot(
        name="test-snapshot",
        created_at=datetime(2025, 1, 29, 10, 30, 0),
        account_id="123456789012",
        regions=["us-east-1"],
        resources=resources,
        inventory_name="test",
    )


class TestSnapshotReportCLI:
    """Tests for awsinv snapshot report command."""

    @patch("src.snapshot.storage.SnapshotStorage.load_snapshot")
    @patch("src.snapshot.storage.SnapshotStorage.get_active_snapshot_name")
    def test_report_command_basic(
        self,
        mock_get_active,
        mock_load,
        cli_runner,
        test_snapshot,
    ):
        """Test CLI command 'snapshot report' with test snapshot."""
        mock_get_active.return_value = "test-snapshot"
        mock_load.return_value = test_snapshot

        result = cli_runner.invoke(app, ["snapshot", "report"])

        assert result.exit_code == 0
        assert "test-snapshot" in result.stdout
        assert "2" in result.stdout  # Total resource count

    @patch("src.snapshot.storage.SnapshotStorage.load_snapshot")
    @patch("src.snapshot.storage.SnapshotStorage.get_active_snapshot_name")
    def test_report_with_snapshot_name(
        self,
        mock_get_active,
        mock_load,
        cli_runner,
        test_snapshot,
    ):
        """Test report command with explicit snapshot name."""
        mock_load.return_value = test_snapshot

        result = cli_runner.invoke(app, ["snapshot", "report", "test-snapshot"])

        assert result.exit_code == 0
        assert "test-snapshot" in result.stdout


class TestSnapshotReportCLIEmptySnapshot:
    """Tests for empty snapshot handling."""

    @patch("src.snapshot.storage.SnapshotStorage.load_snapshot")
    @patch("src.snapshot.storage.SnapshotStorage.get_active_snapshot_name")
    def test_empty_snapshot_handling(
        self,
        mock_get_active,
        mock_load,
        cli_runner,
    ):
        """Test empty snapshot handling with clear message."""
        empty_snapshot = Snapshot(
            name="empty",
            created_at=datetime.now(),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
            inventory_name="test",
        )
        mock_get_active.return_value = "empty"
        mock_load.return_value = empty_snapshot

        result = cli_runner.invoke(app, ["snapshot", "report"])

        # Should either succeed with 0 resources or warn
        assert result.exit_code in [0, 1]
        assert "0" in result.stdout or "empty" in result.stdout.lower()


class TestSnapshotReportCLIErrors:
    """Tests for error conditions."""

    @patch("src.snapshot.storage.SnapshotStorage.load_snapshot")
    def test_missing_snapshot_error(self, mock_load, cli_runner):
        """Test missing snapshot error message."""
        mock_load.side_effect = FileNotFoundError("Snapshot not found")

        result = cli_runner.invoke(app, ["snapshot", "report", "nonexistent"])

        assert result.exit_code != 0
        assert "not found" in result.stdout.lower() or "error" in result.stdout.lower()

    @patch("src.snapshot.storage.SnapshotStorage.get_active_snapshot_name")
    def test_no_active_snapshot_error(self, mock_get_active, cli_runner):
        """Test no active snapshot with helpful message."""
        mock_get_active.return_value = None

        result = cli_runner.invoke(app, ["snapshot", "report"])

        assert result.exit_code != 0
        assert "active" in result.stdout.lower() or "not found" in result.stdout.lower()


class TestSnapshotReportCLIFiltering:
    """Tests for filtering options (User Story 2)."""

    @patch("src.snapshot.storage.SnapshotStorage.load_snapshot")
    @patch("src.snapshot.storage.SnapshotStorage.get_active_snapshot_name")
    def test_report_with_resource_type_filter(
        self,
        mock_get_active,
        mock_load,
        cli_runner,
        test_snapshot,
    ):
        """Test report with --resource-type filter."""
        mock_get_active.return_value = "test-snapshot"
        mock_load.return_value = test_snapshot

        result = cli_runner.invoke(
            app,
            ["snapshot", "report", "--resource-type", "ec2"],
        )

        assert result.exit_code == 0
        # Should show filtered indicator
        assert "filter" in result.stdout.lower() or "ec2" in result.stdout.lower()

    @patch("src.snapshot.storage.SnapshotStorage.load_snapshot")
    @patch("src.snapshot.storage.SnapshotStorage.get_active_snapshot_name")
    def test_report_with_region_filter(
        self,
        mock_get_active,
        mock_load,
        cli_runner,
        test_snapshot,
    ):
        """Test report with --region filter."""
        mock_get_active.return_value = "test-snapshot"
        mock_load.return_value = test_snapshot

        result = cli_runner.invoke(
            app,
            ["snapshot", "report", "--region", "us-east-1"],
        )

        assert result.exit_code == 0

    @patch("src.snapshot.storage.SnapshotStorage.load_snapshot")
    @patch("src.snapshot.storage.SnapshotStorage.get_active_snapshot_name")
    def test_report_with_multiple_filters(
        self,
        mock_get_active,
        mock_load,
        cli_runner,
        test_snapshot,
    ):
        """Test report with multiple filters combined."""
        mock_get_active.return_value = "test-snapshot"
        mock_load.return_value = test_snapshot

        result = cli_runner.invoke(
            app,
            [
                "snapshot",
                "report",
                "--resource-type",
                "ec2",
                "--resource-type",
                "s3",
                "--region",
                "us-east-1",
            ],
        )

        assert result.exit_code == 0


class TestSnapshotReportCLIExport:
    """Tests for export functionality (User Story 4)."""

    @patch("src.snapshot.storage.SnapshotStorage.load_snapshot")
    @patch("src.snapshot.storage.SnapshotStorage.get_active_snapshot_name")
    def test_export_to_json(
        self,
        mock_get_active,
        mock_load,
        cli_runner,
        test_snapshot,
        tmp_path,
    ):
        """Test export to JSON format."""
        mock_get_active.return_value = "test-snapshot"
        mock_load.return_value = test_snapshot

        output_file = tmp_path / "report.json"
        result = cli_runner.invoke(
            app,
            ["snapshot", "report", "--export", str(output_file)],
        )

        assert result.exit_code == 0
        assert output_file.exists()
        assert "Exported" in result.stdout
        assert "JSON" in result.stdout

    @patch("src.snapshot.storage.SnapshotStorage.load_snapshot")
    @patch("src.snapshot.storage.SnapshotStorage.get_active_snapshot_name")
    def test_export_to_csv(
        self,
        mock_get_active,
        mock_load,
        cli_runner,
        test_snapshot,
        tmp_path,
    ):
        """Test export to CSV format."""
        mock_get_active.return_value = "test-snapshot"
        mock_load.return_value = test_snapshot

        output_file = tmp_path / "resources.csv"
        result = cli_runner.invoke(
            app,
            ["snapshot", "report", "--export", str(output_file)],
        )

        assert result.exit_code == 0
        assert output_file.exists()
        assert "Exported" in result.stdout
        assert "CSV" in result.stdout

    @patch("src.snapshot.storage.SnapshotStorage.load_snapshot")
    @patch("src.snapshot.storage.SnapshotStorage.get_active_snapshot_name")
    def test_export_to_txt(
        self,
        mock_get_active,
        mock_load,
        cli_runner,
        test_snapshot,
        tmp_path,
    ):
        """Test export to TXT format."""
        mock_get_active.return_value = "test-snapshot"
        mock_load.return_value = test_snapshot

        output_file = tmp_path / "summary.txt"
        result = cli_runner.invoke(
            app,
            ["snapshot", "report", "--export", str(output_file)],
        )

        assert result.exit_code == 0
        assert output_file.exists()
        assert "Exported" in result.stdout
        assert "TXT" in result.stdout

    @patch("src.snapshot.storage.SnapshotStorage.load_snapshot")
    @patch("src.snapshot.storage.SnapshotStorage.get_active_snapshot_name")
    def test_export_with_filters(
        self,
        mock_get_active,
        mock_load,
        cli_runner,
        test_snapshot,
        tmp_path,
    ):
        """Test export with filtering applied."""
        mock_get_active.return_value = "test-snapshot"
        mock_load.return_value = test_snapshot

        output_file = tmp_path / "filtered.json"
        result = cli_runner.invoke(
            app,
            [
                "snapshot",
                "report",
                "--resource-type",
                "ec2",
                "--export",
                str(output_file),
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()

    @patch("src.snapshot.storage.SnapshotStorage.load_snapshot")
    @patch("src.snapshot.storage.SnapshotStorage.get_active_snapshot_name")
    def test_export_detailed_mode(
        self,
        mock_get_active,
        mock_load,
        cli_runner,
        test_snapshot,
        tmp_path,
    ):
        """Test export in detailed mode."""
        mock_get_active.return_value = "test-snapshot"
        mock_load.return_value = test_snapshot

        output_file = tmp_path / "detailed.json"
        result = cli_runner.invoke(
            app,
            ["snapshot", "report", "--detailed", "--export", str(output_file)],
        )

        assert result.exit_code == 0
        assert output_file.exists()

    @patch("src.snapshot.storage.SnapshotStorage.load_snapshot")
    @patch("src.snapshot.storage.SnapshotStorage.get_active_snapshot_name")
    def test_export_file_exists_error(
        self,
        mock_get_active,
        mock_load,
        cli_runner,
        test_snapshot,
        tmp_path,
    ):
        """Test export fails when file already exists."""
        mock_get_active.return_value = "test-snapshot"
        mock_load.return_value = test_snapshot

        # Create file first
        output_file = tmp_path / "exists.json"
        output_file.write_text("{}")

        result = cli_runner.invoke(
            app,
            ["snapshot", "report", "--export", str(output_file)],
        )

        assert result.exit_code != 0
        assert "exists" in result.stdout.lower() or "error" in result.stdout.lower()

    @patch("src.snapshot.storage.SnapshotStorage.load_snapshot")
    @patch("src.snapshot.storage.SnapshotStorage.get_active_snapshot_name")
    def test_export_invalid_format(
        self,
        mock_get_active,
        mock_load,
        cli_runner,
        test_snapshot,
        tmp_path,
    ):
        """Test export fails with unsupported format."""
        mock_get_active.return_value = "test-snapshot"
        mock_load.return_value = test_snapshot

        output_file = tmp_path / "report.xlsx"
        result = cli_runner.invoke(
            app,
            ["snapshot", "report", "--export", str(output_file)],
        )

        assert result.exit_code != 0
        assert "format" in result.stdout.lower() or "error" in result.stdout.lower()


class TestSnapshotReportCLIInventoryDefault:
    """Tests for inventory-based snapshot selection."""

    @patch("src.snapshot.storage.SnapshotStorage.load_snapshot")
    @patch("src.snapshot.storage.SnapshotStorage.list_snapshots")
    def test_inventory_defaults_to_most_recent(
        self,
        mock_list_snapshots,
        mock_load_snapshot,
        cli_runner,
        test_snapshot,
    ):
        """Test that specifying --inventory uses the most recent snapshot from that inventory."""
        from datetime import datetime

        # Create two snapshots from same inventory with different dates
        older_snapshot = Snapshot(
            name="snapshot-2025-01-01",
            created_at=datetime(2025, 1, 1, 10, 0, 0),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=test_snapshot.resources,
            inventory_name="prod",
        )

        newer_snapshot = Snapshot(
            name="snapshot-2025-01-15",
            created_at=datetime(2025, 1, 15, 10, 0, 0),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=test_snapshot.resources,
            inventory_name="prod",
        )

        # Mock list_snapshots to return both
        mock_list_snapshots.return_value = [
            {"name": "snapshot-2025-01-01", "modified": datetime(2025, 1, 1)},
            {"name": "snapshot-2025-01-15", "modified": datetime(2025, 1, 15)},
        ]

        # Mock load_snapshot to return appropriate snapshot based on name
        def load_side_effect(name):
            if name == "snapshot-2025-01-01":
                return older_snapshot
            elif name == "snapshot-2025-01-15":
                return newer_snapshot
            raise FileNotFoundError(f"Snapshot {name} not found")

        mock_load_snapshot.side_effect = load_side_effect

        result = cli_runner.invoke(app, ["snapshot", "report", "--inventory", "prod"])

        assert result.exit_code == 0
        # Should use the newer snapshot
        assert "snapshot-2025-01-15" in result.stdout
        # Should show informational message
        assert "Using most recent snapshot" in result.stdout or "snapshot-2025-01-15" in result.stdout

    @patch("src.snapshot.storage.SnapshotStorage.load_snapshot")
    @patch("src.snapshot.storage.SnapshotStorage.list_snapshots")
    def test_inventory_no_snapshots_error(
        self,
        mock_list_snapshots,
        mock_load_snapshot,
        cli_runner,
        test_snapshot,
    ):
        """Test error when inventory has no snapshots."""
        # Mock empty list
        mock_list_snapshots.return_value = []

        result = cli_runner.invoke(app, ["snapshot", "report", "--inventory", "nonexistent"])

        assert result.exit_code != 0
        assert "No snapshots found" in result.stdout or "nonexistent" in result.stdout
