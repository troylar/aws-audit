"""Unit tests for CollectionStore."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.models.collection import Collection
from src.models.snapshot import Snapshot
from src.storage.collection_store import CollectionStore
from src.storage.database import Database
from src.storage.snapshot_store import SnapshotStore


@pytest.fixture
def db(tmp_path: Path) -> Database:
    """Create a test database."""
    database = Database(storage_path=tmp_path)
    database.ensure_schema()
    return database


@pytest.fixture
def store(db: Database) -> CollectionStore:
    """Create a collection store."""
    return CollectionStore(db)


@pytest.fixture
def snapshot_store(db: Database) -> SnapshotStore:
    """Create a snapshot store."""
    return SnapshotStore(db)


@pytest.fixture
def sample_collection() -> Collection:
    """Create a sample collection."""
    return Collection(
        name="test-collection",
        account_id="123456789012",
        description="Test collection description",
        include_tags={"Environment": "test"},
        exclude_tags={"Temporary": "true"},
        created_at=datetime(2025, 1, 10, 12, 0, 0, tzinfo=timezone.utc),
        last_updated=datetime(2025, 1, 10, 12, 0, 0, tzinfo=timezone.utc),
    )


class TestCollectionStore:
    """Test cases for CollectionStore."""

    def test_save_new_collection(self, store: CollectionStore, sample_collection: Collection) -> None:
        """Test saving a new collection."""
        collection_id = store.save(sample_collection)

        assert collection_id > 0

    def test_save_and_load_collection(self, store: CollectionStore, sample_collection: Collection) -> None:
        """Test saving and loading a collection."""
        store.save(sample_collection)

        loaded = store.load("test-collection", "123456789012")

        assert loaded is not None
        assert loaded.name == "test-collection"
        assert loaded.account_id == "123456789012"
        assert loaded.description == "Test collection description"

    def test_load_collection_with_tags(self, store: CollectionStore, sample_collection: Collection) -> None:
        """Test that loading collection includes tags."""
        store.save(sample_collection)

        loaded = store.load("test-collection", "123456789012")

        assert loaded.include_tags == {"Environment": "test"}
        assert loaded.exclude_tags == {"Temporary": "true"}

    def test_load_nonexistent_collection(self, store: CollectionStore) -> None:
        """Test loading a collection that doesn't exist."""
        loaded = store.load("nonexistent", "123456789012")

        assert loaded is None

    def test_list_all_empty(self, store: CollectionStore) -> None:
        """Test listing collections when none exist."""
        collections = store.list_all()

        assert collections == []

    def test_list_all_with_collections(self, store: CollectionStore) -> None:
        """Test listing multiple collections."""
        coll1 = Collection(name="coll1", account_id="111111111111")
        coll2 = Collection(name="coll2", account_id="222222222222")
        coll3 = Collection(name="coll3", account_id="111111111111")

        store.save(coll1)
        store.save(coll2)
        store.save(coll3)

        collections = store.list_all()

        assert len(collections) == 3

    def test_list_by_account(self, store: CollectionStore) -> None:
        """Test listing collections filtered by account."""
        coll1 = Collection(name="coll1", account_id="111111111111")
        coll2 = Collection(name="coll2", account_id="222222222222")
        coll3 = Collection(name="coll3", account_id="111111111111")

        store.save(coll1)
        store.save(coll2)
        store.save(coll3)

        account1_colls = store.list_by_account("111111111111")
        account2_colls = store.list_by_account("222222222222")

        assert len(account1_colls) == 2
        assert len(account2_colls) == 1
        assert all(coll.account_id == "111111111111" for coll in account1_colls)

    def test_delete_collection(self, store: CollectionStore, sample_collection: Collection) -> None:
        """Test deleting a collection."""
        store.save(sample_collection)

        result = store.delete("test-collection", "123456789012")

        assert result is True
        assert store.load("test-collection", "123456789012") is None

    def test_delete_nonexistent_collection(self, store: CollectionStore) -> None:
        """Test deleting a collection that doesn't exist."""
        result = store.delete("nonexistent", "123456789012")

        assert result is False

    def test_exists_true(self, store: CollectionStore, sample_collection: Collection) -> None:
        """Test exists returns True for existing collection."""
        store.save(sample_collection)

        assert store.exists("test-collection", "123456789012") is True

    def test_exists_false(self, store: CollectionStore) -> None:
        """Test exists returns False for nonexistent collection."""
        assert store.exists("nonexistent", "123456789012") is False

    def test_get_id(self, store: CollectionStore, sample_collection: Collection) -> None:
        """Test getting collection ID."""
        collection_id = store.save(sample_collection)

        retrieved_id = store.get_id("test-collection", "123456789012")

        assert retrieved_id == collection_id

    def test_get_id_nonexistent(self, store: CollectionStore) -> None:
        """Test getting ID of nonexistent collection."""
        retrieved_id = store.get_id("nonexistent", "123456789012")

        assert retrieved_id is None

    def test_save_updates_existing(self, store: CollectionStore, sample_collection: Collection) -> None:
        """Test that saving with same name updates existing collection."""
        store.save(sample_collection)

        # Modify and save again
        sample_collection.description = "Updated description"
        store.save(sample_collection)

        # Verify updated
        loaded = store.load("test-collection", "123456789012")
        assert loaded.description == "Updated description"

        # Should only have one collection
        collections = store.list_all()
        assert len(collections) == 1

    def test_collection_with_snapshots(
        self, store: CollectionStore, snapshot_store: SnapshotStore, sample_collection: Collection
    ) -> None:
        """Test collection with linked snapshots."""
        # Create snapshots first
        snap1 = Snapshot(
            name="snap1",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
        )
        snap2 = Snapshot(
            name="snap2",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
        )
        snapshot_store.save(snap1)
        snapshot_store.save(snap2)

        # Add snapshots to collection
        sample_collection.snapshots = ["snap1", "snap2"]
        store.save(sample_collection)

        # Load and verify
        loaded = store.load("test-collection", "123456789012")
        assert len(loaded.snapshots) == 2
        assert "snap1" in loaded.snapshots
        assert "snap2" in loaded.snapshots

    def test_collection_with_active_snapshot(
        self, store: CollectionStore, snapshot_store: SnapshotStore, sample_collection: Collection
    ) -> None:
        """Test collection with active snapshot."""
        # Create snapshot first
        snap = Snapshot(
            name="active-snap",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
        )
        snapshot_store.save(snap)

        # Set as active
        sample_collection.snapshots = ["active-snap"]
        sample_collection.active_snapshot = "active-snap"
        store.save(sample_collection)

        # Load and verify
        loaded = store.load("test-collection", "123456789012")
        assert loaded.active_snapshot == "active-snap"

    def test_add_snapshot_to_collection(self, store: CollectionStore, snapshot_store: SnapshotStore) -> None:
        """Test adding a snapshot to a collection."""
        # Create collection
        coll = Collection(name="test", account_id="123456789012")
        store.save(coll)

        # Create snapshot
        snap = Snapshot(
            name="new-snap",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
        )
        snapshot_store.save(snap)

        # Add snapshot
        result = store.add_snapshot_to_collection("test", "123456789012", "new-snap")

        assert result is True
        loaded = store.load("test", "123456789012")
        assert "new-snap" in loaded.snapshots

    def test_add_snapshot_to_collection_and_set_active(
        self, store: CollectionStore, snapshot_store: SnapshotStore
    ) -> None:
        """Test adding a snapshot and setting it as active."""
        # Create collection
        coll = Collection(name="test", account_id="123456789012")
        store.save(coll)

        # Create snapshot
        snap = Snapshot(
            name="active-snap",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
        )
        snapshot_store.save(snap)

        # Add snapshot and set active
        result = store.add_snapshot_to_collection("test", "123456789012", "active-snap", set_active=True)

        assert result is True
        loaded = store.load("test", "123456789012")
        assert loaded.active_snapshot == "active-snap"

    def test_remove_snapshot_from_collection(self, store: CollectionStore, snapshot_store: SnapshotStore) -> None:
        """Test removing a snapshot from a collection."""
        # Create snapshot first
        snap = Snapshot(
            name="to-remove",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
        )
        snapshot_store.save(snap)

        # Create collection with snapshot
        coll = Collection(name="test", account_id="123456789012", snapshots=["to-remove"])
        store.save(coll)

        # Remove snapshot
        result = store.remove_snapshot_from_collection("test", "123456789012", "to-remove")

        assert result is True
        loaded = store.load("test", "123456789012")
        assert "to-remove" not in loaded.snapshots

    def test_unique_name_account_constraint(self, store: CollectionStore) -> None:
        """Test that same name in same account updates, not duplicates."""
        coll1 = Collection(name="shared-name", account_id="123456789012", description="First")
        coll2 = Collection(name="shared-name", account_id="123456789012", description="Second")

        store.save(coll1)
        store.save(coll2)

        # Should only have one collection with updated description
        collections = store.list_all()
        assert len(collections) == 1
        assert collections[0].description == "Second"

    def test_same_name_different_accounts(self, store: CollectionStore) -> None:
        """Test that same name in different accounts creates separate collections."""
        coll1 = Collection(name="shared-name", account_id="111111111111")
        coll2 = Collection(name="shared-name", account_id="222222222222")

        store.save(coll1)
        store.save(coll2)

        # Should have two collections
        collections = store.list_all()
        assert len(collections) == 2
