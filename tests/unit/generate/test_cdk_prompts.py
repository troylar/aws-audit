"""Unit tests for CDK prompt templates (T011)."""

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
    """Setup mocks for problematic imports before loading CDK prompts."""
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


class TestCDKTypeScriptSystemPrompt:
    """Tests for CDK TypeScript system prompt."""

    @pytest.fixture
    def cdk_typescript_prompts(self) -> Any:
        """Return the CDK TypeScript prompts module."""
        from src.generate.prompts import cdk_typescript

        return cdk_typescript

    def test_get_system_prompt_returns_string(self, cdk_typescript_prompts: Any) -> None:
        """Test that get_cdk_typescript_system_prompt returns a string."""
        result = cdk_typescript_prompts.get_cdk_typescript_system_prompt()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_system_prompt_matches_constant(self, cdk_typescript_prompts: Any) -> None:
        """Test that function returns the same value as the constant."""
        assert (
            cdk_typescript_prompts.get_cdk_typescript_system_prompt()
            == cdk_typescript_prompts.CDK_TYPESCRIPT_SYSTEM_PROMPT
        )

    def test_prompt_mentions_cdk(self, cdk_typescript_prompts: Any) -> None:
        """Test prompt mentions CDK."""
        prompt = cdk_typescript_prompts.get_cdk_typescript_system_prompt()
        assert "CDK" in prompt

    def test_prompt_mentions_typescript(self, cdk_typescript_prompts: Any) -> None:
        """Test prompt mentions TypeScript."""
        prompt = cdk_typescript_prompts.get_cdk_typescript_system_prompt()
        assert "TypeScript" in prompt

    def test_prompt_mentions_l2_constructs(self, cdk_typescript_prompts: Any) -> None:
        """Test prompt mentions L2 constructs preference."""
        prompt = cdk_typescript_prompts.get_cdk_typescript_system_prompt()
        assert "L2" in prompt or "high-level" in prompt.lower()

    def test_prompt_mentions_stack(self, cdk_typescript_prompts: Any) -> None:
        """Test prompt mentions Stack."""
        prompt = cdk_typescript_prompts.get_cdk_typescript_system_prompt()
        assert "Stack" in prompt

    def test_prompt_mentions_constructs(self, cdk_typescript_prompts: Any) -> None:
        """Test prompt mentions constructs."""
        prompt = cdk_typescript_prompts.get_cdk_typescript_system_prompt()
        assert "construct" in prompt.lower()

    def test_prompt_mentions_props(self, cdk_typescript_prompts: Any) -> None:
        """Test prompt mentions props pattern."""
        prompt = cdk_typescript_prompts.get_cdk_typescript_system_prompt()
        assert "props" in prompt.lower() or "Props" in prompt

    def test_prompt_mentions_cross_stack_references(self, cdk_typescript_prompts: Any) -> None:
        """Test prompt mentions cross-stack references."""
        prompt = cdk_typescript_prompts.get_cdk_typescript_system_prompt()
        assert "cross-stack" in prompt.lower() or "cross stack" in prompt.lower()

    def test_prompt_specifies_output_format(self, cdk_typescript_prompts: Any) -> None:
        """Test prompt specifies TypeScript output format."""
        prompt = cdk_typescript_prompts.get_cdk_typescript_system_prompt()
        assert "TypeScript" in prompt

    def test_prompt_instructs_no_markdown(self, cdk_typescript_prompts: Any) -> None:
        """Test prompt instructs not to include markdown."""
        prompt = cdk_typescript_prompts.get_cdk_typescript_system_prompt()
        assert "no markdown" in prompt.lower() or "only valid" in prompt.lower()


