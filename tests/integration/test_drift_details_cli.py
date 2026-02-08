"""Integration tests for drift details CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.cli.main import app
from src.snapshot.storage import SnapshotStorage
from tests.fixtures.snapshots import (
    create_ec2_instance,
    create_mock_snapshot,
    create_rds_instance,
    create_s3_bucket,
    create_security_group,
)

pytestmark = pytest.mark.skip(
    reason="Integration tests require AWS access or mocking infrastructure. Unit tests provide coverage."
)


@pytest.fixture
def runner() -> CliRunner:
    """Create CLI test runner."""
    return CliRunner()


@pytest.fixture
def baseline_snapshot(tmp_path: Path) -> tuple[str, Path]:
    """Create a baseline snapshot."""
    # Create baseline resources
    bucket = create_s3_bucket("test-bucket", public=False, encrypted=False)
    instance = create_ec2_instance("test-instance", instance_type="t2.micro", tags={"Environment": "dev"})
    db = create_rds_instance("test-db", publicly_accessible=False, encrypted=False)
    sg = create_security_group("sg-baseline", open_ports=[])

    snapshot = create_mock_snapshot(
        name="baseline",
        resources=[bucket, instance, db, sg],
    )

    storage = SnapshotStorage(tmp_path)
    storage.save_snapshot(snapshot)

    return "baseline", tmp_path


@pytest.fixture
def modified_snapshot(tmp_path: Path) -> tuple[str, Path]:
    """Create a modified snapshot with changes."""
    # Create modified resources with changes:
    # 1. Tag change on instance
    # 2. Instance type change
    # 3. RDS made public (security change)
    # 4. Encryption enabled on bucket
    bucket = create_s3_bucket("test-bucket", public=False, encrypted=True)  # Encryption added
    instance = create_ec2_instance(
        "test-instance",
        instance_type="t2.small",  # Changed from t2.micro
        tags={"Environment": "prod"},  # Changed from dev
    )
    db = create_rds_instance(
        "test-db",
        publicly_accessible=True,  # Changed from False - SECURITY!
        encrypted=False,
    )
    sg = create_security_group("sg-baseline", open_ports=[22])  # Added SSH - SECURITY!

    snapshot = create_mock_snapshot(
        name="modified",
        resources=[bucket, instance, db, sg],
    )

    storage = SnapshotStorage(tmp_path)
    storage.save_snapshot(snapshot)

    return "modified", tmp_path


class TestDriftDetailsCLI:
    """Integration tests for drift details CLI command."""

    def test_delta_without_show_diff_flag(
        self,
        runner: CliRunner,
        baseline_snapshot: tuple[str, Path],
        modified_snapshot: tuple[str, Path],
        tmp_path: Path,
    ) -> None:
        """Test delta command WITHOUT --show-diff flag (backward compatibility)."""
        # This test ensures existing delta behavior is unchanged
        # We need both snapshots in same storage
        baseline_name, _ = baseline_snapshot
        modified_name, _ = modified_snapshot

        # Copy both to tmp_path
        storage = SnapshotStorage(tmp_path)
        base_storage = SnapshotStorage(baseline_snapshot[1])
        mod_storage = SnapshotStorage(modified_snapshot[1])

        base_snap = base_storage.load_snapshot(baseline_name)
        mod_snap = mod_storage.load_snapshot(modified_name)

        storage.save_snapshot(base_snap)
        storage.save_snapshot(mod_snap)

        # Mock current AWS state by loading modified snapshot
        # (This test would need actual AWS mocking in real scenario)
        # For now, just verify command doesn't break without --show-diff

        # Command should work without --show-diff
        result = runner.invoke(
            app,
            ["delta", "--snapshot", baseline_name, "--storage-path", str(tmp_path)],
            env={"AWS_PROFILE": "test"},
        )

        # Should not show drift details (only resource-level changes)
        # This is basic delta output, NOT field-level changes
        assert "InstanceType" not in result.stdout  # Field-level detail shouldn't appear

    def test_delta_with_show_diff_flag_displays_changes(
        self,
        runner: CliRunner,
        baseline_snapshot: tuple[str, Path],
        modified_snapshot: tuple[str, Path],
        tmp_path: Path,
    ) -> None:
        """Test delta --show-diff shows field-level configuration changes."""
        baseline_name, _ = baseline_snapshot
        modified_name, _ = modified_snapshot

        # Copy both to tmp_path
        storage = SnapshotStorage(tmp_path)
        base_storage = SnapshotStorage(baseline_snapshot[1])
        mod_storage = SnapshotStorage(modified_snapshot[1])

        base_snap = base_storage.load_snapshot(baseline_name)
        mod_snap = mod_storage.load_snapshot(modified_name)

        storage.save_snapshot(base_snap)
        storage.save_snapshot(mod_snap)

        # Run with --show-diff flag
        result = runner.invoke(
            app,
            ["delta", "--snapshot", baseline_name, "--storage-path", str(tmp_path), "--show-diff"],
            env={"AWS_PROFILE": "test"},
        )

        # Should show field-level changes
        assert result.exit_code == 0
        # Should show specific field changes
        assert "InstanceType" in result.stdout or "Environment" in result.stdout
        # Should show old → new format
        assert "→" in result.stdout or "->" in result.stdout

    def test_delta_show_diff_with_resource_type_filter(
        self,
        runner: CliRunner,
        baseline_snapshot: tuple[str, Path],
        modified_snapshot: tuple[str, Path],
        tmp_path: Path,
    ) -> None:
        """Test delta --show-diff --resource-type ec2 filters to EC2 changes only."""
        baseline_name, _ = baseline_snapshot
        modified_name, _ = modified_snapshot

        storage = SnapshotStorage(tmp_path)
        base_storage = SnapshotStorage(baseline_snapshot[1])
        mod_storage = SnapshotStorage(modified_snapshot[1])

        base_snap = base_storage.load_snapshot(baseline_name)
        mod_snap = mod_storage.load_snapshot(modified_name)

        storage.save_snapshot(base_snap)
        storage.save_snapshot(mod_snap)

        result = runner.invoke(
            app,
            [
                "delta",
                "--snapshot",
                baseline_name,
                "--storage-path",
                str(tmp_path),
                "--show-diff",
                "--type",
                "ec2",
            ],
            env={"AWS_PROFILE": "test"},
        )

        assert result.exit_code == 0
        # Should show EC2 instance changes
        assert "InstanceType" in result.stdout or "instance" in result.stdout.lower()
        # Should NOT show RDS changes
        assert "PubliclyAccessible" not in result.stdout

    def test_delta_show_diff_with_region_filter(
        self,
        runner: CliRunner,
        baseline_snapshot: tuple[str, Path],
        modified_snapshot: tuple[str, Path],
        tmp_path: Path,
    ) -> None:
        """Test delta --show-diff --region us-east-1 filters by region."""
        baseline_name, _ = baseline_snapshot
        modified_name, _ = modified_snapshot

        storage = SnapshotStorage(tmp_path)
        base_storage = SnapshotStorage(baseline_snapshot[1])
        mod_storage = SnapshotStorage(modified_snapshot[1])

        base_snap = base_storage.load_snapshot(baseline_name)
        mod_snap = mod_storage.load_snapshot(modified_name)

        storage.save_snapshot(base_snap)
        storage.save_snapshot(mod_snap)

        result = runner.invoke(
            app,
            [
                "delta",
                "--snapshot",
                baseline_name,
                "--storage-path",
                str(tmp_path),
                "--show-diff",
                "--region",
                "us-east-1",
            ],
            env={"AWS_PROFILE": "test"},
        )

        assert result.exit_code == 0
        # Should show changes for us-east-1 resources
        assert result.stdout  # Should have output

    def test_delta_show_diff_export_json(
        self,
        runner: CliRunner,
        baseline_snapshot: tuple[str, Path],
        modified_snapshot: tuple[str, Path],
        tmp_path: Path,
    ) -> None:
        """Test delta --show-diff --export JSON includes drift details."""
        baseline_name, _ = baseline_snapshot
        modified_name, _ = modified_snapshot

        storage = SnapshotStorage(tmp_path)
        base_storage = SnapshotStorage(baseline_snapshot[1])
        mod_storage = SnapshotStorage(modified_snapshot[1])

        base_snap = base_storage.load_snapshot(baseline_name)
        mod_snap = mod_storage.load_snapshot(modified_name)

        storage.save_snapshot(base_snap)
        storage.save_snapshot(mod_snap)

        export_file = tmp_path / "drift_export.json"

        result = runner.invoke(
            app,
            [
                "delta",
                "--snapshot",
                baseline_name,
                "--storage-path",
                str(tmp_path),
                "--show-diff",
                "--output",
                str(export_file),
            ],
            env={"AWS_PROFILE": "test"},
        )

        assert result.exit_code == 0
        assert export_file.exists()

        # Verify JSON contains drift details
        with open(export_file) as f:
            data = json.load(f)

        # Should have drift_details field
        assert "drift_details" in data or "configuration_changes" in data
        # Should include field_path, old_value, new_value, category
        # (exact structure depends on implementation)

    def test_delta_show_diff_with_identical_snapshots(
        self,
        runner: CliRunner,
        baseline_snapshot: tuple[str, Path],
        tmp_path: Path,
    ) -> None:
        """Test delta --show-diff when snapshots are identical shows no changes."""
        baseline_name, _ = baseline_snapshot

        storage = SnapshotStorage(tmp_path)
        base_storage = SnapshotStorage(baseline_snapshot[1])
        base_snap = base_storage.load_snapshot(baseline_name)
        storage.save_snapshot(base_snap)

        # Compare snapshot to itself
        result = runner.invoke(
            app,
            ["delta", "--snapshot", baseline_name, "--storage-path", str(tmp_path), "--show-diff"],
            env={"AWS_PROFILE": "test"},
        )

        assert result.exit_code == 0
        # Should indicate no changes
        assert "no changes" in result.stdout.lower() or "0 changes" in result.stdout.lower()

    def test_delta_show_diff_categorizes_security_changes(
        self,
        runner: CliRunner,
        baseline_snapshot: tuple[str, Path],
        modified_snapshot: tuple[str, Path],
        tmp_path: Path,
    ) -> None:
        """Test that security-critical changes are highlighted."""
        baseline_name, _ = baseline_snapshot
        modified_name, _ = modified_snapshot

        storage = SnapshotStorage(tmp_path)
        base_storage = SnapshotStorage(baseline_snapshot[1])
        mod_storage = SnapshotStorage(modified_snapshot[1])

        base_snap = base_storage.load_snapshot(baseline_name)
        mod_snap = mod_storage.load_snapshot(modified_name)

        storage.save_snapshot(base_snap)
        storage.save_snapshot(mod_snap)

        result = runner.invoke(
            app,
            ["delta", "--snapshot", baseline_name, "--storage-path", str(tmp_path), "--show-diff"],
            env={"AWS_PROFILE": "test"},
        )

        assert result.exit_code == 0
        # Should highlight security changes
        # PubliclyAccessible change should be flagged
        assert "Security" in result.stdout or "SECURITY" in result.stdout or "PubliclyAccessible" in result.stdout

    def test_delta_show_diff_shows_tag_changes(
        self,
        runner: CliRunner,
        baseline_snapshot: tuple[str, Path],
        modified_snapshot: tuple[str, Path],
        tmp_path: Path,
    ) -> None:
        """Test that tag changes are properly displayed."""
        baseline_name, _ = baseline_snapshot
        modified_name, _ = modified_snapshot

        storage = SnapshotStorage(tmp_path)
        base_storage = SnapshotStorage(baseline_snapshot[1])
        mod_storage = SnapshotStorage(modified_snapshot[1])

        base_snap = base_storage.load_snapshot(baseline_name)
        mod_snap = mod_storage.load_snapshot(modified_name)

        storage.save_snapshot(base_snap)
        storage.save_snapshot(mod_snap)

        result = runner.invoke(
            app,
            ["delta", "--snapshot", baseline_name, "--storage-path", str(tmp_path), "--show-diff"],
            env={"AWS_PROFILE": "test"},
        )

        assert result.exit_code == 0
        # Should show tag changes (Environment: dev → prod)
        assert "Environment" in result.stdout
        assert "dev" in result.stdout or "prod" in result.stdout

    def test_delta_show_diff_shows_configuration_changes(
        self,
        runner: CliRunner,
        baseline_snapshot: tuple[str, Path],
        modified_snapshot: tuple[str, Path],
        tmp_path: Path,
    ) -> None:
        """Test that configuration changes are properly displayed."""
        baseline_name, _ = baseline_snapshot
        modified_name, _ = modified_snapshot

        storage = SnapshotStorage(tmp_path)
        base_storage = SnapshotStorage(baseline_snapshot[1])
        mod_storage = SnapshotStorage(modified_snapshot[1])

        base_snap = base_storage.load_snapshot(baseline_name)
        mod_snap = mod_storage.load_snapshot(modified_name)

        storage.save_snapshot(base_snap)
        storage.save_snapshot(mod_snap)

        result = runner.invoke(
            app,
            ["delta", "--snapshot", baseline_name, "--storage-path", str(tmp_path), "--show-diff"],
            env={"AWS_PROFILE": "test"},
        )

        assert result.exit_code == 0
        # Should show configuration changes (InstanceType change)
        assert "InstanceType" in result.stdout or "t2.micro" in result.stdout or "t2.small" in result.stdout
