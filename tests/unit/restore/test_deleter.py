"""Tests for ResourceDeleter class.

Test coverage for AWS resource deletion with boto3 integration.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

from botocore.exceptions import ClientError

from src.restore.deleter import RESOURCES_WITH_PREREQUISITES, ResourceDeleter


class TestResourceDeleter:
    """Test suite for ResourceDeleter class."""

    def test_init_creates_deleter_with_defaults(self) -> None:
        """Test initialization with default parameters."""
        deleter = ResourceDeleter()

        assert deleter.aws_profile is None
        assert deleter.max_retries == 3

    def test_init_with_custom_parameters(self) -> None:
        """Test initialization with custom parameters."""
        deleter = ResourceDeleter(aws_profile="prod", max_retries=5)

        assert deleter.aws_profile == "prod"
        assert deleter.max_retries == 5

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_ec2_instance_success(self, mock_create_client: Mock) -> None:
        """Test successful EC2 instance deletion."""
        # Setup mock client
        mock_client = Mock()
        mock_client.terminate_instances.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::EC2::Instance",
            resource_id="i-123456",
            region="us-east-1",
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-123456",
        )

        assert success is True
        assert error is None
        mock_create_client.assert_called_once_with(
            service_name="ec2",
            region_name="us-east-1",
            profile_name=None,
        )
        mock_client.terminate_instances.assert_called_once_with(InstanceIds=["i-123456"])

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_lambda_function_success(self, mock_create_client: Mock) -> None:
        """Test successful Lambda function deletion."""
        mock_client = Mock()
        mock_client.delete_function.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::Lambda::Function",
            resource_id="my-function",
            region="us-west-2",
            arn="arn:aws:lambda:us-west-2:123456789012:function:my-function",
        )

        assert success is True
        assert error is None
        mock_client.delete_function.assert_called_once_with(FunctionName="my-function")

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_rds_instance_with_skip_snapshot(self, mock_create_client: Mock) -> None:
        """Test RDS instance deletion skips final snapshot."""
        mock_client = Mock()
        mock_client.delete_db_instance.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::RDS::DBInstance",
            resource_id="my-database",
            region="us-east-1",
            arn="arn:aws:rds:us-east-1:123456789012:db:my-database",
        )

        assert success is True
        assert error is None
        mock_client.delete_db_instance.assert_called_once_with(
            DBInstanceIdentifier="my-database",
            SkipFinalSnapshot=True,
            DeleteAutomatedBackups=True,
        )

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_handles_already_deleted_resource(self, mock_create_client: Mock) -> None:
        """Test deletion handles already-deleted resources gracefully."""
        mock_client = Mock()
        error_response = {
            "Error": {
                "Code": "InvalidInstanceID.NotFound",
                "Message": "The instance ID 'i-123456' does not exist",
            }
        }
        mock_client.terminate_instances.side_effect = ClientError(error_response, "TerminateInstances")
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::EC2::Instance",
            resource_id="i-123456",
            region="us-east-1",
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-123456",
        )

        # Should succeed because resource is already gone
        assert success is True
        assert error is None

    @patch("src.restore.deleter.create_boto_client")
    @patch("src.restore.deleter.time.sleep")
    def test_delete_retries_on_dependency_violation(self, mock_sleep: Mock, mock_create_client: Mock) -> None:
        """Test deletion retries on dependency violations."""
        mock_client = Mock()
        error_response = {
            "Error": {
                "Code": "DependencyViolation",
                "Message": "The resource has a dependent object",
            }
        }
        # Fail twice, succeed on third attempt
        mock_client.terminate_instances.side_effect = [
            ClientError(error_response, "TerminateInstances"),
            ClientError(error_response, "TerminateInstances"),
            {},  # Success
        ]
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter(max_retries=3)
        success, error = deleter.delete_resource(
            resource_type="AWS::EC2::Instance",
            resource_id="i-123456",
            region="us-east-1",
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-123456",
        )

        assert success is True
        assert error is None
        # Should have been called 3 times
        assert mock_client.terminate_instances.call_count == 3
        # Should have slept twice (exponential backoff: 1s, 2s)
        assert mock_sleep.call_count == 2

    @patch("src.restore.deleter.create_boto_client")
    @patch("src.restore.deleter.time.sleep")
    def test_delete_fails_after_max_retries(self, mock_sleep: Mock, mock_create_client: Mock) -> None:
        """Test deletion fails after exhausting retries."""
        mock_client = Mock()
        error_response = {
            "Error": {
                "Code": "DependencyViolation",
                "Message": "The resource has a dependent object",
            }
        }
        mock_client.terminate_instances.side_effect = ClientError(error_response, "TerminateInstances")
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter(max_retries=3)
        success, error = deleter.delete_resource(
            resource_type="AWS::EC2::Instance",
            resource_id="i-123456",
            region="us-east-1",
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-123456",
        )

        assert success is False
        assert "after 3 attempts" in error
        assert mock_client.terminate_instances.call_count == 3

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_handles_client_error(self, mock_create_client: Mock) -> None:
        """Test deletion handles general client errors."""
        mock_client = Mock()
        error_response = {
            "Error": {
                "Code": "AccessDenied",
                "Message": "You are not authorized",
            }
        }
        mock_client.terminate_instances.side_effect = ClientError(error_response, "TerminateInstances")
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::EC2::Instance",
            resource_id="i-123456",
            region="us-east-1",
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-123456",
        )

        assert success is False
        assert "AccessDenied" in error
        assert "not authorized" in error

    def test_delete_unsupported_resource_type(self) -> None:
        """Test deletion of unsupported resource type."""
        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::UnsupportedService::Resource",
            resource_id="resource-123",
            region="us-east-1",
            arn="arn:aws:unsupported:us-east-1:123456789012:resource/resource-123",
        )

        assert success is False
        assert "Unsupported resource type" in error

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_with_aws_profile(self, mock_create_client: Mock) -> None:
        """Test deletion uses specified AWS profile."""
        mock_client = Mock()
        mock_client.terminate_instances.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter(aws_profile="production")
        success, error = deleter.delete_resource(
            resource_type="AWS::EC2::Instance",
            resource_id="i-123456",
            region="us-east-1",
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-123456",
        )

        assert success is True
        mock_create_client.assert_called_once_with(
            service_name="ec2",
            region_name="us-east-1",
            profile_name="production",
        )

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_s3_bucket(self, mock_create_client: Mock) -> None:
        """Test S3 bucket deletion with prerequisite emptying."""
        mock_client = Mock()
        mock_client.delete_bucket.return_value = {}
        # Mock object lock check (no lock)
        mock_client.get_object_lock_configuration.side_effect = ClientError(
            {"Error": {"Code": "ObjectLockConfigurationNotFoundError"}},
            "GetObjectLockConfiguration",
        )
        # Mock empty bucket (no objects)
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"Versions": [], "DeleteMarkers": []}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::S3::Bucket",
            resource_id="my-bucket",
            region="us-east-1",
            arn="arn:aws:s3:::my-bucket",
        )

        assert success is True
        assert error is None
        mock_client.delete_bucket.assert_called_once_with(Bucket="my-bucket")

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_dynamodb_table(self, mock_create_client: Mock) -> None:
        """Test DynamoDB table deletion."""
        mock_client = Mock()
        mock_client.delete_table.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::DynamoDB::Table",
            resource_id="my-table",
            region="us-east-1",
            arn="arn:aws:dynamodb:us-east-1:123456789012:table/my-table",
        )

        assert success is True
        assert error is None
        mock_client.delete_table.assert_called_once_with(TableName="my-table")

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_iam_role(self, mock_create_client: Mock) -> None:
        """Test IAM role deletion with prerequisite cleanup."""
        mock_client = Mock()
        mock_client.delete_role.return_value = {}
        # Mock empty paginators for prerequisite cleanup
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{}]  # No policies/profiles
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::IAM::Role",
            resource_id="MyRole",
            region="us-east-1",
            arn="arn:aws:iam::123456789012:role/MyRole",
        )

        assert success is True
        assert error is None
        mock_client.delete_role.assert_called_once_with(RoleName="MyRole")

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_kms_key_schedules_deletion(self, mock_create_client: Mock) -> None:
        """Test KMS key schedules deletion with minimum waiting period."""
        mock_client = Mock()
        mock_client.schedule_key_deletion.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::KMS::Key",
            resource_id="key-123",
            region="us-east-1",
            arn="arn:aws:kms:us-east-1:123456789012:key/key-123",
        )

        assert success is True
        assert error is None
        mock_client.schedule_key_deletion.assert_called_once_with(
            KeyId="key-123",
            PendingWindowInDays=7,
        )

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_secret_forces_deletion(self, mock_create_client: Mock) -> None:
        """Test Secrets Manager secret forces immediate deletion."""
        mock_client = Mock()
        mock_client.delete_secret.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::SecretsManager::Secret",
            resource_id="my-secret",
            region="us-east-1",
            arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:my-secret",
        )

        assert success is True
        assert error is None
        mock_client.delete_secret.assert_called_once_with(
            SecretId="my-secret",
            ForceDeleteWithoutRecovery=True,
        )

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_handles_unexpected_exception_in_deletion_loop(self, mock_create_client: Mock) -> None:
        """Test deletion handles unexpected exception in main loop."""
        mock_client = Mock()
        # Raise unexpected exception (not ClientError)
        mock_client.terminate_instances.side_effect = RuntimeError("Unexpected boto3 error")
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter(max_retries=2)
        success, error = deleter.delete_resource(
            resource_type="AWS::EC2::Instance",
            resource_id="i-exception",
            region="us-east-1",
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-exception",
        )

        assert success is False
        assert "Unexpected error" in error
        assert "Unexpected boto3 error" in error
        # Exception in _attempt_deletion gets caught and returned, no retry
        assert mock_client.terminate_instances.call_count == 1

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_handles_unexpected_exception_in_attempt(self, mock_create_client: Mock) -> None:
        """Test _attempt_deletion handles unexpected non-ClientError exception."""
        mock_client = Mock()
        # Raise unexpected exception during deletion attempt
        mock_client.delete_function.side_effect = ValueError("Unexpected internal error")
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::Lambda::Function",
            resource_id="my-function",
            region="us-west-2",
            arn="arn:aws:lambda:us-west-2:123456789012:function:my-function",
        )

        assert success is False
        assert "Unexpected error" in error
        assert "ValueError" in error or "Unexpected internal error" in error

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_iam_policy_uses_arn_parameter(self, mock_create_client: Mock) -> None:
        """Test IAM policy deletion uses ARN in parameter."""
        mock_client = Mock()
        mock_client.delete_policy.return_value = {}
        # Set up paginator for list_policy_versions (prerequisite cleanup)
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"Versions": []}]  # No versions to delete
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        policy_arn = "arn:aws:iam::123456789012:policy/MyCustomPolicy"
        success, error = deleter.delete_resource(
            resource_type="AWS::IAM::Policy",
            resource_id="MyCustomPolicy",
            region="us-east-1",
            arn=policy_arn,
        )

        assert success is True
        # Should use ARN parameter (PolicyArn contains "Arn")
        mock_client.delete_policy.assert_called_once_with(PolicyArn=policy_arn)

    def test_delete_handles_exception_from_attempt_deletion_with_retry(self) -> None:
        """Test deletion retries when _attempt_deletion itself raises an exception."""
        deleter = ResourceDeleter(max_retries=3)

        # Mock _attempt_deletion to raise exception twice, then succeed
        with patch.object(
            deleter,
            "_attempt_deletion",
            side_effect=[
                RuntimeError("Attempt failed"),
                RuntimeError("Attempt failed again"),
                (True, None),  # Success on third attempt
            ],
        ):
            success, error = deleter.delete_resource(
                resource_type="AWS::EC2::Instance",
                resource_id="i-retry",
                region="us-east-1",
                arn="arn:aws:ec2:us-east-1:123456789012:instance/i-retry",
            )

        # Should eventually succeed after retries
        assert success is True
        assert error is None

    def test_delete_handles_exception_from_attempt_deletion_exhausts_retries(self) -> None:
        """Test deletion fails after exhausting retries when _attempt_deletion raises exceptions."""
        deleter = ResourceDeleter(max_retries=2)

        # Mock _attempt_deletion to always raise exception
        with patch.object(deleter, "_attempt_deletion", side_effect=RuntimeError("Always fails")):
            success, error = deleter.delete_resource(
                resource_type="AWS::EC2::Instance",
                resource_id="i-always-fail",
                region="us-east-1",
                arn="arn:aws:ec2:us-east-1:123456789012:instance/i-always-fail",
            )

        # Should fail after exhausting retries
        assert success is False
        assert "Unexpected error deleting" in error
        assert "AWS::EC2::Instance" in error
        assert "i-always-fail" in error
        assert "Always fails" in error


class TestResourcePrerequisites:
    """Test suite for resource prerequisite cleanup methods."""

    def test_resources_with_prerequisites_constant(self) -> None:
        """Test RESOURCES_WITH_PREREQUISITES includes expected types."""
        assert "AWS::S3::Bucket" in RESOURCES_WITH_PREREQUISITES
        assert "AWS::IAM::Role" in RESOURCES_WITH_PREREQUISITES
        assert "AWS::IAM::User" in RESOURCES_WITH_PREREQUISITES

    def test_prepare_for_deletion_skips_non_prerequisite_resources(self) -> None:
        """Test _prepare_for_deletion skips resources without prerequisites."""
        deleter = ResourceDeleter()
        success, error = deleter._prepare_for_deletion(
            resource_type="AWS::EC2::Instance",
            resource_id="i-123456",
            region="us-east-1",
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-123456",
        )
        assert success is True
        assert error is None


class TestS3BucketEmptying:
    """Test suite for S3 bucket emptying logic."""

    @patch("src.restore.deleter.create_boto_client")
    def test_empty_s3_bucket_with_objects(self, mock_create_client: Mock) -> None:
        """Test emptying S3 bucket with objects."""
        mock_client = Mock()
        # No object lock
        mock_client.get_object_lock_configuration.side_effect = ClientError(
            {"Error": {"Code": "ObjectLockConfigurationNotFoundError"}},
            "GetObjectLockConfiguration",
        )
        # Mock objects in bucket
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [
            {
                "Versions": [
                    {"Key": "file1.txt", "VersionId": "v1"},
                    {"Key": "file2.txt", "VersionId": "v2"},
                ],
                "DeleteMarkers": [
                    {"Key": "deleted.txt", "VersionId": "dm1"},
                ],
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.delete_objects.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter._empty_s3_bucket("test-bucket", "us-east-1")

        assert success is True
        assert error is None
        mock_client.delete_objects.assert_called_once()
        call_args = mock_client.delete_objects.call_args
        assert call_args[1]["Bucket"] == "test-bucket"
        assert len(call_args[1]["Delete"]["Objects"]) == 3

    @patch("src.restore.deleter.create_boto_client")
    def test_empty_s3_bucket_with_object_lock(self, mock_create_client: Mock) -> None:
        """Test emptying S3 bucket fails when object lock is enabled."""
        mock_client = Mock()
        mock_client.get_object_lock_configuration.return_value = {
            "ObjectLockConfiguration": {"ObjectLockEnabled": "Enabled"}
        }
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter._empty_s3_bucket("locked-bucket", "us-east-1")

        assert success is False
        assert "Object Lock enabled" in error

    @patch("src.restore.deleter.create_boto_client")
    def test_empty_s3_bucket_already_deleted(self, mock_create_client: Mock) -> None:
        """Test emptying bucket that no longer exists."""
        mock_client = Mock()
        mock_client.get_object_lock_configuration.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket"}},
            "GetObjectLockConfiguration",
        )
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter._empty_s3_bucket("gone-bucket", "us-east-1")

        assert success is True
        assert error is None

    @patch("src.restore.deleter.create_boto_client")
    def test_empty_s3_bucket_large_batch(self, mock_create_client: Mock) -> None:
        """Test emptying S3 bucket with more than 1000 objects."""
        mock_client = Mock()
        mock_client.get_object_lock_configuration.side_effect = ClientError(
            {"Error": {"Code": "ObjectLockConfigurationNotFoundError"}},
            "GetObjectLockConfiguration",
        )
        # Create 1500 objects to test batching
        objects = [{"Key": f"file{i}.txt", "VersionId": f"v{i}"} for i in range(1500)]
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"Versions": objects, "DeleteMarkers": []}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.delete_objects.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter._empty_s3_bucket("big-bucket", "us-east-1")

        assert success is True
        # Should have called delete_objects twice (1000 + 500)
        assert mock_client.delete_objects.call_count == 2


class TestIAMRoleCleanup:
    """Test suite for IAM role cleanup logic."""

    @patch("src.restore.deleter.create_boto_client")
    def test_cleanup_iam_role_with_policies(self, mock_create_client: Mock) -> None:
        """Test IAM role cleanup detaches policies."""
        mock_client = Mock()
        # Mock attached policies
        attached_paginator = Mock()
        attached_paginator.paginate.return_value = [
            {"AttachedPolicies": [{"PolicyArn": "arn:aws:iam::aws:policy/ReadOnlyAccess"}]}
        ]
        # Mock inline policies
        inline_paginator = Mock()
        inline_paginator.paginate.return_value = [{"PolicyNames": ["InlinePolicy1"]}]
        # Mock instance profiles
        profile_paginator = Mock()
        profile_paginator.paginate.return_value = [{"InstanceProfiles": [{"InstanceProfileName": "MyProfile"}]}]

        def get_paginator(name: str) -> Mock:
            if name == "list_attached_role_policies":
                return attached_paginator
            elif name == "list_role_policies":
                return inline_paginator
            elif name == "list_instance_profiles_for_role":
                return profile_paginator
            return Mock()

        mock_client.get_paginator.side_effect = get_paginator
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter._cleanup_iam_role("TestRole")

        assert success is True
        assert error is None
        mock_client.detach_role_policy.assert_called_once_with(
            RoleName="TestRole",
            PolicyArn="arn:aws:iam::aws:policy/ReadOnlyAccess",
        )
        mock_client.delete_role_policy.assert_called_once_with(
            RoleName="TestRole",
            PolicyName="InlinePolicy1",
        )
        mock_client.remove_role_from_instance_profile.assert_called_once_with(
            InstanceProfileName="MyProfile",
            RoleName="TestRole",
        )

    @patch("src.restore.deleter.create_boto_client")
    def test_cleanup_iam_role_not_found(self, mock_create_client: Mock) -> None:
        """Test IAM role cleanup when role doesn't exist."""
        mock_client = Mock()
        mock_client.get_paginator.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity", "Message": "Role not found"}},
            "ListAttachedRolePolicies",
        )
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter._cleanup_iam_role("NonExistentRole")

        assert success is True  # Already gone is success
        assert error is None


