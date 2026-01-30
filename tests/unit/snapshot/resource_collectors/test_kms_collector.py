"""Tests for KMS resource collector."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.kms import KMSCollector


@pytest.fixture
def mock_session():
    """Create a mock boto3 session."""
    session = MagicMock()
    session.profile_name = "default"
    return session


class TestKMSCollectorProperties:
    """Tests for KMSCollector properties."""

    def test_service_name(self, mock_session):
        """Test service_name property returns kms."""
        collector = KMSCollector(session=mock_session, region="us-east-1")
        assert collector.service_name == "kms"


class TestKMSCollectorCollect:
    """Tests for KMSCollector.collect method."""

    @patch.object(KMSCollector, "_create_client")
    def test_collect_no_keys(self, mock_create_client, mock_session):
        """Test collecting when no keys exist."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"Keys": []}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = KMSCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert resources == []
        mock_client.get_paginator.assert_called_once_with("list_keys")

    @patch.object(KMSCollector, "_create_client")
    def test_collect_single_customer_key(self, mock_create_client, mock_session):
        """Test collecting a single customer-managed key."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_paginator.paginate.return_value = [
            {
                "Keys": [
                    {
                        "KeyId": "key-12345",
                        "KeyArn": "arn:aws:kms:us-east-1:123456789012:key/key-12345",
                    }
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.describe_key.return_value = {
            "KeyMetadata": {
                "KeyId": "key-12345",
                "KeyManager": "CUSTOMER",
                "KeyState": "Enabled",
                "CreationDate": created_at,
            }
        }
        mock_client.list_aliases.return_value = {"Aliases": [{"AliasName": "alias/my-key"}]}
        mock_client.list_resource_tags.return_value = {"Tags": [{"TagKey": "Environment", "TagValue": "test"}]}
        mock_client.get_key_rotation_status.return_value = {"KeyRotationEnabled": True}
        mock_create_client.return_value = mock_client

        collector = KMSCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "alias/my-key"
        assert resources[0].resource_type == "AWS::KMS::Key"
        assert resources[0].region == "us-east-1"
        assert resources[0].tags == {"Environment": "test"}
        assert resources[0].created_at == created_at

    @patch.object(KMSCollector, "_create_client")
    def test_collect_skips_aws_managed_keys(self, mock_create_client, mock_session):
        """Test that AWS-managed keys are skipped."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Keys": [
                    {
                        "KeyId": "aws-managed-key",
                        "KeyArn": "arn:aws:kms:us-east-1:123456789012:key/aws-managed-key",
                    }
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.describe_key.return_value = {
            "KeyMetadata": {
                "KeyId": "aws-managed-key",
                "KeyManager": "AWS",  # AWS-managed key
                "KeyState": "Enabled",
            }
        }
        mock_create_client.return_value = mock_client

        collector = KMSCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should skip AWS-managed keys
        assert resources == []

    @patch.object(KMSCollector, "_create_client")
    def test_collect_skips_pending_deletion_keys(self, mock_create_client, mock_session):
        """Test that keys pending deletion are skipped."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Keys": [
                    {
                        "KeyId": "key-pending",
                        "KeyArn": "arn:aws:kms:us-east-1:123456789012:key/key-pending",
                    }
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.describe_key.return_value = {
            "KeyMetadata": {
                "KeyId": "key-pending",
                "KeyManager": "CUSTOMER",
                "KeyState": "PendingDeletion",  # Pending deletion
            }
        }
        mock_create_client.return_value = mock_client

        collector = KMSCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should skip pending deletion keys
        assert resources == []

    @patch.object(KMSCollector, "_create_client")
    def test_collect_key_without_alias(self, mock_create_client, mock_session):
        """Test collecting key without alias uses key ID as name."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Keys": [
                    {
                        "KeyId": "key-no-alias",
                        "KeyArn": "arn:aws:kms:us-east-1:123456789012:key/key-no-alias",
                    }
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.describe_key.return_value = {
            "KeyMetadata": {
                "KeyId": "key-no-alias",
                "KeyManager": "CUSTOMER",
                "KeyState": "Enabled",
            }
        }
        mock_client.list_aliases.return_value = {"Aliases": []}  # No aliases
        mock_client.list_resource_tags.return_value = {"Tags": []}
        mock_client.get_key_rotation_status.return_value = {"KeyRotationEnabled": False}
        mock_create_client.return_value = mock_client

        collector = KMSCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "key-no-alias"  # Uses key ID as name

    @patch.object(KMSCollector, "_create_client")
    def test_collect_handles_describe_key_error(self, mock_create_client, mock_session):
        """Test collecting continues when describe_key fails."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Keys": [
                    {"KeyId": "good-key", "KeyArn": "arn:1"},
                    {"KeyId": "bad-key", "KeyArn": "arn:2"},
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator

        def describe_key_side_effect(**kwargs):
            if kwargs["KeyId"] == "bad-key":
                raise Exception("Access denied")
            return {
                "KeyMetadata": {
                    "KeyId": "good-key",
                    "KeyManager": "CUSTOMER",
                    "KeyState": "Enabled",
                }
            }

        mock_client.describe_key.side_effect = describe_key_side_effect
        mock_client.list_aliases.return_value = {"Aliases": []}
        mock_client.list_resource_tags.return_value = {"Tags": []}
        mock_client.get_key_rotation_status.return_value = {"KeyRotationEnabled": False}
        mock_create_client.return_value = mock_client

        collector = KMSCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should only get the good key
        assert len(resources) == 1
        assert resources[0].name == "good-key"

    @patch.object(KMSCollector, "_create_client")
    def test_collect_handles_aliases_error(self, mock_create_client, mock_session):
        """Test collecting continues when list_aliases fails."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Keys": [
                    {
                        "KeyId": "key-123",
                        "KeyArn": "arn:aws:kms:us-east-1:123456789012:key/key-123",
                    }
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.describe_key.return_value = {
            "KeyMetadata": {
                "KeyId": "key-123",
                "KeyManager": "CUSTOMER",
                "KeyState": "Enabled",
            }
        }
        mock_client.list_aliases.side_effect = Exception("Access denied")
        mock_client.list_resource_tags.return_value = {"Tags": []}
        mock_client.get_key_rotation_status.return_value = {"KeyRotationEnabled": False}
        mock_create_client.return_value = mock_client

        collector = KMSCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still get the key using key ID as name
        assert len(resources) == 1
        assert resources[0].name == "key-123"

    @patch.object(KMSCollector, "_create_client")
    def test_collect_handles_tags_error(self, mock_create_client, mock_session):
        """Test collecting continues when list_resource_tags fails."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Keys": [
                    {
                        "KeyId": "key-123",
                        "KeyArn": "arn:aws:kms:us-east-1:123456789012:key/key-123",
                    }
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.describe_key.return_value = {
            "KeyMetadata": {
                "KeyId": "key-123",
                "KeyManager": "CUSTOMER",
                "KeyState": "Enabled",
            }
        }
        mock_client.list_aliases.return_value = {"Aliases": []}
        mock_client.list_resource_tags.side_effect = Exception("Access denied")
        mock_client.get_key_rotation_status.return_value = {"KeyRotationEnabled": False}
        mock_create_client.return_value = mock_client

        collector = KMSCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still get the key without tags
        assert len(resources) == 1
        assert resources[0].tags == {}

    @patch.object(KMSCollector, "_create_client")
    def test_collect_handles_rotation_status_error(self, mock_create_client, mock_session):
        """Test collecting continues when get_key_rotation_status fails."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Keys": [
                    {
                        "KeyId": "key-123",
                        "KeyArn": "arn:aws:kms:us-east-1:123456789012:key/key-123",
                    }
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.describe_key.return_value = {
            "KeyMetadata": {
                "KeyId": "key-123",
                "KeyManager": "CUSTOMER",
                "KeyState": "Enabled",
            }
        }
        mock_client.list_aliases.return_value = {"Aliases": []}
        mock_client.list_resource_tags.return_value = {"Tags": []}
        mock_client.get_key_rotation_status.side_effect = Exception("Access denied")
        mock_create_client.return_value = mock_client

        collector = KMSCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still get the key with rotation disabled as default
        assert len(resources) == 1
        assert resources[0].raw_config.get("RotationEnabled") is False

    @patch.object(KMSCollector, "_create_client")
    def test_collect_handles_list_keys_error(self, mock_create_client, mock_session):
        """Test collecting handles list_keys error."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.side_effect = Exception("Service unavailable")
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = KMSCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should return empty list on error
        assert resources == []

    @patch.object(KMSCollector, "_create_client")
    def test_collect_generates_config_hash(self, mock_create_client, mock_session):
        """Test that config hash is generated."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Keys": [
                    {
                        "KeyId": "key-123",
                        "KeyArn": "arn:aws:kms:us-east-1:123456789012:key/key-123",
                    }
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.describe_key.return_value = {
            "KeyMetadata": {
                "KeyId": "key-123",
                "KeyManager": "CUSTOMER",
                "KeyState": "Enabled",
            }
        }
        mock_client.list_aliases.return_value = {"Aliases": []}
        mock_client.list_resource_tags.return_value = {"Tags": []}
        mock_client.get_key_rotation_status.return_value = {"KeyRotationEnabled": False}
        mock_create_client.return_value = mock_client

        collector = KMSCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].config_hash is not None
        assert len(resources[0].config_hash) > 0

    @patch.object(KMSCollector, "_create_client")
    def test_collect_with_pagination(self, mock_create_client, mock_session):
        """Test collecting with multiple pages."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"Keys": [{"KeyId": "key-1", "KeyArn": "arn:1"}]},
            {"Keys": [{"KeyId": "key-2", "KeyArn": "arn:2"}]},
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.describe_key.return_value = {
            "KeyMetadata": {
                "KeyManager": "CUSTOMER",
                "KeyState": "Enabled",
            }
        }
        mock_client.list_aliases.return_value = {"Aliases": []}
        mock_client.list_resource_tags.return_value = {"Tags": []}
        mock_client.get_key_rotation_status.return_value = {"KeyRotationEnabled": False}
        mock_create_client.return_value = mock_client

        collector = KMSCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 2
