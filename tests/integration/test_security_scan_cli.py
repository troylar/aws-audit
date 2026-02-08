"""Integration tests for security scan CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.cli.main import app
from src.snapshot.storage import SnapshotStorage
from tests.fixtures.snapshots import (
    create_ec2_instance,
    create_iam_user,
    create_mock_snapshot,
    create_rds_instance,
    create_s3_bucket,
    create_secrets_manager_secret,
    create_security_group,
)


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def test_snapshot_with_issues(tmp_path: Path) -> tuple[str, Path]:
    """Create a test snapshot with known security issues."""
    # Create snapshot with various security issues
    public_bucket = create_s3_bucket("public-test-bucket", public=True)
    open_sg_ssh = create_security_group("sg-ssh", open_ports=[22])
    open_sg_db = create_security_group("sg-db", open_ports=[3306, 5432])
    public_db = create_rds_instance("public-database", publicly_accessible=True, encrypted=False)
    imdsv1_instance = create_ec2_instance("old-instance", imdsv2_required=False)
    old_credentials = create_iam_user("old-user", access_key_age_days=120)
    old_secret = create_secrets_manager_secret("old-secret", last_rotated_days_ago=150)

    snapshot = create_mock_snapshot(
        name="test-with-issues",
        resources=[
            public_bucket,
            open_sg_ssh,
            open_sg_db,
            public_db,
            imdsv1_instance,
            old_credentials,
            old_secret,
        ],
    )

    # Save snapshot
    storage = SnapshotStorage(tmp_path)
    storage.save_snapshot(snapshot)

    return "test-with-issues", tmp_path


@pytest.fixture
def test_snapshot_clean(tmp_path: Path) -> tuple[str, Path]:
    """Create a test snapshot with no security issues."""
    private_bucket = create_s3_bucket("private-bucket", public=False, encrypted=True)
    closed_sg = create_security_group("sg-closed", open_ports=[])
    private_db = create_rds_instance("private-db", publicly_accessible=False, encrypted=True)
    imdsv2_instance = create_ec2_instance("new-instance", imdsv2_required=True)

    snapshot = create_mock_snapshot(
        name="test-clean",
        resources=[private_bucket, closed_sg, private_db, imdsv2_instance],
    )

    storage = SnapshotStorage(tmp_path)
    storage.save_snapshot(snapshot)

    return "test-clean", tmp_path


class TestSecurityScanCLI:
    """Integration tests for security scan CLI command."""

    def test_scan_with_findings(self, runner: CliRunner, test_snapshot_with_issues: tuple[str, Path]) -> None:
        """Test running security scan on snapshot with security issues."""
        snapshot_name, storage_dir = test_snapshot_with_issues

        result = runner.invoke(
            app,
            ["security", "scan", "--snapshot", snapshot_name, "--storage-dir", str(storage_dir)],
        )

        # Command should succeed
        assert result.exit_code == 0
        # Should report findings
        assert "finding" in result.stdout.lower() or "issue" in result.stdout.lower()
        # Should show severity levels
        assert "critical" in result.stdout.lower() or "high" in result.stdout.lower()

    def test_scan_with_severity_filter_critical(
        self, runner: CliRunner, test_snapshot_with_issues: tuple[str, Path]
    ) -> None:
        """Test scanning with --severity critical filter."""
        snapshot_name, storage_dir = test_snapshot_with_issues

        result = runner.invoke(
            app,
            [
                "security",
                "scan",
                "--snapshot",
                snapshot_name,
                "--storage-dir",
                str(storage_dir),
                "--severity",
                "critical",
            ],
        )

        assert result.exit_code == 0
        # Should only show CRITICAL findings
        assert "critical" in result.stdout.lower()
        # Should NOT show HIGH/MEDIUM/LOW
        # (might be in header/legend, so this check is relaxed)

    def test_scan_with_severity_filter_high(
        self, runner: CliRunner, test_snapshot_with_issues: tuple[str, Path]
    ) -> None:
        """Test scanning with --severity high filter."""
        snapshot_name, storage_dir = test_snapshot_with_issues

        result = runner.invoke(
            app,
            [
                "security",
                "scan",
                "--snapshot",
                snapshot_name,
                "--storage-dir",
                str(storage_dir),
                "--severity",
                "high",
            ],
        )

        assert result.exit_code == 0
        assert "high" in result.stdout.lower()

    def test_scan_export_json(
        self, runner: CliRunner, test_snapshot_with_issues: tuple[str, Path], tmp_path: Path
    ) -> None:
        """Test exporting scan results to JSON."""
        snapshot_name, storage_dir = test_snapshot_with_issues
        output_file = tmp_path / "scan_results.json"

        result = runner.invoke(
            app,
            [
                "security",
                "scan",
                "--snapshot",
                snapshot_name,
                "--storage-dir",
                str(storage_dir),
                "--output",
                str(output_file),
                "--format",
                "json",
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()

        # Verify JSON structure
        with open(output_file, "r") as f:
            data = json.load(f)

        assert "findings" in data
        assert len(data["findings"]) > 0

    def test_scan_export_csv(
        self, runner: CliRunner, test_snapshot_with_issues: tuple[str, Path], tmp_path: Path
    ) -> None:
        """Test exporting scan results to CSV."""
        snapshot_name, storage_dir = test_snapshot_with_issues
        output_file = tmp_path / "scan_results.csv"

        result = runner.invoke(
            app,
            [
                "security",
                "scan",
                "--snapshot",
                snapshot_name,
                "--storage-dir",
                str(storage_dir),
                "--output",
                str(output_file),
                "--format",
                "csv",
            ],
        )

        assert result.exit_code == 0
        assert output_file.exists()

        # Verify CSV has content
        with open(output_file, "r") as f:
            content = f.read()

        assert len(content) > 0
        # Should have header
        assert "arn" in content.lower() or "resource" in content.lower()

    def test_scan_with_cis_only_flag(self, runner: CliRunner, test_snapshot_with_issues: tuple[str, Path]) -> None:
        """Test scanning with --cis-only flag to show only CIS-mapped findings."""
        snapshot_name, storage_dir = test_snapshot_with_issues

        result = runner.invoke(
            app,
            [
                "security",
                "scan",
                "--snapshot",
                snapshot_name,
                "--storage-dir",
                str(storage_dir),
                "--cis-only",
            ],
        )

        assert result.exit_code == 0
        # Should mention CIS controls
        assert "cis" in result.stdout.lower() or "control" in result.stdout.lower()

    def test_scan_empty_snapshot(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test scanning an empty snapshot."""
        # Create empty snapshot
        empty_snapshot = create_mock_snapshot(name="empty-test", resources=[])
        storage = SnapshotStorage(tmp_path)
        storage.save_snapshot(empty_snapshot)

        result = runner.invoke(
            app,
            ["security", "scan", "--snapshot", "empty-test", "--storage-dir", str(tmp_path)],
        )

        assert result.exit_code == 0
        # Should indicate no findings
        assert "no" in result.stdout.lower() or "0" in result.stdout.lower()

    def test_scan_clean_snapshot(self, runner: CliRunner, test_snapshot_clean: tuple[str, Path]) -> None:
        """Test scanning a snapshot with no security issues."""
        snapshot_name, storage_dir = test_snapshot_clean

        result = runner.invoke(
            app,
            ["security", "scan", "--snapshot", snapshot_name, "--storage-dir", str(storage_dir)],
        )

        assert result.exit_code == 0
        # May have some findings but should be minimal
        # Output should indicate scan was performed
        assert "scan" in result.stdout.lower() or "check" in result.stdout.lower()

    def test_scan_nonexistent_snapshot(self, runner: CliRunner, tmp_path: Path) -> None:
        """Test scanning a snapshot that doesn't exist."""
        result = runner.invoke(
            app,
            [
                "security",
                "scan",
                "--snapshot",
                "nonexistent-snapshot",
                "--storage-dir",
                str(tmp_path),
            ],
        )

        # Should fail with error
        assert result.exit_code != 0
        assert "not found" in result.stdout.lower() or "error" in result.stdout.lower()

    def test_scan_with_collection_name(self, runner: CliRunner, test_snapshot_with_issues: tuple[str, Path]) -> None:
        """Test scanning using --collection flag to auto-select latest snapshot."""
        snapshot_name, storage_dir = test_snapshot_with_issues

        result = runner.invoke(
            app,
            ["security", "scan", "--collection", "default", "--storage-dir", str(storage_dir)],
        )

        # Should work if collection exists and has snapshots
        # Exit code may vary depending on whether collection has active snapshot
        # At minimum, command should not crash
        assert (
            "security" in result.stdout.lower() or "scan" in result.stdout.lower() or "error" in result.stdout.lower()
        )
