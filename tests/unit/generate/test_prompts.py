"""Unit tests for Terraform prompt templates (T033)."""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.models.generation import Layer, ResourceMap, TrackedResource


def _mock_get_property_map(resource_type: str) -> None:
    """Mock property map lookup that returns None."""
    return None


def _setup_mocks() -> None:
    """Setup mocks for problematic imports before loading terraform prompts."""
    mock_langgraph = MagicMock()
    mock_langgraph.graph = MagicMock()
    mock_langgraph.graph.END = "END"
    mock_langgraph.graph.StateGraph = MagicMock()
    sys.modules["langgraph"] = mock_langgraph
    sys.modules["langgraph.graph"] = mock_langgraph.graph

    mock_property_maps = MagicMock()
    mock_property_maps.get_property_map = _mock_get_property_map
    sys.modules["src.generate.property_maps"] = mock_property_maps


_setup_mocks()

from src.generate.prompts import terraform as terraform_prompts_module


class TestTerraformSystemPrompt:
    """Tests for get_terraform_system_prompt() and TERRAFORM_SYSTEM_PROMPT."""

    @pytest.fixture
    def terraform_prompts(self) -> Any:
        """Return the terraform prompts module."""
        return terraform_prompts_module

    def test_get_terraform_system_prompt_returns_string(self, terraform_prompts: Any) -> None:
        """Test that get_terraform_system_prompt returns a string."""
        result = terraform_prompts.get_terraform_system_prompt()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_terraform_system_prompt_matches_constant(self, terraform_prompts: Any) -> None:
        """Test that function returns the same value as the constant."""
        assert terraform_prompts.get_terraform_system_prompt() == terraform_prompts.TERRAFORM_SYSTEM_PROMPT

    def test_prompt_contains_resource_reference_instructions(self, terraform_prompts: Any) -> None:
        """Test prompt contains instructions for resource references."""
        prompt = terraform_prompts.get_terraform_system_prompt()
        assert "Resource References" in prompt

    def test_prompt_mentions_terraform_references_example(self, terraform_prompts: Any) -> None:
        """Test prompt includes Terraform reference example."""
        prompt = terraform_prompts.get_terraform_system_prompt()
        assert "aws_vpc" in prompt or "aws_vpc.main.id" in prompt.lower()

    def test_prompt_warns_against_hardcoded_ids(self, terraform_prompts: Any) -> None:
        """Test prompt mentions using references instead of hardcoded IDs."""
        prompt = terraform_prompts.get_terraform_system_prompt()
        assert "hardcoded" in prompt.lower() or "instead of" in prompt.lower()

    def test_prompt_mentions_resource_map(self, terraform_prompts: Any) -> None:
        """Test prompt mentions the resource map."""
        prompt = terraform_prompts.get_terraform_system_prompt()
        assert "resource map" in prompt.lower()

    def test_prompt_contains_variable_usage_instructions(self, terraform_prompts: Any) -> None:
        """Test prompt includes variable usage guidance."""
        prompt = terraform_prompts.get_terraform_system_prompt()
        assert "Variable" in prompt

    def test_prompt_contains_output_generation_instructions(self, terraform_prompts: Any) -> None:
        """Test prompt includes output generation guidance."""
        prompt = terraform_prompts.get_terraform_system_prompt()
        assert "Output" in prompt

    def test_prompt_mentions_provider_config(self, terraform_prompts: Any) -> None:
        """Test prompt mentions provider configuration."""
        prompt = terraform_prompts.get_terraform_system_prompt()
        assert "Provider" in prompt or "provider" in prompt

    def test_prompt_mentions_naming_convention(self, terraform_prompts: Any) -> None:
        """Test prompt mentions naming conventions."""
        prompt = terraform_prompts.get_terraform_system_prompt()
        assert "Naming" in prompt or "naming" in prompt or "terraform names" in prompt.lower()

    def test_prompt_mentions_dependencies(self, terraform_prompts: Any) -> None:
        """Test prompt includes dependency handling instructions."""
        prompt = terraform_prompts.get_terraform_system_prompt()
        assert "Dependencies" in prompt or "depends_on" in prompt

    def test_prompt_contains_best_practices(self, terraform_prompts: Any) -> None:
        """Test prompt includes Terraform best practices."""
        prompt = terraform_prompts.get_terraform_system_prompt()
        assert "Best Practices" in prompt

    def test_prompt_specifies_hcl_output(self, terraform_prompts: Any) -> None:
        """Test prompt specifies HCL output format."""
        prompt = terraform_prompts.get_terraform_system_prompt()
        assert "HCL" in prompt

    def test_prompt_mentions_no_markdown(self, terraform_prompts: Any) -> None:
        """Test prompt instructs not to include markdown."""
        prompt = terraform_prompts.get_terraform_system_prompt()
        assert "no markdown" in prompt.lower() or "only valid hcl" in prompt.lower()


