"""Unit tests for InventoryStorage service."""

from pathlib import Path

import pytest
import yaml

from src.models.inventory import Inventory
from src.snapshot.inventory_storage import InventoryNotFoundError, InventoryStorage


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
        """Test loading inventories from file."""
        storage = InventoryStorage(str(temp_dir))

        # Create inventories.yaml file
        data = {"inventories": [sample_inventory_data]}
        with open(storage.inventory_file, "w") as f:
            yaml.safe_dump(data, f)

        inventories = storage.load_all()

        assert len(inventories) == 1
        assert inventories[0].name == "test-inventory"
        assert inventories[0].account_id == "123456789012"

    def test_load_all_corrupted_file(self, temp_dir):
        """Test loading inventories from corrupted YAML file."""
        storage = InventoryStorage(str(temp_dir))

        # Create corrupted YAML file
        with open(storage.inventory_file, "w") as f:
            f.write("invalid: yaml: content: [[[")

        with pytest.raises(ValueError, match="Corrupted inventories file"):
            storage.load_all()

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
        storage = InventoryStorage(str(temp_dir))

        # Create initial inventory
        inventory = Inventory(
            name="test",
            account_id="123456789012",
            description="Original",
        )
        storage.save(inventory)

        # Update it
        inventory.description = "Updated"
        inventory.add_snapshot("new-snap.yaml")
        storage.save(inventory)

        # Verify update
        retrieved = storage.get_by_name("test", "123456789012")
        assert retrieved.description == "Updated"
        assert len(retrieved.snapshots) == 1
        assert "new-snap.yaml" in retrieved.snapshots

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
        """Test deleting inventory and its snapshot files."""
        storage = InventoryStorage(str(temp_dir))

        # Create snapshots directory and files
        snapshots_dir = temp_dir / "snapshots"
        snapshots_dir.mkdir()
        snap1 = snapshots_dir / "snap1.yaml"
        snap2 = snapshots_dir / "snap2.yaml"
        snap1.write_text("snapshot data")
        snap2.write_text("snapshot data")

        # Create inventory with snapshots
        inventory = Inventory(
            name="with-snaps",
            account_id="123456789012",
            snapshots=["snap1.yaml", "snap2.yaml"],
        )
        storage.save(inventory)

        # Delete with snapshot files
        deleted_count = storage.delete("with-snaps", "123456789012", delete_snapshots=True)
        assert deleted_count == 2

        # Verify snapshot files deleted
        assert not snap1.exists()
        assert not snap2.exists()

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

    def test_atomic_write_creates_temp_file(self, temp_dir):
        """Test that atomic write uses temporary file."""
        storage = InventoryStorage(str(temp_dir))

        inventory = Inventory(name="test", account_id="123456789012")
        storage.save(inventory)

        # Temp file should not exist after successful write
        temp_file = storage.inventory_file.with_suffix(".tmp")
        assert not temp_file.exists()

        # Main file should exist
        assert storage.inventory_file.exists()

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

    def test_empty_inventories_file_structure(self, temp_dir):
        """Test file structure when saving first inventory."""
        storage = InventoryStorage(str(temp_dir))

        inventory = Inventory(name="first", account_id="123456789012")
        storage.save(inventory)

        # Load and check structure
        with open(storage.inventory_file) as f:
            data = yaml.safe_load(f)

        assert "inventories" in data
        assert isinstance(data["inventories"], list)
        assert len(data["inventories"]) == 1
