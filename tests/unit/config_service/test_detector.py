"""Unit tests for AWS Config detector module."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.config_service.detector import (
    ConfigAvailability,
    check_aggregator_availability,
    detect_config_availability,
    get_config_supported_resource_types,
)


class TestConfigAvailability:
    """Tests for ConfigAvailability dataclass."""

    def test_default_values(self):
        """Test ConfigAvailability has correct default values."""
        avail = ConfigAvailability(region="us-east-1")

        assert avail.region == "us-east-1"
        assert avail.is_enabled is False
        assert avail.recorder_name is None
        assert avail.recording_group_all_supported is False
        assert avail.resource_types_recorded == set()
        assert avail.delivery_channel_configured is False
        assert avail.error_message is None

    def test_supports_resource_type_when_disabled(self):
        """Test supports_resource_type returns False when Config is disabled."""
        avail = ConfigAvailability(region="us-east-1", is_enabled=False)

        assert avail.supports_resource_type("AWS::EC2::Instance") is False

    def test_supports_resource_type_with_all_supported(self):
        """Test supports_resource_type with allSupported=True."""
        avail = ConfigAvailability(
            region="us-east-1",
            is_enabled=True,
            recording_group_all_supported=True,
        )

        # Should support known Config types
        assert avail.supports_resource_type("AWS::EC2::Instance") is True
        assert avail.supports_resource_type("AWS::S3::Bucket") is True

        # Should not support unsupported types
        assert avail.supports_resource_type("AWS::Route53::HostedZone") is False  # In DIRECT_API_ONLY

    def test_supports_resource_type_with_specific_types(self):
        """Test supports_resource_type with specific recorded types."""
        avail = ConfigAvailability(
            region="us-east-1",
            is_enabled=True,
            recording_group_all_supported=False,
            resource_types_recorded={"AWS::EC2::Instance", "AWS::S3::Bucket"},
        )

        assert avail.supports_resource_type("AWS::EC2::Instance") is True
        assert avail.supports_resource_type("AWS::S3::Bucket") is True
        assert avail.supports_resource_type("AWS::Lambda::Function") is False


class TestDetectConfigAvailability:
    """Tests for detect_config_availability function."""

    @patch("src.config_service.detector.create_boto_client")
    def test_detect_config_enabled(self, mock_create_client):
        """Test detection when Config is enabled and recording."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_client.describe_configuration_recorders.return_value = {
            "ConfigurationRecorders": [
                {
                    "name": "default",
                    "recordingGroup": {
                        "allSupported": True,
                        "includeGlobalResourceTypes": True,
                    },
                }
            ]
        }
        mock_client.describe_configuration_recorder_status.return_value = {
            "ConfigurationRecordersStatus": [
                {
                    "name": "default",
                    "recording": True,
                }
            ]
        }
        mock_client.describe_delivery_channels.return_value = {"DeliveryChannels": [{"name": "default"}]}

        mock_session = MagicMock()
        result = detect_config_availability(mock_session, "us-east-1")

        assert result.is_enabled is True
        assert result.recorder_name == "default"
        assert result.recording_group_all_supported is True
        assert result.delivery_channel_configured is True
        assert result.error_message is None

    @patch("src.config_service.detector.create_boto_client")
    def test_detect_config_no_recorders(self, mock_create_client):
        """Test detection when no configuration recorders exist."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_client.describe_configuration_recorders.return_value = {"ConfigurationRecorders": []}

        mock_session = MagicMock()
        result = detect_config_availability(mock_session, "us-east-1")

        assert result.is_enabled is False
        assert result.error_message == "No configuration recorders found"

    @patch("src.config_service.detector.create_boto_client")
    def test_detect_config_not_recording(self, mock_create_client):
        """Test detection when recorder exists but is not recording."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_client.describe_configuration_recorders.return_value = {
            "ConfigurationRecorders": [
                {
                    "name": "default",
                    "recordingGroup": {"allSupported": True},
                }
            ]
        }
        mock_client.describe_configuration_recorder_status.return_value = {
            "ConfigurationRecordersStatus": [
                {
                    "name": "default",
                    "recording": False,
                }
            ]
        }

        mock_session = MagicMock()
        result = detect_config_availability(mock_session, "us-east-1")

        assert result.is_enabled is False
        assert "not recording" in result.error_message

    @patch("src.config_service.detector.create_boto_client")
    def test_detect_config_with_specific_types(self, mock_create_client):
        """Test detection with specific resource types (not allSupported)."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_client.describe_configuration_recorders.return_value = {
            "ConfigurationRecorders": [
                {
                    "name": "partial-recorder",
                    "recordingGroup": {
                        "allSupported": False,
                        "resourceTypes": ["AWS::EC2::Instance", "AWS::S3::Bucket"],
                    },
                }
            ]
        }
        mock_client.describe_configuration_recorder_status.return_value = {
            "ConfigurationRecordersStatus": [
                {
                    "name": "partial-recorder",
                    "recording": True,
                }
            ]
        }
        mock_client.describe_delivery_channels.return_value = {"DeliveryChannels": []}

        mock_session = MagicMock()
        result = detect_config_availability(mock_session, "us-west-2")

        assert result.is_enabled is True
        assert result.recorder_name == "partial-recorder"
        assert result.recording_group_all_supported is False
        assert result.resource_types_recorded == {"AWS::EC2::Instance", "AWS::S3::Bucket"}

    @patch("src.config_service.detector.create_boto_client")
    def test_detect_config_api_error(self, mock_create_client):
        """Test detection handles API errors gracefully."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Create a mock exceptions namespace with a real exception class
        mock_client.exceptions = MagicMock()
        mock_client.exceptions.NoSuchConfigurationRecorderException = type(
            "NoSuchConfigurationRecorderException", (Exception,), {}
        )

        mock_client.describe_configuration_recorders.side_effect = Exception("Access denied")

        mock_session = MagicMock()
        result = detect_config_availability(mock_session, "us-east-1")

        assert result.is_enabled is False
        assert "Access denied" in result.error_message


