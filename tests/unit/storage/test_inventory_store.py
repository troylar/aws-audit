"""Unit tests for InventoryStore."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.models.inventory import Inventory
from src.models.snapshot import Snapshot
from src.storage.database import Database
from src.storage.inventory_store import InventoryStore
from src.storage.snapshot_store import SnapshotStore


@pytest.fixture
def db(tmp_path: Path) -> Database:
    """Create a test database."""
    database = Database(storage_path=tmp_path)
    database.ensure_schema()
    return database


@pytest.fixture
def store(db: Database) -> InventoryStore:
    """Create an inventory store."""
    return InventoryStore(db)


@pytest.fixture
def snapshot_store(db: Database) -> SnapshotStore:
    """Create a snapshot store."""
    return SnapshotStore(db)


@pytest.fixture
def sample_inventory() -> Inventory:
    """Create a sample inventory."""
    return Inventory(
        name="test-inventory",
        account_id="123456789012",
        description="Test inventory description",
        include_tags={"Environment": "test"},
        exclude_tags={"Temporary": "true"},
        created_at=datetime(2025, 1, 10, 12, 0, 0, tzinfo=timezone.utc),
        last_updated=datetime(2025, 1, 10, 12, 0, 0, tzinfo=timezone.utc),
    )


class TestInventoryStore:
    """Test cases for InventoryStore."""

    def test_save_new_inventory(self, store: InventoryStore, sample_inventory: Inventory) -> None:
        """Test saving a new inventory."""
        inventory_id = store.save(sample_inventory)

        assert inventory_id > 0

    def test_save_and_load_inventory(self, store: InventoryStore, sample_inventory: Inventory) -> None:
        """Test saving and loading an inventory."""
        store.save(sample_inventory)

        loaded = store.load("test-inventory", "123456789012")

        assert loaded is not None
        assert loaded.name == "test-inventory"
        assert loaded.account_id == "123456789012"
        assert loaded.description == "Test inventory description"

    def test_load_inventory_with_tags(self, store: InventoryStore, sample_inventory: Inventory) -> None:
        """Test that loading inventory includes tags."""
        store.save(sample_inventory)

        loaded = store.load("test-inventory", "123456789012")

        assert loaded.include_tags == {"Environment": "test"}
        assert loaded.exclude_tags == {"Temporary": "true"}

    def test_load_nonexistent_inventory(self, store: InventoryStore) -> None:
        """Test loading an inventory that doesn't exist."""
        loaded = store.load("nonexistent", "123456789012")

        assert loaded is None

    def test_list_all_empty(self, store: InventoryStore) -> None:
        """Test listing inventories when none exist."""
        inventories = store.list_all()

        assert inventories == []

    def test_list_all_with_inventories(self, store: InventoryStore) -> None:
        """Test listing multiple inventories."""
        inv1 = Inventory(name="inv1", account_id="111111111111")
        inv2 = Inventory(name="inv2", account_id="222222222222")
        inv3 = Inventory(name="inv3", account_id="111111111111")

        store.save(inv1)
        store.save(inv2)
        store.save(inv3)

        inventories = store.list_all()

        assert len(inventories) == 3

    def test_list_by_account(self, store: InventoryStore) -> None:
        """Test listing inventories filtered by account."""
        inv1 = Inventory(name="inv1", account_id="111111111111")
        inv2 = Inventory(name="inv2", account_id="222222222222")
        inv3 = Inventory(name="inv3", account_id="111111111111")

        store.save(inv1)
        store.save(inv2)
        store.save(inv3)

        account1_invs = store.list_by_account("111111111111")
        account2_invs = store.list_by_account("222222222222")

        assert len(account1_invs) == 2
        assert len(account2_invs) == 1
        assert all(inv.account_id == "111111111111" for inv in account1_invs)

    def test_delete_inventory(self, store: InventoryStore, sample_inventory: Inventory) -> None:
        """Test deleting an inventory."""
        store.save(sample_inventory)

        result = store.delete("test-inventory", "123456789012")

        assert result is True
        assert store.load("test-inventory", "123456789012") is None

    def test_delete_nonexistent_inventory(self, store: InventoryStore) -> None:
        """Test deleting an inventory that doesn't exist."""
        result = store.delete("nonexistent", "123456789012")

        assert result is False

    def test_exists_true(self, store: InventoryStore, sample_inventory: Inventory) -> None:
        """Test exists returns True for existing inventory."""
        store.save(sample_inventory)

        assert store.exists("test-inventory", "123456789012") is True

    def test_exists_false(self, store: InventoryStore) -> None:
        """Test exists returns False for nonexistent inventory."""
        assert store.exists("nonexistent", "123456789012") is False

    def test_get_id(self, store: InventoryStore, sample_inventory: Inventory) -> None:
        """Test getting inventory ID."""
        inventory_id = store.save(sample_inventory)

        retrieved_id = store.get_id("test-inventory", "123456789012")

        assert retrieved_id == inventory_id

    def test_get_id_nonexistent(self, store: InventoryStore) -> None:
        """Test getting ID of nonexistent inventory."""
        retrieved_id = store.get_id("nonexistent", "123456789012")

        assert retrieved_id is None

    def test_save_updates_existing(self, store: InventoryStore, sample_inventory: Inventory) -> None:
        """Test that saving with same name updates existing inventory."""
        store.save(sample_inventory)

        # Modify and save again
        sample_inventory.description = "Updated description"
        store.save(sample_inventory)

        # Verify updated
        loaded = store.load("test-inventory", "123456789012")
        assert loaded.description == "Updated description"

        # Should only have one inventory
        inventories = store.list_all()
        assert len(inventories) == 1

    def test_inventory_with_snapshots(
        self, store: InventoryStore, snapshot_store: SnapshotStore, sample_inventory: Inventory
    ) -> None:
        """Test inventory with linked snapshots."""
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

        # Add snapshots to inventory
        sample_inventory.snapshots = ["snap1", "snap2"]
        store.save(sample_inventory)

        # Load and verify
        loaded = store.load("test-inventory", "123456789012")
        assert len(loaded.snapshots) == 2
        assert "snap1" in loaded.snapshots
        assert "snap2" in loaded.snapshots

    def test_inventory_with_active_snapshot(
        self, store: InventoryStore, snapshot_store: SnapshotStore, sample_inventory: Inventory
    ) -> None:
        """Test inventory with active snapshot."""
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
        sample_inventory.snapshots = ["active-snap"]
        sample_inventory.active_snapshot = "active-snap"
        store.save(sample_inventory)

        # Load and verify
        loaded = store.load("test-inventory", "123456789012")
        assert loaded.active_snapshot == "active-snap"

    def test_add_snapshot_to_inventory(
        self, store: InventoryStore, snapshot_store: SnapshotStore
    ) -> None:
        """Test adding a snapshot to an inventory."""
        # Create inventory
        inv = Inventory(name="test", account_id="123456789012")
        store.save(inv)

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
        result = store.add_snapshot_to_inventory("test", "123456789012", "new-snap")

        assert result is True
        loaded = store.load("test", "123456789012")
        assert "new-snap" in loaded.snapshots

    def test_add_snapshot_to_inventory_and_set_active(
        self, store: InventoryStore, snapshot_store: SnapshotStore
    ) -> None:
        """Test adding a snapshot and setting it as active."""
        # Create inventory
        inv = Inventory(name="test", account_id="123456789012")
        store.save(inv)

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
        result = store.add_snapshot_to_inventory("test", "123456789012", "active-snap", set_active=True)

        assert result is True
        loaded = store.load("test", "123456789012")
        assert loaded.active_snapshot == "active-snap"

    def test_remove_snapshot_from_inventory(
        self, store: InventoryStore, snapshot_store: SnapshotStore
    ) -> None:
        """Test removing a snapshot from an inventory."""
        # Create snapshot first
        snap = Snapshot(
            name="to-remove",
            created_at=datetime.now(timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
        )
        snapshot_store.save(snap)

        # Create inventory with snapshot
        inv = Inventory(name="test", account_id="123456789012", snapshots=["to-remove"])
        store.save(inv)

        # Remove snapshot
        result = store.remove_snapshot_from_inventory("test", "123456789012", "to-remove")

        assert result is True
        loaded = store.load("test", "123456789012")
        assert "to-remove" not in loaded.snapshots

    def test_unique_name_account_constraint(self, store: InventoryStore) -> None:
        """Test that same name in same account updates, not duplicates."""
        inv1 = Inventory(name="shared-name", account_id="123456789012", description="First")
        inv2 = Inventory(name="shared-name", account_id="123456789012", description="Second")

        store.save(inv1)
        store.save(inv2)

        # Should only have one inventory with updated description
        inventories = store.list_all()
        assert len(inventories) == 1
        assert inventories[0].description == "Second"

    def test_same_name_different_accounts(self, store: InventoryStore) -> None:
        """Test that same name in different accounts creates separate inventories."""
        inv1 = Inventory(name="shared-name", account_id="111111111111")
        inv2 = Inventory(name="shared-name", account_id="222222222222")

        store.save(inv1)
        store.save(inv2)

        # Should have two inventories
        inventories = store.list_all()
        assert len(inventories) == 2