class TestCDKPythonSystemPrompt:
    """Tests for CDK Python system prompt."""

    @pytest.fixture
    def cdk_python_prompts(self) -> Any:
        """Return the CDK Python prompts module."""
        from src.generate.prompts import cdk_python

        return cdk_python

    def test_get_system_prompt_returns_string(self, cdk_python_prompts: Any) -> None:
        """Test that get_cdk_python_system_prompt returns a string."""
        result = cdk_python_prompts.get_cdk_python_system_prompt()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_system_prompt_matches_constant(self, cdk_python_prompts: Any) -> None:
        """Test that function returns the same value as the constant."""
        assert cdk_python_prompts.get_cdk_python_system_prompt() == cdk_python_prompts.CDK_PYTHON_SYSTEM_PROMPT

    def test_prompt_mentions_cdk(self, cdk_python_prompts: Any) -> None:
        """Test prompt mentions CDK."""
        prompt = cdk_python_prompts.get_cdk_python_system_prompt()
        assert "CDK" in prompt

    def test_prompt_mentions_python(self, cdk_python_prompts: Any) -> None:
        """Test prompt mentions Python."""
        prompt = cdk_python_prompts.get_cdk_python_system_prompt()
        assert "Python" in prompt

    def test_prompt_mentions_l2_constructs(self, cdk_python_prompts: Any) -> None:
        """Test prompt mentions L2 constructs preference."""
        prompt = cdk_python_prompts.get_cdk_python_system_prompt()
        assert "L2" in prompt or "high-level" in prompt.lower()

    def test_prompt_mentions_stack(self, cdk_python_prompts: Any) -> None:
        """Test prompt mentions Stack."""
        prompt = cdk_python_prompts.get_cdk_python_system_prompt()
        assert "Stack" in prompt

    def test_prompt_mentions_snake_case(self, cdk_python_prompts: Any) -> None:
        """Test prompt mentions snake_case naming convention."""
        prompt = cdk_python_prompts.get_cdk_python_system_prompt()
        assert "snake_case" in prompt or "snake case" in prompt.lower()

    def test_prompt_mentions_cross_stack_references(self, cdk_python_prompts: Any) -> None:
        """Test prompt mentions cross-stack references."""
        prompt = cdk_python_prompts.get_cdk_python_system_prompt()
        assert "cross-stack" in prompt.lower() or "cross stack" in prompt.lower()

    def test_prompt_specifies_output_format(self, cdk_python_prompts: Any) -> None:
        """Test prompt specifies Python output format."""
        prompt = cdk_python_prompts.get_cdk_python_system_prompt()
        assert "Python" in prompt

    def test_prompt_instructs_no_markdown(self, cdk_python_prompts: Any) -> None:
        """Test prompt instructs not to include markdown."""
        prompt = cdk_python_prompts.get_cdk_python_system_prompt()
        assert "no markdown" in prompt.lower() or "only valid" in prompt.lower()


class TestCDKTypeScriptLayerPrompt:
    """Tests for CDK TypeScript format_layer_prompt_typescript()."""

    @pytest.fixture
    def cdk_typescript_prompts(self) -> Any:
        """Return the CDK TypeScript prompts module."""
        from src.generate.prompts import cdk_typescript

        return cdk_typescript

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
            ],
        )

    @pytest.fixture
    def sample_resource_map(self) -> ResourceMap:
        """Create a sample resource map."""
        rmap = ResourceMap()
        rmap.add("vpc-existing123", "networkStack.vpc", "ec2:vpc")
        return rmap

    @pytest.fixture
    def empty_resource_map(self) -> ResourceMap:
        """Create an empty resource map."""
        return ResourceMap()

    def test_prompt_includes_layer_name(
        self, cdk_typescript_prompts: Any, sample_layer: Layer, empty_resource_map: ResourceMap
    ) -> None:
        """Test prompt includes the layer name."""
        prompt = cdk_typescript_prompts.format_layer_prompt_typescript(sample_layer, empty_resource_map)
        assert "NETWORK" in prompt

    def test_prompt_includes_resource_count(
        self, cdk_typescript_prompts: Any, sample_layer: Layer, empty_resource_map: ResourceMap
    ) -> None:
        """Test prompt includes total resource count."""
        prompt = cdk_typescript_prompts.format_layer_prompt_typescript(sample_layer, empty_resource_map)
        assert "1 resource" in prompt or "1 construct" in prompt

    def test_prompt_mentions_stack_class(
        self, cdk_typescript_prompts: Any, sample_layer: Layer, empty_resource_map: ResourceMap
    ) -> None:
        """Test prompt mentions generating a Stack class."""
        prompt = cdk_typescript_prompts.format_layer_prompt_typescript(sample_layer, empty_resource_map)
        assert "Stack" in prompt

    def test_prompt_includes_resource_references(
        self, cdk_typescript_prompts: Any, sample_layer: Layer, sample_resource_map: ResourceMap
    ) -> None:
        """Test prompt includes existing resource references."""
        prompt = cdk_typescript_prompts.format_layer_prompt_typescript(sample_layer, sample_resource_map)
        assert "networkStack.vpc" in prompt or "vpc-existing123" in prompt


