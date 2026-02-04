"""Integration tests for CDK compare/coverage workflow.

These tests verify that the compare_inventory node correctly detects
CDK TypeScript and CDK Python constructs in generated code.

Tests are skipped if langgraph is not installed.
"""

from __future__ import annotations

import os
import tempfile
from typing import List
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


@pytest.fixture
def sample_resources() -> List[TrackedResource]:
    """Create sample resources for compare testing."""
    return [
        TrackedResource(
            arn="arn:aws:ec2:us-east-1:123456789012:vpc/vpc-abc123",
            resource_type="ec2:vpc",
            name="main-vpc",
            region="us-east-1",
        ),
        TrackedResource(
            arn="arn:aws:ec2:us-east-1:123456789012:subnet/subnet-def456",
            resource_type="ec2:subnet",
            name="public-subnet",
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
        TrackedResource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:my-func",
            resource_type="lambda:function",
            name="my-func",
            region="us-east-1",
        ),
        TrackedResource(
            arn="arn:aws:iam::123456789012:role/my-role",
            resource_type="iam:role",
            name="my-role",
            region="global",
        ),
    ]


@pytest.fixture
def cdk_typescript_code() -> str:
    """Sample CDK TypeScript code for comparison testing."""
    return """
import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export class NetworkStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // VPC
    const mainVpc = new ec2.Vpc(this, 'mainVpc', {
      ipAddresses: ec2.IpAddresses.cidr('10.0.0.0/16'),
    });

    // Subnet
    const publicSubnet = new ec2.Subnet(this, 'publicSubnet', {
      vpcId: mainVpc.vpcId,
      cidrBlock: '10.0.1.0/24',
      availabilityZone: 'us-east-1a',
    });

    // Security Group
    const webSg = new ec2.SecurityGroup(this, 'webSg', {
      vpc: mainVpc,
      description: 'Web security group',
    });
  }
}

export class StorageStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // S3 Bucket
    const myBucket = new s3.Bucket(this, 'myBucket', {
      bucketName: 'my-bucket',
    });
  }
}

export class ComputeStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Lambda Function
    const myFunc = new lambda.Function(this, 'myFunc', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'index.handler',
      code: lambda.Code.fromInline('def handler(e,c): pass'),
    });

    // IAM Role
    const myRole = new iam.Role(this, 'myRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
    });
  }
}
"""


@pytest.fixture
def cdk_python_code() -> str:
    """Sample CDK Python code for comparison testing."""
    return """
from aws_cdk import Stack, Tags
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_iam as iam
from constructs import Construct


class NetworkStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # VPC
        self.main_vpc = ec2.Vpc(
            self, "main_vpc",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16")
        )

        # Subnet
        self.public_subnet = ec2.Subnet(
            self, "public_subnet",
            vpc_id=self.main_vpc.vpc_id,
            cidr_block="10.0.1.0/24",
            availability_zone="us-east-1a"
        )

        # Security Group
        self.web_sg = ec2.SecurityGroup(
            self, "web_sg",
            vpc=self.main_vpc,
            description="Web security group"
        )


class StorageStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # S3 Bucket
        self.my_bucket = s3.Bucket(
            self, "my_bucket",
            bucket_name="my-bucket"
        )


class ComputeStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        # Lambda Function
        self.my_func = lambda_.Function(
            self, "my_func",
            runtime=lambda_.Runtime.PYTHON_3_11,
            handler="index.handler",
            code=lambda_.Code.from_inline("def handler(e,c): pass")
        )

        # IAM Role
        self.my_role = iam.Role(
            self, "my_role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )
"""


