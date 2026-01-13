"""Tests for EventBridge resource collector."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.eventbridge import EventBridgeCollector


@pytest.fixture
def mock_session():
    """Create a mock boto3 session."""
    session = MagicMock()
    session.profile_name = "default"
    return session


class TestEventBridgeCollectorProperties:
    """Tests for EventBridgeCollector properties."""

    def test_service_name(self, mock_session):
        """Test service_name property returns eventbridge."""
        collector = EventBridgeCollector(session=mock_session, region="us-east-1")
        assert collector.service_name == "eventbridge"


class TestEventBridgeCollectorCollect:
    """Tests for EventBridgeCollector.collect method."""

    @patch.object(EventBridgeCollector, "_create_client")
    def test_collect_no_resources(self, mock_create_client, mock_session):
        """Test collecting when no eventbridge resources exist."""
        mock_client = MagicMock()

        mock_bus_paginator = MagicMock()
        mock_bus_paginator.paginate.return_value = [{"EventBuses": []}]

        mock_rules_paginator = MagicMock()
        mock_rules_paginator.paginate.return_value = [{"Rules": []}]

        def get_paginator_side_effect(op):
            if op == "list_event_buses":
                return mock_bus_paginator
            elif op == "list_rules":
                return mock_rules_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_create_client.return_value = mock_client

        collector = EventBridgeCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert resources == []

    @patch.object(EventBridgeCollector, "_create_client")
    def test_collect_single_event_bus(self, mock_create_client, mock_session):
        """Test collecting a single event bus."""
        mock_client = MagicMock()

        created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_bus_paginator = MagicMock()
        mock_bus_paginator.paginate.return_value = [{
            "EventBuses": [{
                "Name": "my-custom-bus",
                "Arn": "arn:aws:events:us-east-1:123456789012:event-bus/my-custom-bus",
                "CreationTime": created_at,
            }]
        }]

        mock_rules_paginator = MagicMock()
        mock_rules_paginator.paginate.return_value = [{"Rules": []}]

        def get_paginator_side_effect(op):
            if op == "list_event_buses":
                return mock_bus_paginator
            elif op == "list_rules":
                return mock_rules_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.list_tags_for_resource.return_value = {
            "Tags": [{"Key": "Environment", "Value": "test"}]
        }
        mock_create_client.return_value = mock_client

        collector = EventBridgeCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "my-custom-bus"
        assert resources[0].resource_type == "AWS::Events::EventBus"
        assert resources[0].tags == {"Environment": "test"}
        assert resources[0].created_at == created_at

    @patch.object(EventBridgeCollector, "_create_client")
    def test_collect_single_rule(self, mock_create_client, mock_session):
        """Test collecting a single event rule."""
        mock_client = MagicMock()

        mock_bus_paginator = MagicMock()
        mock_bus_paginator.paginate.return_value = [{"EventBuses": []}]

        mock_rules_paginator = MagicMock()
        mock_rules_paginator.paginate.return_value = [{
            "Rules": [{
                "Name": "my-rule",
                "Arn": "arn:aws:events:us-east-1:123456789012:rule/my-rule",
            }]
        }]

        def get_paginator_side_effect(op):
            if op == "list_event_buses":
                return mock_bus_paginator
            elif op == "list_rules":
                return mock_rules_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.list_tags_for_resource.return_value = {"Tags": []}
        mock_client.describe_rule.return_value = {
            "Name": "my-rule",
            "State": "ENABLED",
        }
        mock_create_client.return_value = mock_client

        collector = EventBridgeCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "my-rule"
        assert resources[0].resource_type == "AWS::Events::Rule"

    @patch.object(EventBridgeCollector, "_create_client")
    def test_collect_buses_and_rules(self, mock_create_client, mock_session):
        """Test collecting both event buses and rules."""
        mock_client = MagicMock()

        mock_bus_paginator = MagicMock()
        mock_bus_paginator.paginate.return_value = [{
            "EventBuses": [{
                "Name": "my-bus",
                "Arn": "arn:aws:events:us-east-1:123456789012:event-bus/my-bus",
            }]
        }]

        mock_rules_paginator = MagicMock()
        mock_rules_paginator.paginate.return_value = [{
            "Rules": [{
                "Name": "my-rule",
                "Arn": "arn:aws:events:us-east-1:123456789012:rule/my-rule",
            }]
        }]

        def get_paginator_side_effect(op):
            if op == "list_event_buses":
                return mock_bus_paginator
            elif op == "list_rules":
                return mock_rules_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.list_tags_for_resource.return_value = {"Tags": []}
        mock_client.describe_rule.return_value = {}
        mock_create_client.return_value = mock_client

        collector = EventBridgeCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 3  # 1 bus + 2 rules (default bus + my-bus)
        resource_types = [r.resource_type for r in resources]
        assert "AWS::Events::EventBus" in resource_types
        assert "AWS::Events::Rule" in resource_types

    @patch.object(EventBridgeCollector, "_create_client")
    def test_collect_handles_bus_tags_error(self, mock_create_client, mock_session):
        """Test collecting continues when bus tags fail."""
        mock_client = MagicMock()

        mock_bus_paginator = MagicMock()
        mock_bus_paginator.paginate.return_value = [{
            "EventBuses": [{
                "Name": "my-bus",
                "Arn": "arn:aws:events:us-east-1:123456789012:event-bus/my-bus",
            }]
        }]

        mock_rules_paginator = MagicMock()
        mock_rules_paginator.paginate.return_value = [{"Rules": []}]

        def get_paginator_side_effect(op):
            if op == "list_event_buses":
                return mock_bus_paginator
            elif op == "list_rules":
                return mock_rules_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.list_tags_for_resource.side_effect = Exception("Access denied")
        mock_create_client.return_value = mock_client

        collector = EventBridgeCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].tags == {}

    @patch.object(EventBridgeCollector, "_create_client")
    def test_collect_handles_list_buses_error(self, mock_create_client, mock_session):
        """Test collecting handles list_event_buses error."""
        mock_client = MagicMock()

        mock_bus_paginator = MagicMock()
        mock_bus_paginator.paginate.side_effect = Exception("Service unavailable")

        mock_rules_paginator = MagicMock()
        mock_rules_paginator.paginate.return_value = [{"Rules": []}]

        def get_paginator_side_effect(op):
            if op == "list_event_buses":
                return mock_bus_paginator
            elif op == "list_rules":
                return mock_rules_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_create_client.return_value = mock_client

        collector = EventBridgeCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still work (default bus rules)
        assert resources == []

    @patch.object(EventBridgeCollector, "_create_client")
    def test_collect_handles_describe_rule_error(self, mock_create_client, mock_session):
        """Test collecting continues when describe_rule fails."""
        mock_client = MagicMock()

        mock_bus_paginator = MagicMock()
        mock_bus_paginator.paginate.return_value = [{"EventBuses": []}]

        mock_rules_paginator = MagicMock()
        mock_rules_paginator.paginate.return_value = [{
            "Rules": [{
                "Name": "my-rule",
                "Arn": "arn:aws:events:us-east-1:123456789012:rule/my-rule",
            }]
        }]

        def get_paginator_side_effect(op):
            if op == "list_event_buses":
                return mock_bus_paginator
            elif op == "list_rules":
                return mock_rules_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.list_tags_for_resource.return_value = {"Tags": []}
        mock_client.describe_rule.side_effect = Exception("Access denied")
        mock_create_client.return_value = mock_client

        collector = EventBridgeCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still get the rule with basic info
        assert len(resources) == 1

    @patch.object(EventBridgeCollector, "_create_client")
    def test_collect_handles_rule_tags_error(self, mock_create_client, mock_session):
        """Test collecting continues when rule tags fail."""
        mock_client = MagicMock()

        mock_bus_paginator = MagicMock()
        mock_bus_paginator.paginate.return_value = [{"EventBuses": []}]

        mock_rules_paginator = MagicMock()
        mock_rules_paginator.paginate.return_value = [{
            "Rules": [{
                "Name": "my-rule",
                "Arn": "arn:aws:events:us-east-1:123456789012:rule/my-rule",
            }]
        }]

        def get_paginator_side_effect(op):
            if op == "list_event_buses":
                return mock_bus_paginator
            elif op == "list_rules":
                return mock_rules_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.list_tags_for_resource.side_effect = Exception("Access denied")
        mock_client.describe_rule.return_value = {}
        mock_create_client.return_value = mock_client

        collector = EventBridgeCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].tags == {}

    @patch.object(EventBridgeCollector, "_create_client")
    def test_collect_rules_from_custom_bus(self, mock_create_client, mock_session):
        """Test collecting rules from custom event bus."""
        mock_client = MagicMock()

        mock_bus_paginator = MagicMock()
        mock_bus_paginator.paginate.return_value = [{
            "EventBuses": [{
                "Name": "custom-bus",
                "Arn": "arn:aws:events:us-east-1:123456789012:event-bus/custom-bus",
            }]
        }]

        call_count = [0]
        mock_rules_paginator = MagicMock()

        def paginate_rules(**kwargs):
            call_count[0] += 1
            if kwargs.get("EventBusName") == "default":
                return [{"Rules": []}]
            elif kwargs.get("EventBusName") == "custom-bus":
                return [{
                    "Rules": [{
                        "Name": "custom-rule",
                        "Arn": "arn:aws:events:us-east-1:123456789012:rule/custom-bus/custom-rule",
                    }]
                }]
            return [{"Rules": []}]

        mock_rules_paginator.paginate = paginate_rules

        def get_paginator_side_effect(op):
            if op == "list_event_buses":
                return mock_bus_paginator
            elif op == "list_rules":
                return mock_rules_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.list_tags_for_resource.return_value = {"Tags": []}
        mock_client.describe_rule.return_value = {}
        mock_create_client.return_value = mock_client

        collector = EventBridgeCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # 1 bus + 1 rule from custom bus
        assert len(resources) == 2
        rule_resource = [r for r in resources if r.resource_type == "AWS::Events::Rule"][0]
        assert rule_resource.name == "custom-rule"

    @patch.object(EventBridgeCollector, "_create_client")
    def test_collect_rules_with_tags(self, mock_create_client, mock_session):
        """Test collecting rules with tags to cover tag extraction loop."""
        mock_client = MagicMock()

        mock_bus_paginator = MagicMock()
        mock_bus_paginator.paginate.return_value = [{"EventBuses": []}]

        mock_rules_paginator = MagicMock()
        mock_rules_paginator.paginate.return_value = [{
            "Rules": [{
                "Name": "tagged-rule",
                "Arn": "arn:aws:events:us-east-1:123456789012:rule/tagged-rule",
            }]
        }]

        def get_paginator_side_effect(op):
            if op == "list_event_buses":
                return mock_bus_paginator
            elif op == "list_rules":
                return mock_rules_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.list_tags_for_resource.return_value = {
            "Tags": [
                {"Key": "Environment", "Value": "production"},
                {"Key": "Team", "Value": "backend"},
            ]
        }
        mock_client.describe_rule.return_value = {"Name": "tagged-rule"}
        mock_create_client.return_value = mock_client

        collector = EventBridgeCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "tagged-rule"
        assert resources[0].tags == {"Environment": "production", "Team": "backend"}

    @patch.object(EventBridgeCollector, "_create_client")
    def test_collect_handles_rules_pagination_error_for_bus(self, mock_create_client, mock_session):
        """Test collecting continues when list_rules fails for a specific bus."""
        mock_client = MagicMock()

        mock_bus_paginator = MagicMock()
        mock_bus_paginator.paginate.return_value = [{
            "EventBuses": [{
                "Name": "error-bus",
                "Arn": "arn:aws:events:us-east-1:123456789012:event-bus/error-bus",
            }]
        }]

        def paginate_rules(**kwargs):
            if kwargs.get("EventBusName") == "error-bus":
                raise Exception("Access denied")
            return [{"Rules": []}]

        mock_rules_paginator = MagicMock()
        mock_rules_paginator.paginate = paginate_rules

        def get_paginator_side_effect(op):
            if op == "list_event_buses":
                return mock_bus_paginator
            elif op == "list_rules":
                return mock_rules_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.list_tags_for_resource.return_value = {"Tags": []}
        mock_create_client.return_value = mock_client

        collector = EventBridgeCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still get the bus, but no rules from the error bus
        bus_resources = [r for r in resources if r.resource_type == "AWS::Events::EventBus"]
        assert len(bus_resources) == 1

    @patch.object(EventBridgeCollector, "_create_client")
    def test_collect_rules_handles_top_level_error(self, mock_create_client, mock_session):
        """Test collecting rules handles errors at top level."""
        mock_client = MagicMock()

        mock_bus_paginator = MagicMock()
        mock_bus_paginator.paginate.return_value = [{"EventBuses": []}]

        # Make the first call work (for event buses listing in rules collection)
        # but second call (for list_rules) should fail
        call_count = [0]

        def get_paginator_side_effect(op):
            call_count[0] += 1
            if op == "list_event_buses":
                return mock_bus_paginator
            elif op == "list_rules":
                raise Exception("Critical error in list_rules")
            return mock_bus_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.list_tags_for_resource.return_value = {"Tags": []}
        mock_create_client.return_value = mock_client

        collector = EventBridgeCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should return empty list since rules collection failed
        assert resources == []
