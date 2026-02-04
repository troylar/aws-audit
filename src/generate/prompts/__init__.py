"""AI prompt templates for IaC generation."""

from .terraform import (
    TERRAFORM_SYSTEM_PROMPT,
    format_layer_prompt,
    format_resource_for_prompt,
    format_retry_prompt,
    get_terraform_system_prompt,
)

__all__ = [
    "get_terraform_system_prompt",
    "format_layer_prompt",
    "format_resource_for_prompt",
    "format_retry_prompt",
    "TERRAFORM_SYSTEM_PROMPT",
]

# CDK TypeScript prompts
try:
    from .cdk_typescript import (  # noqa: F401
        CDK_TYPESCRIPT_SYSTEM_PROMPT,
        format_layer_prompt_typescript,
        format_resource_for_cdk_prompt,
        format_retry_prompt_typescript,
        get_cdk_typescript_system_prompt,
    )

    __all__.extend(
        [
            "get_cdk_typescript_system_prompt",
            "format_layer_prompt_typescript",
            "format_resource_for_cdk_prompt",
            "format_retry_prompt_typescript",
            "CDK_TYPESCRIPT_SYSTEM_PROMPT",
        ]
    )
except ImportError:
    pass

# CDK Python prompts
try:
    from .cdk_python import (  # noqa: F401
        CDK_PYTHON_SYSTEM_PROMPT,
        format_layer_prompt_python,
        format_retry_prompt_python,
        get_cdk_python_system_prompt,
    )

    __all__.extend(
        [
            "get_cdk_python_system_prompt",
            "format_layer_prompt_python",
            "format_retry_prompt_python",
            "CDK_PYTHON_SYSTEM_PROMPT",
        ]
    )
except ImportError:
    pass
