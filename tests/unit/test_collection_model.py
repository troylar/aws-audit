"""Unit tests for Collection model."""

from datetime import datetime, timezone

from src.models.collection import Collection


class TestCollectionModel:
    """Test cases for Collection data model."""

    def test_collection_creation(self):
        """Test creating a basic collection."""
        collection = Collection(
            name="test",
            account_id="123456789012",
            description="Test collection",
        )

        assert collection.name == "test"
        assert collection.account_id == "123456789012"
        assert collection.description == "Test collection"
        assert collection.include_tags == {}
        assert collection.exclude_tags == {}
        assert collection.snapshots == []
        assert collection.active_snapshot is None
        assert isinstance(collection.created_at, datetime)
        assert isinstance(collection.last_updated, datetime)

    def test_collection_with_filters(self):
        """Test creating collection with tag filters."""
        collection = Collection(
            name="filtered",
            account_id="123456789012",
            include_tags={"Team": "Alpha"},
            exclude_tags={"Status": "archived"},
        )

        assert collection.include_tags == {"Team": "Alpha"}
        assert collection.exclude_tags == {"Status": "archived"}

    def test_to_dict(self, sample_collection_data):
        """Test serializing collection to dictionary."""
        collection = Collection.from_dict(sample_collection_data)
        result = collection.to_dict()

        assert result["name"] == "test-collection"
        assert result["account_id"] == "123456789012"
        assert result["description"] == "Test collection"
        assert result["include_tags"] == {"Environment": "production"}
        assert result["exclude_tags"] == {"Status": "archived"}
        assert result["snapshots"] == ["snapshot1.yaml", "snapshot2.yaml"]
        assert result["active_snapshot"] == "snapshot1.yaml"
        assert "created_at" in result
        assert "last_updated" in result

    def test_from_dict(self, sample_collection_data):
        """Test deserializing collection from dictionary."""
        collection = Collection.from_dict(sample_collection_data)

        assert collection.name == "test-collection"
        assert collection.account_id == "123456789012"
        assert collection.description == "Test collection"
        assert collection.include_tags == {"Environment": "production"}
        assert collection.exclude_tags == {"Status": "archived"}
        assert len(collection.snapshots) == 2
        assert collection.active_snapshot == "snapshot1.yaml"

    def test_add_snapshot(self):
        """Test adding snapshot to collection."""
        collection = Collection(name="test", account_id="123456789012")

        # Add first snapshot
        collection.add_snapshot("snap1.yaml", set_active=True)
        assert len(collection.snapshots) == 1
        assert "snap1.yaml" in collection.snapshots
        assert collection.active_snapshot == "snap1.yaml"

        # Add second snapshot without setting active
        collection.add_snapshot("snap2.yaml", set_active=False)
        assert len(collection.snapshots) == 2
        assert collection.active_snapshot == "snap1.yaml"

        # Add third snapshot and set as active
        collection.add_snapshot("snap3.yaml", set_active=True)
        assert len(collection.snapshots) == 3
        assert collection.active_snapshot == "snap3.yaml"

    def test_add_snapshot_duplicate(self):
        """Test adding duplicate snapshot (should not duplicate)."""
        collection = Collection(name="test", account_id="123456789012")

        collection.add_snapshot("snap1.yaml")
        collection.add_snapshot("snap1.yaml")

        assert len(collection.snapshots) == 1

    def test_remove_snapshot(self):
        """Test removing snapshot from collection."""
        collection = Collection(
            name="test",
            account_id="123456789012",
            snapshots=["snap1.yaml", "snap2.yaml"],
            active_snapshot="snap1.yaml",
        )

        # Remove non-active snapshot
        collection.remove_snapshot("snap2.yaml")
        assert len(collection.snapshots) == 1
        assert collection.active_snapshot == "snap1.yaml"

        # Remove active snapshot
        collection.remove_snapshot("snap1.yaml")
        assert len(collection.snapshots) == 0
        assert collection.active_snapshot is None

    def test_remove_nonexistent_snapshot(self):
        """Test removing snapshot that doesn't exist (should not error)."""
        collection = Collection(
            name="test",
            account_id="123456789012",
            snapshots=["snap1.yaml"],
        )

        collection.remove_snapshot("nonexistent.yaml")
        assert len(collection.snapshots) == 1

    def test_validate_valid_collection(self):
        """Test validation of valid collection."""
        collection = Collection(
            name="valid-collection_123",
            account_id="123456789012",
            snapshots=["snap1.yaml"],
            active_snapshot="snap1.yaml",
        )

        errors = collection.validate()
        assert len(errors) == 0

    def test_validate_invalid_name_format(self):
        """Test validation with invalid name format."""
        collection = Collection(
            name="invalid name!",  # Spaces and special chars
            account_id="123456789012",
        )

        errors = collection.validate()
        assert len(errors) == 1
        assert "alphanumeric" in errors[0].lower()

    def test_validate_empty_name(self):
        """Test validation with empty name."""
        collection = Collection(
            name="",
            account_id="123456789012",
        )

        errors = collection.validate()
        assert len(errors) > 0

    def test_validate_long_name(self):
        """Test validation with name exceeding 50 characters."""
        collection = Collection(
            name="a" * 51,  # 51 characters
            account_id="123456789012",
        )

        errors = collection.validate()
        assert any("50 characters" in err for err in errors)

    def test_validate_invalid_account_id(self):
        """Test validation with invalid account ID."""
        # Too short
        collection = Collection(
            name="test",
            account_id="12345",
        )
        errors = collection.validate()
        assert any("12 digits" in err for err in errors)

        # Contains letters
        collection = Collection(
            name="test",
            account_id="12345678901a",
        )
        errors = collection.validate()
        assert any("12 digits" in err for err in errors)

    def test_validate_active_snapshot_not_in_list(self):
        """Test validation when active snapshot is not in snapshots list."""
        collection = Collection(
            name="test",
            account_id="123456789012",
            snapshots=["snap1.yaml"],
            active_snapshot="snap2.yaml",  # Not in list
        )

        errors = collection.validate()
        assert any("active snapshot" in err.lower() for err in errors)

    def test_last_updated_changes_on_add(self):
        """Test that last_updated changes when adding snapshot."""
        collection = Collection(name="test", account_id="123456789012")
        original_updated = collection.last_updated

        # Wait a tiny bit to ensure timestamp difference
        import time

        time.sleep(0.01)

        collection.add_snapshot("snap1.yaml")
        assert collection.last_updated > original_updated

    def test_last_updated_changes_on_remove(self):
        """Test that last_updated changes when removing snapshot."""
        collection = Collection(
            name="test",
            account_id="123456789012",
            snapshots=["snap1.yaml"],
        )
        original_updated = collection.last_updated

        # Wait a tiny bit to ensure timestamp difference
        import time

        time.sleep(0.01)

        collection.remove_snapshot("snap1.yaml")
        assert collection.last_updated > original_updated

    def test_collection_with_all_fields(self):
        """Test collection with all possible fields populated."""
        now = datetime.now(timezone.utc)
        collection = Collection(
            name="comprehensive-test",
            account_id="123456789012",
            include_tags={"Env": "prod", "Team": "Platform"},
            exclude_tags={"Status": "archived", "Temp": "true"},
            snapshots=["s1.yaml", "s2.yaml", "s3.yaml"],
            active_snapshot="s2.yaml",
            description="Comprehensive test collection",
            created_at=now,
            last_updated=now,
        )

        assert collection.name == "comprehensive-test"
        assert len(collection.include_tags) == 2
        assert len(collection.exclude_tags) == 2
        assert len(collection.snapshots) == 3
        assert collection.active_snapshot == "s2.yaml"
        assert collection.description == "Comprehensive test collection"

    def test_collection_from_dict_with_datetime_objects(self):
        """Test deserializing collection when datetime fields are already datetime objects.

        This can happen when PyYAML auto-parses ISO datetime strings.
        Regression test for issue #36.
        """
        created_at = datetime(2024, 3, 15, 14, 30, 0, tzinfo=timezone.utc)
        last_updated = datetime(2024, 3, 16, 10, 0, 0, tzinfo=timezone.utc)
        data = {
            "name": "test-collection",
            "account_id": "123456789012",
            "description": "Test",
            "include_tags": {},
            "exclude_tags": {},
            "snapshots": [],
            "active_snapshot": None,
            "created_at": created_at,  # datetime object, not string
            "last_updated": last_updated,  # datetime object, not string
        }
        collection = Collection.from_dict(data)

        assert collection.created_at == created_at
        assert collection.last_updated == last_updated
        # Ensure to_dict works correctly after from_dict with datetime
        data_out = collection.to_dict()
        assert data_out["created_at"] == "2024-03-15T14:30:00+00:00"
        assert data_out["last_updated"] == "2024-03-16T10:00:00+00:00"

    def test_collection_from_dict_with_string_datetimes(self):
        """Test deserializing collection when datetime fields are strings.

        This is the normal case when loading from serialized YAML.
        """
        data = {
            "name": "test-collection",
            "account_id": "123456789012",
            "description": "Test",
            "include_tags": {},
            "exclude_tags": {},
            "snapshots": [],
            "active_snapshot": None,
            "created_at": "2024-03-15T14:30:00+00:00",  # string
            "last_updated": "2024-03-16T10:00:00+00:00",  # string
        }
        collection = Collection.from_dict(data)

        assert collection.created_at == datetime(2024, 3, 15, 14, 30, 0, tzinfo=timezone.utc)
        assert collection.last_updated == datetime(2024, 3, 16, 10, 0, 0, tzinfo=timezone.utc)
        # Ensure to_dict works correctly
        data_out = collection.to_dict()
        assert data_out["created_at"] == "2024-03-15T14:30:00+00:00"
        assert data_out["last_updated"] == "2024-03-16T10:00:00+00:00"

    def test_collection_from_dict_with_mixed_datetime_types(self):
        """Test deserializing collection when one datetime field is a string and one is datetime.

        This is an edge case to ensure both fields are handled independently.
        Regression test for issue #36.
        """
        created_at = datetime(2024, 3, 15, 14, 30, 0, tzinfo=timezone.utc)
        data = {
            "name": "test-collection",
            "account_id": "123456789012",
            "description": "Test",
            "include_tags": {},
            "exclude_tags": {},
            "snapshots": [],
            "active_snapshot": None,
            "created_at": created_at,  # datetime object
            "last_updated": "2024-03-16T10:00:00+00:00",  # string
        }
        collection = Collection.from_dict(data)

        assert collection.created_at == created_at
        assert collection.last_updated == datetime(2024, 3, 16, 10, 0, 0, tzinfo=timezone.utc)
