"""Tests for unsupported resource detection utility."""

from unittest.mock import MagicMock, patch

import pytest

from src.utils.unsupported_resources import (
    SUPPORTED_RESOURCE_TYPE_PREFIXES,
    UnsupportedResource,
    UnsupportedResourceReport,
    check_for_unsupported_resources_quick,
    detect_unsupported_resources,
    get_all_tagged_resources,
    get_unsupported_resource_summary,
    is_resource_type_supported,
)


class TestIsResourceTypeSupported:
    """Tests for is_resource_type_supported function."""

    def test_supported_s3_bucket(self):
        """Test that S3 buckets are supported."""
        assert is_resource_type_supported("s3:bucket") is True

    def test_supported_lambda_function(self):
        """Test that Lambda functions are supported."""
        assert is_resource_type_supported("lambda:function") is True

    def test_supported_ec2_instance(self):
        """Test that EC2 instances are supported."""
        assert is_resource_type_supported("ec2:instance") is True

    def test_supported_iam_role(self):
        """Test that IAM roles are supported."""
        assert is_resource_type_supported("iam:role") is True

    def test_supported_dynamodb_table(self):
        """Test that DynamoDB tables are supported."""
        assert is_resource_type_supported("dynamodb:table") is True

    def test_unsupported_unknown_service(self):
        """Test that unknown services are not supported."""
        assert is_resource_type_supported("unknownservice:resource") is False

    def test_unsupported_new_service(self):
        """Test that hypothetical new services are not supported."""
        assert is_resource_type_supported("newfancyservice2026:widget") is False

    def test_case_insensitive(self):
        """Test that matching is case insensitive."""
        assert is_resource_type_supported("S3:Bucket") is True
        assert is_resource_type_supported("LAMBDA:FUNCTION") is True


