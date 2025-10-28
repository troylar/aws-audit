"""Unit tests for Inventory model."""

from datetime import datetime, timezone

from src.models.inventory import Inventory


class TestInventoryModel:
    """Test cases for Inventory data model."""

    def test_inventory_creation(self):
        """Test creating a basic inventory."""
        inventory = Inventory(
            name="test",
            account_id="123456789012",
            description="Test inventory",
        )

        assert inventory.name == "test"
        assert inventory.account_id == "123456789012"
        assert inventory.description == "Test inventory"
        assert inventory.include_tags == {}
        assert inventory.exclude_tags == {}
        assert inventory.snapshots == []
        assert inventory.active_snapshot is None
        assert isinstance(inventory.created_at, datetime)
        assert isinstance(inventory.last_updated, datetime)

    def test_inventory_with_filters(self):
        """Test creating inventory with tag filters."""
        inventory = Inventory(
            name="filtered",
            account_id="123456789012",
            include_tags={"Team": "Alpha"},
            exclude_tags={"Status": "archived"},
        )

        assert inventory.include_tags == {"Team": "Alpha"}
        assert inventory.exclude_tags == {"Status": "archived"}

    def test_to_dict(self, sample_inventory_data):
        """Test serializing inventory to dictionary."""
        inventory = Inventory.from_dict(sample_inventory_data)
        result = inventory.to_dict()

        assert result["name"] == "test-inventory"
        assert result["account_id"] == "123456789012"
        assert result["description"] == "Test inventory"
        assert result["include_tags"] == {"Environment": "production"}
        assert result["exclude_tags"] == {"Status": "archived"}
        assert result["snapshots"] == ["snapshot1.yaml", "snapshot2.yaml"]
        assert result["active_snapshot"] == "snapshot1.yaml"
        assert "created_at" in result
        assert "last_updated" in result

    def test_from_dict(self, sample_inventory_data):
        """Test deserializing inventory from dictionary."""
        inventory = Inventory.from_dict(sample_inventory_data)

        assert inventory.name == "test-inventory"
        assert inventory.account_id == "123456789012"
        assert inventory.description == "Test inventory"
        assert inventory.include_tags == {"Environment": "production"}
        assert inventory.exclude_tags == {"Status": "archived"}
        assert len(inventory.snapshots) == 2
        assert inventory.active_snapshot == "snapshot1.yaml"

    def test_add_snapshot(self):
        """Test adding snapshot to inventory."""
        inventory = Inventory(name="test", account_id="123456789012")

        # Add first snapshot
        inventory.add_snapshot("snap1.yaml", set_active=True)
        assert len(inventory.snapshots) == 1
        assert "snap1.yaml" in inventory.snapshots
        assert inventory.active_snapshot == "snap1.yaml"

        # Add second snapshot without setting active
        inventory.add_snapshot("snap2.yaml", set_active=False)
        assert len(inventory.snapshots) == 2
        assert inventory.active_snapshot == "snap1.yaml"

        # Add third snapshot and set as active
        inventory.add_snapshot("snap3.yaml", set_active=True)
        assert len(inventory.snapshots) == 3
        assert inventory.active_snapshot == "snap3.yaml"

    def test_add_snapshot_duplicate(self):
        """Test adding duplicate snapshot (should not duplicate)."""
        inventory = Inventory(name="test", account_id="123456789012")

        inventory.add_snapshot("snap1.yaml")
        inventory.add_snapshot("snap1.yaml")

        assert len(inventory.snapshots) == 1

    def test_remove_snapshot(self):
        """Test removing snapshot from inventory."""
        inventory = Inventory(
            name="test",
            account_id="123456789012",
            snapshots=["snap1.yaml", "snap2.yaml"],
            active_snapshot="snap1.yaml",
        )

        # Remove non-active snapshot
        inventory.remove_snapshot("snap2.yaml")
        assert len(inventory.snapshots) == 1
        assert inventory.active_snapshot == "snap1.yaml"

        # Remove active snapshot
        inventory.remove_snapshot("snap1.yaml")
        assert len(inventory.snapshots) == 0
        assert inventory.active_snapshot is None

    def test_remove_nonexistent_snapshot(self):
        """Test removing snapshot that doesn't exist (should not error)."""
        inventory = Inventory(
            name="test",
            account_id="123456789012",
            snapshots=["snap1.yaml"],
        )

        inventory.remove_snapshot("nonexistent.yaml")
        assert len(inventory.snapshots) == 1

    def test_validate_valid_inventory(self):
        """Test validation of valid inventory."""
        inventory = Inventory(
            name="valid-inventory_123",
            account_id="123456789012",
            snapshots=["snap1.yaml"],
            active_snapshot="snap1.yaml",
        )

        errors = inventory.validate()
        assert len(errors) == 0

    def test_validate_invalid_name_format(self):
        """Test validation with invalid name format."""
        inventory = Inventory(
            name="invalid name!",  # Spaces and special chars
            account_id="123456789012",
        )

        errors = inventory.validate()
        assert len(errors) == 1
        assert "alphanumeric" in errors[0].lower()

    def test_validate_empty_name(self):
        """Test validation with empty name."""
        inventory = Inventory(
            name="",
            account_id="123456789012",
        )

        errors = inventory.validate()
        assert len(errors) > 0

    def test_validate_long_name(self):
        """Test validation with name exceeding 50 characters."""
        inventory = Inventory(
            name="a" * 51,  # 51 characters
            account_id="123456789012",
        )

        errors = inventory.validate()
        assert any("50 characters" in err for err in errors)

    def test_validate_invalid_account_id(self):
        """Test validation with invalid account ID."""
        # Too short
        inventory = Inventory(
            name="test",
            account_id="12345",
        )
        errors = inventory.validate()
        assert any("12 digits" in err for err in errors)

        # Contains letters
        inventory = Inventory(
            name="test",
            account_id="12345678901a",
        )
        errors = inventory.validate()
        assert any("12 digits" in err for err in errors)

    def test_validate_active_snapshot_not_in_list(self):
        """Test validation when active snapshot is not in snapshots list."""
        inventory = Inventory(
            name="test",
            account_id="123456789012",
            snapshots=["snap1.yaml"],
            active_snapshot="snap2.yaml",  # Not in list
        )

        errors = inventory.validate()
        assert any("active snapshot" in err.lower() for err in errors)

    def test_last_updated_changes_on_add(self):
        """Test that last_updated changes when adding snapshot."""
        inventory = Inventory(name="test", account_id="123456789012")
        original_updated = inventory.last_updated

        # Wait a tiny bit to ensure timestamp difference
        import time

        time.sleep(0.01)

        inventory.add_snapshot("snap1.yaml")
        assert inventory.last_updated > original_updated

    def test_last_updated_changes_on_remove(self):
        """Test that last_updated changes when removing snapshot."""
        inventory = Inventory(
            name="test",
            account_id="123456789012",
            snapshots=["snap1.yaml"],
        )
        original_updated = inventory.last_updated

        # Wait a tiny bit to ensure timestamp difference
        import time

        time.sleep(0.01)

        inventory.remove_snapshot("snap1.yaml")
        assert inventory.last_updated > original_updated

    def test_inventory_with_all_fields(self):
        """Test inventory with all possible fields populated."""
        now = datetime.now(timezone.utc)
        inventory = Inventory(
            name="comprehensive-test",
            account_id="123456789012",
            include_tags={"Env": "prod", "Team": "Platform"},
            exclude_tags={"Status": "archived", "Temp": "true"},
            snapshots=["s1.yaml", "s2.yaml", "s3.yaml"],
            active_snapshot="s2.yaml",
            description="Comprehensive test inventory",
            created_at=now,
            last_updated=now,
        )

        assert inventory.name == "comprehensive-test"
        assert len(inventory.include_tags) == 2
        assert len(inventory.exclude_tags) == 2
        assert len(inventory.snapshots) == 3
        assert inventory.active_snapshot == "s2.yaml"
        assert inventory.description == "Comprehensive test inventory"
