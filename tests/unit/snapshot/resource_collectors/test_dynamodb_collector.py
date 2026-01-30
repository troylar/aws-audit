"""Tests for DynamoDB resource collector."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.dynamodb import DynamoDBCollector


@pytest.fixture
def mock_session():
    """Create a mock boto3 session."""
    session = MagicMock()
    session.profile_name = "default"
    return session


class TestDynamoDBCollectorProperties:
    """Tests for DynamoDBCollector properties."""

    def test_service_name(self, mock_session):
        """Test service_name property returns dynamodb."""
        collector = DynamoDBCollector(session=mock_session, region="us-east-1")
        assert collector.service_name == "dynamodb"


class TestDynamoDBCollectorCollect:
    """Tests for DynamoDBCollector.collect method."""

    @patch.object(DynamoDBCollector, "_create_client")
    def test_collect_no_tables(self, mock_create_client, mock_session):
        """Test collecting when no tables exist."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"TableNames": []}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = DynamoDBCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert resources == []
        mock_client.get_paginator.assert_called_once_with("list_tables")

    @patch.object(DynamoDBCollector, "_create_client")
    def test_collect_single_table(self, mock_create_client, mock_session):
        """Test collecting a single table."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"TableNames": ["test-table"]}]
        mock_client.get_paginator.return_value = mock_paginator

        created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_client.describe_table.return_value = {
            "Table": {
                "TableName": "test-table",
                "TableArn": "arn:aws:dynamodb:us-east-1:123456789012:table/test-table",
                "CreationDateTime": created_at,
            }
        }
        mock_client.list_tags_of_resource.return_value = {"Tags": [{"Key": "Environment", "Value": "test"}]}
        mock_create_client.return_value = mock_client

        collector = DynamoDBCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "test-table"
        assert resources[0].resource_type == "AWS::DynamoDB::Table"
        assert resources[0].region == "us-east-1"
        assert resources[0].tags == {"Environment": "test"}
        assert resources[0].created_at == created_at

    @patch.object(DynamoDBCollector, "_create_client")
    def test_collect_multiple_tables(self, mock_create_client, mock_session):
        """Test collecting multiple tables."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"TableNames": ["table-1", "table-2"]}]
        mock_client.get_paginator.return_value = mock_paginator

        def describe_table_side_effect(**kwargs):
            table_name = kwargs["TableName"]
            return {
                "Table": {
                    "TableName": table_name,
                    "TableArn": f"arn:aws:dynamodb:us-east-1:123456789012:table/{table_name}",
                }
            }

        mock_client.describe_table.side_effect = describe_table_side_effect
        mock_client.list_tags_of_resource.return_value = {"Tags": []}
        mock_create_client.return_value = mock_client

        collector = DynamoDBCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 2
        assert resources[0].name == "table-1"
        assert resources[1].name == "table-2"

    @patch.object(DynamoDBCollector, "_create_client")
    def test_collect_handles_describe_error(self, mock_create_client, mock_session):
        """Test collecting continues when describe_table fails."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"TableNames": ["good-table", "bad-table"]}]
        mock_client.get_paginator.return_value = mock_paginator

        def describe_table_side_effect(**kwargs):
            if kwargs["TableName"] == "bad-table":
                raise Exception("Access denied")
            return {
                "Table": {
                    "TableName": kwargs["TableName"],
                    "TableArn": f"arn:aws:dynamodb:us-east-1:123456789012:table/{kwargs['TableName']}",
                }
            }

        mock_client.describe_table.side_effect = describe_table_side_effect
        mock_client.list_tags_of_resource.return_value = {"Tags": []}
        mock_create_client.return_value = mock_client

        collector = DynamoDBCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should only get the good table
        assert len(resources) == 1
        assert resources[0].name == "good-table"

    @patch.object(DynamoDBCollector, "_create_client")
    def test_collect_handles_tags_error(self, mock_create_client, mock_session):
        """Test collecting continues when list_tags fails."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"TableNames": ["test-table"]}]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.describe_table.return_value = {
            "Table": {
                "TableName": "test-table",
                "TableArn": "arn:aws:dynamodb:us-east-1:123456789012:table/test-table",
            }
        }
        mock_client.list_tags_of_resource.side_effect = Exception("Access denied")
        mock_create_client.return_value = mock_client

        collector = DynamoDBCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still get the table, just without tags
        assert len(resources) == 1
        assert resources[0].name == "test-table"
        assert resources[0].tags == {}

    @patch.object(DynamoDBCollector, "_create_client")
    def test_collect_handles_list_tables_error(self, mock_create_client, mock_session):
        """Test collecting handles list_tables error."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.side_effect = Exception("Service unavailable")
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = DynamoDBCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should return empty list on error
        assert resources == []

    @patch.object(DynamoDBCollector, "_create_client")
    def test_collect_with_pagination(self, mock_create_client, mock_session):
        """Test collecting with multiple pages."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"TableNames": ["table-1", "table-2"]},
            {"TableNames": ["table-3"]},
        ]
        mock_client.get_paginator.return_value = mock_paginator

        def describe_table_side_effect(**kwargs):
            return {
                "Table": {
                    "TableName": kwargs["TableName"],
                    "TableArn": f"arn:aws:dynamodb:us-east-1:123456789012:table/{kwargs['TableName']}",
                }
            }

        mock_client.describe_table.side_effect = describe_table_side_effect
        mock_client.list_tags_of_resource.return_value = {"Tags": []}
        mock_create_client.return_value = mock_client

        collector = DynamoDBCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 3

    @patch.object(DynamoDBCollector, "_create_client")
    def test_collect_generates_config_hash(self, mock_create_client, mock_session):
        """Test that config hash is generated from table config."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"TableNames": ["test-table"]}]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.describe_table.return_value = {
            "Table": {
                "TableName": "test-table",
                "TableArn": "arn:aws:dynamodb:us-east-1:123456789012:table/test-table",
                "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
            }
        }
        mock_client.list_tags_of_resource.return_value = {"Tags": []}
        mock_create_client.return_value = mock_client

        collector = DynamoDBCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].config_hash is not None
        assert len(resources[0].config_hash) > 0

    @patch.object(DynamoDBCollector, "_create_client")
    def test_collect_stores_raw_config(self, mock_create_client, mock_session):
        """Test that raw config is stored in resource."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"TableNames": ["test-table"]}]
        mock_client.get_paginator.return_value = mock_paginator

        table_config = {
            "TableName": "test-table",
            "TableArn": "arn:aws:dynamodb:us-east-1:123456789012:table/test-table",
            "KeySchema": [{"AttributeName": "id", "KeyType": "HASH"}],
        }
        mock_client.describe_table.return_value = {"Table": table_config}
        mock_client.list_tags_of_resource.return_value = {"Tags": []}
        mock_create_client.return_value = mock_client

        collector = DynamoDBCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].raw_config == table_config