class TestIAMUserCleanup:
    """Test suite for IAM user cleanup logic."""

    @patch("src.restore.deleter.create_boto_client")
    def test_cleanup_iam_user_with_credentials(self, mock_create_client: Mock) -> None:
        """Test IAM user cleanup removes all credentials and associations."""
        mock_client = Mock()

        # Mock access keys
        access_keys_paginator = Mock()
        access_keys_paginator.paginate.return_value = [{"AccessKeyMetadata": [{"AccessKeyId": "AKIAIOSFODNN7EXAMPLE"}]}]
        # Mock MFA devices
        mfa_paginator = Mock()
        mfa_paginator.paginate.return_value = [
            {"MFADevices": [{"SerialNumber": "arn:aws:iam::123456789012:mfa/testuser"}]}
        ]
        # Mock signing certs
        certs_paginator = Mock()
        certs_paginator.paginate.return_value = [{"Certificates": []}]
        # Mock SSH keys
        ssh_paginator = Mock()
        ssh_paginator.paginate.return_value = [{"SSHPublicKeys": []}]
        # Mock attached policies
        attached_paginator = Mock()
        attached_paginator.paginate.return_value = [
            {"AttachedPolicies": [{"PolicyArn": "arn:aws:iam::aws:policy/IAMUserChangePassword"}]}
        ]
        # Mock inline policies
        inline_paginator = Mock()
        inline_paginator.paginate.return_value = [{"PolicyNames": []}]
        # Mock groups
        groups_paginator = Mock()
        groups_paginator.paginate.return_value = [{"Groups": [{"GroupName": "Developers"}]}]

        def get_paginator(name: str) -> Mock:
            mapping = {
                "list_access_keys": access_keys_paginator,
                "list_mfa_devices": mfa_paginator,
                "list_signing_certificates": certs_paginator,
                "list_ssh_public_keys": ssh_paginator,
                "list_attached_user_policies": attached_paginator,
                "list_user_policies": inline_paginator,
                "list_groups_for_user": groups_paginator,
            }
            return mapping.get(name, Mock())

        mock_client.get_paginator.side_effect = get_paginator
        mock_client.list_service_specific_credentials.return_value = {"ServiceSpecificCredentials": []}
        mock_client.delete_login_profile.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter._cleanup_iam_user("testuser")

        assert success is True
        assert error is None
        mock_client.delete_access_key.assert_called_once_with(
            UserName="testuser",
            AccessKeyId="AKIAIOSFODNN7EXAMPLE",
        )
        mock_client.deactivate_mfa_device.assert_called_once()
        mock_client.detach_user_policy.assert_called_once_with(
            UserName="testuser",
            PolicyArn="arn:aws:iam::aws:policy/IAMUserChangePassword",
        )
        mock_client.remove_user_from_group.assert_called_once_with(
            GroupName="Developers",
            UserName="testuser",
        )

    @patch("src.restore.deleter.create_boto_client")
    def test_cleanup_iam_user_not_found(self, mock_create_client: Mock) -> None:
        """Test IAM user cleanup when user doesn't exist."""
        mock_client = Mock()
        mock_client.get_paginator.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity", "Message": "User not found"}},
            "ListAccessKeys",
        )
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter._cleanup_iam_user("NonExistentUser")

        assert success is True  # Already gone is success
        assert error is None

    @patch("src.restore.deleter.create_boto_client")
    def test_cleanup_iam_user_no_login_profile(self, mock_create_client: Mock) -> None:
        """Test IAM user cleanup handles missing login profile."""
        mock_client = Mock()
        # Empty paginators
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.list_service_specific_credentials.return_value = {"ServiceSpecificCredentials": []}
        # Login profile doesn't exist
        mock_client.delete_login_profile.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity", "Message": "Login Profile not found"}},
            "DeleteLoginProfile",
        )
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter._cleanup_iam_user("userwithnologin")

        assert success is True
        assert error is None


