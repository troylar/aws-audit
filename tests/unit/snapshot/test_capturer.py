"""Tests for snapshot capturer module."""

from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.capturer import (
    COLLECTOR_REGISTRY,
    _get_collectors,
    create_snapshot_mvp,
)


class TestGetCollectors:
    """Tests for _get_collectors function."""

    @patch("src.snapshot.capturer.boto3")
    def test_get_collectors_no_filter(self, mock_boto3):
        """Test getting all collectors when no filter specified."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        collectors = _get_collectors(None)

        assert collectors == COLLECTOR_REGISTRY
        assert len(collectors) > 0

    @patch("src.snapshot.capturer.boto3")
    def test_get_collectors_empty_filter(self, mock_boto3):
        """Test getting all collectors when filter is empty list."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        collectors = _get_collectors([])

        assert collectors == COLLECTOR_REGISTRY

    @patch("src.snapshot.capturer.boto3")
    def test_get_collectors_single_type(self, mock_boto3):
        """Test filtering to a single resource type."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        collectors = _get_collectors(["s3"])

        assert len(collectors) == 1
        # Verify it's the S3 collector
        temp = collectors[0](mock_session, "us-east-1")
        assert temp.service_name == "s3"

    @patch("src.snapshot.capturer.boto3")
    def test_get_collectors_multiple_types(self, mock_boto3):
        """Test filtering to multiple resource types."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        collectors = _get_collectors(["s3", "lambda", "iam"])

        assert len(collectors) == 3
        service_names = [c(mock_session, "us-east-1").service_name for c in collectors]
        assert "s3" in service_names
        assert "lambda" in service_names
        assert "iam" in service_names

    @patch("src.snapshot.capturer.boto3")
    def test_get_collectors_unknown_type_returns_all(self, mock_boto3):
        """Test that unknown type filter returns all collectors."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        collectors = _get_collectors(["unknownservice123"])

        # Should return all collectors when filter doesn't match anything
        assert collectors == COLLECTOR_REGISTRY


class TestCreateSnapshotMVP:
    """Tests for create_snapshot_mvp function."""

    @patch("src.snapshot.capturer.create_snapshot")
    def test_create_snapshot_mvp_calls_create_snapshot(self, mock_create_snapshot):
        """Test that create_snapshot_mvp calls create_snapshot with correct args."""
        mock_snapshot = MagicMock()
        mock_create_snapshot.return_value = mock_snapshot

        result = create_snapshot_mvp(
            name="test-snapshot",
            regions=["us-east-1", "us-west-2"],
            account_id="123456789012",
            profile_name="test-profile",
            set_active=True,
        )

        mock_create_snapshot.assert_called_once_with(
            name="test-snapshot",
            regions=["us-east-1", "us-west-2"],
            account_id="123456789012",
            profile_name="test-profile",
            set_active=True,
        )
        assert result == mock_snapshot

    @patch("src.snapshot.capturer.create_snapshot")
    def test_create_snapshot_mvp_default_profile(self, mock_create_snapshot):
        """Test create_snapshot_mvp with default profile (None)."""
        mock_snapshot = MagicMock()
        mock_create_snapshot.return_value = mock_snapshot

        result = create_snapshot_mvp(
            name="my-snapshot",
            regions=["eu-west-1"],
            account_id="987654321098",
        )

        mock_create_snapshot.assert_called_once_with(
            name="my-snapshot",
            regions=["eu-west-1"],
            account_id="987654321098",
            profile_name=None,
            set_active=True,
        )


class TestCollectorRegistry:
    """Tests for COLLECTOR_REGISTRY."""

    def test_registry_not_empty(self):
        """Test that collector registry is not empty."""
        assert len(COLLECTOR_REGISTRY) > 0

    def test_registry_contains_major_services(self):
        """Test that registry contains collectors for major AWS services."""
        # Get service names from registry
        mock_session = MagicMock()
        service_names = [c(mock_session, "us-east-1").service_name for c in COLLECTOR_REGISTRY]

        # Major services should be in the registry
        assert "s3" in service_names
        assert "iam" in service_names
        assert "lambda" in service_names
        assert "ec2" in service_names
        assert "rds" in service_names
        assert "dynamodb" in service_names

    def test_all_collectors_have_service_name(self):
        """Test that all collectors have a service_name property."""
        mock_session = MagicMock()

        for collector_class in COLLECTOR_REGISTRY:
            collector = collector_class(mock_session, "us-east-1")
            assert hasattr(collector, "service_name")
            assert isinstance(collector.service_name, str)
            assert len(collector.service_name) > 0

    def test_all_collectors_have_is_global_service(self):
        """Test that all collectors have is_global_service property."""
        mock_session = MagicMock()

        for collector_class in COLLECTOR_REGISTRY:
            collector = collector_class(mock_session, "us-east-1")
            assert hasattr(collector, "is_global_service")
            assert isinstance(collector.is_global_service, bool)
