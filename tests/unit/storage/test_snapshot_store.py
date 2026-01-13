"""Unit tests for SnapshotStore."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.models.resource import Resource
from src.models.snapshot import Snapshot
from src.storage.database import Database
from src.storage.snapshot_store import SnapshotStore


@pytest.fixture
def db(tmp_path: Path) -> Database:
    """Create a test database."""
    database = Database(storage_path=tmp_path)
    database.ensure_schema()
    return database


@pytest.fixture
def store(db: Database) -> SnapshotStore:
    """Create a snapshot store."""
    return SnapshotStore(db)


@pytest.fixture
def sample_resource() -> Resource:
    """Create a sample resource."""
    return Resource(
        arn="arn:aws:s3:::test-bucket",
        resource_type="s3:bucket",
        name="test-bucket",
        region="us-east-1",
        config_hash="a" * 64,
        raw_config={"BucketName": "test-bucket"},
        tags={"Environment": "test"},
    )


@pytest.fixture
def sample_snapshot(sample_resource: Resource) -> Snapshot:
    """Create a sample snapshot."""
    return Snapshot(
        name="test-snapshot",
        created_at=datetime(2025, 1, 10, 12, 0, 0, tzinfo=timezone.utc),
        account_id="123456789012",
        regions=["us-east-1", "us-west-2"],
        resources=[sample_resource],
        schema_version="1.1",
    )


class TestSnapshotStore:
    """Test cases for SnapshotStore."""

    def test_save_new_snapshot(self, store: SnapshotStore, sample_snapshot: Snapshot) -> None:
        """Test saving a new snapshot."""
        snapshot_id = store.save(sample_snapshot)

        assert snapshot_id > 0

    def test_save_and_load_snapshot(self, store: SnapshotStore, sample_snapshot: Snapshot) -> None:
        """Test saving and loading a snapshot."""
        store.save(sample_snapshot)

        loaded = store.load("test-snapshot")

        assert loaded is not None
        assert loaded.name == "test-snapshot"
        assert loaded.account_id == "123456789012"
        assert loaded.regions == ["us-east-1", "us-west-2"]
        assert loaded.schema_version == "1.1"

    def test_load_snapshot_with_resources(self, store: SnapshotStore, sample_snapshot: Snapshot) -> None:
        """Test that loading snapshot includes resources."""
        store.save(sample_snapshot)

        loaded = store.load("test-snapshot")

        assert len(loaded.resources) == 1
        assert loaded.resources[0].arn == "arn:aws:s3:::test-bucket"
        assert loaded.resources[0].resource_type == "s3:bucket"

    def test_load_snapshot_with_tags(self, store: SnapshotStore, sample_snapshot: Snapshot) -> None:
        """Test that loading snapshot includes resource tags."""
        store.save(sample_snapshot)

        loaded = store.load("test-snapshot")

        assert loaded.resources[0].tags == {"Environment": "test"}

    def test_load_snapshot_with_raw_config(self, store: SnapshotStore, sample_snapshot: Snapshot) -> None:
        """Test that loading snapshot includes raw_config."""
        store.save(sample_snapshot)

        loaded = store.load("test-snapshot")

        assert loaded.resources[0].raw_config is not None
        assert loaded.resources[0].raw_config["BucketName"] == "test-bucket"

    def test_load_nonexistent_snapshot(self, store: SnapshotStore) -> None:
        """Test loading a snapshot that doesn't exist."""
        loaded = store.load("nonexistent")

        assert loaded is None

    def test_list_all_empty(self, store: SnapshotStore) -> None:
        """Test listing snapshots when none exist."""
        snapshots = store.list_all()

        assert snapshots == []

    def test_list_all_with_snapshots(self, store: SnapshotStore) -> None:
        """Test listing multiple snapshots."""
        snap1 = Snapshot(
            name="snap1",
            created_at=datetime(2025, 1, 10, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
        )
        snap2 = Snapshot(
            name="snap2",
            created_at=datetime(2025, 1, 11, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-west-2"],
            resources=[],
        )

        store.save(snap1)
        store.save(snap2)

        snapshots = store.list_all()

        assert len(snapshots) == 2
        names = {s["name"] for s in snapshots}
        assert names == {"snap1", "snap2"}

    def test_delete_snapshot(self, store: SnapshotStore, sample_snapshot: Snapshot) -> None:
        """Test deleting a snapshot."""
        store.save(sample_snapshot)

        result = store.delete("test-snapshot")

        assert result is True
        assert store.load("test-snapshot") is None

    def test_delete_nonexistent_snapshot(self, store: SnapshotStore) -> None:
        """Test deleting a snapshot that doesn't exist."""
        result = store.delete("nonexistent")

        assert result is False

    def test_delete_removes_resources(self, store: SnapshotStore, sample_snapshot: Snapshot, db: Database) -> None:
        """Test that deleting snapshot removes associated resources."""
        store.save(sample_snapshot)

        # Verify resources exist
        resources = db.fetchall("SELECT * FROM resources")
        assert len(resources) == 1

        store.delete("test-snapshot")

        # Verify resources were deleted
        resources = db.fetchall("SELECT * FROM resources")
        assert len(resources) == 0

    def test_exists_true(self, store: SnapshotStore, sample_snapshot: Snapshot) -> None:
        """Test exists returns True for existing snapshot."""
        store.save(sample_snapshot)

        assert store.exists("test-snapshot") is True

    def test_exists_false(self, store: SnapshotStore) -> None:
        """Test exists returns False for nonexistent snapshot."""
        assert store.exists("nonexistent") is False

    def test_get_id(self, store: SnapshotStore, sample_snapshot: Snapshot) -> None:
        """Test getting snapshot ID by name."""
        snapshot_id = store.save(sample_snapshot)

        retrieved_id = store.get_id("test-snapshot")

        assert retrieved_id == snapshot_id

    def test_get_id_nonexistent(self, store: SnapshotStore) -> None:
        """Test getting ID of nonexistent snapshot."""
        retrieved_id = store.get_id("nonexistent")

        assert retrieved_id is None

    def test_save_same_name_raises_error(self, store: SnapshotStore, sample_snapshot: Snapshot) -> None:
        """Test that saving snapshot with same name raises integrity error."""
        import sqlite3

        store.save(sample_snapshot)

        # Trying to save again with same name should raise error
        # (snapshots are immutable - delete and recreate if needed)
        with pytest.raises(sqlite3.IntegrityError):
            store.save(sample_snapshot)

    def test_replace_snapshot_workflow(self, store: SnapshotStore, sample_snapshot: Snapshot) -> None:
        """Test delete-then-save workflow for replacing a snapshot."""
        store.save(sample_snapshot)

        # Delete old snapshot
        store.delete("test-snapshot")

        # Save new version
        sample_snapshot.regions = ["eu-west-1"]
        store.save(sample_snapshot)

        # Verify replacement
        loaded = store.load("test-snapshot")
        assert loaded.regions == ["eu-west-1"]

        # Should only have one snapshot
        snapshots = store.list_all()
        assert len(snapshots) == 1

    def test_save_multiple_resources(self, store: SnapshotStore) -> None:
        """Test saving snapshot with multiple resources."""
        resources = [
            Resource(
                arn=f"arn:aws:s3:::bucket-{i}",
                resource_type="s3:bucket",
                name=f"bucket-{i}",
                region="us-east-1",
                config_hash="a" * 64,
            )
            for i in range(10)
        ]

        snapshot = Snapshot(
            name="multi-resource",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=resources,
        )

        store.save(snapshot)
        loaded = store.load("multi-resource")

        assert len(loaded.resources) == 10

    def test_snapshot_metadata_preserved(self, store: SnapshotStore) -> None:
        """Test that snapshot metadata is preserved."""
        snapshot = Snapshot(
            name="metadata-test",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
            metadata={"tool_version": "1.0.0", "custom_key": "value"},
        )

        store.save(snapshot)
        loaded = store.load("metadata-test")

        assert loaded.metadata == {"tool_version": "1.0.0", "custom_key": "value"}

    def test_service_counts_calculated(self, store: SnapshotStore) -> None:
        """Test that service counts are calculated correctly."""
        resources = [
            Resource(arn="arn:aws:s3:::bucket1", resource_type="s3:bucket", name="bucket1", region="us-east-1", config_hash="a" * 64),
            Resource(arn="arn:aws:s3:::bucket2", resource_type="s3:bucket", name="bucket2", region="us-east-1", config_hash="b" * 64),
            Resource(arn="arn:aws:ec2:us-east-1:123:instance/i-1", resource_type="ec2:instance", name="i-1", region="us-east-1", config_hash="c" * 64),
        ]

        snapshot = Snapshot(
            name="counts-test",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=resources,
        )

        store.save(snapshot)
        loaded = store.load("counts-test")

        assert loaded.service_counts == {"s3": 2, "ec2": 1}
        assert loaded.resource_count == 3
