"""Unit tests for Lambda resource collector."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.lambda_func import (
    LambdaCollector,
    _parse_lambda_timestamp,
)


class TestParseLambdaTimestamp:
    """Tests for the _parse_lambda_timestamp helper function."""

    def test_parse_valid_timestamp_with_plus_offset(self):
        """Test parsing Lambda timestamp with +0000 offset."""
        timestamp = "2024-01-15T10:30:00.000+0000"
        result = _parse_lambda_timestamp(timestamp)

        assert result is not None
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30
        assert result.second == 0

    def test_parse_valid_timestamp_with_minus_offset(self):
        """Test parsing Lambda timestamp with -0000 offset."""
        timestamp = "2024-06-20T15:45:30.123-0000"
        result = _parse_lambda_timestamp(timestamp)

        assert result is not None
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 6
        assert result.day == 20

    def test_parse_timestamp_with_standard_offset(self):
        """Test parsing timestamp already in standard +00:00 format."""
        timestamp = "2024-03-10T08:00:00.000+00:00"
        result = _parse_lambda_timestamp(timestamp)

        assert result is not None
        assert result.year == 2024
        assert result.month == 3
        assert result.day == 10

    def test_parse_none_timestamp(self):
        """Test parsing None returns None."""
        result = _parse_lambda_timestamp(None)
        assert result is None

    def test_parse_empty_string(self):
        """Test parsing empty string returns None."""
        result = _parse_lambda_timestamp("")
        assert result is None

    def test_parse_invalid_timestamp(self):
        """Test parsing invalid timestamp returns None."""
        result = _parse_lambda_timestamp("not-a-timestamp")
        assert result is None

    def test_parse_partial_timestamp(self):
        """Test parsing partial/malformed timestamp returns None."""
        result = _parse_lambda_timestamp("2024-01-15")
        # This is actually valid ISO format for date-only
        assert result is not None
        assert result.year == 2024


class TestLambdaCollector:
    """Tests for LambdaCollector."""

    @pytest.fixture
    def collector(self):
        """Create a LambdaCollector instance for testing."""
        mock_session = MagicMock()
        mock_session.profile_name = "default"
        collector = LambdaCollector(session=mock_session, region="us-east-1")
        return collector

    def test_service_name(self, collector):
        """Test service name property."""
        assert collector.service_name == "lambda"

    def test_collect_functions_with_timestamp(self, collector):
        """Test collecting Lambda functions extracts LastModified timestamp."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Functions": [
                    {
                        "FunctionName": "test-function",
                        "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:test-function",
                        "LastModified": "2024-01-15T10:30:00.000+0000",
                        "Runtime": "python3.9",
                    }
                ]
            }
        ]
        mock_client.get_function.return_value = {
            "Configuration": {
                "FunctionName": "test-function",
                "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:test-function",
                "LastModified": "2024-01-15T10:30:00.000+0000",
                "Runtime": "python3.9",
            },
            "Tags": {"Environment": "test"},
        }

        with patch.object(collector, "_create_client", return_value=mock_client):
            with patch.object(collector, "_get_account_id", return_value="123456789012"):
                resources = collector._collect_functions("123456789012")

        assert len(resources) == 1
        resource = resources[0]
        assert resource.name == "test-function"
        assert resource.created_at is not None
        assert isinstance(resource.created_at, datetime)
        assert resource.created_at.year == 2024
        assert resource.created_at.month == 1
        assert resource.created_at.day == 15

    def test_collect_functions_without_timestamp(self, collector):
        """Test collecting Lambda functions handles missing LastModified."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Functions": [
                    {
                        "FunctionName": "test-function",
                        "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:test-function",
                        "Runtime": "python3.9",
                        # No LastModified field
                    }
                ]
            }
        ]
        mock_client.get_function.return_value = {
            "Configuration": {
                "FunctionName": "test-function",
                "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:test-function",
                "Runtime": "python3.9",
            },
            "Tags": {},
        }

        with patch.object(collector, "_create_client", return_value=mock_client):
            with patch.object(collector, "_get_account_id", return_value="123456789012"):
                resources = collector._collect_functions("123456789012")

        assert len(resources) == 1
        resource = resources[0]
        assert resource.name == "test-function"
        assert resource.created_at is None

    def test_collect_layers_with_timestamp(self, collector):
        """Test collecting Lambda layers extracts CreatedDate timestamp."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Layers": [
                    {
                        "LayerName": "test-layer",
                        "LayerArn": "arn:aws:lambda:us-east-1:123456789012:layer:test-layer",
                        "LatestMatchingVersion": {
                            "LayerVersionArn": "arn:aws:lambda:us-east-1:123456789012:layer:test-layer:1",
                            "CreatedDate": "2024-02-20T14:00:00.000+0000",
                            "Version": 1,
                        },
                    }
                ]
            }
        ]

        with patch.object(collector, "_create_client", return_value=mock_client):
            with patch.object(collector, "_get_account_id", return_value="123456789012"):
                resources = collector._collect_layers("123456789012")

        assert len(resources) == 1
        resource = resources[0]
        assert resource.name == "test-layer"
        assert resource.resource_type == "AWS::Lambda::LayerVersion"
        assert resource.created_at is not None
        assert isinstance(resource.created_at, datetime)
        assert resource.created_at.year == 2024
        assert resource.created_at.month == 2
        assert resource.created_at.day == 20

    def test_collect_layers_without_timestamp(self, collector):
        """Test collecting Lambda layers handles missing CreatedDate."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Layers": [
                    {
                        "LayerName": "test-layer",
                        "LayerArn": "arn:aws:lambda:us-east-1:123456789012:layer:test-layer",
                        "LatestMatchingVersion": {
                            "LayerVersionArn": "arn:aws:lambda:us-east-1:123456789012:layer:test-layer:1",
                            "Version": 1,
                            # No CreatedDate field
                        },
                    }
                ]
            }
        ]

        with patch.object(collector, "_create_client", return_value=mock_client):
            with patch.object(collector, "_get_account_id", return_value="123456789012"):
                resources = collector._collect_layers("123456789012")

        assert len(resources) == 1
        resource = resources[0]
        assert resource.name == "test-layer"
        assert resource.created_at is None

    @patch.object(LambdaCollector, "_create_client")
    @patch.object(LambdaCollector, "_get_account_id")
    def test_collect_combines_functions_and_layers(self, mock_get_account_id, mock_create_client, collector):
        """Test that collect() combines functions and layers."""
        mock_get_account_id.return_value = "123456789012"
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Setup function paginator
        mock_func_paginator = MagicMock()
        mock_func_paginator.paginate.return_value = [{
            "Functions": [{
                "FunctionName": "my-function",
                "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:my-function",
            }]
        }]

        # Setup layer paginator
        mock_layer_paginator = MagicMock()
        mock_layer_paginator.paginate.return_value = [{
            "Layers": [{
                "LayerName": "my-layer",
                "LayerArn": "arn:aws:lambda:us-east-1:123456789012:layer:my-layer",
                "LatestMatchingVersion": {
                    "LayerVersionArn": "arn:aws:lambda:us-east-1:123456789012:layer:my-layer:1",
                },
            }]
        }]

        def get_paginator_side_effect(operation):
            if operation == "list_functions":
                return mock_func_paginator
            elif operation == "list_layers":
                return mock_layer_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.get_function.return_value = {"Configuration": {}, "Tags": {}}

        resources = collector.collect()

        assert len(resources) == 2
        types = [r.resource_type for r in resources]
        assert "AWS::Lambda::Function" in types
        assert "AWS::Lambda::LayerVersion" in types

    @patch.object(LambdaCollector, "_create_client")
    def test_collect_functions_handles_list_error(self, mock_create_client, collector):
        """Test collecting handles list_functions error."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.side_effect = Exception("Service unavailable")
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        resources = collector._collect_functions("123456789012")

        assert resources == []

    @patch.object(LambdaCollector, "_create_client")
    def test_collect_functions_handles_get_function_error(self, mock_create_client, collector):
        """Test collecting continues when get_function fails."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{
            "Functions": [{
                "FunctionName": "my-function",
                "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:my-function",
            }]
        }]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.get_function.side_effect = Exception("Access denied")
        mock_create_client.return_value = mock_client

        resources = collector._collect_functions("123456789012")

        # Should still get the function without tags
        assert len(resources) == 1
        assert resources[0].tags == {}

    @patch.object(LambdaCollector, "_create_client")
    def test_collect_layers_handles_list_error(self, mock_create_client, collector):
        """Test collecting handles list_layers error."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.side_effect = Exception("Service unavailable")
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        resources = collector._collect_layers("123456789012")

        assert resources == []

    @patch.object(LambdaCollector, "_create_client")
    def test_collect_layers_without_latest_version(self, mock_create_client, collector):
        """Test collecting layer when LatestMatchingVersion is missing."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{
            "Layers": [{
                "LayerName": "my-layer",
                "LayerArn": "arn:aws:lambda:us-east-1:123456789012:layer:my-layer",
                # No LatestMatchingVersion
            }]
        }]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        resources = collector._collect_layers("123456789012")

        # Should still get the layer using LayerArn
        assert len(resources) == 1
        assert resources[0].name == "my-layer"

    @patch.object(LambdaCollector, "_create_client")
    def test_collect_generates_config_hash(self, mock_create_client, collector):
        """Test that config hash is generated."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{
            "Functions": [{
                "FunctionName": "my-function",
                "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:my-function",
            }]
        }]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.get_function.return_value = {"Configuration": {}, "Tags": {}}
        mock_create_client.return_value = mock_client

        resources = collector._collect_functions("123456789012")

        assert len(resources) == 1
        assert resources[0].config_hash is not None
        assert len(resources[0].config_hash) > 0
