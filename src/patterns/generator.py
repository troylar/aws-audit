"""AI-powered pattern generation using Bedrock."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Any, List, Optional

from .models import Pattern

if TYPE_CHECKING:
    from .models import ComparisonReport

logger = logging.getLogger(__name__)

MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
ANTHROPIC_VERSION = "bedrock-2023-05-31"
MAX_TOKENS = 2048

GENERATE_FROM_DESCRIPTION_PROMPT = """\
You are an AWS infrastructure architect. \
Generate an infrastructure pattern from this description.

Description: "{description}"
{instructions_block}
Respond ONLY with valid JSON (no markdown, no code fences). The JSON must match this exact schema:

{{
  "name": "short-kebab-case-name",
  "description": "Human-readable description of the pattern",
  "version": 1,
  "tags": ["tag1", "tag2"],
  "owner": "",
  "resources": [
    {{
      "type": "service:resource",
      "count": 1,
      "description": "What this resource does",
      "expect": {{
        "config_key": "expected_value"
      }}
    }}
  ],
  "guardrails": []
}}

Rules:
- resource type must be in "service:resource" format (e.g., "lambda:function", "s3:bucket", "ec2:instance")
- count must be >= 1
- expect keys must be valid dotted-path config fields (alphanumeric + dots)
- name must be kebab-case, concise"""

GENERATE_FROM_SNAPSHOT_PROMPT = """\
You are an AWS infrastructure architect. \
Generate a reusable infrastructure pattern from this snapshot of AWS resources.

Snapshot: "{snapshot_name}"

Resource summary:
{resource_summary}
{guardrails_block}{instructions_block}
Respond ONLY with valid JSON (no markdown, no code fences). The JSON must match this exact schema:

{{
  "name": "short-kebab-case-name",
  "description": "Human-readable description of the pattern",
  "version": 1,
  "tags": ["tag1", "tag2"],
  "owner": "",
  "resources": [
    {{
      "type": "service:resource",
      "count": 1,
      "description": "What this resource does",
      "expect": {{
        "config_key": "expected_value"
      }}
    }}
  ],
  "guardrails": [],
  "source_snapshot": "{snapshot_name}"
}}

Rules:
- resource type must be in "service:resource" format (e.g., "lambda:function", "s3:bucket")
- count must be >= 1
- expect keys must be valid dotted-path config fields
- name must be kebab-case, concise
- Derive expect values from the actual resource configurations shown above"""

GENERATE_GUIDANCE_PROMPT = """\
You are an AWS infrastructure advisor. \
Based on this comparison report, provide actionable guidance.

Snapshot: "{snapshot_name}"
Threshold: {threshold}

Matches:
{matches_summary}

Provide concise, actionable guidance on:
1. How well the snapshot aligns with the matched patterns
2. Key violations or mismatches to address
3. Recommended next steps

