"""Tests for API Gateway resource collector."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.apigateway import APIGatewayCollector


@pytest.fixture
def mock_session():
    """Create a mock boto3 session."""
    session = MagicMock()
    session.profile_name = "default"
    return session


class TestAPIGatewayCollectorProperties:
    """Tests for APIGatewayCollector properties."""

    def test_service_name(self, mock_session):
        """Test service_name property returns apigateway."""
        collector = APIGatewayCollector(session=mock_session, region="us-east-1")
        assert collector.service_name == "apigateway"


class TestAPIGatewayCollectorCollect:
    """Tests for APIGatewayCollector.collect method."""

    @patch.object(APIGatewayCollector, "_create_client")
    def test_collect_no_apis(self, mock_create_client, mock_session):
        """Test collecting when no APIs exist."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"items": [], "Items": []}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = APIGatewayCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert resources == []

    @patch.object(APIGatewayCollector, "_create_client")
    def test_collect_rest_api(self, mock_create_client, mock_session):
        """Test collecting a REST API (v1)."""
        mock_v1_client = MagicMock()
        mock_v2_client = MagicMock()

        created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

        # V1 client for REST APIs
        mock_v1_paginator = MagicMock()
        mock_v1_paginator.paginate.return_value = [{
            "items": [{
                "id": "abc123",
                "name": "my-rest-api",
                "createdDate": created_at,
            }]
        }]
        mock_v1_client.get_paginator.return_value = mock_v1_paginator
        mock_v1_client.get_tags.return_value = {"tags": {"Environment": "test"}}

        # V2 client for HTTP/WebSocket APIs
        mock_v2_paginator = MagicMock()
        mock_v2_paginator.paginate.return_value = [{"Items": []}]
        mock_v2_client.get_paginator.return_value = mock_v2_paginator

        def create_client_side_effect(service_name=None):
            if service_name == "apigatewayv2":
                return mock_v2_client
            return mock_v1_client

        mock_create_client.side_effect = create_client_side_effect

        collector = APIGatewayCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "my-rest-api"
        assert resources[0].resource_type == "AWS::ApiGateway::RestApi"
        assert resources[0].region == "us-east-1"
        assert resources[0].tags == {"Environment": "test"}
        assert resources[0].created_at == created_at
        assert "abc123" in resources[0].arn

    @patch.object(APIGatewayCollector, "_create_client")
    def test_collect_http_api(self, mock_create_client, mock_session):
        """Test collecting an HTTP API (v2)."""
        mock_v1_client = MagicMock()
        mock_v2_client = MagicMock()

        created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

        # V1 client returns empty
        mock_v1_paginator = MagicMock()
        mock_v1_paginator.paginate.return_value = [{"items": []}]
        mock_v1_client.get_paginator.return_value = mock_v1_paginator

        # V2 client returns HTTP API
        mock_v2_paginator = MagicMock()
        mock_v2_paginator.paginate.return_value = [{
            "Items": [{
                "ApiId": "xyz789",
                "Name": "my-http-api",
                "ProtocolType": "HTTP",
                "CreatedDate": created_at,
                "Tags": {"Team": "platform"},
            }]
        }]
        mock_v2_client.get_paginator.return_value = mock_v2_paginator

        def create_client_side_effect(service_name=None):
            if service_name == "apigatewayv2":
                return mock_v2_client
            return mock_v1_client

        mock_create_client.side_effect = create_client_side_effect

        collector = APIGatewayCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "my-http-api"
        assert resources[0].resource_type == "AWS::ApiGatewayV2::Api::HTTP"
        assert resources[0].tags == {"Team": "platform"}

    @patch.object(APIGatewayCollector, "_create_client")
    def test_collect_websocket_api(self, mock_create_client, mock_session):
        """Test collecting a WebSocket API (v2)."""
        mock_v1_client = MagicMock()
        mock_v2_client = MagicMock()

        # V1 client returns empty
        mock_v1_paginator = MagicMock()
        mock_v1_paginator.paginate.return_value = [{"items": []}]
        mock_v1_client.get_paginator.return_value = mock_v1_paginator

        # V2 client returns WebSocket API
        mock_v2_paginator = MagicMock()
        mock_v2_paginator.paginate.return_value = [{
            "Items": [{
                "ApiId": "ws123",
                "Name": "my-websocket-api",
                "ProtocolType": "WEBSOCKET",
                "Tags": {},
            }]
        }]
        mock_v2_client.get_paginator.return_value = mock_v2_paginator

        def create_client_side_effect(service_name=None):
            if service_name == "apigatewayv2":
                return mock_v2_client
            return mock_v1_client

        mock_create_client.side_effect = create_client_side_effect

        collector = APIGatewayCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "my-websocket-api"
        assert resources[0].resource_type == "AWS::ApiGatewayV2::Api::WebSocket"

    @patch.object(APIGatewayCollector, "_create_client")
    def test_collect_unknown_protocol_type(self, mock_create_client, mock_session):
        """Test collecting an API with unknown protocol type."""
        mock_v1_client = MagicMock()
        mock_v2_client = MagicMock()

        # V1 client returns empty
        mock_v1_paginator = MagicMock()
        mock_v1_paginator.paginate.return_value = [{"items": []}]
        mock_v1_client.get_paginator.return_value = mock_v1_paginator

        # V2 client returns unknown protocol
        mock_v2_paginator = MagicMock()
        mock_v2_paginator.paginate.return_value = [{
            "Items": [{
                "ApiId": "new123",
                "Name": "my-new-api",
                "ProtocolType": "NEWPROTOCOL",
                "Tags": {},
            }]
        }]
        mock_v2_client.get_paginator.return_value = mock_v2_paginator

        def create_client_side_effect(service_name=None):
            if service_name == "apigatewayv2":
                return mock_v2_client
            return mock_v1_client

        mock_create_client.side_effect = create_client_side_effect

        collector = APIGatewayCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].resource_type == "AWS::ApiGatewayV2::Api::NEWPROTOCOL"

    @patch.object(APIGatewayCollector, "_create_client")
    def test_collect_multiple_apis(self, mock_create_client, mock_session):
        """Test collecting multiple APIs of different types."""
        mock_v1_client = MagicMock()
        mock_v2_client = MagicMock()

        # V1 client returns REST API
        mock_v1_paginator = MagicMock()
        mock_v1_paginator.paginate.return_value = [{
            "items": [{"id": "rest1", "name": "rest-api-1"}]
        }]
        mock_v1_client.get_paginator.return_value = mock_v1_paginator
        mock_v1_client.get_tags.return_value = {"tags": {}}

        # V2 client returns HTTP and WebSocket APIs
        mock_v2_paginator = MagicMock()
        mock_v2_paginator.paginate.return_value = [{
            "Items": [
                {"ApiId": "http1", "Name": "http-api-1", "ProtocolType": "HTTP", "Tags": {}},
                {"ApiId": "ws1", "Name": "ws-api-1", "ProtocolType": "WEBSOCKET", "Tags": {}},
            ]
        }]
        mock_v2_client.get_paginator.return_value = mock_v2_paginator

        def create_client_side_effect(service_name=None):
            if service_name == "apigatewayv2":
                return mock_v2_client
            return mock_v1_client

        mock_create_client.side_effect = create_client_side_effect

        collector = APIGatewayCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 3
        types = [r.resource_type for r in resources]
        assert "AWS::ApiGateway::RestApi" in types
        assert "AWS::ApiGatewayV2::Api::HTTP" in types
        assert "AWS::ApiGatewayV2::Api::WebSocket" in types

    @patch.object(APIGatewayCollector, "_create_client")
    def test_collect_handles_v1_error(self, mock_create_client, mock_session):
        """Test collecting handles REST API error gracefully."""
        mock_v1_client = MagicMock()
        mock_v2_client = MagicMock()

        # V1 client raises error
        mock_v1_paginator = MagicMock()
        mock_v1_paginator.paginate.side_effect = Exception("V1 service unavailable")
        mock_v1_client.get_paginator.return_value = mock_v1_paginator

        # V2 client works
        mock_v2_paginator = MagicMock()
        mock_v2_paginator.paginate.return_value = [{
            "Items": [{"ApiId": "http1", "Name": "http-api", "ProtocolType": "HTTP", "Tags": {}}]
        }]
        mock_v2_client.get_paginator.return_value = mock_v2_paginator

        def create_client_side_effect(service_name=None):
            if service_name == "apigatewayv2":
                return mock_v2_client
            return mock_v1_client

        mock_create_client.side_effect = create_client_side_effect

        collector = APIGatewayCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still get v2 APIs
        assert len(resources) == 1
        assert resources[0].name == "http-api"

    @patch.object(APIGatewayCollector, "_create_client")
    def test_collect_handles_v2_error(self, mock_create_client, mock_session):
        """Test collecting handles v2 API error gracefully."""
        mock_v1_client = MagicMock()
        mock_v2_client = MagicMock()

        # V1 client works
        mock_v1_paginator = MagicMock()
        mock_v1_paginator.paginate.return_value = [{
            "items": [{"id": "rest1", "name": "rest-api"}]
        }]
        mock_v1_client.get_paginator.return_value = mock_v1_paginator
        mock_v1_client.get_tags.return_value = {"tags": {}}

        # V2 client raises error
        mock_v2_paginator = MagicMock()
        mock_v2_paginator.paginate.side_effect = Exception("V2 service unavailable")
        mock_v2_client.get_paginator.return_value = mock_v2_paginator

        def create_client_side_effect(service_name=None):
            if service_name == "apigatewayv2":
                return mock_v2_client
            return mock_v1_client

        mock_create_client.side_effect = create_client_side_effect

        collector = APIGatewayCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still get v1 APIs
        assert len(resources) == 1
        assert resources[0].name == "rest-api"

    @patch.object(APIGatewayCollector, "_create_client")
    def test_collect_handles_tags_error(self, mock_create_client, mock_session):
        """Test collecting continues when get_tags fails."""
        mock_v1_client = MagicMock()
        mock_v2_client = MagicMock()

        # V1 client returns REST API
        mock_v1_paginator = MagicMock()
        mock_v1_paginator.paginate.return_value = [{
            "items": [{"id": "rest1", "name": "rest-api"}]
        }]
        mock_v1_client.get_paginator.return_value = mock_v1_paginator
        mock_v1_client.get_tags.side_effect = Exception("Access denied")

        # V2 client returns empty
        mock_v2_paginator = MagicMock()
        mock_v2_paginator.paginate.return_value = [{"Items": []}]
        mock_v2_client.get_paginator.return_value = mock_v2_paginator

        def create_client_side_effect(service_name=None):
            if service_name == "apigatewayv2":
                return mock_v2_client
            return mock_v1_client

        mock_create_client.side_effect = create_client_side_effect

        collector = APIGatewayCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still get the API without tags
        assert len(resources) == 1
        assert resources[0].tags == {}

    @patch.object(APIGatewayCollector, "_create_client")
    def test_collect_generates_config_hash(self, mock_create_client, mock_session):
        """Test that config hash is generated."""
        mock_v1_client = MagicMock()
        mock_v2_client = MagicMock()

        # V1 client returns REST API
        mock_v1_paginator = MagicMock()
        mock_v1_paginator.paginate.return_value = [{
            "items": [{"id": "rest1", "name": "rest-api"}]
        }]
        mock_v1_client.get_paginator.return_value = mock_v1_paginator
        mock_v1_client.get_tags.return_value = {"tags": {}}

        # V2 client returns empty
        mock_v2_paginator = MagicMock()
        mock_v2_paginator.paginate.return_value = [{"Items": []}]
        mock_v2_client.get_paginator.return_value = mock_v2_paginator

        def create_client_side_effect(service_name=None):
            if service_name == "apigatewayv2":
                return mock_v2_client
            return mock_v1_client

        mock_create_client.side_effect = create_client_side_effect

        collector = APIGatewayCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].config_hash is not None
        assert len(resources[0].config_hash) > 0

    @patch.object(APIGatewayCollector, "_create_client")
    def test_collect_with_pagination(self, mock_create_client, mock_session):
        """Test collecting with multiple pages."""
        mock_v1_client = MagicMock()
        mock_v2_client = MagicMock()

        # V1 client returns REST API with pagination
        mock_v1_paginator = MagicMock()
        mock_v1_paginator.paginate.return_value = [
            {"items": [{"id": "rest1", "name": "rest-api-1"}]},
            {"items": [{"id": "rest2", "name": "rest-api-2"}]},
        ]
        mock_v1_client.get_paginator.return_value = mock_v1_paginator
        mock_v1_client.get_tags.return_value = {"tags": {}}

        # V2 client returns empty
        mock_v2_paginator = MagicMock()
        mock_v2_paginator.paginate.return_value = [{"Items": []}]
        mock_v2_client.get_paginator.return_value = mock_v2_paginator

        def create_client_side_effect(service_name=None):
            if service_name == "apigatewayv2":
                return mock_v2_client
            return mock_v1_client

        mock_create_client.side_effect = create_client_side_effect

        collector = APIGatewayCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 2
