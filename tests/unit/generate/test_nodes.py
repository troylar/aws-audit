"""Unit tests for LangGraph graph nodes for IaC generation workflow.

Tests the individual node functions that process GenerationState
through the code generation pipeline.

Note: These tests require `langgraph` to be installed. If `langgraph` is not
available, tests will be skipped with an appropriate message.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

try:
    from src.generate.layers import RESOURCE_TYPE_TO_LAYER, LayerOrder, LayerStatus
    from src.generate.nodes.build_resource_map import build_resource_map
    from src.generate.nodes.categorize_layers import categorize_layers
    from src.generate.nodes.extract_lambda import extract_lambda_code
    from src.generate.nodes.generate_layer import generate_layer
    from src.generate.nodes.parse_inventory import parse_inventory
    from src.generate.state import GenerationConfig, GenerationState
    from src.models.generation import LambdaCode, Layer, ResourceMap, TrackedResource

    IMPORTS_AVAILABLE = True
except ImportError as e:
    IMPORTS_AVAILABLE = False
    IMPORT_ERROR = str(e)
    LayerOrder = None
    LayerStatus = None
    RESOURCE_TYPE_TO_LAYER = None
    GenerationConfig = None
    GenerationState = Dict[str, Any]
    LambdaCode = None
    Layer = None
    ResourceMap = None
    TrackedResource = None
    parse_inventory = None
    build_resource_map = None
    categorize_layers = None
    extract_lambda_code = None
    generate_layer = None

pytestmark = pytest.mark.skipif(
    not IMPORTS_AVAILABLE, reason=f"Required imports not available: {IMPORT_ERROR if not IMPORTS_AVAILABLE else ''}"
)


class TestParseInventoryNode:
    """Tests for parse_inventory node (T028).

    The parse_inventory node loads a snapshot from storage and extracts
    resources into the GenerationState.
    """

    @pytest.fixture
    def sample_snapshot_resources(self) -> List[MagicMock]:
        """Create sample resources as they would appear in a snapshot."""
        resources = []
        data = [
            {
                "arn": "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-12345678",
                "resource_type": "ec2:vpc",
                "name": "main-vpc",
                "region": "us-east-1",
                "tags": {"Environment": "production"},
                "raw_config": {
                    "VpcId": "vpc-12345678",
                    "CidrBlock": "10.0.0.0/16",
                    "State": "available",
                },
            },
            {
                "arn": "arn:aws:ec2:us-east-1:123456789012:subnet/subnet-abcdef12",
                "resource_type": "ec2:subnet",
                "name": "public-subnet-1",
                "region": "us-east-1",
                "tags": {"Name": "public-subnet-1"},
                "raw_config": {
                    "SubnetId": "subnet-abcdef12",
                    "VpcId": "vpc-12345678",
                    "CidrBlock": "10.0.1.0/24",
                    "AvailabilityZone": "us-east-1a",
                },
            },
            {
                "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-99887766",
                "resource_type": "ec2:instance",
                "name": "web-server",
                "region": "us-east-1",
                "tags": {"Role": "webserver"},
                "raw_config": {
                    "InstanceId": "i-99887766",
                    "InstanceType": "t3.medium",
                    "State": {"Name": "running"},
                },
            },
        ]
        for d in data:
            mock_resource = MagicMock()
            mock_resource.arn = d["arn"]
            mock_resource.resource_type = d["resource_type"]
            mock_resource.name = d["name"]
            mock_resource.region = d["region"]
            mock_resource.tags = d.get("tags", {})
            mock_resource.raw_config = d.get("raw_config", {})
            resources.append(mock_resource)
        return resources

    @pytest.fixture
    def initial_state(self) -> Dict[str, Any]:
        """Create initial state for parse_inventory node."""
        return {
            "snapshot_name": "test-snapshot",
            "output_dir": "/tmp/terraform-output",
            "output_format": "terraform",
        }

    def test_loads_snapshot_from_storage(
        self, initial_state: Dict[str, Any], sample_snapshot_resources: List[MagicMock]
    ) -> None:
        """Test that parse_inventory loads snapshot by name from storage."""
        mock_snapshot = MagicMock()
        mock_snapshot.resources = sample_snapshot_resources

        with patch("src.generate.nodes.parse_inventory.SnapshotStorage") as mock_storage_class:
            mock_storage = mock_storage_class.return_value
            mock_storage.load_snapshot.return_value = mock_snapshot

            parse_inventory(initial_state)

            mock_storage.load_snapshot.assert_called_once_with("test-snapshot")

    def test_extracts_resources_from_snapshot(
        self, initial_state: Dict[str, Any], sample_snapshot_resources: List[MagicMock]
    ) -> None:
        """Test that parse_inventory extracts resources into resources field."""
        mock_snapshot = MagicMock()
        mock_snapshot.resources = sample_snapshot_resources

        with patch("src.generate.nodes.parse_inventory.SnapshotStorage") as mock_storage_class:
            mock_storage = mock_storage_class.return_value
            mock_storage.load_snapshot.return_value = mock_snapshot

            result = parse_inventory(initial_state)

            assert "resources" in result
            assert len(result["resources"]) == 3

    def test_state_update_with_parsed_resources(
        self, initial_state: Dict[str, Any], sample_snapshot_resources: List[MagicMock]
    ) -> None:
        """Test that parse_inventory returns proper state update dict."""
        mock_snapshot = MagicMock()
        mock_snapshot.resources = sample_snapshot_resources

        with patch("src.generate.nodes.parse_inventory.SnapshotStorage") as mock_storage_class:
            mock_storage = mock_storage_class.return_value
            mock_storage.load_snapshot.return_value = mock_snapshot

            result = parse_inventory(initial_state)

            assert isinstance(result, dict)
            assert "resources" in result
            assert "snapshot" in result
            assert "errors" in result
            assert result["errors"] == []

    def test_handles_snapshot_not_found(self, initial_state: Dict[str, Any]) -> None:
        """Test that parse_inventory handles missing snapshot gracefully."""
        with patch("src.generate.nodes.parse_inventory.SnapshotStorage") as mock_storage_class:
            mock_storage = mock_storage_class.return_value
            mock_storage.load_snapshot.side_effect = FileNotFoundError("Not found")

            result = parse_inventory(initial_state)

            assert "errors" in result
            assert len(result["errors"]) > 0
            assert "test-snapshot" in result["errors"][0]

    def test_handles_empty_snapshot(self, initial_state: Dict[str, Any]) -> None:
        """Test that parse_inventory handles snapshot with no resources."""
        mock_snapshot = MagicMock()
        mock_snapshot.resources = []

        with patch("src.generate.nodes.parse_inventory.SnapshotStorage") as mock_storage_class:
            mock_storage = mock_storage_class.return_value
            mock_storage.load_snapshot.return_value = mock_snapshot

            result = parse_inventory(initial_state)

            assert "resources" in result
            assert result["resources"] == []

    def test_converts_to_tracked_resources(
        self, initial_state: Dict[str, Any], sample_snapshot_resources: List[MagicMock]
    ) -> None:
        """Test that resources are converted to TrackedResource objects."""
        mock_snapshot = MagicMock()
        mock_snapshot.resources = sample_snapshot_resources

        with patch("src.generate.nodes.parse_inventory.SnapshotStorage") as mock_storage_class:
            mock_storage = mock_storage_class.return_value
            mock_storage.load_snapshot.return_value = mock_snapshot

            result = parse_inventory(initial_state)

            assert len(result["resources"]) == 3
            for resource in result["resources"]:
                assert isinstance(resource, TrackedResource)


class TestBuildResourceMapNode:
    """Tests for build_resource_map node (T029).

    The build_resource_map node builds bidirectional mapping between
    AWS resource IDs and Terraform references.
    """

    @pytest.fixture
    def state_with_inventory(self) -> Dict[str, Any]:
        """Create state with populated inventory."""
        return {
            "snapshot_name": "test-snapshot",
            "output_dir": "/tmp/terraform-output",
            "output_format": "terraform",
            "inventory": [
                {
                    "arn": "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-12345678",
                    "type": "vpc:vpc",
                    "name": "main-vpc",
                    "region": "us-east-1",
                    "tags": {},
                    "raw_config": {"VpcId": "vpc-12345678"},
                },
                {
                    "arn": "arn:aws:ec2:us-east-1:123456789012:subnet/subnet-abcdef12",
                    "type": "vpc:subnet",
                    "name": "public-subnet-1",
                    "region": "us-east-1",
                    "tags": {},
                    "raw_config": {"SubnetId": "subnet-abcdef12", "VpcId": "vpc-12345678"},
                },
                {
                    "arn": "arn:aws:ec2:us-east-1:123456789012:instance/i-99887766",
                    "type": "ec2:instance",
                    "name": "web-server-01",
                    "region": "us-east-1",
                    "tags": {},
                    "raw_config": {"InstanceId": "i-99887766"},
                },
            ],
        }

    def test_builds_id_to_reference_mapping(self, state_with_inventory: Dict[str, Any]) -> None:
        """Test building AWS ID to Terraform reference mapping."""
        result = build_resource_map(state_with_inventory)

        assert "resource_map" in result
        resource_map = result["resource_map"]

        assert isinstance(resource_map, ResourceMap)
        assert "vpc-12345678" in resource_map.id_to_ref

    def test_handles_multiple_resource_types(self, state_with_inventory: Dict[str, Any]) -> None:
        """Test handling multiple resource types (vpc, subnet, instance)."""
        result = build_resource_map(state_with_inventory)

        resource_map = result["resource_map"]

        assert len(resource_map.id_to_ref) >= 3

    def test_terraform_name_sanitization(self, state_with_inventory: Dict[str, Any]) -> None:
        """Test that TrackedResource.get_terraform_name() sanitization is applied."""
        state_with_inventory["inventory"].append(
            {
                "arn": "arn:aws:s3:::my-special.bucket-name",
                "type": "s3:bucket",
                "name": "my-special.bucket-name",
                "region": "us-east-1",
                "tags": {},
                "raw_config": {"BucketName": "my-special.bucket-name"},
            }
        )

        result = build_resource_map(state_with_inventory)

        resource_map = result["resource_map"]

        bucket_refs = [v for k, v in resource_map.id_to_ref.items() if "s3" in v.lower()]
        assert len(bucket_refs) >= 1

        for ref in bucket_refs:
            parts = ref.split(".")
            if len(parts) >= 2:
                resource_name = parts[1]
                assert "-" not in resource_name
                assert "." not in resource_name

    def test_handles_empty_inventory(self) -> None:
        """Test build_resource_map with empty inventory."""
        state: Dict[str, Any] = {
            "snapshot_name": "test",
            "output_dir": "/tmp",
            "output_format": "terraform",
            "inventory": [],
        }

        result = build_resource_map(state)

        assert "resource_map" in result
        resource_map = result["resource_map"]
        assert len(resource_map.id_to_ref) == 0

    def test_maps_arns_to_references(self, state_with_inventory: Dict[str, Any]) -> None:
        """Test that full ARNs are also mapped to Terraform references."""
        result = build_resource_map(state_with_inventory)

        resource_map = result["resource_map"]

        arn = "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-12345678"
        assert arn in resource_map.id_to_ref

    def test_resource_map_bidirectional(self, state_with_inventory: Dict[str, Any]) -> None:
        """Test that ResourceMap has bidirectional mappings."""
        result = build_resource_map(state_with_inventory)

        resource_map = result["resource_map"]

        for aws_id, tf_ref in resource_map.id_to_ref.items():
            assert tf_ref in resource_map.ref_to_id


class TestCategorizeLayersNode:
    """Tests for categorize_layers node (T030).

    The categorize_layers node groups resources by dependency layer
    to ensure proper generation order.
    """

    @pytest.fixture
    def state_with_tracked_resources(self) -> Dict[str, Any]:
        """Create state with TrackedResource objects."""
        resources = [
            TrackedResource(
                arn="arn:aws:ec2:us-east-1:123:vpc/vpc-1", resource_type="ec2:vpc", name="vpc-1", region="us-east-1"
            ),
            TrackedResource(
                arn="arn:aws:ec2:us-east-1:123:subnet/subnet-1",
                resource_type="ec2:subnet",
                name="subnet-1",
                region="us-east-1",
            ),
            TrackedResource(
                arn="arn:aws:ec2:us-east-1:123:security-group/sg-1",
                resource_type="ec2:security-group",
                name="sg-1",
                region="us-east-1",
            ),
            TrackedResource(
                arn="arn:aws:iam::123:role/role-1", resource_type="iam:role", name="role-1", region="global"
            ),
            TrackedResource(
                arn="arn:aws:rds:us-east-1:123:db:db-1",
                resource_type="rds:db-instance",
                name="db-1",
                region="us-east-1",
            ),
            TrackedResource(
                arn="arn:aws:s3:::bucket-1", resource_type="s3:bucket", name="bucket-1", region="us-east-1"
            ),
            TrackedResource(
                arn="arn:aws:ec2:us-east-1:123:instance/i-1",
                resource_type="ec2:instance",
                name="instance-1",
                region="us-east-1",
            ),
            TrackedResource(
                arn="arn:aws:lambda:us-east-1:123:function:func-1",
                resource_type="lambda:function",
                name="func-1",
                region="us-east-1",
            ),
            TrackedResource(
                arn="arn:aws:elasticloadbalancing:us-east-1:123:loadbalancer/app/lb-1/123",
                resource_type="elbv2:loadbalancer",
                name="lb-1",
                region="us-east-1",
            ),
            TrackedResource(
                arn="arn:aws:apigateway:us-east-1::/apis/api-1",
                resource_type="apigatewayv2:api",
                name="api-1",
                region="us-east-1",
            ),
            TrackedResource(
                arn="arn:aws:sqs:us-east-1:123:queue-1", resource_type="sqs:queue", name="queue-1", region="us-east-1"
            ),
            TrackedResource(
                arn="arn:aws:logs:us-east-1:123:log-group:/aws/lambda/func-1",
                resource_type="logs:log-group",
                name="/aws/lambda/func-1",
                region="us-east-1",
            ),
            TrackedResource(
                arn="arn:aws:route53:::hostedzone/Z123",
                resource_type="route53:hosted-zone",
                name="example.com",
                region="global",
            ),
        ]
        return {
            "snapshot_name": "test-snapshot",
            "output_dir": "/tmp/terraform-output",
            "output_format": "terraform",
            "resources": resources,
            "resource_map": ResourceMap(),
        }

    def test_groups_resources_by_layer(self, state_with_tracked_resources: Dict[str, Any]) -> None:
        """Test that resources are grouped by their dependency layer."""
        result = categorize_layers(state_with_tracked_resources)

        assert "layers" in result
        layers = result["layers"]

        assert isinstance(layers, list)
        assert len(layers) > 0

    def test_returns_layer_objects(self, state_with_tracked_resources: Dict[str, Any]) -> None:
        """Test that categorize_layers returns Layer objects."""
        result = categorize_layers(state_with_tracked_resources)

        layers = result["layers"]
        for layer in layers:
            assert isinstance(layer, Layer)
            assert hasattr(layer, "order")
            assert hasattr(layer, "name")
            assert hasattr(layer, "resources")
            assert hasattr(layer, "status")

    def test_layer_ordering(self, state_with_tracked_resources: Dict[str, Any]) -> None:
        """Test that layers are ordered correctly."""
        result = categorize_layers(state_with_tracked_resources)

        layers = result["layers"]

        orders = [layer.order for layer in layers]
        assert orders == sorted(orders), "Layers should be in ascending order"

    def test_network_layer_contains_vpc(self, state_with_tracked_resources: Dict[str, Any]) -> None:
        """Test VPC resources are in NETWORK layer."""
        result = categorize_layers(state_with_tracked_resources)

        layers = result["layers"]

        network_layer = None
        for layer in layers:
            if layer.order == LayerOrder.NETWORK:
                network_layer = layer
                break

        assert network_layer is not None, "NETWORK layer should exist"

        vpc_resources = [r for r in network_layer.resources if r.resource_type == "ec2:vpc"]
        assert len(vpc_resources) >= 1

    def test_compute_layer_contains_lambda(self, state_with_tracked_resources: Dict[str, Any]) -> None:
        """Test Lambda functions are in COMPUTE layer."""
        result = categorize_layers(state_with_tracked_resources)

        layers = result["layers"]

        compute_layer = None
        for layer in layers:
            if layer.order == LayerOrder.COMPUTE:
                compute_layer = layer
                break

        assert compute_layer is not None, "COMPUTE layer should exist"

        lambda_resources = [r for r in compute_layer.resources if r.resource_type == "lambda:function"]
        assert len(lambda_resources) >= 1

    def test_all_resources_categorized(self, state_with_tracked_resources: Dict[str, Any]) -> None:
        """Test that all resources are placed into layers."""
        result = categorize_layers(state_with_tracked_resources)

        layers = result["layers"]

        total_resources = sum(len(layer.resources) for layer in layers)
        assert total_resources == len(state_with_tracked_resources["resources"])

    def test_layers_have_pending_status(self, state_with_tracked_resources: Dict[str, Any]) -> None:
        """Test that all layers start with PENDING status."""
        result = categorize_layers(state_with_tracked_resources)

        layers = result["layers"]

        for layer in layers:
            assert layer.status == LayerStatus.PENDING

    def test_handles_unknown_resource_types(self) -> None:
        """Test handling of resource types not in RESOURCE_TYPE_TO_LAYER."""
        resources = [
            TrackedResource(
                arn="arn:aws:unknown:us-east-1:123:thing/thing-1",
                resource_type="unknown:thing",
                name="thing-1",
                region="us-east-1",
            ),
        ]
        state: Dict[str, Any] = {
            "snapshot_name": "test",
            "output_dir": "/tmp",
            "output_format": "terraform",
            "resources": resources,
            "resource_map": ResourceMap(),
        }

        result = categorize_layers(state)

        assert "layers" in result
        layers = result["layers"]
        assert len(layers) > 0


class TestExtractLambdaCodeNode:
    """Tests for extract_lambda_code node (T031).

    The extract_lambda_code node extracts base64-encoded Lambda code
    from resources and writes zip files to the output directory.
    """

    @pytest.fixture
    def lambda_zip_content(self) -> bytes:
        """Create sample zip content for Lambda functions."""
        return b"PK\x03\x04test-lambda-code-package"

    @pytest.fixture
    def state_with_lambda_resources(self, lambda_zip_content: bytes) -> Dict[str, Any]:
        """Create state with Lambda function resources."""
        encoded_code = base64.b64encode(lambda_zip_content).decode("utf-8")

        return {
            "snapshot_name": "test-snapshot",
            "output_dir": "/tmp/terraform-output",
            "output_format": "terraform",
            "inventory": [
                {
                    "arn": "arn:aws:lambda:us-east-1:123456789012:function:inline-func",
                    "type": "lambda:function",
                    "name": "inline-func",
                    "region": "us-east-1",
                    "tags": {},
                    "raw_config": {
                        "FunctionName": "inline-func",
                        "Runtime": "python3.11",
                        "Handler": "index.handler",
                        "CodeSha256": "abc123",
                        "CodeSize": len(lambda_zip_content),
                        "Code": {
                            "ZipFile": encoded_code,
                        },
                    },
                },
                {
                    "arn": "arn:aws:lambda:us-east-1:123456789012:function:s3-func",
                    "type": "lambda:function",
                    "name": "s3-func",
                    "region": "us-east-1",
                    "tags": {},
                    "raw_config": {
                        "FunctionName": "s3-func",
                        "Runtime": "nodejs18.x",
                        "Handler": "app.handler",
                        "Code": {
                            "S3Bucket": "deployment-bucket",
                            "S3Key": "lambda/s3-func.zip",
                        },
                    },
                },
                {
                    "arn": "arn:aws:lambda:us-east-1:123456789012:function:no-code-func",
                    "type": "lambda:function",
                    "name": "no-code-func",
                    "region": "us-east-1",
                    "tags": {},
                    "raw_config": {
                        "FunctionName": "no-code-func",
                        "Runtime": "python3.11",
                        "Handler": "main.handler",
                        "Code": {},
                    },
                },
            ],
            "layers": {},
            "resource_map": {},
        }

    def test_extracts_base64_code_from_lambda(
        self, state_with_lambda_resources: Dict[str, Any], tmp_path: Path
    ) -> None:
        """Test extracting base64-encoded code from Lambda resources."""
        state_with_lambda_resources["output_dir"] = str(tmp_path)

        result = extract_lambda_code(state_with_lambda_resources)

        assert "lambda_code_paths" in result
        lambda_paths = result["lambda_code_paths"]

        assert "inline-func" in lambda_paths

    def test_writes_zip_files_to_output_directory(
        self, state_with_lambda_resources: Dict[str, Any], tmp_path: Path, lambda_zip_content: bytes
    ) -> None:
        """Test that zip files are written to the output directory."""
        state_with_lambda_resources["output_dir"] = str(tmp_path)

        result = extract_lambda_code(state_with_lambda_resources)

        lambda_paths = result["lambda_code_paths"]

        if "inline-func" in lambda_paths:
            zip_path = Path(lambda_paths["inline-func"])
            assert zip_path.exists()
            assert zip_path.read_bytes() == lambda_zip_content

    def test_handles_lambdas_without_inline_code(
        self, state_with_lambda_resources: Dict[str, Any], tmp_path: Path
    ) -> None:
        """Test handling Lambdas without inline code (S3-based)."""
        state_with_lambda_resources["output_dir"] = str(tmp_path)

        result = extract_lambda_code(state_with_lambda_resources)

        lambda_paths = result["lambda_code_paths"]

        assert "s3-func" not in lambda_paths

    def test_handles_lambdas_with_empty_code_config(
        self, state_with_lambda_resources: Dict[str, Any], tmp_path: Path
    ) -> None:
        """Test handling Lambdas with empty Code configuration."""
        state_with_lambda_resources["output_dir"] = str(tmp_path)

        result = extract_lambda_code(state_with_lambda_resources)

        lambda_paths = result["lambda_code_paths"]

        assert "no-code-func" not in lambda_paths

    def test_creates_lambda_subdirectory(self, state_with_lambda_resources: Dict[str, Any], tmp_path: Path) -> None:
        """Test that Lambda code is extracted to lambda subdirectory."""
        state_with_lambda_resources["output_dir"] = str(tmp_path)

        result = extract_lambda_code(state_with_lambda_resources)

        lambda_paths = result["lambda_code_paths"]

        if "inline-func" in lambda_paths:
            zip_path = Path(lambda_paths["inline-func"])
            assert "lambda" in str(zip_path.parent)

    def test_skips_non_lambda_resources(self, tmp_path: Path) -> None:
        """Test that non-Lambda resources are skipped."""
        state: Dict[str, Any] = {
            "snapshot_name": "test",
            "output_dir": str(tmp_path),
            "output_format": "terraform",
            "inventory": [
                {
                    "arn": "arn:aws:ec2:us-east-1:123:vpc/vpc-1",
                    "type": "ec2:vpc",
                    "name": "vpc-1",
                    "region": "us-east-1",
                    "tags": {},
                    "raw_config": {},
                },
                {
                    "arn": "arn:aws:s3:::bucket-1",
                    "type": "s3:bucket",
                    "name": "bucket-1",
                    "region": "us-east-1",
                    "tags": {},
                    "raw_config": {},
                },
            ],
            "layers": {},
            "resource_map": {},
        }

        result = extract_lambda_code(state)

        lambda_paths = result.get("lambda_code_paths", {})
        assert len(lambda_paths) == 0

    def test_returns_errors_list(self, tmp_path: Path) -> None:
        """Test that extract_lambda_code returns an errors list."""
        state: Dict[str, Any] = {
            "snapshot_name": "test",
            "output_dir": str(tmp_path),
            "output_format": "terraform",
            "inventory": [],
            "layers": {},
            "resource_map": {},
        }

        result = extract_lambda_code(state)

        assert "errors" in result
        assert isinstance(result["errors"], list)

    def test_handles_missing_output_dir(self) -> None:
        """Test handling when output_dir is not specified."""
        state: Dict[str, Any] = {
            "snapshot_name": "test",
            "output_dir": "",
            "output_format": "terraform",
            "inventory": [],
        }

        result = extract_lambda_code(state)

        assert "errors" in result
        assert len(result["errors"]) > 0


class TestGenerateLayerNode:
    """Tests for generate_layer node (T032).

    The generate_layer node uses AWS Bedrock to generate Terraform code for
    resources in a specific layer.
    """

    @pytest.fixture
    def state_with_current_layer(self) -> Dict[str, Any]:
        """Create state ready for layer generation."""
        return {
            "snapshot_name": "test-snapshot",
            "output_dir": "/tmp/terraform-output",
            "output_format": "terraform",
            "inventory": [
                {
                    "arn": "arn:aws:ec2:us-east-1:123:vpc/vpc-1",
                    "type": "ec2:vpc",
                    "name": "main-vpc",
                    "region": "us-east-1",
                    "tags": {"Environment": "prod"},
                    "raw_config": {"VpcId": "vpc-1", "CidrBlock": "10.0.0.0/16"},
                },
                {
                    "arn": "arn:aws:ec2:us-east-1:123:subnet/subnet-1",
                    "type": "ec2:subnet",
                    "name": "public-1",
                    "region": "us-east-1",
                    "tags": {},
                    "raw_config": {"SubnetId": "subnet-1", "VpcId": "vpc-1", "CidrBlock": "10.0.1.0/24"},
                },
            ],
            "layers": {
                "NETWORK": [
                    {
                        "arn": "arn:aws:ec2:us-east-1:123:vpc/vpc-1",
                        "type": "ec2:vpc",
                        "name": "main-vpc",
                        "region": "us-east-1",
                        "tags": {"Environment": "prod"},
                        "raw_config": {"VpcId": "vpc-1", "CidrBlock": "10.0.0.0/16"},
                    },
                    {
                        "arn": "arn:aws:ec2:us-east-1:123:subnet/subnet-1",
                        "type": "ec2:subnet",
                        "name": "public-1",
                        "region": "us-east-1",
                        "tags": {},
                        "raw_config": {"SubnetId": "subnet-1", "VpcId": "vpc-1", "CidrBlock": "10.0.1.0/24"},
                    },
                ],
            },
            "layer_order": ["NETWORK"],
            "current_layer_index": 0,
            "current_layer_status": "pending",
            "resource_map": ResourceMap(),
            "attempt_count": 0,
            "max_attempts": 3,
        }

    @pytest.fixture
    def mock_ai_response(self) -> str:
        """Create mock AI response with Terraform code."""
        return """```hcl
resource "aws_vpc" "main_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name        = "main-vpc"
    Environment = "prod"
  }
}

resource "aws_subnet" "public_1" {
  vpc_id            = "vpc-1"
  cidr_block        = "10.0.1.0/24"
  availability_zone = "us-east-1a"

  tags = {
    Name = "public-1"
  }
}
```"""

    def test_calls_bedrock_client(self, state_with_current_layer: Dict[str, Any], tmp_path: Path) -> None:
        """Test that generate_layer calls Bedrock client."""
        state_with_current_layer["output_dir"] = str(tmp_path)

        mock_client = MagicMock()
        mock_response = {"output": {"message": {"content": [{"text": "```hcl\n# test\n```"}]}}}
        mock_client.converse.return_value = mock_response

        with patch("boto3.client", return_value=mock_client):
            generate_layer(state_with_current_layer)

            mock_client.converse.assert_called_once()

    def test_response_parsing_removes_markdown(
        self, state_with_current_layer: Dict[str, Any], mock_ai_response: str, tmp_path: Path
    ) -> None:
        """Test that AI response has markdown code blocks stripped."""
        state_with_current_layer["output_dir"] = str(tmp_path)

        mock_client = MagicMock()
        mock_response = {"output": {"message": {"content": [{"text": mock_ai_response}]}}}
        mock_client.converse.return_value = mock_response

        with patch("boto3.client", return_value=mock_client):
            result = generate_layer(state_with_current_layer)

            if "generated_code" in result:
                for layer_name, code in result["generated_code"].items():
                    assert not code.startswith("```")
                    assert not code.endswith("```")

    def test_resource_reference_substitution(self, state_with_current_layer: Dict[str, Any], tmp_path: Path) -> None:
        """Test that hardcoded IDs are replaced with Terraform references."""
        resource_map = ResourceMap()
        resource_map.add("vpc-1", "aws_vpc.main_vpc", "ec2:vpc")
        state_with_current_layer["resource_map"] = resource_map
        state_with_current_layer["output_dir"] = str(tmp_path)

        ai_response_with_hardcoded_ids = """```hcl
resource "aws_subnet" "public_1" {
  vpc_id     = "vpc-1"
  cidr_block = "10.0.1.0/24"
}
```"""

        mock_client = MagicMock()
        mock_response = {"output": {"message": {"content": [{"text": ai_response_with_hardcoded_ids}]}}}
        mock_client.converse.return_value = mock_response

        with patch("boto3.client", return_value=mock_client):
            result = generate_layer(state_with_current_layer)

            if "generated_code" in result:
                for layer_name, code in result["generated_code"].items():
                    if '"vpc-1"' not in code:
                        assert "aws_vpc.main_vpc.id" in code

    def test_handles_ai_error(self, state_with_current_layer: Dict[str, Any], tmp_path: Path) -> None:
        """Test handling of AI API errors."""
        state_with_current_layer["output_dir"] = str(tmp_path)

        mock_client = MagicMock()
        mock_client.converse.side_effect = Exception("Bedrock API Error")

        with patch("boto3.client", return_value=mock_client):
            result = generate_layer(state_with_current_layer)

            assert "errors" in result or "current_layer_status" in result
            if "current_layer_status" in result:
                assert result["current_layer_status"] == LayerStatus.FAILED.value

    def test_updates_layer_status_on_success(
        self, state_with_current_layer: Dict[str, Any], mock_ai_response: str, tmp_path: Path
    ) -> None:
        """Test that layer status is updated on successful generation."""
        state_with_current_layer["output_dir"] = str(tmp_path)

        mock_client = MagicMock()
        mock_response = {"output": {"message": {"content": [{"text": mock_ai_response}]}}}
        mock_client.converse.return_value = mock_response

        with patch("boto3.client", return_value=mock_client):
            result = generate_layer(state_with_current_layer)

            if "current_layer_status" in result:
                assert result["current_layer_status"] == LayerStatus.COMPLETED.value

    def test_increments_layer_index_on_success(
        self, state_with_current_layer: Dict[str, Any], mock_ai_response: str, tmp_path: Path
    ) -> None:
        """Test that current_layer_index is incremented on success."""
        state_with_current_layer["output_dir"] = str(tmp_path)

        mock_client = MagicMock()
        mock_response = {"output": {"message": {"content": [{"text": mock_ai_response}]}}}
        mock_client.converse.return_value = mock_response

        with patch("boto3.client", return_value=mock_client):
            result = generate_layer(state_with_current_layer)

            if "current_layer_index" in result:
                assert result["current_layer_index"] == 1

    def test_generates_file_in_output_dir(
        self, state_with_current_layer: Dict[str, Any], mock_ai_response: str, tmp_path: Path
    ) -> None:
        """Test that generated Terraform file is written to output directory."""
        state_with_current_layer["output_dir"] = str(tmp_path)

        mock_client = MagicMock()
        mock_response = {"output": {"message": {"content": [{"text": mock_ai_response}]}}}
        mock_client.converse.return_value = mock_response

        with patch("boto3.client", return_value=mock_client):
            result = generate_layer(state_with_current_layer)

            if "generated_files" in result:
                assert len(result["generated_files"]) > 0
                for filepath in result["generated_files"]:
                    assert Path(filepath).exists()

    def test_handles_empty_layer(self, state_with_current_layer: Dict[str, Any], tmp_path: Path) -> None:
        """Test handling layer with no resources."""
        state_with_current_layer["layers"]["NETWORK"] = []
        state_with_current_layer["output_dir"] = str(tmp_path)

        result = generate_layer(state_with_current_layer)

        assert "current_layer_index" in result
        assert result["current_layer_index"] == 1
        assert result["current_layer_status"] == LayerStatus.COMPLETED.value

    def test_handles_no_more_layers(self, state_with_current_layer: Dict[str, Any], tmp_path: Path) -> None:
        """Test handling when all layers have been processed."""
        state_with_current_layer["current_layer_index"] = 1
        state_with_current_layer["output_dir"] = str(tmp_path)

        result = generate_layer(state_with_current_layer)

        assert "errors" in result
        assert len(result["errors"]) > 0


class TestNodeSignatures:
    """Tests to verify all nodes have correct signatures."""

    def test_parse_inventory_signature(self) -> None:
        """Test parse_inventory has correct signature."""
        import inspect

        sig = inspect.signature(parse_inventory)
        params = list(sig.parameters.keys())
        assert len(params) == 1
        assert params[0] == "state"

    def test_build_resource_map_signature(self) -> None:
        """Test build_resource_map has correct signature."""
        import inspect

        sig = inspect.signature(build_resource_map)
        params = list(sig.parameters.keys())
        assert len(params) == 1
        assert params[0] == "state"

    def test_categorize_layers_signature(self) -> None:
        """Test categorize_layers has correct signature."""
        import inspect

        sig = inspect.signature(categorize_layers)
        params = list(sig.parameters.keys())
        assert len(params) == 1
        assert params[0] == "state"

    def test_extract_lambda_code_signature(self) -> None:
        """Test extract_lambda_code has correct signature."""
        import inspect

        sig = inspect.signature(extract_lambda_code)
        params = list(sig.parameters.keys())
        assert len(params) == 1
        assert params[0] == "state"

    def test_generate_layer_signature(self) -> None:
        """Test generate_layer has correct signature."""
        import inspect

        sig = inspect.signature(generate_layer)
        params = list(sig.parameters.keys())
        assert len(params) == 1
        assert params[0] == "state"


class TestNodeReturnTypes:
    """Tests to verify nodes return proper state update dicts."""

    def test_parse_inventory_returns_dict(self) -> None:
        """Test parse_inventory returns a dict for state update."""
        mock_snapshot = MagicMock()
        mock_snapshot.resources = []

        with patch("src.generate.nodes.parse_inventory.SnapshotStorage") as mock_storage_class:
            mock_storage = mock_storage_class.return_value
            mock_storage.load_snapshot.return_value = mock_snapshot

            state: Dict[str, Any] = {"snapshot_name": "test", "output_dir": "/tmp", "output_format": "terraform"}
            result = parse_inventory(state)

            assert isinstance(result, dict)
            assert "resources" in result

    def test_build_resource_map_returns_dict(self) -> None:
        """Test build_resource_map returns a dict for state update."""
        state: Dict[str, Any] = {
            "snapshot_name": "test",
            "output_dir": "/tmp",
            "output_format": "terraform",
            "inventory": [],
        }
        result = build_resource_map(state)

        assert isinstance(result, dict)
        assert "resource_map" in result

    def test_categorize_layers_returns_dict(self) -> None:
        """Test categorize_layers returns a dict for state update."""
        state: Dict[str, Any] = {
            "snapshot_name": "test",
            "output_dir": "/tmp",
            "output_format": "terraform",
            "resources": [],
            "resource_map": ResourceMap(),
        }
        result = categorize_layers(state)

        assert isinstance(result, dict)
        assert "layers" in result

    def test_extract_lambda_code_returns_dict(self, tmp_path: Path) -> None:
        """Test extract_lambda_code returns a dict for state update."""
        state: Dict[str, Any] = {
            "snapshot_name": "test",
            "output_dir": str(tmp_path),
            "output_format": "terraform",
            "inventory": [],
            "layers": {},
            "resource_map": {},
        }
        result = extract_lambda_code(state)

        assert isinstance(result, dict)
        assert "lambda_code_paths" in result
        assert "errors" in result

    def test_generate_layer_returns_dict(self, tmp_path: Path) -> None:
        """Test generate_layer returns a dict for state update."""
        mock_client = MagicMock()
        mock_response = {"output": {"message": {"content": [{"text": "```hcl\n# test\n```"}]}}}
        mock_client.converse.return_value = mock_response

        state: Dict[str, Any] = {
            "snapshot_name": "test",
            "output_dir": str(tmp_path),
            "output_format": "terraform",
            "inventory": [],
            "layers": {"NETWORK": []},
            "layer_order": ["NETWORK"],
            "current_layer_index": 0,
            "current_layer_status": "pending",
            "resource_map": ResourceMap(),
            "attempt_count": 0,
            "max_attempts": 3,
        }

        with patch("boto3.client", return_value=mock_client):
            result = generate_layer(state)

            assert isinstance(result, dict)