class TestLayerPromptGeneration:
    """Tests for format_layer_prompt()."""

    @pytest.fixture
    def terraform_prompts(self) -> Any:
        """Return the terraform prompts module."""
        return terraform_prompts_module

    @pytest.fixture
    def sample_layer(self) -> Layer:
        """Create a sample layer with resources for testing."""
        return Layer(
            name="NETWORK",
            order=1,
            status="pending",
            resources=[
                {
                    "arn": "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-12345678",
                    "type": "ec2:vpc",
                    "name": "main-vpc",
                    "region": "us-east-1",
                    "tags": {"Environment": "production"},
                    "raw_config": {"CidrBlock": "10.0.0.0/16", "EnableDnsHostnames": True},
                },
                {
                    "arn": "arn:aws:ec2:us-east-1:123456789012:subnet/subnet-abcdef12",
                    "type": "ec2:subnet",
                    "name": "public-subnet-1",
                    "region": "us-east-1",
                    "tags": {"Tier": "public"},
                    "raw_config": {"CidrBlock": "10.0.1.0/24", "VpcId": "vpc-12345678"},
                },
            ],
        )

    @pytest.fixture
    def empty_layer(self) -> Layer:
        """Create an empty layer for testing."""
        return Layer(
            name="EMPTY",
            order=99,
            status="pending",
            resources=[],
        )

    @pytest.fixture
    def sample_resource_map(self) -> ResourceMap:
        """Create a sample resource map with existing references."""
        rmap = ResourceMap()
        rmap.add("vpc-existing123", "aws_vpc.existing", "ec2:vpc")
        rmap.add("sg-existing456", "aws_security_group.existing", "ec2:security-group")
        rmap.add(
            "arn:aws:iam::123456789012:role/ExistingRole",
            "aws_iam_role.existing",
            "iam:role",
        )
        return rmap

    @pytest.fixture
    def empty_resource_map(self) -> ResourceMap:
        """Create an empty resource map."""
        return ResourceMap()

    def test_prompt_includes_layer_name(
        self, terraform_prompts: Any, sample_layer: Layer, empty_resource_map: ResourceMap
    ) -> None:
        """Test prompt includes the layer name."""
        prompt = terraform_prompts.format_layer_prompt(sample_layer, empty_resource_map)
        assert "NETWORK" in prompt

    def test_prompt_includes_resource_count(
        self, terraform_prompts: Any, sample_layer: Layer, empty_resource_map: ResourceMap
    ) -> None:
        """Test prompt includes total resource count."""
        prompt = terraform_prompts.format_layer_prompt(sample_layer, empty_resource_map)
        assert "2 resources" in prompt

    def test_prompt_includes_resource_descriptions(
        self, terraform_prompts: Any, sample_layer: Layer, empty_resource_map: ResourceMap
    ) -> None:
        """Test prompt includes resource descriptions."""
        prompt = terraform_prompts.format_layer_prompt(sample_layer, empty_resource_map)
        assert "main-vpc" in prompt or "main_vpc" in prompt
        assert "public-subnet-1" in prompt or "public_subnet_1" in prompt

    def test_prompt_includes_resource_types(
        self, terraform_prompts: Any, sample_layer: Layer, empty_resource_map: ResourceMap
    ) -> None:
        """Test prompt includes resource types."""
        prompt = terraform_prompts.format_layer_prompt(sample_layer, empty_resource_map)
        assert "ec2:vpc" in prompt
        assert "ec2:subnet" in prompt

    def test_prompt_includes_resource_properties(
        self, terraform_prompts: Any, sample_layer: Layer, empty_resource_map: ResourceMap
    ) -> None:
        """Test prompt includes resource properties."""
        prompt = terraform_prompts.format_layer_prompt(sample_layer, empty_resource_map)
        assert "10.0.0.0/16" in prompt
        assert "10.0.1.0/24" in prompt

    def test_prompt_includes_existing_resource_references(
        self, terraform_prompts: Any, sample_layer: Layer, sample_resource_map: ResourceMap
    ) -> None:
        """Test prompt includes existing resource map for references."""
        prompt = terraform_prompts.format_layer_prompt(sample_layer, sample_resource_map)
        assert "Available Resource References" in prompt
        assert "vpc-existing123" in prompt
        assert "aws_vpc.existing" in prompt

    def test_prompt_includes_multiple_resource_references(
        self, terraform_prompts: Any, sample_layer: Layer, sample_resource_map: ResourceMap
    ) -> None:
        """Test prompt includes all resource references."""
        prompt = terraform_prompts.format_layer_prompt(sample_layer, sample_resource_map)
        assert "sg-existing456" in prompt
        assert "aws_security_group.existing" in prompt

    def test_prompt_includes_previous_layers_context(
        self, terraform_prompts: Any, sample_layer: Layer, empty_resource_map: ResourceMap
    ) -> None:
        """Test prompt includes previous layers when provided."""
        previous = ["network.tf", "security.tf"]
        prompt = terraform_prompts.format_layer_prompt(sample_layer, empty_resource_map, previous)
        assert "Previously Generated Layers" in prompt
        assert "network.tf" in prompt
        assert "security.tf" in prompt

    def test_prompt_excludes_previous_layers_when_none(
        self, terraform_prompts: Any, sample_layer: Layer, empty_resource_map: ResourceMap
    ) -> None:
        """Test prompt excludes previous layers section when None."""
        prompt = terraform_prompts.format_layer_prompt(sample_layer, empty_resource_map, None)
        assert "Previously Generated Layers" not in prompt

    def test_empty_layer_generates_valid_prompt(
        self, terraform_prompts: Any, empty_layer: Layer, empty_resource_map: ResourceMap
    ) -> None:
        """Test that empty layer generates a valid prompt."""
        prompt = terraform_prompts.format_layer_prompt(empty_layer, empty_resource_map)
        assert "EMPTY" in prompt
        assert "0 resources" in prompt

    def test_prompt_instructs_to_generate_hcl(
        self, terraform_prompts: Any, sample_layer: Layer, empty_resource_map: ResourceMap
    ) -> None:
        """Test prompt instructs generation of Terraform HCL."""
        prompt = terraform_prompts.format_layer_prompt(sample_layer, empty_resource_map)
        assert "Terraform" in prompt or "HCL" in prompt


