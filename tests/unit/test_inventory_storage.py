"""Unit tests for InventoryStorage service."""

from pathlib import Path

import pytest
import yaml

from src.models.inventory import Inventory
from src.models.snapshot import Snapshot
from src.snapshot.inventory_storage import InventoryNotFoundError, InventoryStorage
from src.storage import SnapshotStore


class TestInventoryStorage:
    """Test cases for InventoryStorage service."""

    def test_initialization_creates_directory(self, temp_dir):
        """Test that InventoryStorage creates storage directory."""
        storage_dir = temp_dir / "test-storage"
        storage = InventoryStorage(str(storage_dir))

        assert storage_dir.exists()
        # get_snapshot_storage_path returns resolved absolute paths
        assert storage.storage_dir == storage_dir.resolve()
        assert storage.inventory_file == storage_dir.resolve() / "inventories.yaml"

    def test_initialization_with_default_directory(self):
        """Test initialization with default .snapshots directory."""
        storage = InventoryStorage()
        # Default is now ~/.snapshots (absolute path)
        assert storage.storage_dir == Path.home() / ".snapshots"

    def test_load_all_empty(self, temp_dir):
        """Test loading inventories when file doesn't exist."""
        storage = InventoryStorage(str(temp_dir))
        inventories = storage.load_all()

        assert inventories == []

    def test_load_all_with_data(self, temp_dir, sample_inventory_data):
        """Test loading inventories from SQLite database."""
        storage = InventoryStorage(str(temp_dir))

        # Create inventory via storage (uses SQLite)
        inventory = Inventory(
            name="test-inventory",
            account_id="123456789012",
            description="Test inventory",
        )
        storage.save(inventory)

        inventories = storage.load_all()

        assert len(inventories) == 1
        assert inventories[0].name == "test-inventory"
        assert inventories[0].account_id == "123456789012"

    def test_load_all_with_multiple_inventories(self, temp_dir):
        """Test loading multiple inventories from SQLite database."""
        storage = InventoryStorage(str(temp_dir))

        # Create multiple inventories
        inv1 = Inventory(name="inv1", account_id="111111111111")
        inv2 = Inventory(name="inv2", account_id="222222222222")
        storage.save(inv1)
        storage.save(inv2)

        inventories = storage.load_all()

        assert len(inventories) == 2
        names = {inv.name for inv in inventories}
        assert names == {"inv1", "inv2"}

    def test_load_by_account(self, temp_dir):
        """Test loading inventories filtered by account."""
        storage = InventoryStorage(str(temp_dir))

        # Create multiple inventories for different accounts
        inv1 = Inventory(name="inv1", account_id="111111111111")
        inv2 = Inventory(name="inv2", account_id="222222222222")
        inv3 = Inventory(name="inv3", account_id="111111111111")

        storage.save(inv1)
        storage.save(inv2)
        storage.save(inv3)

        # Load by first account
        account1_invs = storage.load_by_account("111111111111")
        assert len(account1_invs) == 2
        assert all(inv.account_id == "111111111111" for inv in account1_invs)

        # Load by second account
        account2_invs = storage.load_by_account("222222222222")
        assert len(account2_invs) == 1
        assert account2_invs[0].account_id == "222222222222"

    def test_get_by_name_success(self, temp_dir):
        """Test getting inventory by name."""
        storage = InventoryStorage(str(temp_dir))

        inventory = Inventory(name="test", account_id="123456789012")
        storage.save(inventory)

        retrieved = storage.get_by_name("test", "123456789012")
        assert retrieved.name == "test"
        assert retrieved.account_id == "123456789012"

    def test_get_by_name_not_found(self, temp_dir):
        """Test getting non-existent inventory."""
        storage = InventoryStorage(str(temp_dir))

        with pytest.raises(InventoryNotFoundError, match="not found"):
            storage.get_by_name("nonexistent", "123456789012")

    def test_get_or_create_default_creates(self, temp_dir):
        """Test that get_or_create_default creates default inventory."""
        storage = InventoryStorage(str(temp_dir))

        inventory = storage.get_or_create_default("123456789012")

        assert inventory.name == "default"
        assert inventory.account_id == "123456789012"
        assert "Auto-created" in inventory.description

        # Verify it was saved
        all_invs = storage.load_all()
        assert len(all_invs) == 1

    def test_get_or_create_default_returns_existing(self, temp_dir):
        """Test that get_or_create_default returns existing default."""
        storage = InventoryStorage(str(temp_dir))

        # Create default inventory
        default = Inventory(
            name="default",
            account_id="123456789012",
            description="Custom default",
        )
        storage.save(default)

        # Get should return existing
        retrieved = storage.get_or_create_default("123456789012")
        assert retrieved.description == "Custom default"

        # Should not create duplicate
        all_invs = storage.load_all()
        assert len(all_invs) == 1

    def test_save_new_inventory(self, temp_dir):
        """Test saving a new inventory."""
        storage = InventoryStorage(str(temp_dir))

        inventory = Inventory(
            name="new-inventory",
            account_id="123456789012",
            description="New test inventory",
        )

        storage.save(inventory)

        # Verify saved
        retrieved = storage.get_by_name("new-inventory", "123456789012")
        assert retrieved.name == "new-inventory"
        assert retrieved.description == "New test inventory"

    def test_save_update_existing(self, temp_dir):
        """Test updating an existing inventory."""
        from datetime import datetime, timezone

        storage = InventoryStorage(str(temp_dir))

        # Create initial inventory
        inventory = Inventory(
            name="test",
            account_id="123456789012",
            description="Original",
        )
        storage.save(inventory)

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
        inventory.description = "Updated"
        inventory.add_snapshot("new-snap")  # Add the snapshot name (without extension)
        storage.save(inventory)

        # Verify update
        retrieved = storage.get_by_name("test", "123456789012")
        assert retrieved.description == "Updated"
        assert len(retrieved.snapshots) == 1
        assert "new-snap" in retrieved.snapshots

        # Should only have one inventory
        all_invs = storage.load_all()
        assert len(all_invs) == 1

    def test_save_invalid_inventory(self, temp_dir):
        """Test saving inventory with validation errors."""
        storage = InventoryStorage(str(temp_dir))

        inventory = Inventory(
            name="",  # Invalid empty name
            account_id="123456789012",
        )

        with pytest.raises(ValueError, match="Invalid inventory"):
            storage.save(inventory)

    def test_delete_inventory(self, temp_dir):
        """Test deleting an inventory."""
        storage = InventoryStorage(str(temp_dir))

        # Create inventory
        inventory = Inventory(name="delete-me", account_id="123456789012")
        storage.save(inventory)

        # Delete it
        deleted_count = storage.delete("delete-me", "123456789012", delete_snapshots=False)
        assert deleted_count == 0  # No snapshots to delete

        # Verify deleted
        with pytest.raises(InventoryNotFoundError):
            storage.get_by_name("delete-me", "123456789012")

    def test_delete_with_snapshots(self, temp_dir):
        """Test deleting inventory and its associated snapshots from SQLite."""
        from datetime import datetime, timezone

        storage = InventoryStorage(str(temp_dir))

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

        # Create inventory with snapshots
        inventory = Inventory(
            name="with-snaps",
            account_id="123456789012",
            snapshots=["snap1", "snap2"],
        )
        storage.save(inventory)

        # Delete with snapshots
        deleted_count = storage.delete("with-snaps", "123456789012", delete_snapshots=True)
        assert deleted_count == 2

        # Verify snapshots deleted from database
        assert snapshot_store.load("snap1") is None
        assert snapshot_store.load("snap2") is None

    def test_delete_nonexistent_inventory(self, temp_dir):
        """Test deleting inventory that doesn't exist."""
        storage = InventoryStorage(str(temp_dir))

        with pytest.raises(InventoryNotFoundError):
            storage.delete("nonexistent", "123456789012")

    def test_exists(self, temp_dir):
        """Test checking if inventory exists."""
        storage = InventoryStorage(str(temp_dir))

        assert not storage.exists("test", "123456789012")

        inventory = Inventory(name="test", account_id="123456789012")
        storage.save(inventory)

        assert storage.exists("test", "123456789012")
        assert not storage.exists("other", "123456789012")

    def test_validate_unique(self, temp_dir):
        """Test validating uniqueness of inventory name."""
        storage = InventoryStorage(str(temp_dir))

        # Should be unique initially
        assert storage.validate_unique("test", "123456789012")

        # Create inventory
        inventory = Inventory(name="test", account_id="123456789012")
        storage.save(inventory)

        # Should no longer be unique
        assert not storage.validate_unique("test", "123456789012")

        # Should be unique for different account
        assert storage.validate_unique("test", "999999999999")

    def test_save_creates_database(self, temp_dir):
        """Test that saving inventory creates SQLite database file."""
        storage = InventoryStorage(str(temp_dir))

        inventory = Inventory(name="test", account_id="123456789012")
        storage.save(inventory)

        # SQLite database file should exist
        db_file = storage.storage_dir / "inventory.db"
        assert db_file.exists()

        # Verify inventory can be retrieved
        retrieved = storage.get_by_name("test", "123456789012")
        assert retrieved.name == "test"

    def test_multiple_inventories_same_account(self, temp_dir):
        """Test managing multiple inventories for same account."""
        storage = InventoryStorage(str(temp_dir))

        inv1 = Inventory(name="baseline", account_id="123456789012")
        inv2 = Inventory(name="team-alpha", account_id="123456789012")
        inv3 = Inventory(name="team-beta", account_id="123456789012")

        storage.save(inv1)
        storage.save(inv2)
        storage.save(inv3)

        account_invs = storage.load_by_account("123456789012")
        assert len(account_invs) == 3

        names = {inv.name for inv in account_invs}
        assert names == {"baseline", "team-alpha", "team-beta"}

    def test_inventory_persistence(self, temp_dir):
        """Test that inventories persist across InventoryStorage instances."""
        # Save with first instance
        storage1 = InventoryStorage(temp_dir)
        inventory = Inventory(name="persistent", account_id="123456789012")
        storage1.save(inventory)

        # Load with second instance
        storage2 = InventoryStorage(temp_dir)
        retrieved = storage2.get_by_name("persistent", "123456789012")

        assert retrieved.name == "persistent"
        assert retrieved.account_id == "123456789012"

    def test_inventory_stored_in_sqlite(self, temp_dir):
        """Test that inventory is stored in SQLite database."""
        storage = InventoryStorage(str(temp_dir))

        inventory = Inventory(name="first", account_id="123456789012")
        storage.save(inventory)

        # Verify data is stored in SQLite by checking via a fresh storage instance
        storage2 = InventoryStorage(str(temp_dir))
        inventories = storage2.load_all()

        assert len(inventories) == 1
        assert inventories[0].name == "first"
        assert inventories[0].account_id == "123456789012"

    def test_load_all_empty_database(self, temp_dir):
        """Test loading when database has no inventories."""
        storage = InventoryStorage(str(temp_dir))

        inventories = storage.load_all()

        assert inventories == []

    def test_fresh_storage_empty(self, temp_dir):
        """Test that fresh storage instance returns empty list."""
        storage = InventoryStorage(str(temp_dir))

        # Fresh storage should have no inventories
        inventories = storage.load_all()

        assert inventories == []

    def test_delete_inventory_without_linked_snapshots(self, temp_dir):
        """Test deleting inventory when snapshots are not in database."""
        storage = InventoryStorage(str(temp_dir))

        # Create inventory with snapshot references that don't exist in DB
        inventory = Inventory(
            name="with-snap",
            account_id="123456789012",
            snapshots=["nonexistent-snap"],  # Not in database
        )
        storage.save(inventory)

        # Delete with snapshots - should return 0 because snapshot doesn't exist
        deleted_count = storage.delete("with-snap", "123456789012", delete_snapshots=True)

        # Should return 0 because the snapshot doesn't exist
        assert deleted_count == 0

    def test_get_by_name_case_sensitive(self, temp_dir):
        """Test that inventory lookup is case-sensitive."""
        storage = InventoryStorage(str(temp_dir))

        # Create inventory with lowercase name
        inventory = Inventory(name="myinventory", account_id="123456789012")
        storage.save(inventory)

        # Should find with exact name
        retrieved = storage.get_by_name("myinventory", "123456789012")
        assert retrieved.name == "myinventory"

        # Should not find with different case
        with pytest.raises(InventoryNotFoundError):
            storage.get_by_name("MyInventory", "123456789012")

    def test_yaml_migration_on_first_use(self, temp_dir):
        """Test that YAML inventories are migrated to SQLite on first use."""
        # Create a legacy YAML file before initializing storage
        inventory_file = temp_dir / "inventories.yaml"
        legacy_data = {
            "inventories": [
                {
                    "name": "legacy-inv",
                    "account_id": "123456789012",
                    "description": "Legacy inventory",
                    "include_tags": {},
                    "exclude_tags": {},
                    "snapshots": [],
                    "active_snapshot": None,
                    "created_at": "2025-01-10T00:00:00+00:00",
                    "last_updated": "2025-01-10T00:00:00+00:00",
                }
            ]
        }
        with open(inventory_file, "w") as f:
            yaml.safe_dump(legacy_data, f)

        # Initialize storage - should migrate YAML to SQLite
        storage = InventoryStorage(str(temp_dir))

        # Verify data was migrated
        inventories = storage.load_all()
        assert len(inventories) == 1
        assert inventories[0].name == "legacy-inv"
        assert inventories[0].account_id == "123456789012"

    def test_invalid_inventory_validation(self, temp_dir):
        """Test that invalid inventory is rejected before saving."""
        storage = InventoryStorage(str(temp_dir))

        # Create an inventory with invalid name (empty)
        inventory = Inventory(name="", account_id="123456789012")

        # Should raise ValueError due to validation
        with pytest.raises(ValueError, match="Invalid inventory"):
            storage.save(inventory)
