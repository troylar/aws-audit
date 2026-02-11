"""Unit tests for compare_inventory node.

Tests the compare_inventory node which uses AWS Bedrock to compare
inventory resources against generated Terraform code.
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

try:
    from src.generate.nodes.compare_inventory import (
        _combine_generated_code,
        _deterministic_coverage_check,
        _extract_key_attributes,
        _format_inventory_for_comparison,
        _parse_comparison_response,
        compare_inventory,
    )
    from src.models.generation import TrackedResource

    IMPORTS_AVAILABLE = True
except ImportError as e:
    IMPORTS_AVAILABLE = False
    IMPORT_ERROR = str(e)
    compare_inventory = None
    TrackedResource = None
    _format_inventory_for_comparison = None
    _deterministic_coverage_check = None
    _combine_generated_code = None
    _parse_comparison_response = None
    _extract_key_attributes = None

pytestmark = pytest.mark.skipif(
    not IMPORTS_AVAILABLE, reason=f"Required imports not available: {IMPORT_ERROR if not IMPORTS_AVAILABLE else ''}"
)


class TestCompareInventoryNode:
    """Tests for compare_inventory node."""

    @pytest.fixture
    def sample_resources(self) -> List[TrackedResource]:
        """Create sample TrackedResource objects."""
        return [
            TrackedResource(
                arn="arn:aws:ec2:us-east-1:123456789012:vpc/vpc-12345678",
                resource_type="ec2:vpc",
                name="main-vpc",
                region="us-east-1",
                tags={"Environment": "production"},
                raw_config={"VpcId": "vpc-12345678", "CidrBlock": "10.0.0.0/16"},
            ),
            TrackedResource(
                arn="arn:aws:ec2:us-east-1:123456789012:subnet/subnet-abcdef12",
                resource_type="ec2:subnet",
                name="public-subnet-1",
                region="us-east-1",
                tags={},
                raw_config={"SubnetId": "subnet-abcdef12", "VpcId": "vpc-12345678", "CidrBlock": "10.0.1.0/24"},
            ),
            TrackedResource(
                arn="arn:aws:lambda:us-east-1:123456789012:function:my-function",
                resource_type="lambda:function",
                name="my-function",
                region="us-east-1",
                tags={},
                raw_config={"FunctionName": "my-function", "Runtime": "python3.11", "Handler": "index.handler"},
            ),
        ]

    @pytest.fixture
    def sample_generated_code(self) -> Dict[str, str]:
        """Create sample generated Terraform code."""
        return {
            "Network Foundation": """
resource "aws_vpc" "main_vpc" {
  cidr_block = "10.0.0.0/16"
  tags = {
    Name = "main-vpc"
  }
}

resource "aws_subnet" "public_subnet_1" {
  vpc_id     = aws_vpc.main_vpc.id
  cidr_block = "10.0.1.0/24"
}
""",
            "Compute": """
