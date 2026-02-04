"""Integration tests for CDK Python generation workflow.

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
    """Create sample resources for CDK Python generation."""
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
            resource_type="lambda:function",
            name="my-function",
            arn="arn:aws:lambda:us-east-1:123456789012:function:my-function",
            region="us-east-1",
            config_hash="c" * 64,
            tags={"Name": "my-function"},
            raw_config={
                "FunctionName": "my-function",
                "Runtime": "python3.11",
                "Handler": "index.handler",
                "MemorySize": 128,
                "Timeout": 30,
            },
        ),
    ]


@pytest.fixture
def sample_snapshot(sample_resources: List[Resource]) -> Snapshot:
    """Create a sample snapshot for CDK Python generation."""
    return Snapshot(
        name="test-cdk-python-snapshot",
        created_at=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
        account_id="123456789012",
        regions=["us-east-1"],
        resources=sample_resources,
        metadata={"account_id": "123456789012", "region": "us-east-1"},
    )


@pytest.fixture
def mock_cdk_python_responses() -> Dict[str, str]:
    """Mock AI responses for CDK Python generation."""
    return {
        "Network Foundation": """
from aws_cdk import Stack, Tags
from aws_cdk import aws_ec2 as ec2
from constructs import Construct


class NetworkFoundationStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        self.main_vpc = ec2.Vpc(
            self, "main_vpc",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[]
        )

        Tags.of(self.main_vpc).add("Name", "main-vpc")
        Tags.of(self.main_vpc).add("Environment", "dev")

        self.public_subnet_1 = ec2.Subnet(
            self, "public_subnet_1",
            vpc_id=self.main_vpc.vpc_id,
            cidr_block="10.0.1.0/24",
            availability_zone="us-east-1a",
            map_public_ip_on_launch=True
        )

        Tags.of(self.public_subnet_1).add("Name", "public-subnet-1")
""",
        "Compute": """
from aws_cdk import Stack, Tags, Duration
from aws_cdk import aws_lambda as lambda_
from constructs import Construct


class ComputeStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        self.my_function = lambda_.Function(
            self, "my_function",
            function_name="my-function",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=lambda_.Code.from_inline("def handler(event, context): pass"),
            memory_size=128,
            timeout=Duration.seconds(30)
        )

        Tags.of(self.my_function).add("Name", "my-function")
