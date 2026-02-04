"""LangGraph node for evaluating guardrails against inventory resources."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from ..state import GenerationState, emit_progress

logger = logging.getLogger(__name__)


def _get_bedrock_client() -> Optional[Any]:
    """Get a Bedrock runtime client for auto-fix.

    Returns:
        boto3 Bedrock runtime client, or None if unavailable.
    """
    try:
        import boto3

        return boto3.client("bedrock-runtime")
    except Exception as e:
        logger.warning(f"Failed to create Bedrock client for auto-fix: {e}")
        return None


def evaluate_guardrails(state: GenerationState) -> Dict[str, Any]:
    """LangGraph node that evaluates guardrails against resources.

    Reads from state:
        - resources: List[TrackedResource] - Parsed resources
        - guardrails_enabled: bool - Whether guardrails are enabled
        - guardrails_policy_path: str - Path to policy file
        - guardrails_environment: str - Environment for overrides
        - guardrails_strict: bool - Fail on any violation
        - guardrails_auto_fix: bool - Whether to enable AI auto-fix
        - output_format: str - Target output format

    Writes to state:
        - guardrails_report: Dict - Serialized GuardrailReport
        - guardrails_blocked: bool - Whether to block generation
        - guardrails_auto_fixes: Dict - Fixes to apply to resources

    Returns:
        State updates dictionary.
    """
    # Check if guardrails are enabled
    guardrails_enabled = state.get("guardrails_enabled", False)
    if not guardrails_enabled:
        return {
            "guardrails_blocked": False,
            "guardrails_report": None,
            "guardrails_auto_fixes": {},
        }

    # Import here to avoid circular imports and loading if not needed
    from src.guardrails import GuardrailEvaluator, load_builtin_guardrails, load_policy
    from src.guardrails.models import EvaluationResult, GuardrailPolicy

    resources = state.get("resources", [])
    policy_path = state.get("guardrails_policy_path")
    environment = state.get("guardrails_environment", "default")
    strict_mode = state.get("guardrails_strict", False)
    auto_fix_enabled = state.get("guardrails_auto_fix", True)
    snapshot_name = state.get("snapshot_name", "")
    output_format = state.get("output_format", "terraform")

    emit_progress("guardrails_start", {"total_resources": len(resources)})

    # Load policy
    if policy_path:
        policy = load_policy(policy_path, environment=environment)
    else:
        # Use built-in guardrails
        builtin = load_builtin_guardrails()
        policy = GuardrailPolicy(
            name="builtin",
            version="1.0",
            description="Built-in guardrails",
            guardrails=builtin,
        )

    # Get Bedrock client for auto-fix if enabled
    bedrock_client = None
    if auto_fix_enabled:
        bedrock_client = _get_bedrock_client()
        if bedrock_client:
            logger.info("Auto-fix enabled with Bedrock AI")
        else:
            logger.warning("Auto-fix requested but Bedrock client unavailable")

    # Create evaluator
    evaluator = GuardrailEvaluator(
        policy=policy,
        auto_fix_enabled=auto_fix_enabled and bedrock_client is not None,
        bedrock_client=bedrock_client,
        environment=environment,
        output_format=output_format,
    )

    # Progress callback
    def progress_callback(current: int, total: int) -> None:
        emit_progress("guardrails_progress", {"current": current, "total": total})

    # Evaluate all resources
    report = evaluator.evaluate_all(
        resources=resources,
        snapshot_name=snapshot_name,
        progress_callback=progress_callback,
    )

    # Determine if blocked
    blocked = False

    if strict_mode:
        # In strict mode, any failure blocks
        failed_evals = [e for e in report.evaluations if e.result == EvaluationResult.FAIL]
        if failed_evals:
            blocked = True
            report.blocked = True
            report.block_reason = f"Strict mode: {len(failed_evals)} violations found"
    else:
        # Normal mode: only CRITICAL/HIGH with BLOCK action blocks
        blocked = report.blocked

    # Get auto-fixes (placeholder for future implementation)
    auto_fixes = evaluator.get_auto_fixes()

    emit_progress(
        "guardrails_complete",
        {
            "passed": report.summary.passed,
            "failed": report.summary.failed,
            "auto_fixed": report.summary.auto_fixed,
            "blocked": blocked,
        },
    )

    return {
        "guardrails_blocked": blocked,
        "guardrails_report": report.to_dict(),
        "guardrails_auto_fixes": auto_fixes,
    }
