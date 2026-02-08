"""Unit tests for CollectionStorage service."""

from pathlib import Path

import pytest
import yaml

from src.models.collection import Collection
from src.models.snapshot import Snapshot
from src.snapshot.collection_storage import CollectionNotFoundError, CollectionStorage
from src.storage import SnapshotStore


class TestCollectionStorage:
    """Test cases for CollectionStorage service."""

    def test_initialization_creates_directory(self, temp_dir):
        """Test that CollectionStorage creates storage directory."""
        storage_dir = temp_dir / "test-storage"
        storage = CollectionStorage(str(storage_dir))

        assert storage_dir.exists()
        # get_snapshot_storage_path returns resolved absolute paths
        assert storage.storage_dir == storage_dir.resolve()
        assert storage.collections_file == storage_dir.resolve() / "collections.yaml"

    def test_initialization_with_default_directory(self):
        """Test initialization with default .snapshots directory."""
        storage = CollectionStorage()
        # Default is now ~/.snapshots (absolute path)
        assert storage.storage_dir == Path.home() / ".snapshots"

    def test_load_all_empty(self, temp_dir):
        """Test loading collections when file doesn't exist."""
        storage = CollectionStorage(str(temp_dir))
        collections = storage.load_all()

        assert collections == []

    def test_load_all_with_data(self, temp_dir, sample_collection_data):
        """Test loading collections from SQLite database."""
        storage = CollectionStorage(str(temp_dir))

        # Create collection via storage (uses SQLite)
        collection = Collection(
            name="test-collection",
            account_id="123456789012",
            description="Test collection",
        )
        storage.save(collection)

        collections = storage.load_all()

        assert len(collections) == 1
        assert collections[0].name == "test-collection"
        assert collections[0].account_id == "123456789012"

    def test_load_all_with_multiple_collections(self, temp_dir):
        """Test loading multiple collections from SQLite database."""
        storage = CollectionStorage(str(temp_dir))

        # Create multiple collections
        coll1 = Collection(name="coll1", account_id="111111111111")
        coll2 = Collection(name="coll2", account_id="222222222222")
        storage.save(coll1)
        storage.save(coll2)

        collections = storage.load_all()

        assert len(collections) == 2
        names = {coll.name for coll in collections}
        assert names == {"coll1", "coll2"}

    def test_load_by_account(self, temp_dir):
        """Test loading collections filtered by account."""
        storage = CollectionStorage(str(temp_dir))

        # Create multiple collections for different accounts
        coll1 = Collection(name="coll1", account_id="111111111111")
        coll2 = Collection(name="coll2", account_id="222222222222")
        coll3 = Collection(name="coll3", account_id="111111111111")

        storage.save(coll1)
        storage.save(coll2)
        storage.save(coll3)

        # Load by first account
        account1_colls = storage.load_by_account("111111111111")
        assert len(account1_colls) == 2
        assert all(coll.account_id == "111111111111" for coll in account1_colls)

        # Load by second account
        account2_colls = storage.load_by_account("222222222222")
        assert len(account2_colls) == 1
        assert account2_colls[0].account_id == "222222222222"

    def test_get_by_name_success(self, temp_dir):
        """Test getting collection by name."""
        storage = CollectionStorage(str(temp_dir))

        collection = Collection(name="test", account_id="123456789012")
        storage.save(collection)

        retrieved = storage.get_by_name("test", "123456789012")
        assert retrieved.name == "test"
        assert retrieved.account_id == "123456789012"

    def test_get_by_name_not_found(self, temp_dir):
        """Test getting non-existent collection."""
        storage = CollectionStorage(str(temp_dir))

        with pytest.raises(CollectionNotFoundError, match="not found"):
            storage.get_by_name("nonexistent", "123456789012")

    def test_get_or_create_default_creates(self, temp_dir):
        """Test that get_or_create_default creates default collection."""
        storage = CollectionStorage(str(temp_dir))

        collection = storage.get_or_create_default("123456789012")

        assert collection.name == "default"
        assert collection.account_id == "123456789012"
        assert "Auto-created" in collection.description

        # Verify it was saved
        all_colls = storage.load_all()
        assert len(all_colls) == 1

    def test_get_or_create_default_returns_existing(self, temp_dir):
        """Test that get_or_create_default returns existing default."""
        storage = CollectionStorage(str(temp_dir))

        # Create default collection
        default = Collection(
            name="default",
            account_id="123456789012",
            description="Custom default",
        )
        storage.save(default)

        # Get should return existing
        retrieved = storage.get_or_create_default("123456789012")
        assert retrieved.description == "Custom default"

        # Should not create duplicate
        all_colls = storage.load_all()
        assert len(all_colls) == 1

    def test_save_new_collection(self, temp_dir):
        """Test saving a new collection."""
        storage = CollectionStorage(str(temp_dir))

        collection = Collection(
            name="new-collection",
            account_id="123456789012",
            description="New test collection",
        )

        storage.save(collection)

        # Verify saved
        retrieved = storage.get_by_name("new-collection", "123456789012")
        assert retrieved.name == "new-collection"
        assert retrieved.description == "New test collection"

    def test_save_update_existing(self, temp_dir):
        """Test updating an existing collection."""
        from datetime import datetime, timezone

        storage = CollectionStorage(str(temp_dir))

        # Create initial collection
        collection = Collection(
            name="test",
            account_id="123456789012",
            description="Original",
        )
        storage.save(collection)

        # Create a snapshot in the database first (required for linking)
        snapshot = Snapshot(
            name="new-snap",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
        )
        snapshot_store = SnapshotStore(storage.db)
        snapshot_store.save(snapshot)

        # Update it
        collection.description = "Updated"
        collection.add_snapshot("new-snap")  # Add the snapshot name (without extension)
        storage.save(collection)

        # Verify update
        retrieved = storage.get_by_name("test", "123456789012")
        assert retrieved.description == "Updated"
        assert len(retrieved.snapshots) == 1
        assert "new-snap" in retrieved.snapshots

        # Should only have one collection
        all_colls = storage.load_all()
        assert len(all_colls) == 1

    def test_save_invalid_collection(self, temp_dir):
        """Test saving collection with validation errors."""
        storage = CollectionStorage(str(temp_dir))

        collection = Collection(
            name="",  # Invalid empty name
            account_id="123456789012",
        )

        with pytest.raises(ValueError, match="Invalid collection"):
            storage.save(collection)

    def test_delete_collection(self, temp_dir):
        """Test deleting a collection."""
        storage = CollectionStorage(str(temp_dir))

        # Create collection
        collection = Collection(name="delete-me", account_id="123456789012")
        storage.save(collection)

        # Delete it
        deleted_count = storage.delete("delete-me", "123456789012", delete_snapshots=False)
        assert deleted_count == 0  # No snapshots to delete

        # Verify deleted
        with pytest.raises(CollectionNotFoundError):
            storage.get_by_name("delete-me", "123456789012")

    def test_delete_with_snapshots(self, temp_dir):
        """Test deleting collection and its associated snapshots from SQLite."""
        from datetime import datetime, timezone

        storage = CollectionStorage(str(temp_dir))

        # Create snapshots in the database first
        snapshot_store = SnapshotStore(storage.db)
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

        # Create collection with snapshots
        collection = Collection(
            name="with-snaps",
            account_id="123456789012",
            snapshots=["snap1", "snap2"],
        )
        storage.save(collection)

        # Delete with snapshots
        deleted_count = storage.delete("with-snaps", "123456789012", delete_snapshots=True)
        assert deleted_count == 2

        # Verify snapshots deleted from database
        assert snapshot_store.load("snap1") is None
        assert snapshot_store.load("snap2") is None

    def test_delete_nonexistent_collection(self, temp_dir):
        """Test deleting collection that doesn't exist."""
        storage = CollectionStorage(str(temp_dir))

        with pytest.raises(CollectionNotFoundError):
            storage.delete("nonexistent", "123456789012")

    def test_exists(self, temp_dir):
        """Test checking if collection exists."""
        storage = CollectionStorage(str(temp_dir))

        assert not storage.exists("test", "123456789012")

        collection = Collection(name="test", account_id="123456789012")
        storage.save(collection)

        assert storage.exists("test", "123456789012")
        assert not storage.exists("other", "123456789012")

    def test_validate_unique(self, temp_dir):
        """Test validating uniqueness of collection name."""
        storage = CollectionStorage(str(temp_dir))

        # Should be unique initially
        assert storage.validate_unique("test", "123456789012")

        # Create collection
        collection = Collection(name="test", account_id="123456789012")
        storage.save(collection)

        # Should no longer be unique
        assert not storage.validate_unique("test", "123456789012")

        # Should be unique for different account
        assert storage.validate_unique("test", "999999999999")

    def test_save_creates_database(self, temp_dir):
        """Test that saving collection creates SQLite database file."""
        storage = CollectionStorage(str(temp_dir))

        collection = Collection(name="test", account_id="123456789012")
        storage.save(collection)

        # SQLite database file should exist
        db_file = storage.storage_dir / "inventory.db"
        assert db_file.exists()

        # Verify collection can be retrieved
        retrieved = storage.get_by_name("test", "123456789012")
        assert retrieved.name == "test"

    def test_multiple_collections_same_account(self, temp_dir):
        """Test managing multiple collections for same account."""
        storage = CollectionStorage(str(temp_dir))

        coll1 = Collection(name="baseline", account_id="123456789012")
        coll2 = Collection(name="team-alpha", account_id="123456789012")
        coll3 = Collection(name="team-beta", account_id="123456789012")

        storage.save(coll1)
        storage.save(coll2)
        storage.save(coll3)

        account_colls = storage.load_by_account("123456789012")
        assert len(account_colls) == 3

        names = {coll.name for coll in account_colls}
        assert names == {"baseline", "team-alpha", "team-beta"}

    def test_collection_persistence(self, temp_dir):
        """Test that collections persist across CollectionStorage instances."""
        # Save with first instance
        storage1 = CollectionStorage(temp_dir)
        collection = Collection(name="persistent", account_id="123456789012")
        storage1.save(collection)

        # Load with second instance
        storage2 = CollectionStorage(temp_dir)
        retrieved = storage2.get_by_name("persistent", "123456789012")

        assert retrieved.name == "persistent"
        assert retrieved.account_id == "123456789012"

    def test_collection_stored_in_sqlite(self, temp_dir):
        """Test that collection is stored in SQLite database."""
        storage = CollectionStorage(str(temp_dir))

        collection = Collection(name="first", account_id="123456789012")
        storage.save(collection)

        # Verify data is stored in SQLite by checking via a fresh storage instance
        storage2 = CollectionStorage(str(temp_dir))
        collections = storage2.load_all()

        assert len(collections) == 1
        assert collections[0].name == "first"
        assert collections[0].account_id == "123456789012"

    def test_load_all_empty_database(self, temp_dir):
        """Test loading when database has no collections."""
        storage = CollectionStorage(str(temp_dir))

        collections = storage.load_all()

        assert collections == []

    def test_fresh_storage_empty(self, temp_dir):
        """Test that fresh storage instance returns empty list."""
        storage = CollectionStorage(str(temp_dir))

        # Fresh storage should have no collections
        collections = storage.load_all()

        assert collections == []

    def test_delete_collection_without_linked_snapshots(self, temp_dir):
        """Test deleting collection when snapshots are not in database."""
        storage = CollectionStorage(str(temp_dir))

        # Create collection with snapshot references that don't exist in DB
        collection = Collection(
            name="with-snap",
            account_id="123456789012",
            snapshots=["nonexistent-snap"],  # Not in database
        )
        storage.save(collection)

        # Delete with snapshots - should return 0 because snapshot doesn't exist
        deleted_count = storage.delete("with-snap", "123456789012", delete_snapshots=True)

        # Should return 0 because the snapshot doesn't exist
        assert deleted_count == 0

    def test_get_by_name_case_sensitive(self, temp_dir):
        """Test that collection lookup is case-sensitive."""
        storage = CollectionStorage(str(temp_dir))

        # Create collection with lowercase name
        collection = Collection(name="mycollection", account_id="123456789012")
        storage.save(collection)

        # Should find with exact name
        retrieved = storage.get_by_name("mycollection", "123456789012")
        assert retrieved.name == "mycollection"

        # Should not find with different case
        with pytest.raises(CollectionNotFoundError):
            storage.get_by_name("MyCollection", "123456789012")

    def test_yaml_migration_on_first_use(self, temp_dir):
        """Test that YAML collections are migrated to SQLite on first use."""
        # Create a legacy YAML file before initializing storage
        collection_file = temp_dir / "collections.yaml"
        legacy_data = {
            "collections": [
                {
                    "name": "legacy-coll",
                    "account_id": "123456789012",
                    "description": "Legacy collection",
                    "include_tags": {},
                    "exclude_tags": {},
                    "snapshots": [],
                    "active_snapshot": None,
                    "created_at": "2025-01-10T00:00:00+00:00",
                    "last_updated": "2025-01-10T00:00:00+00:00",
                }
            ]
        }
        with open(collection_file, "w") as f:
            yaml.safe_dump(legacy_data, f)

        # Initialize storage - should migrate YAML to SQLite
        storage = CollectionStorage(str(temp_dir))

        # Verify data was migrated
        collections = storage.load_all()
        assert len(collections) == 1
        assert collections[0].name == "legacy-coll"
        assert collections[0].account_id == "123456789012"

    def test_invalid_collection_validation(self, temp_dir):
        """Test that invalid collection is rejected before saving."""
        storage = CollectionStorage(str(temp_dir))

        # Create a collection with invalid name (empty)
        collection = Collection(name="", account_id="123456789012")

        # Should raise ValueError due to validation
        with pytest.raises(ValueError, match="Invalid collection"):
            storage.save(collection)
