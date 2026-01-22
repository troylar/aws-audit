"""Unit tests for ResourceStore creator-related methods."""

import pytest
from unittest.mock import MagicMock, patch


class TestResourceStoreCreators:
    """Tests for get_creators_summary and related methods."""

    def test_get_creators_summary_returns_aggregated_data(self):
        """Test that get_creators_summary aggregates resources by creator."""
        from src.storage.resource_store import ResourceStore

        # Mock database
        mock_db = MagicMock()
        mock_db.fetchall.return_value = [
            {
                "arn": "arn:aws:s3:::bucket1",
                "resource_type": "AWS::S3::Bucket",
                "name": "bucket1",
                "region": "us-east-1",
                "created_by": "arn:aws:iam::123456789012:role/MyRole",
                "created_by_type": "AssumedRole",
                "created_at": "2025-01-15T10:00:00Z",
            },
            {
                "arn": "arn:aws:s3:::bucket2",
                "resource_type": "AWS::S3::Bucket",
                "name": "bucket2",
                "region": "us-east-1",
                "created_by": "arn:aws:iam::123456789012:role/MyRole",
                "created_by_type": "AssumedRole",
                "created_at": "2025-01-15T11:00:00Z",
            },
            {
                "arn": "arn:aws:lambda:us-east-1:123456789012:function:func1",
                "resource_type": "AWS::Lambda::Function",
                "name": "func1",
                "region": "us-east-1",
                "created_by": "arn:aws:iam::123456789012:user/admin",
                "created_by_type": "IAMUser",
                "created_at": "2025-01-15T12:00:00Z",
            },
        ]

        store = ResourceStore(mock_db)
        result = store.get_creators_summary("test-snapshot")

        # Should have 2 creators
        assert len(result) == 2

        # First creator (most resources) should be MyRole
        role_creator = next(c for c in result if "MyRole" in c["creator"])
        assert role_creator["resource_count"] == 2
        assert role_creator["creator_type"] == "AssumedRole"
        assert role_creator["resource_types"]["AWS::S3::Bucket"] == 2
        assert len(role_creator["resources"]) == 2

        # Second creator should be admin user
        user_creator = next(c for c in result if "admin" in c["creator"])
        assert user_creator["resource_count"] == 1
        assert user_creator["creator_type"] == "IAMUser"
        assert user_creator["resource_types"]["AWS::Lambda::Function"] == 1

    def test_get_creators_summary_empty_snapshot(self):
        """Test get_creators_summary with no creator data."""
        from src.storage.resource_store import ResourceStore

        mock_db = MagicMock()
        mock_db.fetchall.return_value = []

        store = ResourceStore(mock_db)
        result = store.get_creators_summary("empty-snapshot")

        assert result == []

    def test_get_creators_summary_sorts_by_resource_count(self):
        """Test that results are sorted by resource count descending."""
        from src.storage.resource_store import ResourceStore

        mock_db = MagicMock()
        mock_db.fetchall.return_value = [
            {
                "arn": "arn:aws:s3:::bucket1",
                "resource_type": "AWS::S3::Bucket",
                "name": "bucket1",
                "region": "us-east-1",
                "created_by": "arn:aws:iam::123:role/RoleA",
                "created_by_type": "AssumedRole",
                "created_at": None,
            },
            {
                "arn": "arn:aws:s3:::bucket2",
                "resource_type": "AWS::S3::Bucket",
                "name": "bucket2",
                "region": "us-east-1",
                "created_by": "arn:aws:iam::123:role/RoleB",
                "created_by_type": "AssumedRole",
                "created_at": None,
            },
            {
                "arn": "arn:aws:s3:::bucket3",
                "resource_type": "AWS::S3::Bucket",
                "name": "bucket3",
                "region": "us-east-1",
                "created_by": "arn:aws:iam::123:role/RoleB",
                "created_by_type": "AssumedRole",
                "created_at": None,
            },
            {
                "arn": "arn:aws:s3:::bucket4",
                "resource_type": "AWS::S3::Bucket",
                "name": "bucket4",
                "region": "us-east-1",
                "created_by": "arn:aws:iam::123:role/RoleB",
                "created_by_type": "AssumedRole",
                "created_at": None,
            },
        ]

        store = ResourceStore(mock_db)
        result = store.get_creators_summary("test-snapshot")

        # RoleB should be first (3 resources), RoleA second (1 resource)
        assert "RoleB" in result[0]["creator"]
        assert result[0]["resource_count"] == 3
        assert "RoleA" in result[1]["creator"]
        assert result[1]["resource_count"] == 1

    def test_get_creators_count(self):
        """Test get_creators_count returns correct count."""
        from src.storage.resource_store import ResourceStore

        mock_db = MagicMock()
        mock_db.fetchone.return_value = {"count": 5}

        store = ResourceStore(mock_db)
        result = store.get_creators_count("test-snapshot")

        assert result == 5

    def test_get_creators_count_empty(self):
        """Test get_creators_count with no creators."""
        from src.storage.resource_store import ResourceStore

        mock_db = MagicMock()
        mock_db.fetchone.return_value = {"count": 0}

        store = ResourceStore(mock_db)
        result = store.get_creators_count("test-snapshot")

        assert result == 0

    def test_get_creators_count_none_result(self):
        """Test get_creators_count handles None result."""
        from src.storage.resource_store import ResourceStore

        mock_db = MagicMock()
        mock_db.fetchone.return_value = None

        store = ResourceStore(mock_db)
        result = store.get_creators_count("test-snapshot")

        assert result == 0

    def test_get_resources_without_creator(self):
        """Test get_resources_without_creator returns correct count."""
        from src.storage.resource_store import ResourceStore

        mock_db = MagicMock()
        mock_db.fetchone.return_value = {"count": 10}

        store = ResourceStore(mock_db)
        result = store.get_resources_without_creator("test-snapshot")

        assert result == 10

    def test_get_resources_without_creator_none_result(self):
        """Test get_resources_without_creator handles None result."""
        from src.storage.resource_store import ResourceStore

        mock_db = MagicMock()
        mock_db.fetchone.return_value = None

        store = ResourceStore(mock_db)
        result = store.get_resources_without_creator("test-snapshot")

        assert result == 0

    def test_get_creators_summary_handles_missing_type(self):
        """Test that missing creator_type defaults to Unknown."""
        from src.storage.resource_store import ResourceStore

        mock_db = MagicMock()
        mock_db.fetchall.return_value = [
            {
                "arn": "arn:aws:s3:::bucket1",
                "resource_type": "AWS::S3::Bucket",
                "name": "bucket1",
                "region": "us-east-1",
                "created_by": "arn:aws:iam::123:role/MyRole",
                "created_by_type": None,  # Missing type
                "created_at": None,
            },
        ]

        store = ResourceStore(mock_db)
        result = store.get_creators_summary("test-snapshot")

        assert len(result) == 1
        assert result[0]["creator_type"] == "Unknown"