class TestSSMParameterDeletion:
    """Test suite for SSM Parameter deletion."""

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_ssm_parameter(self, mock_create_client: Mock) -> None:
        """Test SSM Parameter deletion."""
        mock_client = Mock()
        mock_client.delete_parameter.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::SSM::Parameter",
            resource_id="/my/parameter",
            region="us-east-1",
            arn="arn:aws:ssm:us-east-1:123456789012:parameter/my/parameter",
        )

        assert success is True
        assert error is None
        mock_client.delete_parameter.assert_called_once_with(Name="/my/parameter")


class TestStepFunctionsDeletion:
    """Test suite for Step Functions state machine deletion."""

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_state_machine(self, mock_create_client: Mock) -> None:
        """Test Step Functions state machine deletion uses ARN."""
        mock_client = Mock()
        mock_client.delete_state_machine.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        state_machine_arn = "arn:aws:states:us-east-1:123456789012:stateMachine:MyStateMachine"
        success, error = deleter.delete_resource(
            resource_type="AWS::StepFunctions::StateMachine",
            resource_id="MyStateMachine",
            region="us-east-1",
            arn=state_machine_arn,
        )

        assert success is True
        assert error is None
        # Should use ARN parameter (stateMachineArn contains "Arn")
        mock_client.delete_state_machine.assert_called_once_with(stateMachineArn=state_machine_arn)