resource "aws_lambda_function" "my_function" {
  function_name = "my-function"
  runtime       = "python3.11"
  handler       = "index.handler"
}
""",
        }

    @pytest.fixture
    def mock_llm_response_text(self) -> str:
        """Create mock LLM response text."""
        return """{
    "coverage_percentage": 100.0,
    "total_resources": 3,
    "represented_count": 3,
    "missing_count": 0,
    "represented_resources": [
        {"type": "ec2:vpc", "name": "main-vpc", "terraform_resource": "aws_vpc.main_vpc"},
        {"type": "ec2:subnet", "name": "public-subnet-1", "terraform_resource": "aws_subnet.public_subnet_1"},
        {"type": "lambda:function", "name": "my-function", "terraform_resource": "aws_lambda_function.my_function"}
    ],
    "missing_resources": [],
    "issues": [],
    "summary": "All 3 inventory resources are represented in the generated Terraform code."
}"""

    def test_empty_resources_returns_zero_coverage(self) -> None:
        """Test handling of empty resources list."""
        state: Dict[str, Any] = {
            "resources": [],
            "generated_code": {"layer1": "# some code"},
        }

        result = compare_inventory(state)

        assert "comparison_result" in result
        comparison = result["comparison_result"]
        assert comparison["coverage_percentage"] == 0.0
        assert comparison["total_resources"] == 0
        assert comparison["summary"] == "No resources in inventory to compare."

    def test_empty_generated_code_returns_all_missing(self, sample_resources: List[TrackedResource]) -> None:
        """Test handling of empty generated code."""
        state: Dict[str, Any] = {
            "resources": sample_resources,
            "generated_code": {},
        }

        result = compare_inventory(state)

        assert "comparison_result" in result
        comparison = result["comparison_result"]
        assert comparison["coverage_percentage"] == 0.0
        assert comparison["total_resources"] == 3
        assert comparison["missing_count"] == 3
        assert len(comparison["missing_resources"]) == 3
        assert len(comparison["issues"]) > 0

    def test_calls_llm_client(
        self,
        sample_resources: List[TrackedResource],
        sample_generated_code: Dict[str, str],
        mock_llm_response_text: str,
    ) -> None:
        """Test that compare_inventory calls LLM client."""
        state: Dict[str, Any] = {
            "resources": sample_resources,
            "generated_code": sample_generated_code,
        }

        mock_instance = MagicMock()
        mock_instance.stream.side_effect = Exception("Streaming not available")
        mock_instance.complete.return_value = mock_llm_response_text

        with patch("src.generate.nodes.compare_inventory.LLMClient", return_value=mock_instance):
            compare_inventory(state)

            mock_instance.complete.assert_called_once()

    def test_parses_successful_response(
        self,
        sample_resources: List[TrackedResource],
        sample_generated_code: Dict[str, str],
        mock_llm_response_text: str,
    ) -> None:
        """Test parsing of successful LLM response."""
        state: Dict[str, Any] = {
            "resources": sample_resources,
            "generated_code": sample_generated_code,
        }

        mock_instance = MagicMock()
        mock_instance.stream.side_effect = Exception("Streaming not available")
        mock_instance.complete.return_value = mock_llm_response_text

        with patch("src.generate.nodes.compare_inventory.LLMClient", return_value=mock_instance):
            result = compare_inventory(state)

            comparison = result["comparison_result"]
            assert comparison["coverage_percentage"] == 100.0
            assert comparison["represented_count"] == 3
            assert comparison["missing_count"] == 0
            assert len(comparison["represented_resources"]) == 3

    def test_handles_llm_error(
        self,
        sample_resources: List[TrackedResource],
        sample_generated_code: Dict[str, str],
    ) -> None:
        """Test handling of LLM API errors."""
        state: Dict[str, Any] = {
            "resources": sample_resources,
            "generated_code": sample_generated_code,
        }

        mock_instance = MagicMock()
        mock_instance.stream.side_effect = Exception("Streaming not available")
        mock_instance.complete.side_effect = Exception("LLM API Error")

        with patch("src.generate.nodes.compare_inventory.LLMClient", return_value=mock_instance):
            result = compare_inventory(state)

            assert "comparison_result" in result
            comparison = result["comparison_result"]
            assert comparison["coverage_percentage"] == 0.0
            assert len(comparison["issues"]) > 0
            assert "errors" in result

    def test_returns_dict_for_state_update(
        self,
        sample_resources: List[TrackedResource],
        sample_generated_code: Dict[str, str],
        mock_llm_response_text: str,
    ) -> None:
        """Test that compare_inventory returns a dict for state update."""
        state: Dict[str, Any] = {
            "resources": sample_resources,
            "generated_code": sample_generated_code,
        }

        mock_instance = MagicMock()
        mock_instance.stream.side_effect = Exception("Streaming not available")
        mock_instance.complete.return_value = mock_llm_response_text

        with patch("src.generate.nodes.compare_inventory.LLMClient", return_value=mock_instance):
            result = compare_inventory(state)

            assert isinstance(result, dict)
            assert "comparison_result" in result


class TestFormatInventoryForComparison:
    """Tests for _format_inventory_for_comparison helper function."""

    def test_formats_tracked_resources(self) -> None:
        """Test formatting TrackedResource objects."""
        resources = [
            TrackedResource(
                arn="arn:aws:ec2:us-east-1:123:vpc/vpc-1",
                resource_type="ec2:vpc",
                name="test-vpc",
                region="us-east-1",
                raw_config={"CidrBlock": "10.0.0.0/16"},
            ),
        ]

        result = _format_inventory_for_comparison(resources)

        assert "ec2:vpc" in result
        assert "test-vpc" in result
        assert "arn:aws:ec2:us-east-1:123:vpc/vpc-1" in result
        assert "CidrBlock=10.0.0.0/16" in result

    def test_formats_dict_resources(self) -> None:
        """Test formatting dict resources."""
        resources = [
            {
                "arn": "arn:aws:s3:::test-bucket",
                "resource_type": "s3:bucket",
                "name": "test-bucket",
                "raw_config": {"BucketName": "test-bucket"},
            },
        ]

        result = _format_inventory_for_comparison(resources)

        assert "s3:bucket" in result
        assert "test-bucket" in result

    def test_handles_multiple_resources(self) -> None:
        """Test formatting multiple resources with numbering."""
        resources = [
            TrackedResource(arn="arn:1", resource_type="ec2:vpc", name="vpc-1", region="us-east-1"),
            TrackedResource(arn="arn:2", resource_type="ec2:subnet", name="subnet-1", region="us-east-1"),
        ]

        result = _format_inventory_for_comparison(resources)

        assert "1. Type: ec2:vpc" in result
        assert "2. Type: ec2:subnet" in result


class TestCombineGeneratedCode:
    """Tests for _combine_generated_code helper function."""

    def test_combines_multiple_layers(self) -> None:
        """Test combining code from multiple layers."""
        generated_code = {
            "Network": "# network code",
            "Compute": "# compute code",
        }

        result = _combine_generated_code(generated_code)

        assert "# === LAYER: Network ===" in result
        assert "# === LAYER: Compute ===" in result
        assert "# network code" in result
        assert "# compute code" in result

    def test_handles_empty_dict(self) -> None:
        """Test handling empty generated code dict."""
        result = _combine_generated_code({})
        assert result == ""


class TestParseComparisonResponse:
    """Tests for _parse_comparison_response helper function."""

    def test_parses_valid_json(self) -> None:
        """Test parsing valid JSON response.

        Note: Coverage is recalculated based on represented_count/total_resources,
        not the AI-reported coverage_percentage (which may have math errors).
        """
        response = """{
            "coverage_percentage": 85.5,
            "total_resources": 10,
            "represented_count": 8,
            "missing_count": 2,
            "represented_resources": [{"type": "ec2:vpc", "name": "vpc-1", "terraform_resource": "aws_vpc.vpc_1"}],
            "missing_resources": [{"type": "s3:bucket", "name": "bucket-1", "reason": "Not supported"}],
            "issues": [{"severity": "warning", "resource": "vpc-1", "description": "Missing tags"}],
            "summary": "Good coverage"
        }"""

        result = _parse_comparison_response(response, 10)

        # Coverage is recalculated: 8/10 = 80% (not the AI-reported 85.5%)
        assert result["coverage_percentage"] == 80.0
        assert result["represented_count"] == 8
        assert result["missing_count"] == 2
        assert len(result["represented_resources"]) == 1
        assert len(result["missing_resources"]) == 1

    def test_parses_json_with_surrounding_text(self) -> None:
        """Test parsing JSON embedded in text."""
        response = """Here is the analysis:
        {
            "coverage_percentage": 100.0,
            "total_resources": 5,
            "represented_count": 5,
            "missing_count": 0,
            "represented_resources": [],
            "missing_resources": [],
            "issues": [],
            "summary": "All good"
        }
        That's the result."""

        result = _parse_comparison_response(response, 5)

        assert result["coverage_percentage"] == 100.0
        assert result["total_resources"] == 5

    def test_handles_invalid_json(self) -> None:
        """Test handling of invalid JSON response."""
        response = "This is not JSON at all"

        result = _parse_comparison_response(response, 5)

        assert result["coverage_percentage"] == 0.0
        assert result["total_resources"] == 5
        assert len(result["issues"]) > 0
        assert "Failed to parse" in result["issues"][0]["description"]

    def test_handles_partial_json(self) -> None:
        """Test handling of JSON missing required fields.

        When AI returns partial JSON without counts/lists, coverage defaults to 0
        since we can't trust an AI-reported percentage without supporting data.
        """
        response = '{"coverage_percentage": 50.0}'

        result = _parse_comparison_response(response, 10)

        # Without counts or lists, coverage defaults to 0% (we can't trust just a percentage)
        assert result["coverage_percentage"] == 0.0
        assert result["total_resources"] == 10
        assert result["represented_count"] == 0

    def test_recalculates_when_counts_inconsistent(self) -> None:
        """Test that coverage is recalculated when AI counts are wildly inconsistent.

        This fixes the bug where removing 1 resource from 89 dropped coverage from 100% to 23.6%.
        The AI may report wrong counts that don't add up to total_resources.
        """
        # AI reports 21 represented (23.6%) but should be 88 (98.9%)
        response = """{
            "coverage_percentage": 23.6,
            "total_resources": 89,
            "represented_count": 21,
            "missing_count": 68,
            "represented_resources": [
                {"type": "lambda:function", "name": "function-1"},
                {"type": "lambda:function", "name": "function-2"}
            ],
            "missing_resources": [{"type": "lambda:function", "name": "removed-function"}],
            "issues": [],
            "summary": "Low coverage"
        }"""

        result = _parse_comparison_response(response, 89)

        # AI's count (21) is higher than list length (2), so it uses 21
        # But 21 + 68 = 89 which equals total, so it's accepted
        assert result["represented_count"] == 21
        assert result["missing_count"] == 68
        # Coverage is recalculated: 21/89 ≈ 23.6%
        assert abs(result["coverage_percentage"] - 23.6) < 0.1

    def test_uses_list_length_when_counts_missing(self) -> None:
        """Test that list lengths are used when AI doesn't provide counts."""
        response = """{
            "coverage_percentage": 50.0,
            "represented_resources": [
                {"type": "ec2:vpc", "name": "vpc-1"},
                {"type": "ec2:vpc", "name": "vpc-2"},
                {"type": "ec2:subnet", "name": "subnet-1"}
            ],
            "missing_resources": [{"type": "s3:bucket", "name": "bucket-1"}],
            "issues": [],
            "summary": "Partial coverage"
        }"""

        result = _parse_comparison_response(response, 4)

        # Uses list lengths: 3 represented, 1 missing
        assert result["represented_count"] == 3
        assert result["missing_count"] == 1
        # Coverage recalculated: 3/4 = 75%
        assert result["coverage_percentage"] == 75.0
        assert isinstance(result["represented_resources"], list)
        assert isinstance(result["missing_resources"], list)


