"""Unit tests for IAM resource collector."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.iam import IAMCollector


class TestIAMCollector:
    """Tests for IAMCollector."""

    @pytest.fixture
    def collector(self):
        """Create an IAMCollector instance for testing."""
        mock_session = MagicMock()
        mock_session.profile_name = "default"
        return IAMCollector(session=mock_session, region="us-east-1")

    def test_service_name(self, collector):
        """Test service name property."""
        assert collector.service_name == "iam"

    def test_is_global_service(self, collector):
        """Test that IAM is a global service."""
        assert collector.is_global_service is True

    def test_collect_roles(self, collector):
        """Test collecting IAM roles."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Roles": [
                    {
                        "RoleName": "test-role",
                        "Arn": "arn:aws:iam::123456789012:role/test-role",
                        "CreateDate": datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
                        "AssumeRolePolicyDocument": {},
                    }
                ]
            }
        ]
        mock_client.list_role_tags.return_value = {"Tags": [{"Key": "Environment", "Value": "test"}]}

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_roles("123456789012")

        assert len(resources) == 1
        resource = resources[0]
        assert resource.name == "test-role"
        assert resource.resource_type == "AWS::IAM::Role"
        assert resource.region == "global"
        assert resource.tags == {"Environment": "test"}
        assert resource.created_at == datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

    def test_collect_roles_tag_error(self, collector):
        """Test collecting IAM roles when tag retrieval fails."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Roles": [
                    {
                        "RoleName": "no-tags-role",
                        "Arn": "arn:aws:iam::123456789012:role/no-tags-role",
                        "CreateDate": datetime.now(timezone.utc),
                    }
                ]
            }
        ]
        mock_client.list_role_tags.side_effect = Exception("Access Denied")

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_roles("123456789012")

        assert len(resources) == 1
        assert resources[0].tags == {}

    def test_collect_users(self, collector):
        """Test collecting IAM users."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Users": [
                    {
                        "UserName": "test-user",
                        "Arn": "arn:aws:iam::123456789012:user/test-user",
                        "CreateDate": datetime(2024, 2, 1, 8, 0, 0, tzinfo=timezone.utc),
                    }
                ]
            }
        ]
        mock_client.list_user_tags.return_value = {"Tags": [{"Key": "Team", "Value": "engineering"}]}

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_users("123456789012")

        assert len(resources) == 1
        resource = resources[0]
        assert resource.name == "test-user"
        assert resource.resource_type == "AWS::IAM::User"
        assert resource.region == "global"
        assert resource.tags == {"Team": "engineering"}

    def test_collect_groups(self, collector):
        """Test collecting IAM groups."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Groups": [
                    {
                        "GroupName": "developers",
                        "Arn": "arn:aws:iam::123456789012:group/developers",
                        "CreateDate": datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
                    }
                ]
            }
        ]

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_groups("123456789012")

        assert len(resources) == 1
        resource = resources[0]
        assert resource.name == "developers"
        assert resource.resource_type == "AWS::IAM::Group"
        assert resource.tags == {}  # Groups don't support tags

    def test_collect_policies(self, collector):
        """Test collecting customer-managed IAM policies."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Policies": [
                    {
                        "PolicyName": "custom-policy",
                        "Arn": "arn:aws:iam::123456789012:policy/custom-policy",
                        "CreateDate": datetime(2024, 3, 15, 12, 0, 0, tzinfo=timezone.utc),
                    }
                ]
            }
        ]
        mock_client.list_policy_tags.return_value = {"Tags": [{"Key": "Purpose", "Value": "security"}]}

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_policies("123456789012")

        assert len(resources) == 1
        resource = resources[0]
        assert resource.name == "custom-policy"
        assert resource.resource_type == "AWS::IAM::Policy"
        assert resource.tags == {"Purpose": "security"}

    def test_collect_all_resources(self, collector):
        """Test the main collect() method calls all sub-collectors."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {"Roles": []},
        ]

        with patch.object(collector, "_create_client", return_value=mock_client):
            with patch.object(collector, "_get_account_id", return_value="123456789012"):
                resources = collector.collect()

        # Should call get_paginator for roles, users, groups, policies
        assert mock_client.get_paginator.call_count == 4

    def test_collect_roles_error_handling(self, collector):
        """Test that role collection handles errors gracefully."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.side_effect = Exception("API Error")

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_roles("123456789012")

        assert resources == []

    def test_collect_multiple_roles(self, collector):
        """Test collecting multiple IAM roles."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Roles": [
                    {
                        "RoleName": "role-1",
                        "Arn": "arn:aws:iam::123456789012:role/role-1",
                        "CreateDate": datetime.now(timezone.utc),
                    },
                    {
                        "RoleName": "role-2",
                        "Arn": "arn:aws:iam::123456789012:role/role-2",
                        "CreateDate": datetime.now(timezone.utc),
                    },
                ]
            }
        ]
        mock_client.list_role_tags.return_value = {"Tags": []}

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_roles("123456789012")

        assert len(resources) == 2
        assert {r.name for r in resources} == {"role-1", "role-2"}
