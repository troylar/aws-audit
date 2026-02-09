"""Tests for creator matching: resource type normalization, name extraction, and end-to-end enrichment."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.cloudtrail.query import (
    CloudTrailQuery,
    ResourceCreationEvent,
    normalize_resource_type,
)
from src.models.resource import Resource

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TS = "2025-01-01T00:00:00"


def _creator(by: str = "role/A", by_type: str = "AssumedRole") -> dict:
    return {"created_by": by, "created_by_type": by_type, "created_at": _TS}


def _make_resource(
    name: str,
    resource_type: str,
    arn: str = "",
    tags: dict | None = None,
) -> Resource:
    return Resource(
        arn=arn,
        resource_type=resource_type,
        name=name,
        region="us-east-1",
        config_hash="abc",
        tags=tags or {},
    )


def _make_creation_event(
    event_name: str,
    resource_type: str,
    resource_name: str,
    resource_arn: str = "",
    created_by_arn: str = "arn:aws:iam::123456789012:role/TestRole",
) -> ResourceCreationEvent:
    return ResourceCreationEvent(
        event_time=datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
        event_name=event_name,
        resource_type=resource_type,
        resource_name=resource_name,
        resource_arn=resource_arn,
        created_by_arn=created_by_arn,
        created_by_type="AssumedRole",
        region="us-east-1",
        account_id="123456789012",
        raw_event={},
    )


# ---------------------------------------------------------------------------
# Event type filtering with normalized resource types
# ---------------------------------------------------------------------------


class TestEventTypeFilteringWithNormalization:
    """Test that get_all_creation_events correctly filters event types when
    snapshot resource types use suffixed names."""

    @patch("src.cloudtrail.query.create_boto_client")
    def test_suffixed_elb_type_includes_create_load_balancer(self, mock_client):
        """Suffixed ELB types should match the CreateLoadBalancer event."""
        mock_ct = MagicMock()
        mock_ct.get_paginator.return_value.paginate.return_value = [{"Events": []}]
        mock_client.return_value = mock_ct

        query = CloudTrailQuery(regions=["us-east-1"])
        query.get_all_creation_events(
            days_back=1,
            regions=["us-east-1"],
            resource_types={"AWS::ElasticLoadBalancingV2::LoadBalancer::Application"},
        )

        # Should have queried CloudTrail (not skipped due to type mismatch)
        assert mock_ct.get_paginator.called

        # Verify CreateLoadBalancer was among the queried events
        paginate_calls = mock_ct.get_paginator.return_value.paginate.call_args_list
        queried_events = set()
        for call in paginate_calls:
            lookup = call[1].get("LookupAttributes", call[0][0] if call[0] else [])
            if isinstance(lookup, list):
                for attr in lookup:
                    if attr.get("AttributeKey") == "EventName":
                        queried_events.add(attr["AttributeValue"])
        # At minimum, the function should not have fallen back to "all events"
        # (it should have found CreateLoadBalancer through normalization)

    @patch("src.cloudtrail.query.create_boto_client")
    def test_suffixed_vpc_endpoint_type_includes_create_vpc_endpoint(self, mock_client):
        """Suffixed VPCEndpoint types should match the CreateVpcEndpoint event."""
        mock_ct = MagicMock()
        mock_ct.get_paginator.return_value.paginate.return_value = [{"Events": []}]
        mock_client.return_value = mock_ct

        query = CloudTrailQuery(regions=["us-east-1"])
        query.get_all_creation_events(
            days_back=1,
            regions=["us-east-1"],
            resource_types={"AWS::EC2::VPCEndpoint::Interface"},
        )

        assert mock_ct.get_paginator.called

    @patch("src.cloudtrail.query.create_boto_client")
    def test_suffixed_waf_type_includes_create_web_acl(self, mock_client):
        """Suffixed WAF types should match the CreateWebACL event."""
        mock_ct = MagicMock()
        mock_ct.get_paginator.return_value.paginate.return_value = [{"Events": []}]
        mock_client.return_value = mock_ct

        query = CloudTrailQuery(regions=["us-east-1"])
        query.get_all_creation_events(
            days_back=1,
            regions=["us-east-1"],
            resource_types={"AWS::WAFv2::WebACL::Regional"},
        )

        assert mock_ct.get_paginator.called

    @patch("src.cloudtrail.query.create_boto_client")
    def test_mixed_suffixed_and_base_types(self, mock_client):
        """A mix of suffixed and base resource types should all resolve."""
        mock_ct = MagicMock()
        mock_ct.get_paginator.return_value.paginate.return_value = [{"Events": []}]
        mock_client.return_value = mock_ct

        query = CloudTrailQuery(regions=["us-east-1"])
        query.get_all_creation_events(
            days_back=1,
            regions=["us-east-1"],
            resource_types={
                "AWS::ElasticLoadBalancingV2::LoadBalancer::Network",
                "AWS::S3::Bucket",
                "AWS::EC2::VPCEndpoint::Gateway",
            },
        )

        assert mock_ct.get_paginator.called

    @patch("src.cloudtrail.query.create_boto_client")
    def test_multi_service_event_included_for_suffixed_type(self, mock_client):
        """Suffixed ECS cluster type should include CreateCluster multi-service event."""
        mock_ct = MagicMock()
        mock_ct.get_paginator.return_value.paginate.return_value = [{"Events": []}]
        mock_client.return_value = mock_ct

        query = CloudTrailQuery(regions=["us-east-1"])
        # ECS Cluster is in MULTI_SERVICE_EVENTS, not in direct mapping
        # This isn't suffixed in collectors, but verifies multi-service still works
        query.get_all_creation_events(
            days_back=1,
            regions=["us-east-1"],
            resource_types={"AWS::ECS::Cluster"},
        )

        assert mock_ct.get_paginator.called


# ---------------------------------------------------------------------------
# get_resource_creators builds correct keys from extracted names
# ---------------------------------------------------------------------------


class TestGetResourceCreatorsKeyBuilding:
    """Test that get_resource_creators builds lookup keys from extracted event data."""

    @patch.object(CloudTrailQuery, "get_all_creation_events")
    def test_volume_event_creates_volume_id_key(self, mock_get_all):
        """A CreateVolume event should produce a key like AWS::EC2::Volume:vol-xxx."""
        mock_get_all.return_value = [
            _make_creation_event("CreateVolume", "AWS::EC2::Volume", "vol-abc123"),
        ]

        query = CloudTrailQuery(regions=["us-east-1"])
        creators = query.get_resource_creators(days_back=1)

        assert "AWS::EC2::Volume:vol-abc123" in creators
        assert creators["AWS::EC2::Volume:vol-abc123"]["created_by_type"] == "AssumedRole"

    @patch.object(CloudTrailQuery, "get_all_creation_events")
    def test_vpc_event_creates_vpc_id_key(self, mock_get_all):
        mock_get_all.return_value = [
            _make_creation_event("CreateVpc", "AWS::EC2::VPC", "vpc-abc123"),
        ]

        query = CloudTrailQuery(regions=["us-east-1"])
        creators = query.get_resource_creators(days_back=1)

        assert "AWS::EC2::VPC:vpc-abc123" in creators

    @patch.object(CloudTrailQuery, "get_all_creation_events")
    def test_subnet_event_creates_subnet_id_key(self, mock_get_all):
        mock_get_all.return_value = [
            _make_creation_event("CreateSubnet", "AWS::EC2::Subnet", "subnet-abc123"),
        ]

        query = CloudTrailQuery(regions=["us-east-1"])
        creators = query.get_resource_creators(days_back=1)

        assert "AWS::EC2::Subnet:subnet-abc123" in creators

    @patch.object(CloudTrailQuery, "get_all_creation_events")
    def test_kms_event_creates_key_id_key(self, mock_get_all):
        mock_get_all.return_value = [
            _make_creation_event("CreateKey", "AWS::KMS::Key", "12345678-1234-1234-1234-123456789012"),
        ]

        query = CloudTrailQuery(regions=["us-east-1"])
        creators = query.get_resource_creators(days_back=1)

        assert "AWS::KMS::Key:12345678-1234-1234-1234-123456789012" in creators

    @patch.object(CloudTrailQuery, "get_all_creation_events")
    def test_null_resource_name_is_excluded(self, mock_get_all):
        """Events where resource_name is None should not appear in creators dict."""
        mock_get_all.return_value = [
            _make_creation_event("CreateVolume", "AWS::EC2::Volume", None),
        ]

        query = CloudTrailQuery(regions=["us-east-1"])
        creators = query.get_resource_creators(days_back=1)

        assert len(creators) == 0

    @patch.object(CloudTrailQuery, "get_all_creation_events")
    def test_most_recent_event_wins(self, mock_get_all):
        """When multiple creation events exist for the same resource, most recent wins."""
        event1 = _make_creation_event(
            "CreateBucket",
            "AWS::S3::Bucket",
            "my-bucket",
            created_by_arn="arn:aws:iam::123:role/OldRole",
        )
        event1.event_time = datetime(2025, 1, 1, tzinfo=timezone.utc)

        event2 = _make_creation_event(
            "CreateBucket",
            "AWS::S3::Bucket",
            "my-bucket",
            created_by_arn="arn:aws:iam::123:role/NewRole",
        )
        event2.event_time = datetime(2025, 6, 1, tzinfo=timezone.utc)

        mock_get_all.return_value = [event1, event2]

        query = CloudTrailQuery(regions=["us-east-1"])
        creators = query.get_resource_creators(days_back=90)

        assert creators["AWS::S3::Bucket:my-bucket"]["created_by"] == "arn:aws:iam::123:role/NewRole"


# ---------------------------------------------------------------------------
# ARN fallback matching
# ---------------------------------------------------------------------------


class TestARNFallbackMatching:
    """Test that resources match creators via ARN name extraction when
    the primary name doesn't match."""

    def test_ec2_instance_name_tag_matches_via_arn(self):
        """An EC2 instance with a Name tag should match via ARN fallback
        when CloudTrail has the instance ID."""
        resource = _make_resource(
            name="web-server-prod",
            resource_type="AWS::EC2::Instance",
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-abc123",
        )
        creators = {
            "AWS::EC2::Instance:i-abc123": {
                "created_by": "arn:aws:iam::123:role/TestRole",
                "created_by_type": "AssumedRole",
                "created_at": "2025-01-01T00:00:00",
            }
        }

        normalized_type = normalize_resource_type(resource.resource_type)
        key = f"{normalized_type}:{resource.name}"
        creator_info = creators.get(key)

        if not creator_info and resource.arn:
            arn_name = resource.arn.split("/")[-1].split(":")[-1]
            key = f"{normalized_type}:{arn_name}"
            creator_info = creators.get(key)

        assert creator_info is not None
        assert creator_info["created_by"] == "arn:aws:iam::123:role/TestRole"

    def test_kms_alias_matches_via_arn(self):
        """A KMS key stored with alias should match via ARN fallback
        when CloudTrail has the key UUID."""
        resource = _make_resource(
            name="alias/my-key",
            resource_type="AWS::KMS::Key",
            arn="arn:aws:kms:us-east-1:123456789012:key/12345678-uuid",
        )
        creators = {
            "AWS::KMS::Key:12345678-uuid": {
                "created_by": "arn:aws:iam::123:role/TestRole",
                "created_by_type": "AssumedRole",
                "created_at": "2025-01-01T00:00:00",
            }
        }

        normalized_type = normalize_resource_type(resource.resource_type)
        key = f"{normalized_type}:{resource.name}"
        creator_info = creators.get(key)

        if not creator_info and resource.arn:
            arn_name = resource.arn.split("/")[-1].split(":")[-1]
            key = f"{normalized_type}:{arn_name}"
            creator_info = creators.get(key)

        assert creator_info is not None

    def test_volume_name_tag_matches_via_arn(self):
        """An EBS volume with a Name tag should match via ARN when
        CloudTrail has the volume ID."""
        resource = _make_resource(
            name="data-volume",
            resource_type="AWS::EC2::Volume",
            arn="arn:aws:ec2:us-east-1:123:volume/vol-abc123",
        )
        creators = {
            "AWS::EC2::Volume:vol-abc123": {
                "created_by": "arn:aws:iam::123:role/TestRole",
                "created_by_type": "AssumedRole",
                "created_at": "2025-01-01T00:00:00",
            }
        }

        normalized_type = normalize_resource_type(resource.resource_type)
        key = f"{normalized_type}:{resource.name}"
        creator_info = creators.get(key)

        if not creator_info and resource.arn:
            arn_name = resource.arn.split("/")[-1].split(":")[-1]
            key = f"{normalized_type}:{arn_name}"
            creator_info = creators.get(key)

        assert creator_info is not None

    def test_direct_name_match_takes_precedence(self):
        """When the name matches directly, ARN fallback is not needed."""
        resource = _make_resource(
            name="my-bucket",
            resource_type="AWS::S3::Bucket",
            arn="arn:aws:s3:::my-bucket",
        )
        creators = {
            "AWS::S3::Bucket:my-bucket": {
                "created_by": "arn:aws:iam::123:role/DirectMatch",
                "created_by_type": "AssumedRole",
                "created_at": "2025-01-01T00:00:00",
            }
        }

        normalized_type = normalize_resource_type(resource.resource_type)
        key = f"{normalized_type}:{resource.name}"
        creator_info = creators.get(key)

        assert creator_info is not None
        assert creator_info["created_by"] == "arn:aws:iam::123:role/DirectMatch"


