"""Unit tests for GenerationConfig and GenerationState."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from src.generate.state import GenerationConfig, GenerationState


class TestGenerationConfig:
    """Tests for GenerationConfig dataclass."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        config = GenerationConfig()

        assert config.ai_endpoint == "https://api.openai.com/v1"
        assert config.ai_api_key == ""
        assert config.ai_model == "gpt-4"
        assert config.temperature == 0.2
        assert config.max_retries == 3
        assert config.validate_each_layer is True
        assert config.terraform_init is True
        assert config.output_format == "terraform"
        assert config.backup_existing is True
        assert config.generate_tfvars is True
        assert config.generate_outputs is True
        assert config.parameterize_env_values is True
        assert config.parameterize_sizing is True
        assert config.parameterize_naming is True

    def test_custom_values(self) -> None:
        """Test that custom values can be provided."""
        config = GenerationConfig(
            ai_endpoint="https://custom.api.com/v1",
            ai_api_key="sk-test-key",
            ai_model="gpt-4-turbo",
            temperature=0.5,
            max_retries=5,
            validate_each_layer=False,
            terraform_init=False,
            output_format="cdk-typescript",
            backup_existing=False,
            generate_tfvars=False,
            generate_outputs=False,
            parameterize_env_values=False,
            parameterize_sizing=False,
            parameterize_naming=False,
        )

        assert config.ai_endpoint == "https://custom.api.com/v1"
        assert config.ai_api_key == "sk-test-key"
        assert config.ai_model == "gpt-4-turbo"
        assert config.temperature == 0.5
        assert config.max_retries == 5
        assert config.validate_each_layer is False
        assert config.terraform_init is False
        assert config.output_format == "cdk-typescript"
        assert config.backup_existing is False
        assert config.generate_tfvars is False
        assert config.generate_outputs is False
        assert config.parameterize_env_values is False
        assert config.parameterize_sizing is False
        assert config.parameterize_naming is False

    def test_from_env_with_all_variables(self) -> None:
        """Test from_env reads all environment variables."""
        env_vars = {
            "AWSINV_AI_ENDPOINT": "https://anthropic.api.com/v1",
            "AWSINV_AI_API_KEY": "sk-anthropic-key-12345",
            "AWSINV_AI_MODEL": "claude-3-opus",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            config = GenerationConfig.from_env()

        assert config.ai_endpoint == "https://anthropic.api.com/v1"
        assert config.ai_api_key == "sk-anthropic-key-12345"
        assert config.ai_model == "claude-3-opus"

    def test_from_env_with_partial_variables(self) -> None:
        """Test from_env uses defaults for missing variables."""
        env_vars = {
            "AWSINV_AI_API_KEY": "sk-partial-key",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            # Remove the other variables if they exist
            with patch.dict(
                os.environ,
                {"AWSINV_AI_ENDPOINT": "", "AWSINV_AI_MODEL": ""},
                clear=False,
            ):
                # Clear the variables we don't want
                env_copy = os.environ.copy()
                for key in ["AWSINV_AI_ENDPOINT", "AWSINV_AI_MODEL"]:
                    env_copy.pop(key, None)
                env_copy["AWSINV_AI_API_KEY"] = "sk-partial-key"

                with patch.dict(os.environ, env_copy, clear=True):
                    config = GenerationConfig.from_env()

        assert config.ai_endpoint == "https://api.openai.com/v1"
        assert config.ai_api_key == "sk-partial-key"
        assert config.ai_model == "gpt-4"

    def test_from_env_with_no_variables(self) -> None:
        """Test from_env uses all defaults when no variables set."""
        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("AWSINV_")}

        with patch.dict(os.environ, clean_env, clear=True):
            config = GenerationConfig.from_env()

        assert config.ai_endpoint == "https://api.openai.com/v1"
        assert config.ai_api_key == ""
        assert config.ai_model == "gpt-4"

    def test_from_env_preserves_non_env_defaults(self) -> None:
        """Test from_env preserves defaults for non-env-configurable fields."""
        env_vars = {
            "AWSINV_AI_ENDPOINT": "https://test.api.com",
            "AWSINV_AI_API_KEY": "test-key",
            "AWSINV_AI_MODEL": "test-model",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            config = GenerationConfig.from_env()

        assert config.temperature == 0.2
        assert config.max_retries == 3
        assert config.validate_each_layer is True
        assert config.terraform_init is True
        assert config.output_format == "terraform"
        assert config.backup_existing is True
        assert config.generate_tfvars is True
        assert config.generate_outputs is True

    def test_from_env_empty_string_uses_default(self) -> None:
        """Test from_env treats empty string as missing (uses default)."""
        env_vars = {
            "AWSINV_AI_ENDPOINT": "",
            "AWSINV_AI_API_KEY": "",
            "AWSINV_AI_MODEL": "",
        }

        clean_env = {k: v for k, v in os.environ.items() if not k.startswith("AWSINV_")}
        clean_env.update(env_vars)

        with patch.dict(os.environ, clean_env, clear=True):
            config = GenerationConfig.from_env()

        assert config.ai_endpoint == ""
        assert config.ai_api_key == ""
        assert config.ai_model == ""

    def test_config_is_dataclass(self) -> None:
        """Test that GenerationConfig behaves as a dataclass."""
        config = GenerationConfig()

        assert hasattr(config, "__dataclass_fields__")
        assert "ai_endpoint" in config.__dataclass_fields__
        assert "ai_api_key" in config.__dataclass_fields__
        assert "ai_model" in config.__dataclass_fields__


class TestGenerationState:
    """Tests for GenerationState TypedDict."""

    def test_state_can_be_created(self) -> None:
        """Test that GenerationState can be instantiated."""
        state: GenerationState = {
            "snapshot_name": "test-snapshot",
            "output_dir": "/tmp/output",
            "output_format": "terraform",
        }

        assert state["snapshot_name"] == "test-snapshot"
        assert state["output_dir"] == "/tmp/output"
        assert state["output_format"] == "terraform"

    def test_state_with_all_fields(self) -> None:
        """Test GenerationState with all fields populated."""
        state: GenerationState = {
            "snapshot_name": "full-snapshot",
            "output_dir": "/tmp/full-output",
            "output_format": "cdk-typescript",
            "inventory": [{"arn": "test", "type": "ec2:instance"}],
            "resource_map": {"vpc-123": "aws_vpc.main"},
            "layers": {"network": [{"arn": "test"}]},
            "layer_order": ["network", "security", "compute"],
            "current_layer_index": 1,
            "current_layer_status": "in_progress",
            "attempt_count": 2,
            "max_attempts": 5,
            "validation_errors": ["error1", "error2"],
            "generated_code": {"vpc.tf": "resource aws_vpc..."},
            "generated_files": ["vpc.tf", "subnets.tf"],
            "lambda_code_paths": {"my-func": "/tmp/lambda/my-func.zip"},
            "total_resources": 100,
            "processed_resources": 50,
            "errors": [{"resource": "vpc-123", "error": "failed"}],
            "messages": [{"level": "info", "text": "Starting..."}],
        }

        assert state["snapshot_name"] == "full-snapshot"
        assert state["total_resources"] == 100
        assert state["processed_resources"] == 50
        assert len(state["validation_errors"]) == 2
        assert len(state["layer_order"]) == 3

    def test_state_partial_fields(self) -> None:
        """Test GenerationState with partial fields (total=False)."""
        state: GenerationState = {}

        state["snapshot_name"] = "partial"
        assert state.get("output_dir") is None
        assert state.get("inventory") is None

    def test_state_field_types(self) -> None:
        """Test that state fields accept correct types."""
        state: GenerationState = {
            "inventory": [{"arn": "arn:aws:ec2:us-east-1:123:instance/i-123", "type": "ec2:instance"}],
            "resource_map": {"vpc-abc": "aws_vpc.main"},
            "layers": {
                "network": [{"name": "vpc"}],
                "security": [{"name": "sg"}],
            },
            "validation_errors": ["Error 1", "Error 2"],
            "generated_files": ["main.tf", "variables.tf"],
            "errors": [{"resource": "test", "message": "failed"}],
            "messages": [{"type": "info", "content": "test"}],
        }

        assert isinstance(state["inventory"], list)
        assert isinstance(state["resource_map"], dict)
        assert isinstance(state["layers"], dict)
        assert isinstance(state["validation_errors"], list)

    def test_state_accumulator_fields(self) -> None:
        """Test that accumulator fields (Annotated with add) work."""
        state: GenerationState = {
            "validation_errors": ["initial error"],
            "generated_files": ["file1.tf"],
            "errors": [{"error": "first"}],
            "messages": [{"msg": "start"}],
        }

        state["validation_errors"].append("second error")
        state["generated_files"].append("file2.tf")
        state["errors"].append({"error": "second"})
        state["messages"].append({"msg": "continue"})

        assert len(state["validation_errors"]) == 2
        assert len(state["generated_files"]) == 2
        assert len(state["errors"]) == 2
        assert len(state["messages"]) == 2


class TestGenerationConfigEnvVariables:
    """Tests specifically for environment variable handling."""

    @pytest.fixture(autouse=True)
    def clean_env(self) -> None:
        """Clean AWSINV_ environment variables before each test."""
        keys_to_remove = [k for k in os.environ if k.startswith("AWSINV_")]
        for key in keys_to_remove:
            del os.environ[key]

    def test_from_env_endpoint_variable(self) -> None:
        """Test AWSINV_AI_ENDPOINT environment variable."""
        with patch.dict(os.environ, {"AWSINV_AI_ENDPOINT": "https://custom-endpoint.com"}):
            config = GenerationConfig.from_env()
            assert config.ai_endpoint == "https://custom-endpoint.com"

    def test_from_env_api_key_variable(self) -> None:
        """Test AWSINV_AI_API_KEY environment variable."""
        with patch.dict(os.environ, {"AWSINV_AI_API_KEY": "secret-api-key-123"}):
            config = GenerationConfig.from_env()
            assert config.ai_api_key == "secret-api-key-123"

    def test_from_env_model_variable(self) -> None:
        """Test AWSINV_AI_MODEL environment variable."""
        with patch.dict(os.environ, {"AWSINV_AI_MODEL": "claude-3-sonnet"}):
            config = GenerationConfig.from_env()
            assert config.ai_model == "claude-3-sonnet"

    def test_from_env_real_world_scenario(self) -> None:
        """Test from_env with realistic configuration."""
        env_vars = {
            "AWSINV_AI_ENDPOINT": "https://api.anthropic.com/v1",
            "AWSINV_AI_API_KEY": "sk-ant-api03-real-key-here",
            "AWSINV_AI_MODEL": "claude-3-5-sonnet-20241022",
        }

        with patch.dict(os.environ, env_vars):
            config = GenerationConfig.from_env()

        assert "anthropic" in config.ai_endpoint
        assert config.ai_api_key.startswith("sk-ant")
        assert "claude" in config.ai_model
