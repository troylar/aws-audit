"""Tests for CloudWatch resource collector."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.cloudwatch import CloudWatchCollector


@pytest.fixture
def mock_session():
    """Create a mock boto3 session."""
    session = MagicMock()
    session.profile_name = "default"
    return session


class TestCloudWatchCollectorProperties:
    """Tests for CloudWatchCollector properties."""

    def test_service_name(self, mock_session):
        """Test service_name property returns cloudwatch."""
        collector = CloudWatchCollector(session=mock_session, region="us-east-1")
        assert collector.service_name == "cloudwatch"


class TestCloudWatchCollectorCollect:
    """Tests for CloudWatchCollector.collect method."""

    @patch.object(CloudWatchCollector, "_get_account_id")
    @patch.object(CloudWatchCollector, "_create_client")
    def test_collect_no_resources(self, mock_create_client, mock_get_account_id, mock_session):
        """Test collecting when no cloudwatch resources exist."""
        mock_get_account_id.return_value = "123456789012"

        mock_cw_client = MagicMock()
        mock_logs_client = MagicMock()

        mock_cw_paginator = MagicMock()
        mock_cw_paginator.paginate.return_value = [{"MetricAlarms": [], "CompositeAlarms": []}]
        mock_cw_client.get_paginator.return_value = mock_cw_paginator

        mock_logs_paginator = MagicMock()
        mock_logs_paginator.paginate.return_value = [{"logGroups": []}]
        mock_logs_client.get_paginator.return_value = mock_logs_paginator

        def create_client_side_effect(service=None):
            if service == "logs":
                return mock_logs_client
            return mock_cw_client

        mock_create_client.side_effect = create_client_side_effect

        collector = CloudWatchCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert resources == []

    @patch.object(CloudWatchCollector, "_get_account_id")
    @patch.object(CloudWatchCollector, "_create_client")
    def test_collect_single_alarm(self, mock_create_client, mock_get_account_id, mock_session):
        """Test collecting a single CloudWatch alarm."""
        mock_get_account_id.return_value = "123456789012"

        mock_cw_client = MagicMock()
        mock_logs_client = MagicMock()

        updated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
        mock_cw_paginator = MagicMock()
        mock_cw_paginator.paginate.return_value = [
            {
                "MetricAlarms": [
                    {
                        "AlarmName": "high-cpu-alarm",
                        "AlarmArn": "arn:aws:cloudwatch:us-east-1:123456789012:alarm:high-cpu-alarm",
                        "AlarmConfigurationUpdatedTimestamp": updated_at,
                        "MetricName": "CPUUtilization",
                    }
                ],
                "CompositeAlarms": [],
            }
        ]
        mock_cw_client.get_paginator.return_value = mock_cw_paginator

        mock_logs_paginator = MagicMock()
        mock_logs_paginator.paginate.return_value = [{"logGroups": []}]
        mock_logs_client.get_paginator.return_value = mock_logs_paginator

        def create_client_side_effect(service=None):
            if service == "logs":
                return mock_logs_client
            return mock_cw_client

        mock_create_client.side_effect = create_client_side_effect

        collector = CloudWatchCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "high-cpu-alarm"
        assert resources[0].resource_type == "AWS::CloudWatch::Alarm"
        assert resources[0].region == "us-east-1"
        assert resources[0].created_at == updated_at

    @patch.object(CloudWatchCollector, "_get_account_id")
    @patch.object(CloudWatchCollector, "_create_client")
    def test_collect_single_log_group(self, mock_create_client, mock_get_account_id, mock_session):
        """Test collecting a single CloudWatch log group."""
        mock_get_account_id.return_value = "123456789012"

        mock_cw_client = MagicMock()
        mock_logs_client = MagicMock()

        mock_cw_paginator = MagicMock()
        mock_cw_paginator.paginate.return_value = [{"MetricAlarms": [], "CompositeAlarms": []}]
        mock_cw_client.get_paginator.return_value = mock_cw_paginator

        mock_logs_paginator = MagicMock()
        mock_logs_paginator.paginate.return_value = [
            {
                "logGroups": [
                    {
                        "logGroupName": "/aws/lambda/my-function",
                        "arn": "arn:aws:logs:us-east-1:123456789012:log-group:/aws/lambda/my-function",
                    }
                ]
            }
        ]
        mock_logs_client.get_paginator.return_value = mock_logs_paginator
        mock_logs_client.list_tags_log_group.return_value = {"tags": {"Environment": "test"}}

        def create_client_side_effect(service=None):
            if service == "logs":
                return mock_logs_client
            return mock_cw_client

        mock_create_client.side_effect = create_client_side_effect

        collector = CloudWatchCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "/aws/lambda/my-function"
        assert resources[0].resource_type == "AWS::Logs::LogGroup"
        assert resources[0].tags == {"Environment": "test"}

    @patch.object(CloudWatchCollector, "_get_account_id")
    @patch.object(CloudWatchCollector, "_create_client")
    def test_collect_alarms_and_log_groups(self, mock_create_client, mock_get_account_id, mock_session):
        """Test collecting both alarms and log groups."""
        mock_get_account_id.return_value = "123456789012"

        mock_cw_client = MagicMock()
        mock_logs_client = MagicMock()

        mock_cw_paginator = MagicMock()
        mock_cw_paginator.paginate.return_value = [
            {
                "MetricAlarms": [
                    {
                        "AlarmName": "my-alarm",
                        "AlarmArn": "arn:aws:cloudwatch:us-east-1:123456789012:alarm:my-alarm",
                    }
                ],
                "CompositeAlarms": [],
            }
        ]
        mock_cw_client.get_paginator.return_value = mock_cw_paginator

        mock_logs_paginator = MagicMock()
        mock_logs_paginator.paginate.return_value = [
            {
                "logGroups": [
                    {
                        "logGroupName": "/my/log/group",
                        "arn": "arn:aws:logs:us-east-1:123456789012:log-group:/my/log/group",
                    }
                ]
            }
        ]
        mock_logs_client.get_paginator.return_value = mock_logs_paginator
        mock_logs_client.list_tags_log_group.return_value = {"tags": {}}

        def create_client_side_effect(service=None):
            if service == "logs":
                return mock_logs_client
            return mock_cw_client

        mock_create_client.side_effect = create_client_side_effect

        collector = CloudWatchCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 2
        resource_types = [r.resource_type for r in resources]
        assert "AWS::CloudWatch::Alarm" in resource_types
        assert "AWS::Logs::LogGroup" in resource_types

    @patch.object(CloudWatchCollector, "_get_account_id")
    @patch.object(CloudWatchCollector, "_create_client")
    def test_collect_handles_alarm_error(self, mock_create_client, mock_get_account_id, mock_session):
        """Test collecting handles describe_alarms error."""
        mock_get_account_id.return_value = "123456789012"

        mock_cw_client = MagicMock()
        mock_logs_client = MagicMock()

        mock_cw_paginator = MagicMock()
        mock_cw_paginator.paginate.side_effect = Exception("Access denied")
        mock_cw_client.get_paginator.return_value = mock_cw_paginator

        mock_logs_paginator = MagicMock()
        mock_logs_paginator.paginate.return_value = [{"logGroups": []}]
        mock_logs_client.get_paginator.return_value = mock_logs_paginator

        def create_client_side_effect(service=None):
            if service == "logs":
                return mock_logs_client
            return mock_cw_client

        mock_create_client.side_effect = create_client_side_effect

        collector = CloudWatchCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still work (collect log groups)
        assert resources == []

    @patch.object(CloudWatchCollector, "_get_account_id")
    @patch.object(CloudWatchCollector, "_create_client")
    def test_collect_handles_log_groups_error(self, mock_create_client, mock_get_account_id, mock_session):
        """Test collecting handles describe_log_groups error."""
        mock_get_account_id.return_value = "123456789012"

        mock_cw_client = MagicMock()
        mock_logs_client = MagicMock()

        mock_cw_paginator = MagicMock()
        mock_cw_paginator.paginate.return_value = [{"MetricAlarms": [], "CompositeAlarms": []}]
        mock_cw_client.get_paginator.return_value = mock_cw_paginator

        mock_logs_paginator = MagicMock()
        mock_logs_paginator.paginate.side_effect = Exception("Access denied")
        mock_logs_client.get_paginator.return_value = mock_logs_paginator

        def create_client_side_effect(service=None):
            if service == "logs":
                return mock_logs_client
            return mock_cw_client

        mock_create_client.side_effect = create_client_side_effect

        collector = CloudWatchCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still work (collect alarms)
        assert resources == []

    @patch.object(CloudWatchCollector, "_get_account_id")
    @patch.object(CloudWatchCollector, "_create_client")
    def test_collect_handles_log_group_tags_error(self, mock_create_client, mock_get_account_id, mock_session):
        """Test collecting continues when list_tags_log_group fails."""
        mock_get_account_id.return_value = "123456789012"

        mock_cw_client = MagicMock()
        mock_logs_client = MagicMock()

        mock_cw_paginator = MagicMock()
        mock_cw_paginator.paginate.return_value = [{"MetricAlarms": [], "CompositeAlarms": []}]
        mock_cw_client.get_paginator.return_value = mock_cw_paginator

        mock_logs_paginator = MagicMock()
        mock_logs_paginator.paginate.return_value = [
            {
                "logGroups": [
                    {
                        "logGroupName": "/my/log/group",
                        "arn": "arn:aws:logs:us-east-1:123456789012:log-group:/my/log/group",
                    }
                ]
            }
        ]
        mock_logs_client.get_paginator.return_value = mock_logs_paginator
        mock_logs_client.list_tags_log_group.side_effect = Exception("Access denied")

        def create_client_side_effect(service=None):
            if service == "logs":
                return mock_logs_client
            return mock_cw_client

        mock_create_client.side_effect = create_client_side_effect

        collector = CloudWatchCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still get the log group without tags
        assert len(resources) == 1
        assert resources[0].tags == {}

    @patch.object(CloudWatchCollector, "_get_account_id")
    @patch.object(CloudWatchCollector, "_create_client")
    def test_collect_log_group_without_arn(self, mock_create_client, mock_get_account_id, mock_session):
        """Test collecting log group without ARN in response."""
        mock_get_account_id.return_value = "123456789012"

        mock_cw_client = MagicMock()
        mock_logs_client = MagicMock()

        mock_cw_paginator = MagicMock()
        mock_cw_paginator.paginate.return_value = [{"MetricAlarms": [], "CompositeAlarms": []}]
        mock_cw_client.get_paginator.return_value = mock_cw_paginator

        mock_logs_paginator = MagicMock()
        mock_logs_paginator.paginate.return_value = [
            {
                "logGroups": [
                    {
                        "logGroupName": "/my/log/group",
                        # No ARN field
                    }
                ]
            }
        ]
        mock_logs_client.get_paginator.return_value = mock_logs_paginator
        mock_logs_client.list_tags_log_group.return_value = {"tags": {}}

        def create_client_side_effect(service=None):
            if service == "logs":
                return mock_logs_client
            return mock_cw_client

        mock_create_client.side_effect = create_client_side_effect

        collector = CloudWatchCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        # Should generate ARN from account ID and log group name
        assert resources[0].arn == "arn:aws:logs:us-east-1:123456789012:log-group:/my/log/group"

    @patch.object(CloudWatchCollector, "_get_account_id")
    @patch.object(CloudWatchCollector, "_create_client")
    def test_collect_generates_config_hash(self, mock_create_client, mock_get_account_id, mock_session):
        """Test that config hash is generated."""
        mock_get_account_id.return_value = "123456789012"

        mock_cw_client = MagicMock()
        mock_logs_client = MagicMock()

        mock_cw_paginator = MagicMock()
        mock_cw_paginator.paginate.return_value = [
            {
                "MetricAlarms": [
                    {
                        "AlarmName": "my-alarm",
                        "AlarmArn": "arn:aws:cloudwatch:us-east-1:123456789012:alarm:my-alarm",
                    }
                ],
                "CompositeAlarms": [],
            }
        ]
        mock_cw_client.get_paginator.return_value = mock_cw_paginator

        mock_logs_paginator = MagicMock()
        mock_logs_paginator.paginate.return_value = [{"logGroups": []}]
        mock_logs_client.get_paginator.return_value = mock_logs_paginator

        def create_client_side_effect(service=None):
            if service == "logs":
                return mock_logs_client
            return mock_cw_client

        mock_create_client.side_effect = create_client_side_effect

        collector = CloudWatchCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].config_hash is not None
        assert len(resources[0].config_hash) > 0