Keep your response under 500 words. Be specific and reference resource types and config keys where relevant."""


def _invoke_bedrock(
    bedrock_client: Any,
    prompt: str,
    max_tokens: int = MAX_TOKENS,
) -> str:
    """Invoke Bedrock model and return the text content."""
    response = bedrock_client.invoke_model(
        modelId=MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(
            {
                "anthropic_version": ANTHROPIC_VERSION,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
        ),
    )
    response_body = json.loads(response["body"].read())
    return response_body.get("content", [{}])[0].get("text", "")


def generate_from_description(
    description: str,
    instructions: Optional[str] = None,
    bedrock_client: Optional[Any] = None,
) -> Pattern:
    """Generate a pattern from a text description using Bedrock.

    Args:
        description: Natural language description of the desired pattern.
        instructions: Optional additional instructions for the AI.
        bedrock_client: Bedrock runtime client.

    Returns:
        Generated Pattern object.

    Raises:
        ValueError: If bedrock_client is None or generation fails.
    """
    if bedrock_client is None:
        raise ValueError("Bedrock credentials required for pattern generation.")

    instructions_block = ""
    if instructions:
        instructions_block = f"\nAdditional instructions: {instructions}\n"

    prompt = GENERATE_FROM_DESCRIPTION_PROMPT.format(
        description=description,
        instructions_block=instructions_block,
    )

    content = _invoke_bedrock(bedrock_client, prompt)
    pattern_dict = json.loads(content)
    return Pattern.from_dict(pattern_dict)


def generate_from_snapshot(
    snapshot_name: str,
    instructions: Optional[str] = None,
    guardrail_names: Optional[List[str]] = None,
    bedrock_client: Optional[Any] = None,
) -> Pattern:
    """Generate a pattern from an existing snapshot using Bedrock.

    Args:
        snapshot_name: Name of the snapshot to derive pattern from.
        instructions: Optional additional instructions for the AI.
        guardrail_names: Guardrail names whose covered properties should be
            excluded from expect fields.
        bedrock_client: Bedrock runtime client.

    Returns:
        Generated Pattern object.

    Raises:
        ValueError: If bedrock_client is None or generation fails.
    """
    if bedrock_client is None:
        raise ValueError("Bedrock credentials required for pattern generation.")

    from ..snapshot.storage import SnapshotStorage

    storage = SnapshotStorage()
    snapshot = storage.load_snapshot(snapshot_name)

    type_groups: dict[str, list[Any]] = defaultdict(list)
    for resource in snapshot.resources:
        rtype = resource.resource_type if isinstance(resource.resource_type, str) else str(resource.resource_type)
        type_groups[rtype].append(resource)

    summary_lines: list[str] = []
    for rtype, resources in sorted(type_groups.items()):
        summary_lines.append(f"- {rtype}: {len(resources)} instance(s)")
        sample = resources[0]
        if hasattr(sample, "raw_config") and sample.raw_config:
            config_preview = json.dumps(sample.raw_config, default=str)
            if len(config_preview) > 300:
                config_preview = config_preview[:300] + "..."
            summary_lines.append(f"  Sample config: {config_preview}")

    resource_summary = "\n".join(summary_lines) if summary_lines else "(no resources)"

    guardrails_block = ""
    if guardrail_names:
        guardrails_block = (
            f"\nThe following guardrails are already applied: {', '.join(guardrail_names)}\n"
            "Do NOT include expect fields that duplicate checks covered by these guardrails.\n"
        )

    instructions_block = ""
    if instructions:
        instructions_block = f"\nAdditional instructions: {instructions}\n"

    prompt = GENERATE_FROM_SNAPSHOT_PROMPT.format(
        snapshot_name=snapshot_name,
        resource_summary=resource_summary,
        guardrails_block=guardrails_block,
        instructions_block=instructions_block,
    )

    content = _invoke_bedrock(bedrock_client, prompt)
    pattern_dict = json.loads(content)
    pattern = Pattern.from_dict(pattern_dict)
    pattern.source_snapshot = snapshot_name
    if snapshot.account_id:
        pattern.source_account = snapshot.account_id
    return pattern


def generate_guidance(
    report: "ComparisonReport",
    bedrock_client: Optional[Any] = None,
) -> str:
    """Generate actionable guidance text from a ComparisonReport.

    Args:
        report: The comparison report to generate guidance for.
        bedrock_client: Bedrock runtime client.

    Returns:
        Guidance string. Empty string if Bedrock is unavailable or call fails.
    """
    if bedrock_client is None:
        return ""

    try:
        matches_lines: list[str] = []
        for match in report.matches:
            matches_lines.append(f"Pattern: {match.pattern.name} (score: {match.score:.2f})")
            if match.aligned:
                matches_lines.append(f"  Aligned: {match.aligned}")
            if match.missing:
                matches_lines.append(f"  Missing: {match.missing}")
            if match.extra:
                matches_lines.append(f"  Extra: {match.extra}")
            if match.expect_violations:
                for v in match.expect_violations:
                    matches_lines.append(
                        f"  Violation: {v.resource_type}/{v.resource_name} "
                        f"- {v.config_key}: expected={v.expected_value}, actual={v.actual_value}"
                    )
            if match.guardrail_violations:
                for gv in match.guardrail_violations:
                    matches_lines.append(
                        f"  Guardrail: {gv.guardrail_name} on {gv.resource_type}/{gv.resource_name} - {gv.detail}"
                    )

        matches_summary = "\n".join(matches_lines) if matches_lines else "(no matches)"

        prompt = GENERATE_GUIDANCE_PROMPT.format(
            snapshot_name=report.snapshot_name,
            threshold=report.threshold,
            matches_summary=matches_summary,
        )

        return _invoke_bedrock(bedrock_client, prompt)
    except Exception:
        logger.debug("Bedrock guidance generation failed", exc_info=True)
        return ""
