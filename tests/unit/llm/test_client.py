"""Unit tests for the unified LLM client."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from src.llm.client import DEFAULT_MODELS, LLMClient, LLMConfig


class TestLLMConfig:
    """Tests for LLMConfig."""

    def test_defaults(self) -> None:
        config = LLMConfig()
        assert config.provider == "bedrock"
        assert config.bedrock_model_id == "us.anthropic.claude-opus-4-20250514-v1:0"
        assert config.bedrock_region == "us-east-1"
        assert config.openai_api_key is None
        assert config.openai_model == "gpt-4o"
        assert config.openai_base_url is None

    def test_from_env_defaults(self) -> None:
        env = {k: v for k, v in os.environ.items() if not k.startswith("AWSINV_") and k != "AWS_DEFAULT_REGION"}
        with patch.dict(os.environ, env, clear=True):
            config = LLMConfig.from_env()
        assert config.provider == "bedrock"
        assert config.bedrock_region == "us-east-1"
        assert config.openai_api_key is None
        assert config.openai_model == "gpt-4o"

    def test_from_env_reads_all_vars(self) -> None:
        env = {
            "AWSINV_LLM_PROVIDER": "openai",
            "AWSINV_BEDROCK_MODEL_ID": "anthropic.claude-3-haiku-20240307-v1:0",
            "AWSINV_BEDROCK_REGION": "eu-west-1",
            "AWSINV_OPENAI_API_KEY": "sk-test-key",
            "AWSINV_OPENAI_MODEL": "gpt-4o-mini",
            "AWSINV_OPENAI_BASE_URL": "https://custom.api.example.com",
        }
        with patch.dict(os.environ, env, clear=True):
            config = LLMConfig.from_env()

        assert config.provider == "openai"
        assert config.bedrock_model_id == "anthropic.claude-3-haiku-20240307-v1:0"
        assert config.bedrock_region == "eu-west-1"
        assert config.openai_api_key == "sk-test-key"
        assert config.openai_model == "gpt-4o-mini"
        assert config.openai_base_url == "https://custom.api.example.com"

    def test_from_env_aws_default_region_fallback(self) -> None:
        env = {"AWS_DEFAULT_REGION": "ap-southeast-1"}
        with patch.dict(os.environ, env, clear=True):
            config = LLMConfig.from_env()
        assert config.bedrock_region == "ap-southeast-1"

    def test_from_env_bedrock_region_overrides_aws_default(self) -> None:
        env = {
            "AWSINV_BEDROCK_REGION": "us-west-2",
            "AWS_DEFAULT_REGION": "ap-southeast-1",
        }
        with patch.dict(os.environ, env, clear=True):
            config = LLMConfig.from_env()
        assert config.bedrock_region == "us-west-2"

    def test_get_default_model_bedrock(self) -> None:
        config = LLMConfig(provider="bedrock")
        assert config.get_default_model("generation") == DEFAULT_MODELS["bedrock"]["generation"]
        assert config.get_default_model("evaluation") == DEFAULT_MODELS["bedrock"]["evaluation"]
        assert config.get_default_model("auto_fix") == DEFAULT_MODELS["bedrock"]["auto_fix"]

    def test_get_default_model_openai(self) -> None:
        config = LLMConfig(provider="openai")
        assert config.get_default_model("generation") == DEFAULT_MODELS["openai"]["generation"]
        assert config.get_default_model("evaluation") == DEFAULT_MODELS["openai"]["evaluation"]
        assert config.get_default_model("auto_fix") == DEFAULT_MODELS["openai"]["auto_fix"]

    def test_get_default_model_unknown_task_falls_back_to_generation(self) -> None:
        config = LLMConfig(provider="bedrock")
        assert config.get_default_model("unknown_task") == DEFAULT_MODELS["bedrock"]["generation"]

    def test_get_default_model_unknown_provider_falls_back_to_bedrock(self) -> None:
        config = LLMConfig(provider="unknown")
        assert config.get_default_model("generation") == DEFAULT_MODELS["bedrock"]["generation"]


class TestLLMClientBedrock:
    """Tests for LLMClient with Bedrock provider."""

    def _make_client(self) -> tuple[LLMClient, MagicMock]:
        config = LLMConfig(provider="bedrock", bedrock_region="us-east-1")
        client = LLMClient(config)
        mock_bedrock = MagicMock()
        client._bedrock_client = mock_bedrock
        return client, mock_bedrock

    def test_complete_bedrock(self) -> None:
        client, mock_bedrock = self._make_client()
        mock_bedrock.converse.return_value = {"output": {"message": {"content": [{"text": "Hello from Bedrock"}]}}}

        result = client.complete(
            messages=[{"role": "user", "content": "Hi"}],
            system="You are helpful.",
        )

        assert result == "Hello from Bedrock"
        mock_bedrock.converse.assert_called_once()
        call_kwargs = mock_bedrock.converse.call_args.kwargs
        assert call_kwargs["modelId"] == "us.anthropic.claude-opus-4-20250514-v1:0"
        assert call_kwargs["system"] == [{"text": "You are helpful."}]
        assert call_kwargs["messages"] == [{"role": "user", "content": [{"text": "Hi"}]}]

    def test_complete_bedrock_model_override(self) -> None:
        client, mock_bedrock = self._make_client()
        mock_bedrock.converse.return_value = {"output": {"message": {"content": [{"text": "response"}]}}}

        client.complete(
            messages=[{"role": "user", "content": "Hi"}],
            model_override="anthropic.claude-3-haiku-20240307-v1:0",
        )

        call_kwargs = mock_bedrock.converse.call_args.kwargs
        assert call_kwargs["modelId"] == "anthropic.claude-3-haiku-20240307-v1:0"

    def test_complete_bedrock_no_system(self) -> None:
        client, mock_bedrock = self._make_client()
        mock_bedrock.converse.return_value = {"output": {"message": {"content": [{"text": "response"}]}}}

        client.complete(messages=[{"role": "user", "content": "Hi"}])

        call_kwargs = mock_bedrock.converse.call_args.kwargs
        assert "system" not in call_kwargs

    def test_complete_bedrock_temperature_and_max_tokens(self) -> None:
        client, mock_bedrock = self._make_client()
        mock_bedrock.converse.return_value = {"output": {"message": {"content": [{"text": "response"}]}}}

        client.complete(
            messages=[{"role": "user", "content": "Hi"}],
            temperature=0.7,
            max_tokens=1024,
        )

        call_kwargs = mock_bedrock.converse.call_args.kwargs
        assert call_kwargs["inferenceConfig"]["temperature"] == 0.7
        assert call_kwargs["inferenceConfig"]["maxTokens"] == 1024

    def test_stream_bedrock(self) -> None:
        client, mock_bedrock = self._make_client()
        mock_bedrock.converse_stream.return_value = {
            "stream": [
                {"contentBlockDelta": {"delta": {"text": "Hello "}}},
                {"contentBlockDelta": {"delta": {"text": "world"}}},
                {"contentBlockStop": {}},
            ]
        }

        chunks = list(
            client.stream(
                messages=[{"role": "user", "content": "Hi"}],
                system="Be helpful.",
            )
        )

        assert chunks == ["Hello ", "world"]
        mock_bedrock.converse_stream.assert_called_once()

    def test_stream_bedrock_empty_stream(self) -> None:
        client, mock_bedrock = self._make_client()
        mock_bedrock.converse_stream.return_value = {"stream": []}

        chunks = list(client.stream(messages=[{"role": "user", "content": "Hi"}]))

        assert chunks == []

    def test_stream_bedrock_no_stream_key(self) -> None:
        client, mock_bedrock = self._make_client()
        mock_bedrock.converse_stream.return_value = {}

        chunks = list(client.stream(messages=[{"role": "user", "content": "Hi"}]))

        assert chunks == []

    @patch("boto3.client")
    def test_lazy_bedrock_client_init(self, mock_boto3: MagicMock) -> None:
        config = LLMConfig(provider="bedrock", bedrock_region="eu-west-1")
        client = LLMClient(config)
        assert client._bedrock_client is None

        mock_boto3.return_value = MagicMock()
        mock_boto3.return_value.converse.return_value = {"output": {"message": {"content": [{"text": "ok"}]}}}

        client.complete(messages=[{"role": "user", "content": "Hi"}])

        mock_boto3.assert_called_once_with("bedrock-runtime", region_name="eu-west-1")
        assert client._bedrock_client is not None


class TestLLMClientOpenAI:
    """Tests for LLMClient with OpenAI provider."""

    def _make_client(self) -> tuple[LLMClient, MagicMock]:
        config = LLMConfig(
            provider="openai",
            openai_api_key="sk-test-key",
            openai_model="gpt-4o",
        )
        client = LLMClient(config)
        mock_openai = MagicMock()
        client._openai_client = mock_openai
        return client, mock_openai

    def test_complete_openai(self) -> None:
        client, mock_openai = self._make_client()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello from OpenAI"
        mock_openai.chat.completions.create.return_value = mock_response

        result = client.complete(
            messages=[{"role": "user", "content": "Hi"}],
            system="You are helpful.",
        )

        assert result == "Hello from OpenAI"
        mock_openai.chat.completions.create.assert_called_once()
        call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o"
        assert call_kwargs["messages"] == [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hi"},
        ]

    def test_complete_openai_model_override(self) -> None:
        client, mock_openai = self._make_client()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "response"
        mock_openai.chat.completions.create.return_value = mock_response

        client.complete(
            messages=[{"role": "user", "content": "Hi"}],
            model_override="gpt-4o-mini",
        )

        call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o-mini"

    def test_complete_openai_no_system(self) -> None:
        client, mock_openai = self._make_client()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "response"
        mock_openai.chat.completions.create.return_value = mock_response

        client.complete(messages=[{"role": "user", "content": "Hi"}])

        call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
        assert call_kwargs["messages"] == [
            {"role": "user", "content": "Hi"},
        ]

    def test_stream_openai(self) -> None:
        client, mock_openai = self._make_client()

        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "Hello "

        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta.content = "world"

        chunk3 = MagicMock()
        chunk3.choices = [MagicMock()]
        chunk3.choices[0].delta.content = None

        mock_openai.chat.completions.create.return_value = iter([chunk1, chunk2, chunk3])

        chunks = list(
            client.stream(
                messages=[{"role": "user", "content": "Hi"}],
                system="Be helpful.",
            )
        )

        assert chunks == ["Hello ", "world"]
        call_kwargs = mock_openai.chat.completions.create.call_args.kwargs
        assert call_kwargs["stream"] is True

    def test_stream_openai_empty_choices(self) -> None:
        client, mock_openai = self._make_client()

        chunk = MagicMock()
        chunk.choices = []

        mock_openai.chat.completions.create.return_value = iter([chunk])

        chunks = list(client.stream(messages=[{"role": "user", "content": "Hi"}]))

        assert chunks == []


class TestLLMClientErrors:
    """Tests for LLMClient error handling."""

    def test_openai_missing_package(self) -> None:
        config = LLMConfig(provider="openai", openai_api_key="sk-test")
        client = LLMClient(config)

        with patch("src.llm.client.OPENAI_AVAILABLE", False):
            with pytest.raises(ImportError, match="OpenAI package not installed"):
                client._openai_client = None
                client._get_openai_client()

    def test_openai_missing_api_key(self) -> None:
        config = LLMConfig(provider="openai", openai_api_key=None)
        client = LLMClient(config)

        with patch("src.llm.client.OPENAI_AVAILABLE", True):
            with pytest.raises(ValueError, match="OpenAI API key required"):
                client._get_openai_client()

    def test_provider_property(self) -> None:
        config = LLMConfig(provider="openai")
        client = LLMClient(config)
        assert client.provider == "openai"

    def test_config_property(self) -> None:
        config = LLMConfig(provider="bedrock")
        client = LLMClient(config)
        assert client.config is config

    def test_default_config_from_env(self) -> None:
        env = {k: v for k, v in os.environ.items() if not k.startswith("AWSINV_") and k != "AWS_DEFAULT_REGION"}
        with patch.dict(os.environ, env, clear=True):
            client = LLMClient()
        assert client.provider == "bedrock"