class TestCodeBuildDeletion:
    """Test suite for CodeBuild project deletion."""

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_codebuild_project(self, mock_create_client: Mock) -> None:
        """Test CodeBuild project deletion."""
        mock_client = Mock()
        mock_client.delete_project.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::CodeBuild::Project",
            resource_id="my-build-project",
            region="us-east-1",
            arn="arn:aws:codebuild:us-east-1:123456789012:project/my-build-project",
        )

        assert success is True
        assert error is None
        mock_client.delete_project.assert_called_once_with(name="my-build-project")


class TestEventBridgeRuleDeletion:
    """Test suite for EventBridge rule deletion."""

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_eventbridge_rule_with_targets(self, mock_create_client: Mock) -> None:
        """Test EventBridge rule deletion removes targets first."""
        mock_client = Mock()
        # Mock targets exist
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"Targets": [{"Id": "target-1"}, {"Id": "target-2"}]}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.remove_targets.return_value = {}
        mock_client.delete_rule.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::Events::Rule",
            resource_id="my-rule",
            region="us-east-1",
            arn="arn:aws:events:us-east-1:123456789012:rule/my-rule",
        )

        assert success is True
        assert error is None
        # Should have removed targets first
        mock_client.remove_targets.assert_called_once_with(
            Rule="my-rule",
            Ids=["target-1", "target-2"],
        )
        # Then deleted the rule
        mock_client.delete_rule.assert_called_once_with(Name="my-rule")

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_eventbridge_rule_no_targets(self, mock_create_client: Mock) -> None:
        """Test EventBridge rule deletion with no targets."""
        mock_client = Mock()
        # Mock no targets
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"Targets": []}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.delete_rule.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::Events::Rule",
            resource_id="empty-rule",
            region="us-east-1",
            arn="arn:aws:events:us-east-1:123456789012:rule/empty-rule",
        )

        assert success is True
        assert error is None
        # Should NOT have called remove_targets
        mock_client.remove_targets.assert_not_called()
        mock_client.delete_rule.assert_called_once()

    @patch("src.restore.deleter.create_boto_client")
    def test_cleanup_eventbridge_rule_already_deleted(self, mock_create_client: Mock) -> None:
        """Test EventBridge rule cleanup when rule doesn't exist."""
        mock_client = Mock()
        mock_paginator = Mock()
        mock_paginator.paginate.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Rule not found"}},
            "ListTargetsByRule",
        )
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter._cleanup_eventbridge_rule("deleted-rule", "us-east-1")

        assert success is True  # Already gone is success
        assert error is None

    @patch("src.restore.deleter.create_boto_client")
    def test_cleanup_eventbridge_rule_many_targets(self, mock_create_client: Mock) -> None:
        """Test EventBridge rule cleanup with more than 10 targets (batch limit)."""
        mock_client = Mock()
        # Mock 15 targets to test batching
        targets = [{"Id": f"target-{i}"} for i in range(15)]
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{"Targets": targets}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.remove_targets.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter._cleanup_eventbridge_rule("busy-rule", "us-east-1")

        assert success is True
        # Should have called remove_targets twice (10 + 5)
        assert mock_client.remove_targets.call_count == 2


