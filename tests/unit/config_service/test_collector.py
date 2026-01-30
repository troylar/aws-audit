"""Unit tests for AWS Config collector module."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.config_service.collector import ConfigResourceCollector


class TestConfigResourceCollector:
    """Tests for ConfigResourceCollector class."""

    def test_init(self):
        """Test collector initialization."""
        mock_session = MagicMock()
        collector = ConfigResourceCollector(
            session=mock_session,
            region="us-east-1",
            profile_name="test-profile",
        )

        assert collector.session == mock_session
        assert collector.region == "us-east-1"
        assert collector.profile_name == "test-profile"
        assert collector._client is None
        assert collector._account_id is None

    @patch("src.config_service.collector.create_boto_client")
    def test_client_property(self, mock_create_client):
        """Test client property creates client on first access."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_session = MagicMock()
        mock_session.profile_name = None
        collector = ConfigResourceCollector(mock_session, "us-east-1")

        # First access creates client
        client = collector.client
        assert client == mock_client
        mock_create_client.assert_called_once_with(
            service_name="config",
            region_name="us-east-1",
            profile_name=None,
        )

        # Second access returns same client
        client2 = collector.client
        assert client2 == mock_client
        assert mock_create_client.call_count == 1

    @patch("src.config_service.collector.create_boto_client")
    def test_account_id_property(self, mock_create_client):
        """Test account_id property fetches from STS."""
        mock_sts_client = MagicMock()
        mock_sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_create_client.return_value = mock_sts_client

        mock_session = MagicMock()
        collector = ConfigResourceCollector(mock_session, "us-east-1")

        account_id = collector.account_id
        assert account_id == "123456789012"

        # Second access returns cached value
        account_id2 = collector.account_id
        assert account_id2 == "123456789012"
        assert mock_sts_client.get_caller_identity.call_count == 1


