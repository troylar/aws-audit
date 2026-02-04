"""Unit tests for CDK generator class (T021)."""

from __future__ import annotations

import os
import sys
import tempfile
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


def _setup_mocks() -> None:
    """Setup mocks for langgraph imports."""
    mock_langgraph = MagicMock()
    mock_langgraph.graph = MagicMock()
    mock_langgraph.graph.END = "END"
    mock_langgraph.graph.StateGraph = MagicMock()
    sys.modules["langgraph"] = mock_langgraph
    sys.modules["langgraph.graph"] = mock_langgraph.graph


_setup_mocks()

# Import after mocks
from src.generate.terraform_generator import GenerationResult


class TestCDKGeneratorInit:
    """Tests for CDKGenerator initialization."""

    @pytest.fixture
    def cdk_generator_module(self) -> Any:
        """Return the cdk_generator module."""
        from src.generate import cdk_generator

        return cdk_generator

    def test_cdk_generator_class_exists(self, cdk_generator_module: Any) -> None:
        """Test that CDKGenerator class exists."""
        assert hasattr(cdk_generator_module, "CDKGenerator")

    def test_cdk_generator_init_with_defaults(self, cdk_generator_module: Any) -> None:
        """Test CDKGenerator initializes with default values."""
        with patch.object(cdk_generator_module, "compile_cdk_agent"):
            generator = cdk_generator_module.CDKGenerator()
            assert generator.output_dir == "./cdk"
            assert generator.output_format in ("cdk-typescript", "cdk-python")

    def test_cdk_generator_init_with_typescript(self, cdk_generator_module: Any) -> None:
        """Test CDKGenerator initializes for TypeScript."""
        with patch.object(cdk_generator_module, "compile_cdk_agent"):
            generator = cdk_generator_module.CDKGenerator(
                output_dir="./my-cdk",
                output_format="cdk-typescript",
            )
            assert generator.output_dir == "./my-cdk"
            assert generator.output_format == "cdk-typescript"

    def test_cdk_generator_init_with_python(self, cdk_generator_module: Any) -> None:
        """Test CDKGenerator initializes for Python."""
        with patch.object(cdk_generator_module, "compile_cdk_agent"):
            generator = cdk_generator_module.CDKGenerator(
                output_dir="./my-cdk",
                output_format="cdk-python",
            )
            assert generator.output_dir == "./my-cdk"
            assert generator.output_format == "cdk-python"


class TestCDKGeneratorRun:
    """Tests for CDKGenerator.run() method."""

    @pytest.fixture
    def cdk_generator_module(self) -> Any:
        """Return the cdk_generator module."""
        from src.generate import cdk_generator

        return cdk_generator

    def test_run_requires_snapshot_or_input_file(self, cdk_generator_module: Any) -> None:
        """Test run() raises error when neither snapshot nor input_file provided."""
        with patch.object(cdk_generator_module, "compile_cdk_agent"):
            generator = cdk_generator_module.CDKGenerator()
            with pytest.raises(ValueError, match="Either snapshot_name or input_file"):
                generator.run()


class TestCDKGeneratorTemplates:
    """Tests for CDK project template generation."""

    @pytest.fixture
    def cdk_generator_module(self) -> Any:
        """Return the cdk_generator module."""
        from src.generate import cdk_generator

        return cdk_generator

    def test_generates_package_json_for_typescript(self, cdk_generator_module: Any) -> None:
        """Test TypeScript project generates package.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_agent = MagicMock()
            mock_agent.invoke.return_value = {
                "generated_files": [os.path.join(tmpdir, "lib", "network_stack.ts")],
                "layers": {"NETWORK": []},
                "layer_order": ["NETWORK"],
                "errors": [],
                "validation_errors": [],
            }

            with patch.object(cdk_generator_module, "compile_cdk_agent", return_value=mock_agent):
                generator = cdk_generator_module.CDKGenerator(
                    output_dir=tmpdir,
                    output_format="cdk-typescript",
                )
                generator.run(snapshot_name="test")

                package_json_path = os.path.join(tmpdir, "package.json")
                assert os.path.exists(package_json_path)

    def test_generates_cdk_json(self, cdk_generator_module: Any) -> None:
        """Test CDK project generates cdk.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_agent = MagicMock()
            mock_agent.invoke.return_value = {
                "generated_files": [os.path.join(tmpdir, "lib", "network_stack.ts")],
                "layers": {"NETWORK": []},
                "layer_order": ["NETWORK"],
                "errors": [],
                "validation_errors": [],
            }

            with patch.object(cdk_generator_module, "compile_cdk_agent", return_value=mock_agent):
                generator = cdk_generator_module.CDKGenerator(
                    output_dir=tmpdir,
                    output_format="cdk-typescript",
                )
                generator.run(snapshot_name="test")

                cdk_json_path = os.path.join(tmpdir, "cdk.json")
                assert os.path.exists(cdk_json_path)

    def test_generates_tsconfig_for_typescript(self, cdk_generator_module: Any) -> None:
        """Test TypeScript project generates tsconfig.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_agent = MagicMock()
            mock_agent.invoke.return_value = {
                "generated_files": [os.path.join(tmpdir, "lib", "network_stack.ts")],
                "layers": {"NETWORK": []},
                "layer_order": ["NETWORK"],
                "errors": [],
                "validation_errors": [],
            }

            with patch.object(cdk_generator_module, "compile_cdk_agent", return_value=mock_agent):
                generator = cdk_generator_module.CDKGenerator(
                    output_dir=tmpdir,
                    output_format="cdk-typescript",
                )
                generator.run(snapshot_name="test")

                tsconfig_path = os.path.join(tmpdir, "tsconfig.json")
                assert os.path.exists(tsconfig_path)

    def test_generates_requirements_for_python(self, cdk_generator_module: Any) -> None:
        """Test Python project generates requirements.txt."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_agent = MagicMock()
            mock_agent.invoke.return_value = {
                "generated_files": [os.path.join(tmpdir, "stacks", "network_stack.py")],
                "layers": {"NETWORK": []},
                "layer_order": ["NETWORK"],
                "errors": [],
                "validation_errors": [],
            }

            with patch.object(cdk_generator_module, "compile_cdk_agent", return_value=mock_agent):
                generator = cdk_generator_module.CDKGenerator(
                    output_dir=tmpdir,
                    output_format="cdk-python",
                )
                generator.run(snapshot_name="test")

                requirements_path = os.path.join(tmpdir, "requirements.txt")
                assert os.path.exists(requirements_path)


