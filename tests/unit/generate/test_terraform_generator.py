"""Unit tests for TerraformGenerator and GenerationResult."""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Ensure langgraph mocks are in place (same as test_agent.py)
if "langgraph" not in sys.modules:
    _mock_lg = MagicMock()
    _mock_lg.graph = MagicMock()
    _mock_lg.graph.END = "END"
    _mock_lg.graph.StateGraph = MagicMock(return_value=MagicMock())
    sys.modules["langgraph"] = _mock_lg
    sys.modules["langgraph.graph"] = _mock_lg.graph

from src.generate.layers import LayerStatus
from src.generate.terraform_generator import GenerationResult, TerraformGenerator, generate_terraform
from src.models.generation import Layer


class TestGenerationResult:
    """Tests for GenerationResult dataclass."""

    def test_default_values(self) -> None:
        r = GenerationResult(success=True, output_dir="/tmp/tf")
        assert r.success is True
        assert r.output_dir == "/tmp/tf"
        assert r.generated_files == []
        assert r.layers == []
        assert r.errors == []
        assert r.validation_errors == []
        assert r.guardrails_blocked is False
        assert r.guardrails_report is None

    def test_is_valid_no_errors(self) -> None:
        r = GenerationResult(success=True, output_dir="/tmp/tf")
        assert r.is_valid is True

    def test_is_valid_with_errors(self) -> None:
        r = GenerationResult(success=True, output_dir="/tmp/tf", validation_errors=["bad config"])
        assert r.is_valid is False

    def test_summary_with_layer_objects(self) -> None:
        layers = [
            Layer(name="NETWORK", order=1, resources=[{"arn": "a"}], status=LayerStatus.COMPLETED.value),
            Layer(name="COMPUTE", order=2, resources=[{"arn": "b"}, {"arn": "c"}], status=LayerStatus.FAILED.value),
        ]
        r = GenerationResult(success=True, output_dir="/tmp/tf", layers=layers, generated_files=["main.tf"])
        s = r.summary
        assert s["total_layers"] == 2
        assert s["total_resources"] == 3
        assert s["completed_layers"] == 1
        assert s["failed_layers"] == 1
        assert s["generated_files"] == 1

    def test_summary_with_list_of_lists(self) -> None:
        layers = [
            [{"arn": "a"}, {"arn": "b"}],
            [{"arn": "c"}],
        ]
        r = GenerationResult(success=True, output_dir="/tmp/tf", layers=layers)
        s = r.summary
        assert s["total_resources"] == 3
        assert s["completed_layers"] == 2

    def test_guardrails_blocked_field(self) -> None:
        r = GenerationResult(success=False, output_dir="/tmp/tf", guardrails_blocked=True)
        assert r.guardrails_blocked is True


class TestTerraformGeneratorInit:
    """Tests for TerraformGenerator.__init__."""

    def _make_generator(self, **kwargs: Any) -> TerraformGenerator:
        with patch("src.generate.terraform_generator.compile_terraform_agent", return_value=MagicMock()):
            with patch("src.generate.terraform_generator.GenerationConfig.from_env") as mock_env:
                mock_env.return_value = MagicMock(
                    bedrock_model_id="default-model",
                    bedrock_region="us-east-1",
                    max_retries=3,
                )
                return TerraformGenerator(**kwargs)

    def test_default_params(self) -> None:
        gen = self._make_generator()
        assert gen.output_dir == "./terraform"
        assert gen.guardrails_enabled is False
        assert gen.best_practices_enabled is True

    def test_custom_params(self, tmp_path: Any) -> None:
        gen = self._make_generator(
            output_dir=str(tmp_path),
            model_id="custom-model",
            region="eu-west-1",
            guardrails_enabled=True,
            guardrails_strict=True,
            best_practices_enabled=False,
        )
        assert gen.output_dir == str(tmp_path)
        assert gen.config.bedrock_model_id == "custom-model"
        assert gen.config.bedrock_region == "eu-west-1"
        assert gen.guardrails_enabled is True
        assert gen.guardrails_strict is True
        assert gen.best_practices_enabled is False