class TestVPCEndpointDeletion:
    """Test suite for VPC Endpoint deletion."""

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_vpc_endpoint(self, mock_create_client: Mock) -> None:
        """Test VPC Endpoint deletion."""
        mock_client = Mock()
        mock_client.delete_vpc_endpoints.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::EC2::VPCEndpoint",
            resource_id="vpce-123456",
            region="us-east-1",
            arn="arn:aws:ec2:us-east-1:123456789012:vpc-endpoint/vpce-123456",
        )

        assert success is True
        assert error is None
        mock_client.delete_vpc_endpoints.assert_called_once_with(VpcEndpointIds=["vpce-123456"])


class TestCodePipelineDeletion:
    """Test suite for CodePipeline deletion."""

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_codepipeline(self, mock_create_client: Mock) -> None:
        """Test CodePipeline deletion."""
        mock_client = Mock()
        mock_client.delete_pipeline.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::CodePipeline::Pipeline",
            resource_id="my-pipeline",
            region="us-east-1",
            arn="arn:aws:codepipeline:us-east-1:123456789012:my-pipeline",
        )

        assert success is True
        assert error is None
        mock_client.delete_pipeline.assert_called_once_with(name="my-pipeline")


class TestCloudFormationDeletion:
    """Test suite for CloudFormation Stack deletion."""

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_cloudformation_stack(self, mock_create_client: Mock) -> None:
        """Test CloudFormation Stack deletion."""
        mock_client = Mock()
        mock_client.delete_stack.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::CloudFormation::Stack",
            resource_id="my-stack",
            region="us-east-1",
            arn="arn:aws:cloudformation:us-east-1:123456789012:stack/my-stack/guid",
        )

        assert success is True
        assert error is None
        mock_client.delete_stack.assert_called_once_with(StackName="my-stack")


