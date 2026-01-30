"""Tests for AWS client wrapper."""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from botocore.config import Config
from botocore.exceptions import ClientError, NoCredentialsError

from src.aws.client import (
    create_boto_client,
    get_enabled_regions,
    check_client_connection,
    DEFAULT_RETRY_CONFIG,
)


class TestDefaultRetryConfig:
    """Tests for default retry configuration."""

    def test_default_config_max_attempts(self):
        """Test default config has correct max attempts."""
        assert DEFAULT_RETRY_CONFIG.retries["max_attempts"] == 10

    def test_default_config_retry_mode(self):
        """Test default config uses adaptive retry mode."""
        assert DEFAULT_RETRY_CONFIG.retries["mode"] == "adaptive"

    def test_default_config_pool_connections(self):
        """Test default config has correct pool connections."""
        assert DEFAULT_RETRY_CONFIG.max_pool_connections == 50

    def test_default_config_timeouts(self):
        """Test default config has correct timeouts."""
        assert DEFAULT_RETRY_CONFIG.connect_timeout == 60
        assert DEFAULT_RETRY_CONFIG.read_timeout == 60


class TestCreateBotoClient:
    """Tests for create_boto_client function."""

    @patch("src.aws.client.boto3.client")
    def test_create_client_default_region(self, mock_boto_client):
        """Test client creation with default region."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        result = create_boto_client("ec2")

        mock_boto_client.assert_called_once()
        call_kwargs = mock_boto_client.call_args.kwargs
        assert call_kwargs["region_name"] == "us-east-1"
        assert result == mock_client

    @patch("src.aws.client.boto3.client")
    def test_create_client_custom_region(self, mock_boto_client):
        """Test client creation with custom region."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        result = create_boto_client("ec2", region_name="eu-west-1")

        call_kwargs = mock_boto_client.call_args.kwargs
        assert call_kwargs["region_name"] == "eu-west-1"
        assert result == mock_client

    @patch("src.aws.client.boto3.Session")
    def test_create_client_with_profile(self, mock_session_class):
        """Test client creation with AWS profile."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        result = create_boto_client("ec2", profile_name="my-profile")

        mock_session_class.assert_called_once_with(profile_name="my-profile")
        mock_session.client.assert_called_once()
        assert result == mock_client

    @patch("src.aws.client.boto3.client")
    def test_create_client_uses_default_retry_config(self, mock_boto_client):
        """Test that default retry config is used when not specified."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        create_boto_client("ec2")

        call_kwargs = mock_boto_client.call_args.kwargs
        assert call_kwargs["config"] == DEFAULT_RETRY_CONFIG

    @patch("src.aws.client.boto3.client")
    def test_create_client_custom_retry_config(self, mock_boto_client):
        """Test client creation with custom retry config."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client
        custom_config = Config(retries={"max_attempts": 5})

        create_boto_client("ec2", retry_config=custom_config)

        call_kwargs = mock_boto_client.call_args.kwargs
        assert call_kwargs["config"] == custom_config

    @patch("src.aws.client.boto3.client")
    def test_create_client_raises_no_credentials_error(self, mock_boto_client):
        """Test that NoCredentialsError is raised when credentials missing."""
        mock_boto_client.side_effect = NoCredentialsError()

        with pytest.raises(NoCredentialsError):
            create_boto_client("ec2")

    @patch("src.aws.client.boto3.client")
    def test_create_client_raises_client_error(self, mock_boto_client):
        """Test that ClientError is raised on client creation failure."""
        error_response = {"Error": {"Code": "InvalidParameterValue", "Message": "Test"}}
        mock_boto_client.side_effect = ClientError(error_response, "CreateClient")

        with pytest.raises(ClientError):
            create_boto_client("ec2")

    @patch("src.aws.client.boto3.client")
    def test_create_client_raises_unexpected_error(self, mock_boto_client):
        """Test that unexpected errors are raised."""
        mock_boto_client.side_effect = ValueError("Unexpected error")

        with pytest.raises(ValueError):
            create_boto_client("ec2")

    @patch("src.aws.client.boto3.client")
    def test_create_different_services(self, mock_boto_client):
        """Test creating clients for different AWS services."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        services = ["ec2", "iam", "lambda", "s3", "sts", "rds"]
        for service in services:
            create_boto_client(service)
            call_args = mock_boto_client.call_args
            assert call_args[0][0] == service


