"""Unit tests for CloudTrail query module."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.cloudtrail.query import (
    EVENT_TO_RESOURCE_TYPE,
    MULTI_SERVICE_EVENTS,
    CloudTrailQuery,
    ResourceCreationEvent,
    get_resource_type_for_event,
)


class TestEventMapping:
    """Test event to resource type mapping."""

    def test_common_events_mapped(self):
        """Test that common creation events are mapped."""
        assert "RunInstances" in EVENT_TO_RESOURCE_TYPE
        assert "CreateBucket" in EVENT_TO_RESOURCE_TYPE
        assert "CreateFunction" in EVENT_TO_RESOURCE_TYPE
        assert "CreateRole" in EVENT_TO_RESOURCE_TYPE
        # CreateTable is in MULTI_SERVICE_EVENTS (maps to both DynamoDB and Glue)
        assert "CreateTable" in MULTI_SERVICE_EVENTS

    def test_event_maps_to_correct_type(self):
        """Test events map to correct resource types."""
        assert EVENT_TO_RESOURCE_TYPE["RunInstances"] == "AWS::EC2::Instance"
        assert EVENT_TO_RESOURCE_TYPE["CreateBucket"] == "AWS::S3::Bucket"
        assert EVENT_TO_RESOURCE_TYPE["CreateRole"] == "AWS::IAM::Role"

    def test_multi_service_events_mapped(self):
        """Test events that map to different services based on event source."""
        # CreateCluster maps to ECS or EKS
        assert "CreateCluster" in MULTI_SERVICE_EVENTS
        assert "ecs.amazonaws.com" in MULTI_SERVICE_EVENTS["CreateCluster"]
        assert "eks.amazonaws.com" in MULTI_SERVICE_EVENTS["CreateCluster"]

        # CreateTable maps to DynamoDB or Glue
        assert "CreateTable" in MULTI_SERVICE_EVENTS
        assert "dynamodb.amazonaws.com" in MULTI_SERVICE_EVENTS["CreateTable"]
        assert "glue.amazonaws.com" in MULTI_SERVICE_EVENTS["CreateTable"]

    def test_get_resource_type_for_event(self):
        """Test the helper function for event type lookup."""
        # Standard event
        assert get_resource_type_for_event("RunInstances") == "AWS::EC2::Instance"

        # Multi-service event with event source
        assert get_resource_type_for_event("CreateCluster", "ecs.amazonaws.com") == "AWS::ECS::Cluster"
        assert get_resource_type_for_event("CreateCluster", "eks.amazonaws.com") == "AWS::EKS::Cluster"

        # Multi-service event without event source (falls back to first mapping)
        result = get_resource_type_for_event("CreateCluster")
        assert result in ["AWS::ECS::Cluster", "AWS::EKS::Cluster"]

        # Unknown event
        assert get_resource_type_for_event("UnknownEvent") is None


class TestCloudTrailQuery:
    """Test CloudTrail query functionality."""

    def test_init_defaults(self):
        """Test default initialization."""
        query = CloudTrailQuery()
        assert query.profile_name is None
        assert query.regions == ["us-east-1"]

    def test_init_with_params(self):
        """Test initialization with parameters."""
        query = CloudTrailQuery(
            profile_name="test-profile",
            regions=["us-west-2", "eu-west-1"],
        )
        assert query.profile_name == "test-profile"
        assert query.regions == ["us-west-2", "eu-west-1"]


class TestRoleArnParsing:
    """Test role ARN parsing."""

    @patch("src.cloudtrail.query.create_boto_client")
    def test_full_arn_parsed(self, mock_client):
        """Test parsing full ARN."""
        mock_ct = MagicMock()
        mock_ct.get_paginator.return_value.paginate.return_value = []
        mock_client.return_value = mock_ct

        query = CloudTrailQuery()
        # Should not raise
        query.get_resources_created_by_role(
            "arn:aws:iam::123456789012:role/MyRole",
            days_back=1,
        )

    @patch("src.cloudtrail.query.create_boto_client")
    def test_role_name_only(self, mock_client):
        """Test parsing role name only."""
        mock_ct = MagicMock()
        mock_ct.get_paginator.return_value.paginate.return_value = []
        mock_client.return_value = mock_ct

        query = CloudTrailQuery()
        # Should not raise
        query.get_resources_created_by_role("MyRole", days_back=1)


class TestEventParsing:
    """Test CloudTrail event parsing."""

    def test_parse_assumed_role_event(self):
        """Test parsing event from assumed role."""
        query = CloudTrailQuery()

        raw_event = {
            "eventName": "CreateBucket",
            "userIdentity": {
                "type": "AssumedRole",
                "sessionContext": {
                    "sessionIssuer": {
                        "arn": "arn:aws:iam::123456789012:role/TestRole",
                    }
                },
            },
            "requestParameters": {
                "bucketName": "my-test-bucket",
            },
            "awsRegion": "us-east-1",
            "recipientAccountId": "123456789012",
        }

        event = {
            "EventTime": datetime.now(timezone.utc),
            "CloudTrailEvent": json.dumps(raw_event),
        }

        result = query._parse_event(event, "TestRole", "", "us-east-1")

        assert result is not None
        assert result.event_name == "CreateBucket"
        assert result.resource_type == "AWS::S3::Bucket"
        assert result.resource_name == "my-test-bucket"
        assert result.created_by_type == "AssumedRole"

    def test_parse_non_creation_event_returns_none(self):
        """Test that non-creation events return None."""
        query = CloudTrailQuery()

        raw_event = {
            "eventName": "GetBucketPolicy",  # Not a creation event
            "userIdentity": {
                "type": "AssumedRole",
                "sessionContext": {
                    "sessionIssuer": {
                        "arn": "arn:aws:iam::123456789012:role/TestRole",
                    }
                },
            },
        }

        event = {
            "EventTime": datetime.now(timezone.utc),
            "CloudTrailEvent": json.dumps(raw_event),
        }

        result = query._parse_event(event, "TestRole", "", "us-east-1")
        assert result is None

    def test_parse_different_role_returns_none(self):
        """Test that events from different roles return None."""
        query = CloudTrailQuery()

        raw_event = {
            "eventName": "CreateBucket",
            "userIdentity": {
                "type": "AssumedRole",
                "sessionContext": {
                    "sessionIssuer": {
                        "arn": "arn:aws:iam::123456789012:role/OtherRole",
                    }
                },
            },
        }

        event = {
            "EventTime": datetime.now(timezone.utc),
            "CloudTrailEvent": json.dumps(raw_event),
        }

        result = query._parse_event(event, "TestRole", "", "us-east-1")
        assert result is None


class TestResourceInfoExtraction:
    """Test resource info extraction from events."""

    def test_extract_bucket_name(self):
        """Test extracting bucket name."""
        query = CloudTrailQuery()

        event = {
            "requestParameters": {"bucketName": "my-bucket"},
            "responseElements": {},
        }

        name, arn = query._extract_resource_info(event, "CreateBucket")
        assert name == "my-bucket"

    def test_extract_function_name(self):
        """Test extracting Lambda function name."""
        query = CloudTrailQuery()

        event = {
            "requestParameters": {"functionName": "my-function"},
            "responseElements": {"functionArn": "arn:aws:lambda:us-east-1:123:function:my-function"},
        }

        name, arn = query._extract_resource_info(event, "CreateFunction")
        assert name == "my-function"
        assert arn == "arn:aws:lambda:us-east-1:123:function:my-function"

    def test_extract_role_name(self):
        """Test extracting IAM role name."""
        query = CloudTrailQuery()

        event = {
            "requestParameters": {"roleName": "my-role"},
            "responseElements": {"roleArn": "arn:aws:iam::123:role/my-role"},
        }

        name, arn = query._extract_resource_info(event, "CreateRole")
        assert name == "my-role"


class TestResourceCreationEvent:
    """Test ResourceCreationEvent dataclass."""

    def test_create_event(self):
        """Test creating a ResourceCreationEvent."""
        event = ResourceCreationEvent(
            event_time=datetime.now(timezone.utc),
            event_name="CreateBucket",
            resource_type="AWS::S3::Bucket",
            resource_name="my-bucket",
            resource_arn="arn:aws:s3:::my-bucket",
            created_by_arn="arn:aws:iam::123:role/TestRole",
            created_by_type="AssumedRole",
            region="us-east-1",
            account_id="123456789012",
            raw_event={},
        )

        assert event.event_name == "CreateBucket"
        assert event.resource_name == "my-bucket"
        assert event.created_by_type == "AssumedRole"
