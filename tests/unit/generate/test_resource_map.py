"""Unit tests for ResourceMap and TrackedResource classes."""

from __future__ import annotations

import pytest

from src.models.generation import ResourceMap, TrackedResource


class TestResourceMap:
    """Tests for ResourceMap bidirectional mapping."""

    @pytest.fixture
    def resource_map(self) -> ResourceMap:
        """Create an empty ResourceMap for testing."""
        return ResourceMap()

    @pytest.fixture
    def populated_map(self) -> ResourceMap:
        """Create a ResourceMap with sample mappings."""
        rmap = ResourceMap()
        rmap.add("vpc-12345678", "aws_vpc.main", "ec2:vpc")
        rmap.add("subnet-abcdef12", "aws_subnet.public_1", "ec2:subnet")
        rmap.add("sg-99887766", "aws_security_group.web", "ec2:security-group")
        rmap.add(
            "arn:aws:iam::123456789012:role/MyRole",
            "aws_iam_role.my_role",
            "iam:role",
        )
        return rmap

    def test_add_creates_bidirectional_mapping(self, resource_map: ResourceMap) -> None:
        """Test that add() creates mappings in both directions."""
        resource_map.add("vpc-12345678", "aws_vpc.main", "ec2:vpc")

        assert resource_map.id_to_ref["vpc-12345678"] == "aws_vpc.main"
        assert resource_map.ref_to_id["aws_vpc.main"] == "vpc-12345678"
        assert resource_map.id_to_type["vpc-12345678"] == "ec2:vpc"

    def test_add_multiple_resources(self, resource_map: ResourceMap) -> None:
        """Test adding multiple resources."""
        resource_map.add("vpc-11111111", "aws_vpc.vpc1", "ec2:vpc")
        resource_map.add("vpc-22222222", "aws_vpc.vpc2", "ec2:vpc")
        resource_map.add("subnet-33333333", "aws_subnet.sub1", "ec2:subnet")

        assert len(resource_map.id_to_ref) == 3
        assert len(resource_map.ref_to_id) == 3
        assert len(resource_map.id_to_type) == 3

    def test_add_overwrites_existing(self, resource_map: ResourceMap) -> None:
        """Test that adding same ID overwrites previous mapping."""
        resource_map.add("vpc-12345678", "aws_vpc.old", "ec2:vpc")
        resource_map.add("vpc-12345678", "aws_vpc.new", "ec2:vpc")

        assert resource_map.id_to_ref["vpc-12345678"] == "aws_vpc.new"

    def test_get_reference_returns_correct_reference(
        self, populated_map: ResourceMap
    ) -> None:
        """Test that get_reference returns the correct Terraform reference."""
        ref = populated_map.get_reference("vpc-12345678")
        assert ref == "aws_vpc.main.id"

    def test_get_reference_with_custom_attribute(
        self, populated_map: ResourceMap
    ) -> None:
        """Test get_reference with a custom attribute."""
        ref = populated_map.get_reference("vpc-12345678", attribute="arn")
        assert ref == "aws_vpc.main.arn"

        ref = populated_map.get_reference("sg-99887766", attribute="name")
        assert ref == "aws_security_group.web.name"

    def test_get_reference_returns_none_for_unknown_id(
        self, populated_map: ResourceMap
    ) -> None:
        """Test that get_reference returns None for unknown IDs."""
        ref = populated_map.get_reference("vpc-nonexistent")
        assert ref is None

    def test_get_reference_empty_map(self, resource_map: ResourceMap) -> None:
        """Test get_reference on empty map."""
        ref = resource_map.get_reference("vpc-12345678")
        assert ref is None

    def test_replace_ids_in_code_double_quotes(
        self, populated_map: ResourceMap
    ) -> None:
        """Test replacing IDs in double-quoted strings."""
        code = '''
resource "aws_subnet" "example" {
  vpc_id = "vpc-12345678"
}
'''
        result = populated_map.replace_ids_in_code(code)

        assert '"vpc-12345678"' not in result
        assert "aws_vpc.main.id" in result

    def test_replace_ids_in_code_single_quotes(
        self, populated_map: ResourceMap
    ) -> None:
        """Test replacing IDs in single-quoted strings."""
        code = """
vpc_id = 'vpc-12345678'
"""
        result = populated_map.replace_ids_in_code(code)

        assert "'vpc-12345678'" not in result
        assert "aws_vpc.main.id" in result

    def test_replace_ids_in_code_multiple_ids(
        self, populated_map: ResourceMap
    ) -> None:
        """Test replacing multiple IDs in the same code."""
        code = '''
resource "aws_instance" "web" {
  vpc_id            = "vpc-12345678"
  subnet_id         = "subnet-abcdef12"
  security_groups   = ["sg-99887766"]
}
'''
        result = populated_map.replace_ids_in_code(code)

        assert "aws_vpc.main.id" in result
        assert "aws_subnet.public_1.id" in result
        assert "aws_security_group.web.id" in result
        assert '"vpc-12345678"' not in result
        assert '"subnet-abcdef12"' not in result
        assert '"sg-99887766"' not in result

    def test_replace_ids_in_code_preserves_unknown_ids(
        self, populated_map: ResourceMap
    ) -> None:
        """Test that unknown IDs are preserved unchanged."""
        code = '''
resource "aws_instance" "web" {
  vpc_id    = "vpc-12345678"
  ami       = "ami-unknown12345"
}
'''
        result = populated_map.replace_ids_in_code(code)

        assert "aws_vpc.main.id" in result
        assert '"ami-unknown12345"' in result

    def test_replace_ids_in_code_no_matches(
        self, populated_map: ResourceMap
    ) -> None:
        """Test that code without matching IDs is returned unchanged."""
        code = '''
resource "aws_instance" "web" {
  ami = "ami-12345678"
}
'''
        result = populated_map.replace_ids_in_code(code)
        assert result == code

    def test_replace_ids_in_code_empty_string(
        self, populated_map: ResourceMap
    ) -> None:
        """Test replacing in empty string."""
        result = populated_map.replace_ids_in_code("")
        assert result == ""

    def test_replace_ids_handles_arn_patterns(
        self, populated_map: ResourceMap
    ) -> None:
        """Test replacing ARN patterns."""
        code = '''
role_arn = "arn:aws:iam::123456789012:role/MyRole"
'''
        result = populated_map.replace_ids_in_code(code)

        assert "aws_iam_role.my_role.id" in result
        assert '"arn:aws:iam::123456789012:role/MyRole"' not in result


