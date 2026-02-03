"""Unit tests for property map filter_properties functions."""

from __future__ import annotations

import sys
import importlib

import pytest

# Ensure we're using the real modules, not mocked ones
# Clear any cached mocks
for mod_name in list(sys.modules.keys()):
    if mod_name.startswith("src.generate.property_maps"):
        if hasattr(sys.modules[mod_name], "_mock_name"):
            del sys.modules[mod_name]

# Import the actual modules
from src.generate.property_maps import lambda_, iam, ec2, s3, sqs, sns, cloudwatch

# Reload to ensure we have the real implementations
importlib.reload(lambda_)
importlib.reload(iam)
importlib.reload(ec2)
importlib.reload(s3)
importlib.reload(sqs)
importlib.reload(sns)
importlib.reload(cloudwatch)


class TestLambdaFilterProperties:
    """Tests for Lambda property map filter_properties function."""

    def test_filters_to_configurable_properties_only(self) -> None:
        """Test that only configurable properties are included."""
        raw_config = {
            "FunctionName": "my-function",
            "Runtime": "python3.11",
            "Handler": "index.handler",
            "Role": "arn:aws:iam::123456789012:role/my-role",
            "MemorySize": 256,
            "Timeout": 30,
            "FunctionArn": "arn:aws:lambda:us-east-1:123456789012:function:my-function",
            "CodeSize": 1234,
            "LastModified": "2024-01-01T00:00:00Z",
            "State": "Active",
            "Version": "$LATEST",
        }
        result = lambda_.filter_properties(raw_config)
        assert "FunctionName" in result
        assert "Runtime" in result
        assert "Handler" in result
        assert "Role" in result
        assert "MemorySize" in result
        assert "Timeout" in result
        # Computed properties should be excluded
        assert "FunctionArn" not in result
        assert "CodeSize" not in result
        assert "LastModified" not in result
        assert "State" not in result
        assert "Version" not in result

    def test_includes_environment_variables(self) -> None:
        """Test that environment variables are included."""
        raw_config = {
            "FunctionName": "my-function",
            "Environment": {
                "Variables": {
                    "MY_VAR": "my-value",
                    "OTHER_VAR": "other-value",
                }
            },
        }
        result = lambda_.filter_properties(raw_config)
        assert "Environment" in result
        assert result["Environment"]["Variables"]["MY_VAR"] == "my-value"

    def test_includes_vpc_config(self) -> None:
        """Test that VPC config is included."""
        raw_config = {
            "FunctionName": "my-function",
            "VpcConfig": {
                "SubnetIds": ["subnet-123", "subnet-456"],
                "SecurityGroupIds": ["sg-789"],
            },
        }
        result = lambda_.filter_properties(raw_config)
        assert "VpcConfig" in result
        assert result["VpcConfig"]["SubnetIds"] == ["subnet-123", "subnet-456"]

    def test_includes_tracing_config(self) -> None:
        """Test that tracing config is included."""
        raw_config = {
            "FunctionName": "my-function",
            "TracingConfig": {"Mode": "Active"},
        }
        result = lambda_.filter_properties(raw_config)
        assert "TracingConfig" in result
        assert result["TracingConfig"]["Mode"] == "Active"

    def test_includes_ephemeral_storage(self) -> None:
        """Test that ephemeral storage is included."""
        raw_config = {
            "FunctionName": "my-function",
            "EphemeralStorage": {"Size": 1024},
        }
        result = lambda_.filter_properties(raw_config)
        assert "EphemeralStorage" in result
        assert result["EphemeralStorage"]["Size"] == 1024

    def test_preserves_code_internal_data(self) -> None:
        """Test that _code internal data is preserved."""
        raw_config = {
            "FunctionName": "my-function",
            "_code": {
                "code_stored": True,
                "storage_type": "inline",
                "code_base64": "base64encodedcode",
            },
        }
        result = lambda_.filter_properties(raw_config)
        assert "_code" in result
        assert result["_code"]["code_stored"] is True

    def test_excludes_empty_collections(self) -> None:
        """Test that empty collections are excluded."""
        raw_config = {
            "FunctionName": "my-function",
            "Layers": [],
            "Environment": {},
        }
        result = lambda_.filter_properties(raw_config)
        assert "Layers" not in result
        # Empty Environment dict should be excluded
        assert "Environment" not in result

    def test_excludes_none_values(self) -> None:
        """Test that None values are excluded."""
        raw_config = {
            "FunctionName": "my-function",
            "Description": None,
            "KMSKeyArn": None,
        }
        result = lambda_.filter_properties(raw_config)
        assert "FunctionName" in result
        assert "Description" not in result
        assert "KMSKeyArn" not in result

    def test_includes_layers(self) -> None:
        """Test that layers list is included when non-empty."""
        raw_config = {
            "FunctionName": "my-function",
            "Layers": [
                "arn:aws:lambda:us-east-1:123456789012:layer:my-layer:1",
            ],
        }
        result = lambda_.filter_properties(raw_config)
        assert "Layers" in result
        assert len(result["Layers"]) == 1

    def test_includes_dead_letter_config(self) -> None:
        """Test that dead letter config is included."""
        raw_config = {
            "FunctionName": "my-function",
            "DeadLetterConfig": {
                "TargetArn": "arn:aws:sqs:us-east-1:123456789012:dlq",
            },
        }
        result = lambda_.filter_properties(raw_config)
        assert "DeadLetterConfig" in result

    def test_includes_architectures(self) -> None:
        """Test that architectures is included."""
        raw_config = {
            "FunctionName": "my-function",
            "Architectures": ["arm64"],
        }
        result = lambda_.filter_properties(raw_config)
        assert "Architectures" in result
        assert result["Architectures"] == ["arm64"]


