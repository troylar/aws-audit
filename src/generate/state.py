from __future__ import annotations

import os
from dataclasses import dataclass
from operator import add
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional  # noqa: F401 - Optional used in TypedDict

from typing_extensions import Annotated, TypedDict

if TYPE_CHECKING:
    from ..llm import LLMConfig

# Type for progress callback: (event_name, event_data) -> None
ProgressCallback = Callable[[str, Dict[str, Any]], None]

# Global progress callback for nodes to use (set by terraform_generator)
_progress_callback: Optional[ProgressCallback] = None


def set_progress_callback(callback: Optional[ProgressCallback]) -> None:
    """Set the global progress callback for nodes to use."""
    global _progress_callback
    _progress_callback = callback


def get_progress_callback() -> Optional[ProgressCallback]:
    """Get the current progress callback."""
    return _progress_callback


def emit_progress(event: str, data: Dict[str, Any]) -> None:
    """Emit a progress event if callback is set."""
    if _progress_callback:
        _progress_callback(event, data)


def merge_dicts(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two dictionaries, with b taking precedence."""
    result = dict(a) if a else {}
    if b:
        result.update(b)
    return result


class GenerationState(TypedDict, total=False):
    """State container for the IaC generation workflow."""

    snapshot_name: str
    input_file: str  # Path to JSON/YAML export file (alternative to snapshot)
    output_dir: str
    output_format: str  # terraform, cdk-typescript, cdk-python
    inventory: List[Dict[str, Any]]
    resources: List[Any]  # TrackedResource objects from parse_inventory
    resource_map: Dict[str, str]  # live_id -> terraform_ref
    layers: Dict[str, List[Dict[str, Any]]]
    layer_order: List[str]
    current_layer_index: int
    current_layer_status: str
    attempt_count: int
    max_attempts: int
    validation_errors: Annotated[List[str], add]  # accumulates
    generated_code: Annotated[Dict[str, str], merge_dicts]  # accumulates per layer
    generated_files: Annotated[List[str], add]
    lambda_code_paths: Annotated[Dict[str, str], merge_dicts]  # accumulates
    total_resources: int
    processed_resources: int
    comparison_result: Dict[str, Any]  # Structured comparison from AI
    init_success: bool  # Whether terraform init succeeded
    validation_skipped: bool  # Whether validation was skipped (no files to validate)
    errors: Annotated[List[Dict[str, Any]], add]
    messages: Annotated[List[Dict[str, Any]], add]

    # Guardrails fields
    best_practices_enabled: bool  # Whether best-practice advisory guardrails are enabled
    guardrails_enabled: bool  # Whether guardrail evaluation is enabled
    guardrails_policy_path: Optional[str]  # Path to guardrail policy file
    guardrails_environment: str  # Environment name for policy overrides (default: "default")
    guardrails_strict: bool  # Fail on any violation, not just CRITICAL/HIGH
    guardrails_auto_fix: bool  # Whether AI auto-fix is enabled (default: True)
    guardrails_report: Dict[str, Any]  # Serialized GuardrailReport
    guardrails_blocked: bool  # Whether generation was blocked by guardrails
    guardrails_auto_fixes: Dict[str, Dict[str, Any]]  # resource_id -> config changes


@dataclass
class GenerationConfig:
    """Configuration for the IaC generation process."""

    bedrock_model_id: str = "us.anthropic.claude-opus-4-20250514-v1:0"
    bedrock_region: str = "us-east-1"
    temperature: float = 0.2
    max_tokens: int = 4096
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
    provider: str = "bedrock"
    openai_model: str = "gpt-4o"
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None

    @classmethod
    def from_env(cls) -> GenerationConfig:
        """Create a GenerationConfig from environment variables.

        Reads:
            AWSINV_LLM_PROVIDER: LLM provider ("bedrock" or "openai")
            AWSINV_BEDROCK_MODEL_ID: Bedrock model ID
            AWSINV_BEDROCK_REGION: AWS region for Bedrock (default: us-east-1)
            AWS_DEFAULT_REGION: Fallback for Bedrock region
            AWSINV_OPENAI_API_KEY: OpenAI API key
            AWSINV_OPENAI_MODEL: OpenAI model name
            AWSINV_OPENAI_BASE_URL: OpenAI-compatible base URL
        """
        return cls(
            bedrock_model_id=os.environ.get("AWSINV_BEDROCK_MODEL_ID", "us.anthropic.claude-opus-4-20250514-v1:0"),
            bedrock_region=os.environ.get(
                "AWSINV_BEDROCK_REGION",
                os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
            ),
            provider=os.environ.get("AWSINV_LLM_PROVIDER", "bedrock"),
            openai_model=os.environ.get("AWSINV_OPENAI_MODEL", "gpt-4o"),
            openai_api_key=os.environ.get("AWSINV_OPENAI_API_KEY"),
            openai_base_url=os.environ.get("AWSINV_OPENAI_BASE_URL"),
        )

    def to_llm_config(self) -> LLMConfig:
        """Convert to an LLMConfig for use with LLMClient."""
        from ..llm import LLMConfig

        return LLMConfig(
            provider=self.provider,
            bedrock_model_id=self.bedrock_model_id,
            bedrock_region=self.bedrock_region,
            openai_api_key=self.openai_api_key,
            openai_model=self.openai_model,
            openai_base_url=self.openai_base_url,
        )
