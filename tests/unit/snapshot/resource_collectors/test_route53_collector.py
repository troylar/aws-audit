"""Tests for Route53 resource collector."""

from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.route53 import Route53Collector


@pytest.fixture
def mock_session():
    """Create a mock boto3 session."""
    session = MagicMock()
    session.profile_name = "default"
    return session


class TestRoute53CollectorProperties:
    """Tests for Route53Collector properties."""

    def test_service_name(self, mock_session):
        """Test service_name property returns route53."""
        collector = Route53Collector(session=mock_session, region="us-east-1")
        assert collector.service_name == "route53"

    def test_is_global_service(self, mock_session):
        """Test is_global_service property returns True."""
        collector = Route53Collector(session=mock_session, region="us-east-1")
        assert collector.is_global_service is True


class TestRoute53CollectorCollect:
    """Tests for Route53Collector.collect method."""

    @patch.object(Route53Collector, "_create_client")
    def test_collect_no_hosted_zones(self, mock_create_client, mock_session):
        """Test collecting when no hosted zones exist."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"HostedZones": []}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = Route53Collector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert resources == []
        mock_client.get_paginator.assert_called_once_with("list_hosted_zones")

    @patch.object(Route53Collector, "_create_client")
    def test_collect_single_public_zone(self, mock_create_client, mock_session):
        """Test collecting a single public hosted zone."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "HostedZones": [
                    {
                        "Id": "/hostedzone/Z123ABC",
                        "Name": "example.com.",
                        "CallerReference": "ref-123",
                        "Config": {"PrivateZone": False},
                        "ResourceRecordSetCount": 10,
                    }
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.list_tags_for_resource.return_value = {"Tags": [{"Key": "Environment", "Value": "production"}]}
        mock_client.get_hosted_zone.return_value = {
            "HostedZone": {
                "Id": "/hostedzone/Z123ABC",
                "Name": "example.com.",
                "ResourceRecordSetCount": 10,
            }
        }
        mock_create_client.return_value = mock_client

        collector = Route53Collector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "example.com."
        assert resources[0].resource_type == "AWS::Route53::HostedZone"
        assert resources[0].region == "global"
        assert resources[0].tags == {"Environment": "production"}
        assert "Z123ABC" in resources[0].arn
        assert resources[0].created_at is None  # Route53 doesn't have creation time

    @patch.object(Route53Collector, "_create_client")
    def test_collect_private_zone(self, mock_create_client, mock_session):
        """Test collecting a private hosted zone."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "HostedZones": [
                    {
                        "Id": "/hostedzone/Z456DEF",
                        "Name": "internal.local.",
                        "Config": {"PrivateZone": True},
                    }
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.list_tags_for_resource.return_value = {"Tags": []}
        mock_client.get_hosted_zone.return_value = {
            "HostedZone": {
                "Id": "/hostedzone/Z456DEF",
                "Name": "internal.local.",
            }
        }
        mock_create_client.return_value = mock_client

        collector = Route53Collector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "internal.local."
        assert resources[0].resource_type == "AWS::Route53::HostedZone"

    @patch.object(Route53Collector, "_create_client")
    def test_collect_multiple_zones(self, mock_create_client, mock_session):
        """Test collecting multiple hosted zones."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "HostedZones": [
                    {"Id": "/hostedzone/Z1", "Name": "zone1.com."},
                    {"Id": "/hostedzone/Z2", "Name": "zone2.com."},
                    {"Id": "/hostedzone/Z3", "Name": "zone3.com."},
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.list_tags_for_resource.return_value = {"Tags": []}
        mock_client.get_hosted_zone.return_value = {"HostedZone": {}}
        mock_create_client.return_value = mock_client

        collector = Route53Collector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 3
        assert resources[0].name == "zone1.com."
        assert resources[1].name == "zone2.com."
        assert resources[2].name == "zone3.com."

    @patch.object(Route53Collector, "_create_client")
    def test_collect_with_pagination(self, mock_create_client, mock_session):
        """Test collecting with multiple pages."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"HostedZones": [{"Id": "/hostedzone/Z1", "Name": "zone1.com."}]},
            {"HostedZones": [{"Id": "/hostedzone/Z2", "Name": "zone2.com."}]},
        ]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.list_tags_for_resource.return_value = {"Tags": []}
        mock_client.get_hosted_zone.return_value = {"HostedZone": {}}
        mock_create_client.return_value = mock_client

        collector = Route53Collector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 2

    @patch.object(Route53Collector, "_create_client")
    def test_collect_handles_list_error(self, mock_create_client, mock_session):
        """Test collecting handles list_hosted_zones error."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.side_effect = Exception("Service unavailable")
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = Route53Collector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert resources == []

    @patch.object(Route53Collector, "_create_client")
    def test_collect_handles_tags_error(self, mock_create_client, mock_session):
        """Test collecting continues when list_tags_for_resource fails."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"HostedZones": [{"Id": "/hostedzone/Z123", "Name": "example.com."}]}]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.list_tags_for_resource.side_effect = Exception("Access denied")
        mock_client.get_hosted_zone.return_value = {"HostedZone": {}}
        mock_create_client.return_value = mock_client

        collector = Route53Collector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still get the zone without tags
        assert len(resources) == 1
        assert resources[0].tags == {}

    @patch.object(Route53Collector, "_create_client")
    def test_collect_handles_get_zone_error(self, mock_create_client, mock_session):
        """Test collecting continues when get_hosted_zone fails."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"HostedZones": [{"Id": "/hostedzone/Z123", "Name": "example.com."}]}]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.list_tags_for_resource.return_value = {"Tags": []}
        mock_client.get_hosted_zone.side_effect = Exception("Access denied")
        mock_create_client.return_value = mock_client

        collector = Route53Collector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still get the zone with basic info
        assert len(resources) == 1
        assert resources[0].name == "example.com."

    @patch.object(Route53Collector, "_create_client")
    def test_collect_generates_config_hash(self, mock_create_client, mock_session):
        """Test that config hash is generated."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"HostedZones": [{"Id": "/hostedzone/Z123", "Name": "example.com."}]}]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.list_tags_for_resource.return_value = {"Tags": []}
        mock_client.get_hosted_zone.return_value = {"HostedZone": {}}
        mock_create_client.return_value = mock_client

        collector = Route53Collector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].config_hash is not None
        assert len(resources[0].config_hash) > 0

    @patch.object(Route53Collector, "_create_client")
    def test_collect_extracts_zone_id_from_full_path(self, mock_create_client, mock_session):
        """Test that zone ID is correctly extracted from /hostedzone/ID format."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"HostedZones": [{"Id": "/hostedzone/ZABCDEFGH12345", "Name": "test.com."}]}
        ]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.list_tags_for_resource.return_value = {"Tags": []}
        mock_client.get_hosted_zone.return_value = {"HostedZone": {}}
        mock_create_client.return_value = mock_client

        collector = Route53Collector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        # ARN should contain extracted ID
        assert "ZABCDEFGH12345" in resources[0].arn
        # list_tags should be called with just the ID
        mock_client.list_tags_for_resource.assert_called_with(ResourceType="hostedzone", ResourceId="ZABCDEFGH12345")
