"""Tests for AI-powered pattern generation."""

from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

import pytest

from src.patterns.generator import (
    generate_from_description,
    generate_from_snapshot,
    generate_guidance,
)
from src.patterns.models import (
    ComparisonReport,
    ExpectViolation,
    GuardrailViolationRef,
    Pattern,
    PatternMatch,
    PatternResource,
)

SAMPLE_PATTERN_DICT = {
    "name": "web-api",
    "description": "A simple web API pattern",
    "version": 1,
    "tags": ["api", "serverless"],
    "owner": "platform-team",
    "resources": [
        {
            "type": "lambda:function",
            "count": 2,
            "description": "API handler functions",
            "expect": {"Runtime": "python3.11"},
        },
        {
            "type": "apigateway:rest-api",
            "count": 1,
            "description": "REST API gateway",
        },
    ],
    "guardrails": [],
}


def _make_bedrock_response(content_dict: dict) -> MagicMock:
    """Create a mock Bedrock invoke_model response."""
    body_bytes = json.dumps(
        {"content": [{"text": json.dumps(content_dict)}]}
    ).encode()
    response = MagicMock()
    response.__getitem__ = lambda self, key: {"body": io.BytesIO(body_bytes)}[key]
    return response


def _make_bedrock_text_response(text: str) -> MagicMock:
    """Create a mock Bedrock response with raw text content."""
    body_bytes = json.dumps(
        {"content": [{"text": text}]}
    ).encode()
    response = MagicMock()
    response.__getitem__ = lambda self, key: {"body": io.BytesIO(body_bytes)}[key]
    return response


class TestGenerateFromDescription:
    """Tests for generate_from_description (T016)."""

    def test_valid_response_returns_pattern(self) -> None:
        mock_client = MagicMock()
        mock_client.invoke_model.return_value = _make_bedrock_response(SAMPLE_PATTERN_DICT)

        pattern = generate_from_description(
            description="A serverless web API with Lambda and API Gateway",
            bedrock_client=mock_client,
        )

        assert isinstance(pattern, Pattern)
        assert pattern.name == "web-api"
        assert pattern.description == "A simple web API pattern"
        assert len(pattern.resources) == 2
        assert pattern.resources[0].type == "lambda:function"
        assert pattern.resources[0].count == 2
        mock_client.invoke_model.assert_called_once()

    def test_instructions_included_in_prompt(self) -> None:
        mock_client = MagicMock()
        mock_client.invoke_model.return_value = _make_bedrock_response(SAMPLE_PATTERN_DICT)

        generate_from_description(
            description="A web API",
            instructions="Use Python 3.12 runtime and ARM64 architecture",
            bedrock_client=mock_client,
        )

        call_args = mock_client.invoke_model.call_args
        body = json.loads(call_args.kwargs.get("body", call_args[1].get("body", "")))
        prompt_text = body["messages"][0]["content"]
        assert "Use Python 3.12 runtime and ARM64 architecture" in prompt_text

    def test_no_bedrock_client_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Bedrock credentials required"):
            generate_from_description(
                description="A web API",
                bedrock_client=None,
            )


