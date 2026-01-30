from __future__ import annotations

import os
from dataclasses import dataclass
from operator import add
from typing import Any, Dict, List

from typing_extensions import Annotated, TypedDict


class GenerationState(TypedDict, total=False):
    """State container for the IaC generation workflow."""

    snapshot_name: str
    output_dir: str
    output_format: str  # terraform, cdk-typescript, cdk-python
    inventory: List[Dict[str, Any]]
    resource_map: Dict[str, str]  # live_id -> terraform_ref
    layers: Dict[str, List[Dict[str, Any]]]
    layer_order: List[str]
    current_layer_index: int
    current_layer_status: str
    attempt_count: int
    max_attempts: int
    validation_errors: Annotated[List[str], add]  # accumulates
    generated_code: Dict[str, str]
    generated_files: Annotated[List[str], add]
    lambda_code_paths: Dict[str, str]
    total_resources: int
    processed_resources: int
    errors: Annotated[List[Dict[str, Any]], add]
    messages: Annotated[List[Dict[str, Any]], add]


@dataclass
class GenerationConfig:
    """Configuration for the IaC generation process."""

    ai_endpoint: str = "https://api.openai.com/v1"
    ai_api_key: str = ""
    ai_model: str = "gpt-4"
    temperature: float = 0.2
    max_retries: int = 3
    validate_each_layer: bool = True
    terraform_init: bool = True
    output_format: str = "terraform"
    backup_existing: bool = True
    generate_tfvars: bool = True
    generate_outputs: bool = True
    parameterize_env_values: bool = True
    parameterize_sizing: bool = True
    parameterize_naming: bool = True

    @classmethod
    def from_env(cls) -> GenerationConfig:
        """Create a GenerationConfig from environment variables.

        Reads:
            AWSINV_AI_ENDPOINT: AI API endpoint URL
            AWSINV_AI_API_KEY: AI API key
            AWSINV_AI_MODEL: AI model name
        """
        return cls(
            ai_endpoint=os.environ.get("AWSINV_AI_ENDPOINT", "https://api.openai.com/v1"),
            ai_api_key=os.environ.get("AWSINV_AI_API_KEY", ""),
            ai_model=os.environ.get("AWSINV_AI_MODEL", "gpt-4"),
        )
