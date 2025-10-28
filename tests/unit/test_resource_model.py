"""Unit tests for Resource model."""

import pytest
from datetime import datetime, timezone
from src.models.resource import Resource


class TestResourceModel:
    """Test cases for Resource model."""

    def test_resource_creation_basic(self):
        """Test creating a basic resource."""
        resource = Resource(
            arn="arn:aws:s3:::my-bucket",
            resource_type="s3:bucket",
            name="my-bucket",
            region="us-east-1",
            config_hash="a" * 64,
            raw_config={"BucketName": "my-bucket"},
        )
        assert resource.arn == "arn:aws:s3:::my-bucket"
        assert resource.resource_type == "s3:bucket"
        assert resource.name == "my-bucket"
        assert resource.region == "us-east-1"
        assert resource.config_hash == "a" * 64
        assert resource.raw_config == {"BucketName": "my-bucket"}
        assert resource.tags == {}
        assert resource.created_at is None

    def test_resource_creation_with_tags(self):
        """Test creating a resource with tags."""
        resource = Resource(
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            resource_type="ec2:instance",
            name="web-server",
            region="us-east-1",
            config_hash="b" * 64,
            raw_config={"InstanceId": "i-1234567890abcdef0"},
            tags={"Environment": "production", "Team": "Alpha"},
        )
        assert resource.tags == {"Environment": "production", "Team": "Alpha"}

    def test_resource_creation_with_timestamp(self):
        """Test creating a resource with creation timestamp."""
        created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        resource = Resource(
            arn="arn:aws:lambda:us-west-2:123456789012:function:my-function",
            resource_type="lambda:function",
            name="my-function",
            region="us-west-2",
            config_hash="c" * 64,
            raw_config={"FunctionName": "my-function"},
            created_at=created_at,
        )
        assert resource.created_at == created_at

    def test_resource_to_dict(self):
        """Test serializing resource to dictionary."""
        created_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        resource = Resource(
            arn="arn:aws:iam::123456789012:role/MyRole",
            resource_type="iam:role",
            name="MyRole",
            region="global",
            config_hash="d" * 64,
            raw_config={"RoleName": "MyRole"},
            tags={"Owner": "DevOps"},
            created_at=created_at,
        )
        data = resource.to_dict()

        assert data["arn"] == "arn:aws:iam::123456789012:role/MyRole"
        assert data["type"] == "iam:role"
        assert data["name"] == "MyRole"
        assert data["region"] == "global"
        assert data["config_hash"] == "d" * 64
        assert data["raw_config"] == {"RoleName": "MyRole"}
        assert data["tags"] == {"Owner": "DevOps"}
        assert data["created_at"] == "2024-01-01T12:00:00+00:00"

    def test_resource_to_dict_no_timestamp(self):
        """Test serializing resource without creation timestamp."""
        resource = Resource(
            arn="arn:aws:s3:::bucket",
            resource_type="s3:bucket",
            name="bucket",
            region="us-east-1",
            config_hash="e" * 64,
            raw_config={},
        )
        data = resource.to_dict()
        assert data["created_at"] is None

    def test_resource_from_dict(self):
        """Test deserializing resource from dictionary."""
        data = {
            "arn": "arn:aws:rds:eu-west-1:123456789012:db:mydb",
            "type": "rds:instance",
            "name": "mydb",
            "region": "eu-west-1",
            "config_hash": "f" * 64,
            "raw_config": {"DBInstanceIdentifier": "mydb"},
            "tags": {"Environment": "staging"},
            "created_at": "2024-01-15T10:30:00+00:00",
        }
        resource = Resource.from_dict(data)

        assert resource.arn == "arn:aws:rds:eu-west-1:123456789012:db:mydb"
        assert resource.resource_type == "rds:instance"
        assert resource.name == "mydb"
        assert resource.region == "eu-west-1"
        assert resource.config_hash == "f" * 64
        assert resource.raw_config == {"DBInstanceIdentifier": "mydb"}
        assert resource.tags == {"Environment": "staging"}
        assert resource.created_at == datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

    def test_resource_from_dict_no_tags(self):
        """Test deserializing resource without tags."""
        data = {
            "arn": "arn:aws:s3:::bucket",
            "type": "s3:bucket",
            "name": "bucket",
            "region": "us-east-1",
            "config_hash": "g" * 64,
            "raw_config": {},
        }
        resource = Resource.from_dict(data)
        assert resource.tags == {}

    def test_resource_from_dict_no_timestamp(self):
        """Test deserializing resource without creation timestamp."""
        data = {
            "arn": "arn:aws:s3:::bucket",
            "type": "s3:bucket",
            "name": "bucket",
            "region": "us-east-1",
            "config_hash": "h" * 64,
            "raw_config": {},
        }
        resource = Resource.from_dict(data)
        assert resource.created_at is None

    def test_resource_roundtrip_serialization(self):
        """Test that to_dict -> from_dict preserves all data."""
        created_at = datetime(2024, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        original = Resource(
            arn="arn:aws:dynamodb:ap-southeast-1:123456789012:table/MyTable",
            resource_type="dynamodb:table",
            name="MyTable",
            region="ap-southeast-1",
            config_hash="i" * 64,
            raw_config={"TableName": "MyTable", "KeySchema": []},
            tags={"Application": "api", "Cost-Center": "engineering"},
            created_at=created_at,
        )

        # Serialize and deserialize
        data = original.to_dict()
        restored = Resource.from_dict(data)

        # Verify all fields match
        assert restored.arn == original.arn
        assert restored.resource_type == original.resource_type
        assert restored.name == original.name
        assert restored.region == original.region
        assert restored.config_hash == original.config_hash
        assert restored.raw_config == original.raw_config
        assert restored.tags == original.tags
        assert restored.created_at == original.created_at

    def test_validate_valid_resource(self):
        """Test validation with valid resource."""
        resource = Resource(
            arn="arn:aws:ec2:us-east-1:123456789012:vpc/vpc-12345678",
            resource_type="ec2:vpc",
            name="main-vpc",
            region="us-east-1",
            config_hash="0123456789abcdef" * 4,  # Valid 64-char hex
            raw_config={},
        )
        assert resource.validate() is True

    def test_validate_invalid_arn_format(self):
        """Test validation with invalid ARN format."""
        resource = Resource(
            arn="not-a-valid-arn",
            resource_type="s3:bucket",
            name="bucket",
            region="us-east-1",
            config_hash="k" * 64,
            raw_config={},
        )
        with pytest.raises(ValueError, match="Invalid ARN format"):
            resource.validate()

    def test_validate_invalid_config_hash_length(self):
        """Test validation with invalid config hash length."""
        resource = Resource(
            arn="arn:aws:s3:::bucket",
            resource_type="s3:bucket",
            name="bucket",
            region="us-east-1",
            config_hash="abc123",  # Too short
            raw_config={},
        )
        with pytest.raises(ValueError, match="Invalid config_hash"):
            resource.validate()

    def test_validate_invalid_config_hash_characters(self):
        """Test validation with non-hex config hash."""
        resource = Resource(
            arn="arn:aws:s3:::bucket",
            resource_type="s3:bucket",
            name="bucket",
            region="us-east-1",
            config_hash="z" * 64,  # Not hex characters
            raw_config={},
        )
        with pytest.raises(ValueError, match="Invalid config_hash"):
            resource.validate()

    def test_validate_global_region(self):
        """Test validation with global region."""
        resource = Resource(
            arn="arn:aws:iam::123456789012:user/john",
            resource_type="iam:user",
            name="john",
            region="global",
            config_hash="fedcba9876543210" * 4,  # Valid 64-char hex
            raw_config={},
        )
        assert resource.validate() is True

    def test_validate_valid_regions(self):
        """Test validation with various valid regions."""
        regions = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1", "ca-central-1"]
        for region in regions:
            resource = Resource(
                arn=f"arn:aws:s3:{region}:123456789012:bucket/test",
                resource_type="s3:bucket",
                name="test",
                region=region,
                config_hash="abcdef0123456789" * 4,  # Valid 64-char hex
                raw_config={},
            )
            assert resource.validate() is True

    def test_service_property_with_colon(self):
        """Test service property extraction with resource type containing colon."""
        resource = Resource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:my-func",
            resource_type="lambda:function",
            name="my-func",
            region="us-east-1",
            config_hash="o" * 64,
            raw_config={},
        )
        assert resource.service == "lambda"

    def test_service_property_without_colon(self):
        """Test service property extraction without colon in resource type."""
        resource = Resource(
            arn="arn:aws:s3:::bucket",
            resource_type="s3",
            name="bucket",
            region="us-east-1",
            config_hash="p" * 64,
            raw_config={},
        )
        assert resource.service == "s3"

    def test_arn_validation_various_services(self):
        """Test ARN validation for various AWS services."""
        valid_arns = [
            "arn:aws:s3:::my-bucket",
            "arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            "arn:aws:iam::123456789012:role/MyRole",
            "arn:aws:lambda:us-west-2:123456789012:function:my-function",
            "arn:aws:rds:eu-west-1:123456789012:db:mydb",
            "arn:aws:dynamodb:ap-southeast-1:123456789012:table/MyTable",
            "arn:aws:sns:us-east-1:123456789012:my-topic",
            "arn:aws:sqs:us-east-1:123456789012:my-queue",
        ]

        for arn in valid_arns:
            resource = Resource(
                arn=arn,
                resource_type="test:type",
                name="test",
                region="us-east-1",
                config_hash="123456789abcdef0" * 4,  # Valid 64-char hex
                raw_config={},
            )
            assert resource.validate() is True

    def test_resource_with_complex_raw_config(self):
        """Test resource with complex nested raw configuration."""
        raw_config = {
            "InstanceId": "i-1234567890abcdef0",
            "InstanceType": "t3.micro",
            "SecurityGroups": [
                {"GroupId": "sg-12345", "GroupName": "web"},
                {"GroupId": "sg-67890", "GroupName": "ssh"},
            ],
            "Tags": [
                {"Key": "Environment", "Value": "production"},
                {"Key": "Team", "Value": "Alpha"},
            ],
            "BlockDeviceMappings": [
                {
                    "DeviceName": "/dev/xvda",
                    "Ebs": {"VolumeId": "vol-12345", "VolumeSize": 30},
                }
            ],
        }

        resource = Resource(
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-1234567890abcdef0",
            resource_type="ec2:instance",
            name="web-server-01",
            region="us-east-1",
            config_hash="r" * 64,
            raw_config=raw_config,
            tags={"Environment": "production", "Team": "Alpha"},
        )

        # Verify serialization preserves complex structure
        data = resource.to_dict()
        restored = Resource.from_dict(data)
        assert restored.raw_config == raw_config

    def test_resource_equality_via_dict_comparison(self):
        """Test that resources with same data produce same dict representation."""
        resource1 = Resource(
            arn="arn:aws:s3:::bucket",
            resource_type="s3:bucket",
            name="bucket",
            region="us-east-1",
            config_hash="s" * 64,
            raw_config={"BucketName": "bucket"},
        )

        resource2 = Resource(
            arn="arn:aws:s3:::bucket",
            resource_type="s3:bucket",
            name="bucket",
            region="us-east-1",
            config_hash="s" * 64,
            raw_config={"BucketName": "bucket"},
        )

        assert resource1.to_dict() == resource2.to_dict()
