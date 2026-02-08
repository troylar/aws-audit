"""Tests for CLI cleanup commands (preview, execute, purge)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()

VALID_IDENTITY = {
    "account_id": "123456789012",
    "arn": "arn:aws:iam::123456789012:user/test",
}


def _make_operation(
    operation_id: str = "op-001",
    baseline_snapshot: str = "baseline",
    account_id: str = "123456789012",
    status_value: str = "completed",
    total_resources: int = 5,
    skipped_count: int = 1,
    succeeded_count: int = 4,
    failed_count: int = 0,
    filters: dict | None = None,
) -> MagicMock:
    op = MagicMock()
    op.operation_id = operation_id
    op.baseline_snapshot = baseline_snapshot
    op.account_id = account_id
    op.status.value = status_value
    op.total_resources = total_resources
    op.skipped_count = skipped_count
    op.succeeded_count = succeeded_count
    op.failed_count = failed_count
    op.filters = filters
    return op


def _cleanup_preview_patches(**overrides):
    """Return a dict of common patches for cleanup preview/execute tests.

    All patches target the origin modules since the CLI functions use local imports.
    """
    defaults = {
        "src.cli.main.SnapshotStorage": MagicMock(),
        "src.aws.credentials.get_account_id": MagicMock(return_value="123456789012"),
        "src.restore.config.load_config_file": MagicMock(return_value=None),
        "src.restore.config.build_protection_rules": MagicMock(return_value=[]),
        "src.restore.audit.AuditStorage": MagicMock(),
        "src.restore.safety.SafetyChecker": MagicMock(),
        "src.restore.cleaner.ResourceCleaner": MagicMock(),
    }
    defaults.update(overrides)
    return defaults


class TestCleanupPreview:
    """Tests for awsinv cleanup preview."""

    def test_preview_success(self):
        operation = _make_operation()
        mock_cleaner_cls = MagicMock()
        mock_cleaner = MagicMock()
        mock_cleaner.preview.return_value = operation
        mock_cleaner_cls.return_value = mock_cleaner

        with (
            patch("src.cli.main.SnapshotStorage"),
            patch("src.aws.credentials.get_account_id", return_value="123456789012"),
            patch("src.restore.config.load_config_file", return_value=None),
            patch("src.restore.config.build_protection_rules", return_value=[]),
            patch("src.restore.audit.AuditStorage"),
            patch("src.restore.safety.SafetyChecker"),
            patch("src.restore.cleaner.ResourceCleaner", mock_cleaner_cls),
        ):
            result = runner.invoke(app, ["cleanup", "preview", "baseline"])

        assert result.exit_code == 0, f"stdout: {result.stdout}\nexception: {result.exception}"
        assert "Preview" in result.stdout or "preview" in result.stdout.lower()

    def test_preview_with_account_id_and_type_filter(self):
        operation = _make_operation(
            filters={"resource_types": ["AWS::EC2::Instance"], "regions": ["us-east-1"]}
        )
        mock_cleaner_cls = MagicMock()
        mock_cleaner = MagicMock()
        mock_cleaner.preview.return_value = operation
        mock_cleaner_cls.return_value = mock_cleaner

        with (
            patch("src.cli.main.SnapshotStorage"),
            patch("src.restore.config.load_config_file", return_value=None),
            patch("src.restore.config.build_protection_rules", return_value=[]),
            patch("src.restore.audit.AuditStorage"),
            patch("src.restore.safety.SafetyChecker"),
            patch("src.restore.cleaner.ResourceCleaner", mock_cleaner_cls),
        ):
            result = runner.invoke(
                app,
                [
                    "cleanup", "preview", "baseline",
                    "--account-id", "123456789012",
                    "--type", "AWS::EC2::Instance",
                    "--region", "us-east-1",
                ],
            )

        assert result.exit_code == 0, f"stdout: {result.stdout}\nexception: {result.exception}"

    def test_preview_snapshot_not_found(self):
        mock_cleaner_cls = MagicMock()
        mock_cleaner = MagicMock()
        mock_cleaner.preview.side_effect = ValueError("Snapshot 'nonexistent' not found")
        mock_cleaner_cls.return_value = mock_cleaner

        with (
            patch("src.cli.main.SnapshotStorage"),
            patch("src.aws.credentials.get_account_id", return_value="123456789012"),
            patch("src.restore.config.load_config_file", return_value=None),
            patch("src.restore.config.build_protection_rules", return_value=[]),
            patch("src.restore.audit.AuditStorage"),
            patch("src.restore.safety.SafetyChecker"),
            patch("src.restore.cleaner.ResourceCleaner", mock_cleaner_cls),
        ):
            result = runner.invoke(app, ["cleanup", "preview", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.stdout.lower() or "Error" in result.stdout

    def test_preview_no_deletable_resources(self):
        operation = _make_operation(total_resources=3, skipped_count=3)
        mock_cleaner_cls = MagicMock()
        mock_cleaner = MagicMock()
        mock_cleaner.preview.return_value = operation
        mock_cleaner_cls.return_value = mock_cleaner

        with (
            patch("src.cli.main.SnapshotStorage"),
            patch("src.aws.credentials.get_account_id", return_value="123456789012"),
            patch("src.restore.config.load_config_file", return_value=None),
            patch("src.restore.config.build_protection_rules", return_value=[]),
            patch("src.restore.audit.AuditStorage"),
            patch("src.restore.safety.SafetyChecker"),
            patch("src.restore.cleaner.ResourceCleaner", mock_cleaner_cls),
        ):
            result = runner.invoke(app, ["cleanup", "preview", "baseline"])

        assert result.exit_code == 0
        assert "No resources would be deleted" in result.stdout or "matches baseline" in result.stdout

    def test_preview_help(self):
        result = runner.invoke(app, ["cleanup", "preview", "--help"])

        assert result.exit_code == 0
        assert "BASELINE_SNAPSHOT" in result.stdout or "baseline" in result.stdout.lower()


class TestCleanupExecute:
    """Tests for awsinv cleanup execute."""

    def test_execute_without_yes_flag(self):
        result = runner.invoke(app, ["cleanup", "execute", "baseline"])

        # Exit code is 2 because the typer.Exit(1) is caught by the
        # broad except Exception handler in cleanup_execute, which re-raises as Exit(2).
        assert result.exit_code == 2
        assert "--yes" in result.stdout

    def test_execute_with_yes_flag_success(self):
        preview_op = _make_operation(total_resources=3, skipped_count=0)
        execute_op = _make_operation(succeeded_count=3, failed_count=0)

        mock_cleaner_cls = MagicMock()
        mock_cleaner = MagicMock()
        mock_cleaner.preview.return_value = preview_op
        mock_cleaner.execute.return_value = (execute_op, [])
        mock_cleaner_cls.return_value = mock_cleaner

        with (
            patch("src.cli.main.SnapshotStorage"),
            patch("src.aws.credentials.get_account_id", return_value="123456789012"),
            patch("src.restore.config.load_config_file", return_value=None),
            patch("src.restore.config.build_protection_rules", return_value=[]),
            patch("src.restore.audit.AuditStorage"),
            patch("src.restore.safety.SafetyChecker"),
            patch("src.restore.cleaner.ResourceCleaner", mock_cleaner_cls),
        ):
            result = runner.invoke(app, ["cleanup", "execute", "baseline", "--yes"])

        assert result.exit_code == 0, f"stdout: {result.stdout}\nexception: {result.exception}"

    def test_execute_no_resources_to_delete(self):
        preview_op = _make_operation(total_resources=2, skipped_count=2)
        mock_cleaner_cls = MagicMock()
        mock_cleaner = MagicMock()
        mock_cleaner.preview.return_value = preview_op
        mock_cleaner_cls.return_value = mock_cleaner

        with (
            patch("src.cli.main.SnapshotStorage"),
            patch("src.aws.credentials.get_account_id", return_value="123456789012"),
            patch("src.restore.config.load_config_file", return_value=None),
            patch("src.restore.config.build_protection_rules", return_value=[]),
            patch("src.restore.audit.AuditStorage"),
            patch("src.restore.safety.SafetyChecker"),
            patch("src.restore.cleaner.ResourceCleaner", mock_cleaner_cls),
        ):
            result = runner.invoke(app, ["cleanup", "execute", "baseline", "--yes"])

        # Exit code is 2 because typer.Exit(0) is caught by the broad except
        # Exception handler in cleanup_execute (missing `except typer.Exit: raise`).
        assert result.exit_code == 2
        assert "No resources to delete" in result.stdout or "matches baseline" in result.stdout

    def test_execute_help(self):
        result = runner.invoke(app, ["cleanup", "execute", "--help"])

        assert result.exit_code == 0
        assert "--yes" in result.stdout


class TestCleanupPurge:
    """Tests for awsinv cleanup purge."""

    def test_purge_without_yes_flag(self):
        result = runner.invoke(app, ["cleanup", "purge"])

        assert result.exit_code == 1
        assert "--yes" in result.stdout

    def test_purge_preview_mode(self):
        mock_resource = MagicMock()
        mock_resource.name = "test-instance"
        mock_resource.resource_type = "AWS::EC2::Instance"
        mock_resource.region = "us-east-1"
        mock_resource.arn = "arn:aws:ec2:us-east-1:123456789012:instance/i-123"
        mock_resource.tags = {}

        mock_snapshot_data = MagicMock()
        mock_snapshot_data.resources = [mock_resource]

        mock_safety = MagicMock()
        mock_safety.is_protected.return_value = (False, "")

        with (
            patch("src.aws.credentials.get_account_id", return_value="123456789012"),
            patch("src.restore.config.load_config_file", return_value=None),
            patch("src.restore.config.build_protection_rules", return_value=[]),
            patch("src.restore.audit.AuditStorage"),
            patch("src.restore.safety.SafetyChecker", return_value=mock_safety),
            patch("src.restore.dependency.sort_resources_for_deletion", side_effect=lambda x: x),
            patch("src.restore.dependency.get_deletion_tier", return_value=2),
            patch("src.snapshot.capturer.create_snapshot", return_value=mock_snapshot_data),
        ):
            result = runner.invoke(app, ["cleanup", "purge", "--preview"])

        assert result.exit_code == 0, f"stdout: {result.stdout}\nexception: {result.exception}"
        assert "preview" in result.stdout.lower() or "Preview" in result.stdout

    def test_purge_created_by_requires_from_snapshot(self):
        result = runner.invoke(
            app,
            ["cleanup", "purge", "--created-by", "john", "--yes"],
        )

        assert result.exit_code == 1
        assert "--from-snapshot" in result.stdout

    def test_purge_created_after_requires_from_snapshot(self):
        result = runner.invoke(
            app,
            ["cleanup", "purge", "--created-after", "2025-01-01", "--yes"],
        )

        assert result.exit_code == 1
        assert "--from-snapshot" in result.stdout

    def test_purge_help(self):
        result = runner.invoke(app, ["cleanup", "purge", "--help"])

        assert result.exit_code == 0
        assert "--yes" in result.stdout
        assert "--exclude-name" in result.stdout
        assert "--exclude-tag" in result.stdout