class TestCollectByType:
    """Tests for collect_by_type method."""

    @patch("src.config_service.collector.create_boto_client")
    def test_collect_by_type_success(self, mock_create_client):
        """Test successful resource collection via Config."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Mock list_discovered_resources paginator
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "resourceIdentifiers": [
                    {"resourceId": "i-1234567890abcdef0"},
                    {"resourceId": "i-0987654321fedcba0"},
                ]
            }
        ]

        # Mock batch_get_resource_config
        mock_client.batch_get_resource_config.return_value = {
            "baseConfigurationItems": [
                {
                    "resourceType": "AWS::EC2::Instance",
                    "resourceId": "i-1234567890abcdef0",
                    "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
                    "resourceName": "my-instance-1",
                    "configuration": json.dumps({"instanceId": "i-1234567890abcdef0"}),
                    "awsRegion": "us-east-1",
                },
                {
                    "resourceType": "AWS::EC2::Instance",
                    "resourceId": "i-0987654321fedcba0",
                    "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-0987654321fedcba0",
                    "resourceName": "my-instance-2",
                    "configuration": json.dumps({"instanceId": "i-0987654321fedcba0"}),
                    "awsRegion": "us-east-1",
                },
            ],
            "unprocessedResourceKeys": [],
        }

        mock_session = MagicMock()
        collector = ConfigResourceCollector(mock_session, "us-east-1")

        resources = collector.collect_by_type("AWS::EC2::Instance")

        assert len(resources) == 2
        assert resources[0].resource_type == "AWS::EC2::Instance"
        assert resources[0].name == "my-instance-1"
        assert resources[1].name == "my-instance-2"

    @patch("src.config_service.collector.create_boto_client")
    def test_collect_by_type_no_resources(self, mock_create_client):
        """Test collection when no resources exist."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"resourceIdentifiers": []}]

        mock_session = MagicMock()
        collector = ConfigResourceCollector(mock_session, "us-east-1")

        resources = collector.collect_by_type("AWS::EC2::Instance")

        assert resources == []

    @patch("src.config_service.collector.create_boto_client")
    def test_collect_by_type_api_error(self, mock_create_client):
        """Test collection handles API errors."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.side_effect = Exception("Config API error")

        mock_session = MagicMock()
        collector = ConfigResourceCollector(mock_session, "us-east-1")

        with pytest.raises(Exception, match="Config API error"):
            collector.collect_by_type("AWS::EC2::Instance")


class TestBatchGetResourceConfigs:
    """Tests for _batch_get_resource_configs method."""

    @patch("src.config_service.collector.create_boto_client")
    def test_batch_get_handles_large_lists(self, mock_create_client):
        """Test batching for more than 100 resources."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Create 150 resource IDs
        resource_ids = [f"resource-{i}" for i in range(150)]

        # Mock batch_get_resource_config to return results
        def batch_response(resourceKeys):
            return {
                "baseConfigurationItems": [
                    {
                        "resourceType": "AWS::S3::Bucket",
                        "resourceId": key["resourceId"],
                        "configuration": "{}",
                    }
                    for key in resourceKeys
                ],
                "unprocessedResourceKeys": [],
            }

        mock_client.batch_get_resource_config.side_effect = batch_response

        mock_session = MagicMock()
        collector = ConfigResourceCollector(mock_session, "us-east-1")

        result = collector._batch_get_resource_configs("AWS::S3::Bucket", resource_ids)

        # Should make 2 calls (100 + 50)
        assert mock_client.batch_get_resource_config.call_count == 2
        assert len(result) == 150

    @patch("src.config_service.collector.create_boto_client")
    def test_batch_get_handles_unprocessed_keys(self, mock_create_client):
        """Test handling of unprocessed resource keys."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_client.batch_get_resource_config.return_value = {
            "baseConfigurationItems": [
                {
                    "resourceType": "AWS::S3::Bucket",
                    "resourceId": "bucket-1",
                    "configuration": "{}",
                }
            ],
            "unprocessedResourceKeys": [{"resourceType": "AWS::S3::Bucket", "resourceId": "bucket-2"}],
        }

        mock_session = MagicMock()
        collector = ConfigResourceCollector(mock_session, "us-east-1")

        result = collector._batch_get_resource_configs("AWS::S3::Bucket", ["bucket-1", "bucket-2"])

        # Should return only the processed items
        assert len(result) == 1


class TestNormalizeConfigItem:
    """Tests for _normalize_config_item method."""

    @patch("src.config_service.collector.create_boto_client")
    def test_normalize_with_arn(self, mock_create_client):
        """Test normalization when ARN is provided."""
        mock_session = MagicMock()
        collector = ConfigResourceCollector(mock_session, "us-east-1")

        config_item = {
            "resourceType": "AWS::EC2::Instance",
            "resourceId": "i-1234567890abcdef0",
            "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            "resourceName": "my-instance",
            "configuration": json.dumps({"instanceId": "i-1234567890abcdef0", "state": "running"}),
            "awsRegion": "us-east-1",
            "configurationItemCaptureTime": "2024-01-15T10:30:00Z",
        }

        resource = collector._normalize_config_item(config_item)

        assert resource is not None
        assert resource.arn == "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0"
        assert resource.resource_type == "AWS::EC2::Instance"
        assert resource.name == "my-instance"
        assert resource.region == "us-east-1"
        assert resource.source == "config"  # Verify source is set

    @patch("src.config_service.collector.create_boto_client")
    def test_normalize_without_arn_constructs_one(self, mock_create_client):
        """Test ARN construction when not provided."""
        mock_sts_client = MagicMock()
        mock_sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_create_client.return_value = mock_sts_client

        mock_session = MagicMock()
        collector = ConfigResourceCollector(mock_session, "us-east-1")

        config_item = {
            "resourceType": "AWS::S3::Bucket",
            "resourceId": "my-bucket",
            "resourceName": "my-bucket",
            "configuration": "{}",
        }

        resource = collector._normalize_config_item(config_item)

        assert resource is not None
        assert resource.arn == "arn:aws:s3:::my-bucket"

    @patch("src.config_service.collector.create_boto_client")
    def test_normalize_with_tags(self, mock_create_client):
        """Test extraction of tags from supplementary configuration."""
        mock_session = MagicMock()
        collector = ConfigResourceCollector(mock_session, "us-east-1")

        config_item = {
            "resourceType": "AWS::EC2::Instance",
            "resourceId": "i-1234567890abcdef0",
            "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            "configuration": "{}",
            "supplementaryConfiguration": {
                "Tags": json.dumps(
                    [
                        {"Key": "Name", "Value": "my-instance"},
                        {"Key": "Environment", "Value": "production"},
                    ]
                )
            },
        }

        resource = collector._normalize_config_item(config_item)

        assert resource is not None
        assert resource.tags == {"Name": "my-instance", "Environment": "production"}

    @patch("src.config_service.collector.create_boto_client")
    def test_normalize_iam_sets_global_region(self, mock_create_client):
        """Test that IAM resources are marked as global."""
        mock_sts_client = MagicMock()
        mock_sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_create_client.return_value = mock_sts_client

        mock_session = MagicMock()
        collector = ConfigResourceCollector(mock_session, "us-east-1")

        config_item = {
            "resourceType": "AWS::IAM::Role",
            "resourceId": "my-role",
            "resourceName": "my-role",
            "arn": "arn:aws:iam::123456789012:role/my-role",
            "configuration": "{}",
            "awsRegion": "us-east-1",
        }

        resource = collector._normalize_config_item(config_item)

        assert resource is not None
        assert resource.region == "global"


class TestConstructArn:
    """Tests for _construct_arn method."""

    @patch("src.config_service.collector.create_boto_client")
    def test_construct_arn_s3(self, mock_create_client):
        """Test S3 bucket ARN construction."""
        mock_sts_client = MagicMock()
        mock_sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_create_client.return_value = mock_sts_client

        mock_session = MagicMock()
        collector = ConfigResourceCollector(mock_session, "us-east-1")

        arn = collector._construct_arn("AWS::S3::Bucket", "my-bucket")
        assert arn == "arn:aws:s3:::my-bucket"

    @patch("src.config_service.collector.create_boto_client")
    def test_construct_arn_lambda(self, mock_create_client):
        """Test Lambda function ARN construction."""
        mock_sts_client = MagicMock()
        mock_sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_create_client.return_value = mock_sts_client

        mock_session = MagicMock()
        collector = ConfigResourceCollector(mock_session, "us-east-1")

        arn = collector._construct_arn("AWS::Lambda::Function", "my-function")
        assert arn == "arn:aws:lambda:us-east-1:123456789012:function:my-function"

    @patch("src.config_service.collector.create_boto_client")
    def test_construct_arn_iam(self, mock_create_client):
        """Test IAM role ARN construction."""
        mock_sts_client = MagicMock()
        mock_sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_create_client.return_value = mock_sts_client

        mock_session = MagicMock()
        collector = ConfigResourceCollector(mock_session, "us-east-1")

        arn = collector._construct_arn("AWS::IAM::Role", "my-role")
        assert arn == "arn:aws:iam::123456789012:role/my-role"

    @patch("src.config_service.collector.create_boto_client")
    def test_construct_arn_dynamodb(self, mock_create_client):
        """Test DynamoDB table ARN construction."""
        mock_sts_client = MagicMock()
        mock_sts_client.get_caller_identity.return_value = {"Account": "123456789012"}
        mock_create_client.return_value = mock_sts_client

        mock_session = MagicMock()
        collector = ConfigResourceCollector(mock_session, "us-east-1")

        arn = collector._construct_arn("AWS::DynamoDB::Table", "my-table")
        assert arn == "arn:aws:dynamodb:us-east-1:123456789012:table/my-table"


class TestCollectMultipleTypes:
    """Tests for collect_multiple_types method."""

    @patch("src.config_service.collector.create_boto_client")
    def test_collect_multiple_types(self, mock_create_client):
        """Test collecting resources of multiple types."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Mock for first type - EC2
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator

        call_count = [0]

        def paginate_side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return [{"resourceIdentifiers": [{"resourceId": "i-123"}]}]
            else:
                return [{"resourceIdentifiers": [{"resourceId": "bucket-1"}]}]

        mock_paginator.paginate.side_effect = paginate_side_effect

        def batch_get_side_effect(resourceKeys):
            resource_type = resourceKeys[0]["resourceType"]
            resource_id = resourceKeys[0]["resourceId"]
            return {
                "baseConfigurationItems": [
                    {
                        "resourceType": resource_type,
                        "resourceId": resource_id,
                        "arn": f"arn:aws:{resource_type.lower()}:us-east-1:123456789012:{resource_id}",
                        "configuration": "{}",
                    }
                ],
                "unprocessedResourceKeys": [],
            }

        mock_client.batch_get_resource_config.side_effect = batch_get_side_effect

        mock_session = MagicMock()
        collector = ConfigResourceCollector(mock_session, "us-east-1")

        resources = collector.collect_multiple_types(["AWS::EC2::Instance", "AWS::S3::Bucket"])

        assert len(resources) == 2

    @patch("src.config_service.collector.create_boto_client")
    def test_collect_multiple_types_handles_errors(self, mock_create_client):
        """Test that errors in one type don't stop others."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator

        call_count = [0]

        def paginate_side_effect(**kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Error on first type")
            return [{"resourceIdentifiers": [{"resourceId": "bucket-1"}]}]

        mock_paginator.paginate.side_effect = paginate_side_effect

        mock_client.batch_get_resource_config.return_value = {
            "baseConfigurationItems": [
                {
                    "resourceType": "AWS::S3::Bucket",
                    "resourceId": "bucket-1",
                    "arn": "arn:aws:s3:::bucket-1",
                    "configuration": "{}",
                }
            ],
            "unprocessedResourceKeys": [],
        }

        mock_session = MagicMock()
        collector = ConfigResourceCollector(mock_session, "us-east-1")

        # Should continue with second type even though first failed
        resources = collector.collect_multiple_types(["AWS::EC2::Instance", "AWS::S3::Bucket"])

        assert len(resources) == 1
        assert resources[0].resource_type == "AWS::S3::Bucket"