class TestRoute53Deletion:
    """Test suite for Route53 Hosted Zone deletion."""

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_route53_zone_with_records(self, mock_create_client: Mock) -> None:
        """Test Route53 zone deletion removes records first."""
        mock_client = Mock()
        # Mock records in zone
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [
            {
                "ResourceRecordSets": [
                    {"Type": "NS", "Name": "example.com."},  # Skip
                    {"Type": "SOA", "Name": "example.com."},  # Skip
                    {"Type": "A", "Name": "www.example.com.", "TTL": 300, "ResourceRecords": [{"Value": "1.2.3.4"}]},
                ]
            }
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.change_resource_record_sets.return_value = {}
        mock_client.delete_hosted_zone.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::Route53::HostedZone",
            resource_id="Z123456789",
            region="us-east-1",
            arn="arn:aws:route53:::hostedzone/Z123456789",
        )

        assert success is True
        assert error is None
        # Should have deleted the A record
        mock_client.change_resource_record_sets.assert_called_once()

    @patch("src.restore.deleter.create_boto_client")
    def test_cleanup_route53_zone_already_deleted(self, mock_create_client: Mock) -> None:
        """Test Route53 zone cleanup when zone doesn't exist."""
        mock_client = Mock()
        mock_paginator = Mock()
        mock_paginator.paginate.side_effect = ClientError(
            {"Error": {"Code": "NoSuchHostedZone", "Message": "Zone not found"}},
            "ListResourceRecordSets",
        )
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter._cleanup_route53_hosted_zone("Z123456789")

        assert success is True
        assert error is None


class TestBackupDeletion:
    """Test suite for AWS Backup deletion."""

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_backup_plan(self, mock_create_client: Mock) -> None:
        """Test Backup Plan deletion."""
        mock_client = Mock()
        mock_client.delete_backup_plan.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::Backup::BackupPlan",
            resource_id="plan-123",
            region="us-east-1",
            arn="arn:aws:backup:us-east-1:123456789012:backup-plan:plan-123",
        )

        assert success is True
        assert error is None
        mock_client.delete_backup_plan.assert_called_once_with(BackupPlanId="plan-123")

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_backup_vault_with_recovery_points(self, mock_create_client: Mock) -> None:
        """Test Backup Vault deletion removes recovery points first."""
        mock_client = Mock()
        # Mock recovery points in vault
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [
            {"RecoveryPoints": [{"RecoveryPointArn": "arn:aws:backup:us-east-1:123:recovery-point:rp-1"}]}
        ]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.delete_recovery_point.return_value = {}
        mock_client.delete_backup_vault.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::Backup::BackupVault",
            resource_id="my-vault",
            region="us-east-1",
            arn="arn:aws:backup:us-east-1:123456789012:backup-vault:my-vault",
        )

        assert success is True
        # Should have deleted the recovery point
        mock_client.delete_recovery_point.assert_called_once()


class TestWAFDeletion:
    """Test suite for WAF WebACL and RuleGroup deletion."""

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_waf_webacl(self, mock_create_client: Mock) -> None:
        """Test WAF WebACL deletion with disassociation."""
        mock_client = Mock()
        # Mock get_web_acl returns LockToken
        mock_client.get_web_acl.return_value = {"LockToken": "token-123", "WebACL": {}}
        # Mock no associated resources
        mock_client.list_resources_for_web_acl.return_value = {"ResourceArns": []}
        mock_client.delete_web_acl.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        # The cleanup method handles everything for WAF
        success, error = deleter._cleanup_waf_webacl(
            webacl_id="webacl-123",
            arn="arn:aws:wafv2:us-east-1:123456789012:regional/webacl/my-webacl/webacl-123",
            region="us-east-1",
        )

        assert success is True
        assert error is None
        mock_client.delete_web_acl.assert_called_once()

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_waf_webacl_with_associations(self, mock_create_client: Mock) -> None:
        """Test WAF WebACL deletion disassociates resources first."""
        mock_client = Mock()
        mock_client.get_web_acl.return_value = {"LockToken": "token-123", "WebACL": {}}
        # Mock associated ALB
        mock_client.list_resources_for_web_acl.return_value = {
            "ResourceArns": ["arn:aws:elasticloadbalancing:us-east-1:123:loadbalancer/app/my-alb/123"]
        }
        mock_client.disassociate_web_acl.return_value = {}
        mock_client.delete_web_acl.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter._cleanup_waf_webacl(
            webacl_id="webacl-123",
            arn="arn:aws:wafv2:us-east-1:123456789012:regional/webacl/my-webacl/webacl-123",
            region="us-east-1",
        )

        assert success is True
        # Should have disassociated the ALB
        mock_client.disassociate_web_acl.assert_called()

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_waf_rulegroup(self, mock_create_client: Mock) -> None:
        """Test WAF RuleGroup deletion."""
        mock_client = Mock()
        mock_client.get_rule_group.return_value = {"LockToken": "token-456", "RuleGroup": {}}
        mock_client.delete_rule_group.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter._cleanup_waf_rulegroup(
            rulegroup_id="rg-123",
            arn="arn:aws:wafv2:us-east-1:123456789012:regional/rulegroup/my-rulegroup/rg-123",
            region="us-east-1",
        )

        assert success is True
        assert error is None
        mock_client.delete_rule_group.assert_called_once()

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_waf_webacl_already_deleted(self, mock_create_client: Mock) -> None:
        """Test WAF WebACL cleanup when already deleted."""
        mock_client = Mock()
        mock_client.get_web_acl.side_effect = ClientError(
            {"Error": {"Code": "WAFNonexistentItemException", "Message": "Not found"}},
            "GetWebACL",
        )
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter._cleanup_waf_webacl(
            webacl_id="webacl-123",
            arn="arn:aws:wafv2:us-east-1:123456789012:regional/webacl/my-webacl/webacl-123",
            region="us-east-1",
        )

        assert success is True
        assert error is None