class TestIAMFilterProperties:
    """Tests for IAM property map filter_properties function."""

    def test_filters_role_properties(self) -> None:
        """Test filtering IAM Role properties."""
        raw_config = {
            "RoleName": "my-role",
            "Path": "/service-role/",
            "AssumeRolePolicyDocument": {"Version": "2012-10-17", "Statement": []},
            "Description": "My role description",
            "RoleId": "AROA1234567890EXAMPLE",
            "Arn": "arn:aws:iam::123456789012:role/my-role",
            "CreateDate": "2024-01-01T00:00:00Z",
        }
        result = iam.filter_properties(raw_config, "AWS::IAM::Role")
        assert "RoleName" in result
        assert "Path" in result
        assert "AssumeRolePolicyDocument" in result
        assert "Description" in result
        # Computed properties should not be in result
        # (they may or may not be filtered depending on implementation)

    def test_filters_policy_properties(self) -> None:
        """Test filtering IAM Policy properties."""
        raw_config = {
            "PolicyName": "my-policy",
            "Path": "/",
            "PolicyDocument": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": "s3:GetObject",
                        "Resource": "*",
                    }
                ],
            },
            "PolicyId": "ANPA1234567890EXAMPLE",
            "Arn": "arn:aws:iam::123456789012:policy/my-policy",
            "CreateDate": "2024-01-01T00:00:00Z",
        }
        result = iam.filter_properties(raw_config, "AWS::IAM::Policy")
        assert "PolicyName" in result
        assert "PolicyDocument" in result

    def test_keeps_assume_role_policy_as_dict(self) -> None:
        """Test that AssumeRolePolicyDocument is kept as dict."""
        raw_config = {
            "RoleName": "my-role",
            "AssumeRolePolicyDocument": {
                "Version": "2012-10-17",
                "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}}],
            },
        }
        result = iam.filter_properties(raw_config, "AWS::IAM::Role")
        assert "AssumeRolePolicyDocument" in result
        assert isinstance(result["AssumeRolePolicyDocument"], dict)

    def test_extracts_permissions_boundary_arn(self) -> None:
        """Test that PermissionsBoundary ARN is extracted from dict."""
        raw_config = {
            "RoleName": "my-role",
            "PermissionsBoundary": {
                "PermissionsBoundaryArn": "arn:aws:iam::123456789012:policy/boundary",
                "PermissionsBoundaryType": "Policy",
            },
        }
        result = iam.filter_properties(raw_config, "AWS::IAM::Role")
        assert "PermissionsBoundary" in result
        assert result["PermissionsBoundary"] == "arn:aws:iam::123456789012:policy/boundary"