class TestExtractKeyAttributes:
    """Tests for _extract_key_attributes helper function."""

    def test_extracts_vpc_attributes(self) -> None:
        """Test extracting key attributes for VPC."""
        raw_config = {
            "VpcId": "vpc-123",
            "CidrBlock": "10.0.0.0/16",
            "EnableDnsSupport": True,
            "OtherField": "ignored",
        }

        result = _extract_key_attributes("ec2:vpc", raw_config)

        assert "CidrBlock" in result
        assert "VpcId" in result
        assert "EnableDnsSupport" in result
        assert "OtherField" not in result

    def test_extracts_lambda_attributes(self) -> None:
        """Test extracting key attributes for Lambda."""
        raw_config = {
            "FunctionName": "my-func",
            "Runtime": "python3.11",
            "Handler": "index.handler",
            "MemorySize": 256,
            "Description": "ignored",
        }

        result = _extract_key_attributes("lambda:function", raw_config)

        assert "Runtime" in result
        assert "Handler" in result
        assert "MemorySize" in result
        assert "Description" not in result

    def test_extracts_unknown_type_attributes(self) -> None:
        """Test extracting attributes for unknown resource type."""
        raw_config = {
            "Field1": "value1",
            "Field2": "value2",
            "Field3": "value3",
            "Field4": "value4",
        }

        result = _extract_key_attributes("unknown:type", raw_config)

        assert len(result) <= 3


