"""Terraform/CDK generation from inventory using LLM."""

from .layers import RESOURCE_TYPE_TO_LAYER, LayerOrder, LayerStatus
from .state import GenerationConfig, GenerationState

# Core exports available without langgraph
__all__ = [
    "GenerationConfig",
    "GenerationState",
    "LayerOrder",
    "LayerStatus",
    "RESOURCE_TYPE_TO_LAYER",
]

# Optional exports that require langgraph
try:
    from .agent import compile_terraform_agent, create_terraform_graph  # noqa: F401
    from .terraform_generator import GenerationResult, TerraformGenerator, generate_terraform  # noqa: F401

    __all__.extend(
        [
            "GenerationResult",
            "TerraformGenerator",
            "create_terraform_graph",
            "compile_terraform_agent",
            "generate_terraform",
        ]
    )
except ImportError:
    # langgraph not installed - agent functionality unavailable
    pass