""",
    }


class TestCDKPythonGenerationWorkflow:
    """Integration tests for CDK Python generation workflow."""

    def test_cdk_generator_python_initialization(self) -> None:
        """Test CDKGenerator initializes correctly for Python."""
        from src.generate.cdk_generator import CDKGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = CDKGenerator(
                output_dir=tmpdir,
                output_format="cdk-python",
            )

            assert generator.output_dir == tmpdir
            assert generator.output_format == "cdk-python"
            assert generator.agent is not None

    def test_generate_layer_selects_python_prompt(self) -> None:
        """Test generate_layer uses Python prompt for cdk-python format."""
        from src.generate.prompts.cdk_python import get_cdk_python_system_prompt

        system_prompt = get_cdk_python_system_prompt()

        assert "Python" in system_prompt
        assert "aws_cdk" in system_prompt
        assert "Stack" in system_prompt
        assert "snake_case" in system_prompt.lower()

    def test_categorize_layers_for_cdk_python(self) -> None:
        """Test categorize_layers works for CDK Python generation."""
        from src.generate.nodes.categorize_layers import categorize_layers

        resources = [
            TrackedResource(
                arn="arn:aws:ec2:us-east-1:123456789012:vpc/vpc-abc123",
                resource_type="ec2:vpc",
                name="main-vpc",
                region="us-east-1",
            ),
            TrackedResource(
                arn="arn:aws:lambda:us-east-1:123456789012:function:my-func",
                resource_type="lambda:function",
                name="my-func",
                region="us-east-1",
            ),
        ]

        state: GenerationState = {
            "resources": resources,
            "output_format": "cdk-python",
        }
        result = categorize_layers(state)

        assert "layers" in result
        assert "layer_order" in result

    @patch("src.generate.nodes.validate_cdk.subprocess.run")
    def test_cdk_synth_python(self, mock_run: MagicMock) -> None:
        """Test cdk_synth node works for Python projects."""
        from src.generate.nodes.validate_cdk import cdk_synth

        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create cdk.json for Python
            with open(os.path.join(tmpdir, "cdk.json"), "w") as f:
                f.write('{"app": "python app.py"}')

            state: GenerationState = {
                "output_dir": tmpdir,
                "output_format": "cdk-python",
                "npm_build_success": True,  # Python skips npm_build
                "validation_errors": [],
            }

            result = cdk_synth(state)

            assert isinstance(result, dict)


class TestCDKPythonProjectStructure:
    """Tests for CDK Python project file generation."""

    def test_generate_python_config_files(self) -> None:
        """Test Python config files are generated correctly."""
        from src.generate.cdk_generator import CDKGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = CDKGenerator(
                output_dir=tmpdir,
                output_format="cdk-python",
                project_name="test_project",
            )

            generator._generate_project_config_files()

            # Check requirements.txt exists
            assert os.path.exists(os.path.join(tmpdir, "requirements.txt"))

            # Check setup.py exists
            assert os.path.exists(os.path.join(tmpdir, "setup.py"))

            # Check cdk.json exists
            assert os.path.exists(os.path.join(tmpdir, "cdk.json"))

            # Check stacks directory exists
            assert os.path.isdir(os.path.join(tmpdir, "stacks"))

            # Check stacks/__init__.py exists
            assert os.path.exists(os.path.join(tmpdir, "stacks", "__init__.py"))

    def test_generate_python_app_entry_point(self) -> None:
        """Test Python app.py entry point is generated correctly."""
        from src.generate.cdk_generator import CDKGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = CDKGenerator(
                output_dir=tmpdir,
                output_format="cdk-python",
            )

            generator._generate_project_config_files()

            state = {
                "layer_order": ["Network Foundation", "Compute"],
            }

            generator._generate_app_entry_point(state)

            app_py_path = os.path.join(tmpdir, "app.py")
            assert os.path.exists(app_py_path)

            with open(app_py_path) as f:
                content = f.read()

            # Check imports
            assert "from stacks.network_foundation_stack import NetworkFoundationStack" in content
            assert "from stacks.compute_stack import ComputeStack" in content

            # Check instantiations
            assert "NetworkFoundationStack(app" in content
            assert "ComputeStack(app" in content

            # Check app.synth()
            assert "app.synth()" in content

    def test_requirements_txt_content(self) -> None:
        """Test requirements.txt has correct content."""
        from src.generate.cdk_generator import CDKGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = CDKGenerator(
                output_dir=tmpdir,
                output_format="cdk-python",
            )

            generator._generate_project_config_files()

            with open(os.path.join(tmpdir, "requirements.txt")) as f:
                content = f.read()

            assert "aws-cdk-lib" in content
            assert "constructs" in content

    def test_setup_py_content(self) -> None:
        """Test setup.py has correct content."""
        from src.generate.cdk_generator import CDKGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = CDKGenerator(
                output_dir=tmpdir,
                output_format="cdk-python",
                project_name="my_cdk_app",
            )

            generator._generate_project_config_files()

            with open(os.path.join(tmpdir, "setup.py")) as f:
                content = f.read()

            assert "my_cdk_app" in content
            assert "aws-cdk-lib" in content

    def test_cdk_json_python_app_command(self) -> None:
        """Test cdk.json has correct Python app command."""
        from src.generate.cdk_generator import CDKGenerator

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = CDKGenerator(
                output_dir=tmpdir,
                output_format="cdk-python",
            )

            generator._generate_project_config_files()

            import json

            with open(os.path.join(tmpdir, "cdk.json")) as f:
                cdk_config = json.load(f)

            assert "python" in cdk_config.get("app", "").lower()


class TestCDKPythonEndToEnd:
    """End-to-end tests for CDK Python generation."""

    @patch("src.generate.nodes.parse_inventory.SnapshotStorage")
    @patch("boto3.client")
    @patch("src.generate.nodes.validate_cdk.subprocess.run")
    def test_full_cdk_python_workflow(
        self,
        mock_subprocess: MagicMock,
        mock_boto_client: MagicMock,
        mock_storage_class: MagicMock,
        sample_snapshot: Snapshot,
        mock_cdk_python_responses: Dict[str, str],
    ) -> None:
        """Test complete CDK Python workflow from snapshot to files."""
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

            response_text = "# No matching layer"
            for key, value in mock_cdk_python_responses.items():
                if key.lower() in user_msg.lower():
                    response_text = value
                    break

            return {
                "output": {
                    "message": {
                        "content": [{"text": response_text}]
                    }
                }
            }

        mock_bedrock_client.converse.side_effect = converse_side_effect
        mock_boto_client.return_value = mock_bedrock_client
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = CDKGenerator(
                output_dir=tmpdir,
                output_format="cdk-python",
            )

            result = generator.run(snapshot_name="test-cdk-python-snapshot")

            # Check result structure
            assert hasattr(result, "success")
            assert hasattr(result, "generated_files")
            assert hasattr(result, "output_dir")

            # Check project files exist
            assert os.path.exists(os.path.join(tmpdir, "requirements.txt"))
            assert os.path.exists(os.path.join(tmpdir, "cdk.json"))
            assert os.path.exists(os.path.join(tmpdir, "setup.py"))

            # Check app.py exists
            assert os.path.exists(os.path.join(tmpdir, "app.py"))

            # Check stacks directory exists
            assert os.path.isdir(os.path.join(tmpdir, "stacks"))

    @patch("src.generate.nodes.parse_inventory.SnapshotStorage")
    def test_workflow_with_empty_snapshot(
        self,
        mock_storage_class: MagicMock,
    ) -> None:
        """Test workflow handles empty snapshot gracefully."""
        from src.generate.cdk_generator import CDKGenerator

        empty_snapshot = Snapshot(
            name="empty-snapshot",
            created_at=datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc),
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[],
            metadata={},
        )

        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = empty_snapshot
        mock_storage_class.return_value = mock_storage

        with tempfile.TemporaryDirectory() as tmpdir:
            generator = CDKGenerator(
                output_dir=tmpdir,
                output_format="cdk-python",
            )

            result = generator.run(snapshot_name="empty-snapshot")

            # Should complete without errors, just with no generated files
            assert result is not None
            assert os.path.exists(os.path.join(tmpdir, "cdk.json"))