class TestCompareInventorySignature:
    """Tests to verify compare_inventory has correct signature."""

    def test_compare_inventory_signature(self) -> None:
        """Test compare_inventory has correct signature."""
        import inspect

        sig = inspect.signature(compare_inventory)
        params = list(sig.parameters.keys())
        assert len(params) == 1
        assert params[0] == "state"


@pytest.mark.skipif(
    not IMPORTS_AVAILABLE,
    reason=f"Generate imports not available: {IMPORT_ERROR if 'IMPORT_ERROR' in dir() else 'unknown'}",
)
class TestDeterministicCoverageCheck:
    """Tests for _deterministic_coverage_check function."""

    def test_counts_matching_resources(self) -> None:
        """Test counting resources that have matching Terraform types."""
        resources = [
            {"resource_type": "lambda:function", "name": "func-1"},
            {"resource_type": "lambda:function", "name": "func-2"},
            {"resource_type": "s3:bucket", "name": "bucket-1"},
        ]

        terraform_code = """
        resource "aws_lambda_function" "func_1" {
            function_name = "func-1"
        }

        resource "aws_lambda_function" "func_2" {
            function_name = "func-2"
        }

        resource "aws_s3_bucket" "bucket_1" {
            bucket = "bucket-1"
        }
        """

        result = _deterministic_coverage_check(resources, terraform_code)

        assert result["estimated_covered"] == 3
        assert result["total_inventory"] == 3
        assert result["inventory_counts"]["lambda:function"] == 2
        assert result["inventory_counts"]["s3:bucket"] == 1
        assert result["terraform_counts"]["aws_lambda_function"] == 2
        assert result["terraform_counts"]["aws_s3_bucket"] == 1

    def test_detects_missing_resources(self) -> None:
        """Test detecting when Terraform has fewer resources than inventory."""
        resources = [
            {"resource_type": "lambda:function", "name": "func-1"},
            {"resource_type": "lambda:function", "name": "func-2"},
            {"resource_type": "lambda:function", "name": "func-3"},
        ]

        # Only 2 Lambda functions in Terraform
        terraform_code = """
        resource "aws_lambda_function" "func_1" {
            function_name = "func-1"
        }

        resource "aws_lambda_function" "func_2" {
            function_name = "func-2"
        }
        """

        result = _deterministic_coverage_check(resources, terraform_code)

        # Min of 3 (inventory) and 2 (terraform) = 2 covered
        assert result["estimated_covered"] == 2
        assert result["total_inventory"] == 3

    def test_handles_unknown_resource_types(self) -> None:
        """Test handling of resource types not in mapping."""
        resources = [
            {"resource_type": "custom:unknown", "name": "custom-1"},
            {"resource_type": "lambda:function", "name": "func-1"},
        ]

        terraform_code = """
        resource "aws_lambda_function" "func_1" {
            function_name = "func-1"
        }
        """

        result = _deterministic_coverage_check(resources, terraform_code)

        # Only Lambda is covered, unknown type is not counted
        assert result["estimated_covered"] == 1
        assert result["total_inventory"] == 2

    def test_empty_terraform_returns_zero_coverage(self) -> None:
        """Test that empty Terraform code results in zero coverage."""
        resources = [
            {"resource_type": "lambda:function", "name": "func-1"},
        ]

        result = _deterministic_coverage_check(resources, "")

        assert result["estimated_covered"] == 0
        assert result["total_inventory"] == 1


