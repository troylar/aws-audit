"""Unit tests for SQSCollector."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import boto3
import pytest

from src.snapshot.resource_collectors.sqs import SQSCollector


class TestSQSCollector:
    """Tests for SQSCollector."""

    @pytest.fixture
    def mock_session(self) -> Mock:
        """Create a mock boto3 session."""
        session = Mock(spec=boto3.Session)
        session.profile_name = "test-profile"
        return session

    @pytest.fixture
    def collector(self, mock_session: Mock) -> SQSCollector:
        """Create an SQSCollector instance."""
        return SQSCollector(session=mock_session, region="us-east-1")

    def test_service_name(self, collector: SQSCollector) -> None:
        """Test that service_name returns 'sqs'."""
        assert collector.service_name == "sqs"

    @patch("src.snapshot.resource_collectors.sqs.SQSCollector._create_client")
    @patch("src.snapshot.resource_collectors.sqs.SQSCollector._get_account_id")
    def test_collect_with_created_timestamp(
        self, mock_get_account_id: Mock, mock_create_client: Mock, collector: SQSCollector
    ) -> None:
        """Test that CreatedTimestamp is correctly converted from epoch to datetime.

        Regression test for issue #38.
        """
        mock_get_account_id.return_value = "123456789012"

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Epoch timestamp: 2024-06-01 00:00:00 UTC = 1717200000
        epoch_timestamp = "1717200000"
        expected_datetime = datetime(2024, 6, 1, 0, 0, 0, tzinfo=timezone.utc)

        mock_client.list_queues.return_value = {
            "QueueUrls": ["https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"]
        }

        mock_client.get_queue_attributes.return_value = {
            "Attributes": {
                "QueueArn": "arn:aws:sqs:us-east-1:123456789012:test-queue",
                "CreatedTimestamp": epoch_timestamp,
                "DelaySeconds": "0",
                "MaximumMessageSize": "262144",
            }
        }

        mock_client.list_queue_tags.return_value = {"Tags": {"Environment": "prod"}}

        resources = collector.collect()

        assert len(resources) == 1
        resource = resources[0]
        assert resource.name == "test-queue"
        assert resource.created_at == expected_datetime
        assert resource.created_at.tzinfo == timezone.utc

    @patch("src.snapshot.resource_collectors.sqs.SQSCollector._create_client")
    @patch("src.snapshot.resource_collectors.sqs.SQSCollector._get_account_id")
    def test_collect_without_created_timestamp(
        self, mock_get_account_id: Mock, mock_create_client: Mock, collector: SQSCollector
    ) -> None:
        """Test that missing CreatedTimestamp results in None created_at."""
        mock_get_account_id.return_value = "123456789012"

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_client.list_queues.return_value = {
            "QueueUrls": ["https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"]
        }

        mock_client.get_queue_attributes.return_value = {
            "Attributes": {
                "QueueArn": "arn:aws:sqs:us-east-1:123456789012:test-queue",
                # No CreatedTimestamp
                "DelaySeconds": "0",
            }
        }

        mock_client.list_queue_tags.return_value = {"Tags": {}}

        resources = collector.collect()

        assert len(resources) == 1
        assert resources[0].created_at is None

    @patch("src.snapshot.resource_collectors.sqs.SQSCollector._create_client")
    @patch("src.snapshot.resource_collectors.sqs.SQSCollector._get_account_id")
    def test_collect_with_invalid_timestamp(
        self, mock_get_account_id: Mock, mock_create_client: Mock, collector: SQSCollector
    ) -> None:
        """Test that invalid CreatedTimestamp is handled gracefully."""
        mock_get_account_id.return_value = "123456789012"

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_client.list_queues.return_value = {
            "QueueUrls": ["https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"]
        }

        mock_client.get_queue_attributes.return_value = {
            "Attributes": {
                "QueueArn": "arn:aws:sqs:us-east-1:123456789012:test-queue",
                "CreatedTimestamp": "not-a-number",  # Invalid timestamp
                "DelaySeconds": "0",
            }
        }

        mock_client.list_queue_tags.return_value = {"Tags": {}}

        resources = collector.collect()

        # Should still collect the queue, just with None created_at
        assert len(resources) == 1
        assert resources[0].created_at is None

    @patch("src.snapshot.resource_collectors.sqs.SQSCollector._create_client")
    @patch("src.snapshot.resource_collectors.sqs.SQSCollector._get_account_id")
    def test_collect_multiple_queues(
        self, mock_get_account_id: Mock, mock_create_client: Mock, collector: SQSCollector
    ) -> None:
        """Test collecting multiple SQS queues."""
        mock_get_account_id.return_value = "123456789012"

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_client.list_queues.return_value = {
            "QueueUrls": [
                "https://sqs.us-east-1.amazonaws.com/123456789012/queue-1",
                "https://sqs.us-east-1.amazonaws.com/123456789012/queue-2",
            ]
        }

        def get_attrs(QueueUrl, AttributeNames):
            queue_name = QueueUrl.split("/")[-1]
            return {
                "Attributes": {
                    "QueueArn": f"arn:aws:sqs:us-east-1:123456789012:{queue_name}",
                    "CreatedTimestamp": "1717200000",
                }
            }

        mock_client.get_queue_attributes.side_effect = get_attrs
        mock_client.list_queue_tags.return_value = {"Tags": {}}

        resources = collector.collect()

        assert len(resources) == 2
        assert resources[0].name == "queue-1"
        assert resources[1].name == "queue-2"
        # Both should have valid created_at
        assert resources[0].created_at is not None
        assert resources[1].created_at is not None

    @patch("src.snapshot.resource_collectors.sqs.SQSCollector._create_client")
    @patch("src.snapshot.resource_collectors.sqs.SQSCollector._get_account_id")
    def test_collect_empty_queues(
        self, mock_get_account_id: Mock, mock_create_client: Mock, collector: SQSCollector
    ) -> None:
        """Test collecting when no queues exist."""
        mock_get_account_id.return_value = "123456789012"

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_client.list_queues.return_value = {}  # No QueueUrls key

        resources = collector.collect()

        assert len(resources) == 0

    @patch("src.snapshot.resource_collectors.sqs.SQSCollector._create_client")
    @patch("src.snapshot.resource_collectors.sqs.SQSCollector._get_account_id")
    def test_collect_handles_list_queues_error(
        self, mock_get_account_id: Mock, mock_create_client: Mock, collector: SQSCollector
    ) -> None:
        """Test collecting handles list_queues error."""
        mock_get_account_id.return_value = "123456789012"

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_client.list_queues.side_effect = Exception("Service unavailable")

        resources = collector.collect()

        assert len(resources) == 0

    @patch("src.snapshot.resource_collectors.sqs.SQSCollector._create_client")
    @patch("src.snapshot.resource_collectors.sqs.SQSCollector._get_account_id")
    def test_collect_handles_get_attributes_error(
        self, mock_get_account_id: Mock, mock_create_client: Mock, collector: SQSCollector
    ) -> None:
        """Test collecting continues when get_queue_attributes fails."""
        mock_get_account_id.return_value = "123456789012"

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_client.list_queues.return_value = {
            "QueueUrls": [
                "https://sqs.us-east-1.amazonaws.com/123456789012/good-queue",
                "https://sqs.us-east-1.amazonaws.com/123456789012/bad-queue",
            ]
        }

        def get_attrs_side_effect(QueueUrl, AttributeNames):
            if "bad-queue" in QueueUrl:
                raise Exception("Access denied")
            return {
                "Attributes": {
                    "QueueArn": "arn:aws:sqs:us-east-1:123456789012:good-queue",
                    "CreatedTimestamp": "1717200000",
                }
            }

        mock_client.get_queue_attributes.side_effect = get_attrs_side_effect
        mock_client.list_queue_tags.return_value = {"Tags": {}}

        resources = collector.collect()

        # Should only get the good queue
        assert len(resources) == 1
        assert resources[0].name == "good-queue"

    @patch("src.snapshot.resource_collectors.sqs.SQSCollector._create_client")
    @patch("src.snapshot.resource_collectors.sqs.SQSCollector._get_account_id")
    def test_collect_handles_tags_error(
        self, mock_get_account_id: Mock, mock_create_client: Mock, collector: SQSCollector
    ) -> None:
        """Test collecting continues when list_queue_tags fails."""
        mock_get_account_id.return_value = "123456789012"

        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_client.list_queues.return_value = {
            "QueueUrls": ["https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"]
        }

        mock_client.get_queue_attributes.return_value = {
            "Attributes": {
                "QueueArn": "arn:aws:sqs:us-east-1:123456789012:test-queue",
                "CreatedTimestamp": "1717200000",
            }
        }

        mock_client.list_queue_tags.side_effect = Exception("Access denied")

        resources = collector.collect()

        # Should still get the queue without tags
        assert len(resources) == 1
        assert resources[0].tags == {}