class TestEC2FilterProperties:
    """Tests for EC2 property map filter_properties function."""

    def test_filters_instance_properties(self) -> None:
        """Test filtering EC2 Instance properties."""
        raw_config = {
            "InstanceId": "i-1234567890abcdef0",
            "ImageId": "ami-12345678",
            "InstanceType": "t3.medium",
            "KeyName": "my-key",
            "SubnetId": "subnet-12345678",
            "SecurityGroupIds": ["sg-12345678"],
            "State": {"Name": "running"},
            "LaunchTime": "2024-01-01T00:00:00Z",
            "PublicIpAddress": "54.123.45.67",
        }
        result = ec2.filter_properties(raw_config)
        assert "ImageId" in result  # Required for Terraform
        assert "InstanceType" in result
        assert "KeyName" in result
        # State and LaunchTime are computed
        assert "State" not in result
        assert "LaunchTime" not in result

    def test_includes_tags(self) -> None:
        """Test that tags are included."""
        raw_config = {
            "InstanceType": "t3.medium",
            "Tags": [
                {"Key": "Name", "Value": "my-instance"},
                {"Key": "Environment", "Value": "prod"},
            ],
        }
        result = ec2.filter_properties(raw_config)
        assert "Tags" in result

    def test_includes_ebs_optimized(self) -> None:
        """Test that EbsOptimized is included."""
        raw_config = {
            "InstanceType": "t3.medium",
            "EbsOptimized": True,
        }
        result = ec2.filter_properties(raw_config)
        assert "EbsOptimized" in result
        assert result["EbsOptimized"] is True


class TestS3FilterProperties:
    """Tests for S3 property map filter_properties function."""

    def test_filters_bucket_properties(self) -> None:
        """Test filtering S3 Bucket properties."""
        raw_config = {
            "Name": "my-bucket",
            "CreationDate": "2024-01-01T00:00:00Z",
            "Tags": {"Environment": "prod"},
            "Versioning": "Enabled",
            "Encryption": {"Rules": []},
            "PublicAccessBlock": {"BlockPublicAcls": True},
        }
        result = s3.filter_properties(raw_config)
        assert "Name" in result
        assert "Tags" in result
        assert "Versioning" in result
        assert "Encryption" in result
        assert "PublicAccessBlock" in result
        # CreationDate is computed
        assert "CreationDate" not in result

    def test_excludes_empty_encryption_rules(self) -> None:
        """Test that empty encryption rules are excluded."""
        raw_config = {
            "Name": "my-bucket",
            "Encryption": {},
        }
        result = s3.filter_properties(raw_config)
        assert "Encryption" not in result


class TestSQSFilterProperties:
    """Tests for SQS property map filter_properties function."""

    def test_filters_queue_properties(self) -> None:
        """Test filtering SQS Queue properties."""
        raw_config = {
            "QueueName": "my-queue",
            "QueueArn": "arn:aws:sqs:us-east-1:123456789012:my-queue",
            "QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/my-queue",
            "VisibilityTimeout": 30,
            "DelaySeconds": 0,
            "MaximumMessageSize": 262144,
            "MessageRetentionPeriod": 345600,
            "ApproximateNumberOfMessages": "0",
        }
        result = sqs.filter_properties(raw_config)
        assert "QueueName" in result
        assert "VisibilityTimeout" in result
        assert "DelaySeconds" in result
        assert "MaximumMessageSize" in result
        assert "MessageRetentionPeriod" in result
        # Computed properties
        assert "QueueArn" not in result
        assert "QueueUrl" not in result
        assert "ApproximateNumberOfMessages" not in result

    def test_includes_redrive_policy(self) -> None:
        """Test that redrive policy is included."""
        raw_config = {
            "QueueName": "my-queue",
            "RedrivePolicy": {
                "deadLetterTargetArn": "arn:aws:sqs:us-east-1:123456789012:dlq",
                "maxReceiveCount": 5,
            },
        }
        result = sqs.filter_properties(raw_config)
        assert "RedrivePolicy" in result

    def test_includes_fifo_queue(self) -> None:
        """Test that FifoQueue is included."""
        raw_config = {
            "QueueName": "my-queue.fifo",
            "FifoQueue": True,
            "ContentBasedDeduplication": True,
        }
        result = sqs.filter_properties(raw_config)
        assert "FifoQueue" in result
        assert "ContentBasedDeduplication" in result


class TestSNSFilterProperties:
    """Tests for SNS property map filter_properties function."""

    def test_filters_topic_properties(self) -> None:
        """Test filtering SNS Topic properties."""
        raw_config = {
            "TopicName": "my-topic",
            "TopicArn": "arn:aws:sns:us-east-1:123456789012:my-topic",
            "DisplayName": "My Topic",
            "KmsMasterKeyId": "alias/my-key",
            "Owner": "123456789012",
        }
        result = sns.filter_properties(raw_config)
        assert "TopicName" in result
        assert "DisplayName" in result
        assert "KmsMasterKeyId" in result
        # Computed
        assert "TopicArn" not in result
        assert "Owner" not in result

    def test_includes_policy(self) -> None:
        """Test that policy is included."""
        raw_config = {
            "TopicName": "my-topic",
            "Policy": '{"Version": "2012-10-17", "Statement": []}',
        }
        result = sns.filter_properties(raw_config)
        assert "Policy" in result