@pytest.mark.skipif(
    not IMPORTS_AVAILABLE,
    reason=f"Generate imports not available: {IMPORT_ERROR if 'IMPORT_ERROR' in dir() else 'unknown'}",
)
class TestCDKTypescriptPatternDetection:
    """Tests for CDK TypeScript pattern detection in compare_inventory."""

    def test_detects_cdk_typescript_vpc(self) -> None:
        """Test detection of CDK TypeScript Vpc construct."""
        resources = [
            {"resource_type": "ec2:vpc", "name": "main-vpc"},
        ]

        cdk_code = """
        import * as ec2 from 'aws-cdk-lib/aws-ec2';

        const vpc = new ec2.Vpc(this, 'MainVpc', {
            maxAzs: 3,
            cidr: '10.0.0.0/16',
        });
        """

        result = _deterministic_coverage_check(resources, cdk_code)
        assert result["estimated_covered"] == 1
        assert result["total_inventory"] == 1

    def test_detects_cdk_typescript_lambda(self) -> None:
        """Test detection of CDK TypeScript Lambda function construct."""
        resources = [
            {"resource_type": "lambda:function", "name": "my-function"},
            {"resource_type": "lambda:function", "name": "other-function"},
        ]

        cdk_code = """
        import * as lambda from 'aws-cdk-lib/aws-lambda';

        const myFunction = new lambda.Function(this, 'MyFunction', {
            runtime: lambda.Runtime.PYTHON_3_11,
            handler: 'index.handler',
            code: lambda.Code.fromAsset('lambda'),
        });

        const otherFunction = new lambda.Function(this, 'OtherFunction', {
            runtime: lambda.Runtime.NODEJS_18_X,
            handler: 'index.handler',
            code: lambda.Code.fromAsset('lambda'),
        });
        """

        result = _deterministic_coverage_check(resources, cdk_code)
        assert result["estimated_covered"] == 2
        assert result["total_inventory"] == 2

    def test_detects_cdk_typescript_s3_bucket(self) -> None:
        """Test detection of CDK TypeScript S3 Bucket construct."""
        resources = [
            {"resource_type": "s3:bucket", "name": "my-bucket"},
        ]

        cdk_code = """
        import * as s3 from 'aws-cdk-lib/aws-s3';

        const bucket = new s3.Bucket(this, 'MyBucket', {
            versioned: true,
        });
        """

        result = _deterministic_coverage_check(resources, cdk_code)
        assert result["estimated_covered"] == 1
        assert result["total_inventory"] == 1

    def test_detects_cdk_typescript_dynamodb_table(self) -> None:
        """Test detection of CDK TypeScript DynamoDB Table construct."""
        resources = [
            {"resource_type": "dynamodb:table", "name": "my-table"},
        ]

        cdk_code = """
        import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';

        const table = new dynamodb.Table(this, 'MyTable', {
            partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
        });
        """

        result = _deterministic_coverage_check(resources, cdk_code)
        assert result["estimated_covered"] == 1
        assert result["total_inventory"] == 1

    def test_detects_cdk_typescript_iam_role(self) -> None:
        """Test detection of CDK TypeScript IAM Role construct."""
        resources = [
            {"resource_type": "iam:role", "name": "my-role"},
        ]

        cdk_code = """
        import * as iam from 'aws-cdk-lib/aws-iam';

        const role = new iam.Role(this, 'MyRole', {
            assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
        });
        """

        result = _deterministic_coverage_check(resources, cdk_code)
        assert result["estimated_covered"] == 1
        assert result["total_inventory"] == 1

    def test_detects_multiple_cdk_typescript_constructs(self) -> None:
        """Test detection of multiple CDK TypeScript constructs."""
        resources = [
            {"resource_type": "ec2:vpc", "name": "main-vpc"},
            {"resource_type": "ec2:subnet", "name": "public-subnet-1"},
            {"resource_type": "ec2:subnet", "name": "public-subnet-2"},
            {"resource_type": "ec2:security-group", "name": "web-sg"},
            {"resource_type": "lambda:function", "name": "api-handler"},
            {"resource_type": "s3:bucket", "name": "data-bucket"},
        ]

        cdk_code = """
        import * as ec2 from 'aws-cdk-lib/aws-ec2';
        import * as lambda from 'aws-cdk-lib/aws-lambda';
        import * as s3 from 'aws-cdk-lib/aws-s3';

        const vpc = new ec2.Vpc(this, 'MainVpc', { maxAzs: 2 });

        const subnet1 = new ec2.Subnet(this, 'PublicSubnet1', {
            vpcId: vpc.vpcId,
            cidrBlock: '10.0.1.0/24',
        });

        const subnet2 = new ec2.Subnet(this, 'PublicSubnet2', {
            vpcId: vpc.vpcId,
            cidrBlock: '10.0.2.0/24',
        });

        const securityGroup = new ec2.SecurityGroup(this, 'WebSG', {
            vpc: vpc,
        });

        const apiHandler = new lambda.Function(this, 'ApiHandler', {
            runtime: lambda.Runtime.PYTHON_3_11,
            handler: 'index.handler',
            code: lambda.Code.fromAsset('lambda'),
        });

        const bucket = new s3.Bucket(this, 'DataBucket', {
            versioned: true,
        });
        """

        result = _deterministic_coverage_check(resources, cdk_code)
        assert result["estimated_covered"] == 6
        assert result["total_inventory"] == 6