class TestGetAllTaggedResources:
    """Tests for get_all_tagged_resources function."""

    @patch("src.utils.unsupported_resources.boto3")
    def test_get_resources_single_region(self, mock_boto3):
        """Test getting tagged resources from a single region."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        mock_tagging_client = MagicMock()
        mock_session.client.return_value = mock_tagging_client

        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "ResourceTagMappingList": [
                    {
                        "ResourceARN": "arn:aws:s3:::my-bucket",
                        "Tags": [{"Key": "Environment", "Value": "test"}],
                    }
                ]
            }
        ]
        mock_tagging_client.get_paginator.return_value = mock_paginator

        resources = get_all_tagged_resources(mock_session, regions=["us-east-1"])

        assert len(resources) == 1
        arn, resource_type, tags, region = resources[0]
        assert arn == "arn:aws:s3:::my-bucket"
        assert tags == {"Environment": "test"}
        assert region == "us-east-1"

    @patch("src.utils.unsupported_resources.boto3")
    def test_get_resources_extracts_type_from_arn(self, mock_boto3):
        """Test that resource type is correctly extracted from ARN."""
        mock_session = MagicMock()
        mock_tagging_client = MagicMock()
        mock_session.client.return_value = mock_tagging_client

        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [
            {
                "ResourceTagMappingList": [
                    {"ResourceARN": "arn:aws:lambda:us-east-1:123456789012:function:my-func", "Tags": []},
                    {"ResourceARN": "arn:aws:ec2:us-east-1:123456789012:instance/i-123", "Tags": []},
                ]
            }
        ]
        mock_tagging_client.get_paginator.return_value = mock_paginator

        resources = get_all_tagged_resources(mock_session, regions=["us-east-1"])

        assert len(resources) == 2
        # Lambda function with colon separator
        assert resources[0][1] == "lambda:function"
        # EC2 instance with slash separator
        assert resources[1][1] == "ec2:instance"

    @patch("src.utils.unsupported_resources.boto3")
    def test_get_resources_handles_client_error(self, mock_boto3):
        """Test that client errors are handled gracefully."""
        from botocore.exceptions import ClientError

        mock_session = MagicMock()
        mock_tagging_client = MagicMock()
        mock_session.client.return_value = mock_tagging_client

        mock_paginator = MagicMock()
        mock_paginator.paginate.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}, "GetResources"
        )
        mock_tagging_client.get_paginator.return_value = mock_paginator

        resources = get_all_tagged_resources(mock_session, regions=["us-east-1"])

        # Should return empty list on error
        assert resources == []


class TestDetectUnsupportedResources:
    """Tests for detect_unsupported_resources function."""

    @patch("src.utils.unsupported_resources.get_all_tagged_resources")
    def test_detect_no_unsupported(self, mock_get_resources):
        """Test detection when all resources are supported."""
        mock_get_resources.return_value = [
            ("arn:aws:s3:::bucket1", "s3:bucket", {}, "us-east-1"),
            ("arn:aws:lambda:us-east-1:123:function:func1", "lambda:function", {}, "us-east-1"),
        ]

        report = detect_unsupported_resources()

        assert len(report.unsupported_resources) == 0
        assert len(report.unsupported_types) == 0
        assert len(report.supported_types) == 2
        assert report.total_resources_scanned == 2

    @patch("src.utils.unsupported_resources.get_all_tagged_resources")
    def test_detect_with_unsupported(self, mock_get_resources):
        """Test detection when there are unsupported resources."""
        mock_get_resources.return_value = [
            ("arn:aws:s3:::bucket1", "s3:bucket", {}, "us-east-1"),
            ("arn:aws:newservice:us-east-1:123:widget:widget1", "newservice:widget", {"App": "test"}, "us-east-1"),
        ]

        report = detect_unsupported_resources()

        assert len(report.unsupported_resources) == 1
        assert len(report.unsupported_types) == 1
        assert "newservice:widget" in report.unsupported_types
        assert len(report.supported_types) == 1
        assert report.total_resources_scanned == 2

    @patch("src.utils.unsupported_resources.get_all_tagged_resources")
    def test_detect_captures_resource_details(self, mock_get_resources):
        """Test that unsupported resource details are captured."""
        mock_get_resources.return_value = [
            ("arn:aws:fancy:us-west-2:123:thing:thing1", "fancy:thing", {"Team": "platform"}, "us-west-2"),
        ]

        report = detect_unsupported_resources()

        assert len(report.unsupported_resources) == 1
        resource = report.unsupported_resources[0]
        assert resource.resource_arn == "arn:aws:fancy:us-west-2:123:thing:thing1"
        assert resource.resource_type == "fancy:thing"
        assert resource.tags == {"Team": "platform"}
        assert resource.region == "us-west-2"


class TestGetUnsupportedResourceSummary:
    """Tests for get_unsupported_resource_summary function."""

    def test_summary_with_unsupported(self):
        """Test summary generation with unsupported resources."""
        report = UnsupportedResourceReport(
            unsupported_resources=[
                UnsupportedResource(
                    resource_arn="arn:aws:new:us-east-1:123:widget:w1",
                    resource_type="new:widget",
                    tags={},
                    region="us-east-1",
                ),
                UnsupportedResource(
                    resource_arn="arn:aws:new:us-east-1:123:widget:w2",
                    resource_type="new:widget",
                    tags={},
                    region="us-east-1",
                ),
            ],
            unsupported_types={"new:widget"},
            supported_types={"s3:bucket"},
            total_resources_scanned=10,
        )

        summary = get_unsupported_resource_summary(report)

        assert "Total resources scanned: 10" in summary
        assert "Unsupported resource types found: 1" in summary
        assert "new:widget: 2 resource(s)" in summary

    def test_summary_no_unsupported(self):
        """Test summary generation with no unsupported resources."""
        report = UnsupportedResourceReport(
            unsupported_resources=[],
            unsupported_types=set(),
            supported_types={"s3:bucket", "lambda:function"},
            total_resources_scanned=5,
        )

        summary = get_unsupported_resource_summary(report)

        assert "Total resources scanned: 5" in summary
        assert "Unsupported resource types found: 0" in summary
        assert "Supported resource types found: 2" in summary


class TestCheckForUnsupportedResourcesQuick:
    """Tests for check_for_unsupported_resources_quick function."""

    @patch("src.utils.unsupported_resources.boto3")
    def test_quick_check_no_unsupported(self, mock_boto3):
        """Test quick check when all resources are supported."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session.client.return_value = mock_client
        mock_client.get_resources.return_value = {
            "ResourceTagMappingList": [
                {"ResourceARN": "arn:aws:s3:::bucket1", "Tags": []},
            ]
        }

        has_unsupported, unsupported_types = check_for_unsupported_resources_quick(mock_session, "us-east-1")

        assert has_unsupported is False
        assert len(unsupported_types) == 0

    @patch("src.utils.unsupported_resources.boto3")
    def test_quick_check_with_unsupported(self, mock_boto3):
        """Test quick check when there are unsupported resources."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session.client.return_value = mock_client
        mock_client.get_resources.return_value = {
            "ResourceTagMappingList": [
                {"ResourceARN": "arn:aws:newservice:us-east-1:123:thing:t1", "Tags": []},
            ]
        }

        has_unsupported, unsupported_types = check_for_unsupported_resources_quick(mock_session, "us-east-1")

        assert has_unsupported is True
        assert "newservice:thing" in unsupported_types

    @patch("src.utils.unsupported_resources.boto3")
    def test_quick_check_handles_error(self, mock_boto3):
        """Test quick check handles errors gracefully."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session.client.return_value = mock_client
        mock_client.get_resources.side_effect = Exception("API error")

        has_unsupported, unsupported_types = check_for_unsupported_resources_quick(mock_session, "us-east-1")

        assert has_unsupported is False
        assert len(unsupported_types) == 0