class TestGenerateFromSnapshot:
    """Tests for generate_from_snapshot (T016)."""

    @patch("src.snapshot.storage.SnapshotStorage")
    def test_valid_snapshot_returns_pattern(self, mock_storage_cls: MagicMock) -> None:
        mock_resource = MagicMock()
        mock_resource.resource_type = "lambda:function"
        mock_resource.raw_config = {"Runtime": "python3.11", "Handler": "index.handler"}

        mock_snapshot = MagicMock()
        mock_snapshot.resources = [mock_resource, mock_resource]
        mock_snapshot.account_id = "123456789012"

        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = mock_snapshot
        mock_storage_cls.return_value = mock_storage

        mock_client = MagicMock()
        mock_client.invoke_model.return_value = _make_bedrock_response(SAMPLE_PATTERN_DICT)

        pattern = generate_from_snapshot(
            snapshot_name="test-snapshot",
            bedrock_client=mock_client,
        )

        assert isinstance(pattern, Pattern)
        assert pattern.source_snapshot == "test-snapshot"
        assert pattern.source_account == "123456789012"
        mock_storage.load_snapshot.assert_called_once_with("test-snapshot")

    @patch("src.snapshot.storage.SnapshotStorage")
    def test_resources_summarized_in_prompt(self, mock_storage_cls: MagicMock) -> None:
        mock_lambda = MagicMock()
        mock_lambda.resource_type = "lambda:function"
        mock_lambda.raw_config = {"Runtime": "python3.11"}

        mock_bucket = MagicMock()
        mock_bucket.resource_type = "s3:bucket"
        mock_bucket.raw_config = {"BucketName": "my-bucket"}

        mock_snapshot = MagicMock()
        mock_snapshot.resources = [mock_lambda, mock_bucket]
        mock_snapshot.account_id = "123456789012"

        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = mock_snapshot
        mock_storage_cls.return_value = mock_storage

        mock_client = MagicMock()
        mock_client.invoke_model.return_value = _make_bedrock_response(SAMPLE_PATTERN_DICT)

        generate_from_snapshot(
            snapshot_name="test-snapshot",
            bedrock_client=mock_client,
        )

        call_args = mock_client.invoke_model.call_args
        body = json.loads(call_args.kwargs.get("body", call_args[1].get("body", "")))
        prompt_text = body["messages"][0]["content"]
        assert "lambda:function" in prompt_text
        assert "s3:bucket" in prompt_text
        assert "1 instance(s)" in prompt_text

    @patch("src.snapshot.storage.SnapshotStorage")
    def test_guardrail_names_excluded_from_expect(self, mock_storage_cls: MagicMock) -> None:
        mock_resource = MagicMock()
        mock_resource.resource_type = "s3:bucket"
        mock_resource.raw_config = {}

        mock_snapshot = MagicMock()
        mock_snapshot.resources = [mock_resource]
        mock_snapshot.account_id = "123456789012"

        mock_storage = MagicMock()
        mock_storage.load_snapshot.return_value = mock_snapshot
        mock_storage_cls.return_value = mock_storage

        mock_client = MagicMock()
        mock_client.invoke_model.return_value = _make_bedrock_response(SAMPLE_PATTERN_DICT)

        generate_from_snapshot(
            snapshot_name="test-snapshot",
            guardrail_names=["encryption-at-rest", "public-access-block"],
            bedrock_client=mock_client,
        )

        call_args = mock_client.invoke_model.call_args
        body = json.loads(call_args.kwargs.get("body", call_args[1].get("body", "")))
        prompt_text = body["messages"][0]["content"]
        assert "encryption-at-rest" in prompt_text
        assert "public-access-block" in prompt_text
        assert "Do NOT include expect fields" in prompt_text

    def test_no_bedrock_client_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Bedrock credentials required"):
            generate_from_snapshot(
                snapshot_name="test-snapshot",
                bedrock_client=None,
            )


class TestGenerateGuidance:
    """Tests for generate_guidance (T017)."""

    def test_returns_guidance_string(self) -> None:
        mock_client = MagicMock()
        mock_client.invoke_model.return_value = _make_bedrock_text_response(
            "You should fix the encryption settings on your S3 buckets."
        )

        report = ComparisonReport(
            snapshot_name="test-snapshot",
            matches=[
                PatternMatch(
                    pattern=Pattern(
                        name="web-api",
                        description="Web API pattern",
                        version=1,
                        tags=["api"],
                        owner="team",
                        resources=[
                            PatternResource(type="lambda:function", count=1),
                        ],
                    ),
                    score=0.8,
                    aligned={"lambda:function": (1, 1)},
                    missing={},
                    extra={},
                    expect_violations=[],
                    guardrail_violations=[],
                ),
            ],
            threshold=0.25,
        )

        result = generate_guidance(report, bedrock_client=mock_client)
        assert "encryption" in result.lower() or len(result) > 0
        mock_client.invoke_model.assert_called_once()

    def test_no_bedrock_returns_empty_string(self) -> None:
        report = ComparisonReport(
            snapshot_name="test",
            matches=[],
            threshold=0.25,
        )
        result = generate_guidance(report, bedrock_client=None)
        assert result == ""

    def test_bedrock_error_returns_empty_string(self) -> None:
        mock_client = MagicMock()
        mock_client.invoke_model.side_effect = RuntimeError("Connection timeout")

        report = ComparisonReport(
            snapshot_name="test",
            matches=[
                PatternMatch(
                    pattern=Pattern(
                        name="test-pattern",
                        description="Test",
                        version=1,
                        tags=[],
                        owner="",
                        resources=[PatternResource(type="s3:bucket", count=1)],
                    ),
                    score=0.5,
                    aligned={"s3:bucket": (1, 1)},
                    missing={},
                    extra={},
                    expect_violations=[
                        ExpectViolation(
                            resource_type="s3:bucket",
                            resource_name="my-bucket",
                            config_key="Versioning",
                            actual_value="Suspended",
                            expected_value="Enabled",
                        ),
                    ],
                    guardrail_violations=[
                        GuardrailViolationRef(
                            guardrail_name="encryption-at-rest",
                            resource_type="s3:bucket",
                            resource_name="my-bucket",
                            detail="No encryption configured",
                        ),
                    ],
                ),
            ],
            threshold=0.25,
        )

        result = generate_guidance(report, bedrock_client=mock_client)
        assert result == ""