class TestCDKTypescriptCoverageDetection:
    """Tests for CDK TypeScript pattern detection in compare_inventory."""

    def test_deterministic_coverage_detects_vpc(
        self,
        sample_resources: List[TrackedResource],
        cdk_typescript_code: str,
    ) -> None:
        """Test that VPC constructs are detected in TypeScript code."""
        from src.generate.nodes.compare_inventory import _deterministic_coverage_check

        result = _deterministic_coverage_check(sample_resources, cdk_typescript_code)

        # Check CDK counts for VPC type
        assert result["cdk_counts"].get("ec2:vpc", 0) > 0

    def test_deterministic_coverage_detects_security_group(
        self,
        sample_resources: List[TrackedResource],
        cdk_typescript_code: str,
    ) -> None:
        """Test that SecurityGroup constructs are detected in TypeScript code."""
        from src.generate.nodes.compare_inventory import _deterministic_coverage_check

        result = _deterministic_coverage_check(sample_resources, cdk_typescript_code)

        assert result["cdk_counts"].get("ec2:security-group", 0) > 0

    def test_deterministic_coverage_detects_s3_bucket(
        self,
        sample_resources: List[TrackedResource],
        cdk_typescript_code: str,
    ) -> None:
        """Test that S3 Bucket constructs are detected in TypeScript code."""
        from src.generate.nodes.compare_inventory import _deterministic_coverage_check

        result = _deterministic_coverage_check(sample_resources, cdk_typescript_code)

        assert result["cdk_counts"].get("s3:bucket", 0) > 0

    def test_deterministic_coverage_detects_lambda_function(
        self,
        sample_resources: List[TrackedResource],
        cdk_typescript_code: str,
    ) -> None:
        """Test that Lambda Function constructs are detected in TypeScript code."""
        from src.generate.nodes.compare_inventory import _deterministic_coverage_check

        result = _deterministic_coverage_check(sample_resources, cdk_typescript_code)

        assert result["cdk_counts"].get("lambda:function", 0) > 0

    def test_deterministic_coverage_detects_iam_role(
        self,
        sample_resources: List[TrackedResource],
        cdk_typescript_code: str,
    ) -> None:
        """Test that IAM Role constructs are detected in TypeScript code."""
        from src.generate.nodes.compare_inventory import _deterministic_coverage_check

        result = _deterministic_coverage_check(sample_resources, cdk_typescript_code)

        assert result["cdk_counts"].get("iam:role", 0) > 0

    def test_deterministic_coverage_calculates_estimated_covered(
        self,
        sample_resources: List[TrackedResource],
        cdk_typescript_code: str,
    ) -> None:
        """Test that estimated covered resources is calculated correctly."""
        from src.generate.nodes.compare_inventory import _deterministic_coverage_check

        result = _deterministic_coverage_check(sample_resources, cdk_typescript_code)

        assert "estimated_covered" in result
        assert result["estimated_covered"] > 0
        assert result["estimated_covered"] <= result["total_inventory"]


class TestCDKPythonCoverageDetection:
    """Tests for CDK Python pattern detection in compare_inventory."""

    def test_deterministic_coverage_detects_vpc_python(
        self,
        sample_resources: List[TrackedResource],
        cdk_python_code: str,
    ) -> None:
        """Test that VPC constructs are detected in Python code."""
        from src.generate.nodes.compare_inventory import _deterministic_coverage_check

        result = _deterministic_coverage_check(sample_resources, cdk_python_code)

        assert result["cdk_counts"].get("ec2:vpc", 0) > 0

    def test_deterministic_coverage_detects_security_group_python(
        self,
        sample_resources: List[TrackedResource],
        cdk_python_code: str,
    ) -> None:
        """Test that SecurityGroup constructs are detected in Python code."""
        from src.generate.nodes.compare_inventory import _deterministic_coverage_check

        result = _deterministic_coverage_check(sample_resources, cdk_python_code)

        assert result["cdk_counts"].get("ec2:security-group", 0) > 0

    def test_deterministic_coverage_detects_s3_bucket_python(
        self,
        sample_resources: List[TrackedResource],
        cdk_python_code: str,
    ) -> None:
        """Test that S3 Bucket constructs are detected in Python code."""
        from src.generate.nodes.compare_inventory import _deterministic_coverage_check

        result = _deterministic_coverage_check(sample_resources, cdk_python_code)

        assert result["cdk_counts"].get("s3:bucket", 0) > 0

    def test_deterministic_coverage_detects_lambda_function_python(
        self,
        sample_resources: List[TrackedResource],
        cdk_python_code: str,
    ) -> None:
        """Test that Lambda Function constructs are detected in Python code."""
        from src.generate.nodes.compare_inventory import _deterministic_coverage_check

        result = _deterministic_coverage_check(sample_resources, cdk_python_code)

        assert result["cdk_counts"].get("lambda:function", 0) > 0