class TestResourceToPromptFormatter:
    """Tests for format_resource_for_prompt()."""

    @pytest.fixture
    def terraform_prompts(self) -> Any:
        """Return the terraform prompts module."""
        return terraform_prompts_module

    @pytest.fixture
    def sample_ec2_resource(self) -> TrackedResource:
        """Create a sample EC2 instance resource."""
        return TrackedResource(
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-12345678",
            resource_type="ec2:instance",
            name="web-server-1",
            region="us-east-1",
            tags={"Environment": "production", "Application": "web"},
            raw_config={
                "InstanceId": "i-12345678",
                "InstanceType": "t3.medium",
                "SubnetId": "subnet-abc12345",
                "SecurityGroupIds": ["sg-12345678"],
                "PublicIpAddress": "54.123.45.67",
                "PrivateIpAddress": "10.0.1.50",
            },
        )

    @pytest.fixture
    def sample_lambda_resource(self) -> TrackedResource:
        """Create a sample Lambda function resource."""
        return TrackedResource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:my-function",
            resource_type="lambda:function",
            name="my-function",
            region="us-east-1",
            tags={"Team": "platform"},
            raw_config={
                "FunctionName": "my-function",
                "Runtime": "python3.11",
                "Handler": "index.handler",
                "MemorySize": 256,
                "Timeout": 30,
            },
        )

    def test_format_includes_resource_type(self, terraform_prompts: Any, sample_ec2_resource: TrackedResource) -> None:
        """Test formatted output includes resource type."""
        result = terraform_prompts.format_resource_for_prompt(sample_ec2_resource)
        assert "ec2:instance" in result

    def test_format_includes_resource_name(self, terraform_prompts: Any, sample_ec2_resource: TrackedResource) -> None:
        """Test formatted output includes resource name."""
        result = terraform_prompts.format_resource_for_prompt(sample_ec2_resource)
        assert "web-server-1" in result or "web_server_1" in result

    def test_format_includes_terraform_name(self, terraform_prompts: Any, sample_ec2_resource: TrackedResource) -> None:
        """Test formatted output includes Terraform name."""
        result = terraform_prompts.format_resource_for_prompt(sample_ec2_resource)
        assert "Terraform name" in result
        assert "web_server_1" in result

    def test_format_includes_region(self, terraform_prompts: Any, sample_ec2_resource: TrackedResource) -> None:
        """Test formatted output includes region."""
        result = terraform_prompts.format_resource_for_prompt(sample_ec2_resource)
        assert "us-east-1" in result

    def test_format_includes_arn(self, terraform_prompts: Any, sample_ec2_resource: TrackedResource) -> None:
        """Test formatted output includes ARN."""
        result = terraform_prompts.format_resource_for_prompt(sample_ec2_resource)
        assert "arn:aws:ec2:us-east-1:123456789012:instance/i-12345678" in result

    def test_format_includes_tags(self, terraform_prompts: Any, sample_ec2_resource: TrackedResource) -> None:
        """Test formatted output includes tags."""
        result = terraform_prompts.format_resource_for_prompt(sample_ec2_resource)
        assert "Tags:" in result
        assert "Environment" in result
        assert "production" in result

    def test_format_includes_properties_section(
        self, terraform_prompts: Any, sample_ec2_resource: TrackedResource
    ) -> None:
        """Test formatted output includes properties section."""
        result = terraform_prompts.format_resource_for_prompt(sample_ec2_resource)
        assert "Properties:" in result

    def test_format_includes_configurable_properties(
        self, terraform_prompts: Any, sample_ec2_resource: TrackedResource
    ) -> None:
        """Test formatted output includes configurable properties."""
        result = terraform_prompts.format_resource_for_prompt(sample_ec2_resource)
        assert "t3.medium" in result
        assert "subnet-abc12345" in result

    def test_format_outputs_json(self, terraform_prompts: Any, sample_ec2_resource: TrackedResource) -> None:
        """Test formatted output includes JSON representation of properties."""
        result = terraform_prompts.format_resource_for_prompt(sample_ec2_resource)
        assert "```json" in result
        assert "```" in result

    def test_lambda_format_includes_runtime(
        self, terraform_prompts: Any, sample_lambda_resource: TrackedResource
    ) -> None:
        """Test Lambda format includes runtime."""
        result = terraform_prompts.format_resource_for_prompt(sample_lambda_resource)
        assert "python3.11" in result

    def test_lambda_format_includes_handler(
        self, terraform_prompts: Any, sample_lambda_resource: TrackedResource
    ) -> None:
        """Test Lambda format includes handler."""
        result = terraform_prompts.format_resource_for_prompt(sample_lambda_resource)
        assert "index.handler" in result

    def test_handles_resource_without_tags(self, terraform_prompts: Any) -> None:
        """Test formatting resource without tags."""
        resource = TrackedResource(
            arn="arn:aws:s3:::my-bucket",
            resource_type="s3:bucket",
            name="my-bucket",
            region="us-east-1",
            tags={},
            raw_config={"BucketName": "my-bucket"},
        )
        result = terraform_prompts.format_resource_for_prompt(resource)
        assert "my-bucket" in result
        assert "Tags:" not in result

    def test_handles_resource_without_arn(self, terraform_prompts: Any) -> None:
        """Test formatting resource without ARN."""
        resource = TrackedResource(
            arn="",
            resource_type="ec2:vpc",
            name="test-vpc",
            region="us-east-1",
            tags={},
            raw_config={"CidrBlock": "10.0.0.0/16"},
        )
        result = terraform_prompts.format_resource_for_prompt(resource)
        assert "test-vpc" in result or "test_vpc" in result
        assert "ARN:" not in result