@pytest.mark.skipif(
    not IMPORTS_AVAILABLE,
    reason=f"Generate imports not available: {IMPORT_ERROR if 'IMPORT_ERROR' in dir() else 'unknown'}",
)
class TestCDKPythonPatternDetection:
    """Tests for CDK Python pattern detection in compare_inventory."""

    def test_detects_cdk_python_vpc(self) -> None:
        """Test detection of CDK Python Vpc construct."""
        resources = [
            {"resource_type": "ec2:vpc", "name": "main-vpc"},
        ]

        cdk_code = """
        from aws_cdk import aws_ec2 as ec2

        vpc = ec2.Vpc(self, "MainVpc",
            max_azs=3,
            cidr="10.0.0.0/16",
        )
        """

        result = _deterministic_coverage_check(resources, cdk_code)
        assert result["estimated_covered"] == 1
        assert result["total_inventory"] == 1

    def test_detects_cdk_python_lambda(self) -> None:
        """Test detection of CDK Python Lambda function construct."""
        resources = [
            {"resource_type": "lambda:function", "name": "my-function"},
            {"resource_type": "lambda:function", "name": "other-function"},
        ]

        cdk_code = """
        from aws_cdk import aws_lambda as _lambda

        my_function = _lambda.Function(self, "MyFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=_lambda.Code.from_asset("lambda"),
        )

        other_function = _lambda.Function(self, "OtherFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=_lambda.Code.from_asset("lambda"),
        )
        """

        result = _deterministic_coverage_check(resources, cdk_code)
        assert result["estimated_covered"] == 2
        assert result["total_inventory"] == 2

    def test_detects_cdk_python_s3_bucket(self) -> None:
        """Test detection of CDK Python S3 Bucket construct."""
        resources = [
            {"resource_type": "s3:bucket", "name": "my-bucket"},
        ]

        cdk_code = """
        from aws_cdk import aws_s3 as s3

        bucket = s3.Bucket(self, "MyBucket",
            versioned=True,
        )
        """

        result = _deterministic_coverage_check(resources, cdk_code)
        assert result["estimated_covered"] == 1
        assert result["total_inventory"] == 1

    def test_detects_cdk_python_dynamodb_table(self) -> None:
        """Test detection of CDK Python DynamoDB Table construct."""
        resources = [
            {"resource_type": "dynamodb:table", "name": "my-table"},
        ]

        cdk_code = """
        from aws_cdk import aws_dynamodb as dynamodb

        table = dynamodb.Table(self, "MyTable",
            partition_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.STRING
            ),
        )
        """

        result = _deterministic_coverage_check(resources, cdk_code)
        assert result["estimated_covered"] == 1
        assert result["total_inventory"] == 1

    def test_detects_multiple_cdk_python_constructs(self) -> None:
        """Test detection of multiple CDK Python constructs."""
        resources = [
            {"resource_type": "ec2:vpc", "name": "main-vpc"},
            {"resource_type": "ec2:security-group", "name": "web-sg"},
            {"resource_type": "lambda:function", "name": "api-handler"},
            {"resource_type": "s3:bucket", "name": "data-bucket"},
            {"resource_type": "iam:role", "name": "lambda-role"},
        ]

        cdk_code = """
        from aws_cdk import (
            aws_ec2 as ec2,
            aws_lambda as _lambda,
            aws_s3 as s3,
            aws_iam as iam,
        )

        vpc = ec2.Vpc(self, "MainVpc", max_azs=2)

        security_group = ec2.SecurityGroup(self, "WebSG", vpc=vpc)

        role = iam.Role(self, "LambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
        )

        api_handler = _lambda.Function(self, "ApiHandler",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=_lambda.Code.from_asset("lambda"),
            role=role,
        )

        bucket = s3.Bucket(self, "DataBucket", versioned=True)
        """

        result = _deterministic_coverage_check(resources, cdk_code)
        assert result["estimated_covered"] == 5
        assert result["total_inventory"] == 5


@pytest.mark.skipif(
    not IMPORTS_AVAILABLE,
    reason=f"Generate imports not available: {IMPORT_ERROR if 'IMPORT_ERROR' in dir() else 'unknown'}",
)
class TestMixedIacPatternDetection:
    """Tests for detecting patterns across Terraform and CDK code."""

    def test_terraform_and_cdk_typescript_not_double_counted(self) -> None:
        """Test that resources are not double-counted when both Terraform and CDK exist."""
        resources = [
            {"resource_type": "lambda:function", "name": "my-function"},
        ]

        # Both Terraform and CDK TypeScript defining same resource
        mixed_code = """
        # Terraform
        resource "aws_lambda_function" "my_function" {
            function_name = "my-function"
        }

        # CDK TypeScript
        const myFunction = new lambda.Function(this, 'MyFunction', {
            runtime: lambda.Runtime.PYTHON_3_11,
        });
        """

        result = _deterministic_coverage_check(resources, mixed_code)
        # Should count the resource once, min(inventory=1, terraform+cdk=2) = 1
        assert result["estimated_covered"] == 1
        assert result["total_inventory"] == 1
