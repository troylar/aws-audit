"""Tests for AWS credential validation."""

from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

from src.aws.credentials import (
    CredentialValidationError,
    check_required_permissions,
    get_account_id,
    get_credential_summary,
    validate_credentials,
)


class TestCredentialValidationError:
    """Tests for CredentialValidationError exception."""

    def test_exception_inheritance(self):
        """Test that exception inherits from Exception."""
        error = CredentialValidationError("test error")
        assert isinstance(error, Exception)

    def test_exception_message(self):
        """Test that exception contains message."""
        error = CredentialValidationError("custom message")
        assert str(error) == "custom message"


class TestValidateCredentials:
    """Tests for validate_credentials function."""

    @patch("src.aws.credentials.boto3.client")
    def test_validate_credentials_success(self, mock_boto_client):
        """Test successful credential validation."""
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "UserId": "AIDAEXAMPLE",
            "Arn": "arn:aws:iam::123456789012:user/testuser",
        }
        mock_boto_client.return_value = mock_sts

        result = validate_credentials()

        assert result["account_id"] == "123456789012"
        assert result["user_id"] == "AIDAEXAMPLE"
        assert result["arn"] == "arn:aws:iam::123456789012:user/testuser"

    @patch("src.aws.credentials.boto3.Session")
    def test_validate_credentials_with_profile(self, mock_session_class):
        """Test credential validation with profile."""
        mock_session = MagicMock()
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {
            "Account": "123456789012",
            "UserId": "AIDAEXAMPLE",
            "Arn": "arn:aws:iam::123456789012:user/testuser",
        }
        mock_session.client.return_value = mock_sts
        mock_session_class.return_value = mock_session

        result = validate_credentials(profile_name="my-profile")

        mock_session_class.assert_called_once_with(profile_name="my-profile")
        assert result["account_id"] == "123456789012"

    @patch("src.aws.credentials.boto3.client")
    def test_validate_credentials_no_credentials(self, mock_boto_client):
        """Test error handling when no credentials found."""
        mock_boto_client.side_effect = NoCredentialsError()

        with pytest.raises(CredentialValidationError) as exc_info:
            validate_credentials()

        assert "credentials not found" in str(exc_info.value).lower()
        assert "aws configure" in str(exc_info.value).lower()

    @patch("src.aws.credentials.boto3.client")
    def test_validate_credentials_partial_credentials(self, mock_boto_client):
        """Test error handling for partial credentials."""
        mock_boto_client.side_effect = PartialCredentialsError(provider="env", cred_var="AWS_SECRET_ACCESS_KEY")

        with pytest.raises(CredentialValidationError) as exc_info:
            validate_credentials()

        assert "incomplete" in str(exc_info.value).lower()

    @patch("src.aws.credentials.boto3.client")
    def test_validate_credentials_invalid_token(self, mock_boto_client):
        """Test error handling for invalid access key."""
        mock_sts = MagicMock()
        error_response = {"Error": {"Code": "InvalidClientTokenId", "Message": "Invalid"}}
        mock_sts.get_caller_identity.side_effect = ClientError(error_response, "GetCallerIdentity")
        mock_boto_client.return_value = mock_sts

        with pytest.raises(CredentialValidationError) as exc_info:
            validate_credentials()

        assert "invalid" in str(exc_info.value).lower()
        assert "access key" in str(exc_info.value).lower()

    @patch("src.aws.credentials.boto3.client")
    def test_validate_credentials_signature_mismatch(self, mock_boto_client):
        """Test error handling for signature mismatch."""
        mock_sts = MagicMock()
        error_response = {"Error": {"Code": "SignatureDoesNotMatch", "Message": "Signature"}}
        mock_sts.get_caller_identity.side_effect = ClientError(error_response, "GetCallerIdentity")
        mock_boto_client.return_value = mock_sts

        with pytest.raises(CredentialValidationError) as exc_info:
            validate_credentials()

        assert "signature" in str(exc_info.value).lower()
        assert "secret access key" in str(exc_info.value).lower()

    @patch("src.aws.credentials.boto3.client")
    def test_validate_credentials_expired_token(self, mock_boto_client):
        """Test error handling for expired credentials."""
        mock_sts = MagicMock()
        error_response = {"Error": {"Code": "ExpiredToken", "Message": "Token expired"}}
        mock_sts.get_caller_identity.side_effect = ClientError(error_response, "GetCallerIdentity")
        mock_boto_client.return_value = mock_sts

        with pytest.raises(CredentialValidationError) as exc_info:
            validate_credentials()

        assert "expired" in str(exc_info.value).lower()

    @patch("src.aws.credentials.boto3.client")
    def test_validate_credentials_unknown_client_error(self, mock_boto_client):
        """Test error handling for unknown client error."""
        mock_sts = MagicMock()
        error_response = {"Error": {"Code": "UnknownError", "Message": "Unknown"}}
        mock_sts.get_caller_identity.side_effect = ClientError(error_response, "GetCallerIdentity")
        mock_boto_client.return_value = mock_sts

        with pytest.raises(CredentialValidationError) as exc_info:
            validate_credentials()

        assert "validation failed" in str(exc_info.value).lower()

    @patch("src.aws.credentials.boto3.client")
    def test_validate_credentials_unexpected_error(self, mock_boto_client):
        """Test error handling for unexpected errors."""
        mock_boto_client.side_effect = ValueError("Unexpected")

        with pytest.raises(CredentialValidationError) as exc_info:
            validate_credentials()

        assert "unexpected error" in str(exc_info.value).lower()


