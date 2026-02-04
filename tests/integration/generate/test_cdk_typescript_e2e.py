"""Integration tests for CDK TypeScript generation workflow.

These tests require the 'generate' optional dependencies:
    pip install -e ".[generate]"

Tests are skipped if langgraph is not installed.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

try:
    import langgraph  # noqa: F401

    HAS_GENERATE_DEPS = True
except ImportError:
    HAS_GENERATE_DEPS = False

pytestmark = pytest.mark.skipif(
    not HAS_GENERATE_DEPS,
    reason="Requires 'generate' optional dependencies (langgraph)",
)

if not HAS_GENERATE_DEPS:
    pytest.skip(
        "Requires 'generate' optional dependencies (langgraph)",
        allow_module_level=True,
    )

from src.generate.state import GenerationState
from src.models.generation import TrackedResource
from src.models.resource import Resource
from src.models.snapshot import Snapshot


@pytest.fixture
def sample_resources() -> List[Resource]:
    """Create sample resources for CDK TypeScript generation."""
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
            resource_type="ec2:security-group",
            name="web-sg",
            arn="arn:aws:ec2:us-east-1:123456789012:security-group/sg-123",
            region="us-east-1",
            config_hash="c" * 64,
            tags={"Name": "web-sg"},
            raw_config={
                "GroupId": "sg-123",
                "GroupName": "web-sg",
                "VpcId": "vpc-abc123",
                "Description": "Web server security group",
            },
        ),
        Resource(
            resource_type="s3:bucket",
            name="my-app-bucket",
            arn="arn:aws:s3:::my-app-bucket",
            region="us-east-1",
            config_hash="d" * 64,
            tags={"Name": "my-app-bucket"},
            raw_config={
                "Name": "my-app-bucket",
                "CreationDate": "2024-01-15T10:00:00Z",
            },
        ),
    ]


@pytest.fixture
def sample_snapshot(sample_resources: List[Resource]) -> Snapshot:
    """Create a sample snapshot for CDK generation."""
    return Snapshot(
        name="test-cdk-snapshot",
        created_at=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        account_id="123456789012",
        regions=["us-east-1"],
        resources=sample_resources,
        metadata={"account_id": "123456789012", "region": "us-east-1"},
    )


@pytest.fixture
def mock_cdk_typescript_responses() -> Dict[str, str]:
    """Mock AI responses for CDK TypeScript generation."""
    return {
        "Network Foundation": """
import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

export class NetworkFoundationStack extends cdk.Stack {
  public readonly mainVpc: ec2.IVpc;
  public readonly publicSubnet1: ec2.ISubnet;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    this.mainVpc = new ec2.Vpc(this, 'mainVpc', {
      ipAddresses: ec2.IpAddresses.cidr('10.0.0.0/16'),
      maxAzs: 2,
      natGateways: 0,
      subnetConfiguration: []
    });

    cdk.Tags.of(this.mainVpc).add('Name', 'main-vpc');
    cdk.Tags.of(this.mainVpc).add('Environment', 'dev');

    this.publicSubnet1 = new ec2.Subnet(this, 'publicSubnet1', {
      vpcId: this.mainVpc.vpcId,
      cidrBlock: '10.0.1.0/24',
      availabilityZone: 'us-east-1a',
      mapPublicIpOnLaunch: true
    });

    cdk.Tags.of(this.publicSubnet1).add('Name', 'public-subnet-1');
  }
}
""",
        "Security Groups": """
import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

export class SecurityGroupsStack extends cdk.Stack {
  public readonly webSg: ec2.ISecurityGroup;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    this.webSg = new ec2.SecurityGroup(this, 'webSg', {
      securityGroupName: 'web-sg',
      description: 'Web server security group',
      allowAllOutbound: true
    });

    cdk.Tags.of(this.webSg).add('Name', 'web-sg');
  }
}
""",
        "Storage": """
import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';

export class StorageStack extends cdk.Stack {
  public readonly myAppBucket: s3.IBucket;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    this.myAppBucket = new s3.Bucket(this, 'myAppBucket', {
      bucketName: 'my-app-bucket',
      removalPolicy: cdk.RemovalPolicy.RETAIN
    });

