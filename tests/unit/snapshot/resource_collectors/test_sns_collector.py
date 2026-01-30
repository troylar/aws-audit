"""Tests for SNS resource collector."""

from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.sns import SNSCollector


@pytest.fixture
def mock_session():
    """Create a mock boto3 session."""
    session = MagicMock()
    session.profile_name = "default"
    return session


class TestSNSCollectorProperties:
    """Tests for SNSCollector properties."""

    def test_service_name(self, mock_session):
        """Test service_name property returns sns."""
        collector = SNSCollector(session=mock_session, region="us-east-1")
        assert collector.service_name == "sns"


class TestSNSCollectorCollect:
    """Tests for SNSCollector.collect method."""

    @patch.object(SNSCollector, "_create_client")
    def test_collect_no_topics(self, mock_create_client, mock_session):
        """Test collecting when no topics exist."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"Topics": []}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = SNSCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert resources == []
        mock_client.get_paginator.assert_called_once_with("list_topics")

    @patch.object(SNSCollector, "_create_client")
    def test_collect_single_topic(self, mock_create_client, mock_session):
        """Test collecting a single topic."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"Topics": [{"TopicArn": "arn:aws:sns:us-east-1:123456789012:test-topic"}]}
        ]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.get_topic_attributes.return_value = {
            "Attributes": {
                "TopicArn": "arn:aws:sns:us-east-1:123456789012:test-topic",
                "DisplayName": "Test Topic",
            }
        }
        mock_client.list_tags_for_resource.return_value = {"Tags": [{"Key": "Environment", "Value": "test"}]}
        mock_create_client.return_value = mock_client

        collector = SNSCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "test-topic"
        assert resources[0].resource_type == "AWS::SNS::Topic"
        assert resources[0].region == "us-east-1"
        assert resources[0].tags == {"Environment": "test"}
        assert resources[0].created_at is None  # SNS doesn't expose creation date

    @patch.object(SNSCollector, "_create_client")
    def test_collect_multiple_topics(self, mock_create_client, mock_session):
        """Test collecting multiple topics."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Topics": [
                    {"TopicArn": "arn:aws:sns:us-east-1:123456789012:topic-1"},
                    {"TopicArn": "arn:aws:sns:us-east-1:123456789012:topic-2"},
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator

        def get_topic_attrs_side_effect(**kwargs):
            return {"Attributes": {"TopicArn": kwargs["TopicArn"]}}

        mock_client.get_topic_attributes.side_effect = get_topic_attrs_side_effect
        mock_client.list_tags_for_resource.return_value = {"Tags": []}
        mock_create_client.return_value = mock_client

        collector = SNSCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 2
        assert resources[0].name == "topic-1"
        assert resources[1].name == "topic-2"

    @patch.object(SNSCollector, "_create_client")
    def test_collect_handles_attributes_error(self, mock_create_client, mock_session):
        """Test collecting continues when get_topic_attributes fails."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "Topics": [
                    {"TopicArn": "arn:aws:sns:us-east-1:123456789012:good-topic"},
                    {"TopicArn": "arn:aws:sns:us-east-1:123456789012:bad-topic"},
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator

        def get_topic_attrs_side_effect(**kwargs):
            if "bad-topic" in kwargs["TopicArn"]:
                raise Exception("Access denied")
            return {"Attributes": {"TopicArn": kwargs["TopicArn"]}}

        mock_client.get_topic_attributes.side_effect = get_topic_attrs_side_effect
        mock_client.list_tags_for_resource.return_value = {"Tags": []}
        mock_create_client.return_value = mock_client

        collector = SNSCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should only get the good topic
        assert len(resources) == 1
        assert resources[0].name == "good-topic"

    @patch.object(SNSCollector, "_create_client")
    def test_collect_handles_tags_error(self, mock_create_client, mock_session):
        """Test collecting continues when list_tags fails."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"Topics": [{"TopicArn": "arn:aws:sns:us-east-1:123456789012:test-topic"}]}
        ]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.get_topic_attributes.return_value = {
            "Attributes": {"TopicArn": "arn:aws:sns:us-east-1:123456789012:test-topic"}
        }
        mock_client.list_tags_for_resource.side_effect = Exception("Access denied")
        mock_create_client.return_value = mock_client

        collector = SNSCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still get the topic, just without tags
        assert len(resources) == 1
        assert resources[0].tags == {}

    @patch.object(SNSCollector, "_create_client")
    def test_collect_handles_list_topics_error(self, mock_create_client, mock_session):
        """Test collecting handles list_topics error."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.side_effect = Exception("Service unavailable")
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = SNSCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should return empty list on error
        assert resources == []

    @patch.object(SNSCollector, "_create_client")
    def test_collect_extracts_topic_name_from_arn(self, mock_create_client, mock_session):
        """Test that topic name is correctly extracted from ARN."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"Topics": [{"TopicArn": "arn:aws:sns:us-west-2:123456789012:my-special-topic"}]}
        ]
        mock_client.get_paginator.return_value = mock_paginator

        mock_client.get_topic_attributes.return_value = {"Attributes": {}}
        mock_client.list_tags_for_resource.return_value = {"Tags": []}
        mock_create_client.return_value = mock_client

        collector = SNSCollector(session=mock_session, region="us-west-2")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].name == "my-special-topic"
        assert resources[0].arn == "arn:aws:sns:us-west-2:123456789012:my-special-topic"

    @patch.object(SNSCollector, "_create_client")
    def test_collect_stores_raw_config(self, mock_create_client, mock_session):
        """Test that raw config (attributes) is stored."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {"Topics": [{"TopicArn": "arn:aws:sns:us-east-1:123456789012:test-topic"}]}
        ]
        mock_client.get_paginator.return_value = mock_paginator

        attributes = {
            "TopicArn": "arn:aws:sns:us-east-1:123456789012:test-topic",
            "Policy": "{}",
            "SubscriptionsPending": "0",
        }
        mock_client.get_topic_attributes.return_value = {"Attributes": attributes}
        mock_client.list_tags_for_resource.return_value = {"Tags": []}
        mock_create_client.return_value = mock_client

        collector = SNSCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].raw_config == attributes
