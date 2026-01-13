"""Unit tests for S3 resource collector."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.s3 import S3Collector


class TestS3Collector:
    """Tests for S3Collector."""

    @pytest.fixture
    def collector(self):
        """Create an S3Collector instance for testing."""
        mock_session = MagicMock()
        mock_session.profile_name = "default"
        return S3Collector(session=mock_session, region="us-east-1")

    def test_service_name(self, collector):
        """Test service name property."""
        assert collector.service_name == "s3"

    def test_is_global_service(self, collector):
        """Test that S3 is a global service."""
        assert collector.is_global_service is True

    def test_collect_buckets_basic(self, collector):
        """Test collecting S3 buckets with basic info."""
        mock_client = MagicMock()
        mock_client.list_buckets.return_value = {
            "Buckets": [
                {
                    "Name": "test-bucket",
                    "CreationDate": datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
                }
            ]
        }
        mock_client.get_bucket_location.return_value = {"LocationConstraint": "us-west-2"}
        mock_client.get_bucket_tagging.side_effect = mock_client.exceptions.NoSuchTagSet({}, "")
        mock_client.get_bucket_versioning.return_value = {"Status": "Enabled"}
        mock_client.get_bucket_encryption.side_effect = Exception("No encryption")

        # Setup the NoSuchTagSet exception class
        mock_client.exceptions = MagicMock()
        mock_client.exceptions.NoSuchTagSet = type("NoSuchTagSet", (Exception,), {})
        mock_client.get_bucket_tagging.side_effect = mock_client.exceptions.NoSuchTagSet()

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector.collect()

        assert len(resources) == 1
        resource = resources[0]
        assert resource.name == "test-bucket"
        assert resource.resource_type == "AWS::S3::Bucket"
        assert resource.arn == "arn:aws:s3:::test-bucket"
        assert resource.region == "us-west-2"
        assert resource.created_at == datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

    def test_collect_buckets_us_east_1_location(self, collector):
        """Test that None LocationConstraint maps to us-east-1."""
        mock_client = MagicMock()
        mock_client.list_buckets.return_value = {
            "Buckets": [{"Name": "east-bucket", "CreationDate": datetime.now(timezone.utc)}]
        }
        # None means us-east-1
        mock_client.get_bucket_location.return_value = {"LocationConstraint": None}
        mock_client.exceptions = MagicMock()
        mock_client.exceptions.NoSuchTagSet = type("NoSuchTagSet", (Exception,), {})
        mock_client.get_bucket_tagging.side_effect = mock_client.exceptions.NoSuchTagSet()
        mock_client.get_bucket_versioning.return_value = {}
        mock_client.get_bucket_encryption.side_effect = Exception("No encryption")

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].region == "us-east-1"

    def test_collect_buckets_with_tags(self, collector):
        """Test collecting S3 buckets with tags."""
        mock_client = MagicMock()
        mock_client.list_buckets.return_value = {
            "Buckets": [{"Name": "tagged-bucket", "CreationDate": datetime.now(timezone.utc)}]
        }
        mock_client.get_bucket_location.return_value = {"LocationConstraint": "eu-west-1"}
        mock_client.get_bucket_tagging.return_value = {
            "TagSet": [
                {"Key": "Environment", "Value": "production"},
                {"Key": "Team", "Value": "data"},
            ]
        }
        mock_client.get_bucket_versioning.return_value = {}
        mock_client.get_bucket_encryption.side_effect = Exception("No encryption")

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].tags == {"Environment": "production", "Team": "data"}

    def test_collect_buckets_with_encryption(self, collector):
        """Test collecting S3 buckets with encryption config."""
        mock_client = MagicMock()
        mock_client.list_buckets.return_value = {
            "Buckets": [{"Name": "encrypted-bucket", "CreationDate": datetime.now(timezone.utc)}]
        }
        mock_client.get_bucket_location.return_value = {"LocationConstraint": "us-east-2"}
        mock_client.exceptions = MagicMock()
        mock_client.exceptions.NoSuchTagSet = type("NoSuchTagSet", (Exception,), {})
        mock_client.get_bucket_tagging.side_effect = mock_client.exceptions.NoSuchTagSet()
        mock_client.get_bucket_versioning.return_value = {"Status": "Enabled"}
        mock_client.get_bucket_encryption.return_value = {
            "ServerSideEncryptionConfiguration": {
                "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
            }
        }

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector.collect()

        assert len(resources) == 1
        # Encryption should be included in raw_config
        assert "Encryption" in resources[0].raw_config

    def test_collect_buckets_location_error(self, collector):
        """Test handling error getting bucket location."""
        mock_client = MagicMock()
        mock_client.list_buckets.return_value = {
            "Buckets": [{"Name": "error-bucket", "CreationDate": datetime.now(timezone.utc)}]
        }
        mock_client.get_bucket_location.side_effect = Exception("Access Denied")
        mock_client.exceptions = MagicMock()
        mock_client.exceptions.NoSuchTagSet = type("NoSuchTagSet", (Exception,), {})
        mock_client.get_bucket_tagging.side_effect = mock_client.exceptions.NoSuchTagSet()
        mock_client.get_bucket_versioning.return_value = {}
        mock_client.get_bucket_encryption.side_effect = Exception("No encryption")

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].region == "unknown"

    def test_collect_buckets_empty(self, collector):
        """Test collecting when no buckets exist."""
        mock_client = MagicMock()
        mock_client.list_buckets.return_value = {"Buckets": []}

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector.collect()

        assert len(resources) == 0

    def test_collect_buckets_api_error(self, collector):
        """Test handling API error during collection."""
        mock_client = MagicMock()
        mock_client.list_buckets.side_effect = Exception("API Error")

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector.collect()

        # Should return empty list on error
        assert resources == []

    def test_collect_multiple_buckets(self, collector):
        """Test collecting multiple S3 buckets."""
        mock_client = MagicMock()
        mock_client.list_buckets.return_value = {
            "Buckets": [
                {"Name": "bucket-1", "CreationDate": datetime(2024, 1, 1, tzinfo=timezone.utc)},
                {"Name": "bucket-2", "CreationDate": datetime(2024, 2, 1, tzinfo=timezone.utc)},
                {"Name": "bucket-3", "CreationDate": datetime(2024, 3, 1, tzinfo=timezone.utc)},
            ]
        }
        mock_client.get_bucket_location.return_value = {"LocationConstraint": "us-west-2"}
        mock_client.exceptions = MagicMock()
        mock_client.exceptions.NoSuchTagSet = type("NoSuchTagSet", (Exception,), {})
        mock_client.get_bucket_tagging.side_effect = mock_client.exceptions.NoSuchTagSet()
        mock_client.get_bucket_versioning.return_value = {}
        mock_client.get_bucket_encryption.side_effect = Exception("No encryption")

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector.collect()

        assert len(resources) == 3
        assert {r.name for r in resources} == {"bucket-1", "bucket-2", "bucket-3"}

    def test_collect_buckets_tagging_generic_error(self, collector):
        """Test handling generic error getting bucket tags (not NoSuchTagSet)."""
        mock_client = MagicMock()
        mock_client.list_buckets.return_value = {
            "Buckets": [{"Name": "tag-error-bucket", "CreationDate": datetime.now(timezone.utc)}]
        }
        mock_client.get_bucket_location.return_value = {"LocationConstraint": "us-west-2"}
        # Set up exception class, but throw a different exception type
        mock_client.exceptions = MagicMock()
        mock_client.exceptions.NoSuchTagSet = type("NoSuchTagSet", (Exception,), {})
        # Throw generic Exception (not NoSuchTagSet)
        mock_client.get_bucket_tagging.side_effect = Exception("Access Denied")
        mock_client.get_bucket_versioning.return_value = {}
        mock_client.get_bucket_encryption.side_effect = Exception("No encryption")

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector.collect()

        # Should still get the bucket without tags
        assert len(resources) == 1
        assert resources[0].tags == {}

    def test_collect_buckets_versioning_error(self, collector):
        """Test handling error getting bucket versioning."""
        mock_client = MagicMock()
        mock_client.list_buckets.return_value = {
            "Buckets": [{"Name": "versioning-error-bucket", "CreationDate": datetime.now(timezone.utc)}]
        }
        mock_client.get_bucket_location.return_value = {"LocationConstraint": "us-west-2"}
        mock_client.exceptions = MagicMock()
        mock_client.exceptions.NoSuchTagSet = type("NoSuchTagSet", (Exception,), {})
        mock_client.get_bucket_tagging.side_effect = mock_client.exceptions.NoSuchTagSet()
        mock_client.get_bucket_versioning.side_effect = Exception("Access Denied")
        mock_client.get_bucket_encryption.side_effect = Exception("No encryption")

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector.collect()

        # Should still get the bucket without versioning info
        assert len(resources) == 1
        assert "Versioning" not in resources[0].raw_config
