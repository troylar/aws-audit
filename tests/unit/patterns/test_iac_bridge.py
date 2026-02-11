"""Tests for pattern-to-IaC bridge (T046)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.patterns.iac_bridge import (
    generate_iac_from_pattern,
    pattern_to_input_file,
    pattern_to_inventory,
)
from src.patterns.models import Pattern, PatternResource


@pytest.fixture
def sample_pattern() -> Pattern:
    return Pattern(
        name="web-api",
        description="Web API pattern",
        version=1,
        tags=["api"],
        owner="team",
        resources=[
            PatternResource(
                type="lambda:function",
                count=2,
                description="Handlers",
                expect={"Runtime": "python3.12", "MemorySize": ">= 256"},
            ),
            PatternResource(
                type="apigateway:rest-api",
                count=1,
                description="API Gateway",
            ),
        ],
        guardrails=["encryption-at-rest"],
    )


class TestPatternToInventory:
    def test_creates_correct_number_of_resources(self, sample_pattern: Pattern) -> None:
        resources = pattern_to_inventory(sample_pattern)
        assert len(resources) == 3  # 2 lambda + 1 apigateway

    def test_resource_types_preserved(self, sample_pattern: Pattern) -> None:
        resources = pattern_to_inventory(sample_pattern)
        types = [r["resource_type"] for r in resources]
        assert types.count("lambda:function") == 2
        assert types.count("apigateway:rest-api") == 1

    def test_expect_fields_in_raw_config(self, sample_pattern: Pattern) -> None:
        resources = pattern_to_inventory(sample_pattern)
        lambda_resources = [r for r in resources if r["resource_type"] == "lambda:function"]
        assert lambda_resources[0]["raw_config"]["Runtime"] == "python3.12"

    def test_empty_expect_produces_empty_raw_config(self) -> None:
        pattern = Pattern(
            name="simple",
            description="Simple",
            version=1,
            tags=[],
            owner="",
            resources=[PatternResource(type="s3:bucket", count=1)],
        )
        resources = pattern_to_inventory(pattern)
        assert resources[0]["raw_config"] == {}

    def test_resources_have_required_fields(self, sample_pattern: Pattern) -> None:
        resources = pattern_to_inventory(sample_pattern)
        for r in resources:
            assert "arn" in r
            assert "resource_type" in r
            assert "name" in r
            assert "region" in r
            assert "tags" in r
            assert "raw_config" in r

    def test_unique_arns(self, sample_pattern: Pattern) -> None:
        resources = pattern_to_inventory(sample_pattern)
        arns = [r["arn"] for r in resources]
        assert len(arns) == len(set(arns))


class TestPatternToInputFile:
    def test_writes_valid_json(self, sample_pattern: Pattern, tmp_path: Path) -> None:
        path = pattern_to_input_file(sample_pattern, output_dir=str(tmp_path))
        assert Path(path).exists()
        with open(path) as f:
            data = json.load(f)
        assert len(data) == 3

    def test_temp_dir_when_no_output_dir(self, sample_pattern: Pattern) -> None:
        path = pattern_to_input_file(sample_pattern)
        assert Path(path).exists()
        with open(path) as f:
            data = json.load(f)
        assert len(data) == 3
        Path(path).unlink(missing_ok=True)

    def test_file_naming(self, sample_pattern: Pattern, tmp_path: Path) -> None:
        path = pattern_to_input_file(sample_pattern, output_dir=str(tmp_path))
        assert "web-api-inventory.json" in path


class TestGenerateIacFromPattern:
    @patch("src.generate.terraform_generator.generate_terraform")
    def test_terraform_format(
        self,
        mock_gen: MagicMock,
        sample_pattern: Pattern,
    ) -> None:
        mock_result = MagicMock()
        mock_result.success = True
        mock_gen.return_value = mock_result

        result = generate_iac_from_pattern(
            sample_pattern,
            output_format="terraform",
            output_dir="./output",
        )

        assert result.success is True
        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args[1]
        assert call_kwargs["output_dir"] == "./output"
        assert call_kwargs["input_file"].endswith(".json")

    @patch("src.generate.cdk_generator.generate_cdk")
    def test_cdk_typescript_format(
        self,
        mock_gen: MagicMock,
        sample_pattern: Pattern,
    ) -> None:
        mock_result = MagicMock()
        mock_result.success = True
        mock_gen.return_value = mock_result

        result = generate_iac_from_pattern(
            sample_pattern,
            output_format="cdk-typescript",
        )

        assert result.success is True
        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args[1]
        assert call_kwargs["output_format"] == "cdk-typescript"

    @patch("src.generate.cdk_generator.generate_cdk")
    def test_cdk_python_format(
        self,
        mock_gen: MagicMock,
        sample_pattern: Pattern,
    ) -> None:
        mock_result = MagicMock()
        mock_result.success = True
        mock_gen.return_value = mock_result

        result = generate_iac_from_pattern(
            sample_pattern,
            output_format="cdk-python",
        )

        assert result.success is True

    def test_invalid_format_raises_value_error(self, sample_pattern: Pattern) -> None:
        with pytest.raises(ValueError, match="Unsupported format"):
            generate_iac_from_pattern(sample_pattern, output_format="invalid")

    @patch("src.generate.terraform_generator.generate_terraform")
    def test_guardrails_passed_through(
        self,
        mock_gen: MagicMock,
        sample_pattern: Pattern,
    ) -> None:
        mock_gen.return_value = MagicMock(success=True)

        generate_iac_from_pattern(
            sample_pattern,
            output_format="terraform",
            guardrails_enabled=True,
            guardrails_policy_path="/path/to/policy.yaml",
        )

        call_kwargs = mock_gen.call_args[1]
        assert call_kwargs["guardrails_enabled"] is True
        assert call_kwargs["guardrails_policy_path"] == "/path/to/policy.yaml"
