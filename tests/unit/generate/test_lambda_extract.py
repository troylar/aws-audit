"""Unit tests for LambdaCode class."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from src.models.generation import LambdaCode, TrackedResource


class TestLambdaCode:
    """Tests for LambdaCode class."""

    @pytest.fixture
    def sample_inline_lambda_resource(self) -> TrackedResource:
        """Create a TrackedResource for an inline Lambda function."""
        zip_content = b"PK\x03\x04fake-zip-content"
        return TrackedResource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:my-function",
            resource_type="lambda:function",
            name="my-function",
            region="us-east-1",
            raw_config={
                "FunctionName": "my-function",
                "Runtime": "python3.11",
                "Handler": "index.handler",
                "CodeSha256": "abc123sha256hash",
                "CodeSize": 1024,
                "Code": {
                    "ZipFile": base64.b64encode(zip_content).decode("utf-8"),
                },
            },
        )

    @pytest.fixture
    def sample_s3_lambda_resource(self) -> TrackedResource:
        """Create a TrackedResource for an S3-based Lambda function."""
        return TrackedResource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:s3-function",
            resource_type="lambda:function",
            name="s3-function",
            region="us-east-1",
            raw_config={
                "FunctionName": "s3-function",
                "Runtime": "nodejs18.x",
                "Handler": "app.handler",
                "CodeSha256": "def456sha256hash",
                "CodeSize": 2048,
                "Code": {
                    "S3Bucket": "my-deployment-bucket",
                    "S3Key": "lambda/s3-function.zip",
                    "S3ObjectVersion": "v1.2.3",
                },
            },
        )

    @pytest.fixture
    def sample_image_lambda_resource(self) -> TrackedResource:
        """Create a TrackedResource for a container image Lambda function."""
        return TrackedResource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:image-function",
            resource_type="lambda:function",
            name="image-function",
            region="us-east-1",
            raw_config={
                "FunctionName": "image-function",
                "PackageType": "Image",
                "Code": {
                    "ImageUri": "123456789012.dkr.ecr.us-east-1.amazonaws.com/my-repo:latest",
                },
            },
        )

    @pytest.fixture
    def sample_minimal_lambda_resource(self) -> TrackedResource:
        """Create a TrackedResource with minimal config."""
        return TrackedResource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:minimal-function",
            resource_type="lambda:function",
            name="minimal-function",
            region="us-east-1",
            raw_config={
                "FunctionName": "minimal-function",
                "Code": {},
            },
        )

    def test_from_resource_inline_code(self, sample_inline_lambda_resource: TrackedResource) -> None:
        """Test from_resource creates correct LambdaCode for inline code."""
        lambda_code = LambdaCode.from_resource(sample_inline_lambda_resource)

        assert lambda_code.function_name == "my-function"
        assert lambda_code.runtime == "python3.11"
        assert lambda_code.handler == "index.handler"
        assert lambda_code.storage_type == "inline"
        assert lambda_code.code_stored is True
        assert lambda_code.code_base64 is not None
        assert lambda_code.code_sha256 == "abc123sha256hash"
        assert lambda_code.code_size_bytes == 1024

    def test_from_resource_s3_code(self, sample_s3_lambda_resource: TrackedResource) -> None:
        """Test from_resource creates correct LambdaCode for S3 code."""
        lambda_code = LambdaCode.from_resource(sample_s3_lambda_resource)

        assert lambda_code.function_name == "s3-function"
        assert lambda_code.runtime == "nodejs18.x"
        assert lambda_code.handler == "app.handler"
        assert lambda_code.storage_type == "s3"
        assert lambda_code.code_stored is False
        assert lambda_code.code_base64 is None
        assert lambda_code.s3_bucket == "my-deployment-bucket"
        assert lambda_code.s3_key == "lambda/s3-function.zip"
        assert lambda_code.s3_version == "v1.2.3"

    def test_from_resource_image_code(self, sample_image_lambda_resource: TrackedResource) -> None:
        """Test from_resource creates correct LambdaCode for container image."""
        lambda_code = LambdaCode.from_resource(sample_image_lambda_resource)

        assert lambda_code.function_name == "image-function"
        assert lambda_code.storage_type == "image"
        assert lambda_code.code_stored is False
        assert lambda_code.image_uri == "123456789012.dkr.ecr.us-east-1.amazonaws.com/my-repo:latest"

    def test_from_resource_unknown_storage_type(self, sample_minimal_lambda_resource: TrackedResource) -> None:
        """Test from_resource handles unknown storage type."""
        lambda_code = LambdaCode.from_resource(sample_minimal_lambda_resource)

        assert lambda_code.function_name == "minimal-function"
        assert lambda_code.storage_type == "unknown"
        assert lambda_code.code_stored is False

    def test_from_resource_missing_code_config(self) -> None:
        """Test from_resource handles missing Code config."""
        resource = TrackedResource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:no-code",
            resource_type="lambda:function",
            name="no-code",
            region="us-east-1",
            raw_config={
                "FunctionName": "no-code",
                "Runtime": "python3.11",
            },
        )
        lambda_code = LambdaCode.from_resource(resource)

        assert lambda_code.function_name == "no-code"
        assert lambda_code.storage_type == "unknown"
        assert lambda_code.code_stored is False

    def test_from_resource_empty_raw_config(self) -> None:
        """Test from_resource handles empty raw_config."""
        resource = TrackedResource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:empty",
            resource_type="lambda:function",
            name="empty",
            region="us-east-1",
            raw_config={},
        )
        lambda_code = LambdaCode.from_resource(resource)

        assert lambda_code.function_name == "empty"
        assert lambda_code.runtime == ""
        assert lambda_code.handler == ""
        assert lambda_code.storage_type == "unknown"

    def test_extract_to_writes_zip_file(self, sample_inline_lambda_resource: TrackedResource, tmp_path: Path) -> None:
        """Test extract_to writes base64 data to zip file."""
        lambda_code = LambdaCode.from_resource(sample_inline_lambda_resource)

        result = lambda_code.extract_to(tmp_path)

        assert result is not None
        zip_path = Path(result)
        assert zip_path.exists()
        assert zip_path.suffix == ".zip"
        assert zip_path.name == "my-function.zip"

        content = zip_path.read_bytes()
        expected = base64.b64decode(lambda_code.code_base64)
        assert content == expected

    def test_extract_to_creates_directory(self, sample_inline_lambda_resource: TrackedResource, tmp_path: Path) -> None:
        """Test extract_to creates output directory if needed."""
        lambda_code = LambdaCode.from_resource(sample_inline_lambda_resource)
        output_dir = tmp_path / "nested" / "lambda" / "code"

        assert not output_dir.exists()
        result = lambda_code.extract_to(output_dir)

        assert result is not None
        assert output_dir.exists()

    def test_extract_to_returns_none_when_no_code(
        self, sample_s3_lambda_resource: TrackedResource, tmp_path: Path
    ) -> None:
        """Test extract_to returns None when code_stored is False."""
        lambda_code = LambdaCode.from_resource(sample_s3_lambda_resource)

        result = lambda_code.extract_to(tmp_path)

        assert result is None

    def test_extract_to_returns_none_when_no_base64(self, tmp_path: Path) -> None:
        """Test extract_to returns None when code_base64 is None."""
        lambda_code = LambdaCode(
            function_name="test-function",
            runtime="python3.11",
            handler="index.handler",
            storage_type="inline",
            code_stored=True,
            code_base64=None,
        )

        result = lambda_code.extract_to(tmp_path)

        assert result is None

    def test_extract_to_sanitizes_filename(self, tmp_path: Path) -> None:
        """Test extract_to sanitizes function name for filename."""
        zip_content = b"PK\x03\x04fake-content"
        lambda_code = LambdaCode(
            function_name="my/function:with-special.chars",
            runtime="python3.11",
            handler="index.handler",
            storage_type="inline",
            code_stored=True,
            code_base64=base64.b64encode(zip_content).decode("utf-8"),
        )

        result = lambda_code.extract_to(tmp_path)

        assert result is not None
        zip_path = Path(result)
        assert "/" not in zip_path.name
        assert ":" not in zip_path.name
        assert zip_path.name == "my_function_with-special_chars.zip"

    def test_extract_to_sets_code_file_path(
        self, sample_inline_lambda_resource: TrackedResource, tmp_path: Path
    ) -> None:
        """Test extract_to sets the code_file_path attribute."""
        lambda_code = LambdaCode.from_resource(sample_inline_lambda_resource)

        assert lambda_code.code_file_path is None
        result = lambda_code.extract_to(tmp_path)

        assert lambda_code.code_file_path == result

    def test_extract_to_handles_invalid_base64(self, tmp_path: Path) -> None:
        """Test extract_to handles invalid base64 data gracefully."""
        lambda_code = LambdaCode(
            function_name="test-function",
            runtime="python3.11",
            handler="index.handler",
            storage_type="inline",
            code_stored=True,
            code_base64="not-valid-base64!!!",
        )

        result = lambda_code.extract_to(tmp_path)

        assert result is None

    def test_default_values(self) -> None:
        """Test LambdaCode default values."""
        lambda_code = LambdaCode(
            function_name="test",
            runtime="python3.11",
            handler="index.handler",
            storage_type="inline",
            code_stored=False,
        )

        assert lambda_code.code_base64 is None
        assert lambda_code.code_file_path is None
        assert lambda_code.s3_bucket is None
        assert lambda_code.s3_key is None
        assert lambda_code.s3_version is None
        assert lambda_code.image_uri is None
        assert lambda_code.code_sha256 is None
        assert lambda_code.code_size_bytes is None


class TestLambdaCodeIntegration:
    """Integration tests for LambdaCode with real file operations."""

    def test_full_extraction_workflow(self, tmp_path: Path) -> None:
        """Test complete workflow of creating and extracting Lambda code."""
        original_content = b"PK\x03\x04test-lambda-package-content-12345"
        encoded_content = base64.b64encode(original_content).decode("utf-8")

        resource = TrackedResource(
            arn="arn:aws:lambda:us-east-1:123456789012:function:workflow-test",
            resource_type="lambda:function",
            name="workflow-test",
            region="us-east-1",
            raw_config={
                "FunctionName": "workflow-test",
                "Runtime": "python3.11",
                "Handler": "main.handler",
                "CodeSha256": "workflow-hash",
                "CodeSize": len(original_content),
                "Code": {
                    "ZipFile": encoded_content,
                },
            },
        )

        lambda_code = LambdaCode.from_resource(resource)
        extracted_path = lambda_code.extract_to(tmp_path)

        assert extracted_path is not None
        extracted_content = Path(extracted_path).read_bytes()
        assert extracted_content == original_content
        assert lambda_code.code_file_path == extracted_path