class TestMixedIaCCoverageDetection:
    """Tests for mixed IaC code detection (Terraform + CDK)."""

    @pytest.fixture
    def terraform_code(self) -> str:
        """Sample Terraform code."""
        return """
resource "aws_vpc" "main" {
  cidr_block = "10.0.0.0/16"
}

resource "aws_security_group" "web" {
  name        = "web-sg"
  vpc_id      = aws_vpc.main.id
}
"""

    def test_coverage_with_terraform_code(
        self,
        sample_resources: List[TrackedResource],
        terraform_code: str,
    ) -> None:
        """Test that Terraform resources are still detected."""
        from src.generate.nodes.compare_inventory import _deterministic_coverage_check

        result = _deterministic_coverage_check(sample_resources, terraform_code)

        # Check Terraform counts for VPC
        assert result["terraform_counts"].get("aws_vpc", 0) > 0

    def test_coverage_with_mixed_code(
        self,
        sample_resources: List[TrackedResource],
        cdk_typescript_code: str,
        terraform_code: str,
    ) -> None:
        """Test coverage detection with both Terraform and CDK code."""
        from src.generate.nodes.compare_inventory import _deterministic_coverage_check

        mixed_code = cdk_typescript_code + "\n\n" + terraform_code
        result = _deterministic_coverage_check(sample_resources, mixed_code)

        # Should detect resources from both formats
        assert result["estimated_covered"] > 0


class TestCompareInventoryNode:
    """Integration tests for the compare_inventory node."""

    @patch("boto3.client")
    def test_compare_inventory_with_cdk_typescript(
        self,
        mock_boto_client: MagicMock,
        sample_resources: List[TrackedResource],
        cdk_typescript_code: str,
    ) -> None:
        """Test compare_inventory node with CDK TypeScript code."""
        from src.generate.nodes.compare_inventory import compare_inventory

        # Mock Bedrock client
        mock_bedrock_client = MagicMock()
        mock_bedrock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [
                        {
                            "text": """{
                            "coverage_percentage": 100.0,
                            "total_resources": 6,
                            "represented_count": 6,
                            "missing_count": 0,
                            "represented_resources": [],
                            "missing_resources": [],
                            "issues": [],
                            "summary": "All resources covered"
                        }"""
                        }
                    ]
                }
            }
        }
        mock_boto_client.return_value = mock_bedrock_client

        state: GenerationState = {
            "resources": sample_resources,
            "generated_code": {"network": cdk_typescript_code},
            "output_format": "cdk-typescript",
        }

        result = compare_inventory(state)

        assert "comparison_result" in result
        comparison = result["comparison_result"]
        assert "coverage_percentage" in comparison

    @patch("boto3.client")
    def test_compare_inventory_with_cdk_python(
        self,
        mock_boto_client: MagicMock,
        sample_resources: List[TrackedResource],
        cdk_python_code: str,
    ) -> None:
        """Test compare_inventory node with CDK Python code."""
        from src.generate.nodes.compare_inventory import compare_inventory

        # Mock Bedrock client
        mock_bedrock_client = MagicMock()
        mock_bedrock_client.converse.return_value = {
            "output": {
                "message": {
                    "content": [
                        {
                            "text": """{
                            "coverage_percentage": 100.0,
                            "total_resources": 6,
                            "represented_count": 6,
                            "missing_count": 0,
                            "represented_resources": [],
                            "missing_resources": [],
                            "issues": [],
                            "summary": "All resources covered"
                        }"""
                        }
                    ]
                }
            }
        }
        mock_boto_client.return_value = mock_bedrock_client

        state: GenerationState = {
            "resources": sample_resources,
            "generated_code": {"network": cdk_python_code},
            "output_format": "cdk-python",
        }

        result = compare_inventory(state)

        assert "comparison_result" in result
        comparison = result["comparison_result"]
        assert "coverage_percentage" in comparison

    def test_compare_inventory_with_no_code(
        self,
        sample_resources: List[TrackedResource],
    ) -> None:
        """Test compare_inventory handles empty generated code."""
        from src.generate.nodes.compare_inventory import compare_inventory

        state: GenerationState = {
            "resources": sample_resources,
            "generated_code": {},
            "output_format": "cdk-typescript",
        }

        result = compare_inventory(state)

        assert "comparison_result" in result
        comparison = result["comparison_result"]
        # With no code, coverage should be 0%
        assert comparison["coverage_percentage"] == 0

    def test_compare_inventory_with_no_resources(self) -> None:
        """Test compare_inventory handles empty resources."""
        from src.generate.nodes.compare_inventory import compare_inventory

        state: GenerationState = {
            "resources": [],
            "generated_code": {"network": "some code"},
            "output_format": "cdk-typescript",
        }

        result = compare_inventory(state)

        assert "comparison_result" in result
        comparison = result["comparison_result"]
        # With no resources, coverage is reported (implementation detail may vary)
        assert "coverage_percentage" in comparison