class TestFilterProperties:
    """Tests for _filter_properties private function."""

    @pytest.fixture
    def terraform_prompts(self) -> Any:
        """Return the terraform prompts module."""
        return terraform_prompts_module

    def test_filters_computed_properties(self, terraform_prompts: Any) -> None:
        """Test that computed properties are filtered out."""
        raw_config = {
            "InstanceType": "t3.medium",
            "State": {"Name": "running"},
            "LaunchTime": "2024-01-01T00:00:00Z",
            "SubnetId": "subnet-123",
        }
        result = terraform_prompts._filter_properties(raw_config, None)
        assert "State" not in result
        assert "LaunchTime" not in result
        assert "InstanceType" in result
        assert "SubnetId" in result

    def test_filters_none_values(self, terraform_prompts: Any) -> None:
        """Test that None values are filtered out."""
        raw_config = {
            "InstanceType": "t3.medium",
            "KeyName": None,
        }
        result = terraform_prompts._filter_properties(raw_config, None)
        assert "KeyName" not in result
        assert "InstanceType" in result

    def test_filters_empty_lists(self, terraform_prompts: Any) -> None:
        """Test that empty lists are filtered out."""
        raw_config = {
            "InstanceType": "t3.medium",
            "SecurityGroups": [],
        }
        result = terraform_prompts._filter_properties(raw_config, None)
        assert "SecurityGroups" not in result
        assert "InstanceType" in result

    def test_filters_empty_dicts(self, terraform_prompts: Any) -> None:
        """Test that empty dicts are filtered out."""
        raw_config = {
            "InstanceType": "t3.medium",
            "Tags": {},
        }
        result = terraform_prompts._filter_properties(raw_config, None)
        assert "Tags" not in result
        assert "InstanceType" in result

    def test_filters_private_keys(self, terraform_prompts: Any) -> None:
        """Test that keys starting with underscore are filtered."""
        raw_config = {
            "InstanceType": "t3.medium",
            "_internal": "value",
        }
        result = terraform_prompts._filter_properties(raw_config, None)
        assert "_internal" not in result
        assert "InstanceType" in result

    def test_keeps_non_empty_lists(self, terraform_prompts: Any) -> None:
        """Test that non-empty lists are kept."""
        raw_config = {
            "SecurityGroups": ["sg-123"],
        }
        result = terraform_prompts._filter_properties(raw_config, None)
        assert "SecurityGroups" in result
        assert result["SecurityGroups"] == ["sg-123"]

    def test_keeps_non_empty_dicts(self, terraform_prompts: Any) -> None:
        """Test that non-empty dicts are kept."""
        raw_config = {
            "VpcConfig": {"SubnetIds": ["subnet-1"]},
        }
        result = terraform_prompts._filter_properties(raw_config, None)
        assert "VpcConfig" in result

    def test_filters_multiple_computed_properties(self, terraform_prompts: Any) -> None:
        """Test filtering of multiple computed properties at once."""
        raw_config = {
            "InstanceId": "i-123",
            "InstanceType": "t3.medium",
            "CreateTime": "2024-01-01",
            "Status": "running",
            "Arn": "arn:aws:...",
            "OwnerId": "123456789012",
        }
        result = terraform_prompts._filter_properties(raw_config, None)
        assert "CreateTime" not in result
        assert "Status" not in result
        assert "Arn" not in result
        assert "OwnerId" not in result
        assert "InstanceType" in result
        assert "InstanceId" in result