class TestGetAllTaggedResourcesNoneSession:
    """Tests for get_all_tagged_resources with session=None."""

    @patch("src.utils.unsupported_resources.boto3")
    def test_creates_default_session_when_none(self, mock_boto3):
        """Test that a default session is created when session is None."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        mock_tagging_client = MagicMock()
        mock_session.client.return_value = mock_tagging_client

        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"ResourceTagMappingList": []}]
        mock_tagging_client.get_paginator.return_value = mock_paginator

        get_all_tagged_resources(session=None, regions=["us-east-1"])

        mock_boto3.Session.assert_called_once()

    @patch("src.utils.unsupported_resources.boto3")
    def test_gets_all_regions_when_none(self, mock_boto3):
        """Test that all regions are fetched when regions is None."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        mock_ec2_client = MagicMock()
        mock_tagging_client = MagicMock()

        def client_side_effect(service, **kwargs):
            if service == "ec2":
                return mock_ec2_client
            return mock_tagging_client

        mock_session.client.side_effect = client_side_effect

        mock_ec2_client.describe_regions.return_value = {
            "Regions": [{"RegionName": "us-east-1"}, {"RegionName": "us-west-2"}]
        }

        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"ResourceTagMappingList": []}]
        mock_tagging_client.get_paginator.return_value = mock_paginator

        resources = get_all_tagged_resources(session=None, regions=None)

        mock_ec2_client.describe_regions.assert_called_once()
        assert resources == []

    @patch("src.utils.unsupported_resources.boto3")
    def test_uses_default_regions_on_describe_regions_error(self, mock_boto3):
        """Test fallback to default regions when describe_regions fails."""
        from botocore.exceptions import ClientError

        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        mock_ec2_client = MagicMock()
        mock_tagging_client = MagicMock()

        def client_side_effect(service, **kwargs):
            if service == "ec2":
                return mock_ec2_client
            return mock_tagging_client

        mock_session.client.side_effect = client_side_effect

        mock_ec2_client.describe_regions.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}, "DescribeRegions"
        )

        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"ResourceTagMappingList": []}]
        mock_tagging_client.get_paginator.return_value = mock_paginator

        resources = get_all_tagged_resources(session=None, regions=None)

        # Should use default regions and not raise
        assert resources == []

    @patch("src.utils.unsupported_resources.boto3")
    def test_handles_generic_exception(self, mock_boto3):
        """Test that generic (non-ClientError) exceptions are logged but don't stop execution."""
        mock_session = MagicMock()
        mock_tagging_client = MagicMock()
        mock_session.client.return_value = mock_tagging_client

        mock_paginator = MagicMock()
        mock_paginator.paginate.side_effect = RuntimeError("Unexpected error")
        mock_tagging_client.get_paginator.return_value = mock_paginator

        resources = get_all_tagged_resources(mock_session, regions=["us-east-1"])

        # Should return empty list on generic exception
        assert resources == []


class TestCheckForUnsupportedResourcesQuickNoneSession:
    """Tests for check_for_unsupported_resources_quick with session=None."""

    @patch("src.utils.unsupported_resources.boto3")
    def test_creates_default_session_when_none(self, mock_boto3):
        """Test that a default session is created when session is None."""
        mock_session = MagicMock()
        mock_boto3.Session.return_value = mock_session

        mock_client = MagicMock()
        mock_session.client.return_value = mock_client
        mock_client.get_resources.return_value = {"ResourceTagMappingList": []}

        check_for_unsupported_resources_quick(session=None, region="us-east-1")

        mock_boto3.Session.assert_called_once()

    @patch("src.utils.unsupported_resources.boto3")
    def test_extracts_type_with_colon_separator(self, mock_boto3):
        """Test extraction of resource type with colon separator in ARN."""
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_session.client.return_value = mock_client
        mock_client.get_resources.return_value = {
            "ResourceTagMappingList": [
                {"ResourceARN": "arn:aws:lambda:us-east-1:123456789012:function:my-function", "Tags": []},
            ]
        }

        has_unsupported, unsupported_types = check_for_unsupported_resources_quick(mock_session, "us-east-1")

        # Lambda functions are supported
        assert has_unsupported is False
        assert len(unsupported_types) == 0


class TestSupportedResourceTypePrefixes:
    """Tests for SUPPORTED_RESOURCE_TYPE_PREFIXES constant."""

    def test_major_services_are_covered(self):
        """Test that major AWS services are covered."""
        # Compute
        assert "ec2:" in SUPPORTED_RESOURCE_TYPE_PREFIXES
        assert "lambda:" in SUPPORTED_RESOURCE_TYPE_PREFIXES
        assert "ecs:" in SUPPORTED_RESOURCE_TYPE_PREFIXES
        assert "eks:" in SUPPORTED_RESOURCE_TYPE_PREFIXES

        # Storage
        assert "s3:" in SUPPORTED_RESOURCE_TYPE_PREFIXES
        assert "dynamodb:" in SUPPORTED_RESOURCE_TYPE_PREFIXES
        assert "rds:" in SUPPORTED_RESOURCE_TYPE_PREFIXES

        # Networking
        assert "elasticloadbalancing:" in SUPPORTED_RESOURCE_TYPE_PREFIXES
        assert "route53:" in SUPPORTED_RESOURCE_TYPE_PREFIXES

        # Security
        assert "iam:" in SUPPORTED_RESOURCE_TYPE_PREFIXES
        assert "kms:" in SUPPORTED_RESOURCE_TYPE_PREFIXES
        assert "secretsmanager:" in SUPPORTED_RESOURCE_TYPE_PREFIXES