class TestCDKGeneratorResult:
    """Tests for CDKGenerator result handling."""

    @pytest.fixture
    def cdk_generator_module(self) -> Any:
        """Return the cdk_generator module."""
        from src.generate import cdk_generator

        return cdk_generator

    def test_returns_generation_result(self, cdk_generator_module: Any) -> None:
        """Test run() returns a GenerationResult."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_agent = MagicMock()
            mock_agent.invoke.return_value = {
                "generated_files": [os.path.join(tmpdir, "lib", "network_stack.ts")],
                "layers": {"NETWORK": []},
                "layer_order": ["NETWORK"],
                "errors": [],
                "validation_errors": [],
            }

            with patch.object(cdk_generator_module, "compile_cdk_agent", return_value=mock_agent):
                generator = cdk_generator_module.CDKGenerator(output_dir=tmpdir)
                result = generator.run(snapshot_name="test")

                assert isinstance(result, GenerationResult)

    def test_result_includes_generated_files(self, cdk_generator_module: Any) -> None:
        """Test result includes list of generated files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_agent = MagicMock()
            mock_agent.invoke.return_value = {
                "generated_files": [
                    os.path.join(tmpdir, "lib", "network_stack.ts"),
                    os.path.join(tmpdir, "lib", "compute_stack.ts"),
                ],
                "layers": {"NETWORK": [], "COMPUTE": []},
                "layer_order": ["NETWORK", "COMPUTE"],
                "errors": [],
                "validation_errors": [],
            }

            with patch.object(cdk_generator_module, "compile_cdk_agent", return_value=mock_agent):
                generator = cdk_generator_module.CDKGenerator(output_dir=tmpdir)
                result = generator.run(snapshot_name="test")

                assert len(result.generated_files) == 2

    def test_result_success_when_no_errors(self, cdk_generator_module: Any) -> None:
        """Test result.success is True when no errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_agent = MagicMock()
            mock_agent.invoke.return_value = {
                "generated_files": [os.path.join(tmpdir, "lib", "network_stack.ts")],
                "layers": {"NETWORK": []},
                "layer_order": ["NETWORK"],
                "errors": [],
                "validation_errors": [],
            }

            with patch.object(cdk_generator_module, "compile_cdk_agent", return_value=mock_agent):
                generator = cdk_generator_module.CDKGenerator(output_dir=tmpdir)
                result = generator.run(snapshot_name="test")

                assert result.success is True

    def test_result_failure_when_errors(self, cdk_generator_module: Any) -> None:
        """Test result.success is False when errors occur."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_agent = MagicMock()
            mock_agent.invoke.return_value = {
                "generated_files": [],
                "layers": {},
                "layer_order": [],
                "errors": [{"message": "Generation failed"}],
                "validation_errors": [],
            }

            with patch.object(cdk_generator_module, "compile_cdk_agent", return_value=mock_agent):
                generator = cdk_generator_module.CDKGenerator(output_dir=tmpdir)
                result = generator.run(snapshot_name="test")

                assert result.success is False


class TestGenerateCdkFunction:
    """Tests for generate_cdk() convenience function."""

    @pytest.fixture
    def cdk_generator_module(self) -> Any:
        """Return the cdk_generator module."""
        from src.generate import cdk_generator

        return cdk_generator

    def test_generate_cdk_function_exists(self, cdk_generator_module: Any) -> None:
        """Test generate_cdk function exists."""
        assert hasattr(cdk_generator_module, "generate_cdk")
        assert callable(cdk_generator_module.generate_cdk)

    def test_generate_cdk_creates_generator_and_runs(self, cdk_generator_module: Any) -> None:
        """Test generate_cdk creates generator and runs it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_agent = MagicMock()
            mock_agent.invoke.return_value = {
                "generated_files": [os.path.join(tmpdir, "lib", "network_stack.ts")],
                "layers": {"NETWORK": []},
                "layer_order": ["NETWORK"],
                "errors": [],
                "validation_errors": [],
            }

            with patch.object(cdk_generator_module, "compile_cdk_agent", return_value=mock_agent):
                result = cdk_generator_module.generate_cdk(
                    snapshot_name="test",
                    output_dir=tmpdir,
                    output_format="cdk-typescript",
                )

                assert isinstance(result, GenerationResult)