class TestCDKPythonLayerPrompt:
    """Tests for CDK Python format_layer_prompt_python()."""

    @pytest.fixture
    def cdk_python_prompts(self) -> Any:
        """Return the CDK Python prompts module."""
        from src.generate.prompts import cdk_python

        return cdk_python

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
            ],
        )

    @pytest.fixture
    def sample_resource_map(self) -> ResourceMap:
        """Create a sample resource map."""
        rmap = ResourceMap()
        rmap.add("vpc-existing123", "network_stack.vpc", "ec2:vpc")
        return rmap

    @pytest.fixture
    def empty_resource_map(self) -> ResourceMap:
        """Create an empty resource map."""
        return ResourceMap()

    def test_prompt_includes_layer_name(
        self, cdk_python_prompts: Any, sample_layer: Layer, empty_resource_map: ResourceMap
    ) -> None:
        """Test prompt includes the layer name."""
        prompt = cdk_python_prompts.format_layer_prompt_python(sample_layer, empty_resource_map)
        assert "NETWORK" in prompt

    def test_prompt_includes_resource_count(
        self, cdk_python_prompts: Any, sample_layer: Layer, empty_resource_map: ResourceMap
    ) -> None:
        """Test prompt includes total resource count."""
        prompt = cdk_python_prompts.format_layer_prompt_python(sample_layer, empty_resource_map)
        assert "1 resource" in prompt or "1 construct" in prompt

    def test_prompt_mentions_stack_class(
        self, cdk_python_prompts: Any, sample_layer: Layer, empty_resource_map: ResourceMap
    ) -> None:
        """Test prompt mentions generating a Stack class."""
        prompt = cdk_python_prompts.format_layer_prompt_python(sample_layer, empty_resource_map)
        assert "Stack" in prompt

    def test_prompt_includes_resource_references(
        self, cdk_python_prompts: Any, sample_layer: Layer, sample_resource_map: ResourceMap
    ) -> None:
        """Test prompt includes existing resource references."""
        prompt = cdk_python_prompts.format_layer_prompt_python(sample_layer, sample_resource_map)
        assert "network_stack.vpc" in prompt or "vpc-existing123" in prompt


class TestCDKResourceFormatting:
    """Tests for CDK resource formatting functions."""

    @pytest.fixture
    def cdk_typescript_prompts(self) -> Any:
        """Return the CDK TypeScript prompts module."""
        from src.generate.prompts import cdk_typescript

        return cdk_typescript

    @pytest.fixture
    def sample_ec2_resource(self) -> TrackedResource:
        """Create a sample EC2 instance resource."""
        return TrackedResource(
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-12345678",
            resource_type="ec2:instance",
            name="web-server-1",
            region="us-east-1",
            tags={"Environment": "production"},
            raw_config={
                "InstanceId": "i-12345678",
                "InstanceType": "t3.medium",
                "SubnetId": "subnet-abc12345",
            },
        )

    def test_format_includes_resource_type(self, cdk_typescript_prompts: Any, sample_ec2_resource: TrackedResource) -> None:
        """Test formatted output includes resource type."""
        result = cdk_typescript_prompts.format_resource_for_cdk_prompt(sample_ec2_resource)
        assert "ec2:instance" in result

    def test_format_includes_resource_name(self, cdk_typescript_prompts: Any, sample_ec2_resource: TrackedResource) -> None:
        """Test formatted output includes resource name."""
        result = cdk_typescript_prompts.format_resource_for_cdk_prompt(sample_ec2_resource)
        assert "web-server-1" in result or "web_server_1" in result or "webServer1" in result

    def test_format_includes_cdk_construct_name(self, cdk_typescript_prompts: Any, sample_ec2_resource: TrackedResource) -> None:
        """Test formatted output includes CDK construct name."""
        result = cdk_typescript_prompts.format_resource_for_cdk_prompt(sample_ec2_resource)
        assert "CDK construct" in result or "Construct" in result or "construct" in result

    def test_format_includes_region(self, cdk_typescript_prompts: Any, sample_ec2_resource: TrackedResource) -> None:
        """Test formatted output includes region."""
        result = cdk_typescript_prompts.format_resource_for_cdk_prompt(sample_ec2_resource)
        assert "us-east-1" in result

    def test_format_includes_properties(self, cdk_typescript_prompts: Any, sample_ec2_resource: TrackedResource) -> None:
        """Test formatted output includes properties."""
        result = cdk_typescript_prompts.format_resource_for_cdk_prompt(sample_ec2_resource)
        assert "t3.medium" in result