class TestTrackedResource:
    """Tests for TrackedResource class."""

    @pytest.fixture
    def sample_resource_dict(self) -> dict:
        """Create a sample resource dictionary."""
        return {
            "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-12345678",
            "type": "ec2:instance",
            "name": "my-web-server",
            "region": "us-east-1",
            "tags": {"Environment": "production", "Name": "my-web-server"},
            "raw_config": {
                "InstanceId": "i-12345678",
                "InstanceType": "t3.medium",
                "State": {"Name": "running"},
            },
        }

    @pytest.fixture
    def tracked_resource(self, sample_resource_dict: dict) -> TrackedResource:
        """Create a TrackedResource from sample data."""
        return TrackedResource.from_inventory(sample_resource_dict)

    def test_from_inventory_creates_instance(
        self, sample_resource_dict: dict
    ) -> None:
        """Test that from_inventory creates a proper TrackedResource."""
        resource = TrackedResource.from_inventory(sample_resource_dict)

        assert resource.arn == "arn:aws:ec2:us-east-1:123456789012:instance/i-12345678"
        assert resource.resource_type == "ec2:instance"
        assert resource.name == "my-web-server"
        assert resource.region == "us-east-1"
        assert resource.tags["Environment"] == "production"
        assert resource.raw_config["InstanceType"] == "t3.medium"

    def test_from_inventory_with_resource_type_key(self) -> None:
        """Test from_inventory handles 'resource_type' key (alternative to 'type')."""
        resource_dict = {
            "arn": "arn:aws:s3:::my-bucket",
            "resource_type": "s3:bucket",
            "name": "my-bucket",
            "region": "us-east-1",
        }
        resource = TrackedResource.from_inventory(resource_dict)

        assert resource.resource_type == "s3:bucket"

    def test_from_inventory_with_missing_fields(self) -> None:
        """Test from_inventory handles missing optional fields."""
        minimal_dict = {
            "arn": "arn:aws:s3:::my-bucket",
            "name": "my-bucket",
        }
        resource = TrackedResource.from_inventory(minimal_dict)

        assert resource.arn == "arn:aws:s3:::my-bucket"
        assert resource.name == "my-bucket"
        assert resource.resource_type == ""
        assert resource.region == ""
        assert resource.tags == {}
        assert resource.raw_config == {}

    def test_from_inventory_empty_dict(self) -> None:
        """Test from_inventory handles empty dict."""
        resource = TrackedResource.from_inventory({})

        assert resource.arn == ""
        assert resource.name == ""
        assert resource.resource_type == ""

    def test_default_values(self) -> None:
        """Test TrackedResource default values."""
        resource = TrackedResource(
            arn="arn:aws:s3:::test",
            resource_type="s3:bucket",
            name="test",
            region="us-east-1",
        )

        assert resource.tags == {}
        assert resource.raw_config == {}
        assert resource.layer == ""
        assert resource.terraform_name == ""
        assert resource.terraform_code == ""
        assert resource.is_generated is False
        assert resource.error is None

    def test_get_terraform_name_simple(
        self, tracked_resource: TrackedResource
    ) -> None:
        """Test get_terraform_name with simple name."""
        tf_name = tracked_resource.get_terraform_name()
        assert tf_name == "my_web_server"

    def test_get_terraform_name_caches_result(
        self, tracked_resource: TrackedResource
    ) -> None:
        """Test that get_terraform_name caches the result."""
        tf_name1 = tracked_resource.get_terraform_name()
        tf_name2 = tracked_resource.get_terraform_name()

        assert tf_name1 == tf_name2
        assert tracked_resource.terraform_name == tf_name1

    def test_get_terraform_name_uses_cached_value(self) -> None:
        """Test that get_terraform_name returns cached value if set."""
        resource = TrackedResource(
            arn="arn:aws:s3:::test",
            resource_type="s3:bucket",
            name="test-bucket",
            region="us-east-1",
            terraform_name="custom_name",
        )

        tf_name = resource.get_terraform_name()
        assert tf_name == "custom_name"

    def test_get_terraform_name_replaces_special_chars(self) -> None:
        """Test that special characters are replaced with underscores."""
        resource = TrackedResource(
            arn="arn:aws:s3:::test",
            resource_type="s3:bucket",
            name="my-bucket.with/special:chars",
            region="us-east-1",
        )

        tf_name = resource.get_terraform_name()
        assert "-" not in tf_name
        assert "." not in tf_name
        assert "/" not in tf_name
        assert ":" not in tf_name
        assert tf_name == "my_bucket_with_special_chars"

    def test_get_terraform_name_lowercases(self) -> None:
        """Test that name is lowercased."""
        resource = TrackedResource(
            arn="arn:aws:s3:::test",
            resource_type="s3:bucket",
            name="MyMixedCase_Bucket",
            region="us-east-1",
        )

        tf_name = resource.get_terraform_name()
        assert tf_name == "mymixedcase_bucket"

    def test_get_terraform_name_collapses_underscores(self) -> None:
        """Test that multiple underscores are collapsed."""
        resource = TrackedResource(
            arn="arn:aws:s3:::test",
            resource_type="s3:bucket",
            name="my---bucket___name",
            region="us-east-1",
        )

        tf_name = resource.get_terraform_name()
        assert "__" not in tf_name
        assert "___" not in tf_name

    def test_get_terraform_name_strips_leading_trailing_underscores(self) -> None:
        """Test that leading/trailing underscores are stripped."""
        resource = TrackedResource(
            arn="arn:aws:s3:::test",
            resource_type="s3:bucket",
            name="---bucket-name---",
            region="us-east-1",
        )

        tf_name = resource.get_terraform_name()
        assert not tf_name.startswith("_")
        assert not tf_name.endswith("_")

    def test_get_terraform_name_empty_returns_resource(self) -> None:
        """Test that empty name returns 'resource'."""
        resource = TrackedResource(
            arn="arn:aws:s3:::test",
            resource_type="s3:bucket",
            name="",
            region="us-east-1",
        )

        tf_name = resource.get_terraform_name()
        assert tf_name == "resource"

    def test_get_terraform_name_all_special_chars_returns_resource(self) -> None:
        """Test that name with only special chars returns 'resource'."""
        resource = TrackedResource(
            arn="arn:aws:s3:::test",
            resource_type="s3:bucket",
            name="---...///",
            region="us-east-1",
        )

        tf_name = resource.get_terraform_name()
        assert tf_name == "resource"

    def test_get_terraform_name_starting_with_number(self) -> None:
        """Test that name starting with number gets prefixed."""
        resource = TrackedResource(
            arn="arn:aws:s3:::test",
            resource_type="s3:bucket",
            name="123bucket",
            region="us-east-1",
        )

        tf_name = resource.get_terraform_name()
        assert tf_name.startswith("r_")
        assert "123" in tf_name

    def test_get_terraform_name_starting_with_underscore(self) -> None:
        """Test name starting with underscore after sanitization."""
        resource = TrackedResource(
            arn="arn:aws:s3:::test",
            resource_type="s3:bucket",
            name="-bucket",
            region="us-east-1",
        )

        tf_name = resource.get_terraform_name()
        assert tf_name[0].isalpha()

    def test_get_terraform_name_valid_chars_preserved(self) -> None:
        """Test that valid characters are preserved."""
        resource = TrackedResource(
            arn="arn:aws:s3:::test",
            resource_type="s3:bucket",
            name="valid_name_123",
            region="us-east-1",
        )

        tf_name = resource.get_terraform_name()
        assert tf_name == "valid_name_123"