class TestRetryPrompt:
    """Tests for format_retry_prompt()."""

    @pytest.fixture
    def terraform_prompts(self) -> Any:
        """Return the terraform prompts module."""
        return terraform_prompts_module

    @pytest.fixture
    def sample_layer(self) -> Layer:
        """Create a sample layer."""
        return Layer(name="NETWORK", order=1, resources=[])

    @pytest.fixture
    def sample_resource_map(self) -> ResourceMap:
        """Create a sample resource map."""
        rmap = ResourceMap()
        rmap.add("vpc-123", "aws_vpc.main", "ec2:vpc")
        return rmap

    def test_retry_prompt_includes_validation_errors(
        self, terraform_prompts: Any, sample_layer: Layer, sample_resource_map: ResourceMap
    ) -> None:
        """Test retry prompt includes validation errors."""
        errors = ["Error: Invalid resource reference", "Error: Missing required argument"]
        prompt = terraform_prompts.format_retry_prompt("resource {} {}", errors, sample_layer, sample_resource_map)
        assert "Validation Errors" in prompt
        assert "Invalid resource reference" in prompt
        assert "Missing required argument" in prompt

    def test_retry_prompt_includes_original_code(
        self, terraform_prompts: Any, sample_layer: Layer, sample_resource_map: ResourceMap
    ) -> None:
        """Test retry prompt includes original code."""
        original_code = 'resource "aws_vpc" "main" {\n  cidr_block = "10.0.0.0/16"\n}'
        prompt = terraform_prompts.format_retry_prompt(original_code, ["Error"], sample_layer, sample_resource_map)
        assert "Original Code" in prompt
        assert original_code in prompt

    def test_retry_prompt_includes_resource_references(
        self, terraform_prompts: Any, sample_layer: Layer, sample_resource_map: ResourceMap
    ) -> None:
        """Test retry prompt includes resource references."""
        prompt = terraform_prompts.format_retry_prompt("code", ["error"], sample_layer, sample_resource_map)
        assert "Available Resource References" in prompt
        assert "vpc-123" in prompt
        assert "aws_vpc.main" in prompt

    def test_retry_prompt_instructs_correction(
        self, terraform_prompts: Any, sample_layer: Layer, sample_resource_map: ResourceMap
    ) -> None:
        """Test retry prompt instructs to generate corrected code."""
        prompt = terraform_prompts.format_retry_prompt("code", ["error"], sample_layer, sample_resource_map)
        assert "corrected" in prompt.lower() or "fix" in prompt.lower()

    def test_retry_prompt_specifies_hcl_output(
        self, terraform_prompts: Any, sample_layer: Layer, sample_resource_map: ResourceMap
    ) -> None:
        """Test retry prompt specifies HCL output."""
        prompt = terraform_prompts.format_retry_prompt("code", ["error"], sample_layer, sample_resource_map)
        assert "HCL" in prompt


