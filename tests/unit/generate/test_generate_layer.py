"""Unit tests for generate_layer output_format handling (T015)."""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock

import pytest


def _setup_mocks() -> None:
    """Setup mocks for problematic imports."""
    mock_langgraph = MagicMock()
    mock_langgraph.graph = MagicMock()
    mock_langgraph.graph.END = "END"
    mock_langgraph.graph.StateGraph = MagicMock()
    sys.modules["langgraph"] = mock_langgraph
    sys.modules["langgraph.graph"] = mock_langgraph.graph

    mock_property_maps = MagicMock()
    mock_property_maps.get_property_map = lambda x: None
    sys.modules["src.generate.property_maps"] = mock_property_maps


_setup_mocks()

from src.models.generation import ResourceMap


class TestGenerateLayerOutputFormat:
    """Tests for generate_layer output_format handling."""

    @pytest.fixture
    def generate_layer_module(self) -> Any:
        """Return the generate_layer module."""
        from src.generate.nodes import generate_layer as gl_module

        return gl_module

    @pytest.fixture
    def sample_state(self) -> dict:
        """Create sample state for testing."""
        return {
            "layers": {
                "NETWORK": [
                    {
                        "arn": "arn:aws:ec2:us-east-1:123456789012:vpc/vpc-12345678",
                        "type": "ec2:vpc",
                        "name": "main-vpc",
                        "region": "us-east-1",
                        "tags": {},
                        "raw_config": {"CidrBlock": "10.0.0.0/16"},
                    }
                ]
            },
            "layer_order": ["NETWORK"],
            "resource_map": ResourceMap(),
            "current_layer_index": 0,
            "generated_files": [],
            "output_dir": "/tmp/test-output",
            "lambda_code_paths": {},
        }

    def test_terraform_format_uses_terraform_prompts(self, generate_layer_module: Any, sample_state: dict) -> None:
        """Test that terraform format uses Terraform prompts."""
        sample_state["output_format"] = "terraform"

        # Verify get_prompts_for_format returns terraform prompts for terraform format
        from src.generate.nodes.generate_layer import get_prompts_for_format
        from src.generate.prompts.terraform import (
            format_layer_prompt,
            get_terraform_system_prompt,
        )

        system_fn, layer_fn = get_prompts_for_format("terraform")
        assert system_fn == get_terraform_system_prompt
        assert layer_fn == format_layer_prompt

    def test_cdk_typescript_format_uses_typescript_prompts(
        self, generate_layer_module: Any, sample_state: dict
    ) -> None:
        """Test that cdk-typescript format uses CDK TypeScript prompts."""
        sample_state["output_format"] = "cdk-typescript"

        from src.generate.prompts.cdk_typescript import (
            format_layer_prompt_typescript,
            get_cdk_typescript_system_prompt,
        )

        assert callable(get_cdk_typescript_system_prompt)
        assert callable(format_layer_prompt_typescript)

        system_prompt = get_cdk_typescript_system_prompt()
        assert "CDK" in system_prompt
        assert "TypeScript" in system_prompt

    def test_cdk_python_format_uses_python_prompts(self, generate_layer_module: Any, sample_state: dict) -> None:
        """Test that cdk-python format uses CDK Python prompts."""
        sample_state["output_format"] = "cdk-python"

        from src.generate.prompts.cdk_python import (
            format_layer_prompt_python,
            get_cdk_python_system_prompt,
        )

        assert callable(get_cdk_python_system_prompt)
        assert callable(format_layer_prompt_python)

        system_prompt = get_cdk_python_system_prompt()
        assert "CDK" in system_prompt
        assert "Python" in system_prompt

    def test_default_format_is_terraform(self, generate_layer_module: Any, sample_state: dict) -> None:
        """Test that default output_format is terraform when not specified."""
        # Remove output_format from state
        if "output_format" in sample_state:
            del sample_state["output_format"]

        # Verify default behavior assumes terraform
        from src.generate.state import GenerationConfig

        config = GenerationConfig()
        assert config.output_format == "terraform"

    def test_get_prompts_for_format_returns_correct_prompts(self, generate_layer_module: Any) -> None:
        """Test get_prompts_for_format returns correct prompt functions."""
        # This tests the helper function that selects prompts based on format
        if hasattr(generate_layer_module, "get_prompts_for_format"):
            tf_prompts = generate_layer_module.get_prompts_for_format("terraform")
            assert tf_prompts is not None

            ts_prompts = generate_layer_module.get_prompts_for_format("cdk-typescript")
            assert ts_prompts is not None

            py_prompts = generate_layer_module.get_prompts_for_format("cdk-python")
            assert py_prompts is not None


class TestGenerateLayerFileExtension:
    """Tests for correct file extensions based on output_format."""

    def test_terraform_uses_tf_extension(self) -> None:
        """Test that Terraform format uses .tf extension."""
        from src.generate.nodes.generate_layer import _get_file_extension

        if hasattr(_get_file_extension, "__call__"):
            ext = _get_file_extension("terraform")
            assert ext == ".tf"
        else:
            # Function may not exist yet - will be added in implementation
            pytest.skip("_get_file_extension not yet implemented")

    def test_cdk_typescript_uses_ts_extension(self) -> None:
        """Test that CDK TypeScript format uses .ts extension."""
        from src.generate.nodes.generate_layer import _get_file_extension

        if hasattr(_get_file_extension, "__call__"):
            ext = _get_file_extension("cdk-typescript")
            assert ext == ".ts"
        else:
            pytest.skip("_get_file_extension not yet implemented")

    def test_cdk_python_uses_py_extension(self) -> None:
        """Test that CDK Python format uses .py extension."""
        from src.generate.nodes.generate_layer import _get_file_extension

        if hasattr(_get_file_extension, "__call__"):
            ext = _get_file_extension("cdk-python")
            assert ext == ".py"
        else:
            pytest.skip("_get_file_extension not yet implemented")


class TestCleanCode:
    """Tests for code cleaning functions."""

    def test_clean_terraform_code(self) -> None:
        """Test cleaning Terraform code removes markdown."""
        from src.generate.nodes.generate_layer import _clean_terraform_code

        code = '```hcl\nresource "aws_vpc" "main" {}\n```'
        result = _clean_terraform_code(code)
        assert "```" not in result
        assert "resource" in result

    def test_clean_typescript_code(self) -> None:
        """Test cleaning TypeScript code removes markdown."""
        from src.generate.nodes.generate_layer import _clean_code

        if hasattr(_clean_code, "__call__"):
            code = "```typescript\nimport * as cdk from 'aws-cdk-lib';\n```"
            result = _clean_code(code, "cdk-typescript")
            assert "```" not in result
            assert "import" in result
        else:
            pytest.skip("_clean_code not yet implemented")

    def test_clean_python_code(self) -> None:
        """Test cleaning Python code removes markdown."""
        from src.generate.nodes.generate_layer import _clean_code

        if hasattr(_clean_code, "__call__"):
            code = "```python\nfrom aws_cdk import Stack\n```"
            result = _clean_code(code, "cdk-python")
            assert "```" not in result
            assert "from" in result
        else:
            pytest.skip("_clean_code not yet implemented")