class TestResourceDeleterAdditionalCoverage:
    """Additional tests for edge cases and branches."""

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_resource_prerequisite_failure(self, mock_create_client: Mock) -> None:
        """Test deletion fails when prerequisite cleanup fails."""
        mock_client = Mock()
        # S3 bucket with object lock enabled (cannot be emptied)
        mock_client.get_object_lock_configuration.return_value = {
            "ObjectLockConfiguration": {
                "ObjectLockEnabled": "Enabled",
                "Rule": {"DefaultRetention": {"Mode": "COMPLIANCE"}}
            }
        }
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::S3::Bucket",
            resource_id="locked-bucket",
            region="us-east-1",
            arn="arn:aws:s3:::locked-bucket",
        )

        assert success is False
        assert error is not None
        assert "Object Lock" in error or "prerequisite" in error.lower() or "cannot be emptied" in error.lower()

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_iam_user_success(self, mock_create_client: Mock) -> None:
        """Test successful IAM user deletion with cleanup."""
        mock_client = Mock()
        mock_client.delete_user.return_value = {}
        # Mock empty lists for all cleanup operations
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.list_access_keys.return_value = {"AccessKeyMetadata": []}
        mock_client.list_mfa_devices.return_value = {"MFADevices": []}
        mock_client.list_service_specific_credentials.return_value = {"ServiceSpecificCredentials": []}
        mock_client.delete_login_profile.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity"}}, "DeleteLoginProfile"
        )
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::IAM::User",
            resource_id="test-user",
            region="us-east-1",
            arn="arn:aws:iam::123456789012:user/test-user",
        )

        assert success is True
        assert error is None

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_waf_webacl_via_delete_resource(self, mock_create_client: Mock) -> None:
        """Test WAF WebACL deletion through delete_resource method."""
        mock_client = Mock()
        # For cleanup
        mock_client.get_web_acl.return_value = {
            "WebACL": {"ARN": "arn:aws:wafv2:us-east-1:123456789012:regional/webacl/my-webacl/id"},
            "LockToken": "lock-token-123"
        }
        mock_client.list_resources_for_web_acl.return_value = {"ResourceArns": []}
        mock_client.delete_web_acl.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::WAFv2::WebACL",
            resource_id="webacl-123",
            region="us-east-1",
            arn="arn:aws:wafv2:us-east-1:123456789012:regional/webacl/my-webacl/webacl-123",
        )

        assert success is True
        assert error is None

    @patch("src.restore.deleter.create_boto_client")
    def test_delete_waf_rulegroup_via_delete_resource(self, mock_create_client: Mock) -> None:
        """Test WAF RuleGroup deletion through delete_resource method."""
        mock_client = Mock()
        mock_client.get_rule_group.return_value = {
            "RuleGroup": {},
            "LockToken": "lock-token-456"
        }
        mock_client.delete_rule_group.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::WAFv2::RuleGroup",
            resource_id="rulegroup-123",
            region="us-east-1",
            arn="arn:aws:wafv2:us-east-1:123456789012:regional/rulegroup/my-rulegroup/rulegroup-123",
        )

        assert success is True
        assert error is None

    @patch("src.restore.deleter.create_boto_client")
    def test_s3_bucket_fallback_for_non_versioned(self, mock_create_client: Mock) -> None:
        """Test S3 bucket emptying falls back for non-versioned buckets."""
        mock_client = Mock()
        mock_client.delete_bucket.return_value = {}
        # No object lock
        mock_client.get_object_lock_configuration.side_effect = ClientError(
            {"Error": {"Code": "ObjectLockConfigurationNotFoundError"}},
            "GetObjectLockConfiguration",
        )
        # Versioning fails, triggers fallback
        version_paginator = Mock()
        version_paginator.paginate.side_effect = ClientError(
            {"Error": {"Code": "NoSuchVersion", "Message": "Versioning not enabled"}},
            "ListObjectVersions"
        )
        object_paginator = Mock()
        object_paginator.paginate.return_value = [
            {"Contents": [{"Key": "file1.txt"}, {"Key": "file2.txt"}]}
        ]

        def get_paginator(operation):
            if operation == "list_object_versions":
                return version_paginator
            return object_paginator

        mock_client.get_paginator = get_paginator
        mock_client.delete_objects.return_value = {}
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter.delete_resource(
            resource_type="AWS::S3::Bucket",
            resource_id="non-versioned-bucket",
            region="us-east-1",
            arn="arn:aws:s3:::non-versioned-bucket",
        )

        assert success is True
        assert error is None
        mock_client.delete_objects.assert_called()

    @patch("src.restore.deleter.create_boto_client")
    def test_iam_user_cleanup_with_access_keys(self, mock_create_client: Mock) -> None:
        """Test IAM user cleanup with access keys."""
        mock_client = Mock()
        mock_client.delete_access_key.return_value = {}

        # Mock paginators for all operations
        def get_paginator_side_effect(operation):
            paginator = Mock()
            if operation == "list_access_keys":
                paginator.paginate.return_value = [
                    {"AccessKeyMetadata": [{"AccessKeyId": "AKIAIOSFODNN7EXAMPLE"}]}
                ]
            elif operation == "list_mfa_devices":
                paginator.paginate.return_value = [{"MFADevices": []}]
            else:
                paginator.paginate.return_value = [{}]
            return paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.list_service_specific_credentials.return_value = {"ServiceSpecificCredentials": []}
        mock_client.delete_login_profile.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity"}}, "DeleteLoginProfile"
        )
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter._cleanup_iam_user("test-user")

        assert success is True
        assert error is None
        mock_client.delete_access_key.assert_called_once()

    @patch("src.restore.deleter.create_boto_client")
    def test_iam_user_cleanup_with_mfa_devices(self, mock_create_client: Mock) -> None:
        """Test IAM user cleanup with MFA devices."""
        mock_client = Mock()
        mock_client.deactivate_mfa_device.return_value = {}
        mock_client.delete_virtual_mfa_device.return_value = {}

        def get_paginator_side_effect(operation):
            paginator = Mock()
            if operation == "list_access_keys":
                paginator.paginate.return_value = [{"AccessKeyMetadata": []}]
            elif operation == "list_mfa_devices":
                paginator.paginate.return_value = [
                    {"MFADevices": [{"SerialNumber": "arn:aws:iam::123456789012:mfa/user-mfa"}]}
                ]
            else:
                paginator.paginate.return_value = [{}]
            return paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.list_service_specific_credentials.return_value = {"ServiceSpecificCredentials": []}
        mock_client.delete_login_profile.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity"}}, "DeleteLoginProfile"
        )
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter._cleanup_iam_user("test-user")

        assert success is True
        assert error is None
        mock_client.deactivate_mfa_device.assert_called_once()

    @patch("src.restore.deleter.create_boto_client")
    def test_iam_user_cleanup_mfa_delete_fails(self, mock_create_client: Mock) -> None:
        """Test IAM user cleanup continues when MFA device deletion fails."""
        mock_client = Mock()
        mock_client.list_access_keys.return_value = {"AccessKeyMetadata": []}
        mock_client.list_mfa_devices.return_value = {
            "MFADevices": [{"SerialNumber": "arn:aws:iam::123456789012:mfa/user-mfa"}]
        }
        mock_client.deactivate_mfa_device.return_value = {}
        # Hardware MFA device cannot be deleted
        mock_client.delete_virtual_mfa_device.side_effect = ClientError(
            {"Error": {"Code": "InvalidInput", "Message": "Cannot delete hardware device"}},
            "DeleteVirtualMFADevice"
        )
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.list_service_specific_credentials.return_value = {"ServiceSpecificCredentials": []}
        mock_client.delete_login_profile.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity"}}, "DeleteLoginProfile"
        )
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter._cleanup_iam_user("test-user")

        # Should still succeed - MFA delete failure is ignored
        assert success is True

    @patch("src.restore.deleter.create_boto_client")
    def test_iam_user_cleanup_with_signing_certificates(self, mock_create_client: Mock) -> None:
        """Test IAM user cleanup with signing certificates."""
        mock_client = Mock()
        mock_client.list_access_keys.return_value = {"AccessKeyMetadata": []}
        mock_client.list_mfa_devices.return_value = {"MFADevices": []}

        # Mock paginator for signing certificates
        def get_paginator_side_effect(operation):
            paginator = Mock()
            if operation == "list_signing_certificates":
                paginator.paginate.return_value = [
                    {"Certificates": [{"CertificateId": "cert-123"}]}
                ]
            elif operation == "list_ssh_public_keys":
                paginator.paginate.return_value = [{}]
            else:
                paginator.paginate.return_value = [{}]
            return paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.delete_signing_certificate.return_value = {}
        mock_client.list_service_specific_credentials.return_value = {"ServiceSpecificCredentials": []}
        mock_client.delete_login_profile.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity"}}, "DeleteLoginProfile"
        )
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter._cleanup_iam_user("test-user")

        assert success is True
        mock_client.delete_signing_certificate.assert_called_once()

    @patch("src.restore.deleter.create_boto_client")
    def test_iam_user_cleanup_with_ssh_keys(self, mock_create_client: Mock) -> None:
        """Test IAM user cleanup with SSH public keys."""
        mock_client = Mock()
        mock_client.list_access_keys.return_value = {"AccessKeyMetadata": []}
        mock_client.list_mfa_devices.return_value = {"MFADevices": []}

        def get_paginator_side_effect(operation):
            paginator = Mock()
            if operation == "list_ssh_public_keys":
                paginator.paginate.return_value = [
                    {"SSHPublicKeys": [{"SSHPublicKeyId": "ssh-key-123"}]}
                ]
            else:
                paginator.paginate.return_value = [{}]
            return paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_client.delete_ssh_public_key.return_value = {}
        mock_client.list_service_specific_credentials.return_value = {"ServiceSpecificCredentials": []}
        mock_client.delete_login_profile.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity"}}, "DeleteLoginProfile"
        )
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter._cleanup_iam_user("test-user")

        assert success is True
        mock_client.delete_ssh_public_key.assert_called_once()

    @patch("src.restore.deleter.create_boto_client")
    def test_iam_user_cleanup_with_service_credentials(self, mock_create_client: Mock) -> None:
        """Test IAM user cleanup with service-specific credentials."""
        mock_client = Mock()
        mock_client.list_access_keys.return_value = {"AccessKeyMetadata": []}
        mock_client.list_mfa_devices.return_value = {"MFADevices": []}
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.list_service_specific_credentials.return_value = {
            "ServiceSpecificCredentials": [
                {"ServiceSpecificCredentialId": "cred-123", "ServiceName": "codecommit"}
            ]
        }
        mock_client.delete_service_specific_credential.return_value = {}
        mock_client.delete_login_profile.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity"}}, "DeleteLoginProfile"
        )
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter._cleanup_iam_user("test-user")

        assert success is True
        mock_client.delete_service_specific_credential.assert_called_once()

    @patch("src.restore.deleter.create_boto_client")
    def test_iam_user_cleanup_service_credentials_fails_gracefully(self, mock_create_client: Mock) -> None:
        """Test IAM user cleanup continues when service credentials listing fails."""
        mock_client = Mock()
        mock_client.list_access_keys.return_value = {"AccessKeyMetadata": []}
        mock_client.list_mfa_devices.return_value = {"MFADevices": []}
        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.list_service_specific_credentials.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied"}}, "ListServiceSpecificCredentials"
        )
        mock_client.delete_login_profile.side_effect = ClientError(
            {"Error": {"Code": "NoSuchEntity"}}, "DeleteLoginProfile"
        )
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter._cleanup_iam_user("test-user")

        # Should still succeed - service credentials failure is ignored
        assert success is True

    @patch("src.restore.deleter.create_boto_client")
    def test_prerequisite_cleanup_exception_handling(self, mock_create_client: Mock) -> None:
        """Test prerequisite cleanup catches unexpected exceptions."""
        mock_client = Mock()
        # Cause an unexpected exception
        mock_client.get_object_lock_configuration.side_effect = ValueError("Unexpected error")
        mock_create_client.return_value = mock_client

        deleter = ResourceDeleter()
        success, error = deleter._prepare_for_deletion(
            resource_type="AWS::S3::Bucket",
            resource_id="test-bucket",
            region="us-east-1",
            arn="arn:aws:s3:::test-bucket",
        )

        assert success is False
        assert "Prerequisite cleanup failed" in error
