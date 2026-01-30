"""Unit tests for EC2 resource collector."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.snapshot.resource_collectors.ec2 import EC2Collector


class TestEC2Collector:
    """Tests for EC2Collector."""

    @pytest.fixture
    def collector(self):
        """Create an EC2Collector instance for testing."""
        mock_session = MagicMock()
        mock_session.profile_name = "default"
        return EC2Collector(session=mock_session, region="us-east-1")

    def test_service_name(self, collector):
        """Test service name property."""
        assert collector.service_name == "ec2"

    def test_is_global_service(self, collector):
        """Test that EC2 is not a global service."""
        assert collector.is_global_service is False

    def test_collect_instances(self, collector):
        """Test collecting EC2 instances."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-abc123",
                                "InstanceType": "t2.micro",
                                "LaunchTime": datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
                                "Tags": [
                                    {"Key": "Name", "Value": "test-instance"},
                                    {"Key": "Environment", "Value": "test"},
                                ],
                            }
                        ]
                    }
                ]
            }
        ]

        with patch.object(collector, "_create_client", return_value=mock_client):
            with patch.object(collector, "_get_account_id", return_value="123456789012"):
                resources = collector._collect_instances("123456789012")

        assert len(resources) == 1
        resource = resources[0]
        assert resource.name == "test-instance"
        assert resource.resource_type == "AWS::EC2::Instance"
        assert resource.region == "us-east-1"
        assert resource.tags == {"Name": "test-instance", "Environment": "test"}
        assert "i-abc123" in resource.arn
        assert resource.created_at == datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)

    def test_collect_instances_no_tags(self, collector):
        """Test collecting EC2 instance without tags uses instance ID as name."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Reservations": [
                    {
                        "Instances": [
                            {
                                "InstanceId": "i-xyz789",
                                "InstanceType": "t3.small",
                                # No Tags key
                            }
                        ]
                    }
                ]
            }
        ]

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_instances("123456789012")

        assert len(resources) == 1
        assert resources[0].name == "i-xyz789"
        assert resources[0].tags == {}

    def test_collect_volumes(self, collector):
        """Test collecting EBS volumes."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Volumes": [
                    {
                        "VolumeId": "vol-abc123",
                        "Size": 100,
                        "VolumeType": "gp3",
                        "CreateTime": datetime(2024, 2, 1, 8, 0, 0, tzinfo=timezone.utc),
                        "Tags": [{"Key": "Name", "Value": "data-volume"}],
                    }
                ]
            }
        ]

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_volumes("123456789012")

        assert len(resources) == 1
        resource = resources[0]
        assert resource.name == "data-volume"
        assert resource.resource_type == "AWS::EC2::Volume"
        assert resource.created_at == datetime(2024, 2, 1, 8, 0, 0, tzinfo=timezone.utc)
        assert "vol-abc123" in resource.arn

    def test_collect_vpcs(self, collector):
        """Test collecting VPCs."""
        mock_client = MagicMock()
        mock_client.describe_vpcs.return_value = {
            "Vpcs": [
                {
                    "VpcId": "vpc-abc123",
                    "CidrBlock": "10.0.0.0/16",
                    "Tags": [{"Key": "Name", "Value": "main-vpc"}],
                }
            ]
        }

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_vpcs("123456789012")

        assert len(resources) == 1
        resource = resources[0]
        assert resource.name == "main-vpc"
        assert resource.resource_type == "AWS::EC2::VPC"
        assert resource.created_at is None  # VPCs don't have creation timestamp
        assert "vpc-abc123" in resource.arn

    def test_collect_security_groups(self, collector):
        """Test collecting security groups."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "SecurityGroups": [
                    {
                        "GroupId": "sg-abc123",
                        "GroupName": "web-servers",
                        "VpcId": "vpc-xyz",
                        "Tags": [{"Key": "Environment", "Value": "prod"}],
                    }
                ]
            }
        ]

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_security_groups("123456789012")

        assert len(resources) == 1
        resource = resources[0]
        assert resource.name == "web-servers"
        assert resource.resource_type == "AWS::EC2::SecurityGroup"
        assert resource.created_at is None  # SGs don't have creation timestamp
        assert resource.tags == {"Environment": "prod"}

    def test_collect_subnets(self, collector):
        """Test collecting subnets."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [
            {
                "Subnets": [
                    {
                        "SubnetId": "subnet-abc123",
                        "VpcId": "vpc-xyz",
                        "CidrBlock": "10.0.1.0/24",
                        "Tags": [{"Key": "Name", "Value": "private-subnet-1"}],
                    }
                ]
            }
        ]

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_subnets("123456789012")

        assert len(resources) == 1
        resource = resources[0]
        assert resource.name == "private-subnet-1"
        assert resource.resource_type == "AWS::EC2::Subnet"
        assert resource.created_at is None  # Subnets don't have creation timestamp

    def test_collect_all_resources(self, collector):
        """Test the main collect() method calls all sub-collectors."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator

        # Setup empty responses for all
        mock_paginator.paginate.return_value = [{"Reservations": []}]
        mock_client.describe_vpcs.return_value = {"Vpcs": []}

        with patch.object(collector, "_create_client", return_value=mock_client):
            with patch.object(collector, "_get_account_id", return_value="123456789012"):
                collector.collect()

        # Should call get_paginator for instances, volumes, security_groups, subnets
        assert mock_client.get_paginator.call_count == 4
        # Should call describe_vpcs once
        assert mock_client.describe_vpcs.call_count == 1

    def test_collect_instances_error_handling(self, collector):
        """Test that instance collection handles errors gracefully."""
        mock_client = MagicMock()
        mock_paginator = MagicMock()
        mock_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.side_effect = Exception("API Error")

        with patch.object(collector, "_create_client", return_value=mock_client):
            resources = collector._collect_instances("123456789012")

        # Should return empty list on error, not raise
        assert resources == []