class TestCheckRequiredPermissions:
    """Tests for check_required_permissions function."""

    @patch("src.aws.credentials.boto3.client")
    @patch("src.aws.credentials.validate_credentials")
    def test_check_permissions_success(self, mock_validate, mock_boto_client):
        """Test successful permission check."""
        mock_validate.return_value = {
            "account_id": "123456789012",
            "user_id": "AIDAEXAMPLE",
            "arn": "arn:aws:iam::123456789012:user/testuser",
        }

        mock_iam = MagicMock()
        mock_iam.simulate_principal_policy.return_value = {"EvaluationResults": [{"EvalDecision": "allowed"}]}
        mock_boto_client.return_value = mock_iam

        result = check_required_permissions(required_actions=["ec2:DescribeInstances"])

        assert result["ec2:DescribeInstances"] is True

    @patch("src.aws.credentials.boto3.client")
    @patch("src.aws.credentials.validate_credentials")
    def test_check_permissions_denied(self, mock_validate, mock_boto_client):
        """Test permission check for denied action."""
        mock_validate.return_value = {
            "account_id": "123456789012",
            "user_id": "AIDAEXAMPLE",
            "arn": "arn:aws:iam::123456789012:user/testuser",
        }

        mock_iam = MagicMock()
        mock_iam.simulate_principal_policy.return_value = {"EvaluationResults": [{"EvalDecision": "implicitDeny"}]}
        mock_boto_client.return_value = mock_iam

        result = check_required_permissions(required_actions=["ec2:DeleteVpc"])

        assert result["ec2:DeleteVpc"] is False

    @patch("src.aws.credentials.boto3.Session")
    @patch("src.aws.credentials.validate_credentials")
    def test_check_permissions_with_profile(self, mock_validate, mock_session_class):
        """Test permission check with profile."""
        mock_validate.return_value = {
            "account_id": "123456789012",
            "user_id": "AIDAEXAMPLE",
            "arn": "arn:aws:iam::123456789012:user/testuser",
        }

        mock_session = MagicMock()
        mock_iam = MagicMock()
        mock_iam.simulate_principal_policy.return_value = {"EvaluationResults": [{"EvalDecision": "allowed"}]}
        mock_session.client.return_value = mock_iam
        mock_session_class.return_value = mock_session

        result = check_required_permissions(profile_name="my-profile", required_actions=["ec2:DescribeInstances"])

        mock_session_class.assert_called_with(profile_name="my-profile")
        assert result["ec2:DescribeInstances"] is True

    @patch("src.aws.credentials.boto3.client")
    @patch("src.aws.credentials.validate_credentials")
    def test_check_permissions_uses_defaults(self, mock_validate, mock_boto_client):
        """Test that default permissions are checked when none specified."""
        mock_validate.return_value = {
            "account_id": "123456789012",
            "user_id": "AIDAEXAMPLE",
            "arn": "arn:aws:iam::123456789012:user/testuser",
        }

        mock_iam = MagicMock()
        mock_iam.simulate_principal_policy.return_value = {"EvaluationResults": [{"EvalDecision": "allowed"}]}
        mock_boto_client.return_value = mock_iam

        result = check_required_permissions()

        # Default actions should be checked
        assert "ec2:DescribeInstances" in result
        assert "s3:ListAllMyBuckets" in result

    @patch("src.aws.credentials.boto3.client")
    @patch("src.aws.credentials.validate_credentials")
    def test_check_permissions_simulation_fails(self, mock_validate, mock_boto_client):
        """Test handling of simulation failure."""
        mock_validate.return_value = {
            "account_id": "123456789012",
            "user_id": "AIDAEXAMPLE",
            "arn": "arn:aws:iam::123456789012:user/testuser",
        }

        mock_iam = MagicMock()
        error_response = {"Error": {"Code": "AccessDenied", "Message": "Not allowed"}}
        mock_iam.simulate_principal_policy.side_effect = ClientError(error_response, "SimulatePrincipalPolicy")
        mock_boto_client.return_value = mock_iam

        result = check_required_permissions(required_actions=["ec2:DescribeInstances"])

        # Should return None for unknown status
        assert result["ec2:DescribeInstances"] is None

    @patch("src.aws.credentials.boto3.client")
    @patch("src.aws.credentials.validate_credentials")
    def test_check_permissions_empty_results(self, mock_validate, mock_boto_client):
        """Test handling of empty evaluation results."""
        mock_validate.return_value = {
            "account_id": "123456789012",
            "user_id": "AIDAEXAMPLE",
            "arn": "arn:aws:iam::123456789012:user/testuser",
        }

        mock_iam = MagicMock()
        mock_iam.simulate_principal_policy.return_value = {"EvaluationResults": []}
        mock_boto_client.return_value = mock_iam

        result = check_required_permissions(required_actions=["ec2:DescribeInstances"])

        assert result["ec2:DescribeInstances"] is False

    @patch("src.aws.credentials.validate_credentials")
    def test_check_permissions_validation_fails(self, mock_validate):
        """Test handling when credential validation fails."""
        mock_validate.side_effect = CredentialValidationError("Invalid credentials")

        result = check_required_permissions(required_actions=["ec2:DescribeInstances"])

        # Should return None for all actions
        assert result["ec2:DescribeInstances"] is None


