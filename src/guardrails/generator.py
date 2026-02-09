"""AI-powered guardrail generation from natural language descriptions."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from .models import Action, Guardrail, Severity

logger = logging.getLogger(__name__)

# Prompt template for generating guardrails
GENERATE_GUARDRAIL_PROMPT = """You are an AWS security expert creating guardrails for infrastructure compliance.

Generate a guardrail based on this requirement:
"{requirement}"

The guardrail should use formula-based conditions with this syntax:
- Simple checks: "Encryption exists", "Tags.Environment == 'prod'"
- Boolean logic: "Encryption exists and Versioning.Status == 'Enabled'"
- If/then: "if PublicAccess then Encryption exists"
- Array iteration: "all(rule.Description exists for rule in IpPermissions)"
- Counts: "count(AvailabilityZones) >= 2"
- Negation: "not Tags.test exists"

Available functions: exists(), count(), matches(), contains(), get(), all(), any()

For AI-based rules (complex logic that can't be expressed in formula), use:
- ai_fail_if: For critical/high severity violations that should block
- ai_warn_if: For medium severity warnings
- ai_notify_if: For low/info notifications

Respond ONLY with valid JSON (no markdown):
{{
  "id": "GR-XXX-NNN",
  "short_description": "Brief description (max 100 chars)",
  "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
  "action": "BLOCK|WARN|AUTO-FIX",
  "applies_to": ["resource:type", ...],
  "condition": "formula string OR null if using AI rule",
  "ai_fail_if": "AI rule text OR null if using condition",
  "ai_warn_if": null,
  "ai_notify_if": null,
  "ai_context": "Context for auto-fix (WHY + HOW TO FIX)",
  "tags": ["security", "encryption", ...]
}}

Category codes for ID:
- ENC: Encryption
- NET: Network/Security Groups
- IAM: IAM/Access
- LOG: Logging/Monitoring
- TAG: Tagging
- HA: High Availability
- COST: Cost optimization
- DATA: Data protection
- SEC: General security"""

GENERATE_BATCH_PROMPT = """You are an AWS security expert creating guardrails for infrastructure compliance.

Generate multiple guardrails based on this policy description:
"{description}"

{context}

Generate {count} guardrails covering the key security requirements.

Use formula-based conditions with this syntax:
- Simple checks: "Encryption exists", "Tags.Environment == 'prod'"
- Boolean logic: "Encryption exists and Versioning.Status == 'Enabled'"
- If/then: "if PublicAccess then Encryption exists"
- Array iteration: "all(rule.Description exists for rule in IpPermissions)"
- Counts: "count(AvailabilityZones) >= 2"

For complex logic that can't be expressed in formula, use ai_fail_if/ai_warn_if/ai_notify_if.

Respond ONLY with valid JSON array (no markdown):
[
  {{
    "id": "GR-XXX-NNN",
    "short_description": "Brief description",
    "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
    "action": "BLOCK|WARN|AUTO-FIX",
    "applies_to": ["resource:type"],
    "condition": "formula OR null",
    "ai_fail_if": "AI rule OR null",
    "ai_context": "WHY + HOW TO FIX",
    "tags": ["tag1", "tag2"]
  }},
  ...
]"""


TRANSLATE_RULES_PROMPT = """You are an AWS security expert creating guardrails for infrastructure compliance.

Translate the following rules into guardrails. Each rule becomes exactly one guardrail.
{instructions}
Rules:
{rules}

Use formula-based conditions with this syntax:
- Simple checks: "Encryption exists", "Tags.Environment == 'prod'"
- Boolean logic: "Encryption exists and Versioning.Status == 'Enabled'"
- If/then: "if PublicAccess then Encryption exists"
- Array iteration: "all(rule.Description exists for rule in IpPermissions)"
- Counts: "count(AvailabilityZones) >= 2"

For complex logic that can't be expressed in formula, use ai_fail_if/ai_warn_if/ai_notify_if.

Respond ONLY with valid JSON array (no markdown):
[
  {{
    "id": "GR-XXX-NNN",
    "short_description": "Brief description",
    "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
    "action": "BLOCK|WARN|AUTO-FIX",
    "applies_to": ["resource:type"],
    "condition": "formula OR null",
    "ai_fail_if": "AI rule OR null",
    "ai_context": "WHY + HOW TO FIX",
    "tags": ["tag1", "tag2"]
  }},
  ...
]"""

_TRANSLATE_BATCH_SIZE = 10


def translate_rules_to_guardrails(
    rules: List[str],
    instructions: Optional[str] = None,
    bedrock_client: Optional[Any] = None,
) -> List[Guardrail]:
    """Translate a list of rule strings into guardrails using AI.

    Processes rules in batches of 10 per API call.

    Args:
        rules: List of rule strings to translate.
        instructions: Optional instructions for interpretation.
        bedrock_client: Bedrock client for AI generation.

    Returns:
        List of successfully translated Guardrail objects.
    """
    if bedrock_client is None:
        logger.error("Bedrock client required for guardrail generation")
        return []

    if not rules:
        return []

    all_guardrails: List[Guardrail] = []
    instructions_text = f"\nAdditional instructions: {instructions}" if instructions else ""

    for i in range(0, len(rules), _TRANSLATE_BATCH_SIZE):
        batch = rules[i : i + _TRANSLATE_BATCH_SIZE]
        numbered_rules = "\n".join(f"{idx + 1}. {rule}" for idx, rule in enumerate(batch))

        prompt = TRANSLATE_RULES_PROMPT.format(
            instructions=instructions_text,
            rules=numbered_rules,
        )

        try:
            response = bedrock_client.invoke_model(
                modelId="anthropic.claude-3-haiku-20240307-v1:0",
                contentType="application/json",
                accept="application/json",
                body=json.dumps(
                    {
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 4096,
                        "messages": [{"role": "user", "content": prompt}],
                    }
                ),
            )

            response_body = json.loads(response["body"].read())
            content = response_body.get("content", [{}])[0].get("text", "[]")

            guardrails_list = json.loads(content)
            for g_dict in guardrails_list:
                guardrail = _dict_to_guardrail(g_dict)
                if guardrail:
                    all_guardrails.append(guardrail)
        except Exception as e:
            logger.warning(f"Failed to translate batch starting at rule {i + 1}: {e}")

    return all_guardrails


def generate_guardrail(
    requirement: str,
    bedrock_client: Optional[Any] = None,
) -> Optional[Guardrail]:
    """Generate a single guardrail from a natural language requirement.

    Args:
        requirement: Natural language description of the requirement.
        bedrock_client: Bedrock client for AI generation.

    Returns:
        Guardrail object or None if generation fails.
    """
    if bedrock_client is None:
        logger.error("Bedrock client required for guardrail generation")
        return None

    try:
        prompt = GENERATE_GUARDRAIL_PROMPT.format(requirement=requirement)

        response = bedrock_client.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                }
            ),
        )

        response_body = json.loads(response["body"].read())
        content = response_body.get("content", [{}])[0].get("text", "{}")

        # Parse JSON response
        guardrail_dict = json.loads(content)
        return _dict_to_guardrail(guardrail_dict)

    except Exception as e:
        logger.error(f"Failed to generate guardrail: {e}")
        return None


def generate_guardrails_batch(
    description: str,
    count: int = 5,
    resource_types: Optional[List[str]] = None,
    bedrock_client: Optional[Any] = None,
) -> List[Guardrail]:
    """Generate multiple guardrails from a policy description.

    Args:
        description: High-level policy description.
        count: Number of guardrails to generate.
        resource_types: Optional list of resource types to focus on.
        bedrock_client: Bedrock client for AI generation.

    Returns:
        List of Guardrail objects.
    """
    if bedrock_client is None:
        logger.error("Bedrock client required for guardrail generation")
        return []

    try:
        context = ""
        if resource_types:
            context = f"Focus on these resource types: {', '.join(resource_types)}"

        prompt = GENERATE_BATCH_PROMPT.format(
            description=description,
            count=count,
            context=context,
        )

        response = bedrock_client.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}],
                }
            ),
        )

        response_body = json.loads(response["body"].read())
        content = response_body.get("content", [{}])[0].get("text", "[]")

        # Parse JSON response
        guardrails_list = json.loads(content)
        return [_dict_to_guardrail(g) for g in guardrails_list if g]

    except Exception as e:
        logger.error(f"Failed to generate guardrails: {e}")
        return []


def generate_guardrail_from_violation(
    resource_type: str,
    resource_config: Dict[str, Any],
    violation_description: str,
    bedrock_client: Optional[Any] = None,
) -> Optional[Guardrail]:
    """Generate a guardrail based on an observed violation.

    Useful for learning from existing issues and creating preventive rules.

    Args:
        resource_type: Type of the resource with the violation.
        resource_config: Configuration of the violating resource.
        violation_description: Description of what's wrong.
        bedrock_client: Bedrock client for AI generation.

    Returns:
        Guardrail object that would catch this violation.
    """
    if bedrock_client is None:
        logger.error("Bedrock client required for guardrail generation")
        return None

    try:
        prompt = f"""You are an AWS security expert. A violation was observed:

Resource Type: {resource_type}
Violation: {violation_description}

Resource Configuration (sample):
{json.dumps(resource_config, indent=2, default=str)[:2000]}

Create a guardrail that would prevent this violation in the future.

Respond ONLY with valid JSON:
{{
  "id": "GR-XXX-NNN",
  "short_description": "Brief description",
  "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO",
  "action": "BLOCK|WARN|AUTO-FIX",
  "applies_to": ["{resource_type}"],
  "condition": "formula to detect this violation",
  "ai_context": "WHY this is bad + HOW TO FIX",
  "tags": ["tag1", "tag2"]
}}"""

        response = bedrock_client.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps(
                {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}],
                }
            ),
        )

        response_body = json.loads(response["body"].read())
        content = response_body.get("content", [{}])[0].get("text", "{}")

        guardrail_dict = json.loads(content)
        return _dict_to_guardrail(guardrail_dict)

    except Exception as e:
        logger.error(f"Failed to generate guardrail from violation: {e}")
        return None


def _dict_to_guardrail(g_dict: Dict[str, Any]) -> Optional[Guardrail]:
    """Convert a dictionary to a Guardrail object."""
    try:
        return Guardrail(
            id=g_dict.get("id", "GR-GEN-001"),
            short_description=g_dict.get("short_description", "")[:100],
            severity=Severity(g_dict.get("severity", "MEDIUM")),
            action=Action(g_dict.get("action", "WARN")),
            applies_to=g_dict.get("applies_to", ["*"]),
            condition=g_dict.get("condition"),
            ai_fail_if=g_dict.get("ai_fail_if"),
            ai_warn_if=g_dict.get("ai_warn_if"),
            ai_notify_if=g_dict.get("ai_notify_if"),
            ai_context=g_dict.get("ai_context", ""),
            enabled=True,
            tags=g_dict.get("tags", []),
        )
    except Exception as e:
        logger.error(f"Failed to parse guardrail dict: {e}")
        return None


def guardrail_to_yaml(guardrail: Guardrail) -> str:
    """Convert a Guardrail to YAML format for easy copy-paste.

    Args:
        guardrail: Guardrail object.

    Returns:
        YAML string representation.
    """
    lines = [
        f"- id: {guardrail.id}",
        f"  short_description: {guardrail.short_description}",
        f"  severity: {guardrail.severity.value}",
        f"  action: {guardrail.action.value}",
        "  applies_to:",
    ]

    for resource_type in guardrail.applies_to:
        lines.append(f"    - {resource_type}")

    if guardrail.condition:
        # Quote the condition if it contains special characters
        if any(c in guardrail.condition for c in ":#{}[]"):
            lines.append(f'  condition: "{guardrail.condition}"')
        else:
            lines.append(f"  condition: {guardrail.condition}")
    elif guardrail.ai_fail_if:
        lines.append("  ai_fail_if: |")
        for line in guardrail.ai_fail_if.split("\n"):
            lines.append(f"    {line}")
    elif guardrail.ai_warn_if:
        lines.append("  ai_warn_if: |")
        for line in guardrail.ai_warn_if.split("\n"):
            lines.append(f"    {line}")
    elif guardrail.ai_notify_if:
        lines.append("  ai_notify_if: |")
        for line in guardrail.ai_notify_if.split("\n"):
            lines.append(f"    {line}")

    if guardrail.ai_context:
        lines.append("  ai_context: |")
        for line in guardrail.ai_context.split("\n"):
            lines.append(f"    {line}")

    if guardrail.tags:
        lines.append(f"  tags: {guardrail.tags}")

    return "\n".join(lines)