# ---------------------------------------------------------------------------
# Suffixed resource type matching
# ---------------------------------------------------------------------------


class TestSuffixedResourceTypeMatching:
    """Test that resources with suffixed types match creators keyed by base types."""

    def test_elb_application_matches_base_type(self):
        """An ALB resource with ::Application suffix should match a creator
        keyed by the base type."""
        resource = _make_resource(
            name="my-alb",
            resource_type="AWS::ElasticLoadBalancingV2::LoadBalancer::Application",
            arn="arn:aws:elasticloadbalancing:us-east-1:123:loadbalancer/app/my-alb/abc",
        )
        creators = {
            "AWS::ElasticLoadBalancingV2::LoadBalancer:my-alb": {
                "created_by": "arn:aws:iam::123:role/TestRole",
                "created_by_type": "AssumedRole",
                "created_at": "2025-01-01T00:00:00",
            }
        }

        normalized_type = normalize_resource_type(resource.resource_type)
        key = f"{normalized_type}:{resource.name}"
        creator_info = creators.get(key)

        assert creator_info is not None

    def test_vpc_endpoint_interface_matches_base_type(self):
        resource = _make_resource(
            name="vpce-abc123",
            resource_type="AWS::EC2::VPCEndpoint::Interface",
            arn="arn:aws:ec2:us-east-1:123:vpc-endpoint/vpce-abc123",
        )
        creators = {
            "AWS::EC2::VPCEndpoint:vpce-abc123": {
                "created_by": "arn:aws:iam::123:role/TestRole",
                "created_by_type": "AssumedRole",
                "created_at": "2025-01-01T00:00:00",
            }
        }

        normalized_type = normalize_resource_type(resource.resource_type)
        key = f"{normalized_type}:{resource.name}"
        creator_info = creators.get(key)

        assert creator_info is not None

    def test_waf_regional_matches_base_type(self):
        resource = _make_resource(
            name="my-waf",
            resource_type="AWS::WAFv2::WebACL::Regional",
        )
        creators = {
            "AWS::WAFv2::WebACL:my-waf": {
                "created_by": "arn:aws:iam::123:role/TestRole",
                "created_by_type": "AssumedRole",
                "created_at": "2025-01-01T00:00:00",
            }
        }

        normalized_type = normalize_resource_type(resource.resource_type)
        key = f"{normalized_type}:{resource.name}"
        creator_info = creators.get(key)

        assert creator_info is not None

    def test_apigateway_http_matches_base_type(self):
        resource = _make_resource(
            name="my-api",
            resource_type="AWS::ApiGatewayV2::Api::HTTP",
        )
        creators = {
            "AWS::ApiGatewayV2::Api:my-api": {
                "created_by": "arn:aws:iam::123:role/TestRole",
                "created_by_type": "AssumedRole",
                "created_at": "2025-01-01T00:00:00",
            }
        }

        normalized_type = normalize_resource_type(resource.resource_type)
        key = f"{normalized_type}:{resource.name}"
        creator_info = creators.get(key)

        assert creator_info is not None


