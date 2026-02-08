"""Unit tests for snapshot storage with schema version support."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from src.models.resource import Resource
from src.models.snapshot import Snapshot
from src.snapshot.storage import SnapshotStorage


@pytest.fixture
def temp_storage_dir(tmp_path: Path) -> Path:
    """Create a temporary storage directory for tests."""
    storage_dir = tmp_path / "test_snapshots"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return storage_dir


@pytest.fixture
def sample_resource_v11() -> Resource:
    """Create a sample resource with raw_config (v1.1 format)."""
    return Resource(
        arn="arn:aws:s3:::test-bucket",
        resource_type="s3:bucket",
        name="test-bucket",
        region="us-east-1",
        config_hash="a" * 64,
        raw_config={"BucketName": "test-bucket", "Versioning": {"Status": "Enabled"}},
        tags={"Environment": "test"},
        created_at=datetime(2025, 1, 10, 12, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def sample_snapshot_v11(sample_resource_v11: Resource) -> Snapshot:
    """Create a sample v1.1 snapshot with raw_config."""
    return Snapshot(
        name="test-snapshot-v11",
        created_at=datetime(2025, 1, 10, 12, 0, 0, tzinfo=timezone.utc),
        account_id="123456789012",
        regions=["us-east-1"],
        resources=[sample_resource_v11],
        schema_version="1.1",
    )


class TestSchemaVersionBackwardCompatibility:
    """Tests for snapshot schema version backward compatibility."""

    def test_read_v10_snapshot_without_raw_config(self, temp_storage_dir: Path) -> None:
        """Test that v1.0 snapshots without raw_config can be loaded."""
        # Create a v1.0 snapshot file manually (no raw_config, no schema_version)
        v10_snapshot_data = {
            "name": "test-v10",
            "created_at": "2025-01-10T12:00:00+00:00",
            "account_id": "123456789012",
            "regions": ["us-east-1"],
            "is_active": True,
            "resource_count": 1,
            "service_counts": {"s3": 1},
            "metadata": {},
            "collection_name": "default",
            "resources": [
                {
                    "arn": "arn:aws:s3:::old-bucket",
                    "type": "s3:bucket",
                    "name": "old-bucket",
                    "region": "us-east-1",
                    "tags": {},
                    "config_hash": "b" * 64,
                    "created_at": None,
                    # No raw_config field
                }
            ],
        }

        # Write v1.0 snapshot file
        snapshot_file = temp_storage_dir / "test-v10.yaml"
        with open(snapshot_file, "w") as f:
            yaml.dump(v10_snapshot_data, f)

        # Load using SnapshotStorage
        storage = SnapshotStorage(temp_storage_dir)
        snapshot = storage.load_snapshot("test-v10")

        # Verify it loaded correctly
        assert snapshot.name == "test-v10"
        assert snapshot.schema_version == "1.0"  # Defaults to 1.0
        assert len(snapshot.resources) == 1
        assert snapshot.resources[0].arn == "arn:aws:s3:::old-bucket"
        assert snapshot.resources[0].raw_config is None  # raw_config is None for v1.0

    def test_write_v11_snapshot_with_raw_config(self, temp_storage_dir: Path, sample_snapshot_v11: Snapshot) -> None:
        """Test that v1.1 snapshots with raw_config are saved correctly (now uses SQLite)."""
        storage = SnapshotStorage(temp_storage_dir)
        filepath = storage.save_snapshot(sample_snapshot_v11)

        # Verify database file was created
        assert filepath.exists()
        assert filepath.name == "inventory.db"

        # Verify data via load (SQLite storage)
        loaded = storage.load_snapshot("test-snapshot-v11")
        assert loaded.schema_version == "1.1"
        assert len(loaded.resources) == 1
        assert loaded.resources[0].raw_config is not None
        assert loaded.resources[0].raw_config["BucketName"] == "test-bucket"  # type: ignore

    def test_read_v11_snapshot_with_raw_config(self, temp_storage_dir: Path, sample_snapshot_v11: Snapshot) -> None:
        """Test that v1.1 snapshots with raw_config can be loaded."""
        storage = SnapshotStorage(temp_storage_dir)
        storage.save_snapshot(sample_snapshot_v11)

        # Load it back
        loaded_snapshot = storage.load_snapshot("test-snapshot-v11")

        # Verify v1.1 fields
        assert loaded_snapshot.schema_version == "1.1"
        assert len(loaded_snapshot.resources) == 1
        assert loaded_snapshot.resources[0].raw_config is not None
        assert loaded_snapshot.resources[0].raw_config["BucketName"] == "test-bucket"  # type: ignore
        assert loaded_snapshot.resources[0].raw_config["Versioning"]["Status"] == "Enabled"  # type: ignore

    def test_mixed_version_snapshots(self, temp_storage_dir: Path, sample_snapshot_v11: Snapshot) -> None:
        """Test that storage can handle both v1.0 and v1.1 snapshots."""
        storage = SnapshotStorage(temp_storage_dir)

        # Create a v1.0 style snapshot (no raw_config)
        v10_snapshot = Snapshot(
            name="old-snapshot",
            created_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-west-2"],
            resources=[
                Resource(
                    arn="arn:aws:ec2:us-west-2:123456789012:instance/i-old",
                    resource_type="ec2:instance",
                    name="old-instance",
                    region="us-west-2",
                    config_hash="c" * 64,
                    tags={},
                    raw_config=None,  # v1.0 style - no raw_config
                )
            ],
            schema_version="1.0",
        )
        storage.save_snapshot(v10_snapshot)

        # Save a v1.1 snapshot
        storage.save_snapshot(sample_snapshot_v11)

        # List snapshots - should show both
        snapshots = storage.list_snapshots()
        assert len(snapshots) >= 2

        snapshot_names = [s["name"] for s in snapshots]
        assert "old-snapshot" in snapshot_names
        assert "test-snapshot-v11" in snapshot_names

        # Load both and verify they work
        v10_loaded = storage.load_snapshot("old-snapshot")
        assert v10_loaded.schema_version == "1.0"
        assert v10_loaded.resources[0].raw_config is None

        v11_loaded = storage.load_snapshot("test-snapshot-v11")
        assert v11_loaded.schema_version == "1.1"
        assert v11_loaded.resources[0].raw_config is not None


class TestResourceModel:
    """Tests for Resource model with optional raw_config."""

    def test_resource_with_raw_config(self) -> None:
        """Test creating a resource with raw_config."""
        resource = Resource(
            arn="arn:aws:rds:us-east-1:123456789012:db:mydb",
            resource_type="rds:db",
            name="mydb",
            region="us-east-1",
            config_hash="d" * 64,
            raw_config={"DBInstanceIdentifier": "mydb", "Engine": "postgres"},
        )

        assert resource.raw_config is not None
        assert resource.raw_config["Engine"] == "postgres"  # type: ignore

    def test_resource_without_raw_config(self) -> None:
        """Test creating a resource without raw_config (v1.0 compatibility)."""
        resource = Resource(
            arn="arn:aws:rds:us-east-1:123456789012:db:mydb",
            resource_type="rds:db",
            name="mydb",
            region="us-east-1",
            config_hash="d" * 64,
            raw_config=None,
        )

        assert resource.raw_config is None

    def test_resource_to_dict_with_raw_config(self) -> None:
        """Test that to_dict includes raw_config."""
        resource = Resource(
            arn="arn:aws:s3:::bucket",
            resource_type="s3:bucket",
            name="bucket",
            region="us-east-1",
            config_hash="e" * 64,
            raw_config={"Name": "bucket"},
        )

        data = resource.to_dict()

        assert "raw_config" in data
        assert data["raw_config"]["Name"] == "bucket"

    def test_resource_to_dict_without_raw_config(self) -> None:
        """Test that to_dict handles None raw_config."""
        resource = Resource(
            arn="arn:aws:s3:::bucket",
            resource_type="s3:bucket",
            name="bucket",
            region="us-east-1",
            config_hash="e" * 64,
            raw_config=None,
        )

        data = resource.to_dict()

        assert "raw_config" in data
        assert data["raw_config"] == {}  # Converts None to empty dict for serialization

    def test_resource_from_dict_with_raw_config(self) -> None:
        """Test creating Resource from dict with raw_config."""
        data = {
            "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-12345",
            "type": "ec2:instance",
            "name": "my-instance",
            "region": "us-east-1",
            "config_hash": "f" * 64,
            "raw_config": {"InstanceId": "i-12345", "InstanceType": "t2.micro"},
            "tags": {"Env": "prod"},
            "created_at": "2025-01-10T00:00:00+00:00",
        }

        resource = Resource.from_dict(data)

        assert resource.raw_config is not None
        assert resource.raw_config["InstanceType"] == "t2.micro"  # type: ignore

    def test_resource_from_dict_without_raw_config(self) -> None:
        """Test creating Resource from dict without raw_config (v1.0)."""
        data = {
            "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-12345",
            "type": "ec2:instance",
            "name": "my-instance",
            "region": "us-east-1",
            "config_hash": "f" * 64,
            "tags": {},
            "created_at": None,
        }

        resource = Resource.from_dict(data)

        assert resource.raw_config is None  # Should be None, not raise an error


class TestSnapshotModel:
    """Tests for Snapshot model with schema_version."""

    def test_snapshot_defaults_to_v11(self) -> None:
        """Test that new snapshots default to schema version 1.1."""
        snapshot = Snapshot(
            name="new-snapshot",
            created_at=datetime(2025, 1, 10, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
        )

        assert snapshot.schema_version == "1.1"

    def test_snapshot_to_dict_includes_schema_version(self) -> None:
        """Test that to_dict includes schema_version."""
        snapshot = Snapshot(
            name="test",
            created_at=datetime(2025, 1, 10, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
            schema_version="1.1",
        )

        data = snapshot.to_dict()

        assert "schema_version" in data
        assert data["schema_version"] == "1.1"

    def test_snapshot_from_dict_with_schema_version(self) -> None:
        """Test creating Snapshot from dict with schema_version."""
        data = {
            "schema_version": "1.1",
            "name": "test",
            "created_at": "2025-01-10T00:00:00+00:00",
            "account_id": "123456789012",
            "regions": ["us-east-1"],
            "resources": [],
        }

        snapshot = Snapshot.from_dict(data)

        assert snapshot.schema_version == "1.1"

    def test_snapshot_from_dict_defaults_to_v10(self) -> None:
        """Test that Snapshot.from_dict defaults to v1.0 for old snapshots."""
        data = {
            # No schema_version field
            "name": "old-snapshot",
            "created_at": "2024-01-01T00:00:00+00:00",
            "account_id": "123456789012",
            "regions": ["us-east-1"],
            "resources": [],
        }

        snapshot = Snapshot.from_dict(data)

        assert snapshot.schema_version == "1.0"  # Defaults to 1.0 for backward compatibility