class TestTerraformGeneratorRun:
    """Tests for TerraformGenerator.run."""

    def _make_generator(self, tmp_path: Any, mock_agent: MagicMock) -> TerraformGenerator:
        with patch("src.generate.terraform_generator.compile_terraform_agent", return_value=mock_agent):
            with patch("src.generate.terraform_generator.GenerationConfig.from_env") as mock_env:
                mock_env.return_value = MagicMock(
                    bedrock_model_id="model",
                    bedrock_region="us-east-1",
                    max_retries=3,
                )
                return TerraformGenerator(output_dir=str(tmp_path / "terraform"))

    def test_no_snapshot_or_input_raises(self, tmp_path: Any) -> None:
        mock_agent = MagicMock()
        gen = self._make_generator(tmp_path, mock_agent)
        with pytest.raises(ValueError, match="Either snapshot_name or input_file"):
            gen.run()

    def test_successful_run(self, tmp_path: Any) -> None:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "generated_files": ["vpc.tf"],
            "layers": {"NETWORK": Layer(name="NETWORK", order=1, resources=[{"arn": "a"}])},
            "layer_order": ["NETWORK"],
            "errors": [],
            "validation_errors": [],
            "guardrails_blocked": False,
            "guardrails_report": None,
        }
        gen = self._make_generator(tmp_path, mock_agent)
        result = gen.run(snapshot_name="snap1")

        assert result.success is True
        assert "vpc.tf" in result.generated_files
        assert (tmp_path / "terraform" / "main.tf").exists()
        assert (tmp_path / "terraform" / "variables.tf").exists()
        assert (tmp_path / "terraform" / "outputs.tf").exists()

    def test_agent_exception_returns_error(self, tmp_path: Any) -> None:
        mock_agent = MagicMock()
        mock_agent.invoke.side_effect = RuntimeError("Bedrock error")
        gen = self._make_generator(tmp_path, mock_agent)
        result = gen.run(snapshot_name="snap1")

        assert result.success is False
        assert any("Bedrock error" in e for e in result.errors)

    def test_guardrails_blocked(self, tmp_path: Any) -> None:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "generated_files": [],
            "layers": {},
            "layer_order": [],
            "errors": [],
            "validation_errors": [],
            "guardrails_blocked": True,
            "guardrails_report": {"violations": ["encryption required"]},
        }
        gen = self._make_generator(tmp_path, mock_agent)
        result = gen.run(snapshot_name="snap1")

        assert result.success is False
        assert result.guardrails_blocked is True
        assert any("guardrails" in e.lower() for e in result.errors)

    def test_input_file_accepted(self, tmp_path: Any) -> None:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "generated_files": ["main.tf"],
            "layers": {},
            "layer_order": [],
            "errors": [],
            "validation_errors": [],
            "guardrails_blocked": False,
            "guardrails_report": None,
        }
        gen = self._make_generator(tmp_path, mock_agent)
        result = gen.run(input_file="/tmp/export.json")

        assert result.success is True


class TestGenerateProviderConfig:
    """Tests for _generate_provider_config."""

    def test_writes_main_tf(self, tmp_path: Any) -> None:
        with patch("src.generate.terraform_generator.compile_terraform_agent", return_value=MagicMock()):
            with patch("src.generate.terraform_generator.GenerationConfig.from_env") as mock_env:
                mock_env.return_value = MagicMock(
                    bedrock_model_id="m",
                    bedrock_region="us-east-1",
                    max_retries=3,
                )
                gen = TerraformGenerator(output_dir=str(tmp_path))

        gen._generate_provider_config()
        content = (tmp_path / "main.tf").read_text()
        assert 'source  = "hashicorp/aws"' in content
        assert "var.aws_region" in content


class TestGenerateVariablesFile:
    """Tests for _generate_variables_file."""

    def test_writes_variables_tf(self, tmp_path: Any) -> None:
        with patch("src.generate.terraform_generator.compile_terraform_agent", return_value=MagicMock()):
            with patch("src.generate.terraform_generator.GenerationConfig.from_env") as mock_env:
                mock_env.return_value = MagicMock(
                    bedrock_model_id="m",
                    bedrock_region="us-east-1",
                    max_retries=3,
                )
                gen = TerraformGenerator(output_dir=str(tmp_path))

        gen._generate_variables_file({"layers": {}})
        content = (tmp_path / "variables.tf").read_text()
        assert 'variable "aws_region"' in content
        assert "us-east-1" in content

    def test_extracts_region_from_layers(self, tmp_path: Any) -> None:
        with patch("src.generate.terraform_generator.compile_terraform_agent", return_value=MagicMock()):
            with patch("src.generate.terraform_generator.GenerationConfig.from_env") as mock_env:
                mock_env.return_value = MagicMock(
                    bedrock_model_id="m",
                    bedrock_region="us-east-1",
                    max_retries=3,
                )
                gen = TerraformGenerator(output_dir=str(tmp_path))

        mock_resource = MagicMock()
        mock_resource.region = "eu-west-1"
        mock_layer = MagicMock()
        mock_layer.resources = [mock_resource]
        gen._generate_variables_file({"layers": {"NETWORK": mock_layer}})
        content = (tmp_path / "variables.tf").read_text()
        assert "eu-west-1" in content


class TestGenerateOutputsFile:
    """Tests for _generate_outputs_file."""

    def test_writes_outputs_tf(self, tmp_path: Any) -> None:
        with patch("src.generate.terraform_generator.compile_terraform_agent", return_value=MagicMock()):
            with patch("src.generate.terraform_generator.GenerationConfig.from_env") as mock_env:
                mock_env.return_value = MagicMock(
                    bedrock_model_id="m",
                    bedrock_region="us-east-1",
                    max_retries=3,
                )
                gen = TerraformGenerator(output_dir=str(tmp_path))

        gen._generate_outputs_file({})
        content = (tmp_path / "outputs.tf").read_text()
        assert "# Outputs" in content


class TestGenerateTerraformFunction:
    """Tests for the generate_terraform convenience function."""

    def test_delegates_to_generator(self, tmp_path: Any) -> None:
        mock_agent = MagicMock()
        mock_agent.invoke.return_value = {
            "generated_files": ["main.tf"],
            "layers": {},
            "layer_order": [],
            "errors": [],
            "validation_errors": [],
            "guardrails_blocked": False,
            "guardrails_report": None,
        }
        with patch("src.generate.terraform_generator.compile_terraform_agent", return_value=mock_agent):
            with patch("src.generate.terraform_generator.GenerationConfig.from_env") as mock_env:
                mock_env.return_value = MagicMock(
                    bedrock_model_id="m",
                    bedrock_region="us-east-1",
                    max_retries=3,
                )
                result = generate_terraform(
                    snapshot_name="snap1",
                    output_dir=str(tmp_path / "tf"),
                )

        assert result.success is True