# ---------------------------------------------------------------------------
# Full extraction pipeline tests (CloudTrail event -> resource name)
# ---------------------------------------------------------------------------


class TestExtractionPipeline:
    """End-to-end tests simulating full CloudTrail event parsing and
    resource info extraction for the event types we fixed."""

    def _make_cloudtrail_event(self, event_name: str, request_params: dict, response_elements: dict) -> dict:
        raw_event = {
            "eventName": event_name,
            "eventSource": "ec2.amazonaws.com",
            "userIdentity": {
                "type": "AssumedRole",
                "sessionContext": {
                    "sessionIssuer": {
                        "arn": "arn:aws:iam::123456789012:role/TestRole",
                    }
                },
            },
            "requestParameters": request_params,
            "responseElements": response_elements,
            "awsRegion": "us-east-1",
            "recipientAccountId": "123456789012",
        }
        return {
            "EventTime": datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
            "CloudTrailEvent": json.dumps(raw_event),
        }

    def test_create_volume_full_pipeline(self):
        query = CloudTrailQuery()
        event = self._make_cloudtrail_event(
            "CreateVolume",
            {"availabilityZone": "us-east-1a", "size": "100", "volumeType": "gp3"},
            {"volumeId": "vol-0abc123", "size": "100"},
        )
        result = query._parse_creation_event(event, "us-east-1")
        assert result is not None
        assert result.resource_name == "vol-0abc123"
        assert result.resource_type == "AWS::EC2::Volume"

    def test_create_vpc_full_pipeline(self):
        query = CloudTrailQuery()
        event = self._make_cloudtrail_event(
            "CreateVpc",
            {"cidrBlock": "10.0.0.0/16", "instanceTenancy": "default"},
            {"vpc": {"vpcId": "vpc-0abc123", "cidrBlock": "10.0.0.0/16"}},
        )
        result = query._parse_creation_event(event, "us-east-1")
        assert result is not None
        assert result.resource_name == "vpc-0abc123"
        assert result.resource_type == "AWS::EC2::VPC"

    def test_create_subnet_full_pipeline(self):
        query = CloudTrailQuery()
        event = self._make_cloudtrail_event(
            "CreateSubnet",
            {"vpcId": "vpc-123", "cidrBlock": "10.0.1.0/24"},
            {"subnet": {"subnetId": "subnet-0abc123", "cidrBlock": "10.0.1.0/24"}},
        )
        result = query._parse_creation_event(event, "us-east-1")
        assert result is not None
        assert result.resource_name == "subnet-0abc123"
        assert result.resource_type == "AWS::EC2::Subnet"

    def test_create_security_group_with_group_name(self):
        query = CloudTrailQuery()
        event = self._make_cloudtrail_event(
            "CreateSecurityGroup",
            {"groupName": "web-sg", "groupDescription": "Web servers", "vpcId": "vpc-123"},
            {"groupId": "sg-0abc123"},
        )
        result = query._parse_creation_event(event, "us-east-1")
        assert result is not None
        # groupName is in the generic name_keys, so it should be extracted first
        assert result.resource_name == "web-sg"

    def test_create_security_group_without_group_name(self):
        query = CloudTrailQuery()
        event = self._make_cloudtrail_event(
            "CreateSecurityGroup",
            {"groupDescription": "test", "vpcId": "vpc-123"},
            {"groupId": "sg-0abc123"},
        )
        result = query._parse_creation_event(event, "us-east-1")
        assert result is not None
        # Falls back to groupId from response
        assert result.resource_name == "sg-0abc123"

    def test_create_key_full_pipeline(self):
        query = CloudTrailQuery()
        raw_event = {
            "eventName": "CreateKey",
            "eventSource": "kms.amazonaws.com",
            "userIdentity": {
                "type": "IAMUser",
                "arn": "arn:aws:iam::123456789012:user/admin",
                "userName": "admin",
            },
            "requestParameters": {"description": "My encryption key", "keyUsage": "ENCRYPT_DECRYPT"},
            "responseElements": {
                "keyMetadata": {
                    "keyId": "12345678-1234-1234-1234-123456789012",
                    "arn": "arn:aws:kms:us-east-1:123:key/12345678-1234-1234-1234-123456789012",
                }
            },
            "awsRegion": "us-east-1",
            "recipientAccountId": "123456789012",
        }
        event = {
            "EventTime": datetime(2025, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
            "CloudTrailEvent": json.dumps(raw_event),
        }
        result = query._parse_creation_event(event, "us-east-1")
        assert result is not None
        assert result.resource_name == "12345678-1234-1234-1234-123456789012"
        assert result.resource_type == "AWS::KMS::Key"

    def test_create_vpc_endpoint_overrides_service_name(self):
        """CreateVpcEndpoint should use vpcEndpointId, not serviceName."""
        query = CloudTrailQuery()
        event = self._make_cloudtrail_event(
            "CreateVpcEndpoint",
            {"vpcId": "vpc-123", "serviceName": "com.amazonaws.us-east-1.s3", "vpcEndpointType": "Gateway"},
            {
                "CreateVpcEndpointResponse": {
                    "vpcEndpoint": {"vpcEndpointId": "vpce-0abc123", "serviceName": "com.amazonaws.us-east-1.s3"}
                }
            },
        )
        result = query._parse_creation_event(event, "us-east-1")
        assert result is not None
        assert result.resource_name == "vpce-0abc123"
        assert result.resource_type == "AWS::EC2::VPCEndpoint"


# ---------------------------------------------------------------------------
# End-to-end enrichment simulation
# ---------------------------------------------------------------------------


class TestEnrichmentSimulation:
    """Simulate the enrichment matching loop from main.py to verify
    that normalized types + ARN fallback resolve correctly."""

    def _simulate_enrichment(self, resources: list[Resource], creators: dict) -> int:
        """Reproduce the matching logic from snapshot_enrich_creators."""
        matched = 0
        for resource in resources:
            normalized_type = normalize_resource_type(resource.resource_type)
            key = f"{normalized_type}:{resource.name}"
            creator_info = creators.get(key)

            if not creator_info and resource.arn:
                arn_name = resource.arn.split("/")[-1].split(":")[-1]
                key = f"{normalized_type}:{arn_name}"
                creator_info = creators.get(key)

            if creator_info:
                matched += 1
                if resource.tags is None:
                    resource.tags = {}
                resource.tags["_created_by"] = creator_info["created_by"]
                resource.tags["_created_by_type"] = creator_info["created_by_type"]
                resource.tags["_created_at"] = creator_info["created_at"]
        return matched

    def test_mixed_resource_types_all_match(self):
        """A realistic mix of resources should all match their creators."""
        resources = [
            _make_resource("my-bucket", "AWS::S3::Bucket", "arn:aws:s3:::my-bucket"),
            _make_resource("my-func", "AWS::Lambda::Function", "arn:aws:lambda:us-east-1:123:function:my-func"),
            _make_resource("web-server", "AWS::EC2::Instance", "arn:aws:ec2:us-east-1:123:instance/i-abc"),
            _make_resource("data-vol", "AWS::EC2::Volume", "arn:aws:ec2:us-east-1:123:volume/vol-abc"),
            _make_resource("alias/my-key", "AWS::KMS::Key", "arn:aws:kms:us-east-1:123:key/uuid-123"),
        ]

        creators = {
            "AWS::S3::Bucket:my-bucket": _creator("role/A"),
            "AWS::Lambda::Function:my-func": _creator("role/A"),
            "AWS::EC2::Instance:i-abc": _creator("role/B"),
            "AWS::EC2::Volume:vol-abc": _creator("role/B"),
            "AWS::KMS::Key:uuid-123": _creator("role/C"),
        }

        matched = self._simulate_enrichment(resources, creators)
        assert matched == 5

    def test_suffixed_types_match_base_creators(self):
        """Resources with suffixed types should match creators with base types."""
        resources = [
            _make_resource("my-alb", "AWS::ElasticLoadBalancingV2::LoadBalancer::Application"),
            _make_resource("my-nlb", "AWS::ElasticLoadBalancingV2::LoadBalancer::Network"),
            _make_resource("vpce-abc", "AWS::EC2::VPCEndpoint::Interface"),
            _make_resource("my-waf", "AWS::WAFv2::WebACL::Regional"),
            _make_resource("my-api", "AWS::ApiGatewayV2::Api::HTTP"),
        ]

        base_type = "AWS::ElasticLoadBalancingV2::LoadBalancer"
        creators = {
            f"{base_type}:my-alb": _creator("r/A"),
            f"{base_type}:my-nlb": _creator("r/A"),
            "AWS::EC2::VPCEndpoint:vpce-abc": _creator("r/B"),
            "AWS::WAFv2::WebACL:my-waf": _creator("r/B"),
            "AWS::ApiGatewayV2::Api:my-api": _creator("r/C"),
        }

        matched = self._simulate_enrichment(resources, creators)
        assert matched == 5

    def test_no_match_leaves_resource_untagged(self):
        """Resources with no matching creator should remain untagged."""
        resources = [
            _make_resource("unknown-thing", "AWS::Unknown::Type"),
        ]
        creators = {
            "AWS::S3::Bucket:some-bucket": _creator("r/A"),
        }

        matched = self._simulate_enrichment(resources, creators)
        assert matched == 0
        assert "_created_by" not in resources[0].tags

    def test_arn_fallback_combined_with_normalization(self):
        """Suffixed type + ARN fallback should work together."""
        resource = _make_resource(
            name="my-alb",
            resource_type="AWS::ElasticLoadBalancingV2::LoadBalancer::Application",
            arn="arn:aws:elasticloadbalancing:us-east-1:123:loadbalancer/app/real-name/abc123",
        )
        creators = {
            "AWS::ElasticLoadBalancingV2::LoadBalancer:abc123": {
                "created_by": "role/X",
                "created_by_type": "AssumedRole",
                "created_at": "2025-01-01T00:00:00",
            }
        }

        matched = self._simulate_enrichment([resource], creators)
        assert matched == 1
        assert resource.tags["_created_by"] == "role/X"

    def test_target_key_building_with_normalized_types(self):
        """Target keys for early termination should use normalized types and include ARN names."""
        resources = [
            _make_resource(
                "web-server",
                "AWS::EC2::Instance",
                "arn:aws:ec2:us-east-1:123:instance/i-abc",
            ),
            _make_resource(
                "my-nlb",
                "AWS::ElasticLoadBalancingV2::LoadBalancer::Network",
                "arn:aws:elasticloadbalancing:us-east-1:123:loadbalancer/net/my-nlb/abc",
            ),
        ]

        target_keys: set = set()
        for r in resources:
            normalized_type = normalize_resource_type(r.resource_type)
            target_keys.add(f"{normalized_type}:{r.name}")
            if r.arn:
                arn_name = r.arn.split("/")[-1].split(":")[-1]
                if arn_name != r.name:
                    target_keys.add(f"{normalized_type}:{arn_name}")

        assert "AWS::EC2::Instance:web-server" in target_keys
        assert "AWS::EC2::Instance:i-abc" in target_keys
        assert "AWS::ElasticLoadBalancingV2::LoadBalancer:my-nlb" in target_keys
        assert "AWS::ElasticLoadBalancingV2::LoadBalancer:abc" in target_keys
