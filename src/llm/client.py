"""Unified LLM client supporting AWS Bedrock and OpenAI providers."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None  # type: ignore[assignment, misc]

DEFAULT_MODELS: Dict[str, Dict[str, str]] = {
    "bedrock": {
        "generation": "us.anthropic.claude-opus-4-20250514-v1:0",
        "evaluation": "anthropic.claude-3-haiku-20240307-v1:0",
        "auto_fix": "us.anthropic.claude-opus-4-20250514-v1:0",
    },
    "openai": {
        "generation": "gpt-4o",
        "evaluation": "gpt-4o-mini",
        "auto_fix": "gpt-4o",
    },
}


@dataclass
class LLMConfig:
    """Configuration for the unified LLM client."""

    provider: str = "bedrock"
    bedrock_model_id: str = "us.anthropic.claude-opus-4-20250514-v1:0"
    bedrock_region: str = "us-east-1"
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o"
    openai_base_url: Optional[str] = None

    @classmethod
    def from_env(cls) -> LLMConfig:
        """Create config from environment variables.

        Reads:
            AWSINV_LLM_PROVIDER: "bedrock" (default) or "openai"
            AWSINV_BEDROCK_MODEL_ID: Bedrock model ID
            AWSINV_BEDROCK_REGION: AWS region for Bedrock
            AWS_DEFAULT_REGION: Fallback for Bedrock region
            AWSINV_OPENAI_API_KEY: OpenAI API key
            AWSINV_OPENAI_MODEL: OpenAI model name
            AWSINV_OPENAI_BASE_URL: OpenAI-compatible base URL
        """
        return cls(
            provider=os.environ.get("AWSINV_LLM_PROVIDER", "bedrock"),
            bedrock_model_id=os.environ.get(
                "AWSINV_BEDROCK_MODEL_ID",
                "us.anthropic.claude-opus-4-20250514-v1:0",
            ),
            bedrock_region=os.environ.get(
                "AWSINV_BEDROCK_REGION",
                os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            ),
            openai_api_key=os.environ.get("AWSINV_OPENAI_API_KEY"),
            openai_model=os.environ.get("AWSINV_OPENAI_MODEL", "gpt-4o"),
            openai_base_url=os.environ.get("AWSINV_OPENAI_BASE_URL"),
        )

    def get_default_model(self, task: str) -> str:
        """Get the default model for a given task.

        Args:
            task: One of "generation", "evaluation", "auto_fix".

        Returns:
            Model identifier string.
        """
        provider_defaults = DEFAULT_MODELS.get(self.provider, DEFAULT_MODELS["bedrock"])
        return provider_defaults.get(task, provider_defaults["generation"])


class LLMClient:
    """Unified client for Bedrock and OpenAI LLM calls."""

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self._config = config or LLMConfig.from_env()
        self._bedrock_client: Optional[Any] = None
        self._openai_client: Optional[Any] = None

    @property
    def provider(self) -> str:
        return self._config.provider

    @property
    def config(self) -> LLMConfig:
        return self._config

    def _get_bedrock_client(self) -> Any:
        if self._bedrock_client is None:
            import boto3

            self._bedrock_client = boto3.client(
                "bedrock-runtime",
                region_name=self._config.bedrock_region,
            )
        return self._bedrock_client

    def _get_openai_client(self) -> Any:
        if self._openai_client is None:
            if not OPENAI_AVAILABLE:
                raise ImportError(
                    "OpenAI package not installed. Install with: pip install aws-inventory-manager[openai]"
                )
            if not self._config.openai_api_key:
                raise ValueError("OpenAI API key required. Set AWSINV_OPENAI_API_KEY or pass --openai-api-key.")
            self._openai_client = OpenAI(
                api_key=self._config.openai_api_key,
                base_url=self._config.openai_base_url,
            )
        return self._openai_client

    def complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        model_override: Optional[str] = None,
    ) -> str:
        """Non-streaming completion.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.
            system: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            model_override: Override model for this call.

        Returns:
            Generated text string.
        """
        if self._config.provider == "openai":
            return self._openai_complete(messages, system, temperature, max_tokens, model_override)
        return self._bedrock_complete(messages, system, temperature, max_tokens, model_override)

    def stream(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        model_override: Optional[str] = None,
    ) -> Iterator[str]:
        """Streaming completion yielding text chunks.

        Args:
            messages: List of {"role": ..., "content": ...} dicts.
            system: Optional system prompt.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens to generate.
            model_override: Override model for this call.

        Yields:
            Text chunks as they arrive.
        """
        if self._config.provider == "openai":
            yield from self._openai_stream(messages, system, temperature, max_tokens, model_override)
        else:
            yield from self._bedrock_stream(messages, system, temperature, max_tokens, model_override)

    # --- Bedrock implementation ---

    def _bedrock_complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
        model_override: Optional[str],
    ) -> str:
        client = self._get_bedrock_client()
        model_id = model_override or self._config.bedrock_model_id

        converse_kwargs = self._build_bedrock_kwargs(messages, system, temperature, max_tokens, model_id)
        response = client.converse(**converse_kwargs)
        return response["output"]["message"]["content"][0]["text"] or ""

    def _bedrock_stream(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
        model_override: Optional[str],
    ) -> Iterator[str]:
        client = self._get_bedrock_client()
        model_id = model_override or self._config.bedrock_model_id

        converse_kwargs = self._build_bedrock_kwargs(messages, system, temperature, max_tokens, model_id)
        stream_response = client.converse_stream(**converse_kwargs)

        event_stream = stream_response.get("stream")
        if event_stream:
            for event in event_stream:
                if "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"].get("delta", {})
                    text = delta.get("text")
                    if text:
                        yield text

    def _build_bedrock_kwargs(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
        model_id: str,
    ) -> Dict[str, Any]:
        bedrock_messages = [
            {
                "role": msg["role"],
                "content": [{"text": msg["content"]}],
            }
            for msg in messages
        ]

        kwargs: Dict[str, Any] = {
            "modelId": model_id,
            "messages": bedrock_messages,
            "inferenceConfig": {
                "temperature": temperature,
                "maxTokens": max_tokens,
            },
        }
        if system:
            kwargs["system"] = [{"text": system}]
        return kwargs

    # --- OpenAI implementation ---

    def _openai_complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
        model_override: Optional[str],
    ) -> str:
        client = self._get_openai_client()
        model = model_override or self._config.openai_model

        openai_messages = self._build_openai_messages(messages, system)
        response = client.chat.completions.create(
            model=model,
            messages=openai_messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    def _openai_stream(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str],
        temperature: float,
        max_tokens: int,
        model_override: Optional[str],
    ) -> Iterator[str]:
        client = self._get_openai_client()
        model = model_override or self._config.openai_model

        openai_messages = self._build_openai_messages(messages, system)
        stream = client.chat.completions.create(
            model=model,
            messages=openai_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def _build_openai_messages(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str],
    ) -> List[Dict[str, str]]:
        openai_messages: List[Dict[str, str]] = []
        if system:
            openai_messages.append({"role": "system", "content": system})
        openai_messages.extend(messages)
        return openai_messages