class TestGetConfigSupportedResourceTypes:
    """Tests for get_config_supported_resource_types function."""

    @patch("src.config_service.detector.detect_config_availability")
    def test_returns_empty_when_disabled(self, mock_detect):
        """Test returns empty set when Config is disabled."""
        mock_detect.return_value = ConfigAvailability(region="us-east-1", is_enabled=False)

        mock_session = MagicMock()
        result = get_config_supported_resource_types(mock_session, "us-east-1")

        assert result == set()

    @patch("src.config_service.detector.detect_config_availability")
    def test_returns_all_supported_types(self, mock_detect):
        """Test returns all Config types when allSupported=True."""
        mock_detect.return_value = ConfigAvailability(
            region="us-east-1",
            is_enabled=True,
            recording_group_all_supported=True,
        )

        mock_session = MagicMock()
        result = get_config_supported_resource_types(mock_session, "us-east-1")

        assert "AWS::EC2::Instance" in result
        assert "AWS::S3::Bucket" in result
        assert len(result) > 50  # Should have many types

    @patch("src.config_service.detector.detect_config_availability")
    def test_returns_specific_types(self, mock_detect):
        """Test returns only recorded types when specific types configured."""
        mock_detect.return_value = ConfigAvailability(
            region="us-east-1",
            is_enabled=True,
            recording_group_all_supported=False,
            resource_types_recorded={"AWS::EC2::Instance", "AWS::RDS::DBInstance"},
        )

        mock_session = MagicMock()
        result = get_config_supported_resource_types(mock_session, "us-east-1")

        assert result == {"AWS::EC2::Instance", "AWS::RDS::DBInstance"}


class TestCheckAggregatorAvailability:
    """Tests for check_aggregator_availability function."""

    @patch("src.config_service.detector.create_boto_client")
    def test_aggregator_available(self, mock_create_client):
        """Test detection of available aggregator."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_client.describe_configuration_aggregators.return_value = {
            "ConfigurationAggregators": [
                {
                    "ConfigurationAggregatorName": "my-aggregator",
                }
            ]
        }

        mock_session = MagicMock()
        is_available, error = check_aggregator_availability(mock_session, "my-aggregator")

        assert is_available is True
        assert error is None

    @patch("src.config_service.detector.create_boto_client")
    def test_aggregator_not_found(self, mock_create_client):
        """Test detection when aggregator doesn't exist."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        mock_client.describe_configuration_aggregators.return_value = {"ConfigurationAggregators": []}

        mock_session = MagicMock()
        is_available, error = check_aggregator_availability(mock_session, "nonexistent")

        assert is_available is False
        assert "not found" in error

    @patch("src.config_service.detector.create_boto_client")
    def test_aggregator_api_error(self, mock_create_client):
        """Test handles API errors gracefully."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client

        # Create a mock exceptions namespace with a real exception class
        mock_client.exceptions = MagicMock()
        mock_client.exceptions.NoSuchConfigurationAggregatorException = type(
            "NoSuchConfigurationAggregatorException", (Exception,), {}
        )

        mock_client.describe_configuration_aggregators.side_effect = Exception("Access denied")

        mock_session = MagicMock()
        is_available, error = check_aggregator_availability(mock_session, "my-aggregator")

        assert is_available is False
        assert "Access denied" in error
