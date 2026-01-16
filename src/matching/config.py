"""Configuration for resource name normalization."""

import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class NormalizerConfig:
    """Configuration for the resource normalizer."""

    # OpenAI API configuration
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: str = "gpt-4o-mini"

    # Batch settings
    max_batch_size: int = 50
    timeout_seconds: int = 60
    max_retries: int = 3

    # Patterns to detect "random" names that need AI normalization
    random_patterns: List[str] = field(
        default_factory=lambda: [
            r"-[a-f0-9]{8,}$",  # Hex suffix: -a1b2c3d4e5
            r"-[A-Z0-9]{8,}$",  # CloudFormation suffix: -ABCD1234XYZ
            r"_[a-z0-9]{5,}$",  # Underscore suffix (Bedrock): _jnwn1
            r"-\d{10,}$",  # Timestamp suffix: -1704067200
            r"\d{12}",  # Account ID anywhere: 123456789012
            r"^(subnet|vpc|vol|sg|i|rtb|igw|nat|eni)-[a-f0-9]+$",  # AWS resource IDs
        ]
    )

    @classmethod
    def from_env(cls) -> "NormalizerConfig":
        """Load configuration from environment variables.

        Environment variables:
            OPENAI_API_KEY: API key for OpenAI-compatible endpoint
            OPENAI_BASE_URL: Custom API endpoint URL
            OPENAI_MODEL: Model name (default: gpt-4o-mini)
        """
        return cls(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL"),
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        )

    @property
    def is_ai_enabled(self) -> bool:
        """Check if AI normalization is available."""
        return bool(self.api_key)
