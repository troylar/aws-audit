"""Tests for WAF resource collector."""

from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.waf import WAFCollector


@pytest.fixture
def mock_session():
    """Create a mock boto3 session."""
    session = MagicMock()
    session.profile_name = "default"
    return session


class TestWAFCollectorProperties:
    """Tests for WAFCollector properties."""

    def test_service_name(self, mock_session):
        """Test service_name property returns waf."""
        collector = WAFCollector(session=mock_session, region="us-east-1")
        assert collector.service_name == "waf"


class TestWAFCollectorCollect:
    """Tests for WAFCollector.collect method."""

    @patch.object(WAFCollector, "_create_client")
    def test_collect_no_web_acls(self, mock_create_client, mock_session):
        """Test collecting when no Web ACLs exist."""
        mock_client = MagicMock()

        mock_regional_paginator = MagicMock()
        mock_regional_paginator.paginate.return_value = [{"WebACLs": []}]

        mock_cf_paginator = MagicMock()
        mock_cf_paginator.paginate.return_value = [{"WebACLs": []}]

        call_count = [0]

        def get_paginator_side_effect(op):
            if op == "list_web_acls":
                call_count[0] += 1
                if call_count[0] == 1:
                    return mock_regional_paginator
                return mock_cf_paginator

        mock_client.get_paginator.side_effect = get_paginator_side_effect
        mock_create_client.return_value = mock_client

        # Test from us-east-1 (collects both regional and CloudFront)
        collector = WAFCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert resources == []

    @patch.object(WAFCollector, "_create_client")
    def test_collect_single_regional_web_acl(self, mock_create_client, mock_session):
        """Test collecting a single regional Web ACL."""
        mock_client = MagicMock()

        mock_regional_paginator = MagicMock()
        mock_regional_paginator.paginate.return_value = [{
            "WebACLs": [{
                "Name": "my-web-acl",
                "Id": "web-acl-123",
                "ARN": "arn:aws:wafv2:us-east-1:123456789012:regional/webacl/my-web-acl/123",
            }]
        }]

        mock_cf_paginator = MagicMock()
        mock_cf_paginator.paginate.return_value = [{"WebACLs": []}]

        def paginate_side_effect(**kwargs):
            if kwargs.get("Scope") == "REGIONAL":
                return mock_regional_paginator.paginate.return_value
            return mock_cf_paginator.paginate.return_value

        mock_paginator = MagicMock()
        mock_paginator.paginate = paginate_side_effect

        mock_client.get_paginator.return_value = mock_paginator
        mock_client.get_web_acl.return_value = {
            "WebACL": {
                "Name": "my-web-acl",
                "Rules": [{"Name": "rule1"}, {"Name": "rule2"}],
            }
        }
        mock_client.list_tags_for_resource.return_value = {
            "TagInfoForResource": {
                "TagList": [{"Key": "Environment", "Value": "test"}]
            }
        }
        mock_create_client.return_value = mock_client

        collector = WAFCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should have 1 regional Web ACL (CloudFront returned empty)
        regional_acls = [r for r in resources if "Regional" in r.resource_type]
        assert len(regional_acls) == 1
        assert regional_acls[0].name == "my-web-acl"
        assert regional_acls[0].resource_type == "AWS::WAFv2::WebACL::Regional"
        assert regional_acls[0].tags == {"Environment": "test"}
        # Rules should be excluded from raw_config
        assert "Rules" not in regional_acls[0].raw_config
        # But RuleCount should be included
        assert regional_acls[0].raw_config["RuleCount"] == 2

    @patch.object(WAFCollector, "_create_client")
    def test_collect_single_cloudfront_web_acl(self, mock_create_client, mock_session):
        """Test collecting a single CloudFront Web ACL from us-east-1."""
        mock_client = MagicMock()

        def paginate_side_effect(**kwargs):
            if kwargs.get("Scope") == "REGIONAL":
                return [{"WebACLs": []}]
            elif kwargs.get("Scope") == "CLOUDFRONT":
                return [{
                    "WebACLs": [{
                        "Name": "cf-web-acl",
                        "Id": "cf-acl-123",
                        "ARN": "arn:aws:wafv2:global:123456789012:global/webacl/cf-web-acl/123",
                    }]
                }]
            return [{"WebACLs": []}]

        mock_paginator = MagicMock()
        mock_paginator.paginate = paginate_side_effect

        mock_client.get_paginator.return_value = mock_paginator
        mock_client.get_web_acl.return_value = {
            "WebACL": {
                "Name": "cf-web-acl",
                "Rules": [],
            }
        }
        mock_client.list_tags_for_resource.return_value = {
            "TagInfoForResource": {"TagList": []}
        }
        mock_create_client.return_value = mock_client

        collector = WAFCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        cf_acls = [r for r in resources if "CloudFront" in r.resource_type]
        assert len(cf_acls) == 1
        assert cf_acls[0].name == "cf-web-acl"
        assert cf_acls[0].resource_type == "AWS::WAFv2::WebACL::CloudFront"
        assert cf_acls[0].region == "global"

    @patch.object(WAFCollector, "_create_client")
    def test_collect_non_us_east_1_skips_cloudfront(self, mock_create_client, mock_session):
        """Test that CloudFront Web ACLs are only collected from us-east-1."""
        mock_client = MagicMock()

        mock_paginator = MagicMock()
        mock_paginator.paginate.return_value = [{"WebACLs": []}]
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        # Test from us-west-2 (should NOT collect CloudFront)
        collector = WAFCollector(session=mock_session, region="us-west-2")
        resources = collector.collect()

        assert resources == []
        # Should only call paginate once for REGIONAL (not CLOUDFRONT)
        assert mock_paginator.paginate.call_count == 1

    @patch.object(WAFCollector, "_create_client")
    def test_collect_handles_get_web_acl_error(self, mock_create_client, mock_session):
        """Test collecting continues when get_web_acl fails."""
        mock_client = MagicMock()

        def paginate_side_effect(**kwargs):
            if kwargs.get("Scope") == "REGIONAL":
                return [{
                    "WebACLs": [
                        {"Name": "good-acl", "Id": "1", "ARN": "arn:1"},
                        {"Name": "bad-acl", "Id": "2", "ARN": "arn:2"},
                    ]
                }]
            return [{"WebACLs": []}]

        mock_paginator = MagicMock()
        mock_paginator.paginate = paginate_side_effect
        mock_client.get_paginator.return_value = mock_paginator

        def get_web_acl_side_effect(**kwargs):
            if kwargs["Name"] == "bad-acl":
                raise Exception("Access denied")
            return {"WebACL": {"Name": kwargs["Name"], "Rules": []}}

        mock_client.get_web_acl.side_effect = get_web_acl_side_effect
        mock_client.list_tags_for_resource.return_value = {
            "TagInfoForResource": {"TagList": []}
        }
        mock_create_client.return_value = mock_client

        collector = WAFCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should only get the good ACL
        regional_acls = [r for r in resources if "Regional" in r.resource_type]
        assert len(regional_acls) == 1
        assert regional_acls[0].name == "good-acl"

    @patch.object(WAFCollector, "_create_client")
    def test_collect_handles_tags_error(self, mock_create_client, mock_session):
        """Test collecting continues when list_tags_for_resource fails."""
        mock_client = MagicMock()

        def paginate_side_effect(**kwargs):
            if kwargs.get("Scope") == "REGIONAL":
                return [{
                    "WebACLs": [{
                        "Name": "my-acl",
                        "Id": "1",
                        "ARN": "arn:1",
                    }]
                }]
            return [{"WebACLs": []}]

        mock_paginator = MagicMock()
        mock_paginator.paginate = paginate_side_effect
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.get_web_acl.return_value = {
            "WebACL": {"Name": "my-acl", "Rules": []}
        }
        mock_client.list_tags_for_resource.side_effect = Exception("Access denied")
        mock_create_client.return_value = mock_client

        collector = WAFCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still get the ACL without tags
        regional_acls = [r for r in resources if "Regional" in r.resource_type]
        assert len(regional_acls) == 1
        assert regional_acls[0].tags == {}

    @patch.object(WAFCollector, "_create_client")
    def test_collect_handles_list_error(self, mock_create_client, mock_session):
        """Test collecting handles list_web_acls error."""
        mock_client = MagicMock()

        mock_paginator = MagicMock()
        mock_paginator.paginate.side_effect = Exception("Service unavailable")
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = WAFCollector(session=mock_session, region="us-west-2")
        resources = collector.collect()

        # Should return empty list on error
        assert resources == []

    @patch.object(WAFCollector, "_create_client")
    def test_collect_generates_config_hash(self, mock_create_client, mock_session):
        """Test that config hash is generated."""
        mock_client = MagicMock()

        def paginate_side_effect(**kwargs):
            if kwargs.get("Scope") == "REGIONAL":
                return [{
                    "WebACLs": [{
                        "Name": "my-acl",
                        "Id": "1",
                        "ARN": "arn:1",
                    }]
                }]
            return [{"WebACLs": []}]

        mock_paginator = MagicMock()
        mock_paginator.paginate = paginate_side_effect
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.get_web_acl.return_value = {
            "WebACL": {"Name": "my-acl", "Rules": []}
        }
        mock_client.list_tags_for_resource.return_value = {
            "TagInfoForResource": {"TagList": []}
        }
        mock_create_client.return_value = mock_client

        collector = WAFCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        regional_acls = [r for r in resources if "Regional" in r.resource_type]
        assert len(regional_acls) == 1
        assert regional_acls[0].config_hash is not None
        assert len(regional_acls[0].config_hash) > 0

    @patch.object(WAFCollector, "_create_client")
    def test_collect_both_regional_and_cloudfront(self, mock_create_client, mock_session):
        """Test collecting both regional and CloudFront Web ACLs."""
        mock_client = MagicMock()

        def paginate_side_effect(**kwargs):
            if kwargs.get("Scope") == "REGIONAL":
                return [{
                    "WebACLs": [{
                        "Name": "regional-acl",
                        "Id": "1",
                        "ARN": "arn:1",
                    }]
                }]
            elif kwargs.get("Scope") == "CLOUDFRONT":
                return [{
                    "WebACLs": [{
                        "Name": "cf-acl",
                        "Id": "2",
                        "ARN": "arn:2",
                    }]
                }]
            return [{"WebACLs": []}]

        mock_paginator = MagicMock()
        mock_paginator.paginate = paginate_side_effect
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.get_web_acl.return_value = {
            "WebACL": {"Rules": []}
        }
        mock_client.list_tags_for_resource.return_value = {
            "TagInfoForResource": {"TagList": []}
        }
        mock_create_client.return_value = mock_client

        collector = WAFCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        assert len(resources) == 2
        regional_acls = [r for r in resources if "Regional" in r.resource_type]
        cf_acls = [r for r in resources if "CloudFront" in r.resource_type]
        assert len(regional_acls) == 1
        assert len(cf_acls) == 1

    @patch.object(WAFCollector, "_create_client")
    def test_collect_cloudfront_handles_tags_error(self, mock_create_client, mock_session):
        """Test CloudFront Web ACL collection continues when list_tags_for_resource fails."""
        mock_client = MagicMock()

        def paginate_side_effect(**kwargs):
            if kwargs.get("Scope") == "REGIONAL":
                return [{"WebACLs": []}]
            elif kwargs.get("Scope") == "CLOUDFRONT":
                return [{
                    "WebACLs": [{
                        "Name": "cf-acl",
                        "Id": "1",
                        "ARN": "arn:aws:wafv2:global:123456789012:global/webacl/cf-acl/123",
                    }]
                }]
            return [{"WebACLs": []}]

        mock_paginator = MagicMock()
        mock_paginator.paginate = paginate_side_effect
        mock_client.get_paginator.return_value = mock_paginator
        mock_client.get_web_acl.return_value = {
            "WebACL": {"Name": "cf-acl", "Rules": []}
        }
        mock_client.list_tags_for_resource.side_effect = Exception("Access denied")
        mock_create_client.return_value = mock_client

        collector = WAFCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should still get the CloudFront ACL without tags
        cf_acls = [r for r in resources if "CloudFront" in r.resource_type]
        assert len(cf_acls) == 1
        assert cf_acls[0].tags == {}

    @patch.object(WAFCollector, "_create_client")
    def test_collect_cloudfront_handles_get_web_acl_error(self, mock_create_client, mock_session):
        """Test CloudFront collection continues when get_web_acl fails for one ACL."""
        mock_client = MagicMock()

        def paginate_side_effect(**kwargs):
            if kwargs.get("Scope") == "REGIONAL":
                return [{"WebACLs": []}]
            elif kwargs.get("Scope") == "CLOUDFRONT":
                return [{
                    "WebACLs": [
                        {"Name": "good-cf-acl", "Id": "1", "ARN": "arn:1"},
                        {"Name": "bad-cf-acl", "Id": "2", "ARN": "arn:2"},
                    ]
                }]
            return [{"WebACLs": []}]

        mock_paginator = MagicMock()
        mock_paginator.paginate = paginate_side_effect
        mock_client.get_paginator.return_value = mock_paginator

        def get_web_acl_side_effect(**kwargs):
            if kwargs["Name"] == "bad-cf-acl":
                raise Exception("Access denied")
            return {"WebACL": {"Name": kwargs["Name"], "Rules": []}}

        mock_client.get_web_acl.side_effect = get_web_acl_side_effect
        mock_client.list_tags_for_resource.return_value = {
            "TagInfoForResource": {"TagList": []}
        }
        mock_create_client.return_value = mock_client

        collector = WAFCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should only get the good CloudFront ACL
        cf_acls = [r for r in resources if "CloudFront" in r.resource_type]
        assert len(cf_acls) == 1
        assert cf_acls[0].name == "good-cf-acl"

    @patch.object(WAFCollector, "_create_client")
    def test_collect_cloudfront_handles_list_error(self, mock_create_client, mock_session):
        """Test CloudFront collection handles list_web_acls error gracefully."""
        mock_client = MagicMock()

        call_count = [0]

        def paginate_side_effect(**kwargs):
            call_count[0] += 1
            if kwargs.get("Scope") == "REGIONAL":
                return [{"WebACLs": []}]
            elif kwargs.get("Scope") == "CLOUDFRONT":
                raise Exception("Service unavailable for CloudFront")
            return [{"WebACLs": []}]

        mock_paginator = MagicMock()
        mock_paginator.paginate = paginate_side_effect
        mock_client.get_paginator.return_value = mock_paginator
        mock_create_client.return_value = mock_client

        collector = WAFCollector(session=mock_session, region="us-east-1")
        resources = collector.collect()

        # Should return empty list since both failed (regional empty, CF errored)
        assert resources == []
