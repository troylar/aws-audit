"""AI-assisted auto-fix for guardrail violations using AWS Bedrock."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Tuple

from .models import Guardrail

logger = logging.getLogger(__name__)


def attempt_auto_fix(
    guardrail: Guardrail,
    resource: Any,
    output_format: str,
    bedrock_client: Optional[Any] = None,
) -> Tuple[bool, Dict[str, Any], str]:
    """Attempt to auto-fix a guardrail violation using AI.

    Args:
        guardrail: The violated guardrail (must have ai_context).
        resource: The resource that violated.
        output_format: Target format (terraform, cdk-typescript, cdk-python).
        bedrock_client: Bedrock client for AI call.

    Returns:
        Tuple of:
        - success: bool - Whether fix was generated.
        - fix: Dict - Configuration changes to apply.
        - description: str - Human-readable fix description.
    """
    # Check prerequisites
    if not guardrail.ai_context:
        return (
            False,
            {},
            "Cannot auto-fix: guardrail has no ai_context defined",
        )

    if bedrock_client is None:
        return (
            False,
            {},
            "Cannot auto-fix: Bedrock client not available",
        )

    # Get resource config
    resource_config = getattr(resource, "config", {}) or {}
    resource_type = getattr(resource, "resource_type", "unknown")
    resource_name = getattr(resource, "name", "unknown")

    try:
        result = _call_bedrock_for_fix(
            bedrock_client=bedrock_client,
            guardrail=guardrail,
            resource_type=resource_type,
            resource_name=resource_name,
            resource_config=resource_config,
            output_format=output_format,
        )

        if result.get("success"):
            return (
                True,
                result.get("fix", {}),
                result.get("description", "Auto-fix applied"),
            )
        else:
            return (
                False,
                {},
                result.get("description", "Auto-fix failed"),
            )

    except Exception as e:
        logger.warning(f"Auto-fix failed for {guardrail.id} on {resource_name}: {e}")
        return (
            False,
            {},
            f"Auto-fix error: {str(e)}",
        )


def _call_bedrock_for_fix(
    bedrock_client: Any,
    guardrail: Guardrail,
    resource_type: str,
    resource_name: str,
    resource_config: Dict[str, Any],
    output_format: str,
) -> Dict[str, Any]:
    """Call Bedrock to generate a fix for the violation.

    Args:
        bedrock_client: Initialized Bedrock client.
        guardrail: The violated guardrail.
        resource_type: Type of the resource.
        resource_name: Name of the resource.
        resource_config: Current resource configuration.
        output_format: Target IaC format.

    Returns:
        Dict with success, fix, and description keys.
    """
    # Build the prompt
    system_prompt = """You are an infrastructure remediation expert. Your task is to generate
configuration changes that fix security/compliance violations.

You must respond with valid JSON in this exact format:
{
    "success": true,
    "fix": { ... configuration object to merge with resource ... },
    "description": "Brief description of what was fixed"
}

If you cannot generate a valid fix, respond with:
{
    "success": false,
    "fix": {},
    "description": "Reason why fix cannot be generated"
}

Only output JSON, no other text."""

    user_prompt = f"""Fix this guardrail violation:

GUARDRAIL: {guardrail.id}
DESCRIPTION: {guardrail.short_description}
SEVERITY: {guardrail.severity.value}

GUARDRAIL CONTEXT:
{guardrail.ai_context}

RESOURCE:
Type: {resource_type}
Name: {resource_name}
Current Config: {json.dumps(resource_config, indent=2, default=str)}

OUTPUT FORMAT: {output_format}

Generate the configuration changes needed to fix this violation."""

    try:
        # Call Bedrock
        response = bedrock_client.invoke_model(
            modelId="us.anthropic.claude-opus-4-20250514-v1:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 2048,
                    "temperature": 0.2,
                    "system": system_prompt,
                    "messages": [
                        {"role": "user", "content": user_prompt},
                    ],
                }
            ),
        )

        # Parse response
        response_body = json.loads(response["body"].read())
        content = response_body.get("content", [{}])[0].get("text", "{}")

        # Try to parse the JSON response
        try:
            result = json.loads(content)
            return result
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            import re

            json_match = re.search(r"\{[\s\S]*\}", content)
            if json_match:
                return json.loads(json_match.group())
            return {
                "success": False,
                "fix": {},
                "description": "Could not parse AI response as JSON",
            }

    except Exception as e:
        logger.error(f"Bedrock API call failed: {e}")
        return {
            "success": False,
            "fix": {},
            "description": f"Bedrock API error: {str(e)}",
        }


def apply_auto_fix(
    resource_config: Dict[str, Any],
    fix: Dict[str, Any],
) -> Dict[str, Any]:
    """Apply an auto-fix to a resource configuration.

    Args:
        resource_config: Original resource configuration.
        fix: Fix configuration to merge.

    Returns:
        Updated resource configuration with fix applied.
    """
    # Deep merge the fix into the config
    result = dict(resource_config)
    _deep_merge(result, fix)
    return result


def _deep_merge(target: Dict[str, Any], source: Dict[str, Any]) -> None:
    """Deep merge source dict into target dict."""
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value
