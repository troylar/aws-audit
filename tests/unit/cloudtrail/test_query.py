"""Unit tests for CloudTrail query module."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.cloudtrail.query import (
    EVENT_TO_RESOURCE_TYPE,
    MULTI_SERVICE_EVENTS,
    RESOURCE_TYPE_NORMALIZATION,
    CloudTrailQuery,
    ResourceCreationEvent,
    get_resource_type_for_event,
    normalize_resource_type,
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


class TestResourceTypeNormalization:
    """Test resource type normalization for suffixed types."""

    def test_normalize_suffixed_elb_types(self):
        expected = "AWS::ElasticLoadBalancingV2::LoadBalancer"
        assert normalize_resource_type(f"{expected}::Application") == expected
        assert normalize_resource_type(f"{expected}::Network") == expected
        assert normalize_resource_type(f"{expected}::Gateway") == expected

    def test_normalize_suffixed_vpc_endpoint_types(self):
        assert normalize_resource_type("AWS::EC2::VPCEndpoint::Interface") == "AWS::EC2::VPCEndpoint"
        assert normalize_resource_type("AWS::EC2::VPCEndpoint::Gateway") == "AWS::EC2::VPCEndpoint"

    def test_normalize_suffixed_waf_types(self):
        assert normalize_resource_type("AWS::WAFv2::WebACL::Regional") == "AWS::WAFv2::WebACL"
        assert normalize_resource_type("AWS::WAFv2::WebACL::CloudFront") == "AWS::WAFv2::WebACL"

    def test_normalize_suffixed_apigateway_types(self):
        assert normalize_resource_type("AWS::ApiGatewayV2::Api::HTTP") == "AWS::ApiGatewayV2::Api"
        assert normalize_resource_type("AWS::ApiGatewayV2::Api::WebSocket") == "AWS::ApiGatewayV2::Api"

    def test_normalize_base_type_unchanged(self):
        assert normalize_resource_type("AWS::EC2::Instance") == "AWS::EC2::Instance"
        assert normalize_resource_type("AWS::S3::Bucket") == "AWS::S3::Bucket"
        assert normalize_resource_type("AWS::Lambda::Function") == "AWS::Lambda::Function"

    def test_all_normalization_entries_map_to_valid_cloudtrail_types(self):
        all_cloudtrail_types = set(EVENT_TO_RESOURCE_TYPE.values())
        for source_mapping in MULTI_SERVICE_EVENTS.values():
            all_cloudtrail_types.update(source_mapping.values())
        for suffixed, base in RESOURCE_TYPE_NORMALIZATION.items():
            assert base in all_cloudtrail_types, f"{suffixed} normalizes to {base} which has no CloudTrail event"


class TestEC2ResourceExtraction:
    """Test resource name extraction for EC2/VPC events that need special handling."""

    def test_extract_volume_id(self):
        query = CloudTrailQuery()
        event = {
            "requestParameters": {"availabilityZone": "us-east-1a", "size": "100"},
            "responseElements": {"volumeId": "vol-0123456789abcdef0"},
        }
        name, arn = query._extract_resource_info(event, "CreateVolume")
        assert name == "vol-0123456789abcdef0"

    def test_extract_vpc_id(self):
        query = CloudTrailQuery()
        event = {
            "requestParameters": {"cidrBlock": "10.0.0.0/16"},
            "responseElements": {"vpc": {"vpcId": "vpc-0123456789abcdef0", "cidrBlock": "10.0.0.0/16"}},
        }
        name, arn = query._extract_resource_info(event, "CreateVpc")
        assert name == "vpc-0123456789abcdef0"

    def test_extract_subnet_id(self):
        query = CloudTrailQuery()
        event = {
            "requestParameters": {"vpcId": "vpc-123", "cidrBlock": "10.0.1.0/24"},
            "responseElements": {"subnet": {"subnetId": "subnet-0123456789abcdef0"}},
        }
        name, arn = query._extract_resource_info(event, "CreateSubnet")
        assert name == "subnet-0123456789abcdef0"

    def test_extract_security_group_id_fallback(self):
        query = CloudTrailQuery()
        event = {
            "requestParameters": {"vpcId": "vpc-123", "groupDescription": "test"},
            "responseElements": {"groupId": "sg-0123456789abcdef0"},
        }
        name, arn = query._extract_resource_info(event, "CreateSecurityGroup")
        assert name == "sg-0123456789abcdef0"

    def test_extract_security_group_name_from_request(self):
        query = CloudTrailQuery()
        event = {
            "requestParameters": {"groupName": "my-security-group", "groupDescription": "test"},
            "responseElements": {"groupId": "sg-0123456789abcdef0"},
        }
        name, arn = query._extract_resource_info(event, "CreateSecurityGroup")
        assert name == "my-security-group"

    def test_extract_vpc_endpoint_id(self):
        query = CloudTrailQuery()
        event = {
            "requestParameters": {"vpcId": "vpc-123", "serviceName": "com.amazonaws.us-east-1.s3"},
            "responseElements": {
                "CreateVpcEndpointResponse": {
                    "vpcEndpoint": {"vpcEndpointId": "vpce-0123456789abcdef0"}
                }
            },
        }
        name, arn = query._extract_resource_info(event, "CreateVpcEndpoint")
        assert name == "vpce-0123456789abcdef0"

    def test_extract_instance_id(self):
        query = CloudTrailQuery()
        event = {
            "requestParameters": {},
            "responseElements": {
                "instancesSet": {"items": [{"instanceId": "i-0123456789abcdef0"}]}
            },
        }
        name, arn = query._extract_resource_info(event, "RunInstances")
        assert name == "i-0123456789abcdef0"


class TestKMSResourceExtraction:
    """Test KMS key ID extraction from CloudTrail events."""

    def test_extract_key_id(self):
        query = CloudTrailQuery()
        event = {
            "requestParameters": {"description": "My key", "keyUsage": "ENCRYPT_DECRYPT"},
            "responseElements": {"keyMetadata": {"keyId": "12345678-1234-1234-1234-123456789012"}},
        }
        name, arn = query._extract_resource_info(event, "CreateKey")
        assert name == "12345678-1234-1234-1234-123456789012"


class TestSQSResourceExtraction:
    """Test SQS queue name extraction from CloudTrail events."""

    def test_extract_queue_name_from_request(self):
        query = CloudTrailQuery()
        event = {
            "requestParameters": {"queueName": "my-queue"},
            "responseElements": {"queueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/my-queue"},
        }
        name, arn = query._extract_resource_info(event, "CreateQueue")
        assert name == "my-queue"

    def test_extract_queue_name_from_url_fallback(self):
        query = CloudTrailQuery()
        event = {
            "requestParameters": {},
            "responseElements": {"queueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/my-queue"},
        }
        name, arn = query._extract_resource_info(event, "CreateQueue")
        assert name == "my-queue"


class TestNewEventMappings:
    """Test newly added event type mappings."""

    def test_lambda_layer_mapping(self):
        assert EVENT_TO_RESOURCE_TYPE["PublishLayerVersion"] == "AWS::Lambda::LayerVersion"

    def test_ssm_document_mapping(self):
        assert EVENT_TO_RESOURCE_TYPE["CreateDocument"] == "AWS::SSM::Document"

    def test_eks_fargate_mapping(self):
        assert EVENT_TO_RESOURCE_TYPE["CreateFargateProfile"] == "AWS::EKS::FargateProfile"

    def test_composite_alarm_mapping(self):
        assert EVENT_TO_RESOURCE_TYPE["PutCompositeAlarm"] == "AWS::CloudWatch::CompositeAlarm"

    def test_extract_layer_name(self):
        query = CloudTrailQuery()
        event = {
            "requestParameters": {"layerName": "my-layer"},
            "responseElements": {},
        }
        name, arn = query._extract_resource_info(event, "PublishLayerVersion")
        assert name == "my-layer"

    def test_extract_document_name(self):
        query = CloudTrailQuery()
        event = {
            "requestParameters": {"name": "MyDocument"},
            "responseElements": {},
        }
        name, arn = query._extract_resource_info(event, "CreateDocument")
        assert name == "MyDocument"

    def test_extract_fargate_profile_name(self):
        query = CloudTrailQuery()
        event = {
            "requestParameters": {"fargateProfileName": "my-profile"},
            "responseElements": {},
        }
        name, arn = query._extract_resource_info(event, "CreateFargateProfile")
        assert name == "my-profile"

    def test_extract_composite_alarm_name(self):
        query = CloudTrailQuery()
        event = {
            "requestParameters": {"alarmName": "my-composite-alarm"},
            "responseElements": {},
        }
        name, arn = query._extract_resource_info(event, "PutCompositeAlarm")
        assert name == "my-composite-alarm"


class TestNullResponseHandling:
    """Test extraction when response elements are null or missing."""

    def test_null_response_elements(self):
        query = CloudTrailQuery()
        event = {
            "requestParameters": {"cidrBlock": "10.0.0.0/16"},
            "responseElements": None,
        }
        name, arn = query._extract_resource_info(event, "CreateVpc")
        assert name is None

    def test_empty_response_elements(self):
        query = CloudTrailQuery()
        event = {
            "requestParameters": {},
            "responseElements": {},
        }
        name, arn = query._extract_resource_info(event, "CreateVolume")
        assert name is None

    def test_vpc_response_not_dict(self):
        query = CloudTrailQuery()
        event = {
            "requestParameters": {},
            "responseElements": {"vpc": "not-a-dict"},
        }
        name, arn = query._extract_resource_info(event, "CreateVpc")
        assert name is None
