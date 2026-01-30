"""Unit tests for resource deletion ordering."""

import pytest
from dataclasses import dataclass
from typing import Optional


@dataclass
class MockResource:
    """Mock resource for testing."""

    resource_type: str
    name: str
    arn: str = ""
    region: str = "us-east-1"


class TestDeletionOrdering:
    """Tests for resource type deletion ordering."""

    def test_get_deletion_tier_known_types(self):
        """Test that known resource types return correct tiers."""
        from src.restore.dependency import get_deletion_tier

        # Tier 1: Application layer
        assert get_deletion_tier("AWS::Lambda::Function") == 1
        assert get_deletion_tier("AWS::ECS::Service") == 1

        # Tier 2: Compute layer
        assert get_deletion_tier("AWS::EC2::Instance") == 2
        assert get_deletion_tier("AWS::RDS::DBInstance") == 2

        # Tier 5: Security groups
        assert get_deletion_tier("AWS::EC2::SecurityGroup") == 5

        # Tier 8: VPCs
        assert get_deletion_tier("AWS::EC2::VPC") == 8

        # Tier 10: IAM
        assert get_deletion_tier("AWS::IAM::Role") == 10

    def test_get_deletion_tier_unknown_type(self):
        """Test that unknown resource types return default tier."""
        from src.restore.dependency import get_deletion_tier, DEFAULT_DELETION_TIER

        assert get_deletion_tier("AWS::Unknown::Resource") == DEFAULT_DELETION_TIER

    def test_sort_resources_for_deletion_basic(self):
        """Test that resources are sorted by deletion tier."""
        from src.restore.dependency import sort_resources_for_deletion

        resources = [
            MockResource("AWS::EC2::VPC", "vpc-1"),  # Tier 8
            MockResource("AWS::Lambda::Function", "func-1"),  # Tier 1
            MockResource("AWS::EC2::Instance", "i-123"),  # Tier 2
            MockResource("AWS::IAM::Role", "role-1"),  # Tier 10
            MockResource("AWS::EC2::SecurityGroup", "sg-1"),  # Tier 5
        ]

        sorted_resources = sort_resources_for_deletion(resources)

        # Lambda (tier 1) should be first
        assert sorted_resources[0].resource_type == "AWS::Lambda::Function"
        # Instance (tier 2) should be second
        assert sorted_resources[1].resource_type == "AWS::EC2::Instance"
        # Security Group (tier 5) should be third
        assert sorted_resources[2].resource_type == "AWS::EC2::SecurityGroup"
        # VPC (tier 8) should be fourth
        assert sorted_resources[3].resource_type == "AWS::EC2::VPC"
        # IAM Role (tier 10) should be last
        assert sorted_resources[4].resource_type == "AWS::IAM::Role"

    def test_sort_resources_same_tier_sorted_by_type_and_name(self):
        """Test that resources in the same tier are sorted by type then name."""
        from src.restore.dependency import sort_resources_for_deletion

        resources = [
            MockResource("AWS::EC2::Instance", "z-instance"),  # Tier 2
            MockResource("AWS::EC2::Instance", "a-instance"),  # Tier 2
            MockResource("AWS::RDS::DBInstance", "db-1"),  # Tier 2
        ]

        sorted_resources = sort_resources_for_deletion(resources)

        # Should be sorted by type first, then name within same type
        assert sorted_resources[0].name == "a-instance"
        assert sorted_resources[1].name == "z-instance"
        assert sorted_resources[2].name == "db-1"

    def test_sort_resources_empty_list(self):
        """Test that empty list is handled correctly."""
        from src.restore.dependency import sort_resources_for_deletion

        result = sort_resources_for_deletion([])
        assert result == []

    def test_sort_resources_single_item(self):
        """Test that single item list is handled correctly."""
        from src.restore.dependency import sort_resources_for_deletion

        resources = [MockResource("AWS::EC2::Instance", "i-123")]
        result = sort_resources_for_deletion(resources)

        assert len(result) == 1
        assert result[0].name == "i-123"

    def test_ec2_dependencies_ordered_correctly(self):
        """Test that EC2 resources are deleted in correct dependency order."""
        from src.restore.dependency import sort_resources_for_deletion

        resources = [
            MockResource("AWS::EC2::VPC", "vpc-1"),
            MockResource("AWS::EC2::InternetGateway", "igw-1"),
            MockResource("AWS::EC2::Subnet", "subnet-1"),
            MockResource("AWS::EC2::SecurityGroup", "sg-1"),
            MockResource("AWS::EC2::Instance", "i-1"),
            MockResource("AWS::EC2::NatGateway", "nat-1"),
        ]

        sorted_resources = sort_resources_for_deletion(resources)
        type_order = [r.resource_type for r in sorted_resources]

        # Instance should come before SecurityGroup
        assert type_order.index("AWS::EC2::Instance") < type_order.index("AWS::EC2::SecurityGroup")
        # SecurityGroup should come before Subnet
        assert type_order.index("AWS::EC2::SecurityGroup") < type_order.index("AWS::EC2::Subnet")
        # Subnet should come before InternetGateway
        assert type_order.index("AWS::EC2::Subnet") < type_order.index("AWS::EC2::InternetGateway")
        # InternetGateway should come before VPC
        assert type_order.index("AWS::EC2::InternetGateway") < type_order.index("AWS::EC2::VPC")

    def test_lambda_deleted_before_iam_role(self):
        """Test that Lambda functions are deleted before IAM roles they might use."""
        from src.restore.dependency import sort_resources_for_deletion

        resources = [
            MockResource("AWS::IAM::Role", "lambda-role"),
            MockResource("AWS::Lambda::Function", "my-function"),
        ]

        sorted_resources = sort_resources_for_deletion(resources)

        assert sorted_resources[0].resource_type == "AWS::Lambda::Function"
        assert sorted_resources[1].resource_type == "AWS::IAM::Role"
