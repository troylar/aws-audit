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
    from .agent import (  # noqa: F401  # noqa: F401
        compile_cdk_agent,
        compile_terraform_agent,
        create_cdk_graph,
        create_terraform_graph,
    )
    from .terraform_generator import (  # noqa: F401
        GenerationResult,
        TerraformGenerator,
        generate_terraform,
    )

    __all__.extend(
        [
            "GenerationResult",
            "TerraformGenerator",
            "create_terraform_graph",
            "compile_terraform_agent",
            "create_cdk_graph",
            "compile_cdk_agent",
            "generate_terraform",
        ]
    )

    # CDK generator exports (when CDKGenerator is implemented)
    try:
        from .cdk_generator import CDKGenerator, generate_cdk  # noqa: F401

        __all__.extend(
            [
                "CDKGenerator",
                "generate_cdk",
            ]
        )
    except ImportError:
        # CDK generator not yet implemented
        pass

except ImportError:
    # langgraph not installed - agent functionality unavailable
    pass
