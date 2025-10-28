"""Unit tests for Snapshot model."""

import pytest
from datetime import datetime, timezone
from src.models.snapshot import Snapshot
from src.models.resource import Resource


class TestSnapshotModel:
    """Test cases for Snapshot model."""

    def test_snapshot_creation_basic(self):
        """Test creating a basic snapshot."""
        created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        snapshot = Snapshot(
            name="baseline-2024-01",
            created_at=created_at,
            account_id="123456789012",
            regions=["us-east-1", "us-west-2"],
            resources=[],
        )

        assert snapshot.name == "baseline-2024-01"
        assert snapshot.created_at == created_at
        assert snapshot.account_id == "123456789012"
        assert snapshot.regions == ["us-east-1", "us-west-2"]
        assert snapshot.resources == []
        assert snapshot.is_active is True
        assert snapshot.resource_count == 0
        assert snapshot.service_counts == {}
        assert snapshot.inventory_name == "default"

    def test_snapshot_creation_with_resources(self):
        """Test creating a snapshot with resources."""
        created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        resources = [
            Resource(
                arn="arn:aws:s3:::bucket1",
                resource_type="s3:bucket",
                name="bucket1",
                region="us-east-1",
                config_hash="a" * 64,
                raw_config={},
            ),
            Resource(
                arn="arn:aws:s3:::bucket2",
                resource_type="s3:bucket",
                name="bucket2",
                region="us-west-2",
                config_hash="b" * 64,
                raw_config={},
            ),
            Resource(
                arn="arn:aws:lambda:us-east-1:123456789012:function:func1",
                resource_type="lambda:function",
                name="func1",
                region="us-east-1",
                config_hash="c" * 64,
                raw_config={},
            ),
        ]

        snapshot = Snapshot(
            name="test-snapshot",
            created_at=created_at,
            account_id="123456789012",
            regions=["us-east-1", "us-west-2"],
            resources=resources,
        )

        assert snapshot.resource_count == 3
        assert snapshot.service_counts == {"s3": 2, "lambda": 1}

    def test_snapshot_post_init_calculates_counts(self):
        """Test that __post_init__ calculates resource counts."""
        created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        resources = [
            Resource(
                arn=f"arn:aws:ec2:us-east-1:123456789012:instance/i-{i}",
                resource_type="ec2:instance",
                name=f"instance-{i}",
                region="us-east-1",
                config_hash=str(i) * 64,
                raw_config={},
            )
            for i in range(5)
        ]

        snapshot = Snapshot(
            name="ec2-snapshot",
            created_at=created_at,
            account_id="123456789012",
            regions=["us-east-1"],
            resources=resources,
        )

        # __post_init__ should calculate these automatically
        assert snapshot.resource_count == 5
        assert snapshot.service_counts == {"ec2": 5}

    def test_snapshot_service_counts_multiple_services(self):
        """Test service count calculation with multiple service types."""
        created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        resources = [
            Resource(
                arn="arn:aws:s3:::bucket1",
                resource_type="s3:bucket",
                name="bucket1",
                region="us-east-1",
                config_hash="a" * 64,
                raw_config={},
            ),
            Resource(
                arn="arn:aws:s3:::bucket2",
                resource_type="s3:bucket",
                name="bucket2",
                region="us-east-1",
                config_hash="b" * 64,
                raw_config={},
            ),
            Resource(
                arn="arn:aws:lambda:us-east-1:123456789012:function:func1",
                resource_type="lambda:function",
                name="func1",
                region="us-east-1",
                config_hash="c" * 64,
                raw_config={},
            ),
            Resource(
                arn="arn:aws:lambda:us-east-1:123456789012:function:func2",
                resource_type="lambda:function",
                name="func2",
                region="us-east-1",
                config_hash="d" * 64,
                raw_config={},
            ),
            Resource(
                arn="arn:aws:iam::123456789012:role/role1",
                resource_type="iam:role",
                name="role1",
                region="global",
                config_hash="e" * 64,
                raw_config={},
            ),
        ]

        snapshot = Snapshot(
            name="multi-service-snapshot",
            created_at=created_at,
            account_id="123456789012",
            regions=["us-east-1", "global"],
            resources=resources,
        )

        assert snapshot.resource_count == 5
        assert snapshot.service_counts == {"s3": 2, "lambda": 2, "iam": 1}

    def test_snapshot_to_dict(self):
        """Test serializing snapshot to dictionary."""
        created_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        resources = [
            Resource(
                arn="arn:aws:s3:::test-bucket",
                resource_type="s3:bucket",
                name="test-bucket",
                region="us-east-1",
                config_hash="f" * 64,
                raw_config={"BucketName": "test-bucket"},
            )
        ]

        snapshot = Snapshot(
            name="test-snapshot",
            created_at=created_at,
            account_id="123456789012",
            regions=["us-east-1"],
            resources=resources,
            is_active=False,
            metadata={"author": "admin", "purpose": "testing"},
            filters_applied={"include_tags": {"Environment": "test"}},
            total_resources_before_filter=10,
            inventory_name="test-inventory",
        )

        data = snapshot.to_dict()

        assert data["name"] == "test-snapshot"
        assert data["created_at"] == "2024-01-15T10:30:00+00:00"
        assert data["account_id"] == "123456789012"
        assert data["regions"] == ["us-east-1"]
        assert data["is_active"] is False
        assert data["resource_count"] == 1
        assert data["service_counts"] == {"s3": 1}
        assert data["metadata"] == {"author": "admin", "purpose": "testing"}
        assert data["filters_applied"] == {"include_tags": {"Environment": "test"}}
        assert data["total_resources_before_filter"] == 10
        assert data["inventory_name"] == "test-inventory"
        assert len(data["resources"]) == 1
        assert data["resources"][0]["name"] == "test-bucket"

    def test_snapshot_from_dict(self):
        """Test deserializing snapshot from dictionary."""
        data = {
            "name": "restored-snapshot",
            "created_at": "2024-02-01T08:00:00+00:00",
            "account_id": "123456789012",
            "regions": ["us-west-1", "us-west-2"],
            "is_active": True,
            "resource_count": 2,
            "service_counts": {"lambda": 2},
            "metadata": {"version": "1.0"},
            "filters_applied": None,
            "total_resources_before_filter": None,
            "inventory_name": "production",
            "resources": [
                {
                    "arn": "arn:aws:lambda:us-west-1:123456789012:function:func1",
                    "type": "lambda:function",
                    "name": "func1",
                    "region": "us-west-1",
                    "config_hash": "g" * 64,
                    "raw_config": {},
                    "tags": {},
                    "created_at": None,
                },
                {
                    "arn": "arn:aws:lambda:us-west-2:123456789012:function:func2",
                    "type": "lambda:function",
                    "name": "func2",
                    "region": "us-west-2",
                    "config_hash": "h" * 64,
                    "raw_config": {},
                    "tags": {},
                    "created_at": None,
                },
            ],
        }

        snapshot = Snapshot.from_dict(data)

        assert snapshot.name == "restored-snapshot"
        assert snapshot.created_at == datetime(2024, 2, 1, 8, 0, 0, tzinfo=timezone.utc)
        assert snapshot.account_id == "123456789012"
        assert snapshot.regions == ["us-west-1", "us-west-2"]
        assert snapshot.is_active is True
        assert snapshot.resource_count == 2
        assert snapshot.service_counts == {"lambda": 2}
        assert snapshot.metadata == {"version": "1.0"}
        assert snapshot.filters_applied is None
        assert snapshot.total_resources_before_filter is None
        assert snapshot.inventory_name == "production"
        assert len(snapshot.resources) == 2

    def test_snapshot_from_dict_backward_compatibility(self):
        """Test deserializing snapshot without inventory_name (backward compatibility)."""
        data = {
            "name": "legacy-snapshot",
            "created_at": "2024-01-01T00:00:00+00:00",
            "account_id": "123456789012",
            "regions": ["us-east-1"],
            "resources": [],
        }

        snapshot = Snapshot.from_dict(data)
        assert snapshot.inventory_name == "default"  # Should default to "default"

    def test_snapshot_roundtrip_serialization(self):
        """Test that to_dict -> from_dict preserves all data."""
        created_at = datetime(2024, 3, 1, 0, 0, 0, tzinfo=timezone.utc)
        resources = [
            Resource(
                arn="arn:aws:rds:eu-west-1:123456789012:db:mydb",
                resource_type="rds:instance",
                name="mydb",
                region="eu-west-1",
                config_hash="i" * 64,
                raw_config={"DBInstanceIdentifier": "mydb"},
                tags={"Environment": "production"},
                created_at=datetime(2024, 2, 15, 0, 0, 0, tzinfo=timezone.utc),
            )
        ]

        original = Snapshot(
            name="production-baseline",
            created_at=created_at,
            account_id="123456789012",
            regions=["eu-west-1"],
            resources=resources,
            is_active=True,
            metadata={"compliance": "sox", "team": "platform"},
            filters_applied={"include_tags": {"Environment": "production"}},
            total_resources_before_filter=50,
            inventory_name="prod-inventory",
        )

        # Serialize and deserialize
        data = original.to_dict()
        restored = Snapshot.from_dict(data)

        # Verify all fields match
        assert restored.name == original.name
        assert restored.created_at == original.created_at
        assert restored.account_id == original.account_id
        assert restored.regions == original.regions
        assert restored.is_active == original.is_active
        assert restored.resource_count == original.resource_count
        assert restored.service_counts == original.service_counts
        assert restored.metadata == original.metadata
        assert restored.filters_applied == original.filters_applied
        assert restored.total_resources_before_filter == original.total_resources_before_filter
        assert restored.inventory_name == original.inventory_name
        assert len(restored.resources) == len(original.resources)

    def test_validate_valid_snapshot(self):
        """Test validation with valid snapshot."""
        snapshot = Snapshot(
            name="valid-snapshot",
            created_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
        )
        assert snapshot.validate() is True

    def test_validate_invalid_name_format(self):
        """Test validation with invalid snapshot name format."""
        snapshot = Snapshot(
            name="invalid name!",  # Spaces and special chars
            created_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
        )
        with pytest.raises(ValueError, match="Invalid snapshot name"):
            snapshot.validate()

    def test_validate_invalid_account_id(self):
        """Test validation with invalid account ID."""
        snapshot = Snapshot(
            name="test-snapshot",
            created_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            account_id="invalid",  # Not 12 digits
            regions=["us-east-1"],
            resources=[],
        )
        with pytest.raises(ValueError, match="Invalid AWS account ID"):
            snapshot.validate()

    def test_validate_empty_regions(self):
        """Test validation with empty regions list."""
        snapshot = Snapshot(
            name="test-snapshot",
            created_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=[],  # Empty regions
            resources=[],
        )
        with pytest.raises(ValueError, match="must include at least one AWS region"):
            snapshot.validate()

    def test_snapshot_with_various_valid_names(self):
        """Test snapshot name validation with various valid formats."""
        valid_names = [
            "baseline-2024",
            "prod_snapshot",
            "test-123",
            "BASELINE",
            "snapshot_2024-01-15",
            "my-snapshot-v1_0",
        ]

        for name in valid_names:
            snapshot = Snapshot(
                name=name,
                created_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                account_id="123456789012",
                regions=["us-east-1"],
                resources=[],
            )
            assert snapshot.validate() is True

    def test_snapshot_with_filters_metadata(self):
        """Test snapshot with filter metadata."""
        snapshot = Snapshot(
            name="filtered-snapshot",
            created_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
            filters_applied={
                "include_tags": {"Team": "Alpha", "Environment": "production"},
                "exclude_tags": {"Status": "archived"},
                "before_date": "2024-01-01",
            },
            total_resources_before_filter=100,
        )

        assert snapshot.filters_applied is not None
        assert snapshot.filters_applied["include_tags"]["Team"] == "Alpha"
        assert snapshot.total_resources_before_filter == 100

    def test_snapshot_inactive_flag(self):
        """Test snapshot with is_active flag set to False."""
        snapshot = Snapshot(
            name="archived-snapshot",
            created_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
            is_active=False,
        )

        assert snapshot.is_active is False

    def test_snapshot_multiple_regions(self):
        """Test snapshot with multiple regions."""
        regions = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1"]
        snapshot = Snapshot(
            name="multi-region-snapshot",
            created_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=regions,
            resources=[],
        )

        assert snapshot.regions == regions
        assert len(snapshot.regions) == 4

    def test_snapshot_with_custom_metadata(self):
        """Test snapshot with custom metadata."""
        metadata = {
            "created_by": "admin@example.com",
            "purpose": "quarterly-audit",
            "compliance_framework": "SOX",
            "retention_days": 90,
            "tags": ["production", "audit", "q1-2024"],
        }

        snapshot = Snapshot(
            name="audit-snapshot",
            created_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
            metadata=metadata,
        )

        assert snapshot.metadata == metadata
        assert snapshot.metadata["purpose"] == "quarterly-audit"

    def test_empty_snapshot_counts(self):
        """Test snapshot with no resources has zero counts."""
        snapshot = Snapshot(
            name="empty-snapshot",
            created_at=datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
        )

        assert snapshot.resource_count == 0
        assert snapshot.service_counts == {}
