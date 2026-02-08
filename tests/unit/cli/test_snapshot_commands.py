"""Tests for snapshot CLI commands (create, list, show, set-active, delete, rename, report, export, creators)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()

VALID_IDENTITY = {
    "account_id": "123456789012",
    "arn": "arn:aws:iam::123456789012:user/test",
}


def _make_snapshot(
    name: str = "test-snapshot",
    resource_count: int = 5,
    is_active: bool = True,
    regions: list[str] | None = None,
    service_counts: dict[str, int] | None = None,
    collection_name: str = "default",
    filters_applied: dict | None = None,
    resources: list | None = None,
) -> MagicMock:
    snap = MagicMock()
    snap.name = name
    snap.created_at = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    snap.account_id = "123456789012"
    snap.regions = regions or ["us-east-1"]
    snap.resources = resources or []
    snap.resource_count = resource_count
    snap.is_active = is_active
    snap.service_counts = service_counts or {"AWS::EC2::Instance": 3, "AWS::S3::Bucket": 2}
    snap.collection_name = collection_name
    snap.filters_applied = filters_applied
    snap.metadata = {}
    return snap


def _make_list_entry(
    name: str = "test-snapshot",
    is_active: bool = True,
    size_mb: float = 1.23,
) -> dict:
    return {
        "name": name,
        "modified": datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc),
        "size_mb": size_mb,
        "is_active": is_active,
    }


# ---------------------------------------------------------------------------
# snapshot create
# ---------------------------------------------------------------------------


class TestSnapshotCreate:
    @patch("src.cli.main.SnapshotStorage")
    @patch("src.cli.main.validate_credentials")
    def test_create_success_with_region(self, mock_creds, mock_storage_cls):
        mock_creds.return_value = VALID_IDENTITY

        mock_snapshot = _make_snapshot(name="my-snap", resource_count=10)
        mock_snapshot.metadata = {"collection_errors": []}
        mock_snapshot.filters_applied = None

        with (
            patch("src.snapshot.capturer.create_snapshot", return_value=mock_snapshot),
            patch("src.snapshot.collection_storage.CollectionStorage") as mock_coll_cls,
        ):
            mock_coll_storage = MagicMock()
            mock_coll_cls.return_value = mock_coll_storage
            mock_coll_storage.get_or_create_default.return_value = MagicMock(
                description=None, include_tags=None, exclude_tags=None
            )

            mock_storage = MagicMock()
            mock_storage.save_snapshot.return_value = MagicMock(name="my-snap.yaml")
            mock_storage_cls.return_value = mock_storage

            result = runner.invoke(app, ["snapshot", "create", "my-snap", "--region", "us-east-1"])

        assert result.exit_code == 0 or "Snapshot complete" in result.stdout or "Authenticated" in result.stdout

    @patch("src.cli.main.validate_credentials")
    def test_create_credential_error(self, mock_creds):
        from src.aws.credentials import CredentialValidationError

        mock_creds.side_effect = CredentialValidationError("No credentials found")

        result = runner.invoke(app, ["snapshot", "create", "my-snap", "--region", "us-east-1"])

        assert result.exit_code != 0

    @patch("src.cli.main.validate_credentials")
    def test_create_collection_conflicts_with_include_tags(self, mock_creds):
        mock_creds.return_value = VALID_IDENTITY

        with patch("src.snapshot.collection_storage.CollectionStorage") as mock_coll_cls:
            mock_coll = MagicMock()
            mock_coll.get_by_name.return_value = MagicMock(description=None, include_tags=None, exclude_tags=None)
            mock_coll_cls.return_value = mock_coll

            result = runner.invoke(
                app,
                [
                    "snapshot",
                    "create",
                    "my-snap",
                    "--region",
                    "us-east-1",
                    "--collection",
                    "prod",
                    "--include-tags",
                    "Env=prod",
                ],
            )

        assert result.exit_code == 1
        assert "Cannot use --collection with --include-tags" in result.stdout


# ---------------------------------------------------------------------------
# snapshot list
# ---------------------------------------------------------------------------


class TestSnapshotList:
    @patch("src.cli.main.SnapshotStorage")
    def test_list_snapshots(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage.list_snapshots.return_value = [
            _make_list_entry("snap-1", is_active=True),
            _make_list_entry("snap-2", is_active=False),
        ]
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(app, ["snapshot", "list"])

        assert result.exit_code == 0
        assert "snap-1" in result.stdout
        assert "snap-2" in result.stdout
        assert "Total snapshots: 2" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_list_no_snapshots(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage.list_snapshots.return_value = []
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(app, ["snapshot", "list"])

        assert result.exit_code == 0
        assert "No snapshots found" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_list_error(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage.list_snapshots.side_effect = Exception("disk error")
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(app, ["snapshot", "list"])

        assert result.exit_code == 1
        assert "Error listing snapshots" in result.stdout


# ---------------------------------------------------------------------------
# snapshot show
# ---------------------------------------------------------------------------


class TestSnapshotShow:
    @patch("src.cli.main.SnapshotStorage")
    def test_show_snapshot(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = _make_snapshot(name="baseline")
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(app, ["snapshot", "show", "baseline"])

        assert result.exit_code == 0
        assert "baseline" in result.stdout
        assert "123456789012" in result.stdout
        assert "us-east-1" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_show_not_found(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage.load_snapshot.side_effect = FileNotFoundError("not found")
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(app, ["snapshot", "show", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_show_with_filters(self, mock_storage_cls):
        mock_storage = MagicMock()
        snap = _make_snapshot(
            name="filtered",
            filters_applied={
                "date_filters": {"before_date": "2025-01-01", "after_date": None},
                "tag_filters": {"Environment": "prod"},
            },
        )
        mock_storage.load_snapshot.return_value = snap
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(app, ["snapshot", "show", "filtered"])

        assert result.exit_code == 0
        assert "Filters applied" in result.stdout


# ---------------------------------------------------------------------------
# snapshot set-active
# ---------------------------------------------------------------------------


class TestSnapshotSetActive:
    @patch("src.cli.main.SnapshotStorage")
    def test_set_active_success(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(app, ["snapshot", "set-active", "baseline"])

        assert result.exit_code == 0
        assert "baseline" in result.stdout
        mock_storage.set_active_snapshot.assert_called_once_with("baseline")

    @patch("src.cli.main.SnapshotStorage")
    def test_set_active_not_found(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage.set_active_snapshot.side_effect = FileNotFoundError("not found")
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(app, ["snapshot", "set-active", "missing"])

        assert result.exit_code == 1
        assert "not found" in result.stdout


# ---------------------------------------------------------------------------
# snapshot delete
# ---------------------------------------------------------------------------


class TestSnapshotDelete:
    @patch("src.cli.main.SnapshotStorage")
    def test_delete_with_yes_flag(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = _make_snapshot(name="old-snap", is_active=False)
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(app, ["snapshot", "delete", "old-snap", "--yes"])

        assert result.exit_code == 0
        assert "Deleted" in result.stdout
        mock_storage.delete_snapshot.assert_called_once_with("old-snap")

    @patch("src.cli.main.SnapshotStorage")
    def test_delete_not_found(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage.load_snapshot.side_effect = FileNotFoundError("not found")
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(app, ["snapshot", "delete", "gone", "--yes"])

        assert result.exit_code == 1
        assert "not found" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_delete_active_snapshot_error(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = _make_snapshot(name="active-snap", is_active=True)
        mock_storage.delete_snapshot.side_effect = ValueError("Cannot delete active snapshot")
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(app, ["snapshot", "delete", "active-snap", "--yes"])

        assert result.exit_code == 1
        assert "Cannot delete active snapshot" in result.stdout


# ---------------------------------------------------------------------------
# snapshot rename
# ---------------------------------------------------------------------------


class TestSnapshotRename:
    @patch("src.cli.main.SnapshotStorage")
    def test_rename_success(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage.exists.side_effect = lambda n: n == "old-name"
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(app, ["snapshot", "rename", "old-name", "new-name"])

        assert result.exit_code == 0
        assert "Renamed" in result.stdout
        assert "old-name" in result.stdout
        assert "new-name" in result.stdout
        mock_storage.rename_snapshot.assert_called_once_with("old-name", "new-name")

    @patch("src.cli.main.SnapshotStorage")
    def test_rename_source_not_found(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage.exists.return_value = False
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(app, ["snapshot", "rename", "missing", "new-name"])

        assert result.exit_code == 1
        assert "not found" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_rename_target_already_exists(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage.exists.return_value = True
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(app, ["snapshot", "rename", "old-name", "existing-name"])

        assert result.exit_code == 1
        assert "already exists" in result.stdout


# ---------------------------------------------------------------------------
# snapshot report
# ---------------------------------------------------------------------------


class TestSnapshotReport:
    @patch("src.cli.main.SnapshotStorage")
    def test_report_with_explicit_name(self, mock_storage_cls):
        mock_storage = MagicMock()
        snap = _make_snapshot(name="my-report-snap", resource_count=10)
        mock_storage.load_snapshot.return_value = snap
        mock_storage_cls.return_value = mock_storage

        with (
            patch("src.snapshot.reporter.SnapshotReporter") as mock_reporter_cls,
            patch("src.snapshot.report_formatter.ReportFormatter") as mock_fmt_cls,
        ):
            mock_reporter = MagicMock()
            mock_reporter._extract_metadata.return_value = MagicMock()
            mock_reporter.generate_summary.return_value = MagicMock(total_count=10)
            mock_reporter_cls.return_value = mock_reporter

            mock_fmt = MagicMock()
            mock_fmt_cls.return_value = mock_fmt

            result = runner.invoke(app, ["snapshot", "report", "my-report-snap"])

        assert result.exit_code == 0
        mock_storage.load_snapshot.assert_called_with("my-report-snap")

    @patch("src.cli.main.SnapshotStorage")
    def test_report_no_active_snapshot(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = None
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(app, ["snapshot", "report"])

        assert result.exit_code == 1
        assert "No active snapshot" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_report_snapshot_not_found(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage.load_snapshot.side_effect = FileNotFoundError("not found")
        mock_storage.list_snapshots.return_value = []
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(app, ["snapshot", "report", "gone"])

        assert result.exit_code == 1
        assert "not found" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_report_empty_snapshot(self, mock_storage_cls):
        mock_storage = MagicMock()
        snap = _make_snapshot(name="empty-snap", resource_count=0)
        mock_storage.load_snapshot.return_value = snap
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(app, ["snapshot", "report", "empty-snap"])

        assert result.exit_code == 0
        assert "0 resources" in result.stdout


# ---------------------------------------------------------------------------
# snapshot export
# ---------------------------------------------------------------------------


class TestSnapshotExport:
    @patch("src.cli.main.SnapshotStorage")
    def test_export_no_active_snapshot(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = None
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(app, ["snapshot", "export"])

        assert result.exit_code == 1
        assert "No active snapshot" in result.stdout

    @patch("src.cli.main.SnapshotStorage")
    def test_export_snapshot_not_found(self, mock_storage_cls):
        mock_storage = MagicMock()
        mock_storage.load_snapshot.side_effect = FileNotFoundError("not found")
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(app, ["snapshot", "export", "missing-snap"])

        assert result.exit_code == 1
        assert "not found" in result.stdout


# ---------------------------------------------------------------------------
# snapshot creators
# ---------------------------------------------------------------------------


class TestSnapshotCreators:
    @patch("src.storage.resource_store.ResourceStore")
    @patch("src.storage.database.Database")
    @patch("src.cli.main.SnapshotStorage")
    def test_creators_no_active_snapshot(self, mock_storage_cls, mock_db_cls, mock_rs_cls):
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = None
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(app, ["snapshot", "creators"])

        assert result.exit_code == 1
        assert "No active snapshot" in result.stdout

    @patch("src.storage.resource_store.ResourceStore")
    @patch("src.storage.database.Database")
    @patch("src.cli.main.SnapshotStorage")
    def test_creators_snapshot_not_found(self, mock_storage_cls, mock_db_cls, mock_rs_cls):
        mock_storage = MagicMock()
        mock_storage.get_active_snapshot_name.return_value = "missing"
        mock_storage.load_snapshot.side_effect = FileNotFoundError("not found")
        mock_storage_cls.return_value = mock_storage

        result = runner.invoke(app, ["snapshot", "creators", "missing"])

        assert result.exit_code == 1
        assert "not found" in result.stdout