class TestGetAccountId:
    """Tests for get_account_id function."""

    @patch("src.aws.credentials.validate_credentials")
    def test_get_account_id_success(self, mock_validate):
        """Test successful account ID retrieval."""
        mock_validate.return_value = {
            "account_id": "123456789012",
            "user_id": "AIDAEXAMPLE",
            "arn": "arn:aws:iam::123456789012:user/testuser",
        }

        result = get_account_id()

        assert result == "123456789012"

    @patch("src.aws.credentials.validate_credentials")
    def test_get_account_id_with_profile(self, mock_validate):
        """Test account ID retrieval with profile."""
        mock_validate.return_value = {
            "account_id": "987654321098",
            "user_id": "AIDAEXAMPLE",
            "arn": "arn:aws:iam::987654321098:user/testuser",
        }

        result = get_account_id(profile_name="my-profile")

        mock_validate.assert_called_once_with("my-profile")
        assert result == "987654321098"

    @patch("src.aws.credentials.validate_credentials")
    def test_get_account_id_validation_fails(self, mock_validate):
        """Test error handling when validation fails."""
        mock_validate.side_effect = CredentialValidationError("Invalid credentials")

        with pytest.raises(CredentialValidationError):
            get_account_id()


class TestGetCredentialSummary:
    """Tests for get_credential_summary function."""

    @patch("src.aws.credentials.validate_credentials")
    def test_get_summary_success(self, mock_validate):
        """Test successful summary generation."""
        mock_validate.return_value = {
            "account_id": "123456789012",
            "user_id": "AIDAEXAMPLE",
            "arn": "arn:aws:iam::123456789012:user/testuser",
        }

        result = get_credential_summary()

        assert "123456789012" in result
        assert "testuser" in result
        assert "AWS Credentials Valid" in result

    @patch("src.aws.credentials.validate_credentials")
    def test_get_summary_with_profile(self, mock_validate):
        """Test summary includes profile when specified."""
        mock_validate.return_value = {
            "account_id": "123456789012",
            "user_id": "AIDAEXAMPLE",
            "arn": "arn:aws:iam::123456789012:user/testuser",
        }

        result = get_credential_summary(profile_name="my-profile")

        assert "my-profile" in result
        assert "Profile:" in result

    @patch("src.aws.credentials.validate_credentials")
    def test_get_summary_validation_fails(self, mock_validate):
        """Test summary shows error when validation fails."""
        mock_validate.side_effect = CredentialValidationError("Credentials invalid")

        result = get_credential_summary()

        assert "Credential Validation Failed" in result
        assert "Credentials invalid" in result

    @patch("src.aws.credentials.validate_credentials")
    def test_get_summary_role_arn(self, mock_validate):
        """Test summary handles role ARN correctly."""
        mock_validate.return_value = {
            "account_id": "123456789012",
            "user_id": "AROA123:session-name",
            "arn": "arn:aws:sts::123456789012:assumed-role/MyRole/session-name",
        }

        result = get_credential_summary()

        assert "session-name" in result
        assert "123456789012" in result
