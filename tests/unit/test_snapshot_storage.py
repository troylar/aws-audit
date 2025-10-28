"""Unit tests for SnapshotStorage."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from src.models.resource import Resource
from src.models.snapshot import Snapshot
from src.snapshot.storage import SnapshotStorage


class TestSnapshotStorage:
    """Test cases for SnapshotStorage."""

    def test_storage_initialization(self, temp_dir):
        """Test creating snapshot storage."""
        storage = SnapshotStorage(temp_dir)
        assert storage.storage_dir == Path(temp_dir)
        assert storage.storage_dir.exists()
        assert storage.active_file == storage.storage_dir / ".active"
        assert storage.index_file == storage.storage_dir / ".index.yaml"

    def test_storage_creates_directory(self, tmp_path):
        """Test that storage creates directory if it doesn't exist."""
        storage_path = tmp_path / "new_snapshots"
        SnapshotStorage(storage_path)
        assert storage_path.exists()

    def test_save_snapshot_uncompressed(self, temp_dir):
        """Test saving an uncompressed snapshot."""
        storage = SnapshotStorage(temp_dir)
        snapshot = Snapshot(
            name="test-snapshot",
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
        )

        filepath = storage.save_snapshot(snapshot, compress=False)

        assert filepath.exists()
        assert filepath.name == "test-snapshot.yaml"
        assert not str(filepath).endswith(".gz")

    def test_save_snapshot_compressed(self, temp_dir):
        """Test saving a compressed snapshot."""
        storage = SnapshotStorage(temp_dir)
        snapshot = Snapshot(
            name="compressed-snapshot",
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
        )

        filepath = storage.save_snapshot(snapshot, compress=True)

        assert filepath.exists()
        assert filepath.name == "compressed-snapshot.yaml.gz"
        assert str(filepath).endswith(".gz")

    def test_save_snapshot_with_resources(self, temp_dir):
        """Test saving a snapshot with resources."""
        storage = SnapshotStorage(temp_dir)
        resources = [
            Resource(
                arn="arn:aws:s3:::bucket1",
                resource_type="s3:bucket",
                name="bucket1",
                region="us-east-1",
                config_hash="a" * 64,
                raw_config={"BucketName": "bucket1"},
            ),
            Resource(
                arn="arn:aws:lambda:us-east-1:123456789012:function:func1",
                resource_type="lambda:function",
                name="func1",
                region="us-east-1",
                config_hash="b" * 64,
                raw_config={"FunctionName": "func1"},
            ),
        ]

        snapshot = Snapshot(
            name="with-resources",
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=resources,
        )

        filepath = storage.save_snapshot(snapshot)
        assert filepath.exists()

        # Verify file contents
        with open(filepath, "r") as f:
            data = yaml.safe_load(f)

        assert data["name"] == "with-resources"
        assert data["resource_count"] == 2
        assert len(data["resources"]) == 2

    def test_save_snapshot_sets_active(self, temp_dir):
        """Test that saving an active snapshot sets it as active."""
        storage = SnapshotStorage(temp_dir)
        snapshot = Snapshot(
            name="active-snapshot",
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
            is_active=True,
        )

        storage.save_snapshot(snapshot)

        assert storage.get_active_snapshot_name() == "active-snapshot"

    def test_load_snapshot_uncompressed(self, temp_dir):
        """Test loading an uncompressed snapshot."""
        storage = SnapshotStorage(temp_dir)
        original = Snapshot(
            name="load-test",
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1", "us-west-2"],
            resources=[],
            metadata={"author": "test"},
        )

        storage.save_snapshot(original, compress=False)
        loaded = storage.load_snapshot("load-test")

        assert loaded.name == original.name
        assert loaded.account_id == original.account_id
        assert loaded.regions == original.regions
        assert loaded.metadata == original.metadata

    def test_load_snapshot_compressed(self, temp_dir):
        """Test loading a compressed snapshot."""
        storage = SnapshotStorage(temp_dir)
        original = Snapshot(
            name="compressed-load",
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
        )

        storage.save_snapshot(original, compress=True)
        loaded = storage.load_snapshot("compressed-load")

        assert loaded.name == original.name
        assert loaded.account_id == original.account_id

    def test_load_snapshot_not_found(self, temp_dir):
        """Test loading a nonexistent snapshot raises FileNotFoundError."""
        storage = SnapshotStorage(temp_dir)

        with pytest.raises(FileNotFoundError, match="not found"):
            storage.load_snapshot("nonexistent")

    def test_load_snapshot_roundtrip(self, temp_dir):
        """Test that save -> load preserves all data."""
        storage = SnapshotStorage(temp_dir)
        resources = [
            Resource(
                arn="arn:aws:rds:eu-west-1:123456789012:db:mydb",
                resource_type="rds:instance",
                name="mydb",
                region="eu-west-1",
                config_hash="c" * 64,
                raw_config={"DBInstanceIdentifier": "mydb"},
                tags={"Environment": "production"},
                created_at=datetime(2024, 1, 15, 0, 0, 0, tzinfo=timezone.utc),
            )
        ]

        original = Snapshot(
            name="roundtrip-test",
            created_at=datetime(2024, 2, 1, 0, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["eu-west-1"],
            resources=resources,
            is_active=False,
            metadata={"purpose": "test", "version": "1.0"},
            filters_applied={"include_tags": {"Environment": "production"}},
            total_resources_before_filter=100,
        )

        storage.save_snapshot(original)
        loaded = storage.load_snapshot("roundtrip-test")

        assert loaded.name == original.name
        assert loaded.created_at == original.created_at
        assert loaded.account_id == original.account_id
        assert loaded.regions == original.regions
        assert loaded.resource_count == original.resource_count
        assert loaded.metadata == original.metadata
        assert loaded.filters_applied == original.filters_applied
        assert loaded.total_resources_before_filter == original.total_resources_before_filter
        assert len(loaded.resources) == len(original.resources)

    def test_list_snapshots_empty(self, temp_dir):
        """Test listing snapshots when none exist."""
        storage = SnapshotStorage(temp_dir)
        snapshots = storage.list_snapshots()
        assert snapshots == []

    def test_list_snapshots_single(self, temp_dir):
        """Test listing a single snapshot."""
        storage = SnapshotStorage(temp_dir)
        snapshot = Snapshot(
            name="snapshot1",
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
        )
        storage.save_snapshot(snapshot)

        snapshots = storage.list_snapshots()

        assert len(snapshots) == 1
        assert snapshots[0]["name"] == "snapshot1"
        assert "size_mb" in snapshots[0]
        assert "modified" in snapshots[0]

    def test_list_snapshots_multiple(self, temp_dir):
        """Test listing multiple snapshots."""
        storage = SnapshotStorage(temp_dir)

        for i in range(3):
            snapshot = Snapshot(
                name=f"snapshot{i}",
                created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
                account_id="123456789012",
                regions=["us-east-1"],
                resources=[],
            )
            storage.save_snapshot(snapshot)

        snapshots = storage.list_snapshots()

        assert len(snapshots) == 3
        names = [s["name"] for s in snapshots]
        assert "snapshot0" in names
        assert "snapshot1" in names
        assert "snapshot2" in names

    def test_list_snapshots_includes_active_flag(self, temp_dir):
        """Test that list_snapshots correctly identifies active snapshot."""
        storage = SnapshotStorage(temp_dir)

        # Create two snapshots
        snapshot1 = Snapshot(
            name="snapshot1",
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
        )
        snapshot2 = Snapshot(
            name="snapshot2",
            created_at=datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
            is_active=True,
        )

        storage.save_snapshot(snapshot1)
        storage.save_snapshot(snapshot2)

        snapshots = storage.list_snapshots()

        snapshot1_data = next(s for s in snapshots if s["name"] == "snapshot1")
        snapshot2_data = next(s for s in snapshots if s["name"] == "snapshot2")

        assert snapshot1_data["is_active"] is False
        assert snapshot2_data["is_active"] is True

    def test_delete_snapshot_uncompressed(self, temp_dir):
        """Test deleting an uncompressed snapshot."""
        storage = SnapshotStorage(temp_dir)
        snapshot = Snapshot(
            name="to-delete",
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
            is_active=False,  # Not active so it can be deleted
        )

        filepath = storage.save_snapshot(snapshot)
        assert filepath.exists()

        result = storage.delete_snapshot("to-delete")

        assert result is True
        assert not filepath.exists()

    def test_delete_snapshot_compressed(self, temp_dir):
        """Test deleting a compressed snapshot."""
        storage = SnapshotStorage(temp_dir)
        snapshot = Snapshot(
            name="to-delete-compressed",
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
            is_active=False,  # Not active so it can be deleted
        )

        filepath = storage.save_snapshot(snapshot, compress=True)
        assert filepath.exists()

        result = storage.delete_snapshot("to-delete-compressed")

        assert result is True
        assert not filepath.exists()

    def test_delete_snapshot_not_found(self, temp_dir):
        """Test deleting a nonexistent snapshot raises FileNotFoundError."""
        storage = SnapshotStorage(temp_dir)

        with pytest.raises(FileNotFoundError, match="not found"):
            storage.delete_snapshot("nonexistent")

    def test_delete_active_snapshot_raises_error(self, temp_dir):
        """Test that deleting the active snapshot raises ValueError."""
        storage = SnapshotStorage(temp_dir)
        snapshot = Snapshot(
            name="active",
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
            is_active=True,
        )

        storage.save_snapshot(snapshot)

        with pytest.raises(ValueError, match="Cannot delete active snapshot"):
            storage.delete_snapshot("active")

    def test_get_active_snapshot_name_none(self, temp_dir):
        """Test getting active snapshot name when none is set."""
        storage = SnapshotStorage(temp_dir)
        assert storage.get_active_snapshot_name() is None

    def test_get_active_snapshot_name(self, temp_dir):
        """Test getting active snapshot name."""
        storage = SnapshotStorage(temp_dir)
        snapshot = Snapshot(
            name="my-active",
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
            is_active=True,
        )

        storage.save_snapshot(snapshot)

        assert storage.get_active_snapshot_name() == "my-active"

    def test_set_active_snapshot(self, temp_dir):
        """Test setting a snapshot as active."""
        storage = SnapshotStorage(temp_dir)
        snapshot = Snapshot(
            name="to-activate",
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
        )

        storage.save_snapshot(snapshot)
        storage.set_active_snapshot("to-activate")

        assert storage.get_active_snapshot_name() == "to-activate"

    def test_set_active_snapshot_not_found(self, temp_dir):
        """Test setting a nonexistent snapshot as active raises FileNotFoundError."""
        storage = SnapshotStorage(temp_dir)

        with pytest.raises(FileNotFoundError, match="not found"):
            storage.set_active_snapshot("nonexistent")

    def test_set_active_snapshot_changes_active(self, temp_dir):
        """Test that setting active snapshot changes the active file."""
        storage = SnapshotStorage(temp_dir)

        # Create two snapshots (both initially inactive)
        snapshot1 = Snapshot(
            name="snapshot1",
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
            is_active=False,
        )
        snapshot2 = Snapshot(
            name="snapshot2",
            created_at=datetime(2024, 1, 2, 12, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
            is_active=False,
        )

        storage.save_snapshot(snapshot1)
        storage.save_snapshot(snapshot2)

        # Set snapshot1 as active
        storage.set_active_snapshot("snapshot1")
        assert storage.get_active_snapshot_name() == "snapshot1"

        # Change active to snapshot2
        storage.set_active_snapshot("snapshot2")
        assert storage.get_active_snapshot_name() == "snapshot2"

    def test_index_updated_on_save(self, temp_dir):
        """Test that snapshot index is updated when saving."""
        storage = SnapshotStorage(temp_dir)
        snapshot = Snapshot(
            name="indexed",
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1", "us-west-2"],
            resources=[],
        )

        storage.save_snapshot(snapshot)

        # Load index file
        with open(storage.index_file, "r") as f:
            index = yaml.safe_load(f)

        assert "indexed" in index
        assert index["indexed"]["name"] == "indexed"
        assert index["indexed"]["account_id"] == "123456789012"
        assert index["indexed"]["regions"] == ["us-east-1", "us-west-2"]

    def test_index_updated_on_delete(self, temp_dir):
        """Test that snapshot index is updated when deleting."""
        storage = SnapshotStorage(temp_dir)
        snapshot = Snapshot(
            name="to-remove",
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
            is_active=False,  # Not active so it can be deleted
        )

        storage.save_snapshot(snapshot)

        # Verify it's in the index
        with open(storage.index_file, "r") as f:
            index = yaml.safe_load(f)
        assert "to-remove" in index

        storage.delete_snapshot("to-remove")

        # Verify it's removed from the index
        with open(storage.index_file, "r") as f:
            index = yaml.safe_load(f)
        assert "to-remove" not in index

    def test_list_snapshots_ignores_hidden_files(self, temp_dir):
        """Test that list_snapshots ignores hidden files."""
        storage = SnapshotStorage(temp_dir)
        snapshot = Snapshot(
            name="visible",
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
        )

        storage.save_snapshot(snapshot)

        # Create a hidden file
        hidden_file = storage.storage_dir / ".hidden.yaml"
        hidden_file.write_text("hidden content")

        snapshots = storage.list_snapshots()

        assert len(snapshots) == 1
        assert snapshots[0]["name"] == "visible"

    def test_snapshot_with_large_resource_count(self, temp_dir):
        """Test snapshot with many resources."""
        storage = SnapshotStorage(temp_dir)

        # Create 100 resources
        resources = [
            Resource(
                arn=f"arn:aws:s3:::bucket-{i}",
                resource_type="s3:bucket",
                name=f"bucket-{i}",
                region="us-east-1",
                config_hash=str(i % 10) * 64,
                raw_config={},
            )
            for i in range(100)
        ]

        snapshot = Snapshot(
            name="large-snapshot",
            created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=resources,
        )

        storage.save_snapshot(snapshot)
        loaded = storage.load_snapshot("large-snapshot")

        assert loaded.resource_count == 100
        assert len(loaded.resources) == 100