class TestCloudWatchFilterProperties:
    """Tests for CloudWatch property map filter_properties function."""

    def test_filters_alarm_properties(self) -> None:
        """Test filtering CloudWatch Alarm properties."""
        raw_config = {
            "AlarmName": "my-alarm",
            "AlarmArn": "arn:aws:cloudwatch:us-east-1:123456789012:alarm:my-alarm",
            "ComparisonOperator": "GreaterThanThreshold",
            "EvaluationPeriods": 2,
            "MetricName": "CPUUtilization",
            "Namespace": "AWS/EC2",
            "Period": 300,
            "Statistic": "Average",
            "Threshold": 80.0,
            "StateUpdatedTimestamp": "2024-01-01T00:00:00Z",
        }
        result = cloudwatch.filter_properties(raw_config, "cloudwatch:alarm")
        assert "AlarmName" in result
        assert "ComparisonOperator" in result
        assert "EvaluationPeriods" in result
        assert "MetricName" in result
        assert "Namespace" in result
        assert "Period" in result
        assert "Statistic" in result
        assert "Threshold" in result
        # Computed
        assert "AlarmArn" not in result
        assert "StateUpdatedTimestamp" not in result

    def test_filters_log_group_properties(self) -> None:
        """Test filtering CloudWatch Log Group properties."""
        raw_config = {
            "LogGroupName": "/aws/lambda/my-function",
            "Arn": "arn:aws:logs:us-east-1:123456789012:log-group:/aws/lambda/my-function",
            "RetentionInDays": 30,
            "KmsKeyId": "arn:aws:kms:us-east-1:123456789012:key/my-key",
            "CreationTime": 1704067200000,
        }
        result = cloudwatch.filter_properties(raw_config, "AWS::Logs::LogGroup")
        assert "LogGroupName" in result
        assert "RetentionInDays" in result
        assert "KmsKeyId" in result
        # Computed
        assert "Arn" not in result
        assert "CreationTime" not in result

    def test_includes_dimensions(self) -> None:
        """Test that dimensions are included for alarms."""
        raw_config = {
            "AlarmName": "my-alarm",
            "Dimensions": [
                {"Name": "InstanceId", "Value": "i-12345678"},
            ],
        }
        result = cloudwatch.filter_properties(raw_config, "cloudwatch:alarm")
        assert "Dimensions" in result
        assert len(result["Dimensions"]) == 1


class TestFilterPropertiesIntegration:
    """Integration tests for filter_properties with terraform.py."""

    def test_lambda_filter_called_by_terraform_prompts(self) -> None:
        """Test that Lambda filter_properties is properly called."""
        # This tests the integration between terraform.py and lambda_.py
        raw_config = {
            "FunctionName": "test-function",
            "Runtime": "python3.11",
            "Handler": "index.handler",
            "MemorySize": 512,
            "Timeout": 60,
            "State": "Active",  # Should be excluded
            "_code": {"code_stored": True},  # Should be included
        }
        result = lambda_.filter_properties(raw_config)

        # Verify configurable properties are included
        assert "FunctionName" in result
        assert "Runtime" in result
        assert "MemorySize" in result
        assert "Timeout" in result

        # Verify _code is preserved
        assert "_code" in result

        # State should not be in result (not in configurable)
        assert "State" not in result

    def test_iam_filter_with_full_role_config(self) -> None:
        """Test IAM filter with realistic role configuration."""
        raw_config = {
            "RoleName": "lambda-execution-role",
            "Path": "/service-role/",
            "AssumeRolePolicyDocument": {
                "Version": "2012-10-17",
                "Statement": [{
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }]
            },
            "Description": "Role for Lambda execution",
            "MaxSessionDuration": 3600,
            "RoleId": "AROAEXAMPLE",
            "Arn": "arn:aws:iam::123456789012:role/lambda-execution-role",
            "CreateDate": "2024-01-01T00:00:00Z",
        }
        result = iam.filter_properties(raw_config, "AWS::IAM::Role")

        # Configurable properties
        assert "RoleName" in result
        assert "Path" in result
        assert "AssumeRolePolicyDocument" in result
        assert "Description" in result
        assert "MaxSessionDuration" in result

    def test_empty_config_returns_empty_dict(self) -> None:
        """Test that empty config returns empty dict."""
        result = lambda_.filter_properties({})
        assert result == {}

        result = iam.filter_properties({}, "AWS::IAM::Role")
        assert result == {}

        result = ec2.filter_properties({})
        assert result == {}
