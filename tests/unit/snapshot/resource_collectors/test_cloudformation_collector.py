"""Tests for CloudFormation resource collector."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.cloudformation import CloudFormationCollector


@pytest.fixture
def mock_session():
    """Create a mock boto3 session."""
    session = MagicMock()
    session.profile_name = "default"
    return session


class TestCloudFormationCollectorProperties:
    """Tests for CloudFormationCollector properties."""

    def test_service_name(self, mock_session):
        """Test service_name property returns cloudformation."""
        collector = CloudFormationCollector(session=mock_session, region="us-east-1")
        assert collector.service_name == "cloudformation"


class TestCloudFormationCollectorCollect:
    """Tests for CloudFormationCollector.collect method."""

    @patch.object(CloudFormationCollector, "_create_client")
    def test_collect_no_stacks(self, mock_create_client, mock_session):
        """Test collecting when no stacks exist."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"Stacks": []}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = CloudFormationCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert resources == []
        mock_client.get_paginator.assert_called_once_with("describe_stacks")

    @patch.object(CloudFormationCollector, "_create_client")
    def test_collect_single_stack(self, mock_create_client, mock_session):
        """Test collecting a single stack."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_paginator.paginate.return_value = [
            {
                "Stacks": [
                    {
                        "StackName": "test-stack",
                        "StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/12345678",
                        "CreationTime": created_at,
                        "Tags": [{"Key": "Environment", "Value": "test"}],
                    }
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = CloudFormationCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "test-stack"
        assert resources[0].resource_type == "AWS::CloudFormation::Stack"
        assert resources[0].region == "us-east-1"
        assert resources[0].tags == {"Environment": "test"}
        assert resources[0].created_at == created_at
        assert resources[0].arn == "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/12345678"

    @patch.object(CloudFormationCollector, "_create_client")
    def test_collect_multiple_stacks(self, mock_create_client, mock_session):
        """Test collecting multiple stacks."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Stacks": [
                    {
                        "StackName": "stack-1",
                        "StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/stack-1/111",
                        "Tags": [],
                    },
                    {
                        "StackName": "stack-2",
                        "StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/stack-2/222",
                        "Tags": [],
                    },
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = CloudFormationCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 2
        assert resources[0].name == "stack-1"
        assert resources[1].name == "stack-2"

    @patch.object(CloudFormationCollector, "_create_client")
    def test_collect_handles_error(self, mock_create_client, mock_session):
        """Test collecting handles list stacks error."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.side_effect = Exception("Service unavailable")
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = CloudFormationCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should return empty list on error
        assert resources == []

    @patch.object(CloudFormationCollector, "_create_client")
    def test_collect_with_pagination(self, mock_create_client, mock_session):
        """Test collecting with multiple pages."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"Stacks": [{"StackName": "stack-1", "StackId": "arn:1", "Tags": []}]},
            {"Stacks": [{"StackName": "stack-2", "StackId": "arn:2", "Tags": []}]},
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = CloudFormationCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 2

    @patch.object(CloudFormationCollector, "_create_client")
    def test_collect_stack_without_creation_time(self, mock_create_client, mock_session):
        """Test collecting stack without creation time."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Stacks": [
                    {
                        "StackName": "test-stack",
                        "StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/12345678",
                        "Tags": [],
                    }
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = CloudFormationCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].created_at is None

    @patch.object(CloudFormationCollector, "_create_client")
    def test_collect_stack_with_multiple_tags(self, mock_create_client, mock_session):
        """Test collecting stack with multiple tags."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Stacks": [
                    {
                        "StackName": "test-stack",
                        "StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/12345678",
                        "Tags": [
                            {"Key": "Environment", "Value": "prod"},
                            {"Key": "Team", "Value": "platform"},
                            {"Key": "CostCenter", "Value": "12345"},
                        ],
                    }
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = CloudFormationCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].tags == {
            "Environment": "prod",
            "Team": "platform",
            "CostCenter": "12345",
        }

    @patch.object(CloudFormationCollector, "_create_client")
    def test_collect_stores_raw_config(self, mock_create_client, mock_session):
        """Test that raw config (stack data) is stored."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        stack_data = {
            "StackName": "test-stack",
            "StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/12345678",
            "StackStatus": "CREATE_COMPLETE",
            "Tags": [],
        }
        mock_paginator.paginate.return_value = [{"Stacks": [stack_data]}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = CloudFormationCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].raw_config == stack_data

    @patch.object(CloudFormationCollector, "_create_client")
    def test_collect_generates_config_hash(self, mock_create_client, mock_session):
        """Test that config hash is generated from stack config."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Stacks": [
                    {
                        "StackName": "test-stack",
                        "StackId": "arn:aws:cloudformation:us-east-1:123456789012:stack/test-stack/12345678",
                        "Tags": [],
                    }
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = CloudFormationCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].config_hash is not None
        assert len(resources[0].config_hash) > 0
