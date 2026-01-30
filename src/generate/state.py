from __future__ import annotations

import os
from dataclasses import dataclass
from operator import add
from typing import Any, Dict, List

from typing_extensions import Annotated, TypedDict


class GenerationState(TypedDict, total=False):
    """State container for the IaC generation workflow."""

    snapshot_name: str
    input_file: str  # Path to JSON/YAML export file (alternative to snapshot)
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

    bedrock_model_id: str = "anthropic.claude-sonnet-4-20250514-v1:0"
    bedrock_region: str = "us-east-1"
    temperature: float = 0.2
    max_tokens: int = 8000
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
            AWSINV_BEDROCK_MODEL_ID: Bedrock model ID (default: anthropic.claude-sonnet-4-20250514-v1:0)
            AWSINV_BEDROCK_REGION: AWS region for Bedrock (default: us-east-1)
            AWS_DEFAULT_REGION: Fallback for Bedrock region
        """
        return cls(
            bedrock_model_id=os.environ.get("AWSINV_BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-20250514-v1:0"),
            bedrock_region=os.environ.get("AWSINV_BEDROCK_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1")),
        )
