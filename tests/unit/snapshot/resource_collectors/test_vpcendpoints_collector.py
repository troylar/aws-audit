"""Tests for VPC Endpoints resource collector."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.vpcendpoints import VPCEndpointsCollector


@pytest.fixture
def mock_session():
    """Create a mock boto3 session."""
    session = MagicMock()
    session.profile_name = "default"
    # Mock the STS client that's used to get account ID
    mock_sts = MagicMock()
    mock_sts.get_caller_identity.return_value = {"Account": "123456789012"}
    session.client.return_value = mock_sts
    return session


class TestVPCEndpointsCollectorProperties:
    """Tests for VPCEndpointsCollector properties."""

    def test_service_name(self, mock_session):
        """Test service_name property returns vpc-endpoints."""
        collector = VPCEndpointsCollector(session=mock_session, region="us-east-1")
        assert collector.service_name == "vpc-endpoints"


class TestVPCEndpointsCollectorCollect:
    """Tests for VPCEndpointsCollector.collect method."""

    @patch.object(VPCEndpointsCollector, "_create_client")
    def test_collect_no_endpoints(self, mock_create_client, mock_session):
        """Test collecting when no VPC endpoints exist."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"VpcEndpoints": []}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = VPCEndpointsCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert resources == []
        mock_client.get_paginator.assert_called_once_with("describe_vpc_endpoints")

    @patch.object(VPCEndpointsCollector, "_create_client")
    def test_collect_single_interface_endpoint(self, mock_create_client, mock_session):
        """Test collecting a single Interface VPC endpoint."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_paginator.paginate.return_value = [{
            "VpcEndpoints": [{
                "VpcEndpointId": "vpce-12345678",
                "ServiceName": "com.amazonaws.us-east-1.s3",
                "VpcEndpointType": "Interface",
                "CreationTimestamp": created_at,
                "Tags": [{"Key": "Environment", "Value": "test"}],
            }]
        }]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = VPCEndpointsCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "vpce-12345678 (s3)"
        assert resources[0].resource_type == "AWS::EC2::VPCEndpoint::Interface"
        assert resources[0].region == "us-east-1"
        assert resources[0].tags == {"Environment": "test"}
        assert resources[0].created_at == created_at
        assert "vpce-12345678" in resources[0].arn

    @patch.object(VPCEndpointsCollector, "_create_client")
    def test_collect_single_gateway_endpoint(self, mock_create_client, mock_session):
        """Test collecting a single Gateway VPC endpoint."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{
            "VpcEndpoints": [{
                "VpcEndpointId": "vpce-87654321",
                "ServiceName": "com.amazonaws.us-east-1.dynamodb",
                "VpcEndpointType": "Gateway",
                "Tags": [],
            }]
        }]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = VPCEndpointsCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "vpce-87654321 (dynamodb)"
        assert resources[0].resource_type == "AWS::EC2::VPCEndpoint::Gateway"

    @patch.object(VPCEndpointsCollector, "_create_client")
    def test_collect_unknown_endpoint_type(self, mock_create_client, mock_session):
        """Test collecting an endpoint with unknown type."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{
            "VpcEndpoints": [{
                "VpcEndpointId": "vpce-11111111",
                "ServiceName": "com.amazonaws.service.new",
                "VpcEndpointType": "NewType",
                "Tags": [],
            }]
        }]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = VPCEndpointsCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].resource_type == "AWS::EC2::VPCEndpoint::NewType"

    @patch.object(VPCEndpointsCollector, "_create_client")
    def test_collect_multiple_endpoints(self, mock_create_client, mock_session):
        """Test collecting multiple VPC endpoints."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{
            "VpcEndpoints": [
                {"VpcEndpointId": "vpce-1", "ServiceName": "com.amazonaws.s3", "VpcEndpointType": "Gateway", "Tags": []},
                {"VpcEndpointId": "vpce-2", "ServiceName": "com.amazonaws.dynamodb", "VpcEndpointType": "Gateway", "Tags": []},
            ]
        }]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = VPCEndpointsCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 2

    @patch.object(VPCEndpointsCollector, "_create_client")
    def test_collect_handles_list_error(self, mock_create_client, mock_session):
        """Test collecting handles describe_vpc_endpoints error."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.side_effect = Exception("Service unavailable")
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = VPCEndpointsCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should return empty list on error
        assert resources == []

    @patch.object(VPCEndpointsCollector, "_create_client")
    def test_collect_with_pagination(self, mock_create_client, mock_session):
        """Test collecting with multiple pages."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"VpcEndpoints": [{"VpcEndpointId": "vpce-1", "ServiceName": "svc1", "VpcEndpointType": "Gateway", "Tags": []}]},
            {"VpcEndpoints": [{"VpcEndpointId": "vpce-2", "ServiceName": "svc2", "VpcEndpointType": "Interface", "Tags": []}]},
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = VPCEndpointsCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 2

    @patch.object(VPCEndpointsCollector, "_create_client")
    def test_collect_generates_config_hash(self, mock_create_client, mock_session):
        """Test that config hash is generated."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{
            "VpcEndpoints": [{
                "VpcEndpointId": "vpce-123",
                "ServiceName": "com.amazonaws.s3",
                "VpcEndpointType": "Gateway",
                "Tags": [],
            }]
        }]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = VPCEndpointsCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].config_hash is not None
        assert len(resources[0].config_hash) > 0

    @patch.object(VPCEndpointsCollector, "_create_client")
    def test_collect_endpoint_without_service_name(self, mock_create_client, mock_session):
        """Test collecting endpoint with missing service name."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{
            "VpcEndpoints": [{
                "VpcEndpointId": "vpce-123",
                # Missing ServiceName
                "VpcEndpointType": "Gateway",
                "Tags": [],
            }]
        }]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = VPCEndpointsCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert "unknown" in resources[0].name
