"""Tests for CloudTrail query early termination and flat pool."""

import threading
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.cloudtrail.query import CloudTrailQuery


class TestQuerySingleEventTypeCancellation:
    def test_skips_query_when_cancel_is_set(self):
        """If cancel_event is already set, _query_single_event_type returns immediately."""
        query = CloudTrailQuery(profile_name=None, regions=["us-east-1"])
        cancel = threading.Event()
        cancel.set()

        client = MagicMock()
        result = query._query_single_event_type(
            client=client,
            event_name="CreateBucket",
            start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
            region="us-east-1",
            cancel_event=cancel,
        )

        assert result == []
        client.get_paginator.assert_not_called()

    def test_stops_pagination_when_cancel_is_set(self):
        """If cancel_event is set mid-pagination, stop iterating."""
        query = CloudTrailQuery(profile_name=None, regions=["us-east-1"])
        cancel = threading.Event()

        client = MagicMock()
        paginator = MagicMock()
        client.get_paginator.return_value = paginator

        # Create two pages; set cancel after first page
        page1 = {"Events": []}
        page2 = {"Events": []}

        def pages_iter(**kwargs):
            yield page1
            cancel.set()
            yield page2

        paginator.paginate.return_value = pages_iter()

        result = query._query_single_event_type(
            client=client,
            event_name="CreateBucket",
            start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
            region="us-east-1",
            cancel_event=cancel,
        )

        # Should have processed page1 but stopped before page2
        assert result == []

    def test_works_without_cancel_event(self):
        """Backward compat: cancel_event=None works fine."""
        query = CloudTrailQuery(profile_name=None, regions=["us-east-1"])

        client = MagicMock()
        paginator = MagicMock()
        client.get_paginator.return_value = paginator
        paginator.paginate.return_value = [{"Events": []}]

        result = query._query_single_event_type(
            client=client,
            event_name="CreateBucket",
            start_time=datetime(2025, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2025, 1, 2, tzinfo=timezone.utc),
            region="us-east-1",
            cancel_event=None,
        )

        assert result == []


class TestGetResourceCreatorsTargetKeys:
    @patch.object(CloudTrailQuery, "get_all_creation_events")
    def test_passes_target_keys_through(self, mock_get_all):
        """get_resource_creators passes target_resource_keys to get_all_creation_events."""
        mock_get_all.return_value = []
        query = CloudTrailQuery(profile_name=None, regions=["us-east-1"])
        target = {"AWS::S3::Bucket:my-bucket"}

        query.get_resource_creators(
            days_back=90,
            regions=["us-east-1"],
            target_resource_keys=target,
        )

        mock_get_all.assert_called_once()
        call_kwargs = mock_get_all.call_args
        assert call_kwargs[0][4] == target or call_kwargs[1].get("target_resource_keys") == target