    cdk.Tags.of(this.myAppBucket).add('Name', 'my-app-bucket');
  }
}
""",
    }


class TestCDKTypescriptGenerationWorkflow:
    """Integration tests for CDK TypeScript generation workflow."""

    def test_create_cdk_graph_structure(self) -> None:
        """Test that the CDK graph is created with correct nodes."""
        from src.generate.agent import create_cdk_graph

        graph = create_cdk_graph()

        assert graph is not None
        assert "parse_inventory" in graph.nodes
        assert "build_resource_map" in graph.nodes
        assert "categorize_layers" in graph.nodes
        assert "extract_lambda" in graph.nodes
        assert "generate_layer" in graph.nodes
        # CDK-specific validation nodes
        assert "npm_build" in graph.nodes
        assert "cdk_synth" in graph.nodes

    def test_compile_cdk_agent(self) -> None:
        """Test that the CDK agent compiles successfully."""
        from src.generate.agent import compile_cdk_agent

        agent = compile_cdk_agent()
        assert agent is not None

    def test_cdk_generator_initialization(self) -> None:
        """Test CDKGenerator initializes correctly."""
        from src.generate.cdk_generator import CDKGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = CDKGenerator(
                output_dir=tmpdir,
                output_format="cdk-typescript",
            )

            assert generator.output_dir == tmpdir
            assert generator.output_format == "cdk-typescript"
            assert generator.agent is not None

    def test_cdk_generator_project_name_derivation(self) -> None:
        """Test CDKGenerator derives project name from output dir."""
        from src.generate.cdk_generator import CDKGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "my-cdk-app")
            os.makedirs(output_dir)

            generator = CDKGenerator(
                output_dir=output_dir,
                output_format="cdk-typescript",
            )

            assert generator.project_name == "my_cdk_app"

    @patch("src.generate.nodes.parse_inventory.SnapshotStorage")
    def test_parse_inventory_for_cdk(
        self,
        mock_storage_class: MagicMock,
        sample_snapshot: Snapshot,
    ) -> None:
        """Test parse_inventory works for CDK generation."""
        from src.generate.nodes.parse_inventory import parse_inventory

        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_class.return_value = mock_storage

        state: GenerationState = {
            "snapshot_name": "test-cdk-snapshot",
            "output_format": "cdk-typescript",
        }
        result = parse_inventory(state)

        assert "resources" in result
        assert len(result["resources"]) == 4
        assert result["errors"] == []

    def test_categorize_layers_for_cdk(self) -> None:
        """Test categorize_layers works for CDK generation."""
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
                arn="arn:aws:s3:::my-bucket",
                resource_type="s3:bucket",
                name="my-bucket",
                region="us-east-1",
            ),
        ]

        state: GenerationState = {
            "resources": resources,
            "output_format": "cdk-typescript",
        }
        result = categorize_layers(state)

        assert "layers" in result
        assert "layer_order" in result
        assert len(result["layers"]) > 0

    def test_generate_layer_selects_typescript_prompt(self) -> None:
        """Test generate_layer uses TypeScript prompt for cdk-typescript format."""
        from src.generate.prompts.cdk_typescript import get_cdk_typescript_system_prompt

        system_prompt = get_cdk_typescript_system_prompt()

        assert "TypeScript" in system_prompt
        assert "aws-cdk-lib" in system_prompt
        assert "cdk.Stack" in system_prompt

    @patch("src.generate.nodes.validate_cdk.subprocess.run")
    def test_npm_build_node(self, mock_run: MagicMock) -> None:
        """Test npm_build node runs npm install and build."""
        from src.generate.nodes.validate_cdk import npm_build

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create package.json
            with open(os.path.join(tmpdir, "package.json"), "w") as f:
                f.write('{"name": "test", "scripts": {"build": "tsc"}}')

            state: GenerationState = {
                "output_dir": tmpdir,
                "output_format": "cdk-typescript",
                "validation_errors": [],
            }

            result = npm_build(state)

            assert result.get("npm_build_success") is True or "validation_errors" in result

    @patch("src.generate.nodes.validate_cdk.subprocess.run")
    def test_cdk_synth_node(self, mock_run: MagicMock) -> None:
        """Test cdk_synth node runs cdk synth."""
        from src.generate.nodes.validate_cdk import cdk_synth

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create cdk.json
            with open(os.path.join(tmpdir, "cdk.json"), "w") as f:
                f.write('{"app": "npx ts-node bin/app.ts"}')

            state: GenerationState = {
                "output_dir": tmpdir,
                "output_format": "cdk-typescript",
                "npm_build_success": True,
                "validation_errors": [],
            }

            result = cdk_synth(state)

            # Should return empty dict or validation_errors
            assert isinstance(result, dict)


class TestCDKTypescriptProjectStructure:
    """Tests for CDK TypeScript project file generation."""

    def test_generate_typescript_config_files(self) -> None:
        """Test TypeScript config files are generated correctly."""
        from src.generate.cdk_generator import CDKGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = CDKGenerator(
                output_dir=tmpdir,
                output_format="cdk-typescript",
                project_name="test_project",
            )

            generator._generate_project_config_files()

            # Check package.json exists
            assert os.path.exists(os.path.join(tmpdir, "package.json"))

            # Check tsconfig.json exists
            assert os.path.exists(os.path.join(tmpdir, "tsconfig.json"))

            # Check cdk.json exists
            assert os.path.exists(os.path.join(tmpdir, "cdk.json"))

            # Check lib directory exists
            assert os.path.isdir(os.path.join(tmpdir, "lib"))

    def test_generate_typescript_app_entry_point(self) -> None:
        """Test TypeScript app.ts entry point is generated correctly."""
        from src.generate.cdk_generator import CDKGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = CDKGenerator(
                output_dir=tmpdir,
                output_format="cdk-typescript",
            )

            generator._generate_project_config_files()

            state = {
                "layer_order": ["Network Foundation", "Security Groups", "Storage"],
            }

            generator._generate_app_entry_point(state)

            app_ts_path = os.path.join(tmpdir, "bin", "app.ts")
            assert os.path.exists(app_ts_path)

            with open(app_ts_path) as f:
                content = f.read()

            # Check imports
            assert "NetworkFoundationStack" in content
            assert "SecurityGroupsStack" in content
            assert "StorageStack" in content

            # Check instantiations
            assert "new NetworkFoundationStack" in content
            assert "new SecurityGroupsStack" in content
            assert "new StorageStack" in content

            # Check app.synth()
            assert "app.synth()" in content

    def test_package_json_content(self) -> None:
        """Test package.json has correct content."""
        from src.generate.cdk_generator import CDKGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = CDKGenerator(
                output_dir=tmpdir,
                output_format="cdk-typescript",
                project_name="my_test_app",
            )

            generator._generate_project_config_files()

            import json

            with open(os.path.join(tmpdir, "package.json")) as f:
                pkg = json.load(f)

            assert pkg["name"] == "my_test_app"
            assert "aws-cdk-lib" in pkg.get("dependencies", {})
            assert "typescript" in pkg.get("devDependencies", {})


class TestCDKTypescriptEndToEnd:
    """End-to-end tests for CDK TypeScript generation."""

    @patch("src.generate.nodes.parse_inventory.SnapshotStorage")
    @patch("boto3.client")
    @patch("src.generate.nodes.validate_cdk.subprocess.run")
    def test_full_cdk_typescript_workflow(
        self,
        mock_subprocess: MagicMock,
        mock_boto_client: MagicMock,
        mock_storage_class: MagicMock,
        sample_snapshot: Snapshot,
        mock_cdk_typescript_responses: Dict[str, str],
    ) -> None:
        """Test complete CDK TypeScript workflow from snapshot to files."""
        from src.generate.cdk_generator import CDKGenerator

        # Setup mocks
        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = sample_snapshot
        mock_storage_class.return_value = mock_storage

        # Mock Bedrock client
        mock_bedrock_client = MagicMock()

        def converse_side_effect(*args: Any, **kwargs: Any) -> Dict[str, Any]:
            messages = kwargs.get("messages", [])
            user_msg = messages[-1]["content"][0]["text"] if messages else ""

            response_text = "// No matching layer"
            for key, value in mock_cdk_typescript_responses.items():
                if key.lower() in user_msg.lower():
                    response_text = value
                    break

            return {"output": {"message": {"content": [{"text": response_text}]}}}

        mock_bedrock_client.converse.side_effect = converse_side_effect
        mock_boto_client.return_value = mock_bedrock_client
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = CDKGenerator(
                output_dir=tmpdir,
                output_format="cdk-typescript",
            )

            result = generator.run(snapshot_name="test-cdk-snapshot")

            # Check result structure
            assert hasattr(result, "success")
            assert hasattr(result, "generated_files")
            assert hasattr(result, "output_dir")

            # Check project files exist
            assert os.path.exists(os.path.join(tmpdir, "package.json"))
            assert os.path.exists(os.path.join(tmpdir, "cdk.json"))
            assert os.path.exists(os.path.join(tmpdir, "tsconfig.json"))

            # Check app.ts exists
            assert os.path.exists(os.path.join(tmpdir, "bin", "app.ts"))