class TestCDKProjectTypeDetection:
    """Tests for CDK project type detection in compare.py."""

    def test_detect_cdk_typescript_project(self) -> None:
        """Test detection of CDK TypeScript project structure."""
        from src.generate.compare import _read_iac_files

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create CDK TypeScript project structure
            os.makedirs(os.path.join(tmpdir, "lib"))
            with open(os.path.join(tmpdir, "cdk.json"), "w") as f:
                f.write('{"app": "npx ts-node bin/app.ts"}')
            with open(os.path.join(tmpdir, "package.json"), "w") as f:
                f.write('{"name": "test"}')
            with open(os.path.join(tmpdir, "lib", "network_stack.ts"), "w") as f:
                f.write("export class NetworkStack {}")

            files = _read_iac_files(tmpdir)

            # Should read TypeScript files
            ts_files = [f for f in files if f.endswith(".ts")]
            assert len(ts_files) > 0

    def test_detect_cdk_python_project(self) -> None:
        """Test detection of CDK Python project structure."""
        from src.generate.compare import _read_iac_files

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create CDK Python project structure
            os.makedirs(os.path.join(tmpdir, "stacks"))
            with open(os.path.join(tmpdir, "cdk.json"), "w") as f:
                f.write('{"app": "python app.py"}')
            with open(os.path.join(tmpdir, "requirements.txt"), "w") as f:
                f.write("aws-cdk-lib")
            with open(os.path.join(tmpdir, "stacks", "network_stack.py"), "w") as f:
                f.write("class NetworkStack: pass")

            files = _read_iac_files(tmpdir)

            # Should read Python files
            py_files = [f for f in files if f.endswith(".py")]
            assert len(py_files) > 0

    def test_detect_terraform_project(self) -> None:
        """Test detection of Terraform project structure."""
        from src.generate.compare import _read_iac_files

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create Terraform project structure
            with open(os.path.join(tmpdir, "main.tf"), "w") as f:
                f.write('resource "aws_vpc" "main" {}')
            with open(os.path.join(tmpdir, "variables.tf"), "w") as f:
                f.write('variable "region" {}')

            files = _read_iac_files(tmpdir)

            # Should read Terraform files
            tf_files = [f for f in files if f.endswith(".tf")]
            assert len(tf_files) > 0
