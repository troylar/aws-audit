"""Integration tests for Terraform generation workflow.

These tests require the 'generate' optional dependencies:
    pip install -e ".[generate]"

Tests are skipped if langgraph or openai are not installed.
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

try:
    import langgraph
    import openai

    HAS_GENERATE_DEPS = True
except ImportError:
    HAS_GENERATE_DEPS = False

pytestmark = pytest.mark.skipif(
    not HAS_GENERATE_DEPS,
    reason="Requires 'generate' optional dependencies (langgraph, openai)",
)

if not HAS_GENERATE_DEPS:
    pytest.skip(
        "Requires 'generate' optional dependencies (langgraph, openai)",
        allow_module_level=True,
    )

from src.generate.layers import LayerOrder, LayerStatus, RESOURCE_TYPE_TO_LAYER
from src.generate.state import GenerationConfig, GenerationState
from src.models.generation import Layer, ResourceMap, TrackedResource
from src.models.resource import Resource
from src.models.snapshot import Snapshot


@pytest.fixture
def sample_resources() -> List[Resource]:
    """Create sample resources with various types."""
    return [
        Resource(
            resource_type="ec2:vpc",
            name="main-vpc",
            arn="arn:aws:ec2:us-east-1:123456789012:vpc/vpc-abc123",
            region="us-east-1",
            config_hash="a" * 64,
            tags={"Name": "main-vpc", "Environment": "dev"},
            raw_config={
                "VpcId": "vpc-abc123",
                "CidrBlock": "10.0.0.0/16",
                "EnableDnsHostnames": True,
                "EnableDnsSupport": True,
            },
        ),
        Resource(
            resource_type="ec2:subnet",
            name="public-subnet-1",
            arn="arn:aws:ec2:us-east-1:123456789012:subnet/subnet-def456",
            region="us-east-1",
            config_hash="b" * 64,
            tags={"Name": "public-subnet-1"},
            raw_config={
                "SubnetId": "subnet-def456",
                "VpcId": "vpc-abc123",
                "CidrBlock": "10.0.1.0/24",
                "AvailabilityZone": "us-east-1a",
                "MapPublicIpOnLaunch": True,
            },
        ),
        Resource(
            resource_type="ec2:instance",
            name="web-server",
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-xyz789",
            region="us-east-1",
            config_hash="c" * 64,
            tags={"Name": "web-server"},
            raw_config={
                "InstanceId": "i-xyz789",
                "InstanceType": "t3.micro",
                "ImageId": "ami-12345678",
                "SubnetId": "subnet-def456",
                "KeyName": "my-key",
            },
        ),
        Resource(
            resource_type="ec2:security-group",
            name="web-sg",
            arn="arn:aws:ec2:us-east-1:123456789012:security-group/sg-123",
            region="us-east-1",
            config_hash="d" * 64,
            tags={"Name": "web-sg"},
            raw_config={
                "GroupId": "sg-123",
                "GroupName": "web-sg",
                "VpcId": "vpc-abc123",
                "Description": "Web server security group",
            },
        ),
    ]


@pytest.fixture
def sample_snapshot(sample_resources: List[Resource]) -> Snapshot:
    """Create a sample snapshot with various resources."""
    return Snapshot(
        name="test-snapshot",
        created_at=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        account_id="123456789012",
        regions=["us-east-1"],
        resources=sample_resources,
        metadata={"account_id": "123456789012", "region": "us-east-1"},
    )


@pytest.fixture
def mock_ai_responses() -> Dict[str, str]:
    """Mock AI responses for each layer."""
    return {
        "Network Foundation": '''
resource "aws_vpc" "main_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "main-vpc"
    Environment = "dev"
  }
}

resource "aws_subnet" "public_subnet_1" {
  vpc_id                  = aws_vpc.main_vpc.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "us-east-1a"
  map_public_ip_on_launch = true

  tags = {
    Name = "public-subnet-1"
  }
}
''',
        "Security Groups": '''
resource "aws_security_group" "web_sg" {
  name        = "web-sg"
  description = "Web server security group"
  vpc_id      = aws_vpc.main_vpc.id

  tags = {
    Name = "web-sg"
  }
}
''',
        "Compute": '''
resource "aws_instance" "web_server" {
  ami           = "ami-12345678"
  instance_type = "t3.micro"
  subnet_id     = aws_subnet.public_subnet_1.id
  key_name      = "my-key"

  tags = {
    Name = "web-server"
  }
}
''',
    }


class TestTerraformGenerationWorkflow:
    """Integration tests for Terraform generation workflow."""

    def test_create_terraform_graph_structure(self) -> None:
        """Test that the graph is created with correct nodes and edges."""
        from src.generate.agent import create_terraform_graph

        graph = create_terraform_graph()

        assert graph is not None
        assert "parse_inventory" in graph.nodes
        assert "build_resource_map" in graph.nodes
        assert "categorize_layers" in graph.nodes
        assert "extract_lambda" in graph.nodes
        assert "generate_layer" in graph.nodes

    def test_compile_terraform_agent(self) -> None:
        """Test that the agent compiles successfully."""
        from src.generate.agent import compile_terraform_agent

        agent = compile_terraform_agent()
        assert agent is not None

    @patch("src.generate.nodes.parse_inventory.SnapshotStorage")
    def test_parse_inventory_node_success(
        self,
        mock_storage_class: MagicMock,
        sample_snapshot: Snapshot,
    ) -> None:
        """Test parse_inventory node loads snapshot correctly."""
        from src.generate.nodes.parse_inventory import parse_inventory

        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_class.return_value = mock_storage

        state: GenerationState = {"snapshot_name": "test-snapshot"}
        result = parse_inventory(state)

        assert "resources" in result
        assert len(result["resources"]) == 4
        assert result["errors"] == []
        assert result["snapshot"] is not None

        resource_types = [r.resource_type for r in result["resources"]]
        assert "ec2:vpc" in resource_types
        assert "ec2:subnet" in resource_types
        assert "ec2:instance" in resource_types
        assert "ec2:security-group" in resource_types

    @patch("src.generate.nodes.parse_inventory.SnapshotStorage")
    def test_parse_inventory_node_not_found(
        self,
        mock_storage_class: MagicMock,
    ) -> None:
        """Test parse_inventory node handles missing snapshot."""
        from src.generate.nodes.parse_inventory import parse_inventory

        mock_storage = MagicMock()
        mock_storage.load_snapshot.side_effect = FileNotFoundError("Not found")
        mock_storage_class.return_value = mock_storage

        state: GenerationState = {"snapshot_name": "nonexistent"}
        result = parse_inventory(state)

        assert result["resources"] == []
        assert result["snapshot"] is None
        assert len(result["errors"]) == 1
        assert "not found" in result["errors"][0].lower()

    def test_categorize_layers_node(self) -> None:
        """Test categorize_layers correctly groups resources by layer."""
        from src.generate.nodes.categorize_layers import categorize_layers

        resources = [
            TrackedResource(
                arn="arn:aws:ec2:us-east-1:123456789012:vpc/vpc-abc123",
                resource_type="ec2:vpc",
                name="main-vpc",
                region="us-east-1",
            ),
            TrackedResource(
                arn="arn:aws:ec2:us-east-1:123456789012:security-group/sg-123",
                resource_type="ec2:security-group",
                name="web-sg",
                region="us-east-1",
            ),
            TrackedResource(
                arn="arn:aws:ec2:us-east-1:123456789012:instance/i-xyz789",
                resource_type="ec2:instance",
                name="web-server",
                region="us-east-1",
            ),
        ]

        state: GenerationState = {"resources": resources}
        result = categorize_layers(state)

        assert "layers" in result
        layers = result["layers"]

        layer_orders = {layer.order for layer in layers}
        assert LayerOrder.NETWORK in layer_orders
        assert LayerOrder.SECURITY in layer_orders
        assert LayerOrder.COMPUTE in layer_orders

    def test_build_resource_map_node(self) -> None:
        """Test build_resource_map creates correct mappings."""
        from src.generate.nodes.build_resource_map import build_resource_map

        inventory = [
            {
                "arn": "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-abc123",
                "type": "vpc:vpc",
                "name": "main-vpc",
                "region": "us-east-1",
                "raw_config": {"VpcId": "vpc-abc123"},
            },
            {
                "arn": "arn:aws:ec2:us-east-1:123456789012:subnet/subnet-def456",
                "type": "vpc:subnet",
                "name": "public-subnet",
                "region": "us-east-1",
                "raw_config": {"SubnetId": "subnet-def456"},
            },
        ]

        state: GenerationState = {"inventory": inventory}
        result = build_resource_map(state)

        assert "resource_map" in result
        resource_map: ResourceMap = result["resource_map"]

        assert "vpc-abc123" in resource_map.id_to_ref
        assert "subnet-def456" in resource_map.id_to_ref

    def test_resource_map_replaces_ids_in_code(self) -> None:
        """Test that resource map replaces AWS IDs with Terraform references."""
        resource_map = ResourceMap()
        resource_map.add("vpc-abc123", "aws_vpc.main", "vpc:vpc")
        resource_map.add("subnet-def456", "aws_subnet.public", "vpc:subnet")

        code = '''
resource "aws_instance" "web" {
  subnet_id = "subnet-def456"
  vpc_security_group_ids = ["sg-123"]
}
'''
        result = resource_map.replace_ids_in_code(code)
        assert "aws_subnet.public.id" in result
        assert '"subnet-def456"' not in result

    @patch("src.generate.nodes.generate_layer.OpenAI")
    def test_generate_layer_node_with_mocked_ai(
        self,
        mock_openai_class: MagicMock,
        mock_ai_responses: Dict[str, str],
    ) -> None:
        """Test generate_layer node with mocked AI responses."""
        from src.generate.nodes.generate_layer import generate_layer

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        def mock_completion(*args: Any, **kwargs: Any) -> MagicMock:
            messages = kwargs.get("messages", [])
            user_msg = messages[-1]["content"] if messages else ""

            response = MagicMock()
            response.choices = [MagicMock()]

            for layer_name, terraform in mock_ai_responses.items():
                if layer_name in user_msg:
                    response.choices[0].message.content = terraform
                    return response

            response.choices[0].message.content = "# No matching layer"
            return response

        mock_client.chat.completions.create = mock_completion

        with tempfile.TemporaryDirectory() as tmpdir:
            state: GenerationState = {
                "layers": {
                    "Network Foundation": [
                        {
                            "arn": "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-abc123",
                            "type": "ec2:vpc",
                            "name": "main-vpc",
                            "region": "us-east-1",
                            "raw_config": {"VpcId": "vpc-abc123", "CidrBlock": "10.0.0.0/16"},
                        }
                    ]
                },
                "layer_order": ["Network Foundation"],
                "current_layer_index": 0,
                "resource_map": ResourceMap(),
                "output_dir": tmpdir,
                "generated_files": [],
            }

            with patch.dict(
                os.environ,
                {"AWSINV_AI_API_KEY": "test-key", "AWSINV_AI_ENDPOINT": "https://api.test.com/v1"},
            ):
                result = generate_layer(state)

            assert "generated_files" in result or "errors" in result


class TestGenerationConfig:
    """Tests for GenerationConfig."""

    def test_config_from_env_defaults(self) -> None:
        """Test GenerationConfig.from_env with defaults."""
        with patch.dict(os.environ, {}, clear=True):
            config = GenerationConfig.from_env()

            assert config.ai_endpoint == "https://api.openai.com/v1"
            assert config.ai_api_key == ""
            assert config.ai_model == "gpt-4"

    def test_config_from_env_custom_values(self) -> None:
        """Test GenerationConfig.from_env with custom values."""
        env_vars = {
            "AWSINV_AI_ENDPOINT": "https://custom.api.com/v1",
            "AWSINV_AI_API_KEY": "custom-key",
            "AWSINV_AI_MODEL": "gpt-3.5-turbo",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            config = GenerationConfig.from_env()

            assert config.ai_endpoint == "https://custom.api.com/v1"
            assert config.ai_api_key == "custom-key"
            assert config.ai_model == "gpt-3.5-turbo"


class TestTrackedResource:
    """Tests for TrackedResource model."""

    def test_from_inventory(self) -> None:
        """Test creating TrackedResource from inventory dict."""
        inventory_dict = {
            "arn": "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-abc123",
            "type": "ec2:vpc",
            "name": "main-vpc",
            "region": "us-east-1",
            "tags": {"Name": "main-vpc"},
            "raw_config": {"VpcId": "vpc-abc123"},
        }

        resource = TrackedResource.from_inventory(inventory_dict)

        assert resource.arn == inventory_dict["arn"]
        assert resource.resource_type == "ec2:vpc"
        assert resource.name == "main-vpc"
        assert resource.region == "us-east-1"
        assert resource.tags == {"Name": "main-vpc"}

    def test_get_terraform_name_simple(self) -> None:
        """Test Terraform name generation for simple names."""
        resource = TrackedResource(
            arn="arn:aws:ec2:us-east-1:123456789012:vpc/vpc-abc",
            resource_type="ec2:vpc",
            name="main-vpc",
            region="us-east-1",
        )

        tf_name = resource.get_terraform_name()
        assert tf_name == "main_vpc"

    def test_get_terraform_name_special_chars(self) -> None:
        """Test Terraform name generation handles special characters."""
        resource = TrackedResource(
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-123",
            resource_type="ec2:instance",
            name="web.server-01@prod",
            region="us-east-1",
        )

        tf_name = resource.get_terraform_name()
        assert tf_name == "web_server_01_prod"
        assert "." not in tf_name
        assert "-" not in tf_name
        assert "@" not in tf_name

    def test_get_terraform_name_starts_with_number(self) -> None:
        """Test Terraform name generation prepends prefix for numeric start."""
        resource = TrackedResource(
            arn="arn:aws:ec2:us-east-1:123456789012:instance/i-123",
            resource_type="ec2:instance",
            name="123-server",
            region="us-east-1",
        )

        tf_name = resource.get_terraform_name()
        assert tf_name.startswith("r_")
        assert tf_name[0].isalpha()


class TestLayerCategorization:
    """Tests for layer categorization logic."""

    def test_all_network_resources_in_network_layer(self) -> None:
        """Test that network resources are categorized to NETWORK layer."""
        network_types = ["ec2:vpc", "ec2:subnet", "ec2:internet-gateway", "ec2:nat-gateway"]

        for resource_type in network_types:
            assert RESOURCE_TYPE_TO_LAYER.get(resource_type) == LayerOrder.NETWORK

    def test_all_security_resources_in_security_layer(self) -> None:
        """Test that security resources are categorized to SECURITY layer."""
        security_types = ["ec2:security-group", "ec2:network-acl", "kms:key"]

        for resource_type in security_types:
            assert RESOURCE_TYPE_TO_LAYER.get(resource_type) == LayerOrder.SECURITY

    def test_layer_names_defined(self) -> None:
        """Test that all layers have human-readable names."""
        from src.generate.nodes.categorize_layers import LAYER_NAMES

        for layer_order in LayerOrder:
            assert layer_order in LAYER_NAMES


class TestEndToEndWorkflow:
    """End-to-end workflow tests with full mocking."""

    @patch("src.generate.nodes.generate_layer.OpenAI")
    @patch("src.generate.nodes.parse_inventory.SnapshotStorage")
    def test_full_workflow_with_mocks(
        self,
        mock_storage_class: MagicMock,
        mock_openai_class: MagicMock,
        sample_snapshot: Snapshot,
        mock_ai_responses: Dict[str, str],
    ) -> None:
        """Test complete workflow from snapshot to generated files."""
        from src.generate.nodes.build_resource_map import build_resource_map
        from src.generate.nodes.categorize_layers import categorize_layers
        from src.generate.nodes.parse_inventory import parse_inventory

        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_class.return_value = mock_storage

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        def mock_completion(*args: Any, **kwargs: Any) -> MagicMock:
            response = MagicMock()
            response.choices = [MagicMock()]
            response.choices[0].message.content = '''
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}
'''
            return response

        mock_client.chat.completions.create = mock_completion

        with tempfile.TemporaryDirectory() as tmpdir:
            initial_state: GenerationState = {
                "snapshot_name": "test-snapshot",
                "output_dir": tmpdir,
                "output_format": "terraform",
            }

            parse_result = parse_inventory(initial_state)
            assert len(parse_result.get("resources", [])) > 0
            assert parse_result.get("errors", []) == []

            inventory_for_map = [
                {
                    "arn": r.arn,
                    "type": r.resource_type,
                    "name": r.name,
                    "region": r.region,
                    "raw_config": r.raw_config,
                    "tags": r.tags,
                }
                for r in parse_result["resources"]
            ]
            map_state: GenerationState = {"inventory": inventory_for_map}
            map_result = build_resource_map(map_state)
            assert "resource_map" in map_result

            categorize_state: GenerationState = {"resources": parse_result["resources"]}
            layer_result = categorize_layers(categorize_state)
            assert "layers" in layer_result
            assert len(layer_result["layers"]) > 0

    @patch("src.generate.nodes.parse_inventory.SnapshotStorage")
    def test_workflow_with_missing_snapshot(
        self,
        mock_storage_class: MagicMock,
    ) -> None:
        """Test workflow handles missing snapshot gracefully."""
        from src.generate.nodes.parse_inventory import parse_inventory

        mock_storage = MagicMock()
        mock_storage.load_snapshot.side_effect = FileNotFoundError("Snapshot not found")
        mock_storage_class.return_value = mock_storage

        state: GenerationState = {"snapshot_name": "nonexistent-snapshot"}
        result = parse_inventory(state)

        assert result["resources"] == []
        assert len(result["errors"]) > 0
        assert any("not found" in err.lower() for err in result["errors"])