class TestFormatResourceMapText:
    """Tests for _format_resource_map_text private function."""

    @pytest.fixture
    def terraform_prompts(self) -> Any:
        """Return the terraform prompts module."""
        return terraform_prompts_module

    def test_formats_single_reference(self, terraform_prompts: Any) -> None:
        """Test formatting single resource reference."""
        rmap = ResourceMap()
        rmap.add("vpc-123", "aws_vpc.main", "ec2:vpc")
        result = terraform_prompts._format_resource_map_text(rmap)
        assert "vpc-123" in result
        assert "aws_vpc.main" in result

    def test_formats_multiple_references(self, terraform_prompts: Any) -> None:
        """Test formatting multiple resource references."""
        rmap = ResourceMap()
        rmap.add("vpc-123", "aws_vpc.main", "ec2:vpc")
        rmap.add("subnet-456", "aws_subnet.public", "ec2:subnet")
        result = terraform_prompts._format_resource_map_text(rmap)
        assert "vpc-123" in result
        assert "subnet-456" in result

    def test_empty_map_returns_no_references_message(self, terraform_prompts: Any) -> None:
        """Test empty map returns appropriate message."""
        rmap = ResourceMap()
        result = terraform_prompts._format_resource_map_text(rmap)
        assert "No resource references" in result or "(No resource" in result
