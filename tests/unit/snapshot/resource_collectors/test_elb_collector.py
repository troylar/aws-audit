"""Tests for ELB resource collector."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.elb import ELBCollector


@pytest.fixture
def mock_session():
    """Create a mock boto3 session."""
    session = MagicMock()
    session.profile_name = "default"
    return session


class TestELBCollectorProperties:
    """Tests for ELBCollector properties."""

    def test_service_name(self, mock_session):
        """Test service_name property returns elb."""
        collector = ELBCollector(session=mock_session, region="us-east-1")
        assert collector.service_name == "elb"


class TestELBCollectorCollect:
    """Tests for ELBCollector.collect method."""

    @patch.object(ELBCollector, "_get_account_id")
    @patch.object(ELBCollector, "_create_client")
    def test_collect_no_load_balancers(self, mock_create_client, mock_get_account_id, mock_session):
        """Test collecting when no load balancers exist."""
        mock_get_account_id.return_value = "123456789012"

        mock_elbv2_client = MagicMock()
        mock_elb_client = MagicMock()

        mock_elbv2_paginator = MagicMock()
        mock_elbv2_paginator.paginate.return_value = [{"LoadBalancers": []}]
        mock_elbv2_client.get_paginator.return_value = mock_elbv2_paginator

        mock_elb_paginator = MagicMock()
        mock_elb_paginator.paginate.return_value = [{"LoadBalancerDescriptions": []}]
        mock_elb_client.get_paginator.return_value = mock_elb_paginator

        def create_client_side_effect(service=None):
            if service == "elbv2":
                return mock_elbv2_client
            elif service == "elb":
                return mock_elb_client
            return mock_elbv2_client

        mock_create_client.side_effect = create_client_side_effect

        collector = ELBCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert resources == []

    @patch.object(ELBCollector, "_get_account_id")
    @patch.object(ELBCollector, "_create_client")
    def test_collect_single_alb(self, mock_create_client, mock_get_account_id, mock_session):
        """Test collecting a single Application Load Balancer."""
        mock_get_account_id.return_value = "123456789012"

        mock_elbv2_client = MagicMock()
        mock_elb_client = MagicMock()

        created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_elbv2_paginator = MagicMock()
        mock_elbv2_paginator.paginate.return_value = [{
            "LoadBalancers": [{
                "LoadBalancerArn": "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/my-alb/12345",
                "LoadBalancerName": "my-alb",
                "Type": "application",
                "CreatedTime": created_at,
            }]
        }]
        mock_elbv2_client.get_paginator.return_value = mock_elbv2_paginator
        mock_elbv2_client.describe_tags.return_value = {
            "TagDescriptions": [{"Tags": [{"Key": "Environment", "Value": "test"}]}]
        }

        mock_elb_paginator = MagicMock()
        mock_elb_paginator.paginate.return_value = [{"LoadBalancerDescriptions": []}]
        mock_elb_client.get_paginator.return_value = mock_elb_paginator

        def create_client_side_effect(service=None):
            if service == "elbv2":
                return mock_elbv2_client
            elif service == "elb":
                return mock_elb_client
            return mock_elbv2_client

        mock_create_client.side_effect = create_client_side_effect

        collector = ELBCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "my-alb"
        assert resources[0].resource_type == "AWS::ElasticLoadBalancingV2::LoadBalancer::Application"
        assert resources[0].tags == {"Environment": "test"}
        assert resources[0].created_at == created_at

    @patch.object(ELBCollector, "_get_account_id")
    @patch.object(ELBCollector, "_create_client")
    def test_collect_single_nlb(self, mock_create_client, mock_get_account_id, mock_session):
        """Test collecting a single Network Load Balancer."""
        mock_get_account_id.return_value = "123456789012"

        mock_elbv2_client = MagicMock()
        mock_elb_client = MagicMock()

        mock_elbv2_paginator = MagicMock()
        mock_elbv2_paginator.paginate.return_value = [{
            "LoadBalancers": [{
                "LoadBalancerArn": "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/net/my-nlb/12345",
                "LoadBalancerName": "my-nlb",
                "Type": "network",
            }]
        }]
        mock_elbv2_client.get_paginator.return_value = mock_elbv2_paginator
        mock_elbv2_client.describe_tags.return_value = {"TagDescriptions": []}

        mock_elb_paginator = MagicMock()
        mock_elb_paginator.paginate.return_value = [{"LoadBalancerDescriptions": []}]
        mock_elb_client.get_paginator.return_value = mock_elb_paginator

        def create_client_side_effect(service=None):
            if service == "elbv2":
                return mock_elbv2_client
            elif service == "elb":
                return mock_elb_client
            return mock_elbv2_client

        mock_create_client.side_effect = create_client_side_effect

        collector = ELBCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].resource_type == "AWS::ElasticLoadBalancingV2::LoadBalancer::Network"

    @patch.object(ELBCollector, "_get_account_id")
    @patch.object(ELBCollector, "_create_client")
    def test_collect_single_gwlb(self, mock_create_client, mock_get_account_id, mock_session):
        """Test collecting a single Gateway Load Balancer."""
        mock_get_account_id.return_value = "123456789012"

        mock_elbv2_client = MagicMock()
        mock_elb_client = MagicMock()

        mock_elbv2_paginator = MagicMock()
        mock_elbv2_paginator.paginate.return_value = [{
            "LoadBalancers": [{
                "LoadBalancerArn": "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/gwy/my-gwlb/12345",
                "LoadBalancerName": "my-gwlb",
                "Type": "gateway",
            }]
        }]
        mock_elbv2_client.get_paginator.return_value = mock_elbv2_paginator
        mock_elbv2_client.describe_tags.return_value = {"TagDescriptions": []}

        mock_elb_paginator = MagicMock()
        mock_elb_paginator.paginate.return_value = [{"LoadBalancerDescriptions": []}]
        mock_elb_client.get_paginator.return_value = mock_elb_paginator

        def create_client_side_effect(service=None):
            if service == "elbv2":
                return mock_elbv2_client
            elif service == "elb":
                return mock_elb_client
            return mock_elbv2_client

        mock_create_client.side_effect = create_client_side_effect

        collector = ELBCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].resource_type == "AWS::ElasticLoadBalancingV2::LoadBalancer::Gateway"

    @patch.object(ELBCollector, "_get_account_id")
    @patch.object(ELBCollector, "_create_client")
    def test_collect_single_classic_elb(self, mock_create_client, mock_get_account_id, mock_session):
        """Test collecting a single classic load balancer."""
        mock_get_account_id.return_value = "123456789012"

        mock_elbv2_client = MagicMock()
        mock_elb_client = MagicMock()

        mock_elbv2_paginator = MagicMock()
        mock_elbv2_paginator.paginate.return_value = [{"LoadBalancers": []}]
        mock_elbv2_client.get_paginator.return_value = mock_elbv2_paginator

        created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_elb_paginator = MagicMock()
        mock_elb_paginator.paginate.return_value = [{
            "LoadBalancerDescriptions": [{
                "LoadBalancerName": "my-classic-elb",
                "CreatedTime": created_at,
            }]
        }]
        mock_elb_client.get_paginator.return_value = mock_elb_paginator
        mock_elb_client.describe_tags.return_value = {
            "TagDescriptions": [{"Tags": [{"Key": "Environment", "Value": "prod"}]}]
        }

        def create_client_side_effect(service=None):
            if service == "elbv2":
                return mock_elbv2_client
            elif service == "elb":
                return mock_elb_client
            return mock_elbv2_client

        mock_create_client.side_effect = create_client_side_effect

        collector = ELBCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "my-classic-elb"
        assert resources[0].resource_type == "AWS::ElasticLoadBalancing::LoadBalancer"
        assert resources[0].tags == {"Environment": "prod"}
        assert "my-classic-elb" in resources[0].arn

    @patch.object(ELBCollector, "_get_account_id")
    @patch.object(ELBCollector, "_create_client")
    def test_collect_both_v2_and_classic(self, mock_create_client, mock_get_account_id, mock_session):
        """Test collecting both v2 and classic load balancers."""
        mock_get_account_id.return_value = "123456789012"

        mock_elbv2_client = MagicMock()
        mock_elb_client = MagicMock()

        mock_elbv2_paginator = MagicMock()
        mock_elbv2_paginator.paginate.return_value = [{
            "LoadBalancers": [{
                "LoadBalancerArn": "arn:1",
                "LoadBalancerName": "my-alb",
                "Type": "application",
            }]
        }]
        mock_elbv2_client.get_paginator.return_value = mock_elbv2_paginator
        mock_elbv2_client.describe_tags.return_value = {"TagDescriptions": []}

        mock_elb_paginator = MagicMock()
        mock_elb_paginator.paginate.return_value = [{
            "LoadBalancerDescriptions": [{
                "LoadBalancerName": "my-classic",
            }]
        }]
        mock_elb_client.get_paginator.return_value = mock_elb_paginator
        mock_elb_client.describe_tags.return_value = {"TagDescriptions": []}

        def create_client_side_effect(service=None):
            if service == "elbv2":
                return mock_elbv2_client
            elif service == "elb":
                return mock_elb_client
            return mock_elbv2_client

        mock_create_client.side_effect = create_client_side_effect

        collector = ELBCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 2
        names = [r.name for r in resources]
        assert "my-alb" in names
        assert "my-classic" in names

    @patch.object(ELBCollector, "_get_account_id")
    @patch.object(ELBCollector, "_create_client")
    def test_collect_handles_v2_tags_error(self, mock_create_client, mock_get_account_id, mock_session):
        """Test collecting continues when v2 describe_tags fails."""
        mock_get_account_id.return_value = "123456789012"

        mock_elbv2_client = MagicMock()
        mock_elb_client = MagicMock()

        mock_elbv2_paginator = MagicMock()
        mock_elbv2_paginator.paginate.return_value = [{
            "LoadBalancers": [{
                "LoadBalancerArn": "arn:1",
                "LoadBalancerName": "my-alb",
                "Type": "application",
            }]
        }]
        mock_elbv2_client.get_paginator.return_value = mock_elbv2_paginator
        mock_elbv2_client.describe_tags.side_effect = Exception("Access denied")

        mock_elb_paginator = MagicMock()
        mock_elb_paginator.paginate.return_value = [{"LoadBalancerDescriptions": []}]
        mock_elb_client.get_paginator.return_value = mock_elb_paginator

        def create_client_side_effect(service=None):
            if service == "elbv2":
                return mock_elbv2_client
            elif service == "elb":
                return mock_elb_client
            return mock_elbv2_client

        mock_create_client.side_effect = create_client_side_effect

        collector = ELBCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].tags == {}

    @patch.object(ELBCollector, "_get_account_id")
    @patch.object(ELBCollector, "_create_client")
    def test_collect_handles_classic_tags_error(self, mock_create_client, mock_get_account_id, mock_session):
        """Test collecting continues when classic describe_tags fails."""
        mock_get_account_id.return_value = "123456789012"

        mock_elbv2_client = MagicMock()
        mock_elb_client = MagicMock()

        mock_elbv2_paginator = MagicMock()
        mock_elbv2_paginator.paginate.return_value = [{"LoadBalancers": []}]
        mock_elbv2_client.get_paginator.return_value = mock_elbv2_paginator

        mock_elb_paginator = MagicMock()
        mock_elb_paginator.paginate.return_value = [{
            "LoadBalancerDescriptions": [{"LoadBalancerName": "my-classic"}]
        }]
        mock_elb_client.get_paginator.return_value = mock_elb_paginator
        mock_elb_client.describe_tags.side_effect = Exception("Access denied")

        def create_client_side_effect(service=None):
            if service == "elbv2":
                return mock_elbv2_client
            elif service == "elb":
                return mock_elb_client
            return mock_elbv2_client

        mock_create_client.side_effect = create_client_side_effect

        collector = ELBCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].tags == {}

    @patch.object(ELBCollector, "_get_account_id")
    @patch.object(ELBCollector, "_create_client")
    def test_collect_handles_v2_error(self, mock_create_client, mock_get_account_id, mock_session):
        """Test collecting handles v2 describe_load_balancers error."""
        mock_get_account_id.return_value = "123456789012"

        mock_elbv2_client = MagicMock()
        mock_elb_client = MagicMock()

        mock_elbv2_paginator = MagicMock()
        mock_elbv2_paginator.paginate.side_effect = Exception("Service unavailable")
        mock_elbv2_client.get_paginator.return_value = mock_elbv2_paginator

        mock_elb_paginator = MagicMock()
        mock_elb_paginator.paginate.return_value = [{"LoadBalancerDescriptions": []}]
        mock_elb_client.get_paginator.return_value = mock_elb_paginator

        def create_client_side_effect(service=None):
            if service == "elbv2":
                return mock_elbv2_client
            elif service == "elb":
                return mock_elb_client
            return mock_elbv2_client

        mock_create_client.side_effect = create_client_side_effect

        collector = ELBCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still work, just no v2 load balancers
        assert resources == []

    @patch.object(ELBCollector, "_get_account_id")
    @patch.object(ELBCollector, "_create_client")
    def test_collect_handles_classic_error(self, mock_create_client, mock_get_account_id, mock_session):
        """Test collecting handles classic describe_load_balancers error."""
        mock_get_account_id.return_value = "123456789012"

        mock_elbv2_client = MagicMock()
        mock_elb_client = MagicMock()

        mock_elbv2_paginator = MagicMock()
        mock_elbv2_paginator.paginate.return_value = [{"LoadBalancers": []}]
        mock_elbv2_client.get_paginator.return_value = mock_elbv2_paginator

        mock_elb_paginator = MagicMock()
        mock_elb_paginator.paginate.side_effect = Exception("Service unavailable")
        mock_elb_client.get_paginator.return_value = mock_elb_paginator

        def create_client_side_effect(service=None):
            if service == "elbv2":
                return mock_elbv2_client
            elif service == "elb":
                return mock_elb_client
            return mock_elbv2_client

        mock_create_client.side_effect = create_client_side_effect

        collector = ELBCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still work, just no classic load balancers
        assert resources == []

    @patch.object(ELBCollector, "_get_account_id")
    @patch.object(ELBCollector, "_create_client")
    def test_collect_unknown_lb_type(self, mock_create_client, mock_get_account_id, mock_session):
        """Test collecting a load balancer with unknown type."""
        mock_get_account_id.return_value = "123456789012"

        mock_elbv2_client = MagicMock()
        mock_elb_client = MagicMock()

        mock_elbv2_paginator = MagicMock()
        mock_elbv2_paginator.paginate.return_value = [{
            "LoadBalancers": [{
                "LoadBalancerArn": "arn:1",
                "LoadBalancerName": "my-lb",
                "Type": "unknown_type",
            }]
        }]
        mock_elbv2_client.get_paginator.return_value = mock_elbv2_paginator
        mock_elbv2_client.describe_tags.return_value = {"TagDescriptions": []}

        mock_elb_paginator = MagicMock()
        mock_elb_paginator.paginate.return_value = [{"LoadBalancerDescriptions": []}]
        mock_elb_client.get_paginator.return_value = mock_elb_paginator

        def create_client_side_effect(service=None):
            if service == "elbv2":
                return mock_elbv2_client
            elif service == "elb":
                return mock_elb_client
            return mock_elbv2_client

        mock_create_client.side_effect = create_client_side_effect

        collector = ELBCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].resource_type == "AWS::ElasticLoadBalancingV2::LoadBalancer"
