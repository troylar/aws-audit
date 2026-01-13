"""Tests for Secrets Manager resource collector."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.secretsmanager import SecretsManagerCollector


@pytest.fixture
def mock_session():
    """Create a mock boto3 session."""
    session = MagicMock()
    session.profile_name = "default"
    return session


class TestSecretsManagerCollectorProperties:
    """Tests for SecretsManagerCollector properties."""

    def test_service_name(self, mock_session):
        """Test service_name property returns secretsmanager."""
        collector = SecretsManagerCollector(session=mock_session, region="us-east-1")
        assert collector.service_name == "secretsmanager"


class TestSecretsManagerCollectorCollect:
    """Tests for SecretsManagerCollector.collect method."""

    @patch.object(SecretsManagerCollector, "_create_client")
    def test_collect_no_secrets(self, mock_create_client, mock_session):
        """Test collecting when no secrets exist."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"SecretList": []}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = SecretsManagerCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert resources == []
        mock_client.get_paginator.assert_called_once_with("list_secrets")

    @patch.object(SecretsManagerCollector, "_create_client")
    def test_collect_single_secret(self, mock_create_client, mock_session):
        """Test collecting a single secret."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_paginator.paginate.return_value = [{
            "SecretList": [{
                "Name": "my-secret",
                "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:my-secret-abc123",
                "CreatedDate": created_at,
                "Tags": [{"Key": "Environment", "Value": "test"}],
            }]
        }]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.describe_secret.return_value = {
            "Name": "my-secret",
            "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:my-secret-abc123",
            "Description": "Test secret",
        }
        mock_create_client.return_value = mock_client

        collector = SecretsManagerCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "my-secret"
        assert resources[0].resource_type == "AWS::SecretsManager::Secret"
        assert resources[0].region == "us-east-1"
        assert resources[0].tags == {"Environment": "test"}
        assert resources[0].created_at == created_at
        assert resources[0].arn == "arn:aws:secretsmanager:us-east-1:123456789012:secret:my-secret-abc123"

    @patch.object(SecretsManagerCollector, "_create_client")
    def test_collect_multiple_secrets(self, mock_create_client, mock_session):
        """Test collecting multiple secrets."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{
            "SecretList": [
                {
                    "Name": "secret-1",
                    "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:secret-1-abc",
                    "Tags": [],
                },
                {
                    "Name": "secret-2",
                    "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:secret-2-def",
                    "Tags": [],
                },
            ]
        }]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.describe_secret.return_value = {}
        mock_create_client.return_value = mock_client

        collector = SecretsManagerCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 2
        assert resources[0].name == "secret-1"
        assert resources[1].name == "secret-2"

    @patch.object(SecretsManagerCollector, "_create_client")
    def test_collect_handles_describe_error(self, mock_create_client, mock_session):
        """Test collecting continues when describe_secret fails."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{
            "SecretList": [{
                "Name": "my-secret",
                "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:my-secret-abc",
                "Tags": [],
            }]
        }]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.describe_secret.side_effect = Exception("Access denied")
        mock_create_client.return_value = mock_client

        collector = SecretsManagerCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still get the secret using list_secrets data
        assert len(resources) == 1
        assert resources[0].name == "my-secret"

    @patch.object(SecretsManagerCollector, "_create_client")
    def test_collect_handles_list_secrets_error(self, mock_create_client, mock_session):
        """Test collecting handles list_secrets error."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.side_effect = Exception("Service unavailable")
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = SecretsManagerCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should return empty list on error
        assert resources == []

    @patch.object(SecretsManagerCollector, "_create_client")
    def test_collect_with_pagination(self, mock_create_client, mock_session):
        """Test collecting with multiple pages."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"SecretList": [{"Name": "secret-1", "ARN": "arn:1", "Tags": []}]},
            {"SecretList": [{"Name": "secret-2", "ARN": "arn:2", "Tags": []}]},
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.describe_secret.return_value = {}
        mock_create_client.return_value = mock_client

        collector = SecretsManagerCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 2

    @patch.object(SecretsManagerCollector, "_create_client")
    def test_collect_filters_sensitive_fields(self, mock_create_client, mock_session):
        """Test that sensitive fields are filtered from config."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{
            "SecretList": [{
                "Name": "my-secret",
                "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:my-secret-abc",
                "Tags": [],
            }]
        }]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.describe_secret.return_value = {
            "Name": "my-secret",
            "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:my-secret-abc",
            "SecretString": "super-secret-value",
            "SecretBinary": b"binary-secret",
        }
        mock_create_client.return_value = mock_client

        collector = SecretsManagerCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        # Ensure sensitive fields are not in raw_config
        assert "SecretString" not in resources[0].raw_config
        assert "SecretBinary" not in resources[0].raw_config

    @patch.object(SecretsManagerCollector, "_create_client")
    def test_collect_generates_config_hash(self, mock_create_client, mock_session):
        """Test that config hash is generated."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{
            "SecretList": [{
                "Name": "my-secret",
                "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:my-secret-abc",
                "Tags": [],
            }]
        }]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.describe_secret.return_value = {}
        mock_create_client.return_value = mock_client

        collector = SecretsManagerCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].config_hash is not None
        assert len(resources[0].config_hash) > 0

    @patch.object(SecretsManagerCollector, "_create_client")
    def test_collect_with_multiple_tags(self, mock_create_client, mock_session):
        """Test collecting secret with multiple tags."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{
            "SecretList": [{
                "Name": "my-secret",
                "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:my-secret-abc",
                "Tags": [
                    {"Key": "Environment", "Value": "prod"},
                    {"Key": "Team", "Value": "platform"},
                    {"Key": "App", "Value": "api"},
                ],
            }]
        }]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.describe_secret.return_value = {}
        mock_create_client.return_value = mock_client

        collector = SecretsManagerCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].tags == {
            "Environment": "prod",
            "Team": "platform",
            "App": "api",
        }