class TestGetEnabledRegions:
    """Tests for get_enabled_regions function."""

    @patch("src.aws.client.create_boto_client")
    def test_get_enabled_regions_success(self, mock_create_client):
        """Test successful retrieval of enabled regions."""
        mock_client = MagicMock()
        mock_client.describe_regions.return_value = {
            "Regions": [
                {"RegionName": "us-east-1"},
                {"RegionName": "us-west-2"},
                {"RegionName": "eu-west-1"},
            ]
        }
        mock_create_client.return_value = mock_client

        result = get_enabled_regions()

        assert result == ["us-east-1", "us-west-2", "eu-west-1"]
        mock_create_client.assert_called_once_with("ec2", region_name="us-east-1", profile_name=None)

    @patch("src.aws.client.create_boto_client")
    def test_get_enabled_regions_with_profile(self, mock_create_client):
        """Test enabled regions retrieval with profile."""
        mock_client = MagicMock()
        mock_client.describe_regions.return_value = {"Regions": [{"RegionName": "us-east-1"}]}
        mock_create_client.return_value = mock_client

        result = get_enabled_regions(profile_name="my-profile")

        mock_create_client.assert_called_once_with("ec2", region_name="us-east-1", profile_name="my-profile")
        assert result == ["us-east-1"]

    @patch("src.aws.client.create_boto_client")
    def test_get_enabled_regions_returns_default_on_error(self, mock_create_client):
        """Test that default regions are returned on error."""
        mock_create_client.side_effect = Exception("API error")

        result = get_enabled_regions()

        expected_defaults = [
            "us-east-1",
            "us-east-2",
            "us-west-1",
            "us-west-2",
            "eu-west-1",
            "eu-central-1",
            "ap-southeast-1",
            "ap-northeast-1",
        ]
        assert result == expected_defaults

    @patch("src.aws.client.create_boto_client")
    def test_get_enabled_regions_empty_response(self, mock_create_client):
        """Test handling of empty regions response."""
        mock_client = MagicMock()
        mock_client.describe_regions.return_value = {"Regions": []}
        mock_create_client.return_value = mock_client

        result = get_enabled_regions()

        assert result == []


class TestTestClientConnection:
    """Tests for check_client_connection function."""

    def test_connection_sts_client(self):
        """Test connection test for STS client."""
        mock_client = MagicMock()
        mock_service_model = MagicMock()
        mock_service_model.service_name = "sts"
        mock_client._service_model = mock_service_model
        mock_client.get_caller_identity.return_value = {"Account": "123456789012"}

        result = check_client_connection(mock_client)

        assert result is True
        mock_client.get_caller_identity.assert_called_once()

    def test_connection_ec2_client(self):
        """Test connection test for EC2 client."""
        mock_client = MagicMock()
        mock_service_model = MagicMock()
        mock_service_model.service_name = "ec2"
        mock_client._service_model = mock_service_model
        mock_client.describe_regions.return_value = {"Regions": []}

        result = check_client_connection(mock_client)

        assert result is True
        mock_client.describe_regions.assert_called_once_with(MaxResults=1)

    def test_connection_iam_client(self):
        """Test connection test for IAM client."""
        mock_client = MagicMock()
        mock_service_model = MagicMock()
        mock_service_model.service_name = "iam"
        mock_client._service_model = mock_service_model
        mock_client.list_users.return_value = {"Users": []}

        result = check_client_connection(mock_client)

        assert result is True
        mock_client.list_users.assert_called_once_with(MaxItems=1)

    def test_connection_lambda_client(self):
        """Test connection test for Lambda client."""
        mock_client = MagicMock()
        mock_service_model = MagicMock()
        mock_service_model.service_name = "lambda"
        mock_client._service_model = mock_service_model
        mock_client.list_functions.return_value = {"Functions": []}

        result = check_client_connection(mock_client)

        assert result is True
        mock_client.list_functions.assert_called_once_with(MaxItems=1)

    def test_connection_s3_client(self):
        """Test connection test for S3 client."""
        mock_client = MagicMock()
        mock_service_model = MagicMock()
        mock_service_model.service_name = "s3"
        mock_client._service_model = mock_service_model
        mock_client.list_buckets.return_value = {"Buckets": []}

        result = check_client_connection(mock_client)

        assert result is True
        mock_client.list_buckets.assert_called_once()

    def test_connection_unknown_service(self):
        """Test connection test for unknown service uses generic method."""
        mock_client = MagicMock()
        mock_service_model = MagicMock()
        mock_service_model.service_name = "custom-service"
        mock_client._service_model = mock_service_model
        mock_client._make_api_call.return_value = {}

        result = check_client_connection(mock_client)

        assert result is True
        mock_client._make_api_call.assert_called_once_with("ListObjects", {})

    def test_connection_failure_returns_false(self):
        """Test connection test returns False on failure."""
        mock_client = MagicMock()
        mock_service_model = MagicMock()
        mock_service_model.service_name = "sts"
        mock_client._service_model = mock_service_model
        mock_client.get_caller_identity.side_effect = Exception("Connection failed")

        result = check_client_connection(mock_client)

        assert result is False

    def test_connection_client_error_returns_false(self):
        """Test connection test returns False on ClientError."""
        mock_client = MagicMock()
        mock_service_model = MagicMock()
        mock_service_model.service_name = "ec2"
        mock_client._service_model = mock_service_model
        error_response = {"Error": {"Code": "UnauthorizedOperation", "Message": "Test"}}
        mock_client.describe_regions.side_effect = ClientError(error_response, "DescribeRegions")

        result = check_client_connection(mock_client)

        assert result is False
